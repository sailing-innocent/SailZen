# -*- coding: utf-8 -*-
# @file session.py
# @brief ORM model for collaborative editing sessions

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class CollabSession(ORMBase):
    __tablename__ = "collab_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("editions.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type = Column(String, nullable=False)  # node | entity | relation | event
    target_id = Column(UUID(as_uuid=True), nullable=False)
    lock_scope = Column(String, default="node")  # node | entity | span | edition
    state = Column(
        String, default="active"
    )  # active | has_draft | committed | closed | needs_merge
    state_reason = Column(Text)
    meta_data = Column(JSONB, default={})
    created_by = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    edition = relationship("Edition", back_populates="collab_sessions")
    batches = relationship(
        "AnnotationBatch", back_populates="session", cascade="all, delete-orphan"
    )
    change_sets = relationship("ChangeSet", back_populates="session")
