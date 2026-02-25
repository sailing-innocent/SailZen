# -*- coding: utf-8 -*-
# @file agent.py
# @brief Agent System Data Models
# @author sailing-innocent
# @date 2025-02-25
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sail_server.data.orm import ORMBase
from sqlalchemy.orm import relationship
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================================
# ORM Models - User Prompt 队列
# ============================================================================

class UserPrompt(ORMBase):
    """
    用户提示表 - 存储用户提交的待处理请求
    状态流转: pending -> scheduled -> processing -> completed/failed/cancelled
    """
    __tablename__ = "user_prompts"

    id = Column(Integer, primary_key=True)
    
    # 用户请求内容
    content = Column(Text, nullable=False)  # 用户的原始请求内容
    prompt_type = Column(String, default='general')  # general | code | analysis | writing | data
    context = Column(JSONB, default={})  # 附加上下文信息
    
    # 优先级和调度
    priority = Column(Integer, default=5)  # 1-10, 1为最高优先级
    status = Column(String, default='pending')  # pending | scheduled | processing | completed | failed | cancelled
    
    # 关联信息
    created_by = Column(String, nullable=True)  # 用户标识
    session_id = Column(String, nullable=True)  # 会话ID，用于关联一组相关请求
    parent_prompt_id = Column(Integer, ForeignKey("user_prompts.id", ondelete="SET NULL"), nullable=True)
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    scheduled_at = Column(TIMESTAMP, nullable=True)  # 计划执行时间
    started_at = Column(TIMESTAMP, nullable=True)   # 实际开始时间
    completed_at = Column(TIMESTAMP, nullable=True)  # 完成时间
    
    # 关联
    agent_tasks = relationship("AgentTask", back_populates="prompt", cascade="all, delete-orphan")


# ============================================================================
# ORM Models - Agent 任务
# ============================================================================

class AgentTask(ORMBase):
    """
    Agent 任务表 - 记录每个 Agent 执行实例
    状态流转: created -> preparing -> running -> paused -> completed/failed/cancelled
    """
    __tablename__ = "agent_tasks"

    id = Column(Integer, primary_key=True)
    prompt_id = Column(Integer, ForeignKey("user_prompts.id", ondelete="CASCADE"), nullable=False)
    
    # Agent 配置
    agent_type = Column(String, default='general')  # general | coder | analyst | writer
    agent_config = Column(JSONB, default={})  # Agent 特定配置
    
    # 执行状态
    status = Column(String, default='created')  # created | preparing | running | paused | completed | failed | cancelled
    progress = Column(Integer, default=0)  # 0-100 百分比
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    started_at = Column(TIMESTAMP, nullable=True)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    completed_at = Column(TIMESTAMP, nullable=True)
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    
    # 资源限制
    max_iterations = Column(Integer, default=100)  # 最大迭代次数
    timeout_seconds = Column(Integer, default=3600)  # 超时时间
    
    # 关联
    prompt = relationship("UserPrompt", back_populates="agent_tasks")
    steps = relationship("AgentStep", back_populates="task", cascade="all, delete-orphan", order_by="AgentStep.step_number")
    outputs = relationship("AgentOutput", back_populates="task", cascade="all, delete-orphan")


class AgentStep(ORMBase):
    """
    Agent 执行步骤表 - 记录 Agent 的每一步操作
    """
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    
    # 步骤信息
    step_number = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False)  # thought | action | observation | error | completion
    
    # 内容
    title = Column(String, nullable=True)  # 步骤标题
    content = Column(Text, nullable=True)  # 详细内容
    content_summary = Column(String, nullable=True)  # 内容摘要（用于列表展示）
    
    # 元数据
    meta_data = Column(JSONB, default={})  # 附加信息，如工具调用参数等
    
    # 时间戳
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    duration_ms = Column(Integer, nullable=True)  # 步骤执行耗时
    
    # 关联
    task = relationship("AgentTask", back_populates="steps")


class AgentOutput(ORMBase):
    """
    Agent 输出结果表 - 存储 Agent 的最终产出
    """
    __tablename__ = "agent_outputs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False)
    
    # 输出内容
    output_type = Column(String, nullable=False)  # text | code | file | json | error
    content = Column(Text, nullable=True)  # 文本内容
    file_path = Column(String, nullable=True)  # 文件路径（如果是文件输出）
    
    # 元数据
    meta_data = Column(JSONB, default={})  # 如代码语言、文件类型等
    
    # 审核状态
    review_status = Column(String, default='pending')  # pending | approved | rejected
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # 关联
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    task = relationship("AgentTask", back_populates="outputs")


# ============================================================================
# ORM Models - Agent 调度器状态
# ============================================================================

class AgentSchedulerState(ORMBase):
    """
    Agent 调度器状态表 - 单例表，记录调度器运行状态
    """
    __tablename__ = "agent_scheduler_state"

    id = Column(Integer, primary_key=True, default=1)  # 单例
    
    # 调度器状态
    is_running = Column(Boolean, default=False)  # 调度器是否运行中
    last_poll_at = Column(TIMESTAMP, nullable=True)  # 上次轮询时间
    active_agent_count = Column(Integer, default=0)  # 当前活跃 Agent 数量
    max_concurrent_agents = Column(Integer, default=3)  # 最大并发数
    
    # 统计信息
    total_processed = Column(Integer, default=0)  # 总共处理数量
    total_failed = Column(Integer, default=0)     # 失败数量
    
    # 时间戳
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# ============================================================================
# Data Transfer Objects - User Prompt
# ============================================================================

@dataclass
class UserPromptData:
    """用户提示数据传输对象"""
    content: str
    id: int = field(default=-1)
    prompt_type: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    created_by: Optional[str] = None
    session_id: Optional[str] = None
    parent_prompt_id: Optional[int] = None
    created_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: UserPrompt):
        return cls(
            id=orm.id,
            content=orm.content,
            prompt_type=orm.prompt_type,
            context=orm.context or {},
            priority=orm.priority,
            status=orm.status,
            created_by=orm.created_by,
            session_id=orm.session_id,
            parent_prompt_id=orm.parent_prompt_id,
            created_at=orm.created_at,
            scheduled_at=orm.scheduled_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
        )

    def create_orm(self) -> UserPrompt:
        return UserPrompt(
            content=self.content,
            prompt_type=self.prompt_type,
            context=self.context,
            priority=self.priority,
            status=self.status,
            created_by=self.created_by,
            session_id=self.session_id,
            parent_prompt_id=self.parent_prompt_id,
        )


@dataclass
class UserPromptCreateRequest:
    """创建用户提示请求"""
    content: str
    prompt_type: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    session_id: Optional[str] = None
    parent_prompt_id: Optional[int] = None


# ============================================================================
# Data Transfer Objects - Agent Task
# ============================================================================

@dataclass
class AgentTaskData:
    """Agent 任务数据传输对象"""
    prompt_id: int
    id: int = field(default=-1)
    agent_type: str = "general"
    agent_config: Dict[str, Any] = field(default_factory=dict)
    status: str = "created"
    progress: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    current_step: Optional['AgentStepData'] = None  # 当前步骤
    step_count: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: AgentTask, current_step=None, step_count: int = 0):
        return cls(
            id=orm.id,
            prompt_id=orm.prompt_id,
            agent_type=orm.agent_type,
            agent_config=orm.agent_config or {},
            status=orm.status,
            progress=orm.progress,
            created_at=orm.created_at,
            started_at=orm.started_at,
            updated_at=orm.updated_at,
            completed_at=orm.completed_at,
            error_message=orm.error_message,
            error_code=orm.error_code,
            current_step=current_step,
            step_count=step_count,
        )


@dataclass
class AgentStepData:
    """Agent 步骤数据传输对象"""
    task_id: int
    step_number: int
    step_type: str
    id: int = field(default=-1)
    title: Optional[str] = None
    content: Optional[str] = None
    content_summary: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentStep):
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            step_number=orm.step_number,
            step_type=orm.step_type,
            title=orm.title,
            content=orm.content,
            content_summary=orm.content_summary,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            duration_ms=orm.duration_ms,
        )


@dataclass
class AgentOutputData:
    """Agent 输出数据传输对象"""
    task_id: int
    output_type: str
    id: int = field(default=-1)
    content: Optional[str] = None
    file_path: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentOutput):
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            output_type=orm.output_type,
            content=orm.content,
            file_path=orm.file_path,
            meta_data=orm.meta_data or {},
            review_status=orm.review_status,
            reviewed_by=orm.reviewed_by,
            reviewed_at=orm.reviewed_at,
            review_notes=orm.review_notes,
            created_at=orm.created_at,
        )


# ============================================================================
# Data Transfer Objects - Scheduler State
# ============================================================================

@dataclass
class SchedulerStateData:
    """调度器状态数据传输对象"""
    is_running: bool = False
    last_poll_at: Optional[datetime] = None
    active_agent_count: int = 0
    max_concurrent_agents: int = 3
    total_processed: int = 0
    total_failed: int = 0
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm: AgentSchedulerState):
        return cls(
            is_running=orm.is_running,
            last_poll_at=orm.last_poll_at,
            active_agent_count=orm.active_agent_count,
            max_concurrent_agents=orm.max_concurrent_agents,
            total_processed=orm.total_processed,
            total_failed=orm.total_failed,
            updated_at=orm.updated_at,
        )


# ============================================================================
# Response Models
# ============================================================================

@dataclass
class AgentTaskDetailResponse:
    """Agent 任务详情响应"""
    task: AgentTaskData
    steps: List[AgentStepData]
    outputs: List[AgentOutputData]
    prompt: UserPromptData


@dataclass
class AgentStreamEvent:
    """Agent 实时流事件 - 用于 WebSocket/SSE"""
    event_type: str  # task_started | step_update | progress_update | task_completed | task_failed | output_ready
    task_id: int
    timestamp: datetime
    data: Dict[str, Any]  # 事件特定数据
