# -*- coding: utf-8 -*-
# @file collection_service.py
# @brief Service layer for knowledge collections
# @author sailing-innocent
# @date 2025-11-08

from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.model.collection import KnowledgeCollection, CollectionItem
from server.data.schemas import (
    KnowledgeCollectionCreate,
    KnowledgeCollectionUpdate,
    KnowledgeCollectionResponse,
    CollectionItemCreate,
    CollectionItemUpdate,
    CollectionItemResponse,
)


class CollectionService:
    """Service for managing knowledge collections (character arcs, plotlines, etc.)"""

    def __init__(self, db: Session):
        self.db = db

    # ============ Collection Methods ============

    def create_collection(
        self, collection_data: KnowledgeCollectionCreate
    ) -> KnowledgeCollectionResponse:
        """Create a new knowledge collection"""
        db_collection = KnowledgeCollection(**collection_data.model_dump())
        self.db.add(db_collection)
        self.db.commit()
        self.db.refresh(db_collection)
        return KnowledgeCollectionResponse.model_validate(db_collection)

    def get_collection(self, collection_id: UUID) -> Optional[KnowledgeCollectionResponse]:
        """Get collection by ID"""
        collection = (
            self.db.query(KnowledgeCollection)
            .filter(KnowledgeCollection.id == collection_id)
            .first()
        )
        if collection:
            return KnowledgeCollectionResponse.model_validate(collection)
        return None

    def list_collections(
        self,
        work_id: Optional[UUID] = None,
        collection_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[KnowledgeCollectionResponse]:
        """List collections with optional filters"""
        query = self.db.query(KnowledgeCollection)
        
        if work_id:
            query = query.filter(KnowledgeCollection.work_id == work_id)
        if collection_type:
            query = query.filter(KnowledgeCollection.collection_type == collection_type)
        
        query = query.order_by(
            KnowledgeCollection.collection_type,
            KnowledgeCollection.name
        )
        
        collections = query.offset(skip).limit(limit).all()
        return [KnowledgeCollectionResponse.model_validate(c) for c in collections]

    def update_collection(
        self, collection_id: UUID, update_data: KnowledgeCollectionUpdate
    ) -> Optional[KnowledgeCollectionResponse]:
        """Update collection"""
        collection = (
            self.db.query(KnowledgeCollection)
            .filter(KnowledgeCollection.id == collection_id)
            .first()
        )
        if not collection:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(collection, key, value)

        self.db.commit()
        self.db.refresh(collection)
        return KnowledgeCollectionResponse.model_validate(collection)

    def delete_collection(self, collection_id: UUID) -> bool:
        """Delete collection"""
        collection = (
            self.db.query(KnowledgeCollection)
            .filter(KnowledgeCollection.id == collection_id)
            .first()
        )
        if not collection:
            return False

        self.db.delete(collection)
        self.db.commit()
        return True

    # ============ Collection Item Methods ============

    def add_item(self, item_data: CollectionItemCreate) -> CollectionItemResponse:
        """Add an item to a collection"""
        db_item = CollectionItem(**item_data.model_dump())
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return CollectionItemResponse.model_validate(db_item)

    def get_collection_items(
        self, collection_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[CollectionItemResponse]:
        """Get all items in a collection"""
        items = (
            self.db.query(CollectionItem)
            .filter(CollectionItem.collection_id == collection_id)
            .order_by(
                CollectionItem.sort_order.asc().nulls_last(),
                CollectionItem.created_at.asc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [CollectionItemResponse.model_validate(i) for i in items]

    def get_item(self, item_id: UUID) -> Optional[CollectionItemResponse]:
        """Get a specific collection item"""
        item = (
            self.db.query(CollectionItem)
            .filter(CollectionItem.id == item_id)
            .first()
        )
        if item:
            return CollectionItemResponse.model_validate(item)
        return None

    def update_item(
        self, item_id: UUID, update_data: CollectionItemUpdate
    ) -> Optional[CollectionItemResponse]:
        """Update collection item"""
        item = (
            self.db.query(CollectionItem)
            .filter(CollectionItem.id == item_id)
            .first()
        )
        if not item:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(item, key, value)

        self.db.commit()
        self.db.refresh(item)
        return CollectionItemResponse.model_validate(item)

    def remove_item(self, item_id: UUID) -> bool:
        """Remove an item from a collection"""
        item = (
            self.db.query(CollectionItem)
            .filter(CollectionItem.id == item_id)
            .first()
        )
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()
        return True

    def find_collections_containing(
        self, target_type: str, target_id: UUID
    ) -> List[KnowledgeCollectionResponse]:
        """Find all collections that contain a specific item"""
        items = (
            self.db.query(CollectionItem)
            .filter(
                CollectionItem.target_type == target_type,
                CollectionItem.target_id == target_id
            )
            .all()
        )
        
        collection_ids = [item.collection_id for item in items]
        if not collection_ids:
            return []
        
        collections = (
            self.db.query(KnowledgeCollection)
            .filter(KnowledgeCollection.id.in_(collection_ids))
            .all()
        )
        return [KnowledgeCollectionResponse.model_validate(c) for c in collections]

    def reorder_items(self, collection_id: UUID, item_order: List[UUID]) -> bool:
        """Reorder items in a collection by providing ordered list of item IDs"""
        for idx, item_id in enumerate(item_order):
            item = (
                self.db.query(CollectionItem)
                .filter(
                    CollectionItem.id == item_id,
                    CollectionItem.collection_id == collection_id
                )
                .first()
            )
            if item:
                item.sort_order = idx
        
        self.db.commit()
        return True

