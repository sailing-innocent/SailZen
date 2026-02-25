# -*- coding: utf-8 -*-
# @file agent.py
# @brief Agent Router
# @author sailing-innocent
# @date 2025-02-25
# @version 1.0
# ---------------------------------

from typing import Generator, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from typing import Any
from litestar import Router, Controller, get, post, delete
from litestar.di import Provide
from litestar.dto import DataclassDTO
from litestar.dto.config import DTOConfig
from litestar.exceptions import NotFoundException
from litestar.handlers import WebsocketListener

from sail_server.data.agent import (
    UserPrompt, UserPromptData, UserPromptCreateRequest,
    AgentTask, AgentTaskData,
    AgentStep, AgentStepData,
    AgentOutput, AgentOutputData,
    AgentSchedulerState, SchedulerStateData,
    AgentTaskDetailResponse,
)
from sail_server.db import get_db_dependency
from sail_server.model.agent import get_agent_scheduler


# ============================================================================
# DTOs
# ============================================================================

class UserPromptWriteDTO(DataclassDTO[UserPromptCreateRequest]):
    config = DTOConfig(include={'content', 'prompt_type', 'context', 'priority', 'session_id', 'parent_prompt_id'})


class UserPromptReadDTO(DataclassDTO[UserPromptData]):
    pass


class AgentTaskReadDTO(DataclassDTO[AgentTaskData]):
    pass


class SchedulerStateReadDTO(DataclassDTO[SchedulerStateData]):
    pass


# ============================================================================
# Controllers
# ============================================================================

class UserPromptController(Controller):
    """用户提示控制器"""
    path = "/prompt"
    dto = UserPromptWriteDTO
    return_dto = UserPromptReadDTO
    
    @post("")
    async def create_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        data: UserPromptCreateRequest,
    ) -> UserPromptData:
        """提交新的用户提示"""
        db = next(router_dependency)
        prompt_data = UserPromptData(
            content=data.content,
            prompt_type=data.prompt_type,
            context=data.context,
            priority=data.priority,
            session_id=data.session_id,
            parent_prompt_id=data.parent_prompt_id,
            status='pending',
        )
        prompt = prompt_data.create_orm()
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        return UserPromptData.read_from_orm(prompt)
    
    @get("")
    async def list_prompts(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[UserPromptData]:
        """获取提示列表"""
        db = next(router_dependency)
        query = db.query(UserPrompt)
        if status:
            query = query.filter(UserPrompt.status == status)
        prompts = query.order_by(UserPrompt.created_at.desc()).offset(skip).limit(limit).all()
        return [UserPromptData.read_from_orm(p) for p in prompts]
    
    @get("/{id:int}")
    async def get_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> UserPromptData:
        """获取单个提示详情"""
        db = next(router_dependency)
        prompt = db.query(UserPrompt).filter(UserPrompt.id == id).first()
        if not prompt:
            raise NotFoundException(f"Prompt {id} not found")
        return UserPromptData.read_from_orm(prompt)
    
    @post("/{id:int}/cancel")
    async def cancel_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> UserPromptData:
        """取消待处理的提示"""
        db = next(router_dependency)
        prompt = db.query(UserPrompt).filter(UserPrompt.id == id).first()
        if not prompt:
            raise NotFoundException(f"Prompt {id} not found")
        if prompt.status not in ('pending', 'scheduled'):
            raise ValueError(f"Cannot cancel prompt with status {prompt.status}")
        
        prompt.status = 'cancelled'
        prompt.completed_at = datetime.utcnow()
        db.commit()
        return UserPromptData.read_from_orm(prompt)
    
    @delete("/{id:int}", status_code=200)
    async def delete_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> UserPromptData:
        """删除提示"""
        db = next(router_dependency)
        prompt = db.query(UserPrompt).filter(UserPrompt.id == id).first()
        if not prompt:
            raise NotFoundException(f"Prompt {id} not found")
        
        prompt_data = UserPromptData.read_from_orm(prompt)
        db.delete(prompt)
        db.commit()
        return prompt_data


class AgentTaskController(Controller):
    """Agent 任务控制器"""
    path = "/task"
    return_dto = AgentTaskReadDTO
    
    @get("")
    async def list_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[AgentTaskData]:
        """获取任务列表"""
        db = next(router_dependency)
        query = db.query(AgentTask)
        if status:
            query = query.filter(AgentTask.status == status)
        tasks = query.order_by(AgentTask.created_at.desc()).offset(skip).limit(limit).all()
        
        result = []
        for task in tasks:
            step_count = db.query(func.count(AgentStep.id)).filter(
                AgentStep.task_id == task.id
            ).scalar() or 0
            result.append(AgentTaskData.read_from_orm(task, step_count=step_count))
        return result
    
    @get("/{id:int}")
    async def get_task(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> AgentTaskDetailResponse:
        """获取任务详情（包含步骤和输出）"""
        db = next(router_dependency)
        task = db.query(AgentTask).filter(AgentTask.id == id).first()
        if not task:
            raise NotFoundException(f"Task {id} not found")
        
        steps = db.query(AgentStep).filter(AgentStep.task_id == id).order_by(AgentStep.step_number).all()
        outputs = db.query(AgentOutput).filter(AgentOutput.task_id == id).all()
        
        return AgentTaskDetailResponse(
            task=AgentTaskData.read_from_orm(task),
            steps=[AgentStepData.read_from_orm(s) for s in steps],
            outputs=[AgentOutputData.read_from_orm(o) for o in outputs],
            prompt=UserPromptData.read_from_orm(task.prompt),
        )
    
    @get("/{id:int}/steps")
    async def get_task_steps(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentStepData]:
        """获取任务步骤列表"""
        db = next(router_dependency)
        steps = db.query(AgentStep).filter(
            AgentStep.task_id == id
        ).order_by(AgentStep.step_number).offset(skip).limit(limit).all()
        return [AgentStepData.read_from_orm(s) for s in steps]
    
    @post("/{id:int}/cancel")
    async def cancel_task(
        self,
        router_dependency: Generator[Session, None, None],
        id: int,
    ) -> AgentTaskData:
        """取消正在运行的任务"""
        db = next(router_dependency)
        task = db.query(AgentTask).filter(AgentTask.id == id).first()
        if not task:
            raise NotFoundException(f"Task {id} not found")
        
        # 调用调度器取消任务
        scheduler = get_agent_scheduler()
        await scheduler.cancel_task(id)
        
        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.commit()
        
        return AgentTaskData.read_from_orm(task)


class SchedulerController(Controller):
    """调度器状态控制器"""
    path = "/scheduler"
    return_dto = SchedulerStateReadDTO
    
    @get("/status")
    async def get_status(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """获取调度器状态"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if not state:
            state = AgentSchedulerState()
            db.add(state)
            db.commit()
        
        # 同步活跃 Agent 数量
        scheduler = get_agent_scheduler()
        state.active_agent_count = len(scheduler.get_active_tasks())
        db.commit()
        
        return SchedulerStateData.read_from_orm(state)
    
    @post("/start")
    async def start_scheduler(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """启动调度器"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if not state:
            state = AgentSchedulerState()
            db.add(state)
        
        # 启动调度器
        scheduler = get_agent_scheduler()
        await scheduler.start()
        
        state.is_running = True
        db.commit()
        return SchedulerStateData.read_from_orm(state)
    
    @post("/stop")
    async def stop_scheduler(
        self,
        router_dependency: Generator[Session, None, None],
    ) -> SchedulerStateData:
        """停止调度器"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if state:
            # 停止调度器
            scheduler = get_agent_scheduler()
            await scheduler.stop()
            
            state.is_running = False
            db.commit()
        return SchedulerStateData.read_from_orm(state)
    
    @post("/config")
    async def update_config(
        self,
        router_dependency: Generator[Session, None, None],
        max_concurrent_agents: int,
    ) -> SchedulerStateData:
        """更新调度器配置"""
        db = next(router_dependency)
        state = db.query(AgentSchedulerState).first()
        if not state:
            state = AgentSchedulerState()
            db.add(state)
        
        state.max_concurrent_agents = max_concurrent_agents
        db.commit()
        return SchedulerStateData.read_from_orm(state)


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

class AgentEventWebSocket(WebsocketListener):
    """Agent 事件 WebSocket - 实时推送状态更新"""
    path = "/ws/events"
    
    async def on_accept(self, websocket: Any, close_code: int = 0) -> None:
        """连接建立时订阅事件"""
        self.websocket = websocket
        # 获取全局调度器并订阅
        scheduler = get_agent_scheduler()
        scheduler.subscribe(self._on_event)
    
    async def on_disconnect(self, websocket: Any, close_code: int) -> None:
        """连接断开时取消订阅"""
        scheduler = get_agent_scheduler()
        scheduler.unsubscribe(self._on_event)
    
    async def on_receive(self, websocket: Any, data: Any) -> Any:
        """接收客户端消息（本实现中不需要处理客户端消息）"""
        # 可以在这里处理客户端发送的命令，如心跳、订阅特定任务等
        return None
    
    async def _on_event(self, event: Any) -> None:
        """事件回调 - 发送给客户端"""
        try:
            await self.websocket.send_json({
                'event_type': event.event_type,
                'task_id': event.task_id,
                'timestamp': event.timestamp.isoformat(),
                'data': event.data,
            })
        except Exception as e:
            # WebSocket 可能已关闭
            pass


# ============================================================================
# Router
# ============================================================================

router = Router(
    path="/agent",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        UserPromptController,
        AgentTaskController,
        SchedulerController,
        AgentEventWebSocket,
    ],
)
