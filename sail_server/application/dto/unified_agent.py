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

from pydantic import BaseModel, Field, ConfigDict


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
