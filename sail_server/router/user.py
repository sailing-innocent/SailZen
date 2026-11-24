# -*- coding: utf-8 -*-
# @file user.py
# @brief User Router (REST + User-Scoped Multi-Device WebSocket /api/v1/user/ws)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一 User 面路由：REST (/api/v1/user/*) + 实时多端同步 WS (/api/v1/user/ws)。"""

from __future__ import annotations

import json
import logging
import os
import traceback
import uuid

from litestar import Router, WebSocket, websocket
from litestar.di import Provide
from litestar.exceptions import WebSocketDisconnect

from sail_server.controller.user import UserController
from sail_server.db import Database, get_db_dependency
from sail_server.utils.user_sync_ws import get_user_sync_hub

logger = logging.getLogger(__name__)


def _resolve_ws_user_and_cursor(user_hint: str) -> tuple[int, int]:
    """解析 WS 归属用户 ID 与当前最新 sync_seq（独立短会话，不占长连接事务）。"""
    db = Database.get_instance().get_db_session()
    try:
        from sail_server.model.inbox import get_inbox_cursor_stats
        from sail_server.model.user import resolve_or_bootstrap_user

        profile = resolve_or_bootstrap_user(db, user_hint=user_hint or None)
        stats = get_inbox_cursor_stats(db, profile.id)
        return profile.id, stats["latest_sync_seq"]
    except Exception as exc:
        logger.warning("[user_ws] failed to resolve user/cursor, fallback user_id=1: %s", exc)
        return 1, 0
    finally:
        db.close()


@websocket("/ws")
async def user_sync_ws_handler(socket: WebSocket) -> None:
    """用户级多端实时同步 WebSocket（Android / Web / 插件共享）。"""
    token = socket.query_params.get("token", "")
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if expected and token != expected:
        await socket.close(code=4401, reason="unauthorized")
        return

    device_id = (socket.query_params.get("device_id") or "").strip()
    client_type = (socket.query_params.get("client_type") or "web").strip().lower()[:32]
    user_hint = (socket.query_params.get("user") or "").strip()
    if not device_id:
        device_id = f"{client_type}-{uuid.uuid4().hex[:12]}"

    user_id, latest_seq = _resolve_ws_user_and_cursor(user_hint)

    await socket.accept()
    hub = get_user_sync_hub()
    hub.register(
        device_id=device_id,
        socket=socket,
        user_id=user_id,
        client_type=client_type,
        legacy_reminder=False,
    )
    try:
        await socket.send_json(
            {
                "type": "connected",
                "data": {
                    "user_id": user_id,
                    "device_id": device_id,
                    "client_type": client_type,
                    "latest_sync_seq": latest_seq,
                    "online": True,
                },
            }
        )
        while True:
            text = await socket.receive_text()
            try:
                msg = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await socket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error(
            "[user_ws] error for device=%s: %s\n%s",
            device_id,
            exc,
            traceback.format_exc(),
        )
    finally:
        hub.unregister(device_id)


router = Router(
    path="/user",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        UserController,
        user_sync_ws_handler,
    ],
)
