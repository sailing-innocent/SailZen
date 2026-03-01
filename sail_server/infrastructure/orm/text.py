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
    Integer,
    String,
    TIMESTAMP,
    func,
    Text,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.data.types import JSONB


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
    language_primary = Column(String, nullable=False, default="zh")
    work_type = Column(String, default="web_novel")  # web_novel | novel | essay
    status = Column(String, default="ongoing")  # ongoing | completed | hiatus
    synopsis = Column(Text, nullable=True)
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


class IngestJob(ORMBase):
    """
    导入作业表 - 跟踪文本导入任务
    """

    __tablename__ = "ingest_jobs"

    id = Column(Integer, primary_key=True)
    edition_id = Column(
        Integer, ForeignKey("editions.id", ondelete="CASCADE"), nullable=False
    )
    job_type = Column(String, default="initial_import")
    status = Column(String, default="pending")  # pending | running | completed | failed
    payload = Column(JSONB, default={})
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    progress = Column(Integer, default=0)  # 0-100 百分比
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
