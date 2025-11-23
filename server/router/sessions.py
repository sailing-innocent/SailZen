# -*- coding: utf-8 -*-
# @file sessions.py
# @brief REST API for collaborative editing sessions

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.data.schemas import (
    SessionCreate,
    SessionResponse,
    SessionStateUpdate,
    SessionDiffResponse,
    DiffEntity,
    AnnotationBatchResponse,
    AnnotationItemResponse,
    LLMSuggestionRequest,
    LLMSuggestionResponse,
)
from server.service.session_service import SessionService
from server.service.annotation_service import AnnotationService
from server.service.llm_service import get_llm_service
from server.model.annotation import AnnotationItem


router = APIRouter(prefix="/api/v1/collab", tags=["collaborative_sessions"])


def get_db(db: Session = Depends(g_db_func)):
    return db


@router.post(
    "/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED
)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """Create a new collaborative editing session"""
    service = SessionService(db)

    try:
        session = service.create_session(
            edition_id=payload.edition_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            created_by=payload.created_by,
            lock_scope=payload.lock_scope,
            meta_data=payload.meta_data,
        )
        db.commit()
        return SessionResponse.model_validate(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID, db: Session = Depends(get_db)):
    """Get session details"""
    service = SessionService(db)
    session = service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse.model_validate(session)


@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    edition_id: Optional[UUID] = None,
    created_by: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List active sessions"""
    service = SessionService(db)
    sessions = service.get_active_sessions(edition_id=edition_id, created_by=created_by)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.put("/sessions/{session_id}/state", response_model=SessionResponse)
def update_session_state(
    session_id: UUID, payload: SessionStateUpdate, db: Session = Depends(get_db)
):
    """Update session state"""
    service = SessionService(db)

    try:
        session = service.update_session_state(
            session_id=session_id,
            state=payload.state,
            state_reason=payload.state_reason,
        )
        db.commit()
        return SessionResponse.model_validate(session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/close", response_model=SessionResponse)
def close_session(
    session_id: UUID, reason: Optional[str] = None, db: Session = Depends(get_db)
):
    """Close a session"""
    service = SessionService(db)

    try:
        session = service.close_session(session_id=session_id, reason=reason)
        db.commit()
        return SessionResponse.model_validate(session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/sessions/{session_id}/llm-suggestions", response_model=LLMSuggestionResponse
)
async def request_llm_suggestions(
    session_id: UUID, payload: LLMSuggestionRequest, db: Session = Depends(get_db)
):
    """Request LLM to generate entity extraction suggestions for a session"""
    session_service = SessionService(db)
    annotation_service = AnnotationService(db)

    # Verify session exists
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # Get LLM service
        llm_service = get_llm_service()

        # Prepare context
        context_data = session_service.prepare_context(session_id)
        context_text = payload.context or context_data.get("context_text", "")

        # Call LLM to extract entities
        entities = await llm_service.extract_entities(
            text=payload.text, context=context_text
        )

        # Create annotation batch
        batch = annotation_service.create_batch(
            edition_id=session.edition_id,
            batch_type="llm_suggestion",
            source=llm_service.model,
            session_id=session_id,
            created_by="llm",
            notes=f"LLM entity extraction from session {session_id}",
        )

        # Create annotation items from LLM results
        node_id = payload.node_id or session.target_id
        items = annotation_service.create_items_from_llm_entities(
            batch_id=batch.id, node_id=node_id, entities=entities
        )

        # Update session state
        session_service.update_session_state(session_id, "has_draft")

        db.commit()

        # Return response
        return LLMSuggestionResponse(
            batch_id=batch.id,
            suggestions=[AnnotationItemResponse.model_validate(item) for item in items],
            meta={"entity_count": len(items), "model": llm_service.model},
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"LLM service not available: {e}")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to generate suggestions: {e}"
        )


@router.get("/sessions/{session_id}/diff", response_model=SessionDiffResponse)
def get_session_diff(session_id: UUID, db: Session = Depends(get_db)):
    """Get diff view of all suggestions in a session"""
    session_service = SessionService(db)
    annotation_service = AnnotationService(db)

    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all batches for this session
    batches = annotation_service.get_session_batches(session_id)

    # Get all items from all batches
    all_items = []
    for batch in batches:
        items = annotation_service.get_batch_items(batch.id)
        all_items.extend(items)

    # Convert items to diff entities
    suggestions = []
    approved_count = 0
    rejected_count = 0
    pending_count = 0

    for item in all_items:
        if item.target_type == "entity":
            payload = item.payload
            suggestions.append(
                DiffEntity(
                    annotation_item_id=item.id,
                    canonical_name=payload.get("canonical_name", ""),
                    entity_type=payload.get("entity_type", ""),
                    aliases=payload.get("aliases", []),
                    first_mention_text=payload.get("first_mention_text", ""),
                    confidence=float(item.confidence or 0.0),
                    status=item.status,
                    span_id=item.span_id,
                )
            )

            if item.status == "approved":
                approved_count += 1
            elif item.status == "rejected":
                rejected_count += 1
            else:
                pending_count += 1

    return SessionDiffResponse(
        session_id=session.id,
        session_state=session.state,
        batches=[AnnotationBatchResponse.model_validate(b) for b in batches],
        suggestions=suggestions,
        approved_count=approved_count,
        rejected_count=rejected_count,
        pending_count=pending_count,
    )


@router.put("/annotation-items/{item_id}/status", response_model=AnnotationItemResponse)
def update_item_status(item_id: UUID, status: str, db: Session = Depends(get_db)):
    """Approve or reject an annotation item"""
    if status not in ["approved", "rejected"]:
        raise HTTPException(
            status_code=400, detail="Status must be 'approved' or 'rejected'"
        )

    service = AnnotationService(db)

    try:
        item = service.update_item_status(item_id, status)
        db.commit()
        return AnnotationItemResponse.model_validate(item)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
