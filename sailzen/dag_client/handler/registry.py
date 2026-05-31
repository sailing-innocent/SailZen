"""Handler 注册表 — 统一入口。

将所有分模块的 handler 注册到 CommandBus。
外部通过 `register_handlers(bus, db, scheduler)` 一次调用完成。
"""

from __future__ import annotations

from cube.command_bus import CommandBus
from bot_server.handler import (
    health as h_health,
    project as h_project,
    batch as h_batch,
    task as h_task,
    agent as h_agent,
    event as h_event,
    pipeline as h_pipeline,
)


def register_handlers(bus: CommandBus, db, scheduler) -> None:
    """将所有命令处理器注册到 CommandBus。"""
    modules = [
        h_health,
        h_project,
        h_batch,
        h_task,
        h_agent,
        h_event,
        h_pipeline,
    ]

    all_handlers: dict = {}
    for mod in modules:
        all_handlers.update(mod.register(bus, db, scheduler))

    bus.register_many(all_handlers)
