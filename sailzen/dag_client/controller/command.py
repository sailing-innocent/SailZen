"""Command Controller — /commands 通用命令端点。"""

from __future__ import annotations

from litestar import post
from litestar.response import Response

from bot_server.deps import get_bus
from cube.command_bus import Command, Source, Role


@post("/commands")
async def execute_command(data: dict) -> Response:
    """通用命令执行端点。Dashboard 可用此端点执行任意命令。"""
    cmd = Command(
        name=data.get("command", ""),
        args=data.get("args", {}),
        source=Source.DASHBOARD,
        actor="dashboard",
        role=Role.ADMIN,
    )
    result = await get_bus().dispatch(cmd)
    if result.success:
        return Response({"ok": True, "data": result.data, "text": result.text})
    return Response({"ok": False, "error": result.error, "text": result.text},
                    status_code=400)
