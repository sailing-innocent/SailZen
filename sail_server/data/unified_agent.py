# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Task Models
# @author sailing-innocent
# @date 2026-02-27
# @version 2.0
# ---------------------------------
#
# 统一的 Agent 任务数据模型
# 整合 Agent 系统和小说分析系统的任务模型

"""
统一 Agent 任务模块数据层

ORM 模型已从 infrastructure.orm.unified_agent 迁移
DTO 模型已从 application.dto.unified_agent 迁移

此文件保留向后兼容的导出、常量枚举和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.unified_agent import (
    UnifiedAgentTask,
    UnifiedAgentStep,
    UnifiedAgentEvent,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.unified_agent import (
    UnifiedAgentTaskBase,
    UnifiedAgentTaskCreateRequest,
    UnifiedAgentTaskUpdateRequest,
    UnifiedAgentTaskResponse,
    UnifiedAgentTaskListResponse,
    UnifiedAgentStepBase,
    UnifiedAgentStepCreateRequest,
    UnifiedAgentStepResponse,
    UnifiedAgentStepListResponse,
    UnifiedAgentEventBase,
    UnifiedAgentEventCreateRequest,
    UnifiedAgentEventResponse,
    UnifiedAgentEventListResponse,
    UnifiedTaskProgressResponse,
    UnifiedTaskResultResponse,
)


# ============================================================================
# Enums / Constants (保留在此，因为是业务常量)
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


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class UnifiedTaskData:
    """统一任务数据传输对象 (legacy dataclass)"""
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


@dataclass
class UnifiedStepData:
    """统一步骤数据传输对象 (legacy dataclass)"""
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


@dataclass
class UnifiedTaskCreateRequest:
    """创建统一任务请求 (legacy dataclass)"""
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
    """任务进度信息 (legacy dataclass)"""
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
    """任务执行结果 (legacy dataclass)"""
    task_id: int
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_seconds: float = 0.0
    total_tokens: int = 0
    total_cost: float = 0.0


__all__ = [
    # Constants
    "TaskType",
    "TaskSubType",
    "TaskStatus",
    "ReviewStatus",
    "StepType",
    # ORM Models
    "UnifiedAgentTask",
    "UnifiedAgentStep",
    "UnifiedAgentEvent",
    # Pydantic DTOs
    "UnifiedAgentTaskBase",
    "UnifiedAgentTaskCreateRequest",
    "UnifiedAgentTaskUpdateRequest",
    "UnifiedAgentTaskResponse",
    "UnifiedAgentTaskListResponse",
    "UnifiedAgentStepBase",
    "UnifiedAgentStepCreateRequest",
    "UnifiedAgentStepResponse",
    "UnifiedAgentStepListResponse",
    "UnifiedAgentEventBase",
    "UnifiedAgentEventCreateRequest",
    "UnifiedAgentEventResponse",
    "UnifiedAgentEventListResponse",
    "UnifiedTaskProgressResponse",
    "UnifiedTaskResultResponse",
    # Legacy Dataclass DTOs
    "UnifiedTaskData",
    "UnifiedStepData",
    "UnifiedTaskCreateRequest",
    "UnifiedTaskProgress",
    "UnifiedTaskResult",
]
