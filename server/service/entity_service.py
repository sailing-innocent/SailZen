# -*- coding: utf-8 -*-
# @file entity_service.py
# @brief Service layer for entities and relations
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from server.model.entity import Entity, EntityAlias, EntityMention
from server.model.relation import EntityRelation, RelationEvidence
from server.data.schemas import (
    EntityCreate,
    EntityUpdate,
    EntityResponse,
    EntityAliasCreate,
    EntityAliasResponse,
    EntityMentionCreate,
    EntityMentionUpdate,
    EntityMentionResponse,
    EntityRelationCreate,
    EntityRelationUpdate,
    EntityRelationResponse,
)


class EntityService:
    """Service for managing entities, mentions, and relations"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Entity Methods ============

    def create_entity(self, entity_data: EntityCreate) -> EntityResponse:
        """Create a new entity"""
        db_entity = Entity(**entity_data.model_dump())
        self.db.add(db_entity)
        self.db.commit()
        self.db.refresh(db_entity)
        return EntityResponse.model_validate(db_entity)

    def get_entity(self, entity_id: UUID) -> Optional[EntityResponse]:
        """Get entity by ID"""
        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if entity:
            return EntityResponse.model_validate(entity)
        return None

    def list_entities(
        self,
        edition_id: Optional[UUID] = None,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[EntityResponse]:
        """List entities with optional filters"""
        query = self.db.query(Entity)
        if edition_id:
            query = query.filter(Entity.edition_id == edition_id)
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        entities = query.offset(skip).limit(limit).all()
        return [EntityResponse.model_validate(e) for e in entities]

    def search_entities(self, name_query: str, limit: int = 20) -> List[EntityResponse]:
        """Search entities by name (case-insensitive)"""
        entities = (
            self.db.query(Entity)
            .filter(Entity.canonical_name.ilike(f"%{name_query}%"))
            .limit(limit)
            .all()
        )
        return [EntityResponse.model_validate(e) for e in entities]

    def update_entity(
        self, entity_id: UUID, update_data: EntityUpdate
    ) -> Optional[EntityResponse]:
        """Update entity"""
        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(entity, key, value)

        self.db.commit()
        self.db.refresh(entity)
        return EntityResponse.model_validate(entity)

    def delete_entity(self, entity_id: UUID) -> bool:
        """Delete entity"""
        entity = self.db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            return False

        self.db.delete(entity)
        self.db.commit()
        return True

    # ============ Entity Alias Methods ============

    def create_entity_alias(self, alias_data: EntityAliasCreate) -> EntityAliasResponse:
        """Create a new entity alias"""
        db_alias = EntityAlias(**alias_data.model_dump())
        self.db.add(db_alias)
        self.db.commit()
        self.db.refresh(db_alias)
        return EntityAliasResponse.model_validate(db_alias)

    def get_entity_aliases(self, entity_id: UUID) -> List[EntityAliasResponse]:
        """Get all aliases for an entity"""
        aliases = (
            self.db.query(EntityAlias).filter(EntityAlias.entity_id == entity_id).all()
        )
        return [EntityAliasResponse.model_validate(a) for a in aliases]

    # ============ Entity Mention Methods ============

    def create_entity_mention(
        self, mention_data: EntityMentionCreate
    ) -> EntityMentionResponse:
        """Create a new entity mention"""
        db_mention = EntityMention(**mention_data.model_dump())
        self.db.add(db_mention)
        self.db.commit()
        self.db.refresh(db_mention)
        return EntityMentionResponse.model_validate(db_mention)

    def get_entity_mentions(self, entity_id: UUID) -> List[EntityMentionResponse]:
        """Get all mentions of an entity"""
        mentions = (
            self.db.query(EntityMention)
            .filter(EntityMention.entity_id == entity_id)
            .all()
        )
        return [EntityMentionResponse.model_validate(m) for m in mentions]

    def verify_mention(
        self, mention_id: UUID, verified_by: str
    ) -> Optional[EntityMentionResponse]:
        """Verify an entity mention"""
        mention = (
            self.db.query(EntityMention).filter(EntityMention.id == mention_id).first()
        )
        if not mention:
            return None

        mention.is_verified = True
        mention.verified_by = verified_by
        mention.verified_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(mention)
        return EntityMentionResponse.model_validate(mention)

    # ============ Entity Relation Methods ============

    def create_relation(
        self, relation_data: EntityRelationCreate
    ) -> EntityRelationResponse:
        """Create a new entity relation"""
        db_relation = EntityRelation(**relation_data.model_dump())
        self.db.add(db_relation)
        self.db.commit()
        self.db.refresh(db_relation)
        return EntityRelationResponse.model_validate(db_relation)

    def get_relation(self, relation_id: UUID) -> Optional[EntityRelationResponse]:
        """Get relation by ID"""
        relation = (
            self.db.query(EntityRelation)
            .filter(EntityRelation.id == relation_id)
            .first()
        )
        if relation:
            return EntityRelationResponse.model_validate(relation)
        return None

    def list_relations(
        self,
        entity_id: Optional[UUID] = None,
        relation_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[EntityRelationResponse]:
        """List relations with optional filters"""
        query = self.db.query(EntityRelation)
        if entity_id:
            query = query.filter(
                (EntityRelation.source_entity_id == entity_id)
                | (EntityRelation.target_entity_id == entity_id)
            )
        if relation_type:
            query = query.filter(EntityRelation.relation_type == relation_type)
        relations = query.offset(skip).limit(limit).all()
        return [EntityRelationResponse.model_validate(r) for r in relations]

    def update_relation(
        self, relation_id: UUID, update_data: EntityRelationUpdate
    ) -> Optional[EntityRelationResponse]:
        """Update relation"""
        relation = (
            self.db.query(EntityRelation)
            .filter(EntityRelation.id == relation_id)
            .first()
        )
        if not relation:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(relation, key, value)

        self.db.commit()
        self.db.refresh(relation)
        return EntityRelationResponse.model_validate(relation)

    def delete_relation(self, relation_id: UUID) -> bool:
        """Delete relation"""
        relation = (
            self.db.query(EntityRelation)
            .filter(EntityRelation.id == relation_id)
            .first()
        )
        if not relation:
            return False

        self.db.delete(relation)
        self.db.commit()
        return True

    def add_relation_evidence(
        self,
        relation_id: UUID,
        span_id: UUID,
        confidence: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Add evidence (text span) to a relation"""
        evidence = RelationEvidence(
            relation_id=relation_id, span_id=span_id, confidence=confidence, notes=notes
        )
        self.db.add(evidence)
        self.db.commit()
        return True
