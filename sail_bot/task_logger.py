# -*- coding: utf-8 -*-
# @file task_logger.py
# @brief 任务历史日志记录器 - 持久化保存任务执行详情
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""任务历史日志记录器。

提供任务执行历史的持久化存储，包括：
- 完整的 tool call 链
- 执行步骤详情
- 按工作区组织的任务历史
- 支持查询和检索

使用 JSON Lines 格式追加写入，避免频繁重写文件。
"""

import json
import logging
import threading
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 配置日志
logger = logging.getLogger("task_history")

from sail_bot.paths import TASK_LOG_DIR  # noqa: E402 (centralized path)


@dataclass
class TaskLogEntry:
    """单个任务的完整日志记录"""

    task_id: str
    workspace_path: str
    workspace_name: str
    task_text: str
    session_id: str
    port: int
    status: str  # pending, running, completed, error, cancelled, timeout
    created_at: str
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    tool_calls_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskLogEntry":
        return cls(**data)


@dataclass
class TaskStepLog:
    """任务执行步骤日志"""

    step_type: str  # thinking, tool_call, tool_result, response
    content: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskHistoryTracker:
    """任务历史追踪器 - 按工作区持久化任务日志"""

    _instance: Optional["TaskHistoryTracker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TaskHistoryTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._lock = threading.Lock()
        self._active_tasks: Dict[str, TaskLogEntry] = {}
        self._log_files: Dict[str, Path] = {}

        # 初始化日志目录
        TASK_LOG_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(f"[TaskHistory] Initialized, log dir: {TASK_LOG_DIR}")

    def _get_log_file(self, workspace_path: str) -> Path:
        """获取工作区的日志文件路径"""
        # FIX: hashlib imported at top level
        path_hash = hashlib.md5(workspace_path.encode()).hexdigest()[:12]
        workspace_name = Path(workspace_path).name
        filename = f"{workspace_name}_{path_hash}.jsonl"
        return TASK_LOG_DIR / filename

    def start_task(
        self,
        task_id: str,
        workspace_path: str,
        task_text: str,
        session_id: str,
        port: int,
    ) -> TaskLogEntry:
        """开始记录一个新任务"""
        workspace_name = Path(workspace_path).name

        entry = TaskLogEntry(
            task_id=task_id,
            workspace_path=workspace_path,
            workspace_name=workspace_name,
            task_text=task_text[:500],  # 限制长度
            session_id=session_id,
            port=port,
            status="running",
            created_at=datetime.now().isoformat(),
        )

        with self._lock:
            self._active_tasks[task_id] = entry

        logger.info(
            f"[TaskHistory] Started task {task_id} in {workspace_name}: {task_text[:80]}..."
        )
        return entry

    def add_step(
        self,
        task_id: str,
        step_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加任务执行步骤"""
        metadata = metadata or {}

        with self._lock:
            entry = self._active_tasks.get(task_id)
            if not entry:
                logger.warning(
                    f"[TaskHistory] Task {task_id} not found for step logging"
                )
                return

            step = TaskStepLog(
                step_type=step_type,
                content=content,
                timestamp=datetime.now().isoformat(),
                metadata=metadata,
            )
            entry.steps.append(step.to_dict())

            # 统计 tool call
            if step_type == "tool_call":
                entry.tool_calls_count += 1

        # 记录到结构化日志
        tool_name = metadata.get("tool", "unknown")
        status = metadata.get("status", "")

        if step_type == "tool_call":
            logger.info(
                f"[TaskHistory] Task {task_id} tool_call: {tool_name} status={status}"
            )
        elif step_type == "thinking":
            logger.debug(f"[TaskHistory] Task {task_id} thinking: {content[:100]}...")

    def complete_task(
        self,
        task_id: str,
        final_result: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """完成任务记录并持久化"""
        with self._lock:
            entry = self._active_tasks.pop(task_id, None)
            if not entry:
                logger.warning(f"[TaskHistory] Task {task_id} not found for completion")
                return

            # 设置完成信息
            entry.completed_at = datetime.now().isoformat()
            entry.duration_seconds = (
                datetime.fromisoformat(entry.completed_at)
                - datetime.fromisoformat(entry.created_at)
            ).total_seconds()

            if error_message:
                entry.status = "error"
                entry.error_message = error_message[:1000]  # 限制长度
            else:
                entry.status = "completed"
                entry.final_result = (final_result or "")[:5000]  # 限制长度

            # 写入日志文件
            self._persist_task(entry)

        logger.info(
            f"[TaskHistory] Completed task {task_id} in {entry.workspace_name}: "
            f"status={entry.status}, duration={entry.duration_seconds:.1f}s, "
            f"tools={entry.tool_calls_count}"
        )

    def _persist_task(self, entry: TaskLogEntry) -> None:
        """将任务记录持久化到文件"""
        try:
            log_file = self._get_log_file(entry.workspace_path)
            with open(log_file, "a", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False)
                f.write("\n")
        except Exception as exc:
            logger.error(f"[TaskHistory] Failed to persist task: {exc}")

    def get_task_history(
        self,
        workspace_path: str,
        limit: int = 10,
        include_completed: bool = True,
    ) -> List[TaskLogEntry]:
        """获取工作区的任务历史"""
        log_file = self._get_log_file(workspace_path)
        entries = []

        # 读取已持久化的任务
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = TaskLogEntry.from_dict(data)
                            if include_completed or entry.status == "running":
                                entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as exc:
                logger.error(f"[TaskHistory] Failed to read history: {exc}")

        # 添加活跃任务
        with self._lock:
            for entry in self._active_tasks.values():
                if entry.workspace_path == workspace_path:
                    if include_completed or entry.status == "running":
                        entries.append(entry)

        # 按创建时间倒序排列
        entries.sort(key=lambda x: x.created_at, reverse=True)
        return entries[:limit]

    def get_recent_tasks(self, limit: int = 20) -> List[TaskLogEntry]:
        """获取最近的所有任务（跨工作区）"""
        entries = []

        # 读取所有工作区的日志
        for log_file in TASK_LOG_DIR.glob("*.jsonl"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            entry = TaskLogEntry.from_dict(data)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as exc:
                logger.error(f"[TaskHistory] Failed to read {log_file}: {exc}")

        # 添加活跃任务
        with self._lock:
            entries.extend(self._active_tasks.values())

        # 按创建时间倒序排列
        entries.sort(key=lambda x: x.created_at, reverse=True)
        return entries[:limit]

    def get_active_task_for_workspace(
        self, workspace_path: str
    ) -> Optional[TaskLogEntry]:
        """获取工作区当前正在运行的任务"""
        with self._lock:
            for entry in self._active_tasks.values():
                if entry.workspace_path == workspace_path and entry.status == "running":
                    return entry
        return None

    def cancel_task(self, task_id: str, reason: str = "user_cancelled") -> None:
        """标记任务为已取消"""
        with self._lock:
            entry = self._active_tasks.pop(task_id, None)
            if entry:
                entry.status = "cancelled"
                entry.error_message = reason
                entry.completed_at = datetime.now().isoformat()
                self._persist_task(entry)
                logger.info(f"[TaskHistory] Cancelled task {task_id}: {reason}")


def get_task_logger() -> TaskHistoryTracker:
    """获取任务日志记录器实例"""
    return TaskHistoryTracker()

# 全局实例
task_logger = get_task_logger()
