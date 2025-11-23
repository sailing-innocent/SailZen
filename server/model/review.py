# -*- coding: utf-8 -*-
# @file review.py
# @brief ORM model for review tasks

from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class ReviewTask(ORMBase):
    __tablename__ = "review_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    change_set_id = Column(
        UUID(as_uuid=True),
        ForeignKey("change_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer = Column(String, nullable=False)
    status = Column(
        String, default="pending"
    )  # pending | approved | rejected | cancelled
    decided_at = Column(TIMESTAMP(timezone=True), nullable=True)
    decision = Column(String, nullable=True)  # approve | reject | request_changes
    comments = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    change_set = relationship("ChangeSet", back_populates="review_tasks")
