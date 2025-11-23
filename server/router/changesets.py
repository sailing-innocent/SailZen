# -*- coding: utf-8 -*-
# @file changesets.py
# @brief REST API for change sets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from server.db import g_db_func
from server.data.schemas import (
    ChangeSetResponse,
    ChangeItemResponse,
    CommitRequest,
)
from server.service.changeset_service import ChangeSetService
from server.service.session_service import SessionService


router = APIRouter(prefix="/api/v1", tags=["changesets"])


def get_db(db: Session = Depends(g_db_func)):
    return db


@router.post(
    "/collab/sessions/{session_id}/commit",
    response_model=ChangeSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def commit_session(
    session_id: UUID, payload: CommitRequest, db: Session = Depends(get_db)
):
    """Commit a session by generating a change set from approved annotation items"""
    session_service = SessionService(db)
    changeset_service = ChangeSetService(db)

    # Verify session exists
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not payload.batch_ids:
        raise HTTPException(status_code=400, detail="At least one batch_id is required")

    try:
        # Generate change set from first batch (for MVP, we process one batch)
        # In production, you'd combine multiple batches
        batch_id = payload.batch_ids[0]

        changeset = changeset_service.generate_changeset_from_annotations(
            batch_id=batch_id, session_id=session_id, created_by=session.created_by
        )

        # Update session state
        session_service.update_session_state(
            session_id, "committed", "Change set generated"
        )

        db.commit()

        return ChangeSetResponse.model_validate(changeset)

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to commit session: {e}")


@router.get("/change-sets/{changeset_id}", response_model=ChangeSetResponse)
def get_changeset(changeset_id: UUID, db: Session = Depends(get_db)):
    """Get change set details"""
    service = ChangeSetService(db)
    changeset = service.get_changeset(changeset_id)

    if not changeset:
        raise HTTPException(status_code=404, detail="Change set not found")

    return ChangeSetResponse.model_validate(changeset)


@router.get(
    "/change-sets/{changeset_id}/items", response_model=List[ChangeItemResponse]
)
def get_changeset_items(changeset_id: UUID, db: Session = Depends(get_db)):
    """Get all items in a change set"""
    service = ChangeSetService(db)
    items = service.get_changeset_items(changeset_id)

    return [ChangeItemResponse.model_validate(item) for item in items]


@router.put("/change-sets/{changeset_id}/apply", response_model=ChangeSetResponse)
def apply_changeset(changeset_id: UUID, db: Session = Depends(get_db)):
    """Apply a change set to the database"""
    service = ChangeSetService(db)

    try:
        changeset = service.apply_changeset(changeset_id)
        db.commit()
        return ChangeSetResponse.model_validate(changeset)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply change set: {e}")


@router.get("/change-sets", response_model=List[ChangeSetResponse])
def list_changesets(
    edition_id: UUID = None, session_id: UUID = None, db: Session = Depends(get_db)
):
    """List change sets"""
    from server.model.changeset import ChangeSet

    query = db.query(ChangeSet)

    if edition_id:
        query = query.filter(ChangeSet.edition_id == edition_id)

    if session_id:
        query = query.filter(ChangeSet.session_id == session_id)

    changesets = query.order_by(ChangeSet.created_at.desc()).limit(100).all()

    return [ChangeSetResponse.model_validate(cs) for cs in changesets]
