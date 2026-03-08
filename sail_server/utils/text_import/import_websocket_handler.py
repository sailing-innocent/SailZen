# -*- coding: utf-8 -*-
# @file import_websocket_handler.py
# @brief 导入任务 WebSocket 通知处理器
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
导入任务的 WebSocket 进度通知处理器
集成 TextImportTaskHandler 和 WebSocketManager
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from sail_server.utils.websocket_manager import WebSocketManager, WSMessage
from sail_server.utils.text_import.text_import_task import ImportProgress, ImportStage

logger = logging.getLogger(__name__)


class ImportWebSocketNotifier:
    """导入任务 WebSocket 通知器"""
    
    def __init__(self, ws_manager: WebSocketManager, task_id: int):
        """
        Args:
            ws_manager: WebSocket 管理器
            task_id: 任务ID
        """
        self.ws_manager = ws_manager
        self.task_id = task_id
        self.last_progress = 0
        self.last_update = datetime.utcnow()
    
    async def on_progress(self, progress: ImportProgress):
        """进度回调 - 由 TextImportTaskHandler 调用
        
        Args:
            progress: 导入进度信息
        """
        # 限制更新频率：每 5% 或每 3 秒
        should_update = (
            progress.overall_progress - self.last_progress >= 5 or
            (datetime.utcnow() - self.last_update).total_seconds() >= 3 or
            progress.overall_progress in [0, 100]  # 开始和结束总是更新
        )
        
        if not should_update and progress.overall_progress < 100:
            return
        
        self.last_progress = progress.overall_progress
        self.last_update = datetime.utcnow()
        
        # 构建消息
        message = WSMessage(
            type="import_progress_update",
            task_id=self.task_id,
            data={
                "stage": progress.stage.value,
                "overall_progress": progress.overall_progress,
                "stage_progress": progress.stage_progress,
                "message": progress.message,
                "chapters_found": progress.chapters_found,
                "chapters_processed": progress.chapters_processed,
                "eta_seconds": progress.eta_seconds,
            }
        )
        
        # 发送给任务订阅者
        await self.ws_manager.send_to_task_subscribers(self.task_id, message)
        
        logger.debug(
            f"Import progress notified: task={self.task_id}, "
            f"progress={progress.overall_progress}%"
        )
    
    async def on_stage_complete(self, stage: ImportStage, duration_seconds: float):
        """阶段完成通知
        
        Args:
            stage: 完成的阶段
            duration_seconds: 阶段耗时
        """
        message = WSMessage(
            type="import_stage_complete",
            task_id=self.task_id,
            data={
                "stage": stage.value,
                "duration_seconds": duration_seconds,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        
        await self.ws_manager.send_to_task_subscribers(self.task_id, message)
        logger.info(f"Import stage completed: task={self.task_id}, stage={stage.value}")
    
    async def on_completed(self, result: Dict[str, Any]):
        """任务完成通知
        
        Args:
            result: 导入结果
        """
        message = WSMessage(
            type="import_completed",
            task_id=self.task_id,
            data={
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        
        await self.ws_manager.send_to_task_subscribers(self.task_id, message)
        logger.info(f"Import completed notified: task={self.task_id}")
    
    async def on_failed(self, error: str, failed_stage: ImportStage):
        """任务失败通知
        
        Args:
            error: 错误信息
            failed_stage: 失败的阶段
        """
        message = WSMessage(
            type="import_failed",
            task_id=self.task_id,
            data={
                "error": error,
                "failed_stage": failed_stage.value,
                "can_retry": True,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        
        await self.ws_manager.send_to_task_subscribers(self.task_id, message)
        logger.error(f"Import failed notified: task={self.task_id}, error={error}")
    
    async def on_cancelled(self):
        """任务取消通知"""
        message = WSMessage(
            type="import_cancelled",
            task_id=self.task_id,
            data={
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        
        await self.ws_manager.send_to_task_subscribers(self.task_id, message)
        logger.info(f"Import cancelled notified: task={self.task_id}")


class ImportWebSocketHandler:
    """导入任务 WebSocket 处理器（用于路由层）"""
    
    def __init__(self, ws_manager: WebSocketManager):
        """
        Args:
            ws_manager: WebSocket 管理器
        """
        self.ws_manager = ws_manager
    
    async def handle_message(
        self,
        client_id: str,
        message: WSMessage
    ) -> Optional[WSMessage]:
        """处理 WebSocket 消息
        
        Args:
            client_id: 客户端ID
            message: 收到的消息
            
        Returns:
            响应消息，None 表示无需响应
        """
        msg_type = message.type
        
        if msg_type == "subscribe_import":
            # 订阅导入任务
            task_id = message.data.get("task_id")
            if task_id:
                await self.ws_manager.subscribe_task(client_id, task_id)
                return WSMessage(
                    type="subscribed",
                    task_id=task_id,
                    data={"message": f"Subscribed to import task {task_id}"}
                )
        
        elif msg_type == "unsubscribe_import":
            # 取消订阅
            task_id = message.data.get("task_id")
            if task_id:
                await self.ws_manager.unsubscribe_task(client_id, task_id)
                return WSMessage(
                    type="unsubscribed",
                    task_id=task_id,
                    data={"message": f"Unsubscribed from import task {task_id}"}
                )
        
        elif msg_type == "subscribe_all_imports":
            # 订阅所有导入任务
            await self.ws_manager.subscribe_all(client_id)
            return WSMessage(
                type="subscribed_all",
                data={"message": "Subscribed to all import tasks"}
            )
        
        elif msg_type == "ping":
            # 心跳响应
            return WSMessage(
                type="pong",
                data={"timestamp": datetime.utcnow().isoformat()}
            )
        
        return None


# ============================================================================
# 便捷函数
# ============================================================================

def create_import_notifier(
    ws_manager: WebSocketManager,
    task_id: int
) -> ImportWebSocketNotifier:
    """创建导入任务 WebSocket 通知器
    
    Args:
        ws_manager: WebSocket 管理器
        task_id: 任务ID
        
    Returns:
        通知器实例
    """
    return ImportWebSocketNotifier(ws_manager, task_id)
