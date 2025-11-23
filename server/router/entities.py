# -*- coding: utf-8 -*-
# @file entities.py
# @brief API routes for entities and mentions
# @author sailing-innocent
# @date 2025-04-21

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.entity_service import EntityService
from server.service.query_service import QueryService
from server.data.schemas import (
    EntityCreate, EntityUpdate, EntityResponse,
    EntityAliasCreate, EntityAliasResponse,
    EntityMentionCreate, EntityMentionUpdate, EntityMentionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["entities"])


def get_entity_service(db: Session = Depends(g_db_func)):
    return EntityService(db)


def get_query_service(db: Session = Depends(g_db_func)):
    return QueryService(db)


# ============ Entity Endpoints ============

@router.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
def create_entity(
    entity: EntityCreate,
    service: EntityService = Depends(get_entity_service)
):
    """Create a new entity"""
    try:
        return service.create_entity(entity)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/entities", response_model=List[EntityResponse])
def list_entities(
    edition_id: Optional[UUID] = None,
    entity_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    service: EntityService = Depends(get_entity_service)
):
    """List entities with optional filters"""
    return service.list_entities(
        edition_id=edition_id,
        entity_type=entity_type,
        skip=skip,
        limit=limit
    )


@router.get("/entities/search", response_model=List[EntityResponse])
def search_entities(
    q: str,
    limit: int = 20,
    service: EntityService = Depends(get_entity_service)
):
    """Search entities by name"""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    return service.search_entities(q, limit=limit)


@router.get("/entities/{entity_id}", response_model=EntityResponse)
def get_entity(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service)
):
    """Get entity by ID"""
    entity = service.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/entities/{entity_id}", response_model=EntityResponse)
def update_entity(
    entity_id: UUID,
    update_data: EntityUpdate,
    service: EntityService = Depends(get_entity_service)
):
    """Update entity"""
    entity = service.update_entity(entity_id, update_data)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service)
):
    """Delete entity"""
    if not service.delete_entity(entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")


# ============ Entity Alias Endpoints ============

@router.post("/entity-aliases", response_model=EntityAliasResponse, status_code=status.HTTP_201_CREATED)
def create_entity_alias(
    alias: EntityAliasCreate,
    service: EntityService = Depends(get_entity_service)
):
    """Create a new entity alias"""
    try:
        return service.create_entity_alias(alias)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/entities/{entity_id}/aliases", response_model=List[EntityAliasResponse])
def get_entity_aliases(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service)
):
    """Get all aliases for an entity"""
    return service.get_entity_aliases(entity_id)


# ============ Entity Mention Endpoints ============

@router.post("/entity-mentions", response_model=EntityMentionResponse, status_code=status.HTTP_201_CREATED)
def create_entity_mention(
    mention: EntityMentionCreate,
    service: EntityService = Depends(get_entity_service)
):
    """Create a new entity mention"""
    try:
        return service.create_entity_mention(mention)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/entities/{entity_id}/mentions", response_model=List[EntityMentionResponse])
def get_entity_mentions(
    entity_id: UUID,
    service: EntityService = Depends(get_entity_service)
):
    """Get all mentions of an entity"""
    return service.get_entity_mentions(entity_id)


@router.post("/entity-mentions/{mention_id}/verify", response_model=EntityMentionResponse)
def verify_mention(
    mention_id: UUID,
    verified_by: str,
    service: EntityService = Depends(get_entity_service)
):
    """Verify an entity mention"""
    mention = service.verify_mention(mention_id, verified_by)
    if not mention:
        raise HTTPException(status_code=404, detail="Mention not found")
    return mention


# ============ Query Endpoints ============

@router.get("/entities/{entity_id}/locations")
def get_entity_mention_locations(
    entity_id: UUID,
    service: QueryService = Depends(get_query_service)
):
    """Get all locations where an entity is mentioned"""
    return service.get_entity_mention_locations(entity_id)


@router.get("/entities/{entity_id}/network")
def get_entity_network(
    entity_id: UUID,
    max_depth: int = 1,
    service: QueryService = Depends(get_query_service)
):
    """Get relationship network for an entity"""
    return service.get_entity_relations_network(entity_id, max_depth=max_depth)

