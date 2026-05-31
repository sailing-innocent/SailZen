"""Session & POPO Controller — /sessions, /popo 端点。"""

from __future__ import annotations

from typing import List

from litestar import get, post
from litestar.response import Response

from bot_server.deps import get_bus, get_popo_bridge
from cube.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


# ── POPO 状态 ───────────────────────────────────────────────────────


@get("/popo/status")
async def get_popo_status() -> dict:
    """获取 POPO Bridge 连接状态。"""
    bridge = get_popo_bridge()
    if bridge:
        return bridge.status_dict
    return {"running": False, "connected": False, "message": "POPOBridge not initialized"}


# ── CodeMaker 会话管理 ──────────────────────────────────────────────


@get("/sessions")
async def list_cm_sessions() -> List[dict]:
    result = await get_bus().dispatch(_dash_cmd("cm_list"))
    return result.data or []


@post("/sessions/start")
async def start_cm_session(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("cm_start", target=data.get("target", "")))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error}, status_code=400)


@post("/sessions/stop")
async def stop_cm_session(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("cm_stop", target=data.get("target", "")))
    return Response({"ok": result.success, "text": result.text})
