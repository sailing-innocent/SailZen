# -*- coding: utf-8 -*-
# @file text.py
# @brief The Text Content Data Storage (Simplified MVP)
# @author sailing-innocent
# @date 2025-01-29
# @version 2.0
# ---------------------------------
#
# 基于 doc/design/manager/text.md 的简化实现
# 实现最小可行的文本管理功能：作品、版本、文档节点
#

"""
文本管理模块数据层

ORM 模型已从 infrastructure.orm.text 迁移
DTO 模型已从 application.dto.text 迁移

此文件保留向后兼容的导出和遗留的 dataclass DTOs
（因为 controller 层仍使用 Litestar DataclassDTO）
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

# 从 infrastructure.orm 导入 ORM 模型
from sail_server.infrastructure.orm.text import (
    Work,
    Edition,
    DocumentNode,
    IngestJob,
)

# 从 application.dto 导入 Pydantic DTOs
from sail_server.application.dto.text import (
    WorkBase,
    WorkCreateRequest,
    WorkUpdateRequest,
    WorkResponse,
    WorkListResponse,
    EditionBase,
    EditionCreateRequest,
    EditionUpdateRequest,
    EditionResponse,
    EditionListResponse,
    DocumentNodeBase,
    DocumentNodeCreateRequest,
    DocumentNodeUpdateRequest,
    DocumentNodeResponse,
    DocumentNodeListResponse,
    IngestJobBase,
    IngestJobCreateRequest,
    IngestJobResponse,
    IngestJobListResponse,
)


# ============================================================================
# Legacy Dataclass DTOs (保留以兼容现有 controller)
# TODO: 迁移到 Pydantic DTOs 后删除
# ============================================================================

@dataclass
class WorkData:
    """作品数据传输对象 (legacy dataclass)"""
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


@dataclass
class EditionData:
    """版本数据传输对象 (legacy dataclass)"""
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


@dataclass
class DocumentNodeData:
    """文档节点数据传输对象 (legacy dataclass)"""
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


@dataclass
class IngestJobData:
    """导入作业数据传输对象 (legacy dataclass)"""
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


@dataclass
class TextImportRequest:
    """文本导入请求数据 (legacy dataclass)"""
    work_title: str
    content: str
    work_author: Optional[str] = None
    work_synopsis: Optional[str] = None
    edition_name: Optional[str] = None
    language: str = "zh"
    chapter_pattern: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterListItem:
    """章节列表项 (legacy dataclass)"""
    id: int
    sort_index: int
    label: Optional[str]
    title: Optional[str]
    char_count: Optional[int]
    path: str


@dataclass
class DocumentNodeUpdateRequest:
    """文档节点更新请求 (legacy dataclass)"""
    label: Optional[str] = None
    title: Optional[str] = None
    raw_text: Optional[str] = None
    meta_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChapterInsertRequest:
    """插入章节请求 (legacy dataclass)"""
    edition_id: int
    sort_index: int
    label: Optional[str] = None
    title: Optional[str] = None
    content: str = ""
    meta_data: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    # ORM Models
    "Work",
    "Edition",
    "DocumentNode",
    "IngestJob",
    # Pydantic DTOs
    "WorkBase",
    "WorkCreateRequest",
    "WorkUpdateRequest",
    "WorkResponse",
    "WorkListResponse",
    "EditionBase",
    "EditionCreateRequest",
    "EditionUpdateRequest",
    "EditionResponse",
    "EditionListResponse",
    "DocumentNodeBase",
    "DocumentNodeCreateRequest",
    "DocumentNodeUpdateRequest",
    "DocumentNodeResponse",
    "DocumentNodeListResponse",
    "IngestJobBase",
    "IngestJobCreateRequest",
    "IngestJobResponse",
    "IngestJobListResponse",
    # Legacy Dataclass DTOs
    "WorkData",
    "EditionData",
    "DocumentNodeData",
    "IngestJobData",
    "TextImportRequest",
    "ChapterListItem",
    "DocumentNodeUpdateRequest",
    "ChapterInsertRequest",
]
