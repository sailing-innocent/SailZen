# -*- coding: utf-8 -*-
# @file events.py
# @brief 内嵌事件总线
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZen DAG Client 内嵌事件总线。

独立于 sail.dag.event_bus，提供 SSE 订阅、事件持久化和通知能力。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventBus:
    """DAG Client 事件总线。

    Usage::

        bus = EventBus()
        queue = bus.subscribe("run_123")
        await bus.emit({"type": "node.completed", "entity_id": "run_123", ...})
        # 在另一个 coroutine 中:
        event = await queue.get()
    """

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._global_subscribers: List[asyncio.Queue] = []
        self._db_logger: Optional[Callable] = None
        self._external_handlers: List[Callable] = []

    def set_db_logger(self, logger_fn: Callable) -> None:
        self._db_logger = logger_fn

    def add_handler(self, handler: Callable) -> None:
        """添加外部事件处理器。"""
        self._external_handlers.append(handler)

    def remove_handler(self, handler: Callable) -> None:
        if handler in self._external_handlers:
            self._external_handlers.remove(handler)

    async def emit(self, event: Dict[str, Any]) -> None:
        event.setdefault("timestamp", datetime.now().isoformat())

        # 1. 持久化
        if self._db_logger:
            try:
                await self._db_logger(event)
            except Exception:
                logger.exception("EventBus: DB log failed")

        # 2. 外部处理器
        for handler in self._external_handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("EventBus: external handler failed")

        # 3. SSE 广播
        await self._broadcast(event)

    def subscribe(self, run_id: str, maxsize: int = 200) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.setdefault(run_id, []).append(queue)
        logger.debug("SSE subscribe: run_id=%s (total=%d)", run_id, len(self._subscribers[run_id]))
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs:
            self._subscribers.pop(run_id, None)

    def subscribe_global(self, maxsize: int = 200) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._global_subscribers.append(queue)
        return queue

    def unsubscribe_global(self, queue: asyncio.Queue) -> None:
        if queue in self._global_subscribers:
            self._global_subscribers.remove(queue)

    async def _broadcast(self, event: Dict[str, Any]) -> None:
        payload = json.dumps(event, ensure_ascii=False, default=str)
        entity_id = event.get("entity_id", "")
        run_id = event.get("run_id", entity_id)

        targets: List[asyncio.Queue] = []
        if run_id and run_id in self._subscribers:
            targets.extend(self._subscribers[run_id])
        targets.extend(self._global_subscribers)

        dead: List[asyncio.Queue] = []
        for q in targets:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    dead.append(q)

        for q in dead:
            if run_id and run_id in self._subscribers:
                subs = self._subscribers[run_id]
                if q in subs:
                    subs.remove(q)
            if q in self._global_subscribers:
                self._global_subscribers.remove(q)

    @property
    def subscriber_count(self) -> int:
        total = len(self._global_subscribers)
        for subs in self._subscribers.values():
            total += len(subs)
        return total
