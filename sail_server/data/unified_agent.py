# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Task Models
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------
#
# 统一的 Agent 任务数据模型
# 整合 Agent 系统和小说分析系统的任务模型

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy import (
    Column, Integer, String, ForeignKey, TIMESTAMP, func, Text, Numeric
)
from sail_server.data.types import JSONB, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sail_server.data.orm import ORMBase


# ============================================================================
# ORM Models
# ============================================================================

class UnifiedAgentTask(ORMBase):
    """
    统一 Agent 任务表
    
    整合 AgentTask 和 AnalysisTask 的功能：
    - 支持通用 Agent 任务 (code/writing/general)
    - 支持小说分析任务 (novel_analysis)
    - 统一的成本追踪和状态管理
    """
    __tablename__ = "unified_agent_tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # =========================================================================
    # 任务分类
    # =========================================================================
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """任务类型: 'novel_analysis' | 'code' | 'writing' | 'general' | 'data'"""
    
    sub_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    """子类型: 如 'outline_extraction', 'character_detection' 等"""
    
    # =========================================================================
    # 关联信息 (小说分析用)
    # =========================================================================
    edition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("editions.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    """关联的版本 ID (小说分析任务)"""
    
    target_node_ids: Mapped[Optional[List[int]]] = mapped_column(
        ARRAY(Integer), 
        nullable=True
    )
    """目标章节节点 ID 列表"""
    
    target_scope: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    """目标范围: 'full' | 'range' | 'chapter'"""
    
    # =========================================================================
    # LLM 配置
    # =========================================================================
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    """LLM 提供商: 'google' | 'openai' | 'moonshot' | 'anthropic'"""
    
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    """LLM 模型名称"""
    
    prompt_template_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    """Prompt 模板 ID"""
    
    # =========================================================================
    # 执行状态
    # =========================================================================
    status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="pending",
        index=True
    )
    """任务状态: pending | scheduled | running | paused | completed | failed | cancelled"""
    
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """执行进度 0-100"""
    
    current_phase: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    """当前执行阶段描述"""
    
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    """优先级 1-10, 1为最高"""
    
    # =========================================================================
    # 错误信息
    # =========================================================================
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """错误信息"""
    
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    """错误码"""
    
    # =========================================================================
    # 成本追踪
    # =========================================================================
    estimated_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    """预估 Token 数量"""
    
    actual_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """实际 Token 消耗"""
    
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    """预估成本 (USD)"""
    
    actual_cost: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.0)
    """实际成本 (USD)"""
    
    # =========================================================================
    # 结果数据
    # =========================================================================
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    """任务结果数据 (JSON 格式)"""
    
    review_status: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default="pending"
    )
    """审核状态: pending | approved | rejected | modified"""
    
    # =========================================================================
    # 配置参数
    # =========================================================================
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, 
        nullable=True, 
        default=dict
    )
    """任务配置参数 (原 agent_config / parameters)"""
    
    # =========================================================================
    # 时间戳
    # =========================================================================
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, 
        server_default=func.current_timestamp()
    )
    
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    """开始执行时间"""
    
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    """完成时间"""
    
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    """取消时间"""
    
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
    
    # =========================================================================
    # 关联
    # =========================================================================
    steps: Mapped[List["UnifiedAgentStep"]] = relationship(
        "UnifiedAgentStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="UnifiedAgentStep.step_number"
    )


class UnifiedAgentStep(ORMBase):
    """
    统一 Agent 任务步骤表
    
    整合 AgentStep 功能，增强 LLM 调用追踪
    """
    __tablename__ = "unified_agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    task_id: Mapped[int] = mapped_column(
        ForeignKey("unified_agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # 步骤信息
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    """步骤序号"""
    
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    """步骤类型: thought | action | observation | llm_call | data_processing | error | completion"""
    
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    """步骤标题"""
    
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """详细内容"""
    
    content_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    """内容摘要"""
    
    # LLM 调用追踪 (新增)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    """LLM 提供商"""
    
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    """LLM 模型"""
    
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """Prompt Token 数"""
    
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    """补全 Token 数"""
    
    cost: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.0)
    """本步成本 (USD)"""
    
    # 元数据
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, 
        nullable=True, 
        default=dict
    )
    """附加信息"""
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, 
        server_default=func.current_timestamp()
    )
    
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    """执行耗时 (毫秒)"""
    
    # 关联
    task: Mapped["UnifiedAgentTask"] = relationship(
        "UnifiedAgentTask", 
        back_populates="steps"
    )


class UnifiedAgentEvent(ORMBase):
    """
    统一 Agent 事件日志表
    
    用于记录任务执行过程中的关键事件，便于审计和调试
    """
    __tablename__ = "unified_agent_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    task_id: Mapped[int] = mapped_column(
        ForeignKey("unified_agent_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    """事件类型: task_started | step_completed | llm_called | progress_update | error | task_completed"""
    
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    """事件数据"""
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, 
        server_default=func.current_timestamp(),
        index=True
    )


# ============================================================================
# Data Transfer Objects
# ============================================================================

@dataclass
class UnifiedTaskData:
    """统一任务数据传输对象"""
    
    id: int = -1
    task_type: str = "general"
    sub_type: Optional[str] = None
    
    # 关联信息
    edition_id: Optional[int] = None
    target_node_ids: Optional[List[int]] = None
    target_scope: Optional[str] = None
    
    # LLM 配置
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_template_id: Optional[str] = None
    
    # 执行状态
    status: str = "pending"
    progress: int = 0
    current_phase: Optional[str] = None
    priority: int = 5
    
    # 错误信息
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # 成本追踪
    estimated_tokens: Optional[int] = None
    actual_tokens: int = 0
    estimated_cost: Optional[float] = None
    actual_cost: float = 0.0
    
    # 结果数据
    result_data: Optional[Dict[str, Any]] = None
    review_status: str = "pending"
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # 统计
    step_count: int = 0
    
    @classmethod
    def from_orm(cls, orm: UnifiedAgentTask, step_count: int = 0) -> "UnifiedTaskData":
        """从 ORM 对象创建 DTO"""
        return cls(
            id=orm.id,
            task_type=orm.task_type,
            sub_type=orm.sub_type,
            edition_id=orm.edition_id,
            target_node_ids=orm.target_node_ids,
            target_scope=orm.target_scope,
            llm_provider=orm.llm_provider,
            llm_model=orm.llm_model,
            prompt_template_id=orm.prompt_template_id,
            status=orm.status,
            progress=orm.progress,
            current_phase=orm.current_phase,
            priority=orm.priority,
            error_message=orm.error_message,
            error_code=orm.error_code,
            estimated_tokens=orm.estimated_tokens,
            actual_tokens=orm.actual_tokens,
            estimated_cost=float(orm.estimated_cost) if orm.estimated_cost else None,
            actual_cost=float(orm.actual_cost),
            result_data=orm.result_data,
            review_status=orm.review_status,
            config=orm.config or {},
            created_at=orm.created_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            cancelled_at=orm.cancelled_at,
            updated_at=orm.updated_at,
            step_count=step_count,
        )
    
    def to_orm(self, for_update: bool = False) -> UnifiedAgentTask:
        """转换为 ORM 对象
        
        Args:
            for_update: 是否为更新操作。如果是更新，则包含 id；如果是创建，则不包含 id
        """
        return UnifiedAgentTask(
            id=self.id if for_update and self.id and self.id > 0 else None,
            task_type=self.task_type,
            sub_type=self.sub_type,
            edition_id=self.edition_id,
            target_node_ids=self.target_node_ids,
            target_scope=self.target_scope,
            llm_provider=self.llm_provider,
            llm_model=self.llm_model,
            prompt_template_id=self.prompt_template_id,
            status=self.status,
            progress=self.progress,
            current_phase=self.current_phase,
            priority=self.priority,
            error_message=self.error_message,
            error_code=self.error_code,
            estimated_tokens=self.estimated_tokens,
            actual_tokens=self.actual_tokens,
            estimated_cost=self.estimated_cost,
            actual_cost=self.actual_cost,
            result_data=self.result_data,
            review_status=self.review_status,
            config=self.config,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            cancelled_at=self.cancelled_at,
        )


@dataclass
class UnifiedStepData:
    """统一步骤数据传输对象"""
    
    id: int = -1
    task_id: int = -1
    step_number: int = 0
    step_type: str = "thought"
    title: Optional[str] = None
    content: Optional[str] = None
    content_summary: Optional[str] = None
    
    # LLM 追踪
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    created_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    @classmethod
    def from_orm(cls, orm: UnifiedAgentStep) -> "UnifiedStepData":
        """从 ORM 对象创建 DTO"""
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            step_number=orm.step_number,
            step_type=orm.step_type,
            title=orm.title,
            content=orm.content,
            content_summary=orm.content_summary,
            llm_provider=orm.llm_provider,
            llm_model=orm.llm_model,
            prompt_tokens=orm.prompt_tokens,
            completion_tokens=orm.completion_tokens,
            cost=float(orm.cost),
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            duration_ms=orm.duration_ms,
        )


@dataclass
class UnifiedTaskCreateRequest:
    """创建统一任务请求"""
    
    task_type: str = "general"
    sub_type: Optional[str] = None
    
    # 小说分析用
    edition_id: Optional[int] = None
    target_node_ids: Optional[List[int]] = None
    target_scope: Optional[str] = None
    
    # LLM 配置
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_template_id: Optional[str] = None
    
    # 优先级
    priority: int = 5
    
    # 配置
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedTaskProgress:
    """任务进度信息"""
    
    task_id: int
    status: str
    progress: int
    current_phase: Optional[str] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    estimated_remaining_seconds: Optional[int] = None
    error_message: Optional[str] = None
    
    # 成本信息
    actual_tokens: int = 0
    actual_cost: float = 0.0
    
    # 时间戳
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class UnifiedTaskResult:
    """任务执行结果"""
    
    task_id: int
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0


# ============================================================================
# Enums
# ============================================================================

class TaskType:
    """任务类型常量"""
    NOVEL_ANALYSIS = "novel_analysis"
    CODE = "code"
    WRITING = "writing"
    GENERAL = "general"
    DATA = "data"


class TaskSubType:
    """任务子类型常量 (小说分析)"""
    OUTLINE_EXTRACTION = "outline_extraction"
    CHARACTER_DETECTION = "character_detection"
    SETTING_EXTRACTION = "setting_extraction"
    RELATION_ANALYSIS = "relation_analysis"
    PLOT_ANALYSIS = "plot_analysis"


class TaskStatus:
    """任务状态常量"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus:
    """审核状态常量"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class StepType:
    """步骤类型常量"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    LLM_CALL = "llm_call"
    DATA_PROCESSING = "data_processing"
    ERROR = "error"
    COMPLETION = "completion"
