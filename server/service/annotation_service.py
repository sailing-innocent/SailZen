# -*- coding: utf-8 -*-
# @file annotation_service.py
# @brief Service for managing annotation batches and items

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from server.model.annotation import AnnotationBatch, AnnotationItem
from server.model.document_node import TextSpan, DocumentNode


class AnnotationService:
    """Service for managing annotation batches and items"""

    def __init__(self, db: Session):
        self.db = db

    def create_batch(
        self,
        edition_id: UUID,
        batch_type: str,
        source: str,
        session_id: Optional[UUID] = None,
        created_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AnnotationBatch:
        """Create a new annotation batch

        Args:
            edition_id: Edition ID
            batch_type: Type of batch (llm_suggestion, human_draft, merged)
            source: Source identifier (model name, user ID)
            session_id: Optional session ID
            created_by: Creator identifier
            notes: Optional notes

        Returns:
            Created AnnotationBatch
        """
        batch = AnnotationBatch(
            edition_id=edition_id,
            session_id=session_id,
            batch_type=batch_type,
            source=source,
            status="draft",
            created_by=created_by,
            notes=notes,
        )

        self.db.add(batch)
        self.db.flush()
        return batch

    def get_batch(self, batch_id: UUID) -> Optional[AnnotationBatch]:
        """Get batch by ID"""
        return (
            self.db.query(AnnotationBatch)
            .filter(AnnotationBatch.id == batch_id)
            .first()
        )

    def create_item(
        self,
        batch_id: UUID,
        target_type: str,
        payload: Dict[str, Any],
        target_id: Optional[UUID] = None,
        span_id: Optional[UUID] = None,
        confidence: Optional[float] = None,
    ) -> AnnotationItem:
        """Create an annotation item

        Args:
            batch_id: Parent batch ID
            target_type: Type of target (entity, relation, event, node, span)
            payload: Full data payload (JSON)
            target_id: Optional target ID (null for new entities)
            span_id: Optional span ID for text reference
            confidence: Optional confidence score (0.0-1.0)

        Returns:
            Created AnnotationItem
        """
        item = AnnotationItem(
            batch_id=batch_id,
            target_type=target_type,
            target_id=target_id,
            span_id=span_id,
            payload=payload,
            confidence=confidence,
            status="pending",
        )

        self.db.add(item)
        self.db.flush()
        return item

    def create_items_from_llm_entities(
        self, batch_id: UUID, node_id: UUID, entities: List[Dict[str, Any]]
    ) -> List[AnnotationItem]:
        """Create annotation items from LLM entity extraction results

        Args:
            batch_id: Batch ID
            node_id: Node ID where entities were extracted
            entities: List of entity dicts from LLM

        Returns:
            List of created AnnotationItems
        """
        node = self.db.query(DocumentNode).filter(DocumentNode.id == node_id).first()
        if not node:
            raise ValueError(f"Node {node_id} not found")

        items = []
        for entity_data in entities:
            # Try to find or create a span for this entity
            first_mention = entity_data.get("first_mention_text", "")
            span_id = None

            if first_mention and node.raw_text:
                # Find the mention in the text
                start_idx = node.raw_text.find(first_mention)
                if start_idx >= 0:
                    end_idx = start_idx + len(first_mention)

                    # Check if span already exists
                    existing_span = (
                        self.db.query(TextSpan)
                        .filter(
                            TextSpan.node_id == node_id,
                            TextSpan.start_char == start_idx,
                            TextSpan.end_char == end_idx,
                        )
                        .first()
                    )

                    if existing_span:
                        span_id = existing_span.id
                    else:
                        # Create new span
                        new_span = TextSpan(
                            node_id=node_id,
                            span_type="explicit",
                            start_char=start_idx,
                            end_char=end_idx,
                            text_snippet=first_mention,
                            created_by="llm",
                        )
                        self.db.add(new_span)
                        self.db.flush()
                        span_id = new_span.id

            # Create annotation item
            item = self.create_item(
                batch_id=batch_id,
                target_type="entity",
                payload=entity_data,
                span_id=span_id,
                confidence=entity_data.get("confidence", 0.8),
            )
            items.append(item)

        return items

    def update_item_status(self, item_id: UUID, status: str) -> AnnotationItem:
        """Update annotation item status

        Args:
            item_id: Item ID
            status: New status (pending, approved, rejected)

        Returns:
            Updated item
        """
        item = (
            self.db.query(AnnotationItem).filter(AnnotationItem.id == item_id).first()
        )
        if not item:
            raise ValueError(f"Annotation item {item_id} not found")

        item.status = status
        self.db.flush()
        return item

    def get_batch_items(
        self, batch_id: UUID, status: Optional[str] = None
    ) -> List[AnnotationItem]:
        """Get items in a batch

        Args:
            batch_id: Batch ID
            status: Optional status filter

        Returns:
            List of annotation items
        """
        query = self.db.query(AnnotationItem).filter(
            AnnotationItem.batch_id == batch_id
        )

        if status:
            query = query.filter(AnnotationItem.status == status)

        return query.all()

    def get_session_batches(
        self, session_id: UUID, batch_type: Optional[str] = None
    ) -> List[AnnotationBatch]:
        """Get batches for a session

        Args:
            session_id: Session ID
            batch_type: Optional batch type filter

        Returns:
            List of annotation batches
        """
        query = self.db.query(AnnotationBatch).filter(
            AnnotationBatch.session_id == session_id
        )

        if batch_type:
            query = query.filter(AnnotationBatch.batch_type == batch_type)

        return query.order_by(AnnotationBatch.created_at.desc()).all()

    def update_batch_status(self, batch_id: UUID, status: str) -> AnnotationBatch:
        """Update batch status

        Args:
            batch_id: Batch ID
            status: New status (draft, pending, approved, rejected, committed)

        Returns:
            Updated batch
        """
        batch = self.get_batch(batch_id)
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        batch.status = status
        batch.updated_at = datetime.utcnow()
        self.db.flush()
        return batch

    def get_approved_items(self, batch_id: UUID) -> List[AnnotationItem]:
        """Get all approved items in a batch

        Args:
            batch_id: Batch ID

        Returns:
            List of approved annotation items
        """
        return self.get_batch_items(batch_id, status="approved")
