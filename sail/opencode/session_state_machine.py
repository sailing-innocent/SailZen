# -*- coding: utf-8 -*-
# @file session_state_machine.py
# @brief Explicit state machine for opencode session interaction.
# @author sailing-innocent
# @date 2026-05-31
# @version 1.0
# ---------------------------------

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set

from sail.opencode.client import OpencodeAsyncClient
from sail.opencode.session_dependencies import SessionRunDependencies
from sail.opencode.session_fallbacks import (
    fetch_final_message,
    poll_until_idle,
    snapshot_message_ids,
)
from sail.opencode.session_handlers import (
    DEFAULT_EVENT_HANDLERS,
    EventHandler,
    SessionAccumulator,
)
from sail.opencode.session_models import TaskResult, TaskRunConfig
from sail.opencode.sse_parser import EventType, parse_event

logger = logging.getLogger(__name__)


class SessionRunState(str, Enum):
    INIT = "init"
    HEALTH_CHECK = "health_check"
    SESSION_READY = "session_ready"
    AGENT_READY = "agent_ready"
    SNAPSHOT_READY = "snapshot_ready"
    PROMPT_SENT = "prompt_sent"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SessionStateMachine:
    """Run one opencode task through explicit interaction states."""

    client: OpencodeAsyncClient
    prompt: str
    cfg: TaskRunConfig
    deps: SessionRunDependencies
    label: str = "task"
    started_at: float = field(default_factory=time.time)
    handlers: Dict[EventType, EventHandler] = field(
        default_factory=lambda: dict(DEFAULT_EVENT_HANDLERS)
    )

    state: SessionRunState = SessionRunState.INIT
    session_id: str = ""
    agent_name: Optional[str] = None
    pre_existing_ids: Set[str] = field(default_factory=set)
    accumulator: SessionAccumulator = field(default_factory=SessionAccumulator)
    delayed_finish_started_at: float = 0.0
    delayed_finish_last_event_at: float = 0.0
    delayed_finish_last_heartbeat_at: float = 0.0
    delayed_finish_heartbeats_sent: int = 0

    async def run(self) -> TaskResult:
        try:
            await self._health_check()
            await self._ensure_session()
            await self._resolve_agent()
            await self._snapshot_messages()
            await self._send_prompt()
            result = await self._stream_until_done()
            result.agent_used = self.agent_name
            return result
        except asyncio.CancelledError:
            self.state = SessionRunState.FAILED
            return self._fail("任务被取消")
        except Exception as exc:
            self.state = SessionRunState.FAILED
            return self._fail(str(exc))

    async def _health_check(self) -> None:
        self.state = SessionRunState.HEALTH_CHECK
        healthy = await self.client.health_check()
        if not healthy:
            raise RuntimeError(
                f"服务不可用: {self.cfg.host}:{self.cfg.port}"
            )

    async def _ensure_session(self) -> None:
        self.state = SessionRunState.SESSION_READY
        if self.cfg.session_id:
            self.session_id = self.cfg.session_id
            return
        title = self.cfg.session_title or f"SailZen {self.label}"
        session = await self.client.create_session(title=title)
        self.session_id = session.id
        logger.info("[%s] 创建 session: %s", self.label, self.session_id[:16])

    async def _resolve_agent(self) -> None:
        self.state = SessionRunState.AGENT_READY
        if self.cfg.auto_discover_agent:
            self.agent_name = await self.deps.agent_resolver.resolve(
                self.client,
                self.cfg.agent,
                self.label,
            )
        else:
            self.agent_name = self.cfg.agent

    async def _snapshot_messages(self) -> None:
        self.state = SessionRunState.SNAPSHOT_READY
        self.pre_existing_ids = await snapshot_message_ids(
            self.client,
            self.session_id,
        )
        logger.debug(
            "[%s] 快照 %d 条已有消息",
            self.label,
            len(self.pre_existing_ids),
        )

    async def _send_prompt(self) -> None:
        self.state = SessionRunState.PROMPT_SENT
        prompt_brief = (
            self.prompt[:80] + "..." + self.prompt[-80:]
            if len(self.prompt) > 160
            else self.prompt
        )
        logger.info(
            "[%s] 发送 prompt (agent=%s): %s",
            self.label,
            self.agent_name or "default",
            prompt_brief,
        )
        ok = await self.client.send_prompt_async(
            self.session_id,
            self.prompt,
            agent=self.agent_name,
            model=self.cfg.model,
        )
        if not ok:
            raise RuntimeError("prompt 被服务器拒绝 (非 204)")

    async def _stream_until_done(self) -> TaskResult:
        self.state = SessionRunState.STREAMING
        queue: asyncio.Queue = asyncio.Queue()
        reader = asyncio.create_task(self._read_sse_events(queue))
        watchdog = asyncio.create_task(self._delayed_finish_watchdog_loop())
        try:
            while True:
                get_event = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    {get_event, reader, watchdog},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    if task is get_event:
                        task.cancel()

                if watchdog in done:
                    watchdog.result()
                if reader in done:
                    error = reader.result()
                    if error:
                        raise error
                    return await self._stream_ended_result()
                if get_event in done:
                    raw_event = get_event.result()
                    result = await self._handle_raw_event(raw_event)
                    if result:
                        return result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self.cfg.poll_fallback:
                raise RuntimeError(f"SSE 错误: {exc}") from exc
            logger.warning("[%s] SSE 异常，降级轮询: %s", self.label, exc)
            text = await poll_until_idle(
                self.client,
                self.session_id,
                self.pre_existing_ids,
                timeout=self.cfg.sse_timeout,
                started_at=self.started_at,
            )
            self.accumulator.text = text
            self.state = SessionRunState.COMPLETED
            return self._success("poll_fallback")
        finally:
            reader.cancel()
            watchdog.cancel()
            await asyncio.gather(reader, watchdog, return_exceptions=True)

    async def _read_sse_events(self, queue: asyncio.Queue) -> Optional[BaseException]:
        logger.info("[%s] SSE reader started", self.label)
        event_count = 0
        try:
            async for raw_event in self.client.stream_events_robust(
                self.session_id,
                timeout=self.cfg.sse_timeout,
                max_reconnects=self.cfg.max_reconnects,
            ):
                event_count += 1
                if event_count == 1 or event_count % 50 == 0:
                    logger.info(
                        "[%s] SSE reader received events=%d queue=%d",
                        self.label,
                        event_count,
                        queue.qsize(),
                    )
                await queue.put(raw_event)
            logger.info("[%s] SSE reader ended after events=%d", self.label, event_count)
            return None
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            return exc
        finally:
            logger.info("[%s] SSE reader stopped after events=%d", self.label, event_count)

    async def _handle_raw_event(self, raw_event) -> Optional[TaskResult]:
        if raw_event.is_reconnect:
            logger.warning("[%s] SSE 重连", self.label)
            self._mark_delayed_finish_activity()
            return None

        parsed = parse_event(raw_event, self.session_id)
        self._publish_event(parsed)

        if parsed.type == EventType.SKIP:
            return None

        if self._is_delayed_finish_resume_event(parsed.type):
            self._reset_delayed_finish("foreground activity resumed")
        else:
            self._mark_delayed_finish_activity()

        handler = self.handlers.get(parsed.type)
        if not handler:
            return None

        finished = await handler.handle(parsed, self.accumulator, self)
        if finished:
            if await self._foreground_finish_allowed():
                self.state = SessionRunState.COMPLETED
                return self._success(self.accumulator.finish_reason)
            logger.info(
                "[%s] foreground finish delayed: background still running",
                self.label,
            )
            self._mark_delayed_finish()
        return None

    def _mark_delayed_finish(self) -> None:
        now = time.time()
        if self.delayed_finish_started_at <= 0:
            self.delayed_finish_started_at = now
            self.delayed_finish_last_event_at = now
            self.delayed_finish_last_heartbeat_at = now
            self.delayed_finish_heartbeats_sent = 0

    def _is_delayed_finish_resume_event(self, event_type: EventType) -> bool:
        if self.delayed_finish_started_at <= 0:
            return False
        return event_type in {
            EventType.STEP_START,
            EventType.TEXT,
            EventType.TEXT_DELTA,
            EventType.TOOL,
            EventType.REASONING,
            EventType.PERMISSION,
        }

    def _reset_delayed_finish(self, reason: str) -> None:
        if self.delayed_finish_started_at <= 0:
            return
        logger.info("[%s] delayed foreground finish resumed: %s", self.label, reason)
        self.delayed_finish_started_at = 0.0
        self.delayed_finish_last_event_at = 0.0
        self.delayed_finish_last_heartbeat_at = 0.0
        self.delayed_finish_heartbeats_sent = 0

    def _mark_delayed_finish_activity(self) -> None:
        if self.delayed_finish_started_at > 0:
            self.delayed_finish_last_event_at = time.time()

    async def _tick_delayed_finish_watchdog(self) -> None:
        if self.delayed_finish_started_at <= 0:
            return
        now = time.time()
        heartbeat_sec = max(1.0, float(self.cfg.delayed_finish_heartbeat_sec))
        if now - self.delayed_finish_last_event_at < heartbeat_sec:
            return
        if now - self.delayed_finish_last_heartbeat_at < heartbeat_sec:
            return
        max_heartbeats = max(1, int(self.cfg.delayed_finish_max_heartbeats))
        if self.delayed_finish_heartbeats_sent >= max_heartbeats:
            raise RuntimeError(
                "前台 terminate 后仍有后台任务，但心跳激活连续无回复，判定超时"
            )

        self.delayed_finish_heartbeats_sent += 1
        self.delayed_finish_last_heartbeat_at = now
        logger.warning(
            "[%s] delayed foreground finish heartbeat %d/%d after %.0fs without progress",
            self.label,
            self.delayed_finish_heartbeats_sent,
            max_heartbeats,
            now - self.delayed_finish_last_event_at,
        )
        ok = await self.client.send_prompt_async(
            self.session_id,
            self.cfg.delayed_finish_heartbeat_prompt,
        )
        if not ok:
            logger.warning("[%s] delayed finish heartbeat rejected by server", self.label)

    async def _delayed_finish_watchdog_loop(self) -> None:
        interval = min(
            5.0,
            max(1.0, float(self.cfg.delayed_finish_heartbeat_sec) / 10.0),
        )
        while True:
            await asyncio.sleep(interval)
            await self._tick_delayed_finish_watchdog()

    async def _foreground_finish_allowed(self) -> bool:
        if not self.deps.can_finish_foreground:
            return True
        try:
            result = self.deps.can_finish_foreground()
            if inspect.isawaitable(result):
                result = await result
            return bool(result)
        except Exception:
            logger.debug("foreground finish predicate failed", exc_info=True)
            return False

    def _publish_event(self, event) -> None:
        if not self.deps.on_event:
            return
        try:
            self.deps.on_event(event)
        except Exception:
            logger.debug("event callback failed", exc_info=True)

    async def _stream_ended_result(self) -> TaskResult:
        logger.info("[%s] SSE 流结束，尝试获取最终消息", self.label)
        if self.accumulator.text.strip():
            self.state = SessionRunState.COMPLETED
            return self._success("stream_ended")

        self.accumulator.text = await fetch_final_message(
            self.client,
            self.session_id,
            self.pre_existing_ids,
        )
        self.state = SessionRunState.COMPLETED
        return self._success("fallback")

    def _success(self, finish_reason: str) -> TaskResult:
        acc = self.accumulator
        if finish_reason:
            acc.finish_reason = finish_reason
        return TaskResult(
            success=True,
            text=acc.text.strip(),
            session_id=self.session_id,
            tool_calls=acc.tool_calls,
            permissions_granted=acc.permissions_granted,
            steps=acc.steps,
            elapsed_sec=time.time() - self.started_at,
            cost=acc.cost,
            tokens=acc.tokens,
            finish_reason=acc.finish_reason,
        )

    def _fail(self, error: str) -> TaskResult:
        return TaskResult.fail(
            error,
            session_id=self.session_id,
            elapsed_sec=time.time() - self.started_at,
        )
