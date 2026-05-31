"""全局依赖注入 — 单例获取/设置。

所有全局实例（Database, TaskScheduler, CommandBus, EventBus, POPOBridge）
在此集中管理，供 controller / handler / service 使用。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from bot_server.database import Database
from bot_server.repositories import DatabaseCompat
from bot_server.scheduler import TaskScheduler
from sail.dag.command_bus import CommandBus
from sail.opencode.process_manager import OpenCodeProcessManager
from sail.dag.event_bus import EventBus

# ── 全局单例 ────────────────────────────────────────────────────────

_db: Optional[DatabaseCompat] = None
_scheduler: Optional[TaskScheduler] = None
_command_bus: Optional[CommandBus] = None
_event_bus: Optional[EventBus] = None
_codemaker_mgr: Optional[OpenCodeProcessManager] = None
_popo_bridge = None
_background_tasks: set[asyncio.Task] = set()


# ── Getters ─────────────────────────────────────────────────────────


def get_db() -> DatabaseCompat:
    assert _db, "Database not initialized"
    return _db


def get_scheduler() -> TaskScheduler:
    assert _scheduler, "Scheduler not initialized"
    return _scheduler


def get_bus() -> CommandBus:
    assert _command_bus, "CommandBus not initialized"
    return _command_bus


def get_event_bus() -> EventBus:
    assert _event_bus, "EventBus not initialized"
    return _event_bus


def get_codemaker_mgr() -> Optional[OpenCodeProcessManager]:
    return _codemaker_mgr


def get_popo_bridge():
    return _popo_bridge


def track_background_task(task: asyncio.Task) -> asyncio.Task:
    """跟踪服务生命周期内启动的后台任务，便于 shutdown 时统一取消。"""
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def cancel_background_tasks() -> int:
    """取消所有已登记后台任务，返回取消数量。"""
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


def set_scheduler(scheduler: TaskScheduler) -> None:
    global _scheduler
    _scheduler = scheduler


def set_bus(bus: CommandBus) -> None:
    global _command_bus
    _command_bus = bus


def set_event_bus(eb: EventBus) -> None:
    global _event_bus
    _event_bus = eb


def set_codemaker_mgr(mgr: OpenCodeProcessManager) -> None:
    global _codemaker_mgr
    _codemaker_mgr = mgr


def set_popo_bridge(bridge) -> None:
    global _popo_bridge
    _popo_bridge = bridge
