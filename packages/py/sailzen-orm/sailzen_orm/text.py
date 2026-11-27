# -*- coding: utf-8 -*-
# @file text.py
# @brief Text ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
文本模块 ORM 模型

从 sail_server/data/text.py 迁移
"""

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
    func,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sailzen_orm.orm_base import ORMBase
from sailzen_orm.types import JSONB


class Work(ORMBase):
    """
    作品表 - 代表一本书、长篇小说、论文或深度文章
    """

    __tablename__ = "works"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)  # 唯一标识符
    title = Column(String, nullable=False)
    original_title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    language_primary = Column(String, nullable=False, default="zh")
    # web_novel | book | paper | article | script | reference | novel | essay
    work_type = Column(String, default="web_novel")
    status = Column(String, default="ongoing")  # ongoing | completed | hiatus
    synopsis = Column(Text, nullable=True)
    # Content 2.0: 素养归属 / 阅读生命周期 / 轨道 / Vault 映射 / 原创标记
    # pillar: tech | history | aesthetics | fiction | general
    pillar = Column(String(32), default="fiction", server_default="fiction", index=True)
    # reading_status: inbox | queued | reading | paused | finished | dropped
    reading_status = Column(
        String(24), default="queued", server_default="queued", index=True
    )
    # reading_track: mainline | project | leisure
    reading_track = Column(
        String(24), default="leisure", server_default="leisure", index=True
    )
    priority = Column(Integer, default=3, server_default="3")
    source_url = Column(String(512), nullable=True)
    vault_slug = Column(String(128), nullable=True)
    is_original = Column(Boolean, default=False, server_default="false")
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    editions = relationship(
        "Edition", back_populates="work", cascade="all, delete-orphan"
    )


class Edition(ORMBase):
    """
    版本表 - 代表作品的一个具体版本/译本
    """

    __tablename__ = "editions"

    id = Column(Integer, primary_key=True)
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=False
    )
    edition_name = Column(String, nullable=True)
    language = Column(String, nullable=False, default="zh")
    source_format = Column(String, default="txt")
    canonical = Column(Boolean, default=False)
    source_path = Column(String, nullable=True)  # 原始文件路径
    source_checksum = Column(String, nullable=True)
    ingest_version = Column(Integer, default=1)
    word_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default="draft")  # draft | active | archived
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    work = relationship("Work", back_populates="editions")
    document_nodes = relationship(
        "DocumentNode", back_populates="edition", cascade="all, delete-orphan"
    )


class NoteItem(ORMBase):
    """
    笔记索引表 - 轻量级索引，实际内容由 workspace 下的 Markdown 文件承载

    category: character | setting | geography | outline | plot | history | person |
              timeline | relationship | misc
    """

    __tablename__ = "note_items"

    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False, index=True)
    setting_file = Column(String, nullable=False)  # relative to workspace root
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="SET NULL"), nullable=True
    )
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="SET NULL"), nullable=True
    )
    title = Column(String, nullable=True)  # 缓存，可选
    slug = Column(String, nullable=True, unique=True)  # URL/文件名友好标识
    meta_data = Column(JSONB, default={})  # 扩展字段，如 frontmatter 摘要
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class DocumentNode(ORMBase):
    """
    文档节点表 - 树形结构存储文本内容
    node_type: volume | part | chapter | section | paragraph
    """

    __tablename__ = "document_nodes"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    parent_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=True
    )
    node_type = Column(
        String, nullable=False
    )  # volume | part | chapter | section | paragraph
    sort_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False)
    label = Column(String, nullable=True)  # "第一章" 等显示标签
    title = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)  # 仅在文本节点填充
    word_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    path = Column(String, nullable=False)  # materialized path，如 "0001.0003"
    status = Column(String, default="active")  # active | deprecated | superseded
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    # 关联
    edition = relationship("Edition", back_populates="document_nodes")
    children = relationship(
        "DocumentNode", back_populates="parent", cascade="all, delete-orphan"
    )
    parent = relationship("DocumentNode", back_populates="children", remote_side=[id])

    __table_args__ = (
        Index("ix_doc_nodes_edition_type_sort", "edition_id", "node_type", "sort_index"),
        Index("ix_doc_nodes_edition_parent_sort", "edition_id", "parent_id", "sort_index"),
    )


class ReadingProgress(ORMBase):
    """云端权威阅读进度表（Web / Android / SailTick 共享）。"""

    __tablename__ = "reading_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, default=1, server_default="1", index=True)
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    sort_index = Column(Integer, nullable=False, default=0, server_default="0")
    char_offset = Column(Integer, nullable=False, default=0, server_default="0")
    scroll_offset = Column(Integer, nullable=False, default=0, server_default="0")
    page_index = Column(Integer, nullable=False, default=0, server_default="0")
    mode = Column(String(16), nullable=False, default="scroll", server_default="scroll")
    progress_pct = Column(Float, nullable=False, default=0.0, server_default="0")
    total_read_seconds = Column(Integer, nullable=False, default=0, server_default="0")
    client_device = Column(String(64), default="", server_default="")
    last_read_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "work_id", name="uq_reading_progress_user_work"),
    )


class ReadingSession(ORMBase):
    """轻量阅读会话日志（用于按素养/项目统计投入时长与活跃度）。"""

    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, default=1, server_default="1", index=True)
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    start_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    end_node_id = Column(
        Integer, ForeignKey("document_nodes.id", ondelete="SET NULL"), nullable=True
    )
    duration_sec = Column(Integer, nullable=False, default=0)
    chars_read = Column(Integer, nullable=False, default=0)
    source_client = Column(String(32), default="web", server_default="web")
    started_at = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    ended_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class ContentTopic(ORMBase):
    """研究专题 / 资料包（支持双向绑定 Rhythm Venture 与本地 D:\\vault 命名空间）。"""

    __tablename__ = "content_topics"

    id = Column(Integer, primary_key=True)
    slug = Column(String(128), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="", server_default="")
    # tech | history | aesthetics | fiction | interdisciplinary
    pillar = Column(String(32), default="tech", server_default="tech", index=True)
    # active | paused | completed | archived
    status = Column(String(24), default="active", server_default="active", index=True)
    # 逻辑引用 rhythm_affairs.id (kind='venture')
    rhythm_venture_id = Column(Integer, nullable=True, index=True)
    vault_prefix = Column(String(128), nullable=True)
    keywords = Column(JSONB, default=list)
    meta_data = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class ContentTopicWork(ORMBase):
    """专题与作品（书籍/论文/小说）的多对多关联表。"""

    __tablename__ = "content_topic_works"

    id = Column(Integer, primary_key=True)
    topic_id = Column(
        Integer,
        ForeignKey("content_topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_id = Column(
        Integer,
        ForeignKey("works.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # core | reference | background | inspiration
    role = Column(String(24), default="core", server_default="core")
    sort_index = Column(Integer, default=0, server_default="0")
    note = Column(Text, default="", server_default="")
    added_at = Column(TIMESTAMP, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("topic_id", "work_id", name="uq_content_topic_work"),
    )


class ContentAsset(ORMBase):
    """内容附件表（论文 PDF 原件、EPUB 源文件、插图与审美参考图）。"""

    __tablename__ = "content_assets"

    id = Column(Integer, primary_key=True)
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=True, index=True
    )
    topic_id = Column(
        Integer,
        ForeignKey("content_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # pdf_source | epub_source | figure | moodboard | attachment
    asset_kind = Column(String(32), default="attachment", server_default="attachment")
    storage_key = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), default="")
    meta_data = Column(JSONB, default=dict)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class VaultNoteIndex(ORMBase):
    """D:\\vault 内容笔记轻量只读索引（read.* / topic.* / study.*）。"""

    __tablename__ = "vault_note_index"

    id = Column(Integer, primary_key=True)
    fname = Column(String(200), unique=True, nullable=False, index=True)
    # read | topic | study | other
    namespace = Column(String(32), default="read", server_default="read", index=True)
    title = Column(String(255), default="")
    summary = Column(Text, default="")
    tags = Column(JSONB, default=list)
    links = Column(JSONB, default=list)
    work_id = Column(
        Integer, ForeignKey("works.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic_id = Column(
        Integer,
        ForeignKey("content_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pillar = Column(String(32), nullable=True, index=True)
    era = Column(String(64), nullable=True)
    year_start = Column(Integer, nullable=True, index=True)
    year_end = Column(Integer, nullable=True)
    content_hash = Column(String(64), default="", index=True)
    source_vault = Column(String(64), default="local")
    synced_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
