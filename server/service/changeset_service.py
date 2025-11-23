# -*- coding: utf-8 -*-
# @file changeset_service.py
# @brief Service for managing change sets and applying changes

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session

from server.model.changeset import ChangeSet, ChangeItem
from server.model.annotation import AnnotationBatch, AnnotationItem
from server.model.entity import Entity, EntityAlias, EntityMention
from server.model.document_node import TextSpan


class ChangeSetService:
    """Service for generating and applying change sets"""

    def __init__(self, db: Session):
        self.db = db

    def create_changeset(
        self,
        edition_id: UUID,
        source: str,
        session_id: Optional[UUID] = None,
        created_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> ChangeSet:
        """Create a new change set

        Args:
            edition_id: Edition ID
            source: Source identifier (manual, llm_auto, collaboration_commit)
            session_id: Optional session ID
            created_by: Creator identifier
            reason: Optional reason for changes

        Returns:
            Created ChangeSet
        """
        changeset = ChangeSet(
            edition_id=edition_id,
            session_id=session_id,
            source=source,
            reason=reason,
            status="pending",
            created_by=created_by,
        )

        self.db.add(changeset)
        self.db.flush()
        return changeset

    def create_change_item(
        self,
        change_set_id: UUID,
        target_table: str,
        operation: str,
        target_id: Optional[UUID] = None,
        column_name: Optional[str] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        span_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> ChangeItem:
        """Create a change item

        Args:
            change_set_id: Parent change set ID
            target_table: Table being modified (entities, entity_mentions, etc.)
            operation: Operation type (insert, update, delete)
            target_id: ID of affected row
            column_name: For updates, which column changed
            old_value: Previous value (for rollback)
            new_value: New value
            span_id: Optional span reference
            notes: Optional notes

        Returns:
            Created ChangeItem
        """
        item = ChangeItem(
            change_set_id=change_set_id,
            target_table=target_table,
            target_id=target_id,
            operation=operation,
            column_name=column_name,
            old_value=old_value,
            new_value=new_value,
            span_id=span_id,
            notes=notes,
        )

        self.db.add(item)
        self.db.flush()
        return item

    def generate_changeset_from_annotations(
        self,
        batch_id: UUID,
        session_id: Optional[UUID] = None,
        created_by: Optional[str] = None,
    ) -> ChangeSet:
        """Generate a change set from approved annotation items

        Args:
            batch_id: Annotation batch ID
            session_id: Optional session ID
            created_by: Creator identifier

        Returns:
            Generated ChangeSet with items
        """
        batch = (
            self.db.query(AnnotationBatch)
            .filter(AnnotationBatch.id == batch_id)
            .first()
        )
        if not batch:
            raise ValueError(f"Annotation batch {batch_id} not found")

        # Get approved items
        approved_items = (
            self.db.query(AnnotationItem)
            .filter(
                AnnotationItem.batch_id == batch_id, AnnotationItem.status == "approved"
            )
            .all()
        )

        if not approved_items:
            raise ValueError(f"No approved items in batch {batch_id}")

        # Create change set
        changeset = self.create_changeset(
            edition_id=batch.edition_id,
            source="collaboration_commit",
            session_id=session_id,
            created_by=created_by,
            reason=f"Applying approved annotations from batch {batch_id}",
        )

        # Generate change items for each approved annotation
        for item in approved_items:
            if item.target_type == "entity":
                self._generate_entity_changes(changeset.id, item)

        return changeset

    def _generate_entity_changes(
        self, change_set_id: UUID, annotation_item: AnnotationItem
    ):
        """Generate change items for entity annotations

        Args:
            change_set_id: Change set ID
            annotation_item: Annotation item with entity data
        """
        payload = annotation_item.payload

        # Check if entity already exists
        canonical_name = payload.get("canonical_name")
        entity_type = payload.get("entity_type")

        existing_entity = None
        if annotation_item.target_id:
            existing_entity = (
                self.db.query(Entity)
                .filter(Entity.id == annotation_item.target_id)
                .first()
            )

        if existing_entity:
            # Update operation
            old_data = {
                "canonical_name": existing_entity.canonical_name,
                "entity_type": existing_entity.entity_type,
                "description": existing_entity.description,
            }
            new_data = {
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "description": payload.get("description", ""),
            }

            self.create_change_item(
                change_set_id=change_set_id,
                target_table="entities",
                operation="update",
                target_id=existing_entity.id,
                old_value=old_data,
                new_value=new_data,
                span_id=annotation_item.span_id,
            )
        else:
            # Insert operation for new entity
            new_data = {
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "description": payload.get("description", ""),
                "aliases": payload.get("aliases", []),
            }

            self.create_change_item(
                change_set_id=change_set_id,
                target_table="entities",
                operation="insert",
                new_value=new_data,
                span_id=annotation_item.span_id,
                notes=f"New entity from annotation {annotation_item.id}",
            )

            # Also create change item for mention
            if annotation_item.span_id:
                self.create_change_item(
                    change_set_id=change_set_id,
                    target_table="entity_mentions",
                    operation="insert",
                    new_value={
                        "entity_placeholder": canonical_name,  # Will be resolved during apply
                        "span_id": str(annotation_item.span_id),
                        "mention_type": "explicit",
                    },
                    span_id=annotation_item.span_id,
                )

    def apply_changeset(self, changeset_id: UUID) -> ChangeSet:
        """Apply a change set to the database

        Args:
            changeset_id: Change set ID

        Returns:
            Applied ChangeSet
        """
        changeset = (
            self.db.query(ChangeSet).filter(ChangeSet.id == changeset_id).first()
        )
        if not changeset:
            raise ValueError(f"Change set {changeset_id} not found")

        if changeset.status != "pending":
            raise ValueError(
                f"Change set {changeset_id} is not pending (status: {changeset.status})"
            )

        try:
            # Get all change items
            items = (
                self.db.query(ChangeItem)
                .filter(ChangeItem.change_set_id == changeset_id)
                .all()
            )

            # Track created entities for resolving references
            entity_map = {}  # canonical_name -> Entity

            # Apply changes
            for item in items:
                if item.target_table == "entities":
                    if item.operation == "insert":
                        self._apply_entity_insert(item, entity_map)
                    elif item.operation == "update":
                        self._apply_entity_update(item)

                elif item.target_table == "entity_mentions":
                    if item.operation == "insert":
                        self._apply_mention_insert(item, entity_map)

            # Mark as applied
            changeset.status = "applied"
            changeset.applied_at = datetime.utcnow()
            self.db.flush()

            return changeset

        except Exception as e:
            changeset.status = "failed"
            changeset.error_message = str(e)
            self.db.flush()
            raise

    def _apply_entity_insert(self, item: ChangeItem, entity_map: Dict[str, Entity]):
        """Apply entity insert operation"""
        new_data = item.new_value

        # Get edition_id from changeset
        changeset = (
            self.db.query(ChangeSet).filter(ChangeSet.id == item.change_set_id).first()
        )

        # Create entity
        entity = Entity(
            canonical_name=new_data["canonical_name"],
            entity_type=new_data["entity_type"],
            description=new_data.get("description", ""),
            edition_id=changeset.edition_id,
            origin_span_id=item.span_id,
            scope="edition",
            status="draft",
        )

        self.db.add(entity)
        self.db.flush()

        # Store in map for later reference
        entity_map[entity.canonical_name] = entity

        # Update change item with actual entity ID
        item.target_id = entity.id

        # Create aliases
        for alias in new_data.get("aliases", []):
            alias_obj = EntityAlias(entity_id=entity.id, alias=alias)
            self.db.add(alias_obj)

    def _apply_entity_update(self, item: ChangeItem):
        """Apply entity update operation"""
        entity = self.db.query(Entity).filter(Entity.id == item.target_id).first()
        if not entity:
            raise ValueError(f"Entity {item.target_id} not found")

        new_data = item.new_value

        if "canonical_name" in new_data:
            entity.canonical_name = new_data["canonical_name"]
        if "entity_type" in new_data:
            entity.entity_type = new_data["entity_type"]
        if "description" in new_data:
            entity.description = new_data["description"]

    def _apply_mention_insert(self, item: ChangeItem, entity_map: Dict[str, Entity]):
        """Apply entity mention insert operation"""
        new_data = item.new_value

        # Resolve entity reference
        entity = None
        if "entity_placeholder" in new_data:
            entity = entity_map.get(new_data["entity_placeholder"])
        elif "entity_id" in new_data:
            entity_id = UUID(new_data["entity_id"])
            entity = self.db.query(Entity).filter(Entity.id == entity_id).first()

        if not entity:
            raise ValueError(f"Cannot resolve entity for mention: {new_data}")

        span_id = UUID(new_data["span_id"])

        # Check if mention already exists
        existing = (
            self.db.query(EntityMention)
            .filter(
                EntityMention.entity_id == entity.id, EntityMention.span_id == span_id
            )
            .first()
        )

        if not existing:
            mention = EntityMention(
                entity_id=entity.id,
                span_id=span_id,
                mention_type=new_data.get("mention_type", "explicit"),
            )
            self.db.add(mention)

    def get_changeset(self, changeset_id: UUID) -> Optional[ChangeSet]:
        """Get change set by ID"""
        return self.db.query(ChangeSet).filter(ChangeSet.id == changeset_id).first()

    def get_changeset_items(self, changeset_id: UUID) -> List[ChangeItem]:
        """Get all items in a change set"""
        return (
            self.db.query(ChangeItem)
            .filter(ChangeItem.change_set_id == changeset_id)
            .all()
        )
