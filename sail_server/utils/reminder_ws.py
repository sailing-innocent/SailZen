# -*- coding: utf-8 -*-
# @file reminder_ws.py
# @brief Reminder WebSocket Push Manager (兼容适配器，底层委托给 UserSyncHub)
# @author sailing-innocent
# @date 2026-08-03
# @version 2.0
# ---------------------------------
"""提醒推送管理器（向后兼容层）。

底层已统一委托给 UserSyncHub（按 user_id 管理 Android / Web 等多端连接），
保留 ReminderPushManager 原有方法签名，确保历史调用点与单测零破坏。
"""

from typing import Any, Dict, List, Optional

from sail_server.utils.user_sync_ws import UserSyncHub, get_user_sync_hub


class ReminderPushManager:
    """兼容旧版接口的设备推送管理器，可独立实例化（单测）或委托全局 UserSyncHub。"""

    def __init__(self, hub: Optional[UserSyncHub] = None) -> None:
        self._hub = hub or UserSyncHub()

    def register(
        self,
        device_id: str,
        socket: Any,
        user_id: int = 1,
        client_type: str = "android",
    ) -> None:
        self._hub.register(
            device_id=device_id,
            socket=socket,
            user_id=user_id,
            client_type=client_type,
            legacy_reminder=True,
        )

    def unregister(self, device_id: str) -> None:
        self._hub.unregister(device_id)

    def online_count(self) -> int:
        return self._hub.online_count()

    def online_device_ids(self) -> List[str]:
        return self._hub.online_device_ids()

    def is_online(self, device_id: str) -> bool:
        return self._hub.is_online(device_id)

    async def send_to(self, device_id: str, message: Dict[str, Any]) -> bool:
        return await self._hub.send_to(device_id, message)

    async def broadcast_reminder(
        self, reminder: Dict[str, Any], user_id: Optional[int] = None
    ) -> int:
        uid = user_id if user_id is not None else int(reminder.get("user_id") or 1)
        return await self._hub.broadcast_reminder(reminder, user_id=uid)


_push_manager: Optional[ReminderPushManager] = None


def get_reminder_push_manager() -> ReminderPushManager:
    global _push_manager
    if _push_manager is None:
        _push_manager = ReminderPushManager(hub=get_user_sync_hub())
    return _push_manager
