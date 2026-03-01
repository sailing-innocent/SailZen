# -*- coding: utf-8 -*-
# @file unified_agent.py
# @brief Unified Agent ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
统一 Agent 任务模块 ORM 模型

从 sail_server/data/unified_agent.py 迁移
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, Integer, String, ForeignKey, TIMESTAMP, func, Text, Numeric
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from sail_server.infrastructure.orm import ORMBase
from sail_server.data.types import JSONB, ARRAY


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
