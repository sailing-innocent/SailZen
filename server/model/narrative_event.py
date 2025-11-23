# -*- coding: utf-8 -*-
# @file narrative_event.py
# @brief ORM models for narrative events and event participants
# @author sailing-innocent
# @date 2025-11-08

from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from server.data.orm import Base


class NarrativeEvent(Base):
    """Narrative event in a story - can be work-level or edition-specific"""

    __tablename__ = "narrative_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_id = Column(UUID(as_uuid=True), ForeignKey("works.id", ondelete="CASCADE"), nullable=False)
    edition_id = Column(UUID(as_uuid=True), ForeignKey("editions.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    event_type = Column(Text, default="plot_point")  # plot_point | backstory | foreshadow | climax | resolution
    summary = Column(Text)
    start_span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="SET NULL"), nullable=True)
    end_span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="SET NULL"), nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("narrative_events.id", ondelete="SET NULL"), nullable=True)
    chronology_order = Column(Numeric(10, 2))
    importance = Column(Text, default="major")  # major | minor | background
    status = Column(Text, default="draft")  # draft | verified | deprecated
    meta_data = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    work = relationship("Work", back_populates="narrative_events")
    edition = relationship("Edition", back_populates="narrative_events")
    participants = relationship("EventParticipant", back_populates="event", cascade="all, delete-orphan")
    
    # Self-referential relationship for hierarchy
    parent = relationship("NarrativeEvent", remote_side=[id], backref="children")


class EventParticipant(Base):
    """Link between narrative events and entities (characters, organizations, etc.)"""

    __tablename__ = "event_participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("narrative_events.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, default="participant")  # protagonist | antagonist | witness | victim | helper
    contribution = Column(Text)
    span_id = Column(UUID(as_uuid=True), ForeignKey("text_spans.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("NarrativeEvent", back_populates="participants")
    entity = relationship("Entity", back_populates="event_participations")

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("event_id", "entity_id", "role", name="uq_event_entity_role"),
    )

