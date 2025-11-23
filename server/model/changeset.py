# -*- coding: utf-8 -*-
# @file changeset.py
# @brief ORM models for change sets and change items

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class ChangeSet(ORMBase):
    __tablename__ = "change_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id = Column(
        UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"), nullable=True
    )
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collab_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source = Column(String, nullable=False)  # manual | llm_auto | collaboration_commit
    reason = Column(Text)
    status = Column(
        String, default="pending"
    )  # pending | applied | rolled_back | failed
    created_by = Column(String)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    applied_at = Column(TIMESTAMP(timezone=True), nullable=True)
    rolled_back_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = Column(Text)

    # Relationships
    edition = relationship("Edition", back_populates="change_sets")
    session = relationship("CollabSession", back_populates="change_sets")
    items = relationship(
        "ChangeItem", back_populates="change_set", cascade="all, delete-orphan"
    )
    review_tasks = relationship(
        "ReviewTask", back_populates="change_set", cascade="all, delete-orphan"
    )


class ChangeItem(ORMBase):
    __tablename__ = "change_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("change_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_table = Column(String, nullable=False)  # entities | entity_mentions | etc.
    target_id = Column(UUID(as_uuid=True), nullable=True)
    operation = Column(String, nullable=False)  # insert | update | delete
    column_name = Column(String, nullable=True)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    span_id = Column(
        UUID(as_uuid=True),
        ForeignKey("text_spans.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = Column(Text)

    # Relationships
    change_set = relationship("ChangeSet", back_populates="items")
    span = relationship("TextSpan", foreign_keys=[span_id])
