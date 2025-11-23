# -*- coding: utf-8 -*-
# @file work_service.py
# @brief Service layer for works and editions
# @author sailing-innocent
# @date 2025-04-21

from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.model.work import Universe, Work, Edition, EditionFile
from server.model.entity import Entity
from server.model.relation import EntityRelation
from server.model.narrative_event import NarrativeEvent
from server.data.schemas import (
    UniverseCreate,
    UniverseUpdate,
    UniverseResponse,
    WorkCreate,
    WorkUpdate,
    WorkResponse,
    EditionCreate,
    EditionUpdate,
    EditionResponse,
    EntityResponse,
    EntityRelationResponse,
    NarrativeEventResponse,
)


class WorkService:
    """Service for managing works, editions, and universes"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Universe Methods ============

    def create_universe(self, universe_data: UniverseCreate) -> UniverseResponse:
        """Create a new universe"""
        db_universe = Universe(**universe_data.model_dump())
        self.db.add(db_universe)
        self.db.commit()
        self.db.refresh(db_universe)
        return UniverseResponse.model_validate(db_universe)

    def get_universe(self, universe_id: UUID) -> Optional[UniverseResponse]:
        """Get universe by ID"""
        universe = self.db.query(Universe).filter(Universe.id == universe_id).first()
        if universe:
            return UniverseResponse.model_validate(universe)
        return None

    def get_universe_by_slug(self, slug: str) -> Optional[UniverseResponse]:
        """Get universe by slug"""
        universe = self.db.query(Universe).filter(Universe.slug == slug).first()
        if universe:
            return UniverseResponse.model_validate(universe)
        return None

    def list_universes(self, skip: int = 0, limit: int = 20) -> List[UniverseResponse]:
        """List all universes with pagination"""
        universes = self.db.query(Universe).offset(skip).limit(limit).all()
        return [UniverseResponse.model_validate(u) for u in universes]

    def update_universe(
        self, universe_id: UUID, update_data: UniverseUpdate
    ) -> Optional[UniverseResponse]:
        """Update universe"""
        universe = self.db.query(Universe).filter(Universe.id == universe_id).first()
        if not universe:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(universe, key, value)

        self.db.commit()
        self.db.refresh(universe)
        return UniverseResponse.model_validate(universe)

    def delete_universe(self, universe_id: UUID) -> bool:
        """Delete universe"""
        universe = self.db.query(Universe).filter(Universe.id == universe_id).first()
        if not universe:
            return False

        self.db.delete(universe)
        self.db.commit()
        return True

    # ============ Work Methods ============

    def create_work(self, work_data: WorkCreate) -> WorkResponse:
        """Create a new work"""
        db_work = Work(**work_data.model_dump())
        self.db.add(db_work)
        self.db.commit()
        self.db.refresh(db_work)
        return WorkResponse.model_validate(db_work)

    def get_work(self, work_id: UUID) -> Optional[WorkResponse]:
        """Get work by ID"""
        work = self.db.query(Work).filter(Work.id == work_id).first()
        if work:
            return WorkResponse.model_validate(work)
        return None

    def get_work_by_slug(self, slug: str) -> Optional[WorkResponse]:
        """Get work by slug"""
        work = self.db.query(Work).filter(Work.slug == slug).first()
        if work:
            return WorkResponse.model_validate(work)
        return None

    def list_works(
        self, skip: int = 0, limit: int = 20, status: Optional[str] = None
    ) -> List[WorkResponse]:
        """List works with pagination and optional status filter"""
        query = self.db.query(Work)
        if status:
            query = query.filter(Work.status == status)
        works = query.offset(skip).limit(limit).all()
        return [WorkResponse.model_validate(w) for w in works]

    def update_work(
        self, work_id: UUID, update_data: WorkUpdate
    ) -> Optional[WorkResponse]:
        """Update work"""
        work = self.db.query(Work).filter(Work.id == work_id).first()
        if not work:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(work, key, value)

        self.db.commit()
        self.db.refresh(work)
        return WorkResponse.model_validate(work)

    def delete_work(self, work_id: UUID) -> bool:
        """Delete work"""
        work = self.db.query(Work).filter(Work.id == work_id).first()
        if not work:
            return False

        self.db.delete(work)
        self.db.commit()
        return True

    # ============ Edition Methods ============

    def create_edition(self, edition_data: EditionCreate) -> EditionResponse:
        """Create a new edition"""
        db_edition = Edition(**edition_data.model_dump())
        self.db.add(db_edition)
        self.db.commit()
        self.db.refresh(db_edition)
        return EditionResponse.model_validate(db_edition)

    def get_edition(self, edition_id: UUID) -> Optional[EditionResponse]:
        """Get edition by ID"""
        edition = self.db.query(Edition).filter(Edition.id == edition_id).first()
        if edition:
            return EditionResponse.model_validate(edition)
        return None

    def list_editions(
        self, work_id: Optional[UUID] = None, skip: int = 0, limit: int = 20
    ) -> List[EditionResponse]:
        """List editions with optional work filter"""
        query = self.db.query(Edition)
        if work_id:
            query = query.filter(Edition.work_id == work_id)
        editions = query.offset(skip).limit(limit).all()
        return [EditionResponse.model_validate(e) for e in editions]

    def update_edition(
        self, edition_id: UUID, update_data: EditionUpdate
    ) -> Optional[EditionResponse]:
        """Update edition"""
        edition = self.db.query(Edition).filter(Edition.id == edition_id).first()
        if not edition:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(edition, key, value)

        self.db.commit()
        self.db.refresh(edition)
        return EditionResponse.model_validate(edition)

    def delete_edition(self, edition_id: UUID) -> bool:
        """Delete edition"""
        edition = self.db.query(Edition).filter(Edition.id == edition_id).first()
        if not edition:
            return False

        self.db.delete(edition)
        self.db.commit()
        return True

    def add_edition_file(
        self,
        edition_id: UUID,
        storage_uri: str,
        file_role: str = "source",
        checksum: Optional[str] = None,
        encoding: str = "utf-8",
    ) -> bool:
        """Add a file reference to an edition"""
        edition = self.db.query(Edition).filter(Edition.id == edition_id).first()
        if not edition:
            return False

        edition_file = EditionFile(
            edition_id=edition_id,
            file_role=file_role,
            storage_uri=storage_uri,
            checksum=checksum,
            encoding=encoding,
        )
        self.db.add(edition_file)
        self.db.commit()
        return True

    # ============ Work-Level Knowledge Query Methods ============

    def list_work_entities(
        self,
        work_id: UUID,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[EntityResponse]:
        """List all entities at work level (not bound to specific edition)"""
        query = self.db.query(Entity).filter(Entity.work_id == work_id)
        
        # Filter for work-level entities (edition_id is NULL)
        query = query.filter(Entity.edition_id.is_(None))
        
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        
        query = query.order_by(Entity.entity_type, Entity.canonical_name)
        entities = query.offset(skip).limit(limit).all()
        return [EntityResponse.model_validate(e) for e in entities]

    def list_work_relations(
        self,
        work_id: UUID,
        relation_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[EntityRelationResponse]:
        """List all relations at work level (not bound to specific edition)"""
        query = self.db.query(EntityRelation).filter(EntityRelation.work_id == work_id)
        
        # Filter for work-level relations (edition_id is NULL)
        query = query.filter(EntityRelation.edition_id.is_(None))
        
        if relation_type:
            query = query.filter(EntityRelation.relation_type == relation_type)
        
        relations = query.offset(skip).limit(limit).all()
        return [EntityRelationResponse.model_validate(r) for r in relations]

    def list_work_events(
        self,
        work_id: UUID,
        event_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[NarrativeEventResponse]:
        """List all narrative events at work level (not bound to specific edition)"""
        query = self.db.query(NarrativeEvent).filter(NarrativeEvent.work_id == work_id)
        
        # Filter for work-level events (edition_id is NULL)
        query = query.filter(NarrativeEvent.edition_id.is_(None))
        
        if event_type:
            query = query.filter(NarrativeEvent.event_type == event_type)
        
        query = query.order_by(
            NarrativeEvent.chronology_order.asc().nulls_last(),
            NarrativeEvent.created_at.asc()
        )
        
        events = query.offset(skip).limit(limit).all()
        return [NarrativeEventResponse.model_validate(e) for e in events]

    def get_work_knowledge_summary(self, work_id: UUID) -> dict:
        """Get a summary of all work-level knowledge"""
        # Count work-level entities by type
        entity_counts = {}
        entities = self.db.query(Entity.entity_type, Entity.id).filter(
            Entity.work_id == work_id,
            Entity.edition_id.is_(None)
        ).all()
        
        for entity_type, _ in entities:
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        
        # Count work-level relations
        relation_count = self.db.query(EntityRelation).filter(
            EntityRelation.work_id == work_id,
            EntityRelation.edition_id.is_(None)
        ).count()
        
        # Count work-level events
        event_count = self.db.query(NarrativeEvent).filter(
            NarrativeEvent.work_id == work_id,
            NarrativeEvent.edition_id.is_(None)
        ).count()
        
        return {
            "work_id": str(work_id),
            "total_entities": len(entities),
            "entities_by_type": entity_counts,
            "total_relations": relation_count,
            "total_events": event_count,
        }
