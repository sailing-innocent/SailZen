"""Event Controller — /events 端点 + GlobalSSE。"""

from __future__ import annotations

import asyncio
from typing import List

from litestar import Controller, get, Request
from litestar.response import Stream

from bot_server.deps import get_bus, get_event_bus
from cube.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


@get("/events")
async def list_events(entity_type: str = "", entity_id: str = "",
                      limit: int = 100) -> List[dict]:
    result = await get_bus().dispatch(
        _dash_cmd("list_events", entity_type=entity_type,
                  entity_id=entity_id, limit=limit))
    return result.data or []


class GlobalSSEController(Controller):
    """全局 SSE 事件流 Controller。"""
    path = "/events"

    @get("/sse")
    async def stream_global(self, request: Request) -> Stream:
        """全局 SSE 事件流，推送所有系统事件。"""

        async def event_generator():
            eb = get_event_bus()
            queue = eb.subscribe_global()
            try:
                while True:
                    if not request.is_connected:
                        break
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=15.0)
                        yield f"data: {data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                eb.unsubscribe_global(queue)

        return Stream(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
