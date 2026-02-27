# -*- coding: utf-8 -*-
# @file agent_compat.py
# @brief Agent API Compatibility Layer
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# Agent API 兼容层
# 保持旧 Agent API 接口不变，内部转发到新实现

from typing import Generator, List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from litestar import Router, Controller, get, post, delete
from litestar.di import Provide
from litestar.exceptions import NotFoundException, ValidationException

from sail_server.db import get_db_dependency
from sail_server.data.agent import (
    UserPrompt,
    UserPromptData,
    AgentTask,
    AgentTaskData,
    AgentStep,
    AgentStepData,
)
from sail_server.data.unified_agent import (
    UnifiedAgentTask,
    UnifiedTaskData,
    TaskType,
    TaskStatus,
    StepType,
)
from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)
from sail_server.model.unified_scheduler_ws import get_unified_scheduler_with_ws
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 类型映射
# ============================================================================

# 旧 prompt_type -> 新 task_type 映射
PROMPT_TYPE_MAPPING = {
    "code": TaskType.CODE,
    "writing": TaskType.WRITING,
    "analysis": TaskType.NOVEL_ANALYSIS,
    "general": TaskType.GENERAL,
}

# 旧状态 -> 新状态映射
STATUS_MAPPING = {
    "pending": TaskStatus.PENDING,
    "scheduled": TaskStatus.SCHEDULED,
    "running": TaskStatus.RUNNING,
    "completed": TaskStatus.COMPLETED,
    "failed": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
}


# ============================================================================
# Request/Response Models (兼容旧格式)
# ============================================================================

@dataclass
class CreatePromptRequest:
    """创建用户提示请求（旧格式）"""
    content: str
    prompt_type: str = "general"  # code, writing, analysis, general
    context: Optional[str] = None
    priority: int = 5
    session_id: Optional[str] = None
    parent_prompt_id: Optional[int] = None


@dataclass
class UserPromptResponse:
    """用户提示响应（旧格式）"""
    id: int
    content: str
    prompt_type: str
    context: Optional[str]
    priority: int
    status: str
    session_id: Optional[str]
    parent_prompt_id: Optional[int]
    created_at: str
    scheduled_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class AgentTaskResponse:
    """Agent 任务响应（旧格式）"""
    id: int
    prompt_id: int
    agent_type: str
    status: str
    agent_config: Dict[str, Any]
    result_data: Optional[Dict[str, Any]]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class AgentStepResponse:
    """Agent 步骤响应（旧格式）"""
    id: int
    task_id: int
    step_number: int
    step_type: str
    content: str
    content_summary: Optional[str]
    created_at: str


# ============================================================================
# 转换函数
# ============================================================================

def convert_prompt_type_to_task_type(prompt_type: str) -> str:
    """将旧 prompt_type 转换为新 task_type"""
    return PROMPT_TYPE_MAPPING.get(prompt_type, TaskType.GENERAL)

def convert_task_status_to_prompt_status(status: str) -> str:
    """将任务状态转换为提示状态"""
    # 新 -> 旧
    if status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
        return "pending"
    elif status == TaskStatus.RUNNING:
        return "running"
    elif status == TaskStatus.COMPLETED:
        return "completed"
    elif status == TaskStatus.FAILED:
        return "failed"
    elif status == TaskStatus.CANCELLED:
        return "cancelled"
    return status

def convert_unified_task_to_prompt_response(
    task: UnifiedAgentTask
) -> UserPromptResponse:
    """将统一任务转换为用户提示响应"""
    # 反向查找旧 prompt_type
    prompt_type = task.task_type
    for old, new in PROMPT_TYPE_MAPPING.items():
        if new == prompt_type:
            prompt_type = old
            break
    
    return UserPromptResponse(
        id=task.id,
        content=task.config.get("prompt", ""),
        prompt_type=prompt_type,
        context=task.config.get("context"),
        priority=task.priority,
        status=convert_task_status_to_prompt_status(task.status),
        session_id=task.config.get("session_id"),
        parent_prompt_id=task.config.get("parent_prompt_id"),
        created_at=task.created_at.isoformat() if task.created_at else "",
        scheduled_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )

def convert_unified_task_to_agent_task_response(
    task: UnifiedAgentTask
) -> AgentTaskResponse:
    """将统一任务转换为 Agent 任务响应"""
    return AgentTaskResponse(
        id=task.id,
        prompt_id=task.config.get("prompt_id", 0),
        agent_type=task.task_type,
        status=convert_task_status_to_prompt_status(task.status),
        agent_config=task.config,
        result_data=task.result_data,
        created_at=task.created_at.isoformat() if task.created_at else "",
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


# ============================================================================
# 兼容层 Controllers
# ============================================================================

class UserPromptCompatController(Controller):
    """用户提示兼容控制器"""
    path = "/prompt"
    
    @post("")
    async def create_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        data: CreatePromptRequest,
    ) -> UserPromptResponse:
        """提交用户提示（兼容旧 API）"""
        db = next(router_dependency)
        
        # 转换为新格式
        task_type = convert_prompt_type_to_task_type(data.prompt_type)
        
        # 创建统一任务
        task_data = UnifiedTaskData(
            task_type=task_type,
            priority=data.priority,
            config={
                "prompt": data.content,
                "context": data.context,
                "session_id": data.session_id,
                "parent_prompt_id": data.parent_prompt_id,
            },
        )
        
        # 保存到数据库
        dao = UnifiedTaskDAO(db)
        orm = dao.create(task_data)
        task_data.id = orm.id
        
        # 调度任务
        scheduler = get_unified_scheduler_with_ws()
        if not scheduler.is_running():
            await scheduler.start()
        
        await scheduler.schedule_task(task_data)
        
        return convert_unified_task_to_prompt_response(orm)
    
    @get("")
    async def list_prompts(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        prompt_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[UserPromptResponse]:
        """获取提示列表（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 转换类型
        task_type = None
        if prompt_type:
            task_type = convert_prompt_type_to_task_type(prompt_type)
        
        # 转换状态
        task_status = None
        if status:
            task_status = STATUS_MAPPING.get(status)
        
        # 查询
        tasks = dao.list_tasks(
            status=task_status,
            task_type=task_type,
            skip=skip,
            limit=limit,
        )
        
        return [convert_unified_task_to_prompt_response(t) for t in tasks]
    
    @get("/{prompt_id:int}")
    async def get_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        prompt_id: int,
    ) -> UserPromptResponse:
        """获取提示详情（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        task = dao.get_by_id(prompt_id)
        if not task:
            raise NotFoundException(f"Prompt {prompt_id} not found")
        
        return convert_unified_task_to_prompt_response(task)
    
    @post("/{prompt_id:int}/cancel")
    async def cancel_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        prompt_id: int,
    ) -> UserPromptResponse:
        """取消提示（兼容旧 API）"""
        db = next(router_dependency)
        scheduler = get_unified_scheduler_with_ws()
        
        # 取消任务
        await scheduler.cancel_task(prompt_id)
        
        # 返回更新后的状态
        dao = UnifiedTaskDAO(db)
        task = dao.get_by_id(prompt_id)
        if not task:
            raise NotFoundException(f"Prompt {prompt_id} not found")
        
        return convert_unified_task_to_prompt_response(task)
    
    @delete("/{prompt_id:int}", status_code=200)
    async def delete_prompt(
        self,
        router_dependency: Generator[Session, None, None],
        prompt_id: int,
    ) -> Dict[str, Any]:
        """删除提示（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 先取消
        scheduler = get_unified_scheduler_with_ws()
        await scheduler.cancel_task(prompt_id)
        
        # 删除
        success = dao.delete(prompt_id)
        if not success:
            raise NotFoundException(f"Prompt {prompt_id} not found")
        
        return {"success": True, "message": f"Prompt {prompt_id} deleted"}


class AgentTaskCompatController(Controller):
    """Agent 任务兼容控制器"""
    path = "/task"
    
    @get("")
    async def list_tasks(
        self,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        agent_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[AgentTaskResponse]:
        """获取 Agent 任务列表（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        # 转换状态
        task_status = None
        if status:
            task_status = STATUS_MAPPING.get(status)
        
        # 查询
        tasks = dao.list_tasks(
            status=task_status,
            task_type=agent_type,
            skip=skip,
            limit=limit,
        )
        
        return [convert_unified_task_to_agent_task_response(t) for t in tasks]
    
    @get("/{task_id:int}")
    async def get_task(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> AgentTaskResponse:
        """获取 Agent 任务详情（兼容旧 API）"""
        db = next(router_dependency)
        dao = UnifiedTaskDAO(db)
        
        task = dao.get_by_id(task_id)
        if not task:
            raise NotFoundException(f"Task {task_id} not found")
        
        return convert_unified_task_to_agent_task_response(task)
    
    @get("/{task_id:int}/steps")
    async def get_task_steps(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AgentStepResponse]:
        """获取 Agent 步骤列表（兼容旧 API）"""
        db = next(router_dependency)
        step_dao = UnifiedStepDAO(db)
        
        steps = step_dao.get_by_task_id(task_id, skip=skip, limit=limit)
        
        return [
            AgentStepResponse(
                id=step.id,
                task_id=step.task_id,
                step_number=step.step_number,
                step_type=step.step_type,
                content=step.content or "",
                content_summary=step.content_summary,
                created_at=step.created_at.isoformat() if step.created_at else "",
            )
            for step in steps
        ]


class AgentStreamCompatController(Controller):
    """Agent 流式接口兼容控制器"""
    path = "/stream"
    
    @get("/{task_id:int}")
    async def stream_task_events(
        self,
        router_dependency: Generator[Session, None, None],
        task_id: int,
    ) -> Dict[str, Any]:
        """获取任务事件流（兼容旧 API）"""
        db = next(router_dependency)
        event_dao = UnifiedEventDAO(db)
        
        events = event_dao.get_by_task_id(task_id, limit=100)
        
        return {
            "success": True,
            "task_id": task_id,
            "events": [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "event_data": e.event_data,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
        }


# ============================================================================
# Router
# ============================================================================

agent_compat_router = Router(
    path="/agent-compat",
    route_handlers=[
        UserPromptCompatController,
        AgentTaskCompatController,
        AgentStreamCompatController,
    ],
    tags=["Agent (Compatibility)"],
    dependencies={"router_dependency": Provide(get_db_dependency)},
)
