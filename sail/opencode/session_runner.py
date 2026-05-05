# -*- coding: utf-8 -*-
# @file session_runner.py
# @brief 高层级 session 执行器：发送 prompt → 监听 SSE → 汇总结果
# @author sailing-innocent
# @date 2026-04-25
# @version 1.0
# ---------------------------------
"""sail.opencode.session_runner — 将"一次 prompt 执行"封装为完整生命周期。

典型用法:
    runner = SessionRunner(port=4096)
    result = await runner.run("请帮我重构这段代码", session_id="abc123")
    print(result.summary)          # 文本摘要
    print(result.tool_calls)       # 工具调用列表
    print(result.elapsed_seconds)  # 耗时
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sail.opencode.client import OpenCodeAsyncClient, SSEEvent
from sail.opencode.sse_parser import EventType, ParsedEvent, parse_event
from sail.opencode.sse_printer import PrinterCallbacks, SSEPrinter

logger = logging.getLogger(__name__)


# ── 执行结果 ──────────────────────────────────────────────────────


@dataclass
class RunResult:
    """一次 prompt 执行的聚合结果。"""

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
        """生成简短摘要（适合飞书卡片）。"""
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


# ── 事件收集器 ────────────────────────────────────────────────────


class _EventCollector:
    """内部使用：收集事件并构建 RunResult。"""

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
            pass  # Reasoning tracked but not included in output
        elif parsed.is_terminal():
            # SESSION_IDLE or STEP_FINISH (terminal) — flush text
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


# ── Session Runner ────────────────────────────────────────────────


class SessionRunner:
    """高层级执行器：prompt → SSE stream → RunResult。"""

    def __init__(
        self,
        port: int,
        *,
        verbose: bool = True,
        printer_callbacks: Optional[PrinterCallbacks] = None,
    ) -> None:
        self._port = port
        self._client = OpenCodeAsyncClient(port=port)
        self._verbose = verbose
        self._printer_callbacks = printer_callbacks
        self._cancel_event: Optional[asyncio.Event] = None

    # ── 主入口 ────────────────────────────────────────────────────

    async def run(
        self,
        prompt: str,
        session_id: str,
        *,
        timeout: float = 14400.0,
        on_event: Optional[Callable[[ParsedEvent], None]] = None,
    ) -> RunResult:
        """发送 prompt 并阻塞直到完成（或超时/取消）。

        Args:
            prompt: 要发送给 agent 的文本
            session_id: opencode session ID
            timeout: 最大等待秒数
            on_event: 每个事件的额外回调

        Returns:
            RunResult 聚合结果
        """
        self._cancel_event = asyncio.Event()
        collector = _EventCollector()
        printer = SSEPrinter(
            verbose=self._verbose,
            callbacks=self._printer_callbacks,
        )

        t0 = time.monotonic()

        # 1) 发送 prompt (fire-and-forget, then listen via SSE)
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

        # 2) 监听 SSE 流
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

    # ── 取消 ──────────────────────────────────────────────────────

    def cancel(self) -> None:
        """从外部取消正在执行的 run()。"""
        if self._cancel_event:
            self._cancel_event.set()

    # ── 辅助方法 ──────────────────────────────────────────────────

    async def create_session(self, title: str = "SailZen") -> Optional[str]:
        """创建新的 opencode session，返回 session_id。"""
        try:
            sess = await self._client.create_session(title)
            return sess.id if sess else None
        except Exception as exc:
            logger.error("[SessionRunner] 创建 session 失败: %s", exc)
            return None

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有 session。"""
        try:
            sessions = await self._client.list_sessions()
            return [{"id": s.id, "title": s.title} for s in sessions]
        except Exception as exc:
            logger.error("[SessionRunner] 列出 sessions 失败: %s", exc)
            return []

    async def check_health(self) -> bool:
        """检查 opencode 服务是否可用。"""
        return await self._client.health_check()

    async def close(self) -> None:
        """清理资源。"""
        await self._client.close()


# ── 快捷函数 ──────────────────────────────────────────────────────


async def run_prompt(
    port: int,
    session_id: str,
    prompt: str,
    *,
    timeout: float = 14400.0,
    verbose: bool = True,
    callbacks: Optional[PrinterCallbacks] = None,
) -> RunResult:
    """一步到位：发送 prompt 并等待结果。

    Usage:
        result = await run_prompt(4096, "sess-id", "帮我修 bug")
    """
    runner = SessionRunner(port, verbose=verbose, printer_callbacks=callbacks)
    try:
        return await runner.run(prompt, session_id, timeout=timeout)
    finally:
        await runner.close()
