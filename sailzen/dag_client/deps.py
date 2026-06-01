# -*- coding: utf-8 -*-
# @file deps.py
# @brief 全局依赖注入
# @author sailing-innocent
# @date 2025-06-02
# @version 3.0
# ---------------------------------
"""SailZen DAG Client 全局依赖注入。

所有全局实例（Database, Scheduler, Executor, EventBus, Store, Bridge）
在此集中管理，供 API / Executor / Scheduler 使用。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from sailzen.dag_client.database import Database
from sailzen.dag_client.repositories import DatabaseCompat
from sailzen.dag_client.scheduler import DAGScheduler
from sailzen.dag_client.executor import DAGExecutor
from sailzen.dag_client.events import EventBus
from sailzen.dag_client.store import DAGStore
from sailzen.dag_client.opencode_bridge import OpenCodeBridge

# ── 全局单例 ────────────────────────────────────────────────────────

_db: Optional[DatabaseCompat] = None
_scheduler: Optional[DAGScheduler] = None
_executor: Optional[DAGExecutor] = None
_event_bus: Optional[EventBus] = None
_store: Optional[DAGStore] = None
_bridge: Optional[OpenCodeBridge] = None
_background_tasks: set[asyncio.Task] = set()


# ── Getters ─────────────────────────────────────────────────────────

def get_db() -> DatabaseCompat:
    assert _db, "Database not initialized"
    return _db


def get_scheduler() -> DAGScheduler:
    assert _scheduler, "Scheduler not initialized"
    return _scheduler


def get_executor() -> Optional[DAGExecutor]:
    return _executor


def get_event_bus() -> EventBus:
    assert _event_bus, "EventBus not initialized"
    return _event_bus


def get_store() -> DAGStore:
    assert _store, "Store not initialized"
    return _store


def get_bridge() -> Optional[OpenCodeBridge]:
    return _bridge


def track_background_task(task: asyncio.Task) -> asyncio.Task:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def cancel_background_tasks() -> int:
    count = len(_background_tasks)
    if not count:
        return 0
    tasks = list(_background_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    _background_tasks.clear()
    return count


# ── Setters ─────────────────────────────────────────────────────────

def set_db(db: DatabaseCompat) -> None:
    global _db
    _db = db


def set_scheduler(scheduler: DAGScheduler) -> None:
    global _scheduler
    _scheduler = scheduler


def set_executor(executor: DAGExecutor) -> None:
    global _executor
    _executor = executor


def set_event_bus(eb: EventBus) -> None:
    global _event_bus
    _event_bus = eb


def set_store(store: DAGStore) -> None:
    global _store
    _store = store


def set_bridge(bridge: OpenCodeBridge) -> None:
    global _bridge
    _bridge = bridge
