# -*- coding: utf-8 -*-
# @file entity.py
# @brief ORM models for entities
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy import Column, String, Text, Boolean, TIMESTAMP, ForeignKey, UniqueConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from server.data.orm import ORMBase


class Entity(ORMBase):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    universe_id = Column(UUID(as_uuid=True), ForeignKey("universes.id", ondelete="SET NULL"))
    work_id = Column(UUID(as_uuid=True), ForeignKey("works.id", ondelete="SET NULL"))
    edition_id = Column(UUID(as_uuid=True), ForeignKey("editions.id", ondelete="SET NULL"))
    entity_type = Column(String, nullable=False)  # character | item | location | organization | concept
    canonical_name = Column(String, nullable=False)
    description = Column(Text)
    origin_span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="SET NULL"))
    scope = Column(String, default='edition')  # edition | work | global
    status = Column(String, default='draft')  # draft | verified | deprecated
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    aliases = relationship("EntityAlias", back_populates="entity", cascade="all, delete-orphan")
    attributes = relationship("EntityAttribute", back_populates="entity", cascade="all, delete-orphan")
    mentions = relationship("EntityMention", back_populates="entity", cascade="all, delete-orphan")
    relations_as_source = relationship("EntityRelation", foreign_keys="[EntityRelation.source_entity_id]", back_populates="source_entity")
    relations_as_target = relationship("EntityRelation", foreign_keys="[EntityRelation.target_entity_id]", back_populates="target_entity")
    event_participations = relationship("EventParticipant", back_populates="entity", cascade="all, delete-orphan")


class EntityAlias(ORMBase):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint('entity_id', 'alias', name='_entity_alias_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=False)
    language = Column(String)
    alias_type = Column(String, default='nickname')
    is_preferred = Column(Boolean, default=False)

    # Relationships
    entity = relationship("Entity", back_populates="aliases")


class EntityAttribute(ORMBase):
    __tablename__ = "entity_attributes"
    __table_args__ = (UniqueConstraint('entity_id', 'attr_key', 'source_span_id', name='_entity_attr_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    attr_key = Column(String, nullable=False)
    attr_value = Column(JSONB, nullable=False)
    source_span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="SET NULL"))
    status = Column(String, default='pending')

    # Relationships
    entity = relationship("Entity", back_populates="attributes")


class EntityMention(ORMBase):
    __tablename__ = "entity_mentions"
    __table_args__ = (UniqueConstraint('entity_id', 'span_id', name='_entity_span_uc'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="CASCADE"), nullable=False)
    mention_type = Column(String, default='explicit')
    confidence = Column(Numeric(5, 4))
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String)
    verified_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    entity = relationship("Entity", back_populates="mentions")
    span = relationship("TextSpan", back_populates="entity_mentions")

