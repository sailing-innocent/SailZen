# -*- coding: utf-8 -*-
# @file session_runner.py
# @brief High-level session executors: legacy simple runner + DI-based runner.
# @author sailing-innocent
# @date 2026-05-31
# @version 2.0
# ---------------------------------
"""sail.opencode.session_runner — Two execution styles:

1. **Legacy** — ``SessionRunner`` (simple class) and ``run_prompt`` (coroutine).
2. **DI-based** — ``run_task`` (coroutine) with injectable dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sail.opencode.client import OpencodeAsyncClient
from sail.opencode.sse_parser import EventType, ParsedEvent, parse_event
from sail.opencode.sse_printer import PrinterCallbacks, SSEPrinter

logger = logging.getLogger(__name__)


# ── Legacy result ─────────────────────────────────────────────────


@dataclass
class RunResult:
    success: bool = True
    summary: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    text_parts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
    events_count: int = 0
    session_id: str = ""
    was_cancelled: bool = False

    @property
    def full_text(self) -> str:
        return "\n".join(self.text_parts)

    def as_brief(self, max_len: int = 500) -> str:
        parts = []
        if self.tool_calls:
            parts.append(f"🔧 {len(self.tool_calls)} 个工具调用")
        if self.text_parts:
            text = self.full_text
            if len(text) > max_len:
                text = text[:max_len] + "…"
            parts.append(text)
        if self.error:
            parts.append(f"❌ {self.error}")
        if not parts:
            parts.append("（无输出）")
        return "\n".join(parts)


# ── Legacy collector ──────────────────────────────────────────────


class _EventCollector:
    def __init__(self) -> None:
        self.tool_calls: List[Dict[str, Any]] = []
        self.text_parts: List[str] = []
        self.events_count: int = 0
        self.last_error: Optional[str] = None
        self._current_text_buf: str = ""

    def handle(self, parsed: ParsedEvent) -> None:
        self.events_count += 1

        if parsed.type == EventType.TOOL:
            status = parsed.tool_status
            self.tool_calls.append({
                "tool": parsed.tool_name or "unknown",
                "status": status,
                "content": parsed.tool_title,
            })
        elif parsed.type in (EventType.TEXT, EventType.TEXT_DELTA):
            content = parsed.delta or parsed.text
            if content:
                self._current_text_buf += content
        elif parsed.type == EventType.REASONING:
            pass
        elif parsed.is_terminal():
            if self._current_text_buf:
                self.text_parts.append(self._current_text_buf.strip())
                self._current_text_buf = ""

    def flush(self) -> None:
        if self._current_text_buf:
            self.text_parts.append(self._current_text_buf.strip())
            self._current_text_buf = ""

    def to_result(self, session_id: str, elapsed: float) -> RunResult:
        self.flush()
        return RunResult(
            success=self.last_error is None,
            summary=self.text_parts[-1] if self.text_parts else "",
            tool_calls=self.tool_calls,
            text_parts=self.text_parts,
            error=self.last_error,
            elapsed_seconds=round(elapsed, 2),
            events_count=self.events_count,
            session_id=session_id,
        )


# ── Legacy runner ─────────────────────────────────────────────────


class SessionRunner:
    """Simple high-level runner: prompt → SSE stream → RunResult."""

    def __init__(
        self,
        port: int,
        *,
        verbose: bool = True,
        printer_callbacks: Optional[PrinterCallbacks] = None,
    ) -> None:
        self._port = port
        self._client = OpencodeAsyncClient(port=port)
        self._verbose = verbose
        self._printer_callbacks = printer_callbacks
        self._cancel_event: Optional[asyncio.Event] = None

    async def run(
        self,
        prompt: str,
        session_id: str,
        *,
        timeout: float = 14400.0,
        on_event: Optional[Callable[[ParsedEvent], None]] = None,
    ) -> RunResult:
        self._cancel_event = asyncio.Event()
        collector = _EventCollector()
        printer = SSEPrinter(
            verbose=self._verbose,
            callbacks=self._printer_callbacks,
        )

        t0 = time.monotonic()

        try:
            ok = await self._client.send_prompt_async(session_id, prompt)
            if not ok:
                return RunResult(
                    success=False,
                    error=f"发送 prompt 失败 (session={session_id})",
                    session_id=session_id,
                    elapsed_seconds=round(time.monotonic() - t0, 2),
                )
        except Exception as exc:
            return RunResult(
                success=False,
                error=f"发送 prompt 异常: {exc}",
                session_id=session_id,
                elapsed_seconds=round(time.monotonic() - t0, 2),
            )

        try:
            async for event in self._client.stream_events_robust(
                session_id=session_id,
                timeout=timeout,
            ):
                if self._cancel_event.is_set():
                    result = collector.to_result(session_id, time.monotonic() - t0)
                    result.was_cancelled = True
                    return result

                parsed = parse_event(event, session_id=session_id)
                if parsed.type == EventType.SKIP:
                    continue

                collector.handle(parsed)
                printer.handle_event(parsed)

                if on_event:
                    try:
                        on_event(parsed)
                    except Exception:
                        logger.debug("on_event callback error", exc_info=True)

                if parsed.is_terminal():
                    break

        except asyncio.TimeoutError:
            result = collector.to_result(session_id, time.monotonic() - t0)
            result.success = False
            result.error = f"执行超时 ({timeout}s)"
            return result
        except asyncio.CancelledError:
            result = collector.to_result(session_id, time.monotonic() - t0)
            result.was_cancelled = True
            return result
        except Exception as exc:
            result = collector.to_result(session_id, time.monotonic() - t0)
            result.success = False
            result.error = f"SSE 流异常: {exc}"
            return result

        return collector.to_result(session_id, time.monotonic() - t0)

    def cancel(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()

    async def create_session(self, title: str = "SailZen") -> Optional[str]:
        try:
            sess = await self._client.create_session(title)
            return sess.id if sess else None
        except Exception as exc:
            logger.error("[SessionRunner] 创建 session 失败: %s", exc)
            return None

    async def list_sessions(self) -> List[Dict[str, Any]]:
        try:
            sessions = await self._client.list_sessions()
            return [{"id": s.id, "title": s.title} for s in sessions]
        except Exception as exc:
            logger.error("[SessionRunner] 列出 sessions 失败: %s", exc)
            return []

    async def check_health(self) -> bool:
        return await self._client.health_check()

    async def close(self) -> None:
        await self._client.close()


# ── Legacy shortcut ───────────────────────────────────────────────


async def run_prompt(
    port: int,
    session_id: str,
    prompt: str,
    *,
    timeout: float = 14400.0,
    verbose: bool = True,
    callbacks: Optional[PrinterCallbacks] = None,
) -> RunResult:
    runner = SessionRunner(port, verbose=verbose, printer_callbacks=callbacks)
    try:
        return await runner.run(prompt, session_id, timeout=timeout)
    finally:
        await runner.close()


# ── DI-based runner ───────────────────────────────────────────────

from sail.opencode.session_dependencies import (
    SessionRunDependencies,
    default_dependencies,
)
from sail.opencode.session_models import (
    DEFAULT_AGENT_NAME,
    DEFAULT_MAX_RECONNECTS,
    DEFAULT_SSE_TIMEOUT,
    TaskResult,
    TaskRunConfig,
)
from sail.opencode.session_state_machine import SessionStateMachine


async def run_task(
    prompt: str,
    port: int = 4096,
    host: str = "127.0.0.1",
    config: Optional[TaskRunConfig] = None,
    on_event: Optional[Callable[[ParsedEvent], None]] = None,
    on_progress: Optional[Callable[[str], None]] = None,
    label: str = "task",
    dependencies: Optional[SessionRunDependencies] = None,
) -> TaskResult:
    """Run one opencode prompt and wait for completion (DI-based).

    Args:
        prompt: Prompt text.
        port: Server port (used when *config* is not provided).
        host: Server host (used when *config* is not provided).
        config: Optional run configuration.
        on_event: Optional parsed-SSE observer.
        on_progress: Optional throttled progress callback.
        label: Log label for this run.
        dependencies: Optional injected services.

    Returns:
        ``TaskResult`` with final text, stats, and failure info.
    """
    cfg = config or TaskRunConfig(host=host, port=port)
    if config is None:
        cfg.host = host
        cfg.port = port

    deps = dependencies or default_dependencies(
        on_event=on_event,
        on_progress=on_progress,
    )
    if dependencies is not None:
        if on_event is not None:
            deps.on_event = on_event
        if on_progress is not None:
            deps.on_progress = on_progress

    async with OpencodeAsyncClient(host=cfg.host, port=cfg.port) as client:
        machine = SessionStateMachine(
            client=client,
            prompt=prompt,
            cfg=cfg,
            deps=deps,
            label=label,
        )
        return await machine.run()


__all__ = [
    "DEFAULT_AGENT_NAME",
    "DEFAULT_MAX_RECONNECTS",
    "DEFAULT_SSE_TIMEOUT",
    "RunResult",
    "SessionRunner",
    "SessionRunDependencies",
    "SessionStateMachine",
    "TaskResult",
    "TaskRunConfig",
    "default_dependencies",
    "run_prompt",
    "run_task",
]
