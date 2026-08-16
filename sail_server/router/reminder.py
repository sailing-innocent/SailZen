# -*- coding: utf-8 -*-
# @file reminder.py
# @brief Reminder Router (REST + WebSocket 长连接)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒模块路由（Android App M1）

- REST：/api/v1/reminder/...（ReminderController）
- WS ：/api/v1/reminder/ws?device_id=<uuid>&token=<tok>
  1. 若 SAILZEN_API_TOKEN 已设置且 token 不符 → close(4401)
  2. accept → 注册到 ReminderPushManager → 回 connected 报文
  3. {"type":"ping"} → {"type":"pong"}，其余忽略
  4. 断开/异常 → unregister
"""

import json
import logging
import os
import traceback

from litestar import Router, WebSocket, websocket
from litestar.di import Provide
from litestar.exceptions import WebSocketDisconnect

from sail_server.controller.reminder import ReminderController
from sail_server.db import get_db_dependency
from sail_server.utils.reminder_ws import get_reminder_push_manager

logger = logging.getLogger(__name__)


def _client_address(socket: WebSocket) -> str:
    """提取 WebSocket 客户端地址，兼容 client 为空的情况。"""
    client = getattr(socket, "client", None)
    if client and isinstance(client, tuple) and len(client) >= 2:
        return f"{client[0]}:{client[1]}"
    return "unknown"


def _token_preview(token: str) -> str:
    """Token 脱敏预览，仅保留前 4 位。"""
    if not token:
        return "(empty)"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


@websocket("/ws")
async def reminder_ws_handler(socket: WebSocket) -> None:
    """App 长连接端点：接收 reminder.delivered 推送"""
    client_addr = _client_address(socket)
    device_id = socket.query_params.get("device_id", "")
    token = socket.query_params.get("token", "")
    user_agent = socket.headers.get("user-agent", "")

    logger.info(
        f"[reminder_ws] connection attempt from {client_addr}, "
        f"device_id={device_id or '(empty)'}, "
        f"token={_token_preview(token)}, "
        f"ua={user_agent[:60] if user_agent else '(none)'}"
    )

    # 鉴权：与 REST 同款可选 Token（未配置则放行）
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if expected and token != expected:
        logger.warning(
            f"[reminder_ws] auth failed for {client_addr}, device_id={device_id or '(empty)'}, "
            f"expected={_token_preview(expected)}, got={_token_preview(token)}"
        )
        await socket.close(code=4401, reason="unauthorized")
        return
    if not device_id:
        logger.warning(f"[reminder_ws] rejected {client_addr}: device_id required")
        await socket.close(code=4400, reason="device_id required")
        return

    await socket.accept()
    logger.info(f"[reminder_ws] connection accepted for {device_id} from {client_addr}")

    manager = get_reminder_push_manager()
    manager.register(device_id, socket)
    try:
        await socket.send_json(
            {"type": "connected", "data": {"device_id": device_id, "online": True}}
        )
        while True:
            text = await socket.receive_text()
            logger.debug(f"[reminder_ws] received from {device_id}: {text[:200]}")
            try:
                msg = json.loads(text)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"[reminder_ws] invalid json from {device_id}: {e}")
                continue
            if msg.get("type") == "ping":
                logger.debug(f"[reminder_ws] ping from {device_id}")
                await socket.send_json({"type": "pong"})
            # 其余客户端报文 M1 忽略
    except WebSocketDisconnect as e:
        logger.info(
            f"[reminder_ws] client {device_id} disconnected from {client_addr}, "
            f"code={getattr(e, 'code', 'unknown')}"
        )
    except Exception as e:
        logger.error(
            f"[reminder_ws] connection error for {device_id} from {client_addr}: "
            f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        )
    finally:
        logger.info(f"[reminder_ws] cleaning up {device_id} from {client_addr}")
        manager.unregister(device_id)


router = Router(
    path="/reminder",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        ReminderController,
        reminder_ws_handler,
    ],
)
