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
)
from sail_server.utils.websocket_manager import (
    WebSocketManager,
    get_websocket_manager,
)
from sail_server.agent import get_agent_registry, AgentContext
from sail_server.agent.base import ProgressUpdate
from sail_server.utils.llm.gateway import create_default_gateway

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
        执行任务（带 WebSocket 通知和 LLM 调用）
        
        重写父类方法，调用具体的 Agent 执行
        """
        logger.info(f"[UnifiedSchedulerWithWebSocket] Executing task: task_id={task_id}")
        
        from sail_server.application.dto.unified_agent import (
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
            
            logger.info(f"[UnifiedSchedulerWithWebSocket] Task {task_id} found: type={task.task_type}")
            
            # 创建开始步骤
            step_number = step_dao.get_next_step_number(task_id)
            logger.info(f"[UnifiedSchedulerWithWebSocket] Creating step {step_number} for task {task_id}")
            step = step_dao.create(
                task_id=task_id,
                step_number=step_number,
                step_type=StepType.THOUGHT,
                title="Task Started",
                content=f"Starting {task.task_type} task",
            )
            logger.info(f"[UnifiedSchedulerWithWebSocket] Step created: step_id={step.id}")
            
            # 记录事件
            event = event_dao.create(
                task_id=task_id,
                event_type="task_started",
                event_data={"step_id": step.id}
            )
            logger.info(f"[UnifiedSchedulerWithWebSocket] Event created: event_id={event.id}")
            
            # 更新进度
            dao.update_progress(task_id, 10, "executing")
            logger.info(f"[UnifiedSchedulerWithWebSocket] Task {task_id} progress updated to 10%")
            
            # 获取 Agent
            registry = get_agent_registry()
            agent = registry.get_agent_for_task(task.task_type)
            
            if not agent:
                logger.error(f"[UnifiedSchedulerWithWebSocket] No agent found for task type: {task.task_type}")
                raise ValueError(f"No agent found for task type: {task.task_type}")
            
            logger.info(f"[UnifiedSchedulerWithWebSocket] Using agent: {agent.agent_type}")
            
            # 创建 Agent 上下文（使用默认网关，自动注册所有可用的 provider）
            llm_gateway = create_default_gateway()
            context = AgentContext(
                db_session=db,
                llm_gateway=llm_gateway,
                config={},
            )
            
            # 定义进度回调
            def progress_callback(update: ProgressUpdate):
                logger.info(f"[UnifiedSchedulerWithWebSocket] Task {task_id} progress: {update.progress}% - {update.phase} - {update.message}")
                dao.update_progress(task_id, update.progress, update.phase)
                self._emit_event(TaskProgressEvent(
                    task_id=task_id,
                    event_type="progress",
                    data={"progress": update.progress, "phase": update.phase, "message": update.message}
                ))
            
            # 调用 Agent 执行
            logger.info(f"[UnifiedSchedulerWithWebSocket] Calling agent.execute for task {task_id}")
            result = await agent.execute(task, context, progress_callback)
            
            logger.info(f"[UnifiedSchedulerWithWebSocket] Agent execution result: success={result.success}")
            
            if result.success:
                # 创建完成步骤
                step_number += 1
                step_content = result.result_data.get("response", "Task completed") if result.result_data else "Task completed"
                step_dao.create(
                    task_id=task_id,
                    step_number=step_number,
                    step_type=StepType.COMPLETION,
                    title="Task Completed",
                    content=step_content[:500],  # 限制长度
                )
                
                # 标记完成
                dao.mark_as_completed(task_id, result_data=result.result_data)
                logger.info(f"[UnifiedSchedulerWithWebSocket] Task {task_id} marked as completed")
                
                # 记录事件
                event_dao.create(
                    task_id=task_id,
                    event_type="task_completed",
                    event_data={
                        "result": "success",
                        "total_tokens": result.total_tokens,
                        "total_cost": result.total_cost,
                    }
                )
                
                self._stats["total_completed"] += 1
                
                # 发送完成事件
                self._emit_event(TaskProgressEvent(
                    task_id=task_id,
                    event_type="completed",
                    data={
                        "progress": 100,
                        "result": "success",
                        "response": step_content[:200],  # 简要响应
                    }
                ))
            else:
                # 执行失败
                logger.error(f"[UnifiedSchedulerWithWebSocket] Task {task_id} failed: {result.error_message}")
                
                # 创建错误步骤
                step_number += 1
                step_dao.create(
                    task_id=task_id,
                    step_number=step_number,
                    step_type=StepType.ERROR,
                    title="Task Failed",
                    content=result.error_message or "Unknown error",
                )
                
                # 标记失败
                dao.mark_as_failed(task_id, result.error_message or "Unknown error", result.error_code)
                
                # 记录事件
                event_dao.create(
                    task_id=task_id,
                    event_type="task_failed",
                    event_data={
                        "error": result.error_message,
                        "error_code": result.error_code,
                    }
                )
                
                self._stats["total_failed"] += 1
                
                # 发送失败事件
                self._emit_event(TaskProgressEvent(
                    task_id=task_id,
                    event_type="failed",
                    data={
                        "error": result.error_message,
                        "error_code": result.error_code,
                    }
                ))
                
                raise ValueError(f"Task execution failed: {result.error_message}")
            
            logger.info(f"[UnifiedSchedulerWithWebSocket] Task {task_id} execution completed")


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
