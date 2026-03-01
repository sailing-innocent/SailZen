# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent Task Models
# @author sailing-innocent
# @date 2026-02-27
# @version 3.0
# ---------------------------------
#
# 统一的 Agent 任务数据模型
# 整合 Agent 系统和小说分析系统的任务模型

"""
统一 Agent 任务模块数据层

此模块导出：
- 业务常量/枚举 (TaskType, TaskSubType, TaskStatus, ReviewStatus, StepType)
- ORM 模型 (从 infrastructure.orm.unified_agent 导入)
- Pydantic DTOs (从 application.dto.unified_agent 导入)
"""

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
# Enums / Constants (业务常量)
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
]
