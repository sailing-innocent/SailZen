# -*- coding: utf-8 -*-
# @file outline.py
# @brief Outline ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
大纲相关 ORM 模型

从 sail_server/data/analysis.py 迁移至此
"""

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, ForeignKey, func, Float
)
from sqlalchemy.orm import relationship

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm import ORMBase


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
