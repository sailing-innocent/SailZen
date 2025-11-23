# -*- coding: utf-8 -*-
# @file brainstorm.py
# @brief API routes for LLM-powered brainstorming
# @author sailing-innocent
# @date 2025-11-09

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from server.db import g_db_func
from server.service.llm_brainstorm_service import BrainstormService

router = APIRouter(prefix="/api/v1/brainstorm", tags=["brainstorm"])


# ============ Request/Response Schemas ============

class BrainstormRequest(BaseModel):
    work_id: UUID
    existing_knowledge: Optional[List[str]] = None
    constraints: Optional[str] = None
    count: int = Field(default=3, ge=1, le=10)


class WorldElementRequest(BrainstormRequest):
    element_type: str = Field(default="location")  # location, item, concept


class ElaborateRequest(BaseModel):
    work_id: UUID
    idea: str
    context: Optional[str] = None


class ConnectionRequest(BaseModel):
    work_id: UUID
    entity_ids: List[UUID]


class BrainstormSuggestion(BaseModel):
    id: str
    type: str  # entity | event | relation
    title: str
    description: str
    rationale: str
    suggested_properties: dict


class BrainstormResponse(BaseModel):
    suggestions: List[BrainstormSuggestion]
    count: int


class ElaborateResponse(BaseModel):
    elaboration: str
    original_idea: str


# ============ Dependency ============

def get_brainstorm_service(db: Session = Depends(g_db_func)):
    return BrainstormService(db)


# ============ Endpoints ============

@router.post("/characters", response_model=BrainstormResponse)
async def brainstorm_characters(
    request: BrainstormRequest,
    service: BrainstormService = Depends(get_brainstorm_service)
):
    """Generate character ideas using LLM
    
    Generates creative character suggestions based on work context,
    existing knowledge, and optional user constraints.
    """
    try:
        suggestions = await service.brainstorm_characters(
            work_id=request.work_id,
            existing_knowledge=request.existing_knowledge,
            constraints=request.constraints,
            count=request.count
        )
        
        return BrainstormResponse(
            suggestions=suggestions,
            count=len(suggestions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brainstorm failed: {str(e)}")


@router.post("/plot-points", response_model=BrainstormResponse)
async def brainstorm_plot_points(
    request: BrainstormRequest,
    service: BrainstormService = Depends(get_brainstorm_service)
):
    """Generate plot point ideas using LLM
    
    Generates creative plot suggestions that fit the work's narrative,
    considering existing events and characters.
    """
    try:
        suggestions = await service.brainstorm_plot_points(
            work_id=request.work_id,
            existing_knowledge=request.existing_knowledge,
            constraints=request.constraints,
            count=request.count
        )
        
        return BrainstormResponse(
            suggestions=suggestions,
            count=len(suggestions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brainstorm failed: {str(e)}")


@router.post("/world-elements", response_model=BrainstormResponse)
async def brainstorm_world_elements(
    request: WorldElementRequest,
    service: BrainstormService = Depends(get_brainstorm_service)
):
    """Generate world-building elements (locations, items, concepts)
    
    Creates world-building suggestions for locations, items, or concepts
    that enhance the story's setting and atmosphere.
    """
    try:
        suggestions = await service.brainstorm_world_elements(
            work_id=request.work_id,
            element_type=request.element_type,
            existing_knowledge=request.existing_knowledge,
            constraints=request.constraints,
            count=request.count
        )
        
        return BrainstormResponse(
            suggestions=suggestions,
            count=len(suggestions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Brainstorm failed: {str(e)}")


@router.post("/elaborate", response_model=ElaborateResponse)
async def elaborate_idea(
    request: ElaborateRequest,
    service: BrainstormService = Depends(get_brainstorm_service)
):
    """Elaborate on a seed idea with detailed description
    
    Takes a simple idea and expands it into a rich, detailed description
    with background, characteristics, and narrative purpose.
    """
    try:
        result = await service.elaborate_idea(
            work_id=request.work_id,
            idea=request.idea,
            context=request.context
        )
        
        return ElaborateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elaboration failed: {str(e)}")


@router.post("/connections", response_model=BrainstormResponse)
async def find_connections(
    request: ConnectionRequest,
    service: BrainstormService = Depends(get_brainstorm_service)
):
    """Suggest relationships between existing elements
    
    Analyzes selected entities and suggests meaningful relationships
    and interactions that could enrich the story.
    """
    try:
        if len(request.entity_ids) < 2:
            raise HTTPException(
                status_code=400, 
                detail="At least 2 entities required to find connections"
            )
        
        suggestions = await service.find_connections(
            work_id=request.work_id,
            entity_ids=request.entity_ids
        )
        
        return BrainstormResponse(
            suggestions=suggestions,
            count=len(suggestions)
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection search failed: {str(e)}")

