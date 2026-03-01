# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Data Models and DTOs
# @author sailing-innocent
# @date 2025-02-28
# @version 2.0
# ---------------------------------

"""
分析模块数据模型

此文件现在仅作为聚合入口，提供向后兼容的导入。
所有 ORM 模型已迁移至 sail_server.infrastructure.orm.analysis
所有 Pydantic DTOs 已迁移至 sail_server.application.dto.analysis
"""

# ============================================================================
# ORM Models (从 infrastructure 层导入)
# ============================================================================

from sail_server.infrastructure.orm.analysis import (
    # Outline
    Outline, OutlineNode, OutlineEvent,
    # Character
    Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation,
    # Setting
    Setting, SettingAttribute, SettingRelation, CharacterSettingLink,
    # Evidence
    TextEvidence,
    # Task
    AnalysisTask, AnalysisResult,
)

# ============================================================================
# Pydantic DTOs (从 application 层导入)
# ============================================================================

from sail_server.application.dto.analysis import (
    # Enums
    RangeSelectionMode,
    AnalysisTaskType,
    AnalysisTaskStatus,
    
    # Text Range DTOs
    TextRangeSelection,
    TextRangePreview,
    
    # Analysis Task DTOs
    AnalysisTaskBase,
    AnalysisTaskCreateRequest,
    AnalysisTaskResponse,
    AnalysisTaskListResponse,
    
    # Character DTOs
    CharacterBase,
    CharacterCreateRequest,
    CharacterResponse,
    CharacterListResponse,
    
    # Outline DTOs
    OutlineBase,
    OutlineCreateRequest,
    OutlineResponse,
    OutlineListResponse,
    OutlineNodeBase,
    OutlineNodeCreateRequest,
    OutlineNodeResponse,
    
    # Evidence DTOs
    TextEvidenceBase,
    TextEvidenceCreateRequest,
    TextEvidenceResponse,
    TextEvidenceListResponse,
)

# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# 保留旧的 DTO 名称别名（用于向后兼容）
TextEvidenceDTO = TextEvidenceResponse

# 旧版 dataclass DTOs 的兼容性导入
# 注意：这些类已被 Pydantic DTOs 取代，保留别名以便旧代码迁移
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class OutlineData:
    """大纲数据 DTO (向后兼容)
    
    注意: 请使用 sail_server.application.dto.analysis.OutlineResponse
    """
    id: Optional[int] = None
    edition_id: int = 0
    title: str = ""
    outline_type: str = "main"
    description: Optional[str] = None
    root_node_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    node_count: int = 0


@dataclass
class OutlineNodeData:
    """大纲节点数据 DTO (向后兼容)
    
    注意: 请使用 sail_server.application.dto.analysis.OutlineNodeResponse
    """
    id: Optional[int] = None
    outline_id: int = 0
    parent_id: Optional[int] = None
    node_type: str = "scene"
    title: str = ""
    summary: Optional[str] = None
    significance: str = "normal"
    chapter_start_id: Optional[int] = None
    chapter_end_id: Optional[int] = None
    path: str = ""
    depth: int = 0
    sort_index: int = 0
    status: str = "draft"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CharacterData:
    """人物数据 DTO (向后兼容)
    
    注意: 请使用 sail_server.application.dto.analysis.CharacterResponse
    """
    id: Optional[int] = None
    edition_id: int = 0
    canonical_name: str = ""
    role_type: str = "supporting"
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    status: str = "draft"
    source: str = "manual"
    importance_score: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CharacterAliasData:
    """人物别名数据 DTO (向后兼容)"""
    id: Optional[int] = None
    character_id: int = 0
    alias: str = ""
    alias_type: str = "nickname"
    usage_context: Optional[str] = None
    is_preferred: bool = False
    source: str = "manual"
    created_at: Optional[datetime] = None


@dataclass
class CharacterAttributeData:
    """人物属性数据 DTO (向后兼容)"""
    id: Optional[int] = None
    character_id: int = 0
    category: Optional[str] = None
    attr_key: str = ""
    attr_value: str = ""
    confidence: Optional[float] = None
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class CharacterRelationData:
    """人物关系数据 DTO (向后兼容)"""
    id: Optional[int] = None
    edition_id: int = 0
    source_character_id: int = 0
    target_character_id: int = 0
    relation_type: str = ""
    relation_subtype: Optional[str] = None
    description: Optional[str] = None
    strength: Optional[float] = None
    is_mutual: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class SettingData:
    """设定数据 DTO (向后兼容)"""
    id: Optional[int] = None
    edition_id: int = 0
    setting_type: str = "item"
    canonical_name: str = ""
    category: Optional[str] = None
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    importance: str = "normal"
    status: str = "draft"
    source: str = "manual"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class SettingAttributeData:
    """设定属性数据 DTO (向后兼容)"""
    id: Optional[int] = None
    setting_id: int = 0
    attr_key: str = ""
    attr_value: str = ""
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None


@dataclass
class SettingRelationData:
    """设定关系数据 DTO (向后兼容)"""
    id: Optional[int] = None
    edition_id: int = 0
    source_setting_id: int = 0
    target_setting_id: int = 0
    relation_type: str = ""
    description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class CharacterSettingLinkData:
    """人物设定关联数据 DTO (向后兼容)"""
    id: Optional[int] = None
    character_id: int = 0
    setting_id: int = 0
    link_type: str = "owner"
    description: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class TextEvidenceData:
    """文本证据数据 DTO (向后兼容)
    
    注意: 请使用 sail_server.application.dto.analysis.TextEvidenceResponse
    """
    id: Optional[int] = None
    edition_id: int = 0
    node_id: int = 0
    target_type: str = ""
    target_id: int = 0
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    text_snippet: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    evidence_type: str = "explicit"
    confidence: Optional[float] = None
    source: str = "manual"
    created_at: Optional[datetime] = None


@dataclass
class AnalysisTaskData:
    """分析任务数据 DTO (向后兼容)"""
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
class AnalysisResultData:
    """分析结果数据 DTO (向后兼容)"""
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


# ============================================================================
# Extraction Types (向后兼容)
# ============================================================================

@dataclass
class OutlineExtractionConfig:
    """大纲提取配置 (向后兼容)"""
    granularity: str = "scene"
    outline_type: str = "main"
    extract_turning_points: bool = True
    extract_characters: bool = True
    max_nodes: int = 50
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "outline_extraction_v2"


@dataclass
class OutlineExtractionRequest:
    """大纲提取请求 (向后兼容)"""
    edition_id: int = 0
    range_selection: Optional[TextRangeSelection] = None
    config: OutlineExtractionConfig = field(default_factory=OutlineExtractionConfig)
    work_title: str = ""
    known_characters: List[str] = field(default_factory=list)


@dataclass
class OutlineEvidence:
    """大纲证据 (向后兼容)"""
    text: str = ""
    chapter_title: Optional[str] = None
    start_fragment: Optional[str] = None
    end_fragment: Optional[str] = None


@dataclass
class ExtractedOutlineNode:
    """提取的大纲节点 (向后兼容)"""
    id: str = ""
    node_type: str = ""
    title: str = ""
    summary: str = ""
    significance: str = ""
    sort_index: int = 0
    parent_id: Optional[str] = None
    characters: List[str] = field(default_factory=list)
    evidence_list: List[OutlineEvidence] = field(default_factory=list)


@dataclass
class OutlineExtractionResult:
    """大纲提取结果 (向后兼容)"""
    nodes: List[ExtractedOutlineNode] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    turning_points: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OutlineExtractionResponse:
    """大纲提取响应 (向后兼容)"""
    success: bool = False
    task_id: Optional[str] = None
    result: Optional[OutlineExtractionResult] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class CharacterDetectionConfig:
    """人物检测配置 (向后兼容)"""
    detect_aliases: bool = True
    detect_attributes: bool = True
    detect_relations: bool = True
    min_confidence: float = 0.5
    max_characters: int = 100
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "character_detection_v2"


@dataclass
class CharacterDetectionRequest:
    """人物检测请求 (向后兼容)"""
    edition_id: int = 0
    range_selection: Optional[TextRangeSelection] = None
    config: CharacterDetectionConfig = field(default_factory=CharacterDetectionConfig)
    work_title: str = ""
    known_characters: List[str] = field(default_factory=list)


@dataclass
class DetectedCharacterAlias:
    """检测到的别名 (向后兼容)"""
    alias: str = ""
    alias_type: str = "other"


@dataclass
class DetectedCharacterAttribute:
    """检测到的属性 (向后兼容)"""
    category: str = ""
    key: str = ""
    value: str = ""
    confidence: Optional[float] = None
    source_text: Optional[str] = None


@dataclass
class DetectedCharacterRelation:
    """检测到的人物关系 (向后兼容)"""
    target_name: str = ""
    relation_type: str = ""
    description: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class DetectedCharacter:
    """检测到的人物 (向后兼容)"""
    canonical_name: str = ""
    aliases: List[DetectedCharacterAlias] = field(default_factory=list)
    role_type: str = "supporting"
    role_confidence: float = 0.5
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[DetectedCharacterAttribute] = field(default_factory=list)
    relations: List[DetectedCharacterRelation] = field(default_factory=list)
    key_actions: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class CharacterDetectionResult:
    """人物检测结果 (向后兼容)"""
    characters: List[DetectedCharacter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[str] = None


@dataclass
class CharacterDetectionResponse:
    """人物检测响应 (向后兼容)"""
    success: bool = False
    task_id: Optional[str] = None
    result: Optional[CharacterDetectionResult] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class CharacterMergeCandidate:
    """人物合并候选 (向后兼容)"""
    character1_id: int = 0
    character2_id: int = 0
    character1_name: str = ""
    character2_name: str = ""
    similarity_score: float = 0.0
    merge_reason: str = ""
    suggested_action: str = ""


@dataclass
class CharacterDeduplicationResult:
    """人物去重结果 (向后兼容)"""
    merged_groups: List[List[int]] = field(default_factory=list)
    merge_candidates: List[CharacterMergeCandidate] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingExtractionConfig:
    """设定提取配置 (向后兼容)"""
    setting_types: List[str] = field(default_factory=lambda: [
        "item", "location", "organization", "concept", "magic_system", "creature", "event_type"
    ])
    min_importance: str = "background"
    extract_relations: bool = True
    extract_attributes: bool = True
    max_settings: int = 100
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "setting_extraction_v1"


@dataclass
class SettingExtractionRequest:
    """设定提取请求 (向后兼容)"""
    edition_id: int = 0
    range_selection: Optional[TextRangeSelection] = None
    config: SettingExtractionConfig = field(default_factory=SettingExtractionConfig)
    work_title: str = ""
    known_settings: List[str] = field(default_factory=list)


@dataclass
class ExtractedSettingAttribute:
    """提取的设定属性 (向后兼容)"""
    key: str = ""
    value: str = ""
    description: Optional[str] = None


@dataclass
class ExtractedSettingRelation:
    """提取的设定关系 (向后兼容)"""
    target_name: str = ""
    relation_type: str = ""
    description: Optional[str] = None


@dataclass
class ExtractedSetting:
    """提取的设定 (向后兼容)"""
    canonical_name: str = ""
    setting_type: str = ""
    category: str = ""
    importance: str = "minor"
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[ExtractedSettingAttribute] = field(default_factory=list)
    relations: List[ExtractedSettingRelation] = field(default_factory=list)
    key_scenes: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class SettingExtractionResult:
    """设定提取结果 (向后兼容)"""
    settings: List[ExtractedSetting] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[str] = None


@dataclass
class SettingExtractionResponse:
    """设定提取响应 (向后兼容)"""
    success: bool = False
    task_id: Optional[str] = None
    result: Optional[SettingExtractionResult] = None
    message: str = ""
    error: Optional[str] = None


# ============================================================================
# Legacy Compat Types (用于 analysis_compat.py)
# ============================================================================

@dataclass
class AnalysisTaskDataCompat:
    """分析任务数据（兼容旧格式）
    
    注意: 此类用于 analysis_compat.py 的兼容层
    """
    id: str = ""
    edition_id: int = 0
    task_type: AnalysisTaskType = field(default_factory=lambda: AnalysisTaskType.OUTLINE_EXTRACTION)
    status: AnalysisTaskStatus = field(default_factory=lambda: AnalysisTaskStatus.PENDING)
    range_selection: Optional[TextRangeSelection] = None
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    progress: int = 0
    current_step: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResultCompat:
    """分析结果（兼容旧格式）
    
    注意: 此类用于 analysis_compat.py 的兼容层
    """
    id: int = 0
    task_id: str = ""
    result_type: str = ""
    result_data: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    review_status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResultDataCompat:
    """分析结果数据（兼容旧格式）
    
    注意: 此类用于 analysis_compat.py 的兼容层
    """
    result_type: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    evidence_ids: List[str] = field(default_factory=list)
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# __all__ 导出列表
# ============================================================================

__all__ = [
    # ORM Models
    "Outline", "OutlineNode", "OutlineEvent",
    "Character", "CharacterAlias", "CharacterAttribute", "CharacterArc", "CharacterRelation",
    "Setting", "SettingAttribute", "SettingRelation", "CharacterSettingLink",
    "TextEvidence",
    "AnalysisTask", "AnalysisResult",
    
    # Enums
    "RangeSelectionMode",
    "AnalysisTaskType",
    "AnalysisTaskStatus",
    
    # Pydantic DTOs
    "TextRangeSelection",
    "TextRangePreview",
    "AnalysisTaskBase",
    "AnalysisTaskCreateRequest",
    "AnalysisTaskResponse",
    "AnalysisTaskListResponse",
    "CharacterBase",
    "CharacterCreateRequest",
    "CharacterResponse",
    "CharacterListResponse",
    "OutlineBase",
    "OutlineCreateRequest",
    "OutlineResponse",
    "OutlineListResponse",
    "OutlineNodeBase",
    "OutlineNodeCreateRequest",
    "OutlineNodeResponse",
    "TextEvidenceBase",
    "TextEvidenceCreateRequest",
    "TextEvidenceResponse",
    "TextEvidenceListResponse",
    
    # Backward Compatibility Aliases
    "TextEvidenceDTO",
    
    # Legacy Dataclass DTOs (for backward compatibility)
    "OutlineData",
    "OutlineNodeData",
    "CharacterData",
    "CharacterAliasData",
    "CharacterAttributeData",
    "CharacterRelationData",
    "SettingData",
    "SettingAttributeData",
    "SettingRelationData",
    "CharacterSettingLinkData",
    "TextEvidenceData",
    "AnalysisTaskData",
    "AnalysisResultData",
    
    # Extraction Types
    "OutlineExtractionConfig",
    "OutlineExtractionRequest",
    "OutlineEvidence",
    "ExtractedOutlineNode",
    "OutlineExtractionResult",
    "OutlineExtractionResponse",
    "CharacterDetectionConfig",
    "CharacterDetectionRequest",
    "DetectedCharacterAlias",
    "DetectedCharacterAttribute",
    "DetectedCharacterRelation",
    "DetectedCharacter",
    "CharacterDetectionResult",
    "CharacterDetectionResponse",
    "CharacterMergeCandidate",
    "CharacterDeduplicationResult",
    "SettingExtractionConfig",
    "SettingExtractionRequest",
    "ExtractedSettingAttribute",
    "ExtractedSettingRelation",
    "ExtractedSetting",
    "SettingExtractionResult",
    "SettingExtractionResponse",
    
    # Legacy Compat Types
    "AnalysisTaskDataCompat",
    "AnalysisResultCompat",
    "AnalysisResultDataCompat",
]
