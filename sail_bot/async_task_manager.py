#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @file async_task_manager.py
# @brief 异步任务管理器 - 支持OpenCode长时间运行任务
# @author sailing-innocent
# @date 2026-04-04
# @version 1.0
# ---------------------------------
"""异步任务管理器 - 处理OpenCode的多轮工具调用和长时任务。

核心特性：
1. 异步发送任务（prompt_async），立即返回
2. 使用 /session/status + SSE 事件流双重检测会话完成状态
3. 支持工具调用链的展示
4. 自动处理超时和错误
"""

import json
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

# 获取日志记录器（避免使用 basicConfig 覆盖全局配置）
logger = logging.getLogger("async_task")

# 确保 httpx 日志级别为 WARNING，避免过多 HTTP 请求日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# 导入任务历史记录器
try:
    from task_logger import task_logger
except ImportError:
    task_logger = None


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"  # 等待中
    RUNNING = "running"  # 执行中
    WAITING_INPUT = "waiting_input"  # 等待用户输入
    COMPLETED = "completed"  # 已完成
    ERROR = "error"  # 出错
    TIMEOUT = "timeout"  # 超时
    CANCELLED = "cancelled"  # 已取消


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
    workspace_path: Optional[str] = None  # 添加工作区路径
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    steps: List[TaskStep] = field(default_factory=list)
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    _last_warning_minute: int = field(default=0, repr=False)  # 上次警告时间（分钟）

    # 工具调用记录
    _tool_calls: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    # 回调函数
    on_step: Optional[Callable[[TaskStep], None]] = None
    on_complete: Optional[Callable[[str], None]] = None
    on_error: Optional[Callable[[str], None]] = None

    def add_step(self, step: TaskStep):
        """添加执行步骤并触发回调"""
        self.steps.append(step)
        self.updated_at = datetime.now()

        # 记录到任务历史日志
        if task_logger and self.workspace_path:
            task_logger.add_step(
                self.task_id, step.step_type, step.content, step.metadata
            )

        if self.on_step:
            try:
                self.on_step(step)
            except Exception as exc:
                logger.error(f"[AsyncTask] on_step callback error: {exc}")

    def add_tool_call(self, tool_name: str, status: str):
        """记录工具调用历史"""
        self._tool_calls.append(
            {
                "time": time.time(),
                "tool": tool_name,
                "status": status,
            }
        )
        # 只保留最近20个
        if len(self._tool_calls) > 20:
            self._tool_calls = self._tool_calls[-20:]

    def get_recent_tools(self, count: int = 5) -> str:
        """获取最近的工具调用链描述"""
        if not self._tool_calls:
            return "无"
        recent = self._tool_calls[-count:]
        parts = []
        for t in recent:
            status_icon = {
                "pending": "⏳",
                "running": "⚙️",
                "completed": "✅",
                "error": "❌",
            }.get(t["status"], "❓")
            parts.append(f"{status_icon}{t['tool']}")
        return " → ".join(parts)


class AsyncTaskManager:
    """异步任务管理器"""

    def __init__(
        self,
        poll_interval: float = 2.0,  # 轮询间隔（秒）
        max_duration: float = 3600.0,  # 最大执行时间（秒）- 默认1小时
        status_check_interval: float = 3.0,  # 状态检查间隔（秒）
    ):
        self.poll_interval = poll_interval
        self.max_duration = max_duration
        self.status_check_interval = status_check_interval
        self._tasks: Dict[str, AsyncTask] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self):
        """启动任务管理器"""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("[AsyncTaskManager] Started")

    def stop(self):
        """停止任务管理器"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        print("[AsyncTaskManager] Stopped")

    def submit_task(
        self,
        session_id: str,
        port: int,
        text: str,
        workspace_path: Optional[str] = None,  # 添加工作区路径
        on_step: Optional[Callable[[TaskStep], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> AsyncTask:
        """提交异步任务"""
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

        # 记录到任务历史日志
        if task_logger and workspace_path:
            task_logger.start_task(
                task_id=task_id,
                workspace_path=workspace_path,
                task_text=text,
                session_id=session_id,
                port=port,
            )

        # 启动异步执行
        threading.Thread(target=self._execute_task, args=(task,), daemon=True).start()

        logger.info(f"[AsyncTaskManager] Submitted task {task_id}: {text[:80]}...")
        return task

    def get_task(self, task_id: str) -> Optional[AsyncTask]:
        """获取任务状态"""
        with self._lock:
            return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def abort_task(self, task_id: str) -> bool:
        """中止正在运行的任务

        调用 OpenCode API: POST /session/:id/abort
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"[AsyncTaskManager] Task {task_id} not found")
                return False

            if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                logger.warning(
                    f"[AsyncTaskManager] Task {task_id} is not running (status: {task.status})"
                )
                return False

        try:
            base_url = f"http://127.0.0.1:{task.port}"
            response = httpx.post(
                f"{base_url}/session/{task.session_id}/abort",
                timeout=10.0,
            )

            if response.status_code == 200:
                logger.info(f"[AsyncTaskManager] Task {task_id} abort request sent")
                # 标记任务为取消状态
                task.status = TaskStatus.CANCELLED
                task.error_message = "任务被用户取消"

                # 记录到任务历史日志
                if task_logger and task.workspace_path:
                    task_logger.cancel_task(task_id, "用户取消")

                # 触发错误回调
                if task.on_error:
                    try:
                        task.on_error("任务被用户取消")
                    except Exception as exc:
                        logger.error(
                            f"[AsyncTaskManager] on_error callback error: {exc}"
                        )

                return True
            else:
                logger.error(
                    f"[AsyncTaskManager] Failed to abort task {task_id}: {response.status_code}"
                )
                return False

        except Exception as exc:
            logger.error(f"[AsyncTaskManager] Abort task {task_id} error: {exc}")
            return False

    def _monitor_loop(self):
        """监控循环 - 清理过期任务"""
        while self._running:
            time.sleep(10)
            self._cleanup_expired()

    def _cleanup_expired(self):
        """清理过期任务"""
        now = datetime.now()
        expired_ids = []

        with self._lock:
            for task_id, task in list(self._tasks.items()):
                age = (now - task.created_at).total_seconds()

                # 已完成/出错/取消的任务保留1小时
                if task.status in (
                    TaskStatus.COMPLETED,
                    TaskStatus.ERROR,
                    TaskStatus.CANCELLED,
                ):
                    if age > 3600:
                        expired_ids.append(task_id)
                # 运行中超时
                elif task.status == TaskStatus.RUNNING and age > self.max_duration:
                    task.status = TaskStatus.TIMEOUT
                    task.error_message = f"任务执行超时（{self.max_duration}秒）"
                    if task.on_error:
                        task.on_error(task.error_message)
                    expired_ids.append(task_id)

        for task_id in expired_ids:
            with self._lock:
                if task_id in self._tasks:
                    del self._tasks[task_id]
            print(f"[AsyncTaskManager] Cleaned up expired task {task_id}")

    def _execute_task(self, task: AsyncTask):
        """执行异步任务"""
        try:
            # 1. 发送异步请求
            task.status = TaskStatus.RUNNING
            success = self._send_async_prompt(task)

            if not success:
                task.status = TaskStatus.ERROR
                task.error_message = "Failed to send async prompt"

                # 记录到任务历史日志
                if task_logger and task.workspace_path:
                    task_logger.complete_task(
                        task.task_id, error_message=task.error_message
                    )

                if task.on_error:
                    task.on_error(task.error_message)
                return

            task.add_step(
                TaskStep(
                    step_type="thinking",
                    content="任务已提交，开始执行...",
                )
            )

            # 2. 轮询等待结果
            self._poll_for_result(task)

        except Exception as exc:
            logger.exception(f"[AsyncTaskManager] Task {task.task_id} error: {exc}")
            task.status = TaskStatus.ERROR
            task.error_message = str(exc)

            # 记录到任务历史日志
            if task_logger and task.workspace_path:
                task_logger.complete_task(
                    task.task_id, error_message=task.error_message
                )

            if task.on_error:
                task.on_error(str(exc))

    def _send_async_prompt(self, task: AsyncTask) -> bool:
        """发送异步prompt请求"""
        try:
            base_url = f"http://127.0.0.1:{task.port}"

            body = {
                "parts": [{"type": "text", "text": task.original_text}],
            }

            response = httpx.post(
                f"{base_url}/session/{task.session_id}/prompt_async",
                json=body,
                timeout=10.0,
            )

            if response.status_code == 204:
                print(f"[AsyncTaskManager] Async prompt sent for task {task.task_id}")
                return True
            else:
                print(
                    f"[AsyncTaskManager] Failed to send async prompt: {response.status_code}"
                )
                return False

        except Exception as exc:
            print(f"[AsyncTaskManager] Send async prompt error: {exc}")
            return False

    def _check_session_status(self, task: AsyncTask) -> Optional[str]:
        """检查会话状态，返回 'busy' | 'idle' | None (error)

        注意：OpenCode API 的行为：
        - 会话 busy 时：返回 {session_id: {type: 'busy'}}
        - 会话完成时：返回 {}（空字典，会话从状态列表中移除）
        """
        try:
            base_url = f"http://127.0.0.1:{task.port}"
            response = httpx.get(
                f"{base_url}/session/status",
                timeout=5.0,
            )

            if response.status_code == 200:
                statuses = response.json()
                # ⭐ 关键逻辑：
                # - 如果 session_id 在 statuses 中 → 返回对应状态
                # - 如果 session_id 不在 statuses 中（返回 {}）→ 视为 idle（完成）
                if task.session_id in statuses:
                    status_info = statuses[task.session_id]
                    return status_info.get("type", "unknown")
                else:
                    # 会话不在状态列表中，说明已完成
                    return "idle"

            return None
        except Exception as exc:
            print(f"[AsyncTaskManager] Failed to check session status: {exc}")
            return None

    def _poll_for_result(self, task: AsyncTask):
        """轮询获取结果 - 使用 /session/status 检测会话状态"""
        base_url = f"http://127.0.0.1:{task.port}"
        start_time = time.time()
        seen_message_ids = set()
        last_message_count = 0
        last_status_check = 0
        consecutive_idle_count = 0  # 连续空闲计数

        # ⭐ 调试追踪数据
        debug_stats = {
            "last_status_change_time": start_time,
            "last_message_change_time": start_time,
            "last_tool_call_time": start_time,
            "status_history": [],  # 记录状态变化历史
            "tool_calls_count": 0,
            "messages_received": 0,
            "status_check_count": 0,
        }

        print(f"[AsyncTaskManager] Starting poll for task {task.task_id}")
        print(f"[AsyncTaskManager] Session: {task.session_id}, Port: {task.port}")

        while task.status == TaskStatus.RUNNING:
            elapsed = time.time() - start_time

            # 检查超时（1小时）
            if elapsed > self.max_duration:
                task.status = TaskStatus.TIMEOUT
                task.error_message = f"任务执行超时（>{int(self.max_duration / 60)}分钟），请尝试简化任务或分批处理"
                logger.warning(
                    f"[AsyncTaskManager] Task {task.task_id} timeout after {elapsed / 60:.1f} minutes"
                )

                # 记录到任务历史日志
                if task_logger and task.workspace_path:
                    task_logger.complete_task(
                        task.task_id, error_message=task.error_message
                    )

                if task.on_error:
                    task.on_error(task.error_message)
                return

            # ⭐ 长时间任务提示（每10分钟）
            elapsed_minutes = int(elapsed / 60)
            if elapsed_minutes > 0 and elapsed_minutes % 10 == 0:
                last_warning = getattr(task, "_last_warning_minute", 0)
                if elapsed_minutes != last_warning:
                    task._last_warning_minute = elapsed_minutes

                    # ⭐ 计算停滞时间
                    time_since_last_status_change = (
                        time.time() - debug_stats["last_status_change_time"]
                    )
                    time_since_last_message = (
                        time.time() - debug_stats["last_message_change_time"]
                    )

                    print(
                        f"[AsyncTaskManager] Task {task.task_id}: {elapsed_minutes}min | status={self._check_session_status(task)} | msgs={debug_stats['messages_received']} | tools={debug_stats['tool_calls_count']}"
                    )
                    print(
                        f"[AsyncTaskManager]   last status change: {time_since_last_status_change:.0f}s ago | last msg: {time_since_last_message:.0f}s ago"
                    )
                    print(
                        f"[AsyncTaskManager]   recent tools: {task.get_recent_tools(5)}"
                    )

            try:
                # ⭐ 定期检查会话状态 (每3秒)
                current_time = time.time()
                if current_time - last_status_check >= self.status_check_interval:
                    last_status_check = current_time
                    debug_stats["status_check_count"] += 1

                    session_status = self._check_session_status(task)

                    # ⭐ 记录状态变化
                    if (
                        not debug_stats["status_history"]
                        or debug_stats["status_history"][-1]["status"] != session_status
                    ):
                        debug_stats["status_history"].append(
                            {
                                "timestamp": current_time,
                                "status": session_status,
                                "elapsed": elapsed,
                            }
                        )
                        debug_stats["last_status_change_time"] = current_time
                        print(
                            f"[AsyncTaskManager] Task {task.task_id} status changed to: {session_status} (elapsed: {elapsed:.1f}s)"
                        )

                    # ⭐ 如果状态长时间未变，发出警告
                    time_since_status_change = (
                        current_time - debug_stats["last_status_change_time"]
                    )
                    time_since_tool = current_time - debug_stats["last_tool_call_time"]
                    if (
                        time_since_status_change > 60
                        and debug_stats["status_check_count"] % 20 == 0
                    ):
                        print(
                            f"[AsyncTaskManager] Task {task.task_id}: status={session_status}, elapsed={elapsed:.0f}s"
                        )
                        print(
                            f"[AsyncTaskManager]   no status change for {time_since_status_change:.0f}s, last tool {time_since_tool:.0f}s ago"
                        )
                        print(
                            f"[AsyncTaskManager]   recent: {task.get_recent_tools(5)}"
                        )

                    if session_status == "idle":
                        consecutive_idle_count += 1
                        logger.info(
                            f"[AsyncTaskManager] Task {task.task_id} detected idle ({consecutive_idle_count}/2)"
                        )
                        # 连续2次检测到 idle 才认为真正完成（避免误判）
                        if consecutive_idle_count >= 2:
                            logger.info(
                                f"[AsyncTaskManager] Task {task.task_id} session is idle, fetching final result..."
                            )

                            # 获取最后助手消息的内容
                            response = httpx.get(
                                f"{base_url}/session/{task.session_id}/message",
                                params={"limit": 10},
                                timeout=5.0,
                            )

                            if response.status_code == 200:
                                messages = response.json()
                                logger.info(
                                    f"[AsyncTaskManager] Fetched {len(messages)} messages for final result"
                                )
                                # 找到最后一条助手消息
                                for msg in reversed(messages):
                                    if msg.get("info", {}).get("role") == "assistant":
                                        parts = msg.get("parts", [])
                                        content = self._extract_text_content(parts)

                                        if content.strip():
                                            task.final_result = content
                                            task.status = TaskStatus.COMPLETED

                                            task.add_step(
                                                TaskStep(
                                                    step_type="response",
                                                    content=content[:200] + "..."
                                                    if len(content) > 200
                                                    else content,
                                                )
                                            )

                                            logger.info(
                                                f"[AsyncTaskManager] Task {task.task_id} completed with {len(content)} chars"
                                            )
                                            logger.info(
                                                f"[AsyncTaskManager] Final stats: tools={debug_stats['tool_calls_count']}, messages={debug_stats['messages_received']}"
                                            )

                                            # 记录到任务历史日志
                                            if task_logger and task.workspace_path:
                                                task_logger.complete_task(
                                                    task.task_id, final_result=content
                                                )

                                            if task.on_complete:
                                                task.on_complete(content)
                                            return
                                        break

                            # 如果拿不到内容，至少结束任务
                            task.status = TaskStatus.COMPLETED
                            task.final_result = "（任务完成，但未获取到响应内容）"
                            logger.info(
                                f"[AsyncTaskManager] Task {task.task_id} completed but no content found"
                            )

                            # 记录到任务历史日志
                            if task_logger and task.workspace_path:
                                task_logger.complete_task(task.task_id)

                            if task.on_complete:
                                task.on_complete(task.final_result)
                            return
                    elif session_status == "busy":
                        if consecutive_idle_count > 0:
                            print(
                                f"[AsyncTaskManager] Task {task.task_id} back to busy (was idle {consecutive_idle_count} times)"
                            )
                        consecutive_idle_count = 0  # 重置计数
                    elif session_status is None:
                        # 检查失败，继续轮询
                        print(
                            f"[AsyncTaskManager] Task {task.task_id} status check failed (returned None)"
                        )

                # 获取消息列表（用于显示进度）
                response = httpx.get(
                    f"{base_url}/session/{task.session_id}/message",
                    params={"limit": 50},
                    timeout=5.0,
                )

                if response.status_code == 200:
                    messages = response.json()

                    # 检查是否有新消息
                    current_message_count = len(messages)
                    if current_message_count != last_message_count:
                        new_count = current_message_count - last_message_count
                        last_message_count = current_message_count
                        debug_stats["messages_received"] += new_count
                        debug_stats["last_message_change_time"] = time.time()
                        print(
                            f"[AsyncTaskManager] Task {task.task_id}: {current_message_count} messages (+{new_count} new)"
                        )

                    # 处理新消息（用于显示进度）
                    for msg in messages:
                        msg_id = msg.get("info", {}).get("id", "")
                        if not msg_id or msg_id in seen_message_ids:
                            continue
                        seen_message_ids.add(msg_id)

                        # ⭐ 统计工具调用
                        parts = msg.get("parts", [])
                        for part in parts:
                            if part.get("type") == "tool":
                                debug_stats["tool_calls_count"] += 1
                                debug_stats["last_tool_call_time"] = time.time()
                                tool_name = part.get("tool", "unknown")
                                tool_status = part.get("state", {}).get(
                                    "status", "unknown"
                                )
                                # 记录到任务
                                task.add_tool_call(tool_name, tool_status)
                                print(
                                    f"[AsyncTaskManager] Task {task.task_id} tool call: {tool_name} ({tool_status})"
                                )

                        self._process_message(task, msg)

                # 等待下次轮询
                time.sleep(self.poll_interval)

            except Exception as exc:
                print(f"[AsyncTaskManager] Poll error for task {task.task_id}: {exc}")
                # FIX: traceback imported at top level
                traceback.print_exc()
                time.sleep(self.poll_interval)

    def _process_message(self, task: AsyncTask, msg: Dict[str, Any]):
        """处理单条消息 - 根据 OpenCode API 类型定义

        支持的 Part 类型:
        - text: TextPart - 文本内容
        - reasoning: ReasoningPart - 推理过程
        - tool: ToolPart - 工具调用（有 state 状态）
        - step-start/step-finish: 步骤标记
        """
        info = msg.get("info", {})
        role = info.get("role", "")
        parts = msg.get("parts", [])

        # 只处理助手消息
        if role != "assistant":
            return

        for part in parts:
            part_type = part.get("type", "")

            if part_type == "tool":
                # ToolPart - 工具调用状态跟踪
                tool_name = part.get("tool", "unknown")
                call_id = part.get("callID", "")
                state = part.get("state", {})
                status = state.get("status", "unknown")

                if status == "pending":
                    task.add_step(
                        TaskStep(
                            step_type="tool_call",
                            content=f"🔧 准备调用: {tool_name}",
                            metadata={
                                "tool": tool_name,
                                "callID": call_id,
                                "status": status,
                            },
                        )
                    )
                elif status == "running":
                    title = state.get("title", tool_name)
                    task.add_step(
                        TaskStep(
                            step_type="tool_call",
                            content=f"⏳ 执行中: {title}",
                            metadata={
                                "tool": tool_name,
                                "callID": call_id,
                                "status": status,
                            },
                        )
                    )
                elif status == "completed":
                    title = state.get("title", tool_name)
                    output = state.get("output", "")[:100]  # 截断输出
                    task.add_step(
                        TaskStep(
                            step_type="tool_result",
                            content=f"✅ {title}",
                            metadata={
                                "tool": tool_name,
                                "output": output,
                                "status": status,
                            },
                        )
                    )
                elif status == "error":
                    error = state.get("error", "Unknown error")
                    task.add_step(
                        TaskStep(
                            step_type="tool_result",
                            content=f"❌ {tool_name} 失败",
                            metadata={
                                "tool": tool_name,
                                "error": error,
                                "status": status,
                            },
                        )
                    )

            elif part_type == "reasoning":
                # ReasoningPart - AI 推理过程
                text = part.get("text", "").strip()
                if text:
                    task.add_step(
                        TaskStep(
                            step_type="thinking",
                            content=f"💭 {text[:150]}{'...' if len(text) > 150 else ''}",
                        )
                    )

            elif part_type == "text":
                # TextPart - 文本内容（可能是中间思考或最终结果）
                text = part.get("text", "").strip()
                if text and len(text) > 5:  # 忽略太短的内容
                    # 只在有实质性内容时记录，避免频繁更新
                    pass  # 暂不添加步骤，避免重复

            elif part_type == "step-start":
                # 步骤开始
                task.add_step(
                    TaskStep(
                        step_type="thinking",
                        content="🚀 开始新步骤...",
                    )
                )

            elif part_type == "step-finish":
                # 步骤完成
                reason = part.get("reason", "")
                cost = part.get("cost", 0)
                tokens = part.get("tokens", {})
                task.add_step(
                    TaskStep(
                        step_type="thinking",
                        content=f"✅ 步骤完成" + (f" ({reason})" if reason else ""),
                        metadata={"cost": cost, "tokens": tokens},
                    )
                )

    def _extract_text_content(self, parts: List[Dict[str, Any]]) -> str:
        """提取所有 text parts 的文本内容

        连接所有 TextPart 的 text 字段，形成完整响应
        """
        texts = []
        for part in parts:
            if part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    texts.append(text)
        return "".join(texts)


# 全局任务管理器实例
task_manager = AsyncTaskManager()
