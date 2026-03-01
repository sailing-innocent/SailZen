# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Router
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 统一 Agent 路由
# 整合 Agent 和 Analysis 功能，提供统一的 API

from typing import Generator, List, Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from litestar import Router, Controller, get, post, delete, websocket
from litestar.di import Provide
from litestar.exceptions import NotFoundException, ValidationException
from litestar.response import Stream
from litestar.handlers.websocket_handlers import WebsocketListener
from litestar.connection import WebSocket
from litestar.types import WebSocketScope, WebSocketReceiveMessage, WebSocketSendMessage, Scope, Receive, Send

from sail_server.db import get_db_dependency, get_db_session
from sail_server.infrastructure.orm.unified_agent import UnifiedAgentTask
from sail_server.application.dto.unified_agent import (
    UnifiedTaskData,
    UnifiedAgentTaskCreateRequest as UnifiedTaskCreateRequest,
    UnifiedTaskProgress,
    TaskStatus,
    TaskType,
)
from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)
from sail_server.model.unified_scheduler import (
    UnifiedAgentScheduler,
    SchedulerConfig,
)
from sail_server.model.unified_scheduler_ws import (
    UnifiedSchedulerWithWebSocket,
    get_unified_scheduler_with_ws,
)
from sail_server.utils.websocket_manager import (
    get_websocket_manager,
    WSMessage,
)
from sail_server.agent import get_agent_registry
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

@dataclass
class CreateTaskRequest:
    """创建任务请求"""
    task_type: str
    sub_type: Optional[str] = None
    edition_id: Optional[int] = None
    target_node_ids: Optional[List[int]] = None
    target_scope: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_template_id: Optional[str] = None
    priority: int = 5
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResponse:
    """任务响应"""
    id: int
    task_type: str
    sub_type: Optional[str]
    status: str
    progress: int
    current_phase: Optional[str]
    priority: int
    estimated_tokens: Optional[int]
    actual_tokens: int
    estimated_cost: Optional[float]
    actual_cost: float
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_data(cls, data: UnifiedTaskData) -> "TaskResponse":
        """从数据对象创建响应"""
        return cls(
            id=data.id,
            task_type=data.task_type,
            sub_type=data.sub_type,
            status=data.status,
            progress=data.progress,
            current_phase=data.current_phase,
            priority=data.priority,
            estimated_tokens=data.estimated_tokens,
            actual_tokens=data.actual_tokens,
            estimated_cost=data.estimated_cost,
            actual_cost=data.actual_cost,
            created_at=data.created_at.isoformat() if data.created_at else None,
            started_at=data.started_at.isoformat() if data.started_at else None,
            completed_at=data.completed_at.isoformat() if data.completed_at else None,
            error_message=data.error_message,
            result_data=data.result_data,
        )


@dataclass
class TaskProgressResponse:
    """任务进度响应"""
    task_id: int
    status: str
    progress: int
    current_phase: Optional[str]
    current_step: Optional[int]
    total_steps: Optional[int]
    estimated_remaining_seconds: Optional[int]
    error_message: Optional[str]
    actual_tokens: int
    actual_cost: float
    
    @classmethod
    def from_progress(cls, progress: UnifiedTaskProgress) -> "TaskProgressResponse":
        """从进度对象创建响应"""
        return cls(
            task_id=progress.task_id,
            status=progress.status,
            progress=progress.progress,
            current_phase=progress.current_phase,
            current_step=progress.current_step,
            total_steps=progress.total_steps,
            estimated_remaining_seconds=progress.estimated_remaining_seconds,
            error_message=progress.error_message,
            actual_tokens=progress.actual_tokens,
            actual_cost=progress.actual_cost,
        )


@dataclass
class TaskListFilter:
    """任务列表过滤条件"""
    status: Optional[str] = None
    task_type: Optional[str] = None
    sub_type: Optional[str] = None
    edition_id: Optional[int] = None
    skip: int = 0
    limit: int = 20


# ============================================================================
# Controllers
# ============================================================================

class UnifiedTaskController(Controller):
    """统一任务控制器"""
    path = "/tasks"
    
    def _get_scheduler(self) -> UnifiedAgentScheduler:
        """获取调度器实例"""
        return get_unified_scheduler_with_ws()
    
    @post("")
    async def create_task(
        self,
        router_dependency: Generator[Session, None, None],
        data: CreateTaskRequest,
    ) -> TaskResponse:
        """创建新任务"""
        db = next(router_dependency)
        
        # 详细记录接收到的所有数据
        logger.info("=" * 60)
        logger.info(f"[UnifiedTaskController] Creating task: type={data.task_type}, sub_type={data.sub_type}, edition_id={data.edition_id}")
        logger.info(f"[UnifiedTaskController] target_node_ids={data.target_node_ids}, target_scope={data.target_scope}")
        logger.info(f"[UnifiedTaskController] LLM config from request: llm_provider={data.llm_provider}, llm_model={data.llm_model}")
        
        # 记录完整的 config 数据
        config_data = data.config or {}
        logger.info(f"[UnifiedTaskController] Full config data: {config_data}")
        range_selection = config_data.get("range_selection", {})
        logger.info(f"[UnifiedTaskController] Range selection from request: {range_selection}")
        
        # 验证任务类型
        registry = get_agent_registry()
        agent = registry.get_agent_for_task(data.task_type)
        if not agent:
            raise ValidationException(f"Unsupported task type: {data.task_type}")
        
        # 创建任务数据
        task_data = UnifiedTaskData(
            task_type=data.task_type,
            sub_type=data.sub_type,
            edition_id=data.edition_id,
            target_node_ids=data.target_node_ids,
            target_scope=data.target_scope,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            prompt_template_id=data.prompt_template_id,
            priority=data.priority,
            config=data.config,
        )
        logger.info(f"[UnifiedTaskController] UnifiedTaskData created: llm_provider={task_data.llm_provider}, llm_model={task_data.llm_model}")
        
        # 调度任务（内部会创建任务记录并加入队列）
        scheduler = self._get_scheduler()
        
        # 启动调度器（如果未运行）
        if not scheduler.is_running():
            await scheduler.start()
        
        # 调度任务
        result_data = await scheduler.schedule_task(task_data)
        
        # 发送 task_created 事件通知客户端
        ws_manager = get_websocket_manager()
        await ws_manager.notify_task_created(
            result_data.id,
            {
                "task_type": result_data.task_type,
                "status": result_data.status,
                "priority": result_data.priority,
            }
        )
        
        return TaskResponse.from_data(result_data)
    
    @get("")
    async def list_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        sub_type: Optional[str] = None,
        edition_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[TaskResponse]:
        """获取任务列表"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        tasks = dao.list_tasks(
            status=status,
            task_type=task_type,
            sub_type=sub_type,
            edition_id=edition_id,
            skip=skip,
            limit=limit,
        )
        
        result = []
        for task in tasks:
            step_dao = UnifiedStepDAO(db)
            step_count = step_dao.get_next_step_number(task.id) - 1
            data = UnifiedTaskData.from_orm(task, step_count)
            result.append(TaskResponse.from_data(data))
        
        return result
    
    @get("/{task_id:int}")
    async def get_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> TaskResponse:
        """获取任务详情"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        result = dao.get_with_step_count(task_id)
        if not result:
            raise NotFoundException(f"Task {task_id} not found")
        
        task, step_count = result
        data = UnifiedTaskData.from_orm(task, step_count)
        return TaskResponse.from_data(data)
    
    @get("/{task_id:int}/progress")
    async def get_task_progress(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> TaskProgressResponse:
        """获取任务进度"""
        db = next(router_dependency)
        scheduler = self._get_scheduler()
        
        progress = scheduler.get_task_progress(task_id)
        if not progress:
            # 从数据库获取基本信息
            dao = UnifiedTaskDAO(db)
            task = dao.get_by_id(task_id)
            if not task:
                raise NotFoundException(f"Task {task_id} not found")
            
            progress = UnifiedTaskProgress(
                task_id=task_id,
                status=task.status,
                progress=task.progress,
                current_phase=task.current_phase,
                actual_tokens=task.actual_tokens,
                actual_cost=float(task.actual_cost),
            )
        
        return TaskProgressResponse.from_progress(progress)
    
    @post("/{task_id:int}/cancel")
    async def cancel_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> Dict[str, Any]:
        """取消任务"""
        scheduler = self._get_scheduler()
        
        success = await scheduler.cancel_task(task_id)
        if not success:
            raise ValidationException(f"Failed to cancel task {task_id}")
        
        return {"success": True, "message": f"Task {task_id} cancelled"}
    
    @delete("/{task_id:int}", status_code=200)
    async def delete_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> Dict[str, Any]:
        """删除任务"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 先尝试取消（如果正在运行）
        scheduler = self._get_scheduler()
        await scheduler.cancel_task(task_id)
        
        # 删除任务
        success = dao.delete(task_id)
        if not success:
            raise NotFoundException(f"Task {task_id} not found")
        
        return {"success": True, "message": f"Task {task_id} deleted"}


class UnifiedAgentInfoController(Controller):
    """Agent 信息控制器"""
    path = "/agents"
    
    @get("")
    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有可用的 Agent"""
        registry = get_agent_registry()
        agents = registry.list_agents()
        return [agent.to_dict() for agent in agents]
    
    @get("/{agent_type:str}")
    async def get_agent_info(self, agent_type: str) -> Dict[str, Any]:
        """获取 Agent 详细信息"""
        registry = get_agent_registry()
        agent = registry.get_agent(agent_type)
        
        if not agent:
            raise NotFoundException(f"Agent {agent_type} not found")
        
        return agent.agent_info.to_dict()
    
    @post("/{agent_type:str}/estimate")
    async def estimate_task_cost(
        self,
        router_dependency: Generator[Session, None, None],
        agent_type: str,
        data: CreateTaskRequest,
    ) -> Dict[str, Any]:
        """预估任务成本"""
        registry = get_agent_registry()
        agent = registry.get_agent(agent_type)
        
        if not agent:
            raise NotFoundException(f"Agent {agent_type} not found")
        
        # 创建临时任务对象用于预估
        task = UnifiedAgentTask(
            task_type=data.task_type,
            sub_type=data.sub_type,
            edition_id=data.edition_id,
            target_node_ids=data.target_node_ids,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            config=data.config,
        )
        
        estimate = agent.estimate_cost(task)
        return estimate.to_dict()
    
    @get("/config/llm")
    async def get_llm_config(self) -> Dict[str, Any]:
        """获取 LLM 配置信息（供前端使用）"""
        from sail_server.utils.llm.available_providers import to_frontend_config
        return to_frontend_config()


class UnifiedSchedulerController(Controller):
    """调度器控制器"""
    path = "/scheduler"
    
    def _get_scheduler(self) -> UnifiedAgentScheduler:
        """获取调度器实例"""
        return get_unified_scheduler_with_ws()
    
    @get("/status")
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        scheduler = self._get_scheduler()
        
        return {
            "is_running": scheduler.is_running(),
            "stats": scheduler.get_stats(),
        }
    
    @post("/start")
    async def start_scheduler(self) -> Dict[str, Any]:
        """启动调度器"""
        scheduler = self._get_scheduler()
        
        if scheduler.is_running():
            return {"success": True, "message": "Scheduler is already running"}
        
        await scheduler.start()
        return {"success": True, "message": "Scheduler started"}
    
    @post("/stop")
    async def stop_scheduler(self) -> Dict[str, Any]:
        """停止调度器"""
        scheduler = self._get_scheduler()
        
        if not scheduler.is_running():
            return {"success": True, "message": "Scheduler is not running"}
        
        await scheduler.stop()
        return {"success": True, "message": "Scheduler stopped"}


# ============================================================================
# WebSocket Handler
# ============================================================================

class TaskProgressWebSocket(WebsocketListener):
    """任务进度 WebSocket"""
    path = "/ws/tasks"
    
    async def on_accept(self, socket: WebSocket) -> None:
        """连接建立时"""
        self.socket = socket
        self.ws_manager = get_websocket_manager()
        self.client_id = f"ws_{id(socket)}"
        
        async def _send_message(msg: str) -> None:
            """发送消息，捕获连接断开异常"""
            try:
                await socket.send_text(msg)
            except Exception:
                # 连接已断开，忽略发送错误
                pass
        
        await self.ws_manager.connect(
            self.client_id,
            lambda msg: asyncio.create_task(_send_message(msg))
        )
        
        logger.info(f"WebSocket client {self.client_id} connected")
    
    async def on_disconnect(self, socket: WebSocket) -> None:
        """连接断开时"""
        await self.ws_manager.disconnect(self.client_id)
        logger.info(f"WebSocket client {self.client_id} disconnected")
    
    async def on_receive(self, data: str) -> None:
        """收到消息时"""
        await self.ws_manager.handle_message(self.client_id, data)


# ============================================================================
# Router
# ============================================================================

unified_agent_router = Router(
    path="/agent-unified",
    route_handlers=[
        UnifiedTaskController,
        UnifiedAgentInfoController,
        UnifiedSchedulerController,
        TaskProgressWebSocket,
    ],
    tags=["Unified Agent"],
    dependencies={"router_dependency": Provide(get_db_dependency)},
)
