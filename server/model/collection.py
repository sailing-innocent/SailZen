# -*- coding: utf-8 -*-
# @file collection.py
# @brief ORM models for knowledge collections (character arcs, plotlines, etc.)
# @author sailing-innocent
# @date 2025-11-08

from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from server.data.orm import Base


class KnowledgeCollection(Base):
    """Generic collection for organizing knowledge items (character arcs, plotlines, themes, etc.)"""

    __tablename__ = "knowledge_collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id = Column(UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    collection_type = Column(Text, nullable=False)  # character_arc | plotline | theme | location_group | faction
    description = Column(Text)
    meta_data = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    work = relationship("Work", back_populates="knowledge_collections")
    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("work_id", "collection_type", "name", name="uq_work_type_name"),
    )


class CollectionItem(Base):
    """Items in a knowledge collection - links to entities, relations, or events"""

    __tablename__ = "collection_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_collections.id", ondelete="CASCADE"), nullable=False)
    target_type = Column(Text, nullable=False)  # entity | relation | narrative_event
    target_id = Column(UUID(as_uuid=True), nullable=False)
    sort_order = Column(Integer)
    role_in_collection = Column(Text)  # e.g., "arc_beginning", "key_moment", "resolution"
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    collection = relationship("KnowledgeCollection", back_populates="items")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("collection_id", "target_type", "target_id", name="uq_collection_target"),
    )

