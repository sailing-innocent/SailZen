# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
分析模块 Pydantic DTOs

原位置: sail_server/data/analysis.py

注意: 这是 Phase 3 最复杂的模块，包含多个子模块的 DTOs。
后续可能按子模块拆分为多个文件。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class RangeSelectionMode(str, Enum):
    """文本范围选择模式"""
    SINGLE_CHAPTER = "single_chapter"
    CHAPTER_RANGE = "chapter_range"
    MULTI_CHAPTER = "multi_chapter"
    FULL_EDITION = "full_edition"
    CURRENT_TO_END = "current_to_end"
    CUSTOM_RANGE = "custom_range"


class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    OUTLINE_EXTRACTION = "outline_extraction"
    CHARACTER_DETECTION = "character_detection"
    SETTING_EXTRACTION = "setting_extraction"
    RELATION_ANALYSIS = "relation_analysis"
    CONSISTENCY_CHECK = "consistency_check"
    CUSTOM_ANALYSIS = "custom_analysis"


class AnalysisTaskStatus(str, Enum):
    """分析任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Text Range DTOs
# ============================================================================

class TextRangeSelection(BaseModel):
    """文本范围选择"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    mode: RangeSelectionMode = Field(description="选择模式")
    chapter_index: Optional[int] = Field(default=None, description="单章索引")
    start_index: Optional[int] = Field(default=None, description="起始索引")
    end_index: Optional[int] = Field(default=None, description="结束索引")
    chapter_indices: List[int] = Field(default_factory=list, description="多章索引")
    node_ids: List[int] = Field(default_factory=list, description="节点ID列表")


class TextRangePreview(BaseModel):
    """文本范围预览"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    mode: RangeSelectionMode = Field(description="选择模式")
    chapter_count: int = Field(description="章节数")
    total_chars: int = Field(description="总字符数")
    total_words: int = Field(description="总词数")
    estimated_tokens: int = Field(description="预估token数")
    preview_text: Optional[str] = Field(default=None, description="预览文本")
    warnings: List[str] = Field(default_factory=list, description="警告信息")


# ============================================================================
# Analysis Task DTOs
# ============================================================================

class AnalysisTaskBase(BaseModel):
    """分析任务基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    task_type: AnalysisTaskType = Field(description="任务类型")
    priority: int = Field(default=5, description="优先级")


class AnalysisTaskCreateRequest(AnalysisTaskBase):
    """创建分析任务请求"""
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")


class AnalysisTaskResponse(AnalysisTaskBase):
    """分析任务响应"""
    id: int = Field(description="任务ID")
    status: AnalysisTaskStatus = Field(description="任务状态")
    progress: int = Field(default=0, description="进度百分比")
    current_step: Optional[str] = Field(default=None, description="当前步骤")
    result_summary: Optional[Dict[str, Any]] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")


class AnalysisTaskListResponse(BaseModel):
    """分析任务列表响应"""
    tasks: List[AnalysisTaskResponse]
    total: int


# ============================================================================
# Character DTOs
# ============================================================================

class CharacterBase(BaseModel):
    """人物基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    canonical_name: str = Field(description="规范名称")
    role_type: str = Field(default="supporting", description="角色类型")
    description: Optional[str] = Field(default=None, description="人物描述")


class CharacterCreateRequest(CharacterBase):
    """创建人物请求"""
    aliases: Optional[List[str]] = Field(default=None, description="别名列表")


class CharacterResponse(CharacterBase):
    """人物响应"""
    id: int = Field(description="人物ID")
    first_appearance_node_id: Optional[int] = Field(default=None, description="首次出现节点ID")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    importance_score: Optional[float] = Field(default=None, description="重要性评分")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class CharacterListResponse(BaseModel):
    """人物列表响应"""
    characters: List[CharacterResponse]
    total: int


# ============================================================================
# Outline DTOs
# ============================================================================

class OutlineNodeBase(BaseModel):
    """大纲节点基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    title: str = Field(description="节点标题")
    node_type: str = Field(default="scene", description="节点类型")
    summary: Optional[str] = Field(default=None, description="节点摘要")
    significance: str = Field(default="normal", description="重要性")


class OutlineNodeCreateRequest(OutlineNodeBase):
    """创建大纲节点请求"""
    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    sort_index: int = Field(default=0, description="排序索引")


class OutlineNodeResponse(OutlineNodeBase):
    """大纲节点响应"""
    id: int = Field(description="节点ID")
    outline_id: int = Field(description="所属大纲ID")
    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    depth: int = Field(default=0, description="深度")
    path: str = Field(default="", description="路径")
    sort_index: int = Field(default=0, description="排序索引")
    chapter_start_id: Optional[int] = Field(default=None, description="起始章节ID")
    chapter_end_id: Optional[int] = Field(default=None, description="结束章节ID")
    status: str = Field(default="draft", description="状态")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class OutlineBase(BaseModel):
    """大纲基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    title: str = Field(description="大纲标题")
    outline_type: str = Field(default="main", description="大纲类型")
    description: Optional[str] = Field(default=None, description="大纲描述")


class OutlineCreateRequest(OutlineBase):
    """创建大纲请求"""
    pass


class OutlineResponse(OutlineBase):
    """大纲响应"""
    id: int = Field(description="大纲ID")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    node_count: int = Field(default=0, description="节点数")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class OutlineListResponse(BaseModel):
    """大纲列表响应"""
    outlines: List[OutlineResponse]
    total: int


# ============================================================================
# Evidence DTOs
# ============================================================================

class TextEvidenceBase(BaseModel):
    """文本证据基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    node_id: int = Field(description="节点ID")
    target_type: str = Field(description="目标类型")
    target_id: int = Field(description="目标ID")
    text_snippet: Optional[str] = Field(default=None, description="文本片段")
    evidence_type: str = Field(default="explicit", description="证据类型")
    confidence: Optional[float] = Field(default=None, description="置信度")


class TextEvidenceCreateRequest(TextEvidenceBase):
    """创建文本证据请求"""
    start_char: Optional[int] = Field(default=None, description="起始字符")
    end_char: Optional[int] = Field(default=None, description="结束字符")
    context_before: Optional[str] = Field(default=None, description="前文")
    context_after: Optional[str] = Field(default=None, description="后文")


class TextEvidenceResponse(TextEvidenceBase):
    """文本证据响应"""
    id: int = Field(description="证据ID")
    start_char: Optional[int] = Field(default=None, description="起始字符")
    end_char: Optional[int] = Field(default=None, description="结束字符")
    context_before: Optional[str] = Field(default=None, description="前文")
    context_after: Optional[str] = Field(default=None, description="后文")
    source: str = Field(default="manual", description="来源")
    created_at: datetime = Field(description="创建时间")


class TextEvidenceListResponse(BaseModel):
    """文本证据列表响应"""
    evidences: List[TextEvidenceResponse]
    total: int
