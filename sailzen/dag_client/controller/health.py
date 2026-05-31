"""Health Controller — /health 端点。"""

from __future__ import annotations

from litestar import get

from bot_server.deps import get_bus
from cube.command_bus import Command, Source, Role


def _dash_cmd(name: str, **args) -> Command:
    return Command(name=name, args=args, source=Source.DASHBOARD,
                   actor="dashboard", role=Role.ADMIN)


@get("/health")
async def health_check() -> dict:
    result = await get_bus().dispatch(_dash_cmd("health"))
    return result.data if result.success else {"status": "error", "error": result.error}
