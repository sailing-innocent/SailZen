# -*- coding: utf-8 -*-
# @file user_sync_ws.py
# @brief User-Scoped Multi-Device WebSocket Sync Hub (Android / Web 统一实时同步)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""用户级多端实时同步中枢（UserSyncHub）。

按 user_id 管理该用户下的全部在线终端连接（Android App、Web 浏览器标签页等），
统一广播：
- inbox.item_upserted : 新增或更新收件箱条目（携带 should_notify 决策）
- inbox.item_resolved : 某端已回复/完成/忽略/自动消解 → 其余端立即可视更新并撤回系统通知
- profile.updated     : UserProfile（安静时段/昵称/偏好）跨端秒级同步
- reminder.delivered  : 兼容旧版 /api/v1/reminder/ws 客户端的推送报文
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceConnection:
    """单个终端的 WebSocket 连接句柄。"""

    user_id: int
    device_id: str
    socket: Any
    client_type: str = "android"  # android | web | cli | vscode
    legacy_reminder: bool = False
    connected_at: datetime = field(default_factory=datetime.now)


class UserSyncHub:
    """按用户维度维护的多端 WebSocket 推送与状态同步中枢。

    使用 threading.Lock 保护极小的 dict 临界区，避免跨事件循环绑定问题。
    """

    def __init__(self) -> None:
        # device_id -> DeviceConnection
        self._connections: Dict[str, DeviceConnection] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def register(
        self,
        device_id: str,
        socket: Any,
        user_id: int = 1,
        client_type: str = "android",
        legacy_reminder: bool = False,
    ) -> None:
        with self._lock:
            is_reconnect = device_id in self._connections
            self._connections[device_id] = DeviceConnection(
                user_id=user_id,
                device_id=device_id,
                socket=socket,
                client_type=client_type or "android",
                legacy_reminder=legacy_reminder,
            )
        action = "re-connected (replace socket)" if is_reconnect else "registered"
        logger.info(
            "[user_sync_ws] user=%s device=%s (%s) %s, online=%d",
            user_id,
            device_id,
            client_type,
            action,
            self.online_count(),
        )

    def unregister(self, device_id: str) -> None:
        with self._lock:
            removed = self._connections.pop(device_id, None)
        if removed is not None:
            logger.info(
                "[user_sync_ws] user=%s device=%s unregistered, online=%d",
                removed.user_id,
                device_id,
                self.online_count(),
            )

    def online_count(self, user_id: Optional[int] = None) -> int:
        with self._lock:
            if user_id is None:
                return len(self._connections)
            return sum(1 for c in self._connections.values() if c.user_id == user_id)

    def online_device_ids(self, user_id: Optional[int] = None) -> List[str]:
        with self._lock:
            if user_id is None:
                return list(self._connections.keys())
            return [
                c.device_id
                for c in self._connections.values()
                if c.user_id == user_id
            ]

    def is_online(self, device_id: str) -> bool:
        with self._lock:
            return device_id in self._connections

    def online_summary(self, user_id: int) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "device_id": c.device_id,
                    "client_type": c.client_type,
                    "connected_at": c.connected_at.isoformat(),
                }
                for c in self._connections.values()
                if c.user_id == user_id
            ]

    # ------------------------------------------------------------------
    # 发送与广播
    # ------------------------------------------------------------------

    async def send_to(self, device_id: str, message: Dict[str, Any]) -> bool:
        """向指定设备发送报文，发送失败则摘除并返回 False。"""
        with self._lock:
            conn = self._connections.get(device_id)
        if conn is None:
            return False
        try:
            await conn.socket.send_text(
                json.dumps(message, ensure_ascii=False, default=str)
            )
            return True
        except Exception as exc:
            logger.warning("[user_sync_ws] send to %s failed: %s", device_id, exc)
            self.unregister(device_id)
            return False

    async def broadcast_to_user(
        self,
        user_id: int,
        event_type: str,
        data: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
        exclude_device_id: Optional[str] = None,
        client_types: Optional[List[str]] = None,
    ) -> int:
        message: Dict[str, Any] = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        if extra:
            message.update(extra)

        with self._lock:
            targets = [
                c.device_id
                for c in self._connections.values()
                if c.user_id == user_id
                and (exclude_device_id is None or c.device_id != exclude_device_id)
                and (client_types is None or c.client_type in client_types)
            ]

        sent = 0
        for device_id in targets:
            if await self.send_to(device_id, message):
                sent += 1
        return sent

    async def broadcast_inbox_upserted(
        self,
        user_id: int,
        item: Dict[str, Any],
        should_notify: bool = True,
        exclude_device_id: Optional[str] = None,
    ) -> int:
        return await self.broadcast_to_user(
            user_id=user_id,
            event_type="inbox.item_upserted",
            data=item,
            extra={"should_notify": bool(should_notify)},
            exclude_device_id=exclude_device_id,
        )

    async def broadcast_inbox_resolved(
        self,
        user_id: int,
        payload: Dict[str, Any],
        exclude_device_id: Optional[str] = None,
    ) -> int:
        return await self.broadcast_to_user(
            user_id=user_id,
            event_type="inbox.item_resolved",
            data=payload,
            exclude_device_id=exclude_device_id,
        )

    async def broadcast_profile_updated(
        self,
        user_id: int,
        profile: Dict[str, Any],
        exclude_device_id: Optional[str] = None,
    ) -> int:
        return await self.broadcast_to_user(
            user_id=user_id,
            event_type="profile.updated",
            data=profile,
            exclude_device_id=exclude_device_id,
        )

    async def broadcast_reminder(
        self, reminder: Dict[str, Any], user_id: int = 1
    ) -> int:
        """兼容广播 reminder.delivered 到该用户的全部在线设备（旧版 Android 兼容）。"""
        return await self.broadcast_to_user(
            user_id=user_id,
            event_type="reminder.delivered",
            data=reminder,
        )

    # ------------------------------------------------------------------
    # 同步上下文安全调度（供同步 model 函数调用）
    # ------------------------------------------------------------------

    def fire_and_forget(self, coro: Any) -> bool:
        """在当前运行中的事件循环调度异步广播；无运行循环（如同步单测）时安全跳过。"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
            return True
        except RuntimeError:
            # 防止未 await 的 coroutine 告警
            if asyncio.iscoroutine(coro):
                coro.close()
            return False


_hub: Optional[UserSyncHub] = None


def get_user_sync_hub() -> UserSyncHub:
    global _hub
    if _hub is None:
        _hub = UserSyncHub()
    return _hub
