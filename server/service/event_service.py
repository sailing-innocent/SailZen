# -*- coding: utf-8 -*-
# @file event_service.py
# @brief Service layer for narrative events
# @author sailing-innocent
# @date 2025-11-08

from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.model.narrative_event import NarrativeEvent, EventParticipant
from server.data.schemas import (
    NarrativeEventCreate,
    NarrativeEventUpdate,
    NarrativeEventResponse,
    EventParticipantCreate,
    EventParticipantUpdate,
    EventParticipantResponse,
)


class EventService:
    """Service for managing narrative events and participants"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Narrative Event Methods ============

    def create_event(self, event_data: NarrativeEventCreate) -> NarrativeEventResponse:
        """Create a new narrative event"""
        db_event = NarrativeEvent(**event_data.model_dump())
        self.db.add(db_event)
        self.db.commit()
        self.db.refresh(db_event)
        return NarrativeEventResponse.model_validate(db_event)

    def get_event(self, event_id: UUID) -> Optional[NarrativeEventResponse]:
        """Get event by ID"""
        event = self.db.query(NarrativeEvent).filter(NarrativeEvent.id == event_id).first()
        if event:
            return NarrativeEventResponse.model_validate(event)
        return None

    def list_events(
        self,
        work_id: Optional[UUID] = None,
        edition_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        parent_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[NarrativeEventResponse]:
        """List events with optional filters"""
        query = self.db.query(NarrativeEvent)
        
        if work_id:
            query = query.filter(NarrativeEvent.work_id == work_id)
        if edition_id:
            query = query.filter(NarrativeEvent.edition_id == edition_id)
        if event_type:
            query = query.filter(NarrativeEvent.event_type == event_type)
        if parent_id is not None:
            # Support filtering for root events (parent_id == None)
            query = query.filter(NarrativeEvent.parent_id == parent_id)
        
        # Order by chronology_order if available, otherwise by created_at
        query = query.order_by(
            NarrativeEvent.chronology_order.asc().nulls_last(),
            NarrativeEvent.created_at.asc()
        )
        
        events = query.offset(skip).limit(limit).all()
        return [NarrativeEventResponse.model_validate(e) for e in events]

    def update_event(
        self, event_id: UUID, update_data: NarrativeEventUpdate
    ) -> Optional[NarrativeEventResponse]:
        """Update event"""
        event = self.db.query(NarrativeEvent).filter(NarrativeEvent.id == event_id).first()
        if not event:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(event, key, value)

        self.db.commit()
        self.db.refresh(event)
        return NarrativeEventResponse.model_validate(event)

    def delete_event(self, event_id: UUID) -> bool:
        """Delete event"""
        event = self.db.query(NarrativeEvent).filter(NarrativeEvent.id == event_id).first()
        if not event:
            return False

        self.db.delete(event)
        self.db.commit()
        return True

    def get_child_events(self, parent_id: UUID) -> List[NarrativeEventResponse]:
        """Get all child events of a parent event"""
        return self.list_events(parent_id=parent_id)

    def get_event_hierarchy(self, event_id: UUID) -> dict:
        """Get event with its full hierarchy (parent chain and children)"""
        event = self.get_event(event_id)
        if not event:
            return None

        # Get parent chain
        parent_chain = []
        current = event
        while current.parent_id:
            parent = self.get_event(current.parent_id)
            if not parent:
                break
            parent_chain.insert(0, parent)
            current = parent

        # Get children
        children = self.get_child_events(event_id)

        return {
            "event": event,
            "parent_chain": parent_chain,
            "children": children,
        }

    # ============ Event Participant Methods ============

    def add_participant(
        self, participant_data: EventParticipantCreate
    ) -> EventParticipantResponse:
        """Add a participant to an event"""
        db_participant = EventParticipant(**participant_data.model_dump())
        self.db.add(db_participant)
        self.db.commit()
        self.db.refresh(db_participant)
        return EventParticipantResponse.model_validate(db_participant)

    def get_event_participants(self, event_id: UUID) -> List[EventParticipantResponse]:
        """Get all participants of an event"""
        participants = (
            self.db.query(EventParticipant)
            .filter(EventParticipant.event_id == event_id)
            .all()
        )
        return [EventParticipantResponse.model_validate(p) for p in participants]

    def get_entity_events(self, entity_id: UUID) -> List[NarrativeEventResponse]:
        """Get all events an entity participates in"""
        participants = (
            self.db.query(EventParticipant)
            .filter(EventParticipant.entity_id == entity_id)
            .all()
        )
        event_ids = [p.event_id for p in participants]
        
        if not event_ids:
            return []
        
        events = (
            self.db.query(NarrativeEvent)
            .filter(NarrativeEvent.id.in_(event_ids))
            .order_by(
                NarrativeEvent.chronology_order.asc().nulls_last(),
                NarrativeEvent.created_at.asc()
            )
            .all()
        )
        return [NarrativeEventResponse.model_validate(e) for e in events]

    def update_participant(
        self, participant_id: UUID, update_data: EventParticipantUpdate
    ) -> Optional[EventParticipantResponse]:
        """Update participant"""
        participant = (
            self.db.query(EventParticipant)
            .filter(EventParticipant.id == participant_id)
            .first()
        )
        if not participant:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(participant, key, value)

        self.db.commit()
        self.db.refresh(participant)
        return EventParticipantResponse.model_validate(participant)

    def remove_participant(self, participant_id: UUID) -> bool:
        """Remove a participant from an event"""
        participant = (
            self.db.query(EventParticipant)
            .filter(EventParticipant.id == participant_id)
            .first()
        )
        if not participant:
            return False

        self.db.delete(participant)
        self.db.commit()
        return True

