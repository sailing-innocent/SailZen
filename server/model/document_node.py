# -*- coding: utf-8 -*-
# @file document_node.py
# @brief ORM models for document structure
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy import Column, String, Integer, SmallInteger, Text, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class DocumentNode(ORMBase):
    __tablename__ = "document_nodes"
    __table_args__ = (UniqueConstraint('edition_id', 'path', name='_edition_path_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id = Column(UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("document_nodes.id", ondelete="CASCADE"))
    node_type = Column(String, nullable=False)  # volume/part/chapter/section/paragraph/sentence/title/extra
    sort_index = Column(Integer, nullable=False)
    depth = Column(SmallInteger, nullable=False)
    label = Column(String)
    title = Column(String)
    raw_text = Column(Text)
    text_checksum = Column(String)
    word_count = Column(Integer)
    char_count = Column(Integer)
    start_char = Column(Integer)
    end_char = Column(Integer)
    path = Column(String, nullable=False)  # materialized path like '0001.0003'
    status = Column(String, default='active')  # active | deprecated | superseded
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    edition = relationship("Edition", back_populates="nodes")
    parent = relationship("DocumentNode", remote_side=[id], backref="children")
    spans = relationship("TextSpan", back_populates="node", cascade="all, delete-orphan")


class TextSpan(ORMBase):
    __tablename__ = "text_spans"
    __table_args__ = (UniqueConstraint('node_id', 'start_char', 'end_char', name='_node_span_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("document_nodes.id", ondelete="CASCADE"), nullable=False)
    span_type = Column(String, default='explicit')  # explicit | inferred | auto_sentence
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    text_snippet = Column(Text)
    created_by = Column(String, default='system')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    node = relationship("DocumentNode", back_populates="spans")
    entity_mentions = relationship("EntityMention", back_populates="span", cascade="all, delete-orphan")

