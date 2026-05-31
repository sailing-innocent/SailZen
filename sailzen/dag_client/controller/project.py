"""Project & Workspace Controller — /projects, /workspaces 端点。"""

from __future__ import annotations

from typing import List

from litestar import get, post
from litestar.response import Response

from bot_server.deps import get_bus
from cube.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


# ── Projects ────────────────────────────────────────────────────────


@get("/projects")
async def list_projects() -> List[dict]:
    result = await get_bus().dispatch(_dash_cmd("list_projects"))
    return result.data or []


@post("/projects")
async def create_project(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("create_project", **data))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error}, status_code=400)


@get("/projects/{project_id:str}")
async def get_project(project_id: str) -> Response:
    result = await get_bus().dispatch(_dash_cmd("get_project", project_id=project_id))
    if result.success:
        return Response(result.data)
    return Response({"error": result.error}, status_code=404)


# ── Workspaces ──────────────────────────────────────────────────────


@get("/workspaces")
async def list_workspaces(project_id: str = "") -> List[dict]:
    result = await get_bus().dispatch(
        _dash_cmd("list_workspaces", project_id=project_id))
    return result.data or []


@post("/workspaces")
async def create_workspace(data: dict) -> Response:
    result = await get_bus().dispatch(_dash_cmd("create_workspace", **data))
    if result.success:
        return Response(result.data, status_code=201)
    return Response({"error": result.error}, status_code=400)
