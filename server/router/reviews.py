# -*- coding: utf-8 -*-
# @file reviews.py
# @brief REST API for review tasks

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.data.schemas import (
    ReviewTaskCreate,
    ReviewTaskResponse,
    ReviewDecision,
)
from server.service.review_service import ReviewService


router = APIRouter(prefix="/api/v1/review-tasks", tags=["reviews"])


def get_db(db: Session = Depends(g_db_func)):
    return db


@router.post("", response_model=ReviewTaskResponse, status_code=status.HTTP_201_CREATED)
def create_review_task(payload: ReviewTaskCreate, db: Session = Depends(get_db)):
    """Create a review task for a change set"""
    service = ReviewService(db)

    task = service.create_review_task(
        change_set_id=payload.change_set_id,
        reviewer=payload.reviewer,
        comments=payload.comments,
    )

    db.commit()
    return ReviewTaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=ReviewTaskResponse)
def get_review_task(task_id: UUID, db: Session = Depends(get_db)):
    """Get review task details"""
    service = ReviewService(db)
    task = service.get_review_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")

    return ReviewTaskResponse.model_validate(task)


@router.post("/{task_id}/approve", response_model=ReviewTaskResponse)
def approve_review(
    task_id: UUID,
    payload: ReviewDecision,
    auto_apply: bool = True,
    db: Session = Depends(get_db),
):
    """Approve a review task and optionally apply the change set"""
    service = ReviewService(db)

    try:
        task = service.approve_review(
            task_id=task_id, comments=payload.comments, auto_apply=auto_apply
        )
        db.commit()
        return ReviewTaskResponse.model_validate(task)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to approve review: {e}")


@router.post("/{task_id}/reject", response_model=ReviewTaskResponse)
def reject_review(
    task_id: UUID, payload: ReviewDecision, db: Session = Depends(get_db)
):
    """Reject a review task"""
    service = ReviewService(db)

    try:
        task = service.reject_review(task_id=task_id, comments=payload.comments)
        db.commit()
        return ReviewTaskResponse.model_validate(task)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ReviewTaskResponse])
def list_pending_reviews(reviewer: Optional[str] = None, db: Session = Depends(get_db)):
    """List pending review tasks"""
    service = ReviewService(db)
    tasks = service.get_pending_reviews(reviewer=reviewer)

    return [ReviewTaskResponse.model_validate(task) for task in tasks]
