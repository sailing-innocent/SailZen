# -*- coding: utf-8 -*-
# @file analysis.py
# @brief Novel Analysis Data Models - ORM and DTOs
# @author sailing-innocent
# @date 2025-02-01
# @version 1.0
# ---------------------------------
#
# 基于 doc/design/manager/novel_analyse.md 的实现
# 实现大纲、人物、设定分析功能的数据模型
#

from sqlalchemy import (
    Column,
    Integer,
    String,
    TIMESTAMP,
    func,
    Text,
    Boolean,
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from .orm import ORMBase
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


# ============================================================================
# ORM Models - Outline
# ============================================================================


class Outline(ORMBase):
    """
    大纲表 - 存储作品的各类大纲结构
    """

    __tablename__ = "outlines"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    outline_type = Column(
        String, nullable=False, default="main"
    )  # main | subplot | character_arc
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft | analyzing | reviewed | finalized
    source = Column(String, default="manual")  # manual | ai_generated | hybrid
    meta_data = Column(JSONB, default={})
    created_by = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    nodes = relationship(
        "OutlineNode", back_populates="outline", cascade="all, delete-orphan"
    )


class OutlineNode(ORMBase):
    """
    大纲节点表 - 树形结构表示情节层级
    """

    __tablename__ = "outline_nodes"

    id = Column(Integer, primary_key=True)
    outline_id = Column(
        Integer, ForeignKey("outlines.id", ondelete="CASCADE"), nullable=False
    )
    parent_id = Column(
        Integer, ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=True
    )
    node_type = Column(
        String, nullable=False
    )  # act | arc | beat | scene | turning_point
    sort_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False, default=0)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    significance = Column(String, default="normal")  # critical | major | normal | minor
    chapter_start_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    chapter_end_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    path = Column(String, nullable=False)
    status = Column(String, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    outline = relationship("Outline", back_populates="nodes")
    children = relationship(
        "OutlineNode", back_populates="parent", cascade="all, delete-orphan"
    )
    parent = relationship("OutlineNode", back_populates="children", remote_side=[id])
    events = relationship(
        "OutlineEvent", back_populates="node", cascade="all, delete-orphan"
    )


class OutlineEvent(ORMBase):
    """
    大纲事件表 - 记录情节中的关键事件
    """

    __tablename__ = "outline_events"

    id = Column(Integer, primary_key=True)
    outline_node_id = Column(
        Integer, ForeignKey("outline_nodes.id", ondelete="CASCADE"), nullable=False
    )
    event_type = Column(
        String, nullable=False
    )  # plot | conflict | revelation | resolution | climax
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    chronology_order = Column(Numeric(10, 2), nullable=True)
    narrative_order = Column(Integer, nullable=True)
    importance = Column(String, default="normal")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    node = relationship("OutlineNode", back_populates="events")


# ============================================================================
# ORM Models - Character
# ============================================================================


class Character(ORMBase):
    """
    人物表 - 存储作品中的人物信息
    """

    __tablename__ = "characters"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    canonical_name = Column(String, nullable=False)
    role_type = Column(
        String, default="supporting"
    )  # protagonist | antagonist | deuteragonist | supporting | minor | mentioned
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, default="draft")
    source = Column(String, default="manual")
    importance_score = Column(Numeric(5, 4), nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    aliases = relationship(
        "CharacterAlias", back_populates="character", cascade="all, delete-orphan"
    )
    attributes = relationship(
        "CharacterAttribute", back_populates="character", cascade="all, delete-orphan"
    )
    arcs = relationship(
        "CharacterArc", back_populates="character", cascade="all, delete-orphan"
    )
    setting_links = relationship(
        "CharacterSettingLink", back_populates="character", cascade="all, delete-orphan"
    )


class CharacterAlias(ORMBase):
    """
    人物别名表 - 存储人物的各种称呼
    """

    __tablename__ = "character_aliases"

    id = Column(Integer, primary_key=True)
    character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    alias = Column(String, nullable=False)
    alias_type = Column(
        String, default="nickname"
    )  # nickname | title | formal_name | pen_name | code_name
    usage_context = Column(Text, nullable=True)
    is_preferred = Column(Boolean, default=False)
    source = Column(String, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    character = relationship("Character", back_populates="aliases")


class CharacterAttribute(ORMBase):
    """
    人物属性表 - 存储人物的各类属性
    """

    __tablename__ = "character_attributes"

    id = Column(Integer, primary_key=True)
    character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    category = Column(
        String, nullable=False
    )  # basic | appearance | personality | ability | background | goal
    attr_key = Column(String, nullable=False)
    attr_value = Column(JSONB, nullable=False)
    confidence = Column(Numeric(5, 4), nullable=True)
    source = Column(String, default="manual")
    source_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    character = relationship("Character", back_populates="attributes")


class CharacterArc(ORMBase):
    """
    人物弧线表 - 记录人物的成长变化轨迹
    """

    __tablename__ = "character_arcs"

    id = Column(Integer, primary_key=True)
    character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    arc_type = Column(
        String, nullable=False
    )  # growth | fall | flat | transformation | redemption
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    end_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    character = relationship("Character", back_populates="arcs")


class CharacterRelation(ORMBase):
    """
    人物关系表 - 存储人物之间的关系
    """

    __tablename__ = "character_relations"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    source_character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    target_character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(
        String, nullable=False
    )  # family | romance | friendship | rivalry | mentor | alliance | enemy
    relation_subtype = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    strength = Column(Numeric(5, 4), nullable=True)
    is_mutual = Column(Boolean, default=True)
    start_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    end_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, default="draft")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    source_character = relationship("Character", foreign_keys=[source_character_id])
    target_character = relationship("Character", foreign_keys=[target_character_id])


# ============================================================================
# ORM Models - Setting
# ============================================================================


class Setting(ORMBase):
    """
    设定表 - 存储世界观设定元素
    """

    __tablename__ = "novel_settings"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    setting_type = Column(
        String, nullable=False
    )  # item | location | organization | concept | magic_system | creature
    canonical_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    first_appearance_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    importance = Column(String, default="normal")
    status = Column(String, default="draft")
    source = Column(String, default="manual")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    attributes = relationship(
        "SettingAttribute", back_populates="setting", cascade="all, delete-orphan"
    )
    character_links = relationship(
        "CharacterSettingLink", back_populates="setting", cascade="all, delete-orphan"
    )


class SettingAttribute(ORMBase):
    """
    设定属性表 - 存储设定的详细属性
    """

    __tablename__ = "setting_attributes"

    id = Column(Integer, primary_key=True)
    setting_id = Column(
        Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False
    )
    attr_key = Column(String, nullable=False)
    attr_value = Column(JSONB, nullable=False)
    source = Column(String, default="manual")
    source_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String, default="pending")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    setting = relationship("Setting", back_populates="attributes")


class SettingRelation(ORMBase):
    """
    设定关系表 - 存储设定之间的关系
    """

    __tablename__ = "setting_relations"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    source_setting_id = Column(
        Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False
    )
    target_setting_id = Column(
        Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False
    )
    relation_type = Column(
        String, nullable=False
    )  # contains | belongs_to | produces | requires | opposes
    description = Column(Text, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    source_setting = relationship("Setting", foreign_keys=[source_setting_id])
    target_setting = relationship("Setting", foreign_keys=[target_setting_id])


class CharacterSettingLink(ORMBase):
    """
    人物-设定关联表 - 记录人物与设定的关系
    """

    __tablename__ = "character_setting_links"

    id = Column(Integer, primary_key=True)
    character_id = Column(
        Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    setting_id = Column(
        Integer, ForeignKey("novel_settings.id", ondelete="CASCADE"), nullable=False
    )
    link_type = Column(
        String, nullable=False
    )  # owns | belongs_to | created | uses | guards
    description = Column(Text, nullable=True)
    start_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    end_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    character = relationship("Character", back_populates="setting_links")
    setting = relationship("Setting", back_populates="character_links")


# ============================================================================
# ORM Models - Analysis Task
# ============================================================================


class TextEvidence(ORMBase):
    """
    文本证据表 - 存储分析结果的原文依据
    """

    __tablename__ = "text_evidence"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=False
    )
    target_type = Column(
        String, nullable=False
    )  # outline_node | character | character_attribute | setting | relation
    target_id = Column(Integer, nullable=False)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    text_snippet = Column(Text, nullable=True)
    context_before = Column(Text, nullable=True)
    context_after = Column(Text, nullable=True)
    evidence_type = Column(String, default="explicit")  # explicit | implicit | inferred
    confidence = Column(Numeric(5, 4), nullable=True)
    source = Column(String, default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class AnalysisTask(ORMBase):
    """
    分析任务表 - 管理AI分析和人工标注任务
    """

    __tablename__ = "analysis_tasks"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    task_type = Column(
        String, nullable=False
    )  # outline_extraction | character_detection | setting_extraction | relation_analysis
    target_scope = Column(String, nullable=False)  # full | range | chapter
    target_node_ids = Column(ARRAY(Integer), default=[])
    parameters = Column(JSONB, default={})
    llm_model = Column(String, nullable=True)
    llm_prompt_template = Column(String, nullable=True)
    status = Column(
        String, default="pending"
    )  # pending | running | completed | failed | cancelled
    priority = Column(Integer, default=0)
    scheduled_at = Column(TIMESTAMP, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    result_summary = Column(JSONB, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    results = relationship(
        "AnalysisResult", back_populates="task", cascade="all, delete-orphan"
    )


class AnalysisResult(ORMBase):
    """
    分析结果表 - 存储待审核的分析结果
    """

    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True)
    task_id = Column(
        Integer, ForeignKey("analysis_tasks.id", ondelete="CASCADE"), nullable=False
    )
    result_type = Column(String, nullable=False)
    result_data = Column(JSONB, nullable=False)
    confidence = Column(Numeric(5, 4), nullable=True)
    review_status = Column(
        String, default="pending"
    )  # pending | approved | rejected | modified
    reviewer = Column(String, nullable=True)
    reviewed_at = Column(TIMESTAMP, nullable=True)
    review_notes = Column(Text, nullable=True)
    applied = Column(Boolean, default=False)
    applied_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    # 关联
    task = relationship("AnalysisTask", back_populates="results")


# ============================================================================
# Data Transfer Objects - Outline
# ============================================================================


@dataclass
class OutlineData:
    """大纲数据传输对象"""

    edition_id: int
    title: str
    id: int = field(default=-1)
    outline_type: str = "main"
    description: Optional[str] = None
    status: str = "draft"
    source: str = "manual"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    node_count: int = 0

    @classmethod
    def read_from_orm(cls, orm: Outline, node_count: int = 0):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            title=orm.title,
            outline_type=orm.outline_type,
            description=orm.description,
            status=orm.status,
            source=orm.source,
            meta_data=orm.meta_data or {},
            created_by=orm.created_by,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            node_count=node_count,
        )

    def create_orm(self) -> Outline:
        return Outline(
            edition_id=self.edition_id,
            title=self.title,
            outline_type=self.outline_type,
            description=self.description,
            status=self.status,
            source=self.source,
            meta_data=self.meta_data,
            created_by=self.created_by,
        )

    def update_orm(self, orm: Outline):
        orm.title = self.title
        orm.outline_type = self.outline_type
        orm.description = self.description
        orm.status = self.status
        orm.source = self.source
        orm.meta_data = self.meta_data


@dataclass
class OutlineNodeData:
    """大纲节点数据传输对象"""

    outline_id: int
    node_type: str
    sort_index: int
    title: str
    path: str
    id: int = field(default=-1)
    parent_id: Optional[int] = None
    depth: int = 0
    summary: Optional[str] = None
    significance: str = "normal"
    chapter_start_id: Optional[int] = None
    chapter_end_id: Optional[int] = None
    status: str = "draft"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    children_count: int = 0
    events_count: int = 0

    @classmethod
    def read_from_orm(
        cls, orm: OutlineNode, children_count: int = 0, events_count: int = 0
    ):
        return cls(
            id=orm.id,
            outline_id=orm.outline_id,
            parent_id=orm.parent_id,
            node_type=orm.node_type,
            sort_index=orm.sort_index,
            depth=orm.depth,
            title=orm.title,
            summary=orm.summary,
            significance=orm.significance,
            chapter_start_id=orm.chapter_start_id,
            chapter_end_id=orm.chapter_end_id,
            path=orm.path,
            status=orm.status,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            children_count=children_count,
            events_count=events_count,
        )

    def create_orm(self) -> OutlineNode:
        return OutlineNode(
            outline_id=self.outline_id,
            parent_id=self.parent_id,
            node_type=self.node_type,
            sort_index=self.sort_index,
            depth=self.depth,
            title=self.title,
            summary=self.summary,
            significance=self.significance,
            chapter_start_id=self.chapter_start_id,
            chapter_end_id=self.chapter_end_id,
            path=self.path,
            status=self.status,
            meta_data=self.meta_data,
        )

    def update_orm(self, orm: OutlineNode):
        orm.parent_id = self.parent_id
        orm.node_type = self.node_type
        orm.sort_index = self.sort_index
        orm.depth = self.depth
        orm.title = self.title
        orm.summary = self.summary
        orm.significance = self.significance
        orm.chapter_start_id = self.chapter_start_id
        orm.chapter_end_id = self.chapter_end_id
        orm.path = self.path
        orm.status = self.status
        orm.meta_data = self.meta_data


@dataclass
class OutlineEventData:
    """大纲事件数据传输对象"""

    outline_node_id: int
    event_type: str
    title: str
    id: int = field(default=-1)
    description: Optional[str] = None
    chronology_order: Optional[float] = None
    narrative_order: Optional[int] = None
    importance: str = "normal"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: OutlineEvent):
        return cls(
            id=orm.id,
            outline_node_id=orm.outline_node_id,
            event_type=orm.event_type,
            title=orm.title,
            description=orm.description,
            chronology_order=float(orm.chronology_order)
            if orm.chronology_order
            else None,
            narrative_order=orm.narrative_order,
            importance=orm.importance,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
        )

    def create_orm(self) -> OutlineEvent:
        return OutlineEvent(
            outline_node_id=self.outline_node_id,
            event_type=self.event_type,
            title=self.title,
            description=self.description,
            chronology_order=self.chronology_order,
            narrative_order=self.narrative_order,
            importance=self.importance,
            meta_data=self.meta_data,
        )


# ============================================================================
# Data Transfer Objects - Character
# ============================================================================


@dataclass
class CharacterData:
    """人物数据传输对象"""

    edition_id: int
    canonical_name: str
    id: int = field(default=-1)
    role_type: str = "supporting"
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    status: str = "draft"
    source: str = "manual"
    importance_score: Optional[float] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    alias_count: int = 0
    attribute_count: int = 0
    relation_count: int = 0

    @classmethod
    def read_from_orm(
        cls,
        orm: Character,
        alias_count: int = 0,
        attribute_count: int = 0,
        relation_count: int = 0,
    ):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            canonical_name=orm.canonical_name,
            role_type=orm.role_type,
            description=orm.description,
            first_appearance_node_id=orm.first_appearance_node_id,
            status=orm.status,
            source=orm.source,
            importance_score=float(orm.importance_score)
            if orm.importance_score
            else None,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            alias_count=alias_count,
            attribute_count=attribute_count,
            relation_count=relation_count,
        )

    def create_orm(self) -> Character:
        return Character(
            edition_id=self.edition_id,
            canonical_name=self.canonical_name,
            role_type=self.role_type,
            description=self.description,
            first_appearance_node_id=self.first_appearance_node_id,
            status=self.status,
            source=self.source,
            importance_score=self.importance_score,
            meta_data=self.meta_data,
        )

    def update_orm(self, orm: Character):
        orm.canonical_name = self.canonical_name
        orm.role_type = self.role_type
        orm.description = self.description
        orm.first_appearance_node_id = self.first_appearance_node_id
        orm.status = self.status
        orm.source = self.source
        orm.importance_score = self.importance_score
        orm.meta_data = self.meta_data


@dataclass
class CharacterAliasData:
    """人物别名数据传输对象"""

    character_id: int
    alias: str
    id: int = field(default=-1)
    alias_type: str = "nickname"
    usage_context: Optional[str] = None
    is_preferred: bool = False
    source: str = "manual"
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: CharacterAlias):
        return cls(
            id=orm.id,
            character_id=orm.character_id,
            alias=orm.alias,
            alias_type=orm.alias_type,
            usage_context=orm.usage_context,
            is_preferred=orm.is_preferred,
            source=orm.source,
            created_at=orm.created_at,
        )

    def create_orm(self) -> CharacterAlias:
        return CharacterAlias(
            character_id=self.character_id,
            alias=self.alias,
            alias_type=self.alias_type,
            usage_context=self.usage_context,
            is_preferred=self.is_preferred,
            source=self.source,
        )


@dataclass
class CharacterAttributeData:
    """人物属性数据传输对象"""

    character_id: int
    category: str
    attr_key: str
    attr_value: Any
    id: int = field(default=-1)
    confidence: Optional[float] = None
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: CharacterAttribute):
        return cls(
            id=orm.id,
            character_id=orm.character_id,
            category=orm.category,
            attr_key=orm.attr_key,
            attr_value=orm.attr_value,
            confidence=float(orm.confidence) if orm.confidence else None,
            source=orm.source,
            source_node_id=orm.source_node_id,
            status=orm.status,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    def create_orm(self) -> CharacterAttribute:
        return CharacterAttribute(
            character_id=self.character_id,
            category=self.category,
            attr_key=self.attr_key,
            attr_value=self.attr_value,
            confidence=self.confidence,
            source=self.source,
            source_node_id=self.source_node_id,
            status=self.status,
        )

    def update_orm(self, orm: CharacterAttribute):
        orm.attr_value = self.attr_value
        orm.confidence = self.confidence
        orm.status = self.status


@dataclass
class CharacterArcData:
    """人物弧线数据传输对象"""

    character_id: int
    arc_type: str
    title: str
    id: int = field(default=-1)
    description: Optional[str] = None
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    status: str = "draft"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: CharacterArc):
        return cls(
            id=orm.id,
            character_id=orm.character_id,
            arc_type=orm.arc_type,
            title=orm.title,
            description=orm.description,
            start_node_id=orm.start_node_id,
            end_node_id=orm.end_node_id,
            status=orm.status,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
        )

    def create_orm(self) -> CharacterArc:
        return CharacterArc(
            character_id=self.character_id,
            arc_type=self.arc_type,
            title=self.title,
            description=self.description,
            start_node_id=self.start_node_id,
            end_node_id=self.end_node_id,
            status=self.status,
            meta_data=self.meta_data,
        )


@dataclass
class CharacterRelationData:
    """人物关系数据传输对象"""

    edition_id: int
    source_character_id: int
    target_character_id: int
    relation_type: str
    id: int = field(default=-1)
    relation_subtype: Optional[str] = None
    description: Optional[str] = None
    strength: Optional[float] = None
    is_mutual: bool = True
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    status: str = "draft"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 关联的人物名称（用于展示）
    source_character_name: Optional[str] = None
    target_character_name: Optional[str] = None

    @classmethod
    def read_from_orm(
        cls, orm: CharacterRelation, source_name: str = None, target_name: str = None
    ):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            source_character_id=orm.source_character_id,
            target_character_id=orm.target_character_id,
            relation_type=orm.relation_type,
            relation_subtype=orm.relation_subtype,
            description=orm.description,
            strength=float(orm.strength) if orm.strength else None,
            is_mutual=orm.is_mutual,
            start_node_id=orm.start_node_id,
            end_node_id=orm.end_node_id,
            status=orm.status,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            source_character_name=source_name,
            target_character_name=target_name,
        )

    def create_orm(self) -> CharacterRelation:
        return CharacterRelation(
            edition_id=self.edition_id,
            source_character_id=self.source_character_id,
            target_character_id=self.target_character_id,
            relation_type=self.relation_type,
            relation_subtype=self.relation_subtype,
            description=self.description,
            strength=self.strength,
            is_mutual=self.is_mutual,
            start_node_id=self.start_node_id,
            end_node_id=self.end_node_id,
            status=self.status,
            meta_data=self.meta_data,
        )

    def update_orm(self, orm: CharacterRelation):
        orm.relation_type = self.relation_type
        orm.relation_subtype = self.relation_subtype
        orm.description = self.description
        orm.strength = self.strength
        orm.is_mutual = self.is_mutual
        orm.start_node_id = self.start_node_id
        orm.end_node_id = self.end_node_id
        orm.status = self.status
        orm.meta_data = self.meta_data


# ============================================================================
# Data Transfer Objects - Setting
# ============================================================================


@dataclass
class SettingData:
    """设定数据传输对象"""

    edition_id: int
    setting_type: str
    canonical_name: str
    id: int = field(default=-1)
    category: Optional[str] = None
    description: Optional[str] = None
    first_appearance_node_id: Optional[int] = None
    importance: str = "normal"
    status: str = "draft"
    source: str = "manual"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    attribute_count: int = 0
    character_link_count: int = 0

    @classmethod
    def read_from_orm(
        cls, orm: Setting, attribute_count: int = 0, character_link_count: int = 0
    ):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            setting_type=orm.setting_type,
            canonical_name=orm.canonical_name,
            category=orm.category,
            description=orm.description,
            first_appearance_node_id=orm.first_appearance_node_id,
            importance=orm.importance,
            status=orm.status,
            source=orm.source,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            attribute_count=attribute_count,
            character_link_count=character_link_count,
        )

    def create_orm(self) -> Setting:
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
            meta_data=self.meta_data,
        )

    def update_orm(self, orm: Setting):
        orm.setting_type = self.setting_type
        orm.canonical_name = self.canonical_name
        orm.category = self.category
        orm.description = self.description
        orm.first_appearance_node_id = self.first_appearance_node_id
        orm.importance = self.importance
        orm.status = self.status
        orm.source = self.source
        orm.meta_data = self.meta_data


@dataclass
class SettingAttributeData:
    """设定属性数据传输对象"""

    setting_id: int
    attr_key: str
    attr_value: Any
    id: int = field(default=-1)
    source: str = "manual"
    source_node_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: SettingAttribute):
        return cls(
            id=orm.id,
            setting_id=orm.setting_id,
            attr_key=orm.attr_key,
            attr_value=orm.attr_value,
            source=orm.source,
            source_node_id=orm.source_node_id,
            status=orm.status,
            created_at=orm.created_at,
        )

    def create_orm(self) -> SettingAttribute:
        return SettingAttribute(
            setting_id=self.setting_id,
            attr_key=self.attr_key,
            attr_value=self.attr_value,
            source=self.source,
            source_node_id=self.source_node_id,
            status=self.status,
        )


@dataclass
class SettingRelationData:
    """设定关系数据传输对象"""

    edition_id: int
    source_setting_id: int
    target_setting_id: int
    relation_type: str
    id: int = field(default=-1)
    description: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    # 关联的设定名称（用于展示）
    source_setting_name: Optional[str] = None
    target_setting_name: Optional[str] = None

    @classmethod
    def read_from_orm(
        cls, orm: SettingRelation, source_name: str = None, target_name: str = None
    ):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            source_setting_id=orm.source_setting_id,
            target_setting_id=orm.target_setting_id,
            relation_type=orm.relation_type,
            description=orm.description,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            source_setting_name=source_name,
            target_setting_name=target_name,
        )

    def create_orm(self) -> SettingRelation:
        return SettingRelation(
            edition_id=self.edition_id,
            source_setting_id=self.source_setting_id,
            target_setting_id=self.target_setting_id,
            relation_type=self.relation_type,
            description=self.description,
            meta_data=self.meta_data,
        )


@dataclass
class CharacterSettingLinkData:
    """人物-设定关联数据传输对象"""

    character_id: int
    setting_id: int
    link_type: str
    id: int = field(default=-1)
    description: Optional[str] = None
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    # 关联名称（用于展示）
    character_name: Optional[str] = None
    setting_name: Optional[str] = None

    @classmethod
    def read_from_orm(
        cls,
        orm: CharacterSettingLink,
        character_name: str = None,
        setting_name: str = None,
    ):
        return cls(
            id=orm.id,
            character_id=orm.character_id,
            setting_id=orm.setting_id,
            link_type=orm.link_type,
            description=orm.description,
            start_node_id=orm.start_node_id,
            end_node_id=orm.end_node_id,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            character_name=character_name,
            setting_name=setting_name,
        )

    def create_orm(self) -> CharacterSettingLink:
        return CharacterSettingLink(
            character_id=self.character_id,
            setting_id=self.setting_id,
            link_type=self.link_type,
            description=self.description,
            start_node_id=self.start_node_id,
            end_node_id=self.end_node_id,
            meta_data=self.meta_data,
        )


# ============================================================================
# Data Transfer Objects - Analysis Task
# ============================================================================


@dataclass
class TextEvidenceData:
    """文本证据数据传输对象"""

    edition_id: int
    node_id: int
    target_type: str
    target_id: int
    id: int = field(default=-1)
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    text_snippet: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    evidence_type: str = "explicit"
    confidence: Optional[float] = None
    source: str = "manual"
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: TextEvidence):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            node_id=orm.node_id,
            target_type=orm.target_type,
            target_id=orm.target_id,
            start_char=orm.start_char,
            end_char=orm.end_char,
            text_snippet=orm.text_snippet,
            context_before=orm.context_before,
            context_after=orm.context_after,
            evidence_type=orm.evidence_type,
            confidence=float(orm.confidence) if orm.confidence else None,
            source=orm.source,
            created_at=orm.created_at,
        )

    def create_orm(self) -> TextEvidence:
        return TextEvidence(
            edition_id=self.edition_id,
            node_id=self.node_id,
            target_type=self.target_type,
            target_id=self.target_id,
            start_char=self.start_char,
            end_char=self.end_char,
            text_snippet=self.text_snippet,
            context_before=self.context_before,
            context_after=self.context_after,
            evidence_type=self.evidence_type,
            confidence=self.confidence,
            source=self.source,
        )


@dataclass
class AnalysisTaskData:
    """分析任务数据传输对象"""

    edition_id: int
    task_type: str
    target_scope: str
    id: int = field(default=-1)
    target_node_ids: List[int] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    llm_model: Optional[str] = None
    llm_prompt_template: Optional[str] = None
    status: str = "pending"
    priority: int = 0
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    result_count: int = 0

    @classmethod
    def read_from_orm(cls, orm: AnalysisTask, result_count: int = 0):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            task_type=orm.task_type,
            target_scope=orm.target_scope,
            target_node_ids=orm.target_node_ids or [],
            parameters=orm.parameters or {},
            llm_model=orm.llm_model,
            llm_prompt_template=orm.llm_prompt_template,
            status=orm.status,
            priority=orm.priority,
            scheduled_at=orm.scheduled_at,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            error_message=orm.error_message,
            result_summary=orm.result_summary,
            created_by=orm.created_by,
            created_at=orm.created_at,
            result_count=result_count,
        )

    def create_orm(self) -> AnalysisTask:
        return AnalysisTask(
            edition_id=self.edition_id,
            task_type=self.task_type,
            target_scope=self.target_scope,
            target_node_ids=self.target_node_ids,
            parameters=self.parameters,
            llm_model=self.llm_model,
            llm_prompt_template=self.llm_prompt_template,
            status=self.status,
            priority=self.priority,
            scheduled_at=self.scheduled_at,
            created_by=self.created_by,
        )

    def update_orm(self, orm: AnalysisTask):
        orm.status = self.status
        orm.priority = self.priority
        orm.scheduled_at = self.scheduled_at
        orm.started_at = self.started_at
        orm.completed_at = self.completed_at
        orm.error_message = self.error_message
        orm.result_summary = self.result_summary


@dataclass
class AnalysisResultData:
    """分析结果数据传输对象"""

    task_id: int
    result_type: str
    result_data: Dict[str, Any]
    id: int = field(default=-1)
    confidence: Optional[float] = None
    review_status: str = "pending"
    reviewer: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @classmethod
    def read_from_orm(cls, orm: AnalysisResult):
        return cls(
            id=orm.id,
            task_id=orm.task_id,
            result_type=orm.result_type,
            result_data=orm.result_data,
            confidence=float(orm.confidence) if orm.confidence else None,
            review_status=orm.review_status,
            reviewer=orm.reviewer,
            reviewed_at=orm.reviewed_at,
            review_notes=orm.review_notes,
            applied=orm.applied,
            applied_at=orm.applied_at,
            created_at=orm.created_at,
        )

    def create_orm(self) -> AnalysisResult:
        return AnalysisResult(
            task_id=self.task_id,
            result_type=self.result_type,
            result_data=self.result_data,
            confidence=self.confidence,
            review_status=self.review_status,
        )

    def update_orm(self, orm: AnalysisResult):
        orm.review_status = self.review_status
        orm.reviewer = self.reviewer
        orm.reviewed_at = self.reviewed_at
        orm.review_notes = self.review_notes
        orm.applied = self.applied
        orm.applied_at = self.applied_at


# ============================================================================
# Composite Data Types for API responses
# ============================================================================


@dataclass
class CharacterProfile:
    """人物完整档案"""

    character: CharacterData
    aliases: List[CharacterAliasData]
    attributes: Dict[str, List[CharacterAttributeData]]  # 按 category 分组
    arcs: List[CharacterArcData]
    relations: List[CharacterRelationData]
    setting_links: List[CharacterSettingLinkData]


@dataclass
class SettingDetail:
    """设定详情"""

    setting: SettingData
    attributes: List[SettingAttributeData]
    character_links: List[CharacterSettingLinkData]
    related_settings: List[SettingRelationData]


@dataclass
class OutlineTree:
    """大纲树结构"""

    outline: OutlineData
    nodes: List[Dict[str, Any]]  # 嵌套的树形结构


@dataclass
class RelationGraphData:
    """关系图数据（用于可视化）"""

    nodes: List[Dict[str, Any]]  # id, name, role_type, importance_score
    edges: List[Dict[str, Any]]  # source, target, relation_type, strength
