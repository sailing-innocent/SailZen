# -*- coding: utf-8 -*-
# @file collections.py
# @brief API routes for knowledge collections
# @author sailing-innocent
# @date 2025-11-08

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from server.db import g_db_func
from server.service.collection_service import CollectionService
from server.data.schemas import (
    KnowledgeCollectionCreate,
    KnowledgeCollectionUpdate,
    KnowledgeCollectionResponse,
    CollectionItemCreate,
    CollectionItemUpdate,
    CollectionItemResponse,
)

router = APIRouter(prefix="/api/v1", tags=["collections"])


def get_collection_service(db: Session = Depends(g_db_func)):
    return CollectionService(db)


# ============ Knowledge Collection Endpoints ============


@router.post("/collections", response_model=KnowledgeCollectionResponse, status_code=status.HTTP_201_CREATED)
def create_collection(
    collection: KnowledgeCollectionCreate,
    service: CollectionService = Depends(get_collection_service)
):
    """Create a new knowledge collection"""
    try:
        return service.create_collection(collection)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/collections", response_model=List[KnowledgeCollectionResponse])
def list_collections(
    work_id: Optional[UUID] = None,
    collection_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    service: CollectionService = Depends(get_collection_service)
):
    """List knowledge collections with optional filters"""
    return service.list_collections(
        work_id=work_id,
        collection_type=collection_type,
        skip=skip,
        limit=limit
    )


@router.get("/collections/{collection_id}", response_model=KnowledgeCollectionResponse)
def get_collection(
    collection_id: UUID,
    service: CollectionService = Depends(get_collection_service)
):
    """Get collection by ID"""
    collection = service.get_collection(collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.put("/collections/{collection_id}", response_model=KnowledgeCollectionResponse)
def update_collection(
    collection_id: UUID,
    update_data: KnowledgeCollectionUpdate,
    service: CollectionService = Depends(get_collection_service)
):
    """Update collection"""
    collection = service.update_collection(collection_id, update_data)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: UUID,
    service: CollectionService = Depends(get_collection_service)
):
    """Delete collection"""
    if not service.delete_collection(collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")


# ============ Collection Item Endpoints ============


@router.post("/collections/{collection_id}/items", response_model=CollectionItemResponse, status_code=status.HTTP_201_CREATED)
def add_item(
    collection_id: UUID,
    item: CollectionItemCreate,
    service: CollectionService = Depends(get_collection_service)
):
    """Add an item to a collection"""
    # Ensure collection_id matches
    if item.collection_id != collection_id:
        raise HTTPException(status_code=400, detail="Collection ID mismatch")
    
    try:
        return service.add_item(item)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/collections/{collection_id}/items", response_model=List[CollectionItemResponse])
def get_collection_items(
    collection_id: UUID,
    skip: int = 0,
    limit: int = 100,
    service: CollectionService = Depends(get_collection_service)
):
    """Get all items in a collection"""
    return service.get_collection_items(collection_id, skip=skip, limit=limit)


@router.put("/collection-items/{item_id}", response_model=CollectionItemResponse)
def update_item(
    item_id: UUID,
    update_data: CollectionItemUpdate,
    service: CollectionService = Depends(get_collection_service)
):
    """Update collection item"""
    item = service.update_item(item_id, update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Collection item not found")
    return item


@router.delete("/collection-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    item_id: UUID,
    service: CollectionService = Depends(get_collection_service)
):
    """Remove an item from a collection"""
    if not service.remove_item(item_id):
        raise HTTPException(status_code=404, detail="Collection item not found")


@router.get("/items/{target_type}/{target_id}/collections", response_model=List[KnowledgeCollectionResponse])
def find_collections_containing(
    target_type: str,
    target_id: UUID,
    service: CollectionService = Depends(get_collection_service)
):
    """Find all collections that contain a specific item"""
    return service.find_collections_containing(target_type, target_id)


@router.post("/collections/{collection_id}/reorder", status_code=status.HTTP_200_OK)
def reorder_items(
    collection_id: UUID,
    item_order: List[UUID] = Body(..., description="Ordered list of item IDs"),
    service: CollectionService = Depends(get_collection_service)
):
    """Reorder items in a collection"""
    success = service.reorder_items(collection_id, item_order)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reorder items")
    return {"message": "Items reordered successfully"}

