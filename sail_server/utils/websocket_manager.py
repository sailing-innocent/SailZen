# -*- coding: utf-8 -*-
# @file websocket_manager.py
# @brief WebSocket Connection Manager
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# WebSocket 连接管理器
# - 管理客户端连接
# - 任务进度推送
# - 订阅/取消订阅

import asyncio
import logging
import json
from typing import Dict, List, Set, Optional, Callable, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# 数据类型
# ============================================================================

@dataclass
class WSMessage:
    """WebSocket 消息"""
    type: str  # event | progress | error | ping | pong
    task_id: Optional[int] = None
    data: Dict[str, Any] = {}
    timestamp: str = ""
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps({
            "type": self.type,
            "task_id": self.task_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WSMessage":
        """从字典创建"""
        return cls(
            type=data.get("type", "unknown"),
            task_id=data.get("task_id"),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )


@dataclass
class ClientInfo:
    """客户端信息"""
    client_id: str
    connected_at: datetime
    subscribed_tasks: Set[int]
    
    def __post_init__(self):
        if self.subscribed_tasks is None:
            self.subscribed_tasks = set()


# ============================================================================
# WebSocket 管理器
# ============================================================================

class WebSocketManager:
    """
    WebSocket 连接管理器
    
    功能：
    1. 管理客户端连接
    2. 处理订阅/取消订阅
    3. 推送任务进度
    4. 广播消息
    """
    
    def __init__(self):
        # 客户端连接: client_id -> send_callback
        self._connections: Dict[str, Callable[[str], None]] = {}
        
        # 客户端信息
        self._client_info: Dict[str, ClientInfo] = {}
        
        # 任务订阅: task_id -> set of client_ids
        self._task_subscribers: Dict[int, Set[str]] = {}
        
        # 全局订阅者（接收所有事件）
        self._global_subscribers: Set[str] = set()
        
        # 锁
        self._lock = asyncio.Lock()
        
        # 统计
        self._stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "total_messages_received": 0,
        }
    
    # ========================================================================
    # 连接管理
    # ========================================================================
    
    async def connect(
        self,
        client_id: str,
        send_callback: Callable[[str], None]
    ) -> bool:
        """
        注册客户端连接
        
        Args:
            client_id: 客户端唯一标识
            send_callback: 发送消息的回调函数
        
        Returns:
            bool: 是否成功连接
        """
        async with self._lock:
            if client_id in self._connections:
                logger.warning(f"Client {client_id} already connected, updating connection")
            
            self._connections[client_id] = send_callback
            self._client_info[client_id] = ClientInfo(
                client_id=client_id,
                connected_at=datetime.utcnow()
            )
            self._stats["total_connections"] += 1
        
        logger.info(f"Client {client_id} connected")
        
        # 发送欢迎消息
        await self.send_to_client(client_id, WSMessage(
            type="connected",
            data={"client_id": client_id, "message": "Connected to WebSocket server"}
        ))
        
        return True
    
    async def disconnect(self, client_id: str):
        """
        断开客户端连接
        
        Args:
            client_id: 客户端唯一标识
        """
        async with self._lock:
            # 从所有订阅中移除
            info = self._client_info.get(client_id)
            if info:
                for task_id in list(info.subscribed_tasks):
                    await self._unsubscribe_task_locked(client_id, task_id)
                
                # 从全局订阅中移除
                self._global_subscribers.discard(client_id)
            
            # 移除连接
            self._connections.pop(client_id, None)
            self._client_info.pop(client_id, None)
        
        logger.info(f"Client {client_id} disconnected")
    
    # ========================================================================
    # 订阅管理
    # ========================================================================
    
    async def subscribe_task(self, client_id: str, task_id: int) -> bool:
        """
        订阅任务进度
        
        Args:
            client_id: 客户端标识
            task_id: 任务 ID
        
        Returns:
            bool: 是否成功订阅
        """
        async with self._lock:
            if client_id not in self._connections:
                logger.warning(f"Client {client_id} not connected")
                return False
            
            # 添加到客户端的订阅列表
            info = self._client_info.get(client_id)
            if info:
                info.subscribed_tasks.add(task_id)
            
            # 添加到任务的订阅者列表
            if task_id not in self._task_subscribers:
                self._task_subscribers[task_id] = set()
            self._task_subscribers[task_id].add(client_id)
        
        logger.debug(f"Client {client_id} subscribed to task {task_id}")
        
        # 发送确认消息
        await self.send_to_client(client_id, WSMessage(
            type="subscribed",
            task_id=task_id,
            data={"message": f"Subscribed to task {task_id}"}
        ))
        
        return True
    
    async def unsubscribe_task(self, client_id: str, task_id: int) -> bool:
        """
        取消订阅任务进度
        
        Args:
            client_id: 客户端标识
            task_id: 任务 ID
        
        Returns:
            bool: 是否成功取消订阅
        """
        async with self._lock:
            return await self._unsubscribe_task_locked(client_id, task_id)
    
    async def _unsubscribe_task_locked(self, client_id: str, task_id: int) -> bool:
        """内部取消订阅（需要持有锁）"""
        # 从客户端订阅列表移除
        info = self._client_info.get(client_id)
        if info and task_id in info.subscribed_tasks:
            info.subscribed_tasks.discard(task_id)
        
        # 从任务订阅者列表移除
        if task_id in self._task_subscribers:
            self._task_subscribers[task_id].discard(client_id)
            
            # 如果没有订阅者了，清理
            if not self._task_subscribers[task_id]:
                del self._task_subscribers[task_id]
        
        logger.debug(f"Client {client_id} unsubscribed from task {task_id}")
        return True
    
    async def subscribe_all(self, client_id: str) -> bool:
        """
        订阅所有任务事件（全局订阅）
        
        Args:
            client_id: 客户端标识
        
        Returns:
            bool: 是否成功订阅
        """
        async with self._lock:
            if client_id not in self._connections:
                return False
            
            self._global_subscribers.add(client_id)
        
        logger.debug(f"Client {client_id} subscribed to all events")
        
        await self.send_to_client(client_id, WSMessage(
            type="subscribed_all",
            data={"message": "Subscribed to all events"}
        ))
        
        return True
    
    async def unsubscribe_all(self, client_id: str) -> bool:
        """
        取消全局订阅
        
        Args:
            client_id: 客户端标识
        
        Returns:
            bool: 是否成功取消订阅
        """
        async with self._lock:
            self._global_subscribers.discard(client_id)
        
        logger.debug(f"Client {client_id} unsubscribed from all events")
        return True
    
    # ========================================================================
    # 消息发送
    # ========================================================================
    
    async def send_to_client(self, client_id: str, message: WSMessage) -> bool:
        """
        发送消息给指定客户端
        
        Args:
            client_id: 客户端标识
            message: 消息
        
        Returns:
            bool: 是否成功发送
        """
        send_callback = self._connections.get(client_id)
        if not send_callback:
            return False
        
        try:
            send_callback(message.to_json())
            self._stats["total_messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"Failed to send message to client {client_id}: {e}")
            return False
    
    async def broadcast(self, message: WSMessage) -> int:
        """
        广播消息给所有客户端
        
        Args:
            message: 消息
        
        Returns:
            int: 成功发送的客户端数量
        """
        success_count = 0
        
        async with self._lock:
            client_ids = list(self._connections.keys())
        
        for client_id in client_ids:
            if await self.send_to_client(client_id, message):
                success_count += 1
        
        return success_count
    
    async def send_to_task_subscribers(self, task_id: int, message: WSMessage) -> int:
        """
        发送消息给任务的所有订阅者
        
        Args:
            task_id: 任务 ID
            message: 消息
        
        Returns:
            int: 成功发送的客户端数量
        """
        success_count = 0
        
        async with self._lock:
            # 获取任务订阅者
            subscribers = list(self._task_subscribers.get(task_id, set()))
            
            # 获取全局订阅者
            global_subs = list(self._global_subscribers)
            
            # 合并（去重）
            all_recipients = set(subscribers + global_subs)
        
        message.task_id = task_id
        
        for client_id in all_recipients:
            if await self.send_to_client(client_id, message):
                success_count += 1
        
        return success_count
    
    # ========================================================================
    # 任务事件推送
    # ========================================================================
    
    async def notify_task_created(self, task_id: int, data: Dict[str, Any] = None):
        """通知任务创建"""
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="task_created",
            task_id=task_id,
            data=data or {}
        ))
    
    async def notify_task_started(self, task_id: int, data: Dict[str, Any] = None):
        """通知任务开始"""
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="task_started",
            task_id=task_id,
            data=data or {}
        ))
    
    async def notify_task_progress(
        self,
        task_id: int,
        progress: int,
        phase: Optional[str] = None,
        data: Dict[str, Any] = None
    ):
        """通知任务进度"""
        message_data = {
            "progress": progress,
            **(data or {})
        }
        if phase:
            message_data["phase"] = phase
        
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="progress",
            task_id=task_id,
            data=message_data
        ))
    
    async def notify_task_step(
        self,
        task_id: int,
        step_number: int,
        step_type: str,
        title: Optional[str] = None,
        data: Dict[str, Any] = None
    ):
        """通知任务步骤更新"""
        message_data = {
            "step_number": step_number,
            "step_type": step_type,
            **(data or {})
        }
        if title:
            message_data["title"] = title
        
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="step",
            task_id=task_id,
            data=message_data
        ))
    
    async def notify_task_completed(self, task_id: int, data: Dict[str, Any] = None):
        """通知任务完成"""
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="task_completed",
            task_id=task_id,
            data=data or {}
        ))
    
    async def notify_task_failed(self, task_id: int, error: str, data: Dict[str, Any] = None):
        """通知任务失败"""
        message_data = {
            "error": error,
            **(data or {})
        }
        
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="task_failed",
            task_id=task_id,
            data=message_data
        ))
    
    async def notify_task_cancelled(self, task_id: int, reason: str = "user_request"):
        """通知任务取消"""
        await self.send_to_task_subscribers(task_id, WSMessage(
            type="task_cancelled",
            task_id=task_id,
            data={"reason": reason}
        ))
    
    # ========================================================================
    # 消息处理
    # ========================================================================
    
    async def handle_message(self, client_id: str, message_data: str):
        """
        处理客户端消息
        
        Args:
            client_id: 客户端标识
            message_data: JSON 字符串
        """
        self._stats["total_messages_received"] += 1
        
        try:
            data = json.loads(message_data)
            message = WSMessage.from_dict(data)
            
            # 处理不同类型的消息
            if message.type == "ping":
                await self.send_to_client(client_id, WSMessage(type="pong"))
            
            elif message.type == "subscribe":
                task_id = message.task_id
                if task_id:
                    await self.subscribe_task(client_id, task_id)
                else:
                    # 没有指定 task_id，订阅所有事件
                    await self.subscribe_all(client_id)
            
            elif message.type == "unsubscribe":
                task_id = message.task_id
                if task_id:
                    await self.unsubscribe_task(client_id, task_id)
            
            elif message.type == "subscribe_all":
                await self.subscribe_all(client_id)
            
            elif message.type == "unsubscribe_all":
                await self.unsubscribe_all(client_id)
            
            else:
                logger.warning(f"Unknown message type: {message.type}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from client {client_id}: {e}")
            await self.send_to_client(client_id, WSMessage(
                type="error",
                data={"message": "Invalid JSON format"}
            ))
        
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            await self.send_to_client(client_id, WSMessage(
                type="error",
                data={"message": str(e)}
            ))
    
    # ========================================================================
    # 查询和统计
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "subscribed_tasks": len(self._task_subscribers),
            "global_subscribers": len(self._global_subscribers),
        }
    
    def get_client_count(self) -> int:
        """获取连接数"""
        return len(self._connections)
    
    def get_task_subscriber_count(self, task_id: int) -> int:
        """获取任务的订阅者数量"""
        return len(self._task_subscribers.get(task_id, set()))
    
    def is_client_connected(self, client_id: str) -> bool:
        """检查客户端是否连接"""
        return client_id in self._connections


# ============================================================================
# 全局实例
# ============================================================================

_ws_manager_instance: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """获取全局 WebSocket 管理器实例"""
    global _ws_manager_instance
    if _ws_manager_instance is None:
        _ws_manager_instance = WebSocketManager()
    return _ws_manager_instance


def set_websocket_manager(manager: WebSocketManager):
    """设置全局 WebSocket 管理器实例"""
    global _ws_manager_instance
    _ws_manager_instance = manager
