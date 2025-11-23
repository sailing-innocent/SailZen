# -*- coding: utf-8 -*-
# @file works.py
# @brief API routes for works, editions, and universes
# @author sailing-innocent
# @date 2025-04-21

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.work_service import WorkService
from server.data.schemas import (
    UniverseCreate,
    UniverseUpdate,
    UniverseResponse,
    WorkCreate,
    WorkUpdate,
    WorkResponse,
    EditionCreate,
    EditionUpdate,
    EditionResponse,
    EntityResponse,
    EntityRelationResponse,
    NarrativeEventResponse,
)

router = APIRouter(prefix="/api/v1", tags=["works"])


def get_work_service(db: Session = Depends(g_db_func)):
    return WorkService(db)


# ============ Universe Endpoints ============


@router.post(
    "/universes", response_model=UniverseResponse, status_code=status.HTTP_201_CREATED
)
def create_universe(
    universe: UniverseCreate, service: WorkService = Depends(get_work_service)
):
    """Create a new universe"""
    try:
        return service.create_universe(universe)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/universes", response_model=List[UniverseResponse])
def list_universes(
    skip: int = 0, limit: int = 20, service: WorkService = Depends(get_work_service)
):
    """List all universes"""
    return service.list_universes(skip=skip, limit=limit)


@router.get("/universes/{universe_id}", response_model=UniverseResponse)
def get_universe(universe_id: UUID, service: WorkService = Depends(get_work_service)):
    """Get universe by ID"""
    universe = service.get_universe(universe_id)
    if not universe:
        raise HTTPException(status_code=404, detail="Universe not found")
    return universe


@router.put("/universes/{universe_id}", response_model=UniverseResponse)
def update_universe(
    universe_id: UUID,
    update_data: UniverseUpdate,
    service: WorkService = Depends(get_work_service),
):
    """Update universe"""
    universe = service.update_universe(universe_id, update_data)
    if not universe:
        raise HTTPException(status_code=404, detail="Universe not found")
    return universe


@router.delete("/universes/{universe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_universe(
    universe_id: UUID, service: WorkService = Depends(get_work_service)
):
    """Delete universe"""
    if not service.delete_universe(universe_id):
        raise HTTPException(status_code=404, detail="Universe not found")


# ============ Work Endpoints ============


@router.post("/works", response_model=WorkResponse, status_code=status.HTTP_201_CREATED)
def create_work(work: WorkCreate, service: WorkService = Depends(get_work_service)):
    """Create a new work"""
    try:
        return service.create_work(work)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/works", response_model=List[WorkResponse])
def list_works(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    service: WorkService = Depends(get_work_service),
):
    """List all works"""
    return service.list_works(skip=skip, limit=limit, status=status_filter)


@router.get("/works/{work_id}", response_model=WorkResponse)
def get_work(work_id: UUID, service: WorkService = Depends(get_work_service)):
    """Get work by ID"""
    work = service.get_work(work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@router.put("/works/{work_id}", response_model=WorkResponse)
def update_work(
    work_id: UUID,
    update_data: WorkUpdate,
    service: WorkService = Depends(get_work_service),
):
    """Update work"""
    work = service.update_work(work_id, update_data)
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@router.delete("/works/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work(work_id: UUID, service: WorkService = Depends(get_work_service)):
    """Delete work"""
    if not service.delete_work(work_id):
        raise HTTPException(status_code=404, detail="Work not found")


# ============ Edition Endpoints ============


@router.post(
    "/editions", response_model=EditionResponse, status_code=status.HTTP_201_CREATED
)
def create_edition(
    edition: EditionCreate, service: WorkService = Depends(get_work_service)
):
    """Create a new edition"""
    try:
        return service.create_edition(edition)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/editions", response_model=List[EditionResponse])
def list_editions(
    work_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 20,
    service: WorkService = Depends(get_work_service),
):
    """List editions, optionally filtered by work"""
    return service.list_editions(work_id=work_id, skip=skip, limit=limit)


@router.get("/editions/{edition_id}", response_model=EditionResponse)
def get_edition(edition_id: UUID, service: WorkService = Depends(get_work_service)):
    """Get edition by ID"""
    edition = service.get_edition(edition_id)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    return edition


@router.put("/editions/{edition_id}", response_model=EditionResponse)
def update_edition(
    edition_id: UUID,
    update_data: EditionUpdate,
    service: WorkService = Depends(get_work_service),
):
    """Update edition"""
    edition = service.update_edition(edition_id, update_data)
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
    return edition


@router.delete("/editions/{edition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_edition(edition_id: UUID, service: WorkService = Depends(get_work_service)):
    """Delete edition"""
    if not service.delete_edition(edition_id):
        raise HTTPException(status_code=404, detail="Edition not found")


# ============ Work-Level Knowledge Endpoints ============


@router.get("/works/{work_id}/entities", response_model=List[EntityResponse])
def list_work_entities(
    work_id: UUID,
    entity_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    service: WorkService = Depends(get_work_service),
):
    """List all work-level entities (not bound to specific edition)"""
    return service.list_work_entities(
        work_id=work_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit
    )


@router.get("/works/{work_id}/relations", response_model=List[EntityRelationResponse])
def list_work_relations(
    work_id: UUID,
    relation_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    service: WorkService = Depends(get_work_service),
):
    """List all work-level relations (not bound to specific edition)"""
    return service.list_work_relations(
        work_id=work_id,
        relation_type=relation_type,
        skip=skip,
        limit=limit
    )


@router.get("/works/{work_id}/events", response_model=List[NarrativeEventResponse])
def list_work_events(
    work_id: UUID,
    event_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    service: WorkService = Depends(get_work_service),
):
    """List all work-level narrative events (not bound to specific edition)"""
    return service.list_work_events(
        work_id=work_id,
        event_type=event_type,
        skip=skip,
        limit=limit
    )


@router.get("/works/{work_id}/knowledge-summary")
def get_work_knowledge_summary(
    work_id: UUID,
    service: WorkService = Depends(get_work_service),
):
    """Get a summary of all work-level knowledge"""
    return service.get_work_knowledge_summary(work_id)
