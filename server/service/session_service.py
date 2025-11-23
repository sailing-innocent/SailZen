# -*- coding: utf-8 -*-
# @file session_service.py
# @brief Service for managing collaborative editing sessions

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from server.model.session import CollabSession
from server.model.document_node import DocumentNode, TextSpan
from server.model.entity import Entity


class SessionService:
    """Service for managing collaborative editing sessions"""

    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        edition_id: UUID,
        target_type: str,
        target_id: UUID,
        created_by: str,
        lock_scope: str = "node",
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> CollabSession:
        """Create a new collaborative session

        Args:
            edition_id: Edition being edited
            target_type: Type of target (node, entity, relation, event)
            target_id: ID of the target
            created_by: User/system identifier
            lock_scope: Scope of the lock (node, entity, span, edition)
            meta_data: Additional metadata

        Returns:
            Created CollabSession
        """
        # Check if there's already an active session on this target
        existing = (
            self.db.query(CollabSession)
            .filter(
                CollabSession.target_type == target_type,
                CollabSession.target_id == target_id,
                CollabSession.state.in_(["active", "has_draft"]),
            )
            .first()
        )

        if existing:
            raise ValueError(
                f"Target {target_type}:{target_id} already has an active session: {existing.id}"
            )

        session = CollabSession(
            edition_id=edition_id,
            target_type=target_type,
            target_id=target_id,
            created_by=created_by,
            lock_scope=lock_scope,
            state="active",
            meta_data=meta_data or {},
        )

        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, session_id: UUID) -> Optional[CollabSession]:
        """Get session by ID"""
        return (
            self.db.query(CollabSession).filter(CollabSession.id == session_id).first()
        )

    def update_session_state(
        self, session_id: UUID, state: str, state_reason: Optional[str] = None
    ) -> CollabSession:
        """Update session state

        Args:
            session_id: Session ID
            state: New state (active, has_draft, committed, closed, needs_merge)
            state_reason: Optional reason for state change

        Returns:
            Updated session
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.state = state
        if state_reason:
            session.state_reason = state_reason
        session.updated_at = datetime.utcnow()

        if state == "closed":
            session.closed_at = datetime.utcnow()

        self.db.flush()
        return session

    def close_session(
        self, session_id: UUID, reason: Optional[str] = None
    ) -> CollabSession:
        """Close a session

        Args:
            session_id: Session ID
            reason: Optional reason for closing

        Returns:
            Closed session
        """
        return self.update_session_state(session_id, "closed", reason)

    def get_active_sessions(
        self, edition_id: Optional[UUID] = None, created_by: Optional[str] = None
    ) -> list[CollabSession]:
        """Get active sessions

        Args:
            edition_id: Filter by edition
            created_by: Filter by creator

        Returns:
            List of active sessions
        """
        query = self.db.query(CollabSession).filter(
            CollabSession.state.in_(["active", "has_draft"])
        )

        if edition_id:
            query = query.filter(CollabSession.edition_id == edition_id)

        if created_by:
            query = query.filter(CollabSession.created_by == created_by)

        return query.order_by(CollabSession.created_at.desc()).all()

    def prepare_context(
        self, session_id: UUID, include_surrounding: int = 3
    ) -> Dict[str, Any]:
        """Prepare context for LLM based on session target

        Args:
            session_id: Session ID
            include_surrounding: Number of surrounding nodes/spans to include

        Returns:
            Context dict with text, entities, etc.
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        context = {
            "session_id": str(session.id),
            "target_type": session.target_type,
            "target_id": str(session.target_id),
            "text": "",
            "context_text": "",
            "entities": [],
        }

        # Gather context based on target type
        if session.target_type == "node":
            node = (
                self.db.query(DocumentNode)
                .filter(DocumentNode.id == session.target_id)
                .first()
            )
            if node:
                context["text"] = node.raw_text or ""
                context["node_title"] = node.title
                context["node_label"] = node.label

                # Get surrounding nodes for context
                if node.parent_id:
                    siblings = (
                        self.db.query(DocumentNode)
                        .filter(
                            DocumentNode.parent_id == node.parent_id,
                            DocumentNode.id != node.id,
                        )
                        .order_by(DocumentNode.sort_index)
                        .limit(include_surrounding * 2)
                        .all()
                    )
                    context["context_text"] = "\n\n".join(
                        [s.raw_text or "" for s in siblings if s.raw_text]
                    )

                # Get entities mentioned in this node
                spans = (
                    self.db.query(TextSpan).filter(TextSpan.node_id == node.id).all()
                )
                entity_ids = set()
                for span in spans:
                    for mention in span.entity_mentions:
                        entity_ids.add(mention.entity_id)

                if entity_ids:
                    entities = (
                        self.db.query(Entity).filter(Entity.id.in_(entity_ids)).all()
                    )
                    context["entities"] = [
                        {
                            "id": str(e.id),
                            "canonical_name": e.canonical_name,
                            "entity_type": e.entity_type,
                        }
                        for e in entities
                    ]

        elif session.target_type == "entity":
            entity = (
                self.db.query(Entity).filter(Entity.id == session.target_id).first()
            )
            if entity:
                context["entity_name"] = entity.canonical_name
                context["entity_type"] = entity.entity_type
                context["description"] = entity.description or ""

        return context
