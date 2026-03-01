# -*- coding: utf-8 -*-
# @file task.py
# @brief Task ORM Placeholders
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
分析任务相关占位符

注意: 这些是 dataclass 占位符，不是真正的 ORM 模型。
在 Phase 2 重构后，这些将被替换为真正的 SQLAlchemy ORM 模型
或迁移到 unified_agent 模块。

从 sail_server/data/analysis.py 迁移至此
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class AnalysisTask:
    """分析任务占位符
    
    注意: 此类当前为 dataclass 占位符。在 Phase 2 重构后，
    将被替换为真正的 SQLAlchemy ORM 模型或迁移到 unified_agent 模块。
    
    新代码请使用 AnalysisTaskData（包含 ORM 转换方法）
    """
    id: Optional[int] = None
    edition_id: int = 0
    task_type: str = ""
    status: str = "pending"
    target_scope: str = "full"
    target_node_ids: Optional[List[int]] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_prompt_template: Optional[str] = None
    priority: int = 5
    result_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AnalysisResult:
    """分析结果占位符
    
    注意: 此类当前为 dataclass 占位符。在 Phase 2 重构后，
    将被替换为真正的 SQLAlchemy ORM 模型或迁移到 unified_agent 模块。
    
    新代码请使用 AnalysisResultData（包含 ORM 转换方法）
    """
    id: Optional[int] = None
    task_id: int = 0
    result_type: str = ""
    result_data: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    review_status: str = "pending"
    reviewer: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
