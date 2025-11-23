# -*- coding: utf-8 -*-
# @file review_service.py
# @brief Service for managing review tasks

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from server.model.review import ReviewTask
from server.model.changeset import ChangeSet
from server.service.changeset_service import ChangeSetService


class ReviewService:
    """Service for managing review tasks"""

    def __init__(self, db: Session):
        self.db = db
        self.changeset_service = ChangeSetService(db)

    def create_review_task(
        self, change_set_id: UUID, reviewer: str, comments: Optional[str] = None
    ) -> ReviewTask:
        """Create a review task for a change set

        Args:
            change_set_id: Change set to review
            reviewer: Reviewer identifier
            comments: Optional initial comments

        Returns:
            Created ReviewTask
        """
        task = ReviewTask(
            change_set_id=change_set_id,
            reviewer=reviewer,
            status="pending",
            comments=comments,
        )

        self.db.add(task)
        self.db.flush()
        return task

    def get_review_task(self, task_id: UUID) -> Optional[ReviewTask]:
        """Get review task by ID"""
        return self.db.query(ReviewTask).filter(ReviewTask.id == task_id).first()

    def approve_review(
        self, task_id: UUID, comments: Optional[str] = None, auto_apply: bool = True
    ) -> ReviewTask:
        """Approve a review task

        Args:
            task_id: Review task ID
            comments: Optional approval comments
            auto_apply: Whether to automatically apply the change set

        Returns:
            Approved ReviewTask
        """
        task = self.get_review_task(task_id)
        if not task:
            raise ValueError(f"Review task {task_id} not found")

        if task.status != "pending":
            raise ValueError(
                f"Review task {task_id} is not pending (status: {task.status})"
            )

        task.status = "approved"
        task.decision = "approve"
        task.decided_at = datetime.utcnow()
        if comments:
            task.comments = comments

        self.db.flush()

        # Auto-apply change set if requested
        if auto_apply:
            self.changeset_service.apply_changeset(task.change_set_id)

        return task

    def reject_review(
        self, task_id: UUID, comments: Optional[str] = None
    ) -> ReviewTask:
        """Reject a review task

        Args:
            task_id: Review task ID
            comments: Optional rejection reason

        Returns:
            Rejected ReviewTask
        """
        task = self.get_review_task(task_id)
        if not task:
            raise ValueError(f"Review task {task_id} not found")

        if task.status != "pending":
            raise ValueError(
                f"Review task {task_id} is not pending (status: {task.status})"
            )

        task.status = "rejected"
        task.decision = "reject"
        task.decided_at = datetime.utcnow()
        if comments:
            task.comments = comments

        self.db.flush()

        # Mark change set as failed
        changeset = (
            self.db.query(ChangeSet).filter(ChangeSet.id == task.change_set_id).first()
        )
        if changeset:
            changeset.status = "failed"
            changeset.error_message = (
                f"Rejected by reviewer: {comments or 'No reason provided'}"
            )

        return task

    def get_pending_reviews(self, reviewer: Optional[str] = None) -> List[ReviewTask]:
        """Get pending review tasks

        Args:
            reviewer: Optional reviewer filter

        Returns:
            List of pending review tasks
        """
        query = self.db.query(ReviewTask).filter(ReviewTask.status == "pending")

        if reviewer:
            query = query.filter(ReviewTask.reviewer == reviewer)

        return query.order_by(ReviewTask.created_at.desc()).all()
