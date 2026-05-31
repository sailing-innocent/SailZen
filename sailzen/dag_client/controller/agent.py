"""Agent Controller — /agents 端点。"""

from __future__ import annotations

from typing import List

from litestar import get, post
from litestar.response import Response

from bot_server.deps import get_bus
from sail.dag.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


@get("/agents")
async def list_agents(status: str = "") -> List[dict]:
    result = await get_bus().dispatch(_dash_cmd("list_agents", status=status))
    return result.data or []


@post("/agents/register")
async def register_agent(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("register_agent", **data))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error}, status_code=400)


@post("/agents/{agent_id:str}/heartbeat")
async def agent_heartbeat(agent_id: str, data: dict) -> Response:
    result = await get_bus().dispatch(
        _dash_cmd("heartbeat", agent_id=agent_id, **data))
    return Response(result.data or {"ack": True})
