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


class TextRangeContent(BaseModel):
    """文本范围内容"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    mode: RangeSelectionMode = Field(description="选择模式")
    full_text: str = Field(description="完整文本")
    chapter_count: int = Field(description="章节数")
    total_chars: int = Field(description="总字符数")
    total_words: int = Field(description="总词数")
    estimated_tokens: int = Field(description="预估token数")
    chapters: List[Dict[str, Any]] = Field(default_factory=list, description="章节内容列表")


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
# Setting DTOs
# ============================================================================

class SettingBase(BaseModel):
    """设定基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    setting_type: str = Field(description="设定类型")
    canonical_name: str = Field(description="规范名称")
    category: Optional[str] = Field(default=None, description="分类")
    description: Optional[str] = Field(default=None, description="描述")


class SettingCreateRequest(SettingBase):
    """创建设定请求"""
    pass


class SettingResponse(SettingBase):
    """设定响应"""
    id: int = Field(description="设定ID")
    first_appearance_node_id: Optional[int] = Field(default=None, description="首次出现节点ID")
    importance: str = Field(default="normal", description="重要性")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class SettingListResponse(BaseModel):
    """设定列表响应"""
    settings: List[SettingResponse]
    total: int


# ============================================================================
# Evidence DTOs
# ============================================================================

class TextEvidenceBase(BaseModel):
    """文本证据基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    node_id: int = Field(description="节点ID")
    evidence_type: str = Field(default="explicit", description="证据类型")


class TextEvidenceCreateRequest(TextEvidenceBase):
    """创建文本证据请求"""
    start_offset: int = Field(description="起始偏移")
    end_offset: int = Field(description="结束偏移")
    selected_text: str = Field(description="选中的文本")
    content: str = Field(description="证据内容")
    target_type: Optional[str] = Field(default=None, description="目标类型")
    target_id: Optional[str] = Field(default=None, description="目标ID")
    context: Optional[str] = Field(default=None, description="上下文")


class TextEvidenceResponse(TextEvidenceBase):
    """文本证据响应"""
    id: str = Field(description="证据ID")
    start_offset: int = Field(description="起始偏移")
    end_offset: int = Field(description="结束偏移")
    selected_text: str = Field(description="选中的文本")
    content: str = Field(description="证据内容")
    target_type: Optional[str] = Field(default=None, description="目标类型")
    target_id: Optional[str] = Field(default=None, description="目标ID")
    context: Optional[str] = Field(default=None, description="上下文")
    created_at: str = Field(description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")
    message: str = Field(default="操作成功", description="消息")


class TextEvidenceListResponse(BaseModel):
    """文本证据列表响应"""
    evidences: List[TextEvidenceResponse]
    total: int


# ============================================================================
# Extraction DTOs (AI提取结果)
# ============================================================================

class OutlineEvidence(BaseModel):
    """大纲证据"""
    model_config = ConfigDict(from_attributes=True)
    
    text: str = Field(default="", description="证据文本")
    chapter_title: Optional[str] = Field(default=None, description="章节标题")
    start_fragment: Optional[str] = Field(default=None, description="起始片段")
    end_fragment: Optional[str] = Field(default=None, description="结束片段")


class ExtractedOutlineNode(BaseModel):
    """提取的大纲节点
    
    用于AI大纲提取结果的中间表示，最终被转换为 OutlineNode ORM 模型
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(default="", description="节点临时ID")
    node_type: str = Field(default="", description="节点类型 (act/arc/scene/beat)")
    title: str = Field(default="", description="节点标题")
    summary: str = Field(default="", description="节点摘要")
    significance: str = Field(default="", description="重要性 (critical/major/normal/minor)")
    sort_index: int = Field(default=0, description="排序索引")
    parent_id: Optional[str] = Field(default=None, description="父节点ID")
    characters: List[str] = Field(default_factory=list, description="涉及人物列表")
    evidence_list: List[OutlineEvidence] = Field(default_factory=list, description="文本证据列表")


class OutlineExtractionConfig(BaseModel):
    """大纲提取配置"""
    model_config = ConfigDict(from_attributes=True)
    
    granularity: str = Field(default="scene", description="粒度 (act/arc/scene/beat)")
    outline_type: str = Field(default="main", description="大纲类型 (main/subplot/character_arc/theme)")
    extract_turning_points: bool = Field(default=True, description="是否提取转折点")
    extract_characters: bool = Field(default=True, description="是否提取人物")
    max_nodes: int = Field(default=50, description="最大节点数")
    temperature: float = Field(default=0.3, description="LLM温度")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")
    prompt_template_id: Optional[str] = Field(default=None, description="提示词模板ID")


class OutlineExtractionRequest(BaseModel):
    """大纲提取请求"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: OutlineExtractionConfig = Field(default_factory=OutlineExtractionConfig, description="提取配置")
    work_title: str = Field(default="", description="作品标题")
    known_characters: List[str] = Field(default_factory=list, description="已知人物列表")


class OutlineExtractionResult(BaseModel):
    """大纲提取结果"""
    model_config = ConfigDict(from_attributes=True)
    
    nodes: List[ExtractedOutlineNode] = Field(default_factory=list, description="提取的节点列表")
    turning_points: List[Dict[str, Any]] = Field(default_factory=list, description="转折点列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class OutlineExtractionResponse(BaseModel):
    """大纲提取响应"""
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(default=False, description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    result: Optional[OutlineExtractionResult] = Field(default=None, description="提取结果")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


# ============================================================================
# Character Detection DTOs
# ============================================================================

class DetectedCharacterAlias(BaseModel):
    """检测到的别名"""
    model_config = ConfigDict(from_attributes=True)
    
    alias: str = Field(default="", description="别名")
    alias_type: str = Field(default="other", description="别名类型")


class DetectedCharacterAttribute(BaseModel):
    """检测到的属性"""
    model_config = ConfigDict(from_attributes=True)
    
    category: str = Field(default="", description="分类")
    key: str = Field(default="", description="键")
    value: str = Field(default="", description="值")
    confidence: Optional[float] = Field(default=None, description="置信度")
    source_text: Optional[str] = Field(default=None, description="源文本")


class DetectedCharacterRelation(BaseModel):
    """检测到的人物关系"""
    model_config = ConfigDict(from_attributes=True)
    
    target_name: str = Field(default="", description="目标人物名称")
    relation_type: str = Field(default="", description="关系类型")
    description: Optional[str] = Field(default=None, description="描述")
    evidence: Optional[str] = Field(default=None, description="证据")


class DetectedCharacter(BaseModel):
    """检测到的人物"""
    model_config = ConfigDict(from_attributes=True)
    
    canonical_name: str = Field(default="", description="规范名称")
    aliases: List[DetectedCharacterAlias] = Field(default_factory=list, description="别名列表")
    role_type: str = Field(default="supporting", description="角色类型")
    role_confidence: float = Field(default=0.5, description="角色置信度")
    first_appearance: Optional[Dict[str, str]] = Field(default=None, description="首次出现")
    description: str = Field(default="", description="描述")
    attributes: List[DetectedCharacterAttribute] = Field(default_factory=list, description="属性列表")
    relations: List[DetectedCharacterRelation] = Field(default_factory=list, description="关系列表")
    key_actions: List[str] = Field(default_factory=list, description="关键行为")
    mention_count: int = Field(default=0, description="提及次数")


class CharacterDetectionConfig(BaseModel):
    """人物检测配置"""
    model_config = ConfigDict(from_attributes=True)
    
    detect_aliases: bool = Field(default=True, description="检测别名")
    detect_attributes: bool = Field(default=True, description="检测属性")
    detect_relations: bool = Field(default=True, description="检测关系")
    min_confidence: float = Field(default=0.5, description="最小置信度")
    max_characters: int = Field(default=100, description="最大人物数")
    temperature: float = Field(default=0.3, description="LLM温度")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")


class CharacterDetectionRequest(BaseModel):
    """人物检测请求"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: CharacterDetectionConfig = Field(default_factory=CharacterDetectionConfig, description="检测配置")
    work_title: str = Field(default="", description="作品标题")
    known_characters: List[str] = Field(default_factory=list, description="已知人物列表")


class CharacterDetectionResult(BaseModel):
    """人物检测结果"""
    model_config = ConfigDict(from_attributes=True)
    
    characters: List[DetectedCharacter] = Field(default_factory=list, description="检测到的人物列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    raw_response: Optional[str] = Field(default=None, description="原始响应")


class CharacterDetectionResponse(BaseModel):
    """人物检测响应"""
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(default=False, description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    result: Optional[CharacterDetectionResult] = Field(default=None, description="检测结果")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


# ============================================================================
# Setting Extraction DTOs
# ============================================================================

class ExtractedSettingAttribute(BaseModel):
    """提取的设定属性"""
    model_config = ConfigDict(from_attributes=True)
    
    key: str = Field(default="", description="键")
    value: str = Field(default="", description="值")
    description: Optional[str] = Field(default=None, description="描述")


class ExtractedSettingRelation(BaseModel):
    """提取的设定关系"""
    model_config = ConfigDict(from_attributes=True)
    
    target_name: str = Field(default="", description="目标名称")
    relation_type: str = Field(default="", description="关系类型")
    description: Optional[str] = Field(default=None, description="描述")


class ExtractedSetting(BaseModel):
    """提取的设定"""
    model_config = ConfigDict(from_attributes=True)
    
    canonical_name: str = Field(default="", description="规范名称")
    setting_type: str = Field(default="", description="设定类型")
    category: str = Field(default="", description="分类")
    importance: str = Field(default="minor", description="重要性")
    first_appearance: Optional[Dict[str, str]] = Field(default=None, description="首次出现")
    description: str = Field(default="", description="描述")
    attributes: List[ExtractedSettingAttribute] = Field(default_factory=list, description="属性列表")
    relations: List[ExtractedSettingRelation] = Field(default_factory=list, description="关系列表")
    key_scenes: List[str] = Field(default_factory=list, description="关键场景")
    mention_count: int = Field(default=0, description="提及次数")


class SettingExtractionConfig(BaseModel):
    """设定提取配置"""
    model_config = ConfigDict(from_attributes=True)
    
    setting_types: List[str] = Field(default_factory=lambda: [
        "item", "location", "organization", "concept", "magic_system", "creature", "event_type"
    ], description="设定类型列表")
    min_importance: str = Field(default="background", description="最小重要性")
    extract_relations: bool = Field(default=True, description="提取关系")
    extract_attributes: bool = Field(default=True, description="提取属性")
    max_settings: int = Field(default=100, description="最大设定数")
    temperature: float = Field(default=0.3, description="LLM温度")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")


class SettingExtractionRequest(BaseModel):
    """设定提取请求"""
    model_config = ConfigDict(from_attributes=True)
    
    edition_id: int = Field(description="版本ID")
    range_selection: TextRangeSelection = Field(description="文本范围选择")
    config: SettingExtractionConfig = Field(default_factory=SettingExtractionConfig, description="提取配置")
    work_title: str = Field(default="", description="作品标题")
    known_settings: List[str] = Field(default_factory=list, description="已知设定列表")


class SettingExtractionResult(BaseModel):
    """设定提取结果"""
    model_config = ConfigDict(from_attributes=True)
    
    settings: List[ExtractedSetting] = Field(default_factory=list, description="提取的设定列表")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    raw_response: Optional[str] = Field(default=None, description="原始响应")


class SettingExtractionResponse(BaseModel):
    """设定提取响应"""
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(default=False, description="是否成功")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    result: Optional[SettingExtractionResult] = Field(default=None, description="提取结果")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


# ============================================================================
# Setting Data DTOs (for backward compatibility)
# ============================================================================

class SettingData(BaseModel):
    """设定数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="设定ID")
    edition_id: int = Field(default=0, description="版本ID")
    setting_type: str = Field(default="", description="设定类型")
    canonical_name: str = Field(default="", description="规范名称")
    category: Optional[str] = Field(default=None, description="分类")
    description: Optional[str] = Field(default=None, description="描述")
    first_appearance_node_id: Optional[int] = Field(default=None, description="首次出现节点ID")
    importance: str = Field(default="normal", description="重要性")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class SettingAttributeData(BaseModel):
    """设定属性数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="属性ID")
    setting_id: int = Field(default=0, description="设定ID")
    attr_key: str = Field(default="", description="属性键")
    attr_value: str = Field(default="", description="属性值")
    source: str = Field(default="manual", description="来源")
    source_node_id: Optional[int] = Field(default=None, description="来源节点ID")
    status: str = Field(default="pending", description="状态")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class SettingRelationData(BaseModel):
    """设定关系数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="关系ID")
    edition_id: int = Field(default=0, description="版本ID")
    source_setting_id: int = Field(default=0, description="源设定ID")
    target_setting_id: int = Field(default=0, description="目标设定ID")
    relation_type: str = Field(default="", description="关系类型")
    description: Optional[str] = Field(default=None, description="描述")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class OutlineData(BaseModel):
    """大纲数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="大纲ID")
    edition_id: int = Field(default=0, description="版本ID")
    title: str = Field(default="", description="大纲标题")
    outline_type: str = Field(default="main", description="大纲类型")
    description: Optional[str] = Field(default=None, description="大纲描述")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    node_count: int = Field(default=0, description="节点数")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


# ============================================================================
# Legacy Data DTOs (with read_from_orm method for backward compatibility)
# ============================================================================

class CharacterData(BaseModel):
    """人物数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="人物ID")
    edition_id: int = Field(default=0, description="版本ID")
    canonical_name: str = Field(default="", description="规范名称")
    role_type: str = Field(default="supporting", description="角色类型")
    description: Optional[str] = Field(default=None, description="描述")
    first_appearance_node_id: Optional[int] = Field(default=None, description="首次出现节点ID")
    status: str = Field(default="draft", description="状态")
    source: str = Field(default="manual", description="来源")
    importance_score: Optional[float] = Field(default=None, description="重要性评分")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class CharacterAliasData(BaseModel):
    """人物别名数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="别名ID")
    character_id: int = Field(default=0, description="人物ID")
    alias: str = Field(default="", description="别名")
    alias_type: str = Field(default="nickname", description="别名类型")
    usage_context: Optional[str] = Field(default=None, description="使用上下文")
    is_preferred: bool = Field(default=False, description="是否首选")
    source: str = Field(default="manual", description="来源")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class CharacterAttributeData(BaseModel):
    """人物属性数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="属性ID")
    character_id: int = Field(default=0, description="人物ID")
    category: Optional[str] = Field(default=None, description="分类")
    attr_key: str = Field(default="", description="属性键")
    attr_value: str = Field(default="", description="属性值")
    confidence: Optional[float] = Field(default=None, description="置信度")
    source: str = Field(default="manual", description="来源")
    source_node_id: Optional[int] = Field(default=None, description="来源节点ID")
    status: str = Field(default="pending", description="状态")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class CharacterRelationData(BaseModel):
    """人物关系数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="关系ID")
    edition_id: int = Field(default=0, description="版本ID")
    source_character_id: int = Field(default=0, description="源人物ID")
    target_character_id: int = Field(default=0, description="目标人物ID")
    relation_type: str = Field(default="", description="关系类型")
    relation_subtype: Optional[str] = Field(default=None, description="关系子类型")
    description: Optional[str] = Field(default=None, description="描述")
    strength: Optional[float] = Field(default=None, description="强度")
    is_mutual: bool = Field(default=True, description="是否双向")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class CharacterArcData(BaseModel):
    """人物弧光数据 DTO (向后兼容)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="弧光ID")
    character_id: int = Field(default=0, description="人物ID")
    arc_type: str = Field(default="", description="弧光类型")
    title: str = Field(default="", description="标题")
    description: Optional[str] = Field(default=None, description="描述")
    start_node_id: Optional[int] = Field(default=None, description="起始节点ID")
    end_node_id: Optional[int] = Field(default=None, description="结束节点ID")
    status: str = Field(default="draft", description="状态")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class CharacterProfile(BaseModel):
    """人物档案"""
    model_config = ConfigDict(from_attributes=True)
    
    character: CharacterData = Field(default_factory=CharacterData, description="人物数据")
    aliases: List[CharacterAliasData] = Field(default_factory=list, description="别名列表")
    attributes: List[CharacterAttributeData] = Field(default_factory=list, description="属性列表")
    arcs: List[CharacterArcData] = Field(default_factory=list, description="弧光列表")
    relations: List[CharacterRelationData] = Field(default_factory=list, description="关系列表")


class AnalysisTaskData(BaseModel):
    """分析任务数据 DTO (向后兼容)
    
    注意: 请使用 AnalysisTaskResponse 替代此类
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="任务ID")
    edition_id: int = Field(default=0, description="版本ID")
    task_type: str = Field(default="", description="任务类型")
    status: str = Field(default="pending", description="状态")
    target_scope: str = Field(default="full", description="目标范围")
    target_node_ids: Optional[List[int]] = Field(default=None, description="目标节点ID列表")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="参数")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")
    llm_model: Optional[str] = Field(default=None, description="LLM模型")
    llm_prompt_template: Optional[str] = Field(default=None, description="LLM提示模板")
    priority: int = Field(default=5, description="优先级")
    result_summary: Optional[Dict[str, Any]] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    result_count: int = Field(default=0, description="结果数量")
    
    @classmethod
    def read_from_orm(cls, orm: Any, result_count: int = 0) -> "AnalysisTaskData":
        """从 ORM 模型创建 DTO"""
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            task_type=orm.task_type,
            status=orm.status,
            target_scope=getattr(orm, 'target_scope', 'full'),
            target_node_ids=getattr(orm, 'target_node_ids', None),
            parameters=getattr(orm, 'parameters', {}) or {},
            llm_provider=getattr(orm, 'llm_provider', None),
            llm_model=getattr(orm, 'llm_model', None),
            llm_prompt_template=getattr(orm, 'llm_prompt_template', None),
            priority=getattr(orm, 'priority', 5),
            result_summary=getattr(orm, 'result_summary', None),
            error_message=getattr(orm, 'error_message', None),
            created_at=getattr(orm, 'created_at', None),
            started_at=getattr(orm, 'started_at', None),
            completed_at=getattr(orm, 'completed_at', None),
            result_count=result_count,
        )


class AnalysisResultData(BaseModel):
    """分析结果数据 DTO (向后兼容)
    
    注意: 请使用 Pydantic DTOs 替代此类
    """
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = Field(default=None, description="结果ID")
    task_id: int = Field(default=0, description="任务ID")
    result_type: str = Field(default="", description="结果类型")
    result_data: Dict[str, Any] = Field(default_factory=dict, description="结果数据")
    confidence: Optional[float] = Field(default=None, description="置信度")
    review_status: str = Field(default="pending", description="审核状态")
    reviewer: Optional[str] = Field(default=None, description="审核人")
    review_notes: Optional[str] = Field(default=None, description="审核备注")
    reviewed_at: Optional[datetime] = Field(default=None, description="审核时间")
    applied: bool = Field(default=False, description="是否已应用")
    applied_at: Optional[datetime] = Field(default=None, description="应用时间")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    
    @classmethod
    def read_from_orm(cls, orm: Any) -> "AnalysisResultData":
        """从 ORM 模型创建 DTO"""
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            result_type=orm.result_type,
            result_data=orm.result_data or {},
            confidence=orm.confidence,
            review_status=getattr(orm, 'review_status', 'pending'),
            reviewer=getattr(orm, 'reviewer', None),
            review_notes=getattr(orm, 'review_notes', None),
            reviewed_at=getattr(orm, 'reviewed_at', None),
            applied=getattr(orm, 'applied', False),
            applied_at=getattr(orm, 'applied_at', None),
            created_at=getattr(orm, 'created_at', None),
            updated_at=getattr(orm, 'updated_at', None),
        )
