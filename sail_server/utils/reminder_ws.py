# -*- coding: utf-8 -*-
# @file reminder_ws.py
# @brief Reminder WebSocket Push Manager (设备寻址推送)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒推送管理器（Android App M1）

与 utils/websocket_manager.py（任务订阅语义）相互独立：
本模块是轻量的 "device_id → WebSocket" 字典 + 广播，专用于把
reminder.delivered 报文推给在线 App 设备。

推送失败（无在线设备）不视为错误——客户端由 WorkManager 轮询
/api/v1/reminder/pending 兜回（设计文档通道 2 语义）。
"""

import json
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReminderPushManager:
    """设备寻址推送管理器

    说明：临界区极小（dict 读写），使用 threading.Lock 而非 asyncio.Lock，
    避免单例跨事件循环（如 pytest 多次 asyncio.run）时的 loop 绑定问题。
    """

    def __init__(self) -> None:
        # device_id -> 具有 async send_text(str) 方法的对象（Litestar WebSocket 或 fake）
        self._devices: Dict[str, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def register(self, device_id: str, socket: Any) -> None:
        with self._lock:
            if device_id in self._devices:
                logger.info(f"[reminder_ws] device {device_id} re-connected, replace socket")
            self._devices[device_id] = socket
        logger.info(
            f"[reminder_ws] device {device_id} registered, online={self.online_count()}"
        )

    def unregister(self, device_id: str) -> None:
        with self._lock:
            removed = self._devices.pop(device_id, None)
        if removed is not None:
            logger.info(
                f"[reminder_ws] device {device_id} unregistered, online={self.online_count()}"
            )

    def online_count(self) -> int:
        with self._lock:
            return len(self._devices)

    def online_device_ids(self) -> List[str]:
        with self._lock:
            return list(self._devices.keys())

    def is_online(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._devices

    # ------------------------------------------------------------------
    # 推送
    # ------------------------------------------------------------------

    async def send_to(self, device_id: str, message: Dict[str, Any]) -> bool:
        """向指定设备发送报文，失败（连接已死）则摘除并返回 False"""
        with self._lock:
            socket = self._devices.get(device_id)
        if socket is None:
            return False
        try:
            await socket.send_text(json.dumps(message, ensure_ascii=False, default=str))
            return True
        except Exception as e:
            logger.warning(f"[reminder_ws] send to {device_id} failed: {e}")
            self.unregister(device_id)
            return False

    async def broadcast_reminder(self, reminder: Dict[str, Any]) -> int:
        """广播 reminder.delivered 报文到全部在线设备，返回成功送达数"""
        message = {
            "type": "reminder.delivered",
            "data": reminder,
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            targets = list(self._devices.keys())
        sent = 0
        for device_id in targets:
            if await self.send_to(device_id, message):
                sent += 1
        if sent == 0:
            # 无在线设备不视为错误：客户端轮询 /pending 兜回
            logger.debug(
                f"[reminder_ws] no online device for reminder {reminder.get('id')}"
            )
        return sent


# ============================================================================
# 模块级单例
# ============================================================================

_push_manager: Optional[ReminderPushManager] = None


def get_reminder_push_manager() -> ReminderPushManager:
    global _push_manager
    if _push_manager is None:
        _push_manager = ReminderPushManager()
    return _push_manager
