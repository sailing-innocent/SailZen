# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Analysis Data Models and DTOs
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sail_server.data.types import JSONB


# ============================================================================
# Text Range Selection Types
# ============================================================================

class RangeSelectionMode(str, Enum):
    """文本范围选择模式"""
    SINGLE_CHAPTER = "single_chapter"      # 单章选择
    CHAPTER_RANGE = "chapter_range"        # 连续章节范围
    MULTI_CHAPTER = "multi_chapter"        # 多章选择（不连续）
    FULL_EDITION = "full_edition"          # 整部作品
    CURRENT_TO_END = "current_to_end"      # 从当前到结尾
    CUSTOM_RANGE = "custom_range"          # 自定义范围


@dataclass
class TextRangeSelection:
    """文本范围选择数据类
    
    支持多种选择模式：
    - single_chapter: 单个章节，使用 chapter_index 指定
    - chapter_range: 连续章节范围，使用 start_index 和 end_index 指定
    - multi_chapter: 多章选择，使用 chapter_indices 指定
    - full_edition: 整部作品，无需额外参数
    - current_to_end: 从当前章节到结尾，使用 start_index 指定
    - custom_range: 自定义范围，使用 node_ids 指定具体节点
    """
    edition_id: int
    mode: RangeSelectionMode
    
    # 单章选择
    chapter_index: Optional[int] = None
    
    # 连续章节范围
    start_index: Optional[int] = None
    end_index: Optional[int] = None
    
    # 多章选择（不连续）
    chapter_indices: List[int] = field(default_factory=list)
    
    # 自定义范围（节点ID列表）
    node_ids: List[int] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextRangePreview:
    """文本范围预览结果"""
    edition_id: int
    mode: RangeSelectionMode
    
    # 统计信息
    chapter_count: int
    total_chars: int
    total_words: int
    estimated_tokens: int
    
    # 选中的章节信息
    selected_chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    # 预览内容（前N个字符）
    preview_text: Optional[str] = None
    
    # 警告信息
    warnings: List[str] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TextRangeContent:
    """文本范围内容结果"""
    edition_id: int
    mode: RangeSelectionMode
    
    # 完整文本内容
    full_text: str
    
    # 统计信息
    chapter_count: int
    total_chars: int
    total_words: int
    estimated_tokens: int
    
    # 章节内容列表
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Analysis Task Types
# ============================================================================

class AnalysisTaskType(str, Enum):
    """分析任务类型"""
    OUTLINE_EXTRACTION = "outline_extraction"      # 大纲提取
    CHARACTER_DETECTION = "character_detection"    # 人物检测
    SETTING_EXTRACTION = "setting_extraction"      # 设定提取
    RELATION_ANALYSIS = "relation_analysis"        # 关系分析
    CONSISTENCY_CHECK = "consistency_check"        # 一致性检查
    CUSTOM_ANALYSIS = "custom_analysis"            # 自定义分析


class AnalysisTaskStatus(str, Enum):
    """分析任务状态"""
    PENDING = "pending"           # 待处理
    RUNNING = "running"           # 运行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消


@dataclass
class AnalysisTaskRequest:
    """分析任务请求"""
    edition_id: int
    task_type: AnalysisTaskType
    range_selection: TextRangeSelection
    
    # 任务配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 优先级
    priority: int = 0
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisTask:
    """分析任务"""
    id: str
    edition_id: int
    task_type: AnalysisTaskType
    status: AnalysisTaskStatus
    
    # 范围选择
    range_selection: TextRangeSelection
    
    # 任务配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    # 进度信息
    progress: int = 0  # 0-100
    current_step: Optional[str] = None
    
    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 结果
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # 元数据
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Evidence Types
# ============================================================================

@dataclass
class TextEvidence:
    """文本证据"""
    id: str
    edition_id: int
    
    # 证据位置
    node_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    
    # 证据类型和目标
    evidence_type: str  # character, setting, outline, etc.
    
    # 证据内容
    content: str
    context: Optional[str] = None  # 上下文
    
    # 目标关联
    target_type: Optional[str] = None  # character, setting, etc.
    target_id: Optional[str] = None
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceCreateRequest:
    """创建证据请求"""
    edition_id: int
    node_id: int
    start_offset: int
    end_offset: int
    selected_text: str
    evidence_type: str
    content: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceUpdateRequest:
    """更新证据请求"""
    content: Optional[str] = None
    evidence_type: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    context: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


@dataclass
class EvidenceListResponse:
    """证据列表响应"""
    evidences: List[TextEvidence]
    total: int
    node_id: Optional[int] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None


# ============================================================================
# Compatibility Types (for analysis_compat.py)
# ============================================================================

@dataclass
class AnalysisTaskData:
    """分析任务数据（兼容旧格式）"""
    id: str
    edition_id: int
    task_type: AnalysisTaskType
    status: AnalysisTaskStatus
    range_selection: TextRangeSelection
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
class AnalysisResult:
    """分析结果（兼容旧格式）"""
    id: int
    task_id: str
    result_type: str
    result_data: Dict[str, Any]
    confidence: Optional[float] = None
    review_status: str = "pending"  # pending, approved, rejected
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResultData:
    """分析结果数据（兼容旧格式）"""
    result_type: str
    content: Dict[str, Any]
    confidence: Optional[float] = None
    evidence_ids: List[str] = field(default_factory=list)
    meta_data: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Outline Extraction Types
# ============================================================================

@dataclass
class OutlineExtractionConfig:
    """大纲提取配置"""
    granularity: str = "scene"  # act | arc | scene | beat
    outline_type: str = "main"  # main | subplot | character_arc | theme
    extract_turning_points: bool = True
    extract_characters: bool = True
    max_nodes: int = 50
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "outline_extraction_v2"


@dataclass
class OutlineExtractionRequest:
    """大纲提取请求"""
    edition_id: int
    range_selection: TextRangeSelection
    config: OutlineExtractionConfig = field(default_factory=OutlineExtractionConfig)
    work_title: str = ""
    known_characters: List[str] = field(default_factory=list)


@dataclass
class OutlineEvidence:
    """大纲证据"""
    text: str
    chapter_title: Optional[str] = None
    start_fragment: Optional[str] = None
    end_fragment: Optional[str] = None


@dataclass
class ExtractedOutlineNode:
    """提取的大纲节点"""
    id: str
    node_type: str
    title: str
    summary: str
    significance: str
    sort_index: int
    parent_id: Optional[str] = None
    characters: List[str] = field(default_factory=list)
    evidence_list: List[OutlineEvidence] = field(default_factory=list)


@dataclass
class OutlineExtractionResult:
    """大纲提取结果"""
    nodes: List[ExtractedOutlineNode]
    metadata: Dict[str, Any]
    turning_points: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OutlineExtractionResponse:
    """大纲提取响应"""
    success: bool
    task_id: Optional[str] = None
    result: Optional[OutlineExtractionResult] = None
    message: str = ""
    error: Optional[str] = None


# ============================================================================
# Character Types (DTOs for model/analysis/character.py)
# ============================================================================

@dataclass
class CharacterData:
    """人物数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    canonical_name: str = ""
    role_type: str = "supporting"  # protagonist, antagonist, deuteragonist, supporting, minor, mentioned
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def create_orm(self):
        """创建 ORM 对象（简化实现）"""
        pass
    
    @classmethod
    def read_from_orm(cls, orm_obj, alias_count: int = 0, attribute_count: int = 0, relation_count: int = 0) -> 'CharacterData':
        """从 ORM 对象读取"""
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            canonical_name=orm_obj.canonical_name,
            role_type=orm_obj.role_type,
            description=orm_obj.description,
            first_appearance_node_id=orm_obj.first_appearance_node_id,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )
    
    def update_orm(self, orm_obj):
        """更新 ORM 对象"""
        orm_obj.canonical_name = self.canonical_name
        orm_obj.role_type = self.role_type
        orm_obj.description = self.description


@dataclass
class CharacterAliasData:
    """人物别名数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    alias: str = ""
    alias_type: str = "other"  # nickname, title, courtesy_name, other
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterAliasData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            alias=orm_obj.alias,
            alias_type=orm_obj.alias_type,
            created_at=orm_obj.created_at,
        )


@dataclass
class CharacterAttributeData:
    """人物属性数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    category: str = "other"  # appearance, personality, ability, background, relationship, other
    key: str = ""
    value: str = ""
    confidence: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterAttributeData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            category=orm_obj.category,
            key=orm_obj.key,
            value=orm_obj.value,
            confidence=orm_obj.confidence,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


@dataclass
class CharacterArcData:
    """人物弧光数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    arc_name: str = ""
    arc_type: str = "growth"  # growth, fall, redemption, tragedy, other
    description: Optional[str] = None
    start_chapter_id: Optional[int] = None
    end_chapter_id: Optional[int] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterArcData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            arc_name=orm_obj.arc_name,
            arc_type=orm_obj.arc_type,
            description=orm_obj.description,
            start_chapter_id=orm_obj.start_chapter_id,
            end_chapter_id=orm_obj.end_chapter_id,
            created_at=orm_obj.created_at,
        )


@dataclass
class CharacterRelationData:
    """人物关系数据 DTO"""
    id: Optional[int] = None
    source_character_id: int = 0
    target_character_id: int = 0
    relation_type: str = ""
    description: Optional[str] = None
    strength: Optional[float] = None
    is_mutual: bool = False
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterRelationData':
        return cls(
            id=orm_obj.id,
            source_character_id=orm_obj.source_character_id,
            target_character_id=orm_obj.target_character_id,
            relation_type=orm_obj.relation_type,
            description=orm_obj.description,
            strength=orm_obj.strength,
            is_mutual=orm_obj.is_mutual,
            created_at=orm_obj.created_at,
        )


@dataclass
class CharacterProfile:
    """人物档案"""
    character: CharacterData
    aliases: List[CharacterAliasData]
    attributes: List[CharacterAttributeData]
    arcs: List[CharacterArcData]
    relations: List[CharacterRelationData]


@dataclass
class RelationGraphData:
    """关系图谱数据"""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


# ============================================================================
# Outline Types (DTOs for model/analysis/outline.py)
# ============================================================================

@dataclass
class OutlineData:
    """大纲数据 DTO - 字段与 ORM 保持一致"""
    id: Optional[int] = None
    edition_id: int = 0
    title: str = ""  # 与 ORM 字段保持一致
    outline_type: str = "main"  # main, subplot, character_arc, theme
    description: Optional[str] = None
    root_node_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    node_count: int = 0
    
    def create_orm(self) -> 'Outline':
        """创建 ORM 对象"""
        # 注意：Outline 类在当前文件底部定义，这里使用延迟导入避免循环导入
        import sys
        current_module = sys.modules[__name__]
        Outline = getattr(current_module, 'Outline')
        return Outline(
            edition_id=self.edition_id,
            title=self.title,
            outline_type=self.outline_type,
            description=self.description,
            status="draft",
            source="extraction",
        )
    
    @classmethod
    def read_from_orm(cls, orm_obj, node_count: int = 0) -> 'OutlineData':
        """从 ORM 对象创建 DTO"""
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            title=orm_obj.title,
            outline_type=orm_obj.outline_type,
            description=orm_obj.description,
            root_node_id=orm_obj.meta_data.get("root_node_id") if orm_obj.meta_data else None,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
            node_count=node_count,
        )
    
    def update_orm(self, orm_obj):
        """更新 ORM 对象"""
        orm_obj.title = self.title
        orm_obj.description = self.description


@dataclass
class OutlineNodeData:
    """大纲节点数据 DTO"""
    id: Optional[int] = None
    outline_id: int = 0
    parent_id: Optional[int] = None
    node_type: str = "scene"  # act, arc, scene, beat, event
    title: str = ""
    summary: Optional[str] = None
    significance: str = "normal"  # critical, major, normal, minor
    chapter_start_id: Optional[int] = None
    chapter_end_id: Optional[int] = None
    path: str = ""
    depth: int = 0
    sort_index: int = 0
    status: str = "draft"  # draft, reviewed, approved
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj, children_count: int = 0, events_count: int = 0) -> 'OutlineNodeData':
        return cls(
            id=orm_obj.id,
            outline_id=orm_obj.outline_id,
            parent_id=orm_obj.parent_id,
            node_type=orm_obj.node_type,
            title=orm_obj.title,
            summary=orm_obj.summary,
            significance=orm_obj.significance,
            chapter_start_id=orm_obj.chapter_start_id,
            chapter_end_id=orm_obj.chapter_end_id,
            path=orm_obj.path,
            depth=orm_obj.depth,
            sort_index=orm_obj.sort_index,
            status=orm_obj.status,
            meta_data=orm_obj.meta_data or {},
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


@dataclass
class OutlineEventData:
    """大纲事件数据 DTO"""
    id: Optional[int] = None
    outline_node_id: int = 0
    event_type: str = "plot"  # plot, conflict, revelation, resolution, climax
    title: str = ""
    description: Optional[str] = None
    chronology_order: Optional[float] = None
    narrative_order: Optional[int] = None
    importance: str = "normal"  # critical, major, normal, minor
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'OutlineEventData':
        return cls(
            id=orm_obj.id,
            outline_node_id=orm_obj.outline_node_id,
            event_type=orm_obj.event_type,
            title=orm_obj.title,
            description=orm_obj.description,
            chronology_order=orm_obj.chronology_order,
            narrative_order=orm_obj.narrative_order,
            importance=orm_obj.importance,
            created_at=orm_obj.created_at,
        )


@dataclass
class OutlineTree:
    """大纲树结构"""
    outline: OutlineData
    nodes: List[Dict[str, Any]]


# ============================================================================
# Evidence Types (DTOs for model/analysis/evidence.py)
# ============================================================================

@dataclass
class TextEvidenceData:
    """文本证据数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    node_id: int = 0
    target_type: str = ""  # character, setting, outline_node, etc.
    target_id: int = 0
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    text_snippet: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    evidence_type: str = "explicit"  # explicit, implicit, inferred
    confidence: Optional[float] = None
    source: str = "manual"  # manual, llm_extraction
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'TextEvidenceData':
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            node_id=orm_obj.node_id,
            target_type=orm_obj.target_type,
            target_id=orm_obj.target_id,
            start_char=orm_obj.start_char,
            end_char=orm_obj.end_char,
            text_snippet=orm_obj.text_snippet,
            context_before=orm_obj.context_before,
            context_after=orm_obj.context_after,
            evidence_type=orm_obj.evidence_type,
            confidence=orm_obj.confidence,
            source=orm_obj.source,
            created_at=orm_obj.created_at,
        )


@dataclass
class AnalysisTaskData:
    """分析任务数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    task_type: str = ""  # outline_extraction, character_detection, etc.
    status: str = "pending"  # pending, running, completed, failed, cancelled
    target_scope: str = "full"  # full, selected, custom
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
    
    def create_orm(self):
        pass
    
    @classmethod
    def read_from_orm(cls, orm_obj, result_count: int = 0) -> 'AnalysisTaskData':
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            task_type=orm_obj.task_type,
            status=orm_obj.status,
            target_scope=orm_obj.target_scope,
            target_node_ids=orm_obj.target_node_ids,
            parameters=orm_obj.parameters or {},
            llm_provider=orm_obj.llm_provider,
            llm_model=orm_obj.llm_model,
            llm_prompt_template=orm_obj.llm_prompt_template,
            priority=orm_obj.priority,
            result_summary=orm_obj.result_summary,
            error_message=orm_obj.error_message,
            created_at=orm_obj.created_at,
            started_at=orm_obj.started_at,
            completed_at=orm_obj.completed_at,
        )


@dataclass
class AnalysisResultData:
    """分析结果数据 DTO"""
    id: Optional[int] = None
    task_id: int = 0
    result_type: str = ""  # character, setting, outline_node, etc.
    result_data: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    review_status: str = "pending"  # pending, approved, rejected
    reviewer: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'AnalysisResultData':
        return cls(
            id=orm_obj.id,
            task_id=orm_obj.task_id,
            result_type=orm_obj.result_type,
            result_data=orm_obj.result_data or {},
            confidence=orm_obj.confidence,
            review_status=orm_obj.review_status,
            reviewer=orm_obj.reviewer,
            review_notes=orm_obj.review_notes,
            reviewed_at=orm_obj.reviewed_at,
            applied=orm_obj.applied,
            applied_at=orm_obj.applied_at,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


# ============================================================================
# Character DTOs
# ============================================================================

@dataclass
class CharacterData:
    """人物数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    canonical_name: str = ""
    role_type: str = "supporting"  # protagonist, antagonist, deuteragonist, supporting, minor
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    status: str = "draft"
    source: str = "manual"
    importance_score: Optional[float] = None
    aliases: List['CharacterAliasData'] = field(default_factory=list)
    attributes: List['CharacterAttributeData'] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def create_orm(self) -> 'Character':
        """创建 ORM 对象"""
        import sys
        current_module = sys.modules[__name__]
        Character = getattr(current_module, 'Character')
        return Character(
            edition_id=self.edition_id,
            canonical_name=self.canonical_name,
            role_type=self.role_type,
            description=self.description,
            first_appearance_node_id=self.first_appearance_node_id,
            status=self.status,
            source=self.source,
            importance_score=self.importance_score,
        )
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterData':
        """从 ORM 对象创建 DTO"""
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            canonical_name=orm_obj.canonical_name,
            role_type=orm_obj.role_type or "supporting",
            description=orm_obj.description,
            first_appearance_node_id=orm_obj.first_appearance_node_id,
            status=orm_obj.status or "draft",
            source=orm_obj.source or "manual",
            importance_score=orm_obj.importance_score,
            aliases=[CharacterAliasData.read_from_orm(a) for a in orm_obj.aliases] if hasattr(orm_obj, 'aliases') else [],
            attributes=[CharacterAttributeData.read_from_orm(a) for a in orm_obj.attributes] if hasattr(orm_obj, 'attributes') else [],
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


@dataclass
class CharacterAliasData:
    """人物别名数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    alias: str = ""
    alias_type: str = "nickname"  # nickname, title, formal, diminutive
    usage_context: Optional[str] = None
    is_preferred: bool = False
    source: str = "manual"
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterAliasData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            alias=orm_obj.alias,
            alias_type=orm_obj.alias_type or "nickname",
            usage_context=orm_obj.usage_context,
            is_preferred=orm_obj.is_preferred or False,
            source=orm_obj.source or "manual",
            created_at=orm_obj.created_at,
        )


@dataclass
class CharacterAttributeData:
    """人物属性数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    category: Optional[str] = None  # physical, personality, background, ability
    attr_key: str = ""
    attr_value: str = ""
    confidence: Optional[float] = None
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterAttributeData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            category=orm_obj.category,
            attr_key=orm_obj.attr_key,
            attr_value=orm_obj.attr_value,
            confidence=orm_obj.confidence,
            source=orm_obj.source or "manual",
            source_node_id=orm_obj.source_node_id,
            status=orm_obj.status or "pending",
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


@dataclass
class CharacterRelationData:
    """人物关系数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    source_character_id: int = 0
    target_character_id: int = 0
    relation_type: str = ""  # family, friend, enemy, romantic, professional
    relation_subtype: Optional[str] = None
    description: Optional[str] = None
    strength: Optional[float] = None
    is_mutual: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterRelationData':
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            source_character_id=orm_obj.source_character_id,
            target_character_id=orm_obj.target_character_id,
            relation_type=orm_obj.relation_type,
            relation_subtype=orm_obj.relation_subtype,
            description=orm_obj.description,
            strength=orm_obj.strength,
            is_mutual=orm_obj.is_mutual if orm_obj.is_mutual is not None else True,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


# ============================================================================
# Setting DTOs
# ============================================================================

@dataclass
class SettingData:
    """设定数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    setting_type: str = "item"  # item, location, organization, concept, magic_system, creature, event_type
    canonical_name: str = ""
    category: Optional[str] = None
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    importance: str = "normal"  # critical, major, normal, minor
    status: str = "draft"
    source: str = "manual"
    attributes: List['SettingAttributeData'] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def create_orm(self) -> 'Setting':
        """创建 ORM 对象"""
        import sys
        current_module = sys.modules[__name__]
        Setting = getattr(current_module, 'Setting')
        return Setting(
            edition_id=self.edition_id,
            setting_type=self.setting_type,
            canonical_name=self.canonical_name,
            category=self.category,
            description=self.description,
            first_appearance_node_id=self.first_appearance_node_id,
            importance=self.importance,
            status=self.status,
            source=self.source,
        )
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'SettingData':
        """从 ORM 对象创建 DTO"""
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            setting_type=orm_obj.setting_type,
            canonical_name=orm_obj.canonical_name,
            category=orm_obj.category,
            description=orm_obj.description,
            first_appearance_node_id=orm_obj.first_appearance_node_id,
            importance=orm_obj.importance or "normal",
            status=orm_obj.status or "draft",
            source=orm_obj.source or "manual",
            attributes=[SettingAttributeData.read_from_orm(a) for a in orm_obj.attributes] if hasattr(orm_obj, 'attributes') else [],
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at,
        )


@dataclass
class SettingAttributeData:
    """设定属性数据 DTO"""
    id: Optional[int] = None
    setting_id: int = 0
    attr_key: str = ""
    attr_value: str = ""
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'SettingAttributeData':
        return cls(
            id=orm_obj.id,
            setting_id=orm_obj.setting_id,
            attr_key=orm_obj.attr_key,
            attr_value=orm_obj.attr_value,
            source=orm_obj.source or "manual",
            source_node_id=orm_obj.source_node_id,
            status=orm_obj.status or "pending",
            created_at=orm_obj.created_at,
        )


@dataclass
class SettingRelationData:
    """设定关系数据 DTO"""
    id: Optional[int] = None
    edition_id: int = 0
    source_setting_id: int = 0
    target_setting_id: int = 0
    relation_type: str = ""  # contains, belongs_to, produces, requires, opposes
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'SettingRelationData':
        return cls(
            id=orm_obj.id,
            edition_id=orm_obj.edition_id,
            source_setting_id=orm_obj.source_setting_id,
            target_setting_id=orm_obj.target_setting_id,
            relation_type=orm_obj.relation_type,
            description=orm_obj.description,
            created_at=orm_obj.created_at,
        )


@dataclass
class CharacterSettingLinkData:
    """人物设定关联数据 DTO"""
    id: Optional[int] = None
    character_id: int = 0
    setting_id: int = 0
    link_type: str = "owner"  # owner, user, creator, victim, other
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def read_from_orm(cls, orm_obj) -> 'CharacterSettingLinkData':
        return cls(
            id=orm_obj.id,
            character_id=orm_obj.character_id,
            setting_id=orm_obj.setting_id,
            link_type=orm_obj.link_type,
            description=orm_obj.description,
            created_at=orm_obj.created_at,
        )


@dataclass
class SettingDetail:
    """设定详情"""
    setting: SettingData
    attributes: List[SettingAttributeData]
    related_settings: List[SettingRelationData]
    related_characters: List[CharacterSettingLinkData]


# ============================================================================
# Setting Extraction Types
# ============================================================================

@dataclass
class SettingExtractionConfig:
    """设定提取配置"""
    setting_types: List[str] = field(default_factory=lambda: [
        "item", "location", "organization", "concept", "magic_system", "creature", "event_type"
    ])
    min_importance: str = "background"  # critical, major, minor, background
    extract_relations: bool = True
    extract_attributes: bool = True
    max_settings: int = 100
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "setting_extraction_v1"


@dataclass
class SettingExtractionRequest:
    """设定提取请求"""
    edition_id: int
    range_selection: TextRangeSelection
    config: SettingExtractionConfig = field(default_factory=SettingExtractionConfig)
    work_title: str = ""
    known_settings: List[str] = field(default_factory=list)


@dataclass
class ExtractedSettingAttribute:
    """提取的设定属性"""
    key: str
    value: str
    description: Optional[str] = None


@dataclass
class ExtractedSettingRelation:
    """提取的设定关系"""
    target_name: str
    relation_type: str  # contains, belongs_to, produces, requires, opposes
    description: Optional[str] = None


@dataclass
class ExtractedSetting:
    """提取的设定"""
    canonical_name: str
    setting_type: str  # item, location, organization, concept, magic_system, creature, event_type
    category: str = ""
    importance: str = "minor"  # critical, major, minor, background
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[ExtractedSettingAttribute] = field(default_factory=list)
    relations: List[ExtractedSettingRelation] = field(default_factory=list)
    key_scenes: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class SettingExtractionResult:
    """设定提取结果"""
    settings: List[ExtractedSetting]
    metadata: Dict[str, Any]
    raw_response: Optional[str] = None


@dataclass
class SettingExtractionResponse:
    """设定提取响应"""
    success: bool
    task_id: Optional[str] = None
    result: Optional[SettingExtractionResult] = None
    message: str = ""
    error: Optional[str] = None


# ============================================================================
# Character Detection Types
# ============================================================================

@dataclass
class CharacterDetectionConfig:
    """人物检测配置"""
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
    """人物检测请求"""
    edition_id: int
    range_selection: TextRangeSelection
    config: CharacterDetectionConfig = field(default_factory=CharacterDetectionConfig)
    work_title: str = ""
    known_characters: List[str] = field(default_factory=list)


@dataclass
class DetectedCharacterAlias:
    """检测到的别名"""
    alias: str
    alias_type: str = "other"  # nickname, title, courtesy_name, other


@dataclass
class DetectedCharacterAttribute:
    """检测到的属性"""
    category: str  # appearance, personality, ability, background, relationship
    key: str
    value: str
    confidence: Optional[float] = None
    source_text: Optional[str] = None


@dataclass
class DetectedCharacterRelation:
    """检测到的人物关系"""
    target_name: str
    relation_type: str  # family, friend, enemy, romantic, professional, other
    description: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class DetectedCharacter:
    """检测到的人物"""
    canonical_name: str
    aliases: List[DetectedCharacterAlias] = field(default_factory=list)
    role_type: str = "supporting"  # protagonist, deuteragonist, supporting, minor, mentioned
    role_confidence: float = 0.5
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[DetectedCharacterAttribute] = field(default_factory=list)
    relations: List[DetectedCharacterRelation] = field(default_factory=list)
    key_actions: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class CharacterDetectionResult:
    """人物检测结果"""
    characters: List[DetectedCharacter]
    metadata: Dict[str, Any]
    raw_response: Optional[str] = None


@dataclass
class CharacterDetectionResponse:
    """人物检测响应"""
    success: bool
    task_id: Optional[str] = None
    result: Optional[CharacterDetectionResult] = None
    message: str = ""
    error: Optional[str] = None


@dataclass
class CharacterMergeCandidate:
    """人物合并候选"""
    character1_id: int
    character2_id: int
    character1_name: str
    character2_name: str
    similarity_score: float
    merge_reason: str
    suggested_action: str  # merge, review, ignore


@dataclass
class CharacterDeduplicationResult:
    """人物去重结果"""
    merged_groups: List[List[int]]
    merge_candidates: List[CharacterMergeCandidate]
    statistics: Dict[str, Any]


# ============================================================================
# SQLAlchemy ORM Imports
# ============================================================================

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Float, Boolean
)
from sqlalchemy.orm import relationship
from sail_server.data.orm import ORMBase

# ============================================================================
# ORM Model Classes
# ============================================================================

class Outline(ORMBase):
    """大纲 ORM 模型"""
    __tablename__ = "outlines"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    outline_type = Column(String, nullable=False, default="main")
    description = Column(Text, nullable=True)
    status = Column(String, nullable=True, default="draft")
    source = Column(String, nullable=True, default="manual")
    meta_data = Column(JSONB, default={})
    created_by = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    nodes = relationship("OutlineNode", back_populates="outline", cascade="all, delete-orphan")


class OutlineNode(ORMBase):
    """大纲节点 ORM 模型"""
    __tablename__ = "outline_nodes"
    
    id = Column(Integer, primary_key=True)
    outline_id = Column(Integer, ForeignKey("outlines.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=True)
    node_type = Column(String, nullable=False, default="chapter")
    sort_index = Column(Integer, nullable=False, default=0)
    depth = Column(Integer, nullable=False, default=0)
    path = Column(String, nullable=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    significance = Column(String, nullable=True, default="normal")
    chapter_start_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    chapter_end_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    outline = relationship("Outline", back_populates="nodes")
    events = relationship("OutlineEvent", back_populates="node", cascade="all, delete-orphan")


class OutlineEvent(ORMBase):
    """大纲事件 ORM 模型"""
    __tablename__ = "outline_events"
    
    id = Column(Integer, primary_key=True)
    outline_node_id = Column(Integer, ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    chronology_order = Column(Float, nullable=True)
    narrative_order = Column(Integer, nullable=True)
    importance = Column(String, nullable=True, default="normal")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    node = relationship("OutlineNode", back_populates="events")


# ============================================================================
# Character ORM Models
# ============================================================================

class Character(ORMBase):
    """人物 ORM 模型"""
    __tablename__ = "characters"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    canonical_name = Column(String, nullable=False)
    role_type = Column(String, nullable=True, default="supporting")  # protagonist, antagonist, deuteragonist, supporting, minor
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    source = Column(String, nullable=True, default="manual")
    importance_score = Column(Float, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    aliases = relationship("CharacterAlias", back_populates="character", cascade="all, delete-orphan")
    attributes = relationship("CharacterAttribute", back_populates="character", cascade="all, delete-orphan")
    arcs = relationship("CharacterArc", back_populates="character", cascade="all, delete-orphan")


class CharacterAlias(ORMBase):
    """人物别名 ORM 模型"""
    __tablename__ = "character_aliases"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=False)
    alias_type = Column(String, nullable=True, default="nickname")  # nickname, title, formal, diminutive
    usage_context = Column(String, nullable=True)
    is_preferred = Column(Boolean, nullable=True, default=False)
    source = Column(String, nullable=True, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="aliases")


class CharacterAttribute(ORMBase):
    """人物属性 ORM 模型"""
    __tablename__ = "character_attributes"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=True)  # physical, personality, background, ability, etc.
    attr_key = Column(String, nullable=False)
    attr_value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True, default="manual")
    source_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="attributes")


class CharacterArc(ORMBase):
    """人物弧光 ORM 模型"""
    __tablename__ = "character_arcs"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    arc_type = Column(String, nullable=True)  # growth, fall, redemption, tragic, etc.
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    character = relationship("Character", back_populates="arcs")


class CharacterRelation(ORMBase):
    """人物关系 ORM 模型"""
    __tablename__ = "character_relations"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    source_character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    target_character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # family, friend, enemy, romantic, professional, etc.
    relation_subtype = Column(String, nullable=True)  # parent, sibling, spouse, etc.
    description = Column(Text, nullable=True)
    strength = Column(Float, nullable=True)  # 关系强度 0-1
    is_mutual = Column(Boolean, nullable=True, default=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# ============================================================================
# Setting ORM Models
# ============================================================================

class Setting(ORMBase):
    """设定 ORM 模型"""
    __tablename__ = "novel_settings"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    setting_type = Column(String, nullable=False)  # item, location, organization, concept, magic_system, creature, event_type
    canonical_name = Column(String, nullable=False)
    category = Column(String, nullable=True)  # 子分类
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    importance = Column(String, nullable=True, default="normal")  # critical, major, normal, minor
    status = Column(String, nullable=True, default="draft")
    source = Column(String, nullable=True, default="manual")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    attributes = relationship("SettingAttribute", back_populates="setting", cascade="all, delete-orphan")


class SettingAttribute(ORMBase):
    """设定属性 ORM 模型"""
    __tablename__ = "setting_attributes"
    
    id = Column(Integer, primary_key=True)
    setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    attr_key = Column(String, nullable=False)
    attr_value = Column(Text, nullable=False)
    source = Column(String, nullable=True, default="manual")
    source_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    status = Column(String, nullable=True, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # 关联
    setting = relationship("Setting", back_populates="attributes")


class SettingRelation(ORMBase):
    """设定关系 ORM 模型"""
    __tablename__ = "setting_relations"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    source_setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    target_setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # contains, belongs_to, produces, requires, opposes
    description = Column(Text, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class CharacterSettingLink(ORMBase):
    """人物-设定关联 ORM 模型"""
    __tablename__ = "character_setting_links"
    
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    setting_id = Column(Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False)
    link_type = Column(String, nullable=False)  # owns, belongs_to, created, uses, guards
    description = Column(Text, nullable=True)
    start_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    end_node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

class TextEvidence(ORMBase):
    """文本证据 ORM 模型"""
    __tablename__ = "text_evidence"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    node_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(String, nullable=False)  # outline_node | character | setting | etc.
    target_id = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    text_snippet = Column(Text, nullable=True)
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    evidence_type = Column(String, nullable=True, default="explicit")
    confidence = Column(Float, nullable=True)
    source = Column(String, nullable=True, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

@dataclass
class AnalysisTask:
    """分析任务 ORM 占位符"""
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
    """分析结果 ORM 占位符"""
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
