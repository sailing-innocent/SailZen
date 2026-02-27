# -*- coding: utf-8 -*-
# @file unified_scheduler_ws.py
# @brief Unified Agent Scheduler with WebSocket Support
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 带 WebSocket 支持的统一调度器
# 继承 UnifiedAgentScheduler，添加 WebSocket 通知功能

import logging
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session

from sail_server.model.unified_scheduler import (
    UnifiedAgentScheduler,
    SchedulerConfig,
    TaskProgressEvent,
    ProgressCallback,
)
from sail_server.utils.websocket_manager import (
    WebSocketManager,
    get_websocket_manager,
)

logger = logging.getLogger(__name__)


class UnifiedSchedulerWithWebSocket(UnifiedAgentScheduler):
    """
    带 WebSocket 通知的统一调度器
    
    在 UnifiedAgentScheduler 基础上，自动将任务事件发送到 WebSocket
    """
    
    def __init__(
        self,
        db_session_factory: Callable[[], Session],
        config: Optional[SchedulerConfig] = None,
        ws_manager: Optional[WebSocketManager] = None,
    ):
        super().__init__(db_session_factory, config)
        
        # WebSocket 管理器
        self._ws_manager = ws_manager or get_websocket_manager()
        
        # 注册为调度器的进度回调
        self.subscribe(self._on_progress_event)
    
    def _on_progress_event(self, event: TaskProgressEvent):
        """处理进度事件并发送到 WebSocket"""
        try:
            import asyncio
            
            # 使用 asyncio.create_task 异步发送，避免阻塞
            if event.event_type == "started":
                asyncio.create_task(self._ws_manager.notify_task_started(
                    event.task_id,
                    event.data
                ))
            
            elif event.event_type == "progress":
                asyncio.create_task(self._ws_manager.notify_task_progress(
                    event.task_id,
                    event.data.get("progress", 0),
                    event.data.get("phase"),
                    event.data
                ))
            
            elif event.event_type == "step":
                asyncio.create_task(self._ws_manager.notify_task_step(
                    event.task_id,
                    event.data.get("step_number", 0),
                    event.data.get("step_type", "unknown"),
                    event.data.get("title"),
                    event.data
                ))
            
            elif event.event_type == "completed":
                asyncio.create_task(self._ws_manager.notify_task_completed(
                    event.task_id,
                    event.data
                ))
            
            elif event.event_type == "failed":
                asyncio.create_task(self._ws_manager.notify_task_failed(
                    event.task_id,
                    event.data.get("error", "Unknown error"),
                    event.data
                ))
            
            elif event.event_type == "cancelled":
                asyncio.create_task(self._ws_manager.notify_task_cancelled(
                    event.task_id,
                    event.data.get("reason", "user_request")
                ))
        
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
    
    async def _execute_task(self, task_id: int):
        """
        执行任务（带 WebSocket 通知）
        
        重写父类方法，添加更详细的步骤通知
        """
        from sail_server.data.unified_agent import (
            TaskStatus,
            StepType,
        )
        from sail_server.model.unified_agent import (
            UnifiedTaskDAO,
            UnifiedStepDAO,
            UnifiedEventDAO,
        )
        
        with self.db_factory() as db:
            dao = UnifiedTaskDAO(db)
            step_dao = UnifiedStepDAO(db)
            event_dao = UnifiedEventDAO(db)
            
            task = dao.get_by_id(task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            
            # 创建开始步骤
            step_number = step_dao.get_next_step_number(task_id)
            step = step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.THOUGHT,
                title="Task Started",
                content=f"Starting {task.task_type} task",
            )
            
            # 发送步骤事件
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="step",
                data={
                    "step_number": step_number,
                    "step_type": StepType.THOUGHT,
                    "title": "Task Started",
                }
            ))
            
            # 记录事件
            event_dao.create(
                task_id=task_id,
                event_type="task_started",
                event_data={"step_id": step.id}
            )
            
            # 更新进度
            dao.update_progress(task_id, 10, "executing")
            
            # 发送进度事件
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="progress",
                data={"progress": 10, "phase": "executing"}
            ))
            
            # TODO: 这里应该调用具体的 Agent 执行
            # 目前只是模拟执行，实际应由子类或 Agent 实现
            import asyncio
            await asyncio.sleep(1)
            
            # 模拟中间步骤
            step_number += 1
            step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.ACTION,
                title="Processing",
                content="Processing task data",
            )
            
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="step",
                data={
                    "step_number": step_number,
                    "step_type": StepType.ACTION,
                    "title": "Processing",
                }
            ))
            
            dao.update_progress(task_id, 50, "processing")
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="progress",
                data={"progress": 50, "phase": "processing"}
            ))
            
            await asyncio.sleep(1)
            
            # 完成步骤
            step_number += 1
            step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.COMPLETION,
                title="Task Completed",
                content="Task execution completed successfully",
            )
            
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="step",
                data={
                    "step_number": step_number,
                    "step_type": StepType.COMPLETION,
                    "title": "Task Completed",
                }
            ))
            
            # 标记完成
            dao.mark_as_completed(task_id, result_data={
                "message": "Task completed",
                "task_type": task.task_type,
            })
            
            # 记录事件
            event_dao.create(
                task_id=task_id,
                event_type="task_completed",
                event_data={"result": "success"}
            )
            
            self._stats["total_completed"] += 1
            
            # 发送完成事件
            self._emit_event(TaskProgressEvent(
                task_id=task_id,
                event_type="completed",
                data={
                    "progress": 100,
                    "result": "success",
                }
            ))


# ============================================================================
# 便捷函数
# ============================================================================

_scheduler_ws_instance: Optional[UnifiedSchedulerWithWebSocket] = None


def get_unified_scheduler_with_ws(
    db_session_factory: Optional[Callable[[], Session]] = None,
    config: Optional[SchedulerConfig] = None,
    ws_manager: Optional[WebSocketManager] = None,
) -> UnifiedSchedulerWithWebSocket:
    """获取带 WebSocket 的全局调度器实例"""
    global _scheduler_ws_instance
    if _scheduler_ws_instance is None:
        if db_session_factory is None:
            from sail_server.db import get_db_session
            db_session_factory = get_db_session
        
        if ws_manager is None:
            ws_manager = get_websocket_manager()
        
        _scheduler_ws_instance = UnifiedSchedulerWithWebSocket(
            db_session_factory,
            config,
            ws_manager
        )
    
    return _scheduler_ws_instance


def set_unified_scheduler_with_ws(scheduler: UnifiedSchedulerWithWebSocket):
    """设置带 WebSocket 的全局调度器实例"""
    global _scheduler_ws_instance
    _scheduler_ws_instance = scheduler
