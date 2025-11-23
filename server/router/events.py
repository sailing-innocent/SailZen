# -*- coding: utf-8 -*-
# @file events.py
# @brief API routes for narrative events
# @author sailing-innocent
# @date 2025-11-08

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.event_service import EventService
from server.data.schemas import (
    NarrativeEventCreate,
    NarrativeEventUpdate,
    NarrativeEventResponse,
    EventParticipantCreate,
    EventParticipantUpdate,
    EventParticipantResponse,
)

router = APIRouter(prefix="/api/v1", tags=["events"])


def get_event_service(db: Session = Depends(g_db_func)):
    return EventService(db)


# ============ Narrative Event Endpoints ============


@router.post("/events", response_model=NarrativeEventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event: NarrativeEventCreate,
    service: EventService = Depends(get_event_service)
):
    """Create a new narrative event"""
    try:
        return service.create_event(event)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events", response_model=List[NarrativeEventResponse])
def list_events(
    work_id: Optional[UUID] = None,
    edition_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    parent_id: Optional[UUID] = Query(None, description="Filter by parent_id. Use 'null' for root events"),
    skip: int = 0,
    limit: int = 50,
    service: EventService = Depends(get_event_service)
):
    """List narrative events with optional filters"""
    return service.list_events(
        work_id=work_id,
        edition_id=edition_id,
        event_type=event_type,
        parent_id=parent_id,
        skip=skip,
        limit=limit
    )


@router.get("/events/{event_id}", response_model=NarrativeEventResponse)
def get_event(
    event_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Get event by ID"""
    event = service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/events/{event_id}/hierarchy")
def get_event_hierarchy(
    event_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Get event with its full hierarchy (parent chain and children)"""
    hierarchy = service.get_event_hierarchy(event_id)
    if not hierarchy:
        raise HTTPException(status_code=404, detail="Event not found")
    return hierarchy


@router.get("/events/{event_id}/children", response_model=List[NarrativeEventResponse])
def get_child_events(
    event_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Get all child events of a parent event"""
    return service.get_child_events(event_id)


@router.put("/events/{event_id}", response_model=NarrativeEventResponse)
def update_event(
    event_id: UUID,
    update_data: NarrativeEventUpdate,
    service: EventService = Depends(get_event_service)
):
    """Update event"""
    event = service.update_event(event_id, update_data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Delete event"""
    if not service.delete_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")


# ============ Event Participant Endpoints ============


@router.post("/events/{event_id}/participants", response_model=EventParticipantResponse, status_code=status.HTTP_201_CREATED)
def add_participant(
    event_id: UUID,
    participant: EventParticipantCreate,
    service: EventService = Depends(get_event_service)
):
    """Add a participant to an event"""
    # Ensure event_id matches
    if participant.event_id != event_id:
        raise HTTPException(status_code=400, detail="Event ID mismatch")
    
    try:
        return service.add_participant(participant)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events/{event_id}/participants", response_model=List[EventParticipantResponse])
def get_event_participants(
    event_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Get all participants of an event"""
    return service.get_event_participants(event_id)


@router.get("/entities/{entity_id}/events", response_model=List[NarrativeEventResponse])
def get_entity_events(
    entity_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Get all events an entity participates in"""
    return service.get_entity_events(entity_id)


@router.put("/participants/{participant_id}", response_model=EventParticipantResponse)
def update_participant(
    participant_id: UUID,
    update_data: EventParticipantUpdate,
    service: EventService = Depends(get_event_service)
):
    """Update participant"""
    participant = service.update_participant(participant_id, update_data)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    return participant


@router.delete("/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    participant_id: UUID,
    service: EventService = Depends(get_event_service)
):
    """Remove a participant from an event"""
    if not service.remove_participant(participant_id):
        raise HTTPException(status_code=404, detail="Participant not found")

