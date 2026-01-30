# -*- coding: utf-8 -*-
# @file text.py
# @brief The Text Content Data Storage (Simplified MVP)
# @author sailing-innocent
# @date 2025-01-29
# @version 1.0
# ---------------------------------
# 
# 基于 doc/design/manager/text.md 的简化实现
# 实现最小可行的文本管理功能：作品、版本、文档节点
#

from sqlalchemy import Column, Integer, String, TIMESTAMP, func, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, UUID
from sqlalchemy.orm import relationship
from .orm import ORMBase
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid


# ============================================================================
# ORM Models
# ============================================================================

class Work(ORMBase):
    """
    作品表 - 代表一本书或小说
    """
    __tablename__ = "works"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)  # 唯一标识符
    title = Column(String, nullable=False)
    original_title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    language_primary = Column(String, nullable=False, default='zh')
    work_type = Column(String, default='web_novel')  # web_novel | novel | essay
    status = Column(String, default='ongoing')  # ongoing | completed | hiatus
    synopsis = Column(Text, nullable=True)
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    editions = relationship("Edition", back_populates="work", cascade="all, delete-orphan")


class Edition(ORMBase):
    """
    版本表 - 代表作品的一个具体版本/译本
    """
    __tablename__ = "editions"
    
    id = Column(Integer, primary_key=True)
    work_id = Column(Integer, ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    edition_name = Column(String, nullable=True)
    language = Column(String, nullable=False, default='zh')
    source_format = Column(String, default='txt')
    canonical = Column(Boolean, default=False)
    source_path = Column(String, nullable=True)  # 原始文件路径
    source_checksum = Column(String, nullable=True)
    ingest_version = Column(Integer, default=1)
    word_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String, default='draft')  # draft | active | archived
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    work = relationship("Work", back_populates="editions")
    document_nodes = relationship("DocumentNode", back_populates="edition", cascade="all, delete-orphan")


class DocumentNode(ORMBase):
    """
    文档节点表 - 树形结构存储文本内容
    node_type: volume | part | chapter | section | paragraph
    """
    __tablename__ = "document_nodes"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=True)
    node_type = Column(String, nullable=False)  # volume | part | chapter | section | paragraph
    sort_index = Column(Integer, nullable=False)
    depth = Column(Integer, nullable=False)
    label = Column(String, nullable=True)  # "第一章" 等显示标签
    title = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)  # 仅在文本节点填充
    word_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=True)
    path = Column(String, nullable=False)  # materialized path，如 "0001.0003"
    status = Column(String, default='active')  # active | deprecated | superseded
    meta_data = Column(JSONB, default={})
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关联
    edition = relationship("Edition", back_populates="document_nodes")
    children = relationship("DocumentNode", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("DocumentNode", back_populates="children", remote_side=[id])


class IngestJob(ORMBase):
    """
    导入作业表 - 跟踪文本导入任务
    """
    __tablename__ = "ingest_jobs"
    
    id = Column(Integer, primary_key=True)
    edition_id = Column(Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String, default='initial_import')
    status = Column(String, default='pending')  # pending | running | completed | failed
    payload = Column(JSONB, default={})
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    progress = Column(Integer, default=0)  # 0-100 百分比
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)


# ============================================================================
# Data Transfer Objects
# ============================================================================

@dataclass
class WorkData:
    """作品数据传输对象"""
    title: str
    slug: str = ""
    id: int = field(default=-1)
    original_title: Optional[str] = None
    author: Optional[str] = None
    language_primary: str = "zh"
    work_type: str = "web_novel"
    status: str = "ongoing"
    synopsis: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    edition_count: int = 0
    chapter_count: int = 0
    total_chars: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: Work, edition_count: int = 0, chapter_count: int = 0, total_chars: int = 0):
        return cls(
            id=orm.id,
            slug=orm.slug,
            title=orm.title,
            original_title=orm.original_title,
            author=orm.author,
            language_primary=orm.language_primary,
            work_type=orm.work_type,
            status=orm.status,
            synopsis=orm.synopsis,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            edition_count=edition_count,
            chapter_count=chapter_count,
            total_chars=total_chars,
        )
    
    def create_orm(self) -> Work:
        return Work(
            slug=self.slug or self._generate_slug(),
            title=self.title,
            original_title=self.original_title,
            author=self.author,
            language_primary=self.language_primary,
            work_type=self.work_type,
            status=self.status,
            synopsis=self.synopsis,
            meta_data=self.meta_data,
        )
    
    def update_orm(self, orm: Work):
        orm.title = self.title
        orm.original_title = self.original_title
        orm.author = self.author
        orm.language_primary = self.language_primary
        orm.work_type = self.work_type
        orm.status = self.status
        orm.synopsis = self.synopsis
        orm.meta_data = self.meta_data
    
    def _generate_slug(self) -> str:
        import re
        import time
        # 简单的slug生成：移除特殊字符，转小写，用下划线连接
        slug = re.sub(r'[^\w\s-]', '', self.title.lower())
        slug = re.sub(r'[-\s]+', '_', slug)
        return f"{slug}_{int(time.time())}"


@dataclass
class EditionData:
    """版本数据传输对象"""
    work_id: int
    language: str = "zh"
    id: int = field(default=-1)
    edition_name: Optional[str] = None
    source_format: str = "txt"
    canonical: bool = False
    source_path: Optional[str] = None
    source_checksum: Optional[str] = None
    ingest_version: int = 1
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    description: Optional[str] = None
    status: str = "draft"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    chapter_count: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: Edition, chapter_count: int = 0):
        return cls(
            id=orm.id,
            work_id=orm.work_id,
            edition_name=orm.edition_name,
            language=orm.language,
            source_format=orm.source_format,
            canonical=orm.canonical,
            source_path=orm.source_path,
            source_checksum=orm.source_checksum,
            ingest_version=orm.ingest_version,
            word_count=orm.word_count,
            char_count=orm.char_count,
            description=orm.description,
            status=orm.status,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            chapter_count=chapter_count,
        )
    
    def create_orm(self) -> Edition:
        return Edition(
            work_id=self.work_id,
            edition_name=self.edition_name,
            language=self.language,
            source_format=self.source_format,
            canonical=self.canonical,
            source_path=self.source_path,
            source_checksum=self.source_checksum,
            ingest_version=self.ingest_version,
            word_count=self.word_count,
            char_count=self.char_count,
            description=self.description,
            status=self.status,
            meta_data=self.meta_data,
        )
    
    def update_orm(self, orm: Edition):
        orm.edition_name = self.edition_name
        orm.language = self.language
        orm.source_format = self.source_format
        orm.canonical = self.canonical
        orm.source_path = self.source_path
        orm.source_checksum = self.source_checksum
        orm.ingest_version = self.ingest_version
        orm.word_count = self.word_count
        orm.char_count = self.char_count
        orm.description = self.description
        orm.status = self.status
        orm.meta_data = self.meta_data


@dataclass
class DocumentNodeData:
    """文档节点数据传输对象"""
    edition_id: int
    node_type: str
    sort_index: int
    depth: int
    path: str
    id: int = field(default=-1)
    parent_id: Optional[int] = None
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    status: str = "active"
    meta_data: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    children_count: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: DocumentNode, children_count: int = 0, include_content: bool = True):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            parent_id=orm.parent_id,
            node_type=orm.node_type,
            sort_index=orm.sort_index,
            depth=orm.depth,
            label=orm.label,
            title=orm.title,
            raw_text=orm.raw_text if include_content else None,
            word_count=orm.word_count,
            char_count=orm.char_count,
            path=orm.path,
            status=orm.status,
            meta_data=orm.meta_data or {},
            created_at=orm.created_at,
            updated_at=orm.updated_at,
            children_count=children_count,
        )
    
    def create_orm(self) -> DocumentNode:
        return DocumentNode(
            edition_id=self.edition_id,
            parent_id=self.parent_id,
            node_type=self.node_type,
            sort_index=self.sort_index,
            depth=self.depth,
            label=self.label,
            title=self.title,
            raw_text=self.raw_text,
            word_count=self.word_count,
            char_count=self.char_count,
            path=self.path,
            status=self.status,
            meta_data=self.meta_data,
        )
    
    def update_orm(self, orm: DocumentNode):
        orm.parent_id = self.parent_id
        orm.node_type = self.node_type
        orm.sort_index = self.sort_index
        orm.depth = self.depth
        orm.label = self.label
        orm.title = self.title
        orm.raw_text = self.raw_text
        orm.word_count = self.word_count
        orm.char_count = self.char_count
        orm.path = self.path
        orm.status = self.status
        orm.meta_data = self.meta_data


@dataclass
class IngestJobData:
    """导入作业数据传输对象"""
    edition_id: int
    id: int = field(default=-1)
    job_type: str = "initial_import"
    status: str = "pending"
    payload: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: int = 0
    total_items: int = 0
    processed_items: int = 0
    
    @classmethod
    def read_from_orm(cls, orm: IngestJob):
        return cls(
            id=orm.id,
            edition_id=orm.edition_id,
            job_type=orm.job_type,
            status=orm.status,
            payload=orm.payload or {},
            started_at=orm.started_at,
            finished_at=orm.finished_at,
            error_message=orm.error_message,
            progress=orm.progress,
            total_items=orm.total_items,
            processed_items=orm.processed_items,
        )


@dataclass
class TextImportRequest:
    """文本导入请求数据"""
    work_title: str
    content: str  # 原始文本内容
    work_author: Optional[str] = None
    work_synopsis: Optional[str] = None
    edition_name: Optional[str] = None
    language: str = "zh"
    chapter_pattern: Optional[str] = None  # 章节识别正则表达式
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterListItem:
    """章节列表项（简化版，用于目录展示）"""
    id: int
    sort_index: int
    label: Optional[str]
    title: Optional[str]
    char_count: Optional[int]
    path: str


@dataclass
class DocumentNodeUpdateRequest:
    """文档节点更新请求（仅包含可编辑字段）"""
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterInsertRequest:
    """插入章节请求"""
    edition_id: int
    sort_index: int  # 插入位置（0-based），插入后该位置及之后的章节会后移
    label: Optional[str] = None  # 章节标签，如 "第一章"
    title: Optional[str] = None  # 章节标题
    content: str = ""  # 章节内容
    meta_data: Dict[str, Any] = field(default_factory=dict)
