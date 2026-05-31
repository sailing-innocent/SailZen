"""CubeClaw EventBus — 统一事件分发层。

职责:
  1. 接收 CommandBus 产生的事件
  2. 分发到 SSE 订阅者（Dashboard 实时更新）
  3. 分发到 POPO 通知（重要事件自动推送）
  4. 写入 event_logs 表（持久化审计）

事件格式:
  {
    "type": "task.completed",
    "entity_type": "task",
    "entity_id": "xxx",
    "data": {...},
    "source": "dashboard" | "popo" | "bot" | "system",
    "actor": "user_id",
    "timestamp": "ISO8601",
  }
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── 事件重要性分级 ──────────────────────────────────────────────────

# 这些事件类型会自动推送到 POPO
_POPO_NOTIFY_EVENTS: Set[str] = {
    "batch.completed",
    "batch.failed",
    "task.completed",
    "task.blocked",
    "task.resolved",
    "pipeline_run.started",
    "pipeline_run.completed",
    "pipeline_run.failed",
    "agent.offline",
    "system.error",
}

# 所有事件都推送到 SSE
# 只有上面列出的重要事件推送到 POPO


# ── EventBus ────────────────────────────────────────────────────────


class EventBus:
    """统一事件总线。

    Usage::

        bus = EventBus()
        bus.set_popo_sender(popo_bridge.send_notification)
        bus.set_db_logger(database.log_event)

        # 从 CommandBus 接收事件
        command_bus.on_events(bus.emit)

        # SSE 订阅
        async for data in bus.subscribe("run_123"):
            ...
    """

    def __init__(self):
        # SSE 订阅: run_id → [asyncio.Queue, ...]
        self._sse_subscribers: Dict[str, List[asyncio.Queue]] = {}
        # 全局 SSE 订阅（监听所有事件）
        self._global_subscribers: List[asyncio.Queue] = []
        # POPO 发送回调
        self._popo_sender: Optional[Callable] = None
        # DB 事件记录回调
        self._db_logger: Optional[Callable] = None

    # ── 配置 ────────────────────────────────────────────────────────

    def set_popo_sender(self, sender: Callable) -> None:
        """设置 POPO 通知发送函数。签名: async (text: str, **kwargs) -> None"""
        self._popo_sender = sender

    def set_db_logger(self, logger_fn: Callable) -> None:
        """设置 DB 事件日志函数。签名: async (event_dict) -> None"""
        self._db_logger = logger_fn

    # ── 发射事件 ────────────────────────────────────────────────────

    async def emit(self, event: Dict[str, Any]) -> None:
        """发射一个事件，分发到所有订阅者。"""
        event.setdefault("timestamp", datetime.now().isoformat())

        # 1. 持久化到 DB
        if self._db_logger:
            try:
                await self._db_logger(event)
            except Exception:
                logger.exception("EventBus: DB 日志写入失败")

        # 2. SSE 推送
        await self._broadcast_sse(event)

        # 3. POPO 通知（仅重要事件）
        if event.get("type") in _POPO_NOTIFY_EVENTS and self._popo_sender:
            try:
                text = self._format_popo_notification(event)
                if text:
                    await self._popo_sender(text)
            except Exception:
                logger.exception("EventBus: POPO 通知发送失败")

    # ── SSE 订阅管理 ────────────────────────────────────────────────

    def subscribe(self, run_id: str, maxsize: int = 200) -> asyncio.Queue:
        """创建一个 SSE 订阅队列。"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._sse_subscribers.setdefault(run_id, []).append(queue)
        logger.debug("SSE 订阅: run_id=%s (total=%d)", run_id,
                      len(self._sse_subscribers[run_id]))
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """移除 SSE 订阅。"""
        subs = self._sse_subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._sse_subscribers.pop(run_id, None)

    def subscribe_global(self, maxsize: int = 200) -> asyncio.Queue:
        """创建全局 SSE 订阅（监听所有事件）。"""
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._global_subscribers.append(queue)
        return queue

    def unsubscribe_global(self, queue: asyncio.Queue) -> None:
        if queue in self._global_subscribers:
            self._global_subscribers.remove(queue)

    # ── 内部方法 ────────────────────────────────────────────────────

    async def _broadcast_sse(self, event: Dict[str, Any]) -> None:
        """广播事件到对应的 SSE 队列。"""
        payload = json.dumps(event, ensure_ascii=False, default=str)

        # 按 entity_id 路由（pipeline run = batch_id）
        entity_id = event.get("entity_id", "")
        # 也尝试 run_id 字段
        run_id = event.get("run_id", entity_id)

        targets: List[asyncio.Queue] = []
        if run_id and run_id in self._sse_subscribers:
            targets.extend(self._sse_subscribers[run_id])
        targets.extend(self._global_subscribers)

        dead: List[asyncio.Queue] = []
        for q in targets:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # 队列满了，尝试丢弃最老的
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    dead.append(q)

        # 清理死队列
        for q in dead:
            if run_id and run_id in self._sse_subscribers:
                subs = self._sse_subscribers[run_id]
                if q in subs:
                    subs.remove(q)
            if q in self._global_subscribers:
                self._global_subscribers.remove(q)

    def _format_popo_notification(self, event: Dict[str, Any]) -> Optional[str]:
        """将事件格式化为 POPO 通知文本。"""
        etype = event.get("type", "")
        data = event.get("data", {})
        entity_id = event.get("entity_id", "")[:16]

        if etype == "pipeline_run.started":
            return self._format_pipeline_started(data, entity_id)
        if etype == "task.completed":
            return self._format_task_completed(data, entity_id)

        formatters = {
            "batch.completed": lambda: f"✅ Batch {entity_id} 已完成",
            "batch.failed": lambda: f"❌ Batch {entity_id} 失败",
            "task.blocked": lambda: (
                f"🚫 Task BLOCKED: {data.get('type', '?')} ({entity_id})\n"
                f"原因: {data.get('error', 'unknown')}"
            ),
            "task.resolved": lambda: f"✅ Task {entity_id} 已解决（人工介入）",
            "pipeline_run.completed": lambda: (
                f"✅ Pipeline 完成: {data.get('pipeline_name', entity_id)}"
            ),
            "pipeline_run.failed": lambda: (
                f"❌ Pipeline 失败: {data.get('pipeline_name', entity_id)}"
            ),
            "agent.offline": lambda: f"⚠️ Agent 离线: {data.get('name', entity_id)}",
            "system.error": lambda: f"🔴 系统错误: {data.get('message', 'unknown')}",
        }

        formatter = formatters.get(etype)
        return formatter() if formatter else None

    @staticmethod
    def _format_pipeline_started(data: dict, entity_id: str) -> str:
        """格式化 Pipeline 启动通知，包含 SubBatch 切分详情。"""
        name = data.get("pipeline_name", entity_id)
        init = data.get("init_result", {})
        tasks = data.get("tasks", 0)

        lines = [f"🚀 Pipeline 启动: {name}"]

        if init:
            lines.append(f"  基准分支: {init.get('predecessor_branch', '?')}")
            lines.append(f"  总 commit: {init.get('total_commits', '?')}, Tasks: {tasks}")

            sbs = init.get("subbatches", [])
            if sbs:
                lines.append("  ── SubBatch 切分 ──")
                for sb in sbs:
                    suffix = sb.get("suffix", "?")
                    count = sb.get("commit_count", 0)
                    start = sb.get("start_commit", "?")
                    end = sb.get("end_commit", "?")
                    branch = sb.get("branch", "")
                    lines.append(
                        f"  _{suffix}: {start}..{end} ({count} commits)"
                        f"  → {branch}"
                    )
        else:
            lines.append(f"  Tasks: {tasks}")

        return "\n".join(lines)

    @staticmethod
    def _format_task_completed(data: dict, entity_id: str) -> str:
        """格式化 Task 完成通知，对 summary 类型展示 commit 切分信息。"""
        task_type = data.get("task_type", "")
        label = data.get("task_label", entity_id)
        pipeline = data.get("pipeline_name", "")
        summary_text = data.get("summary", "")

        if task_type == "summary" and summary_text:
            return (
                f"📋 Summary 完成: {label} [{pipeline}]\n"
                f"  {summary_text}"
            )

        return (
            f"📋 Task 完成: {label} [{pipeline}]"
        )

    # ── 统计 ────────────────────────────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        total = len(self._global_subscribers)
        for subs in self._sse_subscribers.values():
            total += len(subs)
        return total
