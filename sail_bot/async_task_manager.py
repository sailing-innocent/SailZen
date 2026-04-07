#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file async_task_manager.py
# @brief 异步任务管理器 - 基于SSE事件流的OpenCode任务执行
# @author sailing-innocent
# @date 2026-04-07
# @version 2.0
# ---------------------------------
"""异步任务管理器 - 基于SSE事件流实时追踪OpenCode任务。

v2.0 核心改进:
1. 使用 SSE (GET /session/:id/events) 替代轮询，延迟从秒级降到毫秒级
2. 统一到 asyncio 事件循环，消除线程泛滥
3. 自动重连机制处理网络抖动
4. 保留同步回调接口兼容上层 handler
"""

import asyncio
import json
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from sail_bot.opencode_client import (
    OpenCodeAsyncClient,
    OpenCodeSessionClient,
    SSEEvent,
    Message,
    MessagePartType,
)

logger = logging.getLogger("async_task")

# Suppress noisy HTTP logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Optional imports
try:
    from sail_bot.task_logger import task_logger
except ImportError:
    task_logger = None

try:
    from sail_bot.opencode_message_logger import OpenCodeMessageLogger
except ImportError:
    OpenCodeMessageLogger = None

try:
    from sail_bot.log_formatter import (
        async_mgr, task_progress, task_status, log, error, warn,
    )
except ImportError:
    def async_mgr(msg, task_id="", level="INFO"):
        tid = f"{task_id[:16]}... " if task_id else ""
        print(f"[Async] {tid}{msg}")
    def task_progress(tid, action, detail=""):
        print(f"[Async] {action} {tid[:16]}... {detail}")
    def task_status(tid, status, elapsed, last_activity="", extra=""):
        print(f"[Async] {tid[:16]}... status={status} elapsed={elapsed}s")
    def log(level, comp, msg):
        print(f"[{comp}] {msg}")
    def error(comp, msg):
        print(f"[ERROR][{comp}] {msg}")
    def warn(comp, msg):
        print(f"[WARN][{comp}] {msg}")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    """任务执行步骤"""
    step_type: str  # "thinking", "tool_call", "tool_result", "response"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AsyncTask:
    """异步任务记录"""

    task_id: str
    session_id: str
    port: int
    original_text: str
    workspace_path: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    steps: List[TaskStep] = field(default_factory=list)
    final_result: Optional[str] = None
    error_message: Optional[str] = None

    # Tool call history (for display)
    _tool_calls: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    # Callbacks (called from the event loop thread)
    on_step: Optional[Callable[[TaskStep], None]] = None
    on_complete: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None

    # Internal: asyncio task handle for cancellation
    _asyncio_task: Optional[Any] = field(default=None, repr=False)

    def add_step(self, step: TaskStep) -> None:
        """添加执行步骤并触发回调"""
        self.steps.append(step)
        self.updated_at = datetime.now()

        if task_logger and self.workspace_path:
            try:
                task_logger.add_step(
                    self.task_id, step.step_type, step.content, step.metadata
                )
            except Exception:
                pass

        if self.on_step:
            try:
                self.on_step(step)
            except Exception as exc:
                logger.error("[AsyncTask] on_step callback error: %s", exc)

    def add_tool_call(self, tool_name: str, status: str) -> None:
        """记录工具调用历史"""
        self._tool_calls.append({
            "time": time.time(), "tool": tool_name, "status": status,
        })
        if len(self._tool_calls) > 30:
            self._tool_calls = self._tool_calls[-30:]

    def get_recent_tools(self, count: int = 5) -> str:
        """获取最近的工具调用链描述"""
        if not self._tool_calls:
            return "无"
        icons = {"pending": "⏳", "running": "⚙️", "completed": "✅", "error": "❌"}
        recent = self._tool_calls[-count:]
        return " → ".join(
            f"{icons.get(t['status'], '❓')}{t['tool']}" for t in recent
        )

    def _fire_complete(self, result: str) -> None:
        self.final_result = result
        self.status = TaskStatus.COMPLETED
        self.updated_at = datetime.now()
        if task_logger and self.workspace_path:
            try:
                task_logger.complete_task(self.task_id, final_result=result)
            except Exception:
                pass
        if self.on_complete:
            try:
                self.on_complete(result)
            except Exception as exc:
                logger.error("[AsyncTask] on_complete callback error: %s", exc)

    def _fire_error(self, msg: str) -> None:
        self.error_message = msg
        if self.status not in (TaskStatus.CANCELLED,):
            self.status = TaskStatus.ERROR
        self.updated_at = datetime.now()
        if task_logger and self.workspace_path:
            try:
                task_logger.complete_task(self.task_id, error_message=msg)
            except Exception:
                pass
        if self.on_error:
            try:
                self.on_error(msg)
            except Exception as exc:
                logger.error("[AsyncTask] on_error callback error: %s", exc)


# ---------------------------------------------------------------------------
# AsyncTaskManager - unified asyncio event loop
# ---------------------------------------------------------------------------

class AsyncTaskManager:
    """异步任务管理器 - 基于SSE事件流。

    内部维护一个 asyncio 事件循环（运行在独立的 daemon 线程上）。
    外部通过 submit_task / abort_task 等同步方法与之交互。
    """

    def __init__(
        self,
        max_duration: float = 3600.0,
        fallback_poll_interval: float = 15.0,
    ):
        self.max_duration = max_duration
        self.fallback_poll_interval = fallback_poll_interval
        self._tasks: Dict[str, AsyncTask] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """启动任务管理器（创建事件循环线程）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="task-mgr-loop",
        )
        self._thread.start()
        # Wait for loop to be ready
        for _ in range(50):
            if self._loop is not None:
                break
            time.sleep(0.05)
        log("INFO", "Async", "Task manager started (SSE mode)")

    def stop(self) -> None:
        """停止任务管理器"""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5.0)
        log("INFO", "Async", "Task manager stopped")

    def _run_loop(self) -> None:
        """Event loop thread entry point."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Schedule cleanup task
        self._loop.create_task(self._cleanup_loop())
        try:
            self._loop.run_forever()
        finally:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(self._loop)
            for t in pending:
                t.cancel()
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
            self._loop.close()
            self._loop = None

    # -- Public API (thread-safe, called from any thread) ---------------------

    def submit_task(
        self,
        session_id: str,
        port: int,
        text: str,
        workspace_path: Optional[str] = None,
        on_step: Optional[Callable[[TaskStep], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> AsyncTask:
        """提交异步任务（线程安全）"""
        task_id = f"task_{int(time.time() * 1000)}_{session_id[:8]}"

        task = AsyncTask(
            task_id=task_id,
            session_id=session_id,
            port=port,
            original_text=text,
            workspace_path=workspace_path,
            on_step=on_step,
            on_complete=on_complete,
            on_error=on_error,
        )

        with self._lock:
            self._tasks[task_id] = task

        # Check for concurrent tasks on same session
        existing = self._get_running_tasks_for_session(session_id, exclude=task_id)
        if existing:
            warn("Async", f"Task {task_id[:16]}... started while session has running: "
                 f"{[t.task_id[:16] for t in existing]}")

        # Log to task history
        if task_logger and workspace_path:
            try:
                task_logger.start_task(
                    task_id=task_id,
                    workspace_path=workspace_path,
                    task_text=text,
                    session_id=session_id,
                    port=port,
                )
            except Exception:
                pass

        # Schedule on event loop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._execute_task(task), self._loop
            )
        else:
            error("Async", "Event loop not running! Falling back to thread.")
            threading.Thread(
                target=self._execute_task_sync_fallback,
                args=(task,),
                daemon=True,
            ).start()

        task_progress(task_id, "started", f"session={session_id[:16]}...")
        return task

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def abort_task(self, task_id: str) -> bool:
        """中止正在运行的任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                return False

        # Cancel the asyncio task
        if task._asyncio_task and not task._asyncio_task.done():
            task._asyncio_task.cancel()

        # Also send abort to OpenCode server
        try:
            client = OpenCodeSessionClient(port=task.port, timeout=10.0)
            ok = client.abort_session(task.session_id)
            client.close()

            task.status = TaskStatus.CANCELLED
            task.error_message = "任务被用户取消"

            if task_logger and task.workspace_path:
                try:
                    task_logger.cancel_task(task_id, "用户取消")
                except Exception:
                    pass

            task._fire_error("任务被用户取消")
            return ok
        except Exception as exc:
            error("Async", f"Abort task {task_id[:16]}... error: {exc}")
            return False

    # -- Internal helpers (thread-safe) ----------------------------------------

    def _get_running_tasks_for_session(
        self, session_id: str, exclude: Optional[str] = None
    ) -> List[AsyncTask]:
        with self._lock:
            return [
                t for tid, t in self._tasks.items()
                if t.session_id == session_id
                and t.status == TaskStatus.RUNNING
                and tid != exclude
            ]

    # -- Async task execution (runs on event loop) ----------------------------

    async def _execute_task(self, task: AsyncTask) -> None:
        """Execute a task using SSE event stream."""
        # Store asyncio task handle for cancellation
        task._asyncio_task = asyncio.current_task()

        try:
            task.status = TaskStatus.RUNNING

            async with OpenCodeAsyncClient(port=task.port) as client:
                # 1. Send prompt
                ok = await client.send_prompt_async(task.session_id, task.original_text)
                if not ok:
                    task._fire_error("Failed to send prompt (server rejected)")
                    return

                task.add_step(TaskStep(
                    step_type="thinking",
                    content="任务已提交，开始执行...",
                ))

                # 2. Stream SSE events
                await self._stream_task_events(client, task)

        except asyncio.CancelledError:
            async_mgr("Task cancelled", task.task_id)
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.CANCELLED
                task.error_message = "任务被取消"
        except Exception as exc:
            error("Async", f"Task {task.task_id[:16]}... error: {exc}")
            traceback.print_exc()
            task._fire_error(str(exc))

    async def _stream_task_events(
        self,
        client: OpenCodeAsyncClient,
        task: AsyncTask,
    ) -> None:
        """Stream SSE events from OpenCode and process them."""
        start_time = time.time()
        tool_call_count = 0
        sse_connected = False

        try:
            async for event in client.stream_events_robust(
                task.session_id,
                timeout=self.max_duration,
                max_reconnects=5,
                on_reconnect=lambda n: async_mgr(
                    f"SSE reconnected (attempt {n})", task.task_id, "WARN"
                ),
            ):
                # Check cancellation
                if task.status == TaskStatus.CANCELLED:
                    async_mgr("Task cancelled during SSE stream", task.task_id)
                    return

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.max_duration:
                    task.status = TaskStatus.TIMEOUT
                    task._fire_error(
                        f"任务执行超时（>{int(self.max_duration / 60)}分钟）"
                    )
                    return

                if not sse_connected:
                    sse_connected = True
                    async_mgr("SSE connected", task.task_id)

                # Handle reconnection synthetic event
                if event.event == "__reconnected__":
                    task.add_step(TaskStep(
                        step_type="thinking",
                        content="🔄 连接已恢复，继续监听...",
                    ))
                    continue

                # Process the SSE event
                completed = self._process_sse_event(task, event)
                if completed:
                    return

            # Stream ended normally (server closed connection)
            # This usually means the session is idle - fetch final result
            async_mgr("SSE stream ended, fetching final result", task.task_id)
            await self._fetch_final_result(client, task)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if task.status == TaskStatus.RUNNING:
                # SSE failed completely - fall back to status polling
                warn("Async", f"SSE failed for {task.task_id[:16]}...: {exc}")
                warn("Async", "Falling back to status polling")
                await self._fallback_poll(client, task, start_time)

    def _process_sse_event(self, task: AsyncTask, event: SSEEvent) -> bool:
        """Process a single SSE event. Returns True if task is completed."""
        data = event.json()
        if data is None:
            return False

        event_type = event.event

        # OpenCode SSE event types (based on API docs):
        # - message.created: new message (user or assistant)
        # - message.updated: message content updated (parts changed)
        # - session.updated: session metadata changed
        # etc.

        # For message events, data contains the full message object
        if event_type in ("message.created", "message.updated"):
            return self._handle_message_event(task, data)

        # For session status events
        if event_type == "session.updated":
            # Could track session-level status here
            return False

        # Log unrecognized events for debugging
        if event_type:
            async_mgr(f"SSE event: {event_type}", task.task_id)

        return False

    def _handle_message_event(self, task: AsyncTask, msg_data: Dict[str, Any]) -> bool:
        """Handle a message event from SSE. Returns True if task completed."""
        info = msg_data.get("info", {})
        role = info.get("role", "")
        parts = msg_data.get("parts", [])

        # Only process assistant messages
        if role != "assistant":
            return False

        for part in parts:
            part_type = part.get("type", "")

            if part_type == "tool":
                tool_name = part.get("tool", "unknown")
                state = part.get("state", {})
                status = state.get("status", "unknown")
                title = state.get("title", tool_name)

                task.add_tool_call(tool_name, status)

                if status == "pending":
                    task.add_step(TaskStep(
                        step_type="tool_call",
                        content=f"🔧 准备调用: {tool_name}",
                        metadata={"tool": tool_name, "status": status},
                    ))
                elif status == "running":
                    task.add_step(TaskStep(
                        step_type="tool_call",
                        content=f"⏳ 执行中: {title}",
                        metadata={"tool": tool_name, "status": status},
                    ))
                elif status == "completed":
                    task.add_step(TaskStep(
                        step_type="tool_result",
                        content=f"✅ {title}",
                        metadata={"tool": tool_name, "status": status},
                    ))
                    task_progress(task.task_id, "tool", f"{tool_name} (completed)")
                elif status == "error":
                    err = state.get("error", "Unknown error")
                    task.add_step(TaskStep(
                        step_type="tool_result",
                        content=f"❌ {tool_name} 失败: {err[:100]}",
                        metadata={"tool": tool_name, "status": status, "error": err},
                    ))

                # Auto-answer question/permission tools
                if tool_name in ("question", "permission", "ask") and status in ("pending", "running"):
                    asyncio.ensure_future(
                        self._auto_answer_tool(task, tool_name, state)
                    )

            elif part_type == "reasoning":
                text = part.get("text", "").strip()
                if text:
                    task.add_step(TaskStep(
                        step_type="thinking",
                        content=f"💭 {text[:150]}{'...' if len(text) > 150 else ''}",
                    ))

            elif part_type == "step-start":
                task.add_step(TaskStep(
                    step_type="thinking",
                    content="🚀 开始新步骤...",
                ))

            elif part_type == "step-finish":
                reason = part.get("reason", "")
                cost = part.get("cost", 0)

                if reason == "stop":
                    # ✅ Task completed!
                    text_content = self._extract_text_from_parts(parts)
                    result = text_content if text_content.strip() else "（任务已完成）"
                    task_progress(task.task_id, "completed", f"reason=stop")
                    task._fire_complete(result)
                    return True

                elif reason == "tool-calls":
                    task.add_step(TaskStep(
                        step_type="thinking",
                        content="✅ 步骤完成（工具调用链结束，可能还有后续步骤）",
                        metadata={"cost": cost},
                    ))

            elif part_type == "text":
                # Text parts are accumulated; we only extract at completion
                pass

        return False

    async def _auto_answer_tool(
        self, task: AsyncTask, tool_name: str, state: Dict[str, Any]
    ) -> None:
        """自动回答反问工具 (question/permission)，让任务继续执行。"""
        try:
            async_mgr(f"Auto-answering {tool_name} tool", task.task_id)
            async with OpenCodeAsyncClient(port=task.port) as client:
                if tool_name == "permission":
                    answer = "确认授权，继续执行当前操作。"
                else:
                    answer = "收到，继续执行。"

                await client.send_message_async(task.session_id, answer)
                task.add_step(TaskStep(
                    step_type="thinking",
                    content=f"🤖 自动回复 {tool_name}: {answer[:50]}",
                ))
        except Exception as exc:
            warn("Async", f"Auto-answer {tool_name} failed: {exc}")

    async def _fetch_final_result(
        self, client: OpenCodeAsyncClient, task: AsyncTask
    ) -> None:
        """Fetch the final result from the last assistant message."""
        if task.status != TaskStatus.RUNNING:
            return

        try:
            messages = await client.get_messages(task.session_id, limit=5)
            for msg in reversed(messages):
                if msg.role == "assistant" and msg.text_content.strip():
                    task._fire_complete(msg.text_content)
                    return

            # No text content found
            task._fire_complete("（任务完成，无文字输出）")
        except Exception as exc:
            error("Async", f"Fetch final result error: {exc}")
            task._fire_error(f"获取结果失败: {exc}")

    async def _fallback_poll(
        self,
        client: OpenCodeAsyncClient,
        task: AsyncTask,
        start_time: float,
    ) -> None:
        """Fallback: poll session status when SSE is unavailable."""
        async_mgr("Using fallback polling", task.task_id)
        consecutive_idle = 0

        while task.status == TaskStatus.RUNNING:
            elapsed = time.time() - start_time
            if elapsed > self.max_duration:
                task.status = TaskStatus.TIMEOUT
                task._fire_error(
                    f"任务执行超时（>{int(self.max_duration / 60)}分钟）"
                )
                return

            try:
                statuses = await client.get_session_status()
                if task.session_id in statuses:
                    status_type = statuses[task.session_id].get("type", "unknown")
                    if status_type == "idle":
                        consecutive_idle += 1
                    else:
                        consecutive_idle = 0
                else:
                    # Session not in status list = idle
                    consecutive_idle += 1

                if consecutive_idle >= 2:
                    await self._fetch_final_result(client, task)
                    return

            except Exception as exc:
                warn("Async", f"Fallback poll error: {exc}")

            await asyncio.sleep(self.fallback_poll_interval)

    # -- Sync fallback (only if event loop fails to start) --------------------

    def _execute_task_sync_fallback(self, task: AsyncTask) -> None:
        """Synchronous fallback when event loop is not available."""
        try:
            task.status = TaskStatus.RUNNING
            client = OpenCodeSessionClient(port=task.port, timeout=30.0)

            ok = client.send_prompt_async(task.session_id, task.original_text)
            if not ok:
                task._fire_error("Failed to send prompt")
                client.close()
                return

            task.add_step(TaskStep(
                step_type="thinking",
                content="任务已提交（降级模式），等待完成...",
            ))

            # Simple status polling
            start = time.time()
            consecutive_idle = 0
            while task.status == TaskStatus.RUNNING:
                if time.time() - start > self.max_duration:
                    task._fire_error("任务超时")
                    break

                try:
                    statuses = client.get_session_status()
                    if task.session_id not in statuses:
                        consecutive_idle += 1
                    elif statuses[task.session_id].get("type") == "idle":
                        consecutive_idle += 1
                    else:
                        consecutive_idle = 0

                    if consecutive_idle >= 2:
                        msgs = client.get_messages(task.session_id, limit=5)
                        for m in reversed(msgs):
                            if m.role == "assistant" and m.text_content.strip():
                                task._fire_complete(m.text_content)
                                client.close()
                                return
                        task._fire_complete("（任务完成）")
                        client.close()
                        return
                except Exception as exc:
                    warn("Async", f"Sync fallback poll error: {exc}")

                time.sleep(self.fallback_poll_interval)

            client.close()
        except Exception as exc:
            error("Async", f"Sync fallback error: {exc}")
            task._fire_error(str(exc))

    # -- Cleanup loop ---------------------------------------------------------

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired tasks."""
        while self._running:
            await asyncio.sleep(30)
            self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        """Remove tasks that have been completed/errored for over 1 hour."""
        now = datetime.now()
        to_remove = []

        with self._lock:
            for task_id, task in list(self._tasks.items()):
                age = (now - task.created_at).total_seconds()

                if task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.ERROR,
                    TaskStatus.CANCELLED,
                    TaskStatus.TIMEOUT,
                ):
                    if age > 3600:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self._tasks[task_id]

        if to_remove:
            log("INFO", "Async",
                f"Cleaned up {len(to_remove)} expired task(s)")

    # -- Utility ---------------------------------------------------------------

    @staticmethod
    def _extract_text_from_parts(parts: List[Dict[str, Any]]) -> str:
        """Extract all text content from message parts."""
        texts = []
        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    texts.append(text)
        return "".join(texts)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

task_manager = AsyncTaskManager()
