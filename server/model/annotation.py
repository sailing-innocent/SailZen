# -*- coding: utf-8 -*-
# @file annotation.py
# @brief ORM models for annotation batches and items

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class AnnotationBatch(ORMBase):
    __tablename__ = "annotation_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collab_sessions.id", ondelete="CASCADE"),
        nullable=True,
    )
    batch_type = Column(String, nullable=False)  # llm_suggestion | human_draft | merged
    source = Column(String, nullable=False)  # model name or user identifier
    status = Column(
        String, default="draft"
    )  # draft | pending | approved | rejected | committed
    confidence = Column(JSONB, default={})
    notes = Column(Text)
    created_by = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    edition = relationship("Edition", back_populates="annotation_batches")
    session = relationship("CollabSession", back_populates="batches")
    items = relationship(
        "AnnotationItem", back_populates="batch", cascade="all, delete-orphan"
    )


class AnnotationItem(ORMBase):
    __tablename__ = "annotation_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("annotation_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type = Column(
        String, nullable=False
    )  # node | span | entity | relation | event
    target_id = Column(UUID(as_uuid=True), nullable=True)
    span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("text_spans.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload = Column(JSONB, nullable=False)
    confidence = Column(Numeric(5, 4), nullable=True)
    status = Column(String, default="pending")  # pending | approved | rejected
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    batch = relationship("AnnotationBatch", back_populates="items")
    span = relationship("TextSpan", foreign_keys=[span_id])
