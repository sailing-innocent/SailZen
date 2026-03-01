# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
统一 Agent 任务模块 Pydantic DTOs

原位置: sail_server/data/unified_agent.py
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Task Status & Type Constants
# ============================================================================

class TaskStatus:
    """任务状态常量"""
    PENDING = "pending"           # 待处理
    SCHEDULED = "scheduled"       # 已调度
    RUNNING = "running"           # 运行中
    PAUSED = "paused"             # 已暂停
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


class TaskType:
    """任务类型常量"""
    NOVEL_ANALYSIS = "novel_analysis"  # 小说分析
    CODE = "code"                      # 代码任务
    WRITING = "writing"                # 写作任务
    GENERAL = "general"                # 通用任务
    DATA = "data"                      # 数据处理任务


class TaskSubType:
    """任务子类型常量"""
    OUTLINE_EXTRACTION = "outline_extraction"    # 大纲提取
    CHARACTER_DETECTION = "character_detection"  # 人物检测
    SETTING_DETECTION = "setting_detection"      # 设定检测
    RELATION_ANALYSIS = "relation_analysis"      # 关系分析
    SUMMARY_GENERATION = "summary_generation"    # 摘要生成
    SETTING_EXTRACTION = "setting_extraction"
    PLOT_ANALYSIS = "plot_analysis"

class StepType:
    """步骤类型常量"""
    THOUGHT = "thought"                # 思考
    ACTION = "action"                  # 行动
    OBSERVATION = "observation"        # 观察
    LLM_CALL = "llm_call"              # LLM调用
    DATA_PROCESSING = "data_processing"  # 数据处理
    ERROR = "error"                    # 错误
    COMPLETION = "completion"          # 完成


# ============================================================================
# UnifiedAgentTask DTOs
# ============================================================================

class UnifiedAgentTaskBase(BaseModel):
    """统一 Agent 任务基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    task_type: str = Field(default="general", description="任务类型")
    sub_type: Optional[str] = Field(default=None, description="子类型")
    edition_id: Optional[int] = Field(default=None, description="关联的版本ID")
    target_node_ids: Optional[List[int]] = Field(default=None, description="目标章节节点ID列表")
    target_scope: Optional[str] = Field(default=None, description="目标范围")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型名称")
    prompt_template_id: Optional[str] = Field(default=None, description="Prompt模板ID")
    priority: int = Field(default=5, description="优先级")
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置参数")


class UnifiedAgentTaskCreateRequest(BaseModel):
    """创建统一 Agent 任务请求"""
    model_config = ConfigDict(from_attributes=True)
    
    task_type: str = Field(default="general", description="任务类型")
    sub_type: Optional[str] = Field(default=None, description="子类型")
    edition_id: Optional[int] = Field(default=None, description="关联的版本ID")
    target_node_ids: Optional[List[int]] = Field(default=None, description="目标章节节点ID列表")
    target_scope: Optional[str] = Field(default=None, description="目标范围")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型名称")
    prompt_template_id: Optional[str] = Field(default=None, description="Prompt模板ID")
    priority: int = Field(default=5, description="优先级")
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置参数")


class UnifiedAgentTaskUpdateRequest(BaseModel):
    """更新统一 Agent 任务请求"""
    model_config = ConfigDict(from_attributes=True)
    
    status: Optional[str] = Field(default=None, description="任务状态")
    progress: Optional[int] = Field(default=None, description="执行进度")
    current_phase: Optional[str] = Field(default=None, description="当前执行阶段")
    priority: Optional[int] = Field(default=None, description="优先级")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    error_code: Optional[str] = Field(default=None, description="错误码")
    review_status: Optional[str] = Field(default=None, description="审核状态")


class UnifiedAgentTaskResponse(BaseModel):
    """统一 Agent 任务响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(description="任务ID")
    task_type: str = Field(description="任务类型")
    sub_type: Optional[str] = Field(default=None, description="子类型")
    edition_id: Optional[int] = Field(default=None, description="关联的版本ID")
    target_node_ids: Optional[List[int]] = Field(default=None, description="目标章节节点ID列表")
    target_scope: Optional[str] = Field(default=None, description="目标范围")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型名称")
    prompt_template_id: Optional[str] = Field(default=None, description="Prompt模板ID")
    status: str = Field(description="任务状态")
    progress: int = Field(description="执行进度")
    current_phase: Optional[str] = Field(default=None, description="当前执行阶段")
    priority: int = Field(description="优先级")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    error_code: Optional[str] = Field(default=None, description="错误码")
    estimated_tokens: Optional[int] = Field(default=None, description="预估Token数量")
    actual_tokens: int = Field(description="实际Token消耗")
    estimated_cost: Optional[Decimal] = Field(default=None, description="预估成本")
    actual_cost: Decimal = Field(description="实际成本")
    result_data: Optional[Dict[str, Any]] = Field(default=None, description="任务结果数据")
    review_status: str = Field(description="审核状态")
    config: Dict[str, Any] = Field(default_factory=dict, description="任务配置参数")
    created_at: datetime = Field(description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    cancelled_at: Optional[datetime] = Field(default=None, description="取消时间")
    updated_at: datetime = Field(description="更新时间")


class UnifiedAgentTaskListResponse(BaseModel):
    """统一 Agent 任务列表响应"""
    tasks: List[UnifiedAgentTaskResponse]
    total: int


# ============================================================================
# UnifiedAgentStep DTOs
# ============================================================================

class UnifiedAgentStepBase(BaseModel):
    """统一 Agent 步骤基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    task_id: int = Field(description="所属任务ID")
    step_number: int = Field(description="步骤序号")
    step_type: str = Field(description="步骤类型")
    title: Optional[str] = Field(default=None, description="步骤标题")
    content: Optional[str] = Field(default=None, description="详细内容")
    content_summary: Optional[str] = Field(default=None, description="内容摘要")


class UnifiedAgentStepCreateRequest(UnifiedAgentStepBase):
    """创建统一 Agent 步骤请求"""
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")
    prompt_tokens: int = Field(default=0, description="Prompt Token数")
    completion_tokens: int = Field(default=0, description="补全Token数")
    cost: Decimal = Field(default=Decimal("0"), description="本步成本")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="附加信息")
    duration_ms: Optional[int] = Field(default=None, description="执行耗时(毫秒)")


class UnifiedAgentStepResponse(UnifiedAgentStepBase):
    """统一 Agent 步骤响应"""
    id: int = Field(description="步骤ID")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")
    prompt_tokens: int = Field(description="Prompt Token数")
    completion_tokens: int = Field(description="补全Token数")
    cost: Decimal = Field(description="本步成本")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="附加信息")
    created_at: datetime = Field(description="创建时间")
    duration_ms: Optional[int] = Field(default=None, description="执行耗时(毫秒)")


class UnifiedAgentStepListResponse(BaseModel):
    """统一 Agent 步骤列表响应"""
    steps: List[UnifiedAgentStepResponse]
    total: int


# ============================================================================
# UnifiedAgentEvent DTOs
# ============================================================================

class UnifiedAgentEventBase(BaseModel):
    """统一 Agent 事件基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    task_id: int = Field(description="所属任务ID")
    event_type: str = Field(description="事件类型")
    event_data: Optional[Dict[str, Any]] = Field(default=None, description="事件数据")


class UnifiedAgentEventCreateRequest(UnifiedAgentEventBase):
    """创建统一 Agent 事件请求"""
    pass


class UnifiedAgentEventResponse(UnifiedAgentEventBase):
    """统一 Agent 事件响应"""
    id: int = Field(description="事件ID")
    created_at: datetime = Field(description="创建时间")


class UnifiedAgentEventListResponse(BaseModel):
    """统一 Agent 事件列表响应"""
    events: List[UnifiedAgentEventResponse]
    total: int


# ============================================================================
# Unified Task Data & Progress (for internal use)
# ============================================================================

@dataclass
class UnifiedTaskData:
    """统一任务数据对象 (用于调度器内部传递)"""
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
    
    # 以下字段在创建后填充
    id: Optional[int] = None
    status: str = "pending"
    progress: int = 0
    current_phase: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    estimated_tokens: Optional[int] = None
    actual_tokens: int = 0
    estimated_cost: Optional[float] = None
    actual_cost: float = 0.0
    result_data: Optional[Dict[str, Any]] = None
    review_status: str = "pending"
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_orm(cls, orm: Any, step_count: int = 0) -> "UnifiedTaskData":
        """从 ORM 模型创建"""
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
            priority=orm.priority,
            config=orm.config or {},
            status=orm.status,
            progress=orm.progress,
            current_phase=orm.current_phase,
            error_message=orm.error_message,
            error_code=orm.error_code,
            estimated_tokens=orm.estimated_tokens,
            actual_tokens=orm.actual_tokens,
            estimated_cost=float(orm.estimated_cost) if orm.estimated_cost else None,
            actual_cost=float(orm.actual_cost) if orm.actual_cost else 0.0,
            result_data=orm.result_data,
            review_status=orm.review_status,
            created_at=orm.created_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            updated_at=orm.updated_at,
        )


@dataclass
class UnifiedTaskProgress:
    """统一任务进度对象"""
    task_id: int
    status: str
    progress: int
    current_phase: Optional[str] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    estimated_remaining_seconds: Optional[int] = None
    error_message: Optional[str] = None
    actual_tokens: int = 0
    actual_cost: float = 0.0


# ============================================================================
# Task Progress & Result DTOs
# ============================================================================

class UnifiedTaskProgressResponse(BaseModel):
    """任务进度响应"""
    model_config = ConfigDict(from_attributes=True)
    
    task_id: int = Field(description="任务ID")
    status: str = Field(description="任务状态")
    progress: int = Field(description="执行进度")
    current_phase: Optional[str] = Field(default=None, description="当前执行阶段")
    current_step: Optional[int] = Field(default=None, description="当前步骤")
    total_steps: Optional[int] = Field(default=None, description="总步骤数")
    estimated_remaining_seconds: Optional[int] = Field(default=None, description="预估剩余时间(秒)")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    actual_tokens: int = Field(description="实际Token消耗")
    actual_cost: Decimal = Field(description="实际成本")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    updated_at: datetime = Field(description="更新时间")


class UnifiedTaskResultResponse(BaseModel):
    """任务执行结果响应"""
    model_config = ConfigDict(from_attributes=True)
    
    task_id: int = Field(description="任务ID")
    success: bool = Field(description="是否成功")
    result_data: Optional[Dict[str, Any]] = Field(default=None, description="结果数据")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    execution_time_seconds: float = Field(description="执行时间(秒)")
    total_tokens: int = Field(description="总Token数")
    total_cost: Decimal = Field(description="总成本")
