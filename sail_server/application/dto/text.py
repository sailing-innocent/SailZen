# -*- coding: utf-8 -*-
# @file text.py
# @brief Text Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
文本管理模块 Pydantic DTOs

原位置: sail_server/data/text.py
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Work DTOs
# ============================================================================


class WorkBase(BaseModel):
    """作品基础信息"""

    model_config = ConfigDict(from_attributes=True)

    slug: str = Field(description="唯一标识符")
    title: str = Field(description="作品标题")
    original_title: Optional[str] = Field(default=None, description="原始标题")
    author: Optional[str] = Field(default=None, description="作者")
    language_primary: str = Field(default="zh", description="主要语言")
    work_type: str = Field(default="web_novel", description="作品类型")
    status: str = Field(default="ongoing", description="作品状态")
    synopsis: Optional[str] = Field(default=None, description="简介")


class WorkCreateRequest(WorkBase):
    """创建作品请求"""

    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class WorkUpdateRequest(BaseModel):
    """更新作品请求"""

    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, description="作品标题")
    author: Optional[str] = Field(default=None, description="作者")
    status: Optional[str] = Field(default=None, description="作品状态")
    synopsis: Optional[str] = Field(default=None, description="简介")


class WorkResponse(WorkBase):
    """作品响应"""

    id: int = Field(description="作品ID")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    edition_count: int = Field(default=0, description="版本数量")
    chapter_count: int = Field(default=0, description="章节数量")
    total_chars: int = Field(default=0, description="总字符数")


class WorkListResponse(BaseModel):
    """作品列表响应"""

    works: List[WorkResponse]
    total: int


# ============================================================================
# Edition DTOs
# ============================================================================


class EditionBase(BaseModel):
    """版本基础信息"""

    model_config = ConfigDict(from_attributes=True)

    work_id: int = Field(description="所属作品ID")
    edition_name: Optional[str] = Field(default=None, description="版本名称")
    language: str = Field(default="zh", description="语言")
    source_format: str = Field(default="txt", description="源格式")
    canonical: bool = Field(default=False, description="是否规范版本")
    description: Optional[str] = Field(default=None, description="版本描述")


class EditionCreateRequest(EditionBase):
    """创建版本请求"""

    source_path: Optional[str] = Field(default=None, description="源文件路径")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class EditionUpdateRequest(BaseModel):
    """更新版本请求"""

    model_config = ConfigDict(from_attributes=True)

    edition_name: Optional[str] = Field(default=None, description="版本名称")
    canonical: Optional[bool] = Field(default=None, description="是否规范版本")
    status: Optional[str] = Field(default=None, description="版本状态")
    description: Optional[str] = Field(default=None, description="版本描述")


class EditionResponse(EditionBase):
    """版本响应"""

    id: int = Field(description="版本ID")
    source_path: Optional[str] = Field(default=None, description="源文件路径")
    source_checksum: Optional[str] = Field(default=None, description="源文件校验和")
    ingest_version: int = Field(default=1, description="导入版本")
    word_count: Optional[int] = Field(default=None, description="字数")
    char_count: Optional[int] = Field(default=None, description="字符数")
    status: str = Field(default="draft", description="版本状态")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class EditionListResponse(BaseModel):
    """版本列表响应"""

    editions: List[EditionResponse]
    total: int


# ============================================================================
# DocumentNode DTOs
# ============================================================================


class DocumentNodeBase(BaseModel):
    """文档节点基础信息"""

    model_config = ConfigDict(from_attributes=True)

    edition_id: int = Field(description="所属版本ID")
    node_type: str = Field(default="chapter", description="节点类型")
    title: str = Field(description="节点标题")
    raw_text: Optional[str] = Field(default=None, description="节点内容")
    level: int = Field(default=1, description="层级")


class DocumentNodeCreateRequest(DocumentNodeBase):
    """创建文档节点请求"""

    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    sort_order: Optional[int] = Field(default=None, description="排序顺序")
    meta_data: Optional[Dict[str, Any]] = Field(default=None, description="元数据")


class DocumentNodeUpdateRequest(BaseModel):
    """更新文档节点请求"""

    model_config = ConfigDict(from_attributes=True)

    title: Optional[str] = Field(default=None, description="节点标题")
    raw_text: Optional[str] = Field(default=None, description="节点内容")
    sort_order: Optional[int] = Field(default=None, description="排序顺序")


class DocumentNodeResponse(DocumentNodeBase):
    """文档节点响应"""

    id: int = Field(description="节点ID")
    parent_id: Optional[int] = Field(default=None, description="父节点ID")
    sort_order: int = Field(default=0, description="排序顺序")
    word_count: Optional[int] = Field(default=None, description="字数")
    char_count: Optional[int] = Field(default=None, description="字符数")
    meta_data: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class DocumentNodeListResponse(BaseModel):
    """文档节点列表响应"""

    nodes: List[DocumentNodeResponse]
    total: int
