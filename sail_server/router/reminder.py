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

from litestar import Router, WebSocket, websocket
from litestar.di import Provide
from litestar.exceptions import WebSocketDisconnect

from sail_server.controller.reminder import ReminderController
from sail_server.db import get_db_dependency
from sail_server.utils.reminder_ws import get_reminder_push_manager

logger = logging.getLogger(__name__)


@websocket("/ws")
async def reminder_ws_handler(socket: WebSocket) -> None:
    """App 长连接端点：接收 reminder.delivered 推送"""
    device_id = socket.query_params.get("device_id", "")
    token = socket.query_params.get("token", "")

    # 鉴权：与 REST 同款可选 Token（未配置则放行）
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if expected and token != expected:
        await socket.close(code=4401, reason="unauthorized")
        return
    if not device_id:
        await socket.close(code=4400, reason="device_id required")
        return

    await socket.accept()
    manager = get_reminder_push_manager()
    manager.register(device_id, socket)
    await socket.send_json(
        {"type": "connected", "data": {"device_id": device_id, "online": True}}
    )
    try:
        while True:
            text = await socket.receive_text()
            try:
                msg = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                continue
            if msg.get("type") == "ping":
                await socket.send_json({"type": "pong"})
            # 其余客户端报文 M1 忽略
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"[reminder_ws] connection error for {device_id}: {e}")
    finally:
        manager.unregister(device_id)


router = Router(
    path="/reminder",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        ReminderController,
        reminder_ws_handler,
    ],
)
