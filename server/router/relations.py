# -*- coding: utf-8 -*-
# @file relations.py
# @brief API routes for entity relations
# @author sailing-innocent
# @date 2025-04-21

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.entity_service import EntityService
from server.data.schemas import (
    EntityRelationCreate,
    EntityRelationUpdate,
    EntityRelationResponse,
)

router = APIRouter(prefix="/api/v1", tags=["relations"])


def get_entity_service(db: Session = Depends(g_db_func)):
    return EntityService(db)


# ============ Entity Relation Endpoints ============


@router.post(
    "/relations",
    response_model=EntityRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relation(
    relation: EntityRelationCreate, service: EntityService = Depends(get_entity_service)
):
    """Create a new entity relation"""
    try:
        return service.create_relation(relation)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/relations", response_model=List[EntityRelationResponse])
def list_relations(
    entity_id: Optional[UUID] = None,
    relation_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    service: EntityService = Depends(get_entity_service),
):
    """List relations with optional filters"""
    return service.list_relations(
        entity_id=entity_id, relation_type=relation_type, skip=skip, limit=limit
    )


@router.get("/relations/{relation_id}", response_model=EntityRelationResponse)
def get_relation(
    relation_id: UUID, service: EntityService = Depends(get_entity_service)
):
    """Get relation by ID"""
    relation = service.get_relation(relation_id)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    return relation


@router.put("/relations/{relation_id}", response_model=EntityRelationResponse)
def update_relation(
    relation_id: UUID,
    update_data: EntityRelationUpdate,
    service: EntityService = Depends(get_entity_service),
):
    """Update relation"""
    relation = service.update_relation(relation_id, update_data)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    return relation


@router.delete("/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(
    relation_id: UUID, service: EntityService = Depends(get_entity_service)
):
    """Delete relation"""
    if not service.delete_relation(relation_id):
        raise HTTPException(status_code=404, detail="Relation not found")


@router.post("/relations/{relation_id}/evidence", status_code=status.HTTP_201_CREATED)
def add_relation_evidence(
    relation_id: UUID,
    span_id: UUID,
    confidence: Optional[float] = None,
    notes: Optional[str] = None,
    service: EntityService = Depends(get_entity_service),
):
    """Add evidence (text span) to a relation"""
    try:
        success = service.add_relation_evidence(relation_id, span_id, confidence, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Relation not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
