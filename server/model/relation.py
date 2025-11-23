# -*- coding: utf-8 -*-
# @file relation.py
# @brief ORM models for entity relations
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy import Column, String, Text, TIMESTAMP, ForeignKey, UniqueConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class EntityRelation(ORMBase):
    __tablename__ = "entity_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    universe_id = Column(UUID(as_uuid=True), ForeignKey("universes.id", ondelete="CASCADE"))
    work_id = Column(UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"))
    edition_id = Column(UUID(as_uuid=True), ForeignKey("editions.id", ondelete="CASCADE"))
    source_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String, nullable=False)  # family | alliance | ownership | conflict | etc.
    direction = Column(String, default='directed')
    description = Column(Text)
    status = Column(String, default='draft')
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="relations_as_source")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id], back_populates="relations_as_target")
    evidence = relationship("RelationEvidence", back_populates="relation", cascade="all, delete-orphan")


class RelationEvidence(ORMBase):
    __tablename__ = "relation_evidence"
    __table_args__ = (UniqueConstraint('relation_id', 'span_id', name='_relation_span_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    relation_id = Column(UUID(as_uuid=True), ForeignKey("entity_relations.id", ondelete="CASCADE"), nullable=False)
    span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="CASCADE"), nullable=False)
    confidence = Column(Numeric(5, 4))
    notes = Column(Text)

    # Relationships
    relation = relationship("EntityRelation", back_populates="evidence")

