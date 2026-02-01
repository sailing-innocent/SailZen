# -*- coding: utf-8 -*-
# @file item.py
# @brief Item model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.data.necessity import (
    Item,
    ItemData,
    ItemCategory,
)
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_item_impl",
    "read_item_impl",
    "read_items_impl",
    "read_items_paginated_impl",
    "update_item_impl",
    "delete_item_impl",
    "search_items_impl",
    "get_expiring_items_impl",
    "get_portable_items_impl",
]


def _timestamp_to_datetime(ts: Optional[float]) -> Optional[datetime]:
    """Convert timestamp to datetime"""
    if ts is None or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts)
    except (ValueError, OSError):
        return None


def _datetime_to_timestamp(dt: Optional[datetime]) -> Optional[float]:
    """Convert datetime to timestamp"""
    if dt is None:
        return None
    try:
        return dt.timestamp()
    except (ValueError, OSError):
        return None


def item_from_data(data: ItemData) -> Item:
    """Convert ItemData to Item ORM object"""
    return Item(
        name=data.name,
        category_id=data.category_id,
        type=data.type,
        brand=data.brand,
        model=data.model,
        serial_number=data.serial_number,
        description=data.description,
        purchase_date=_timestamp_to_datetime(data.purchase_date),
        purchase_price=data.purchase_price,
        warranty_until=_timestamp_to_datetime(data.warranty_until),
        expire_date=_timestamp_to_datetime(data.expire_date),
        importance=data.importance,
        portability=data.portability,
        tags=data.tags,
        image_url=data.image_url,
        state=data.state,
    )


def data_from_item(item: Item) -> ItemData:
    """Convert Item ORM object to ItemData"""
    return ItemData(
        id=item.id,
        name=item.name,
        category_id=item.category_id,
        type=item.type,
        brand=item.brand or "",
        model=item.model or "",
        serial_number=item.serial_number or "",
        description=item.description or "",
        purchase_date=_datetime_to_timestamp(item.purchase_date),
        purchase_price=item.purchase_price or "",
        warranty_until=_datetime_to_timestamp(item.warranty_until),
        expire_date=_datetime_to_timestamp(item.expire_date),
        importance=item.importance or 3,
        portability=item.portability or 3,
        tags=item.tags or "",
        image_url=item.image_url or "",
        state=item.state,
        ctime=item.ctime,
        mtime=item.mtime,
    )


def create_item_impl(db: Session, data: ItemData) -> ItemData:
    """Create a new item"""
    item = item_from_data(data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return data_from_item(item)


def read_item_impl(db: Session, item_id: int) -> Optional[ItemData]:
    """Read an item by ID"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        return None
    return data_from_item(item)


def read_items_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
    category_id: Optional[int] = None,
    item_type: Optional[int] = None,
    state: Optional[int] = None,
    tags: Optional[str] = None,
) -> List[ItemData]:
    """Read items with optional filtering"""
    q = db.query(Item)
    
    if category_id is not None:
        q = q.filter(Item.category_id == category_id)
    if item_type is not None:
        q = q.filter(Item.type == item_type)
    if state is not None:
        q = q.filter(Item.state == state)
    if tags:
        # Filter by any matching tag
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            tag_filters = [Item.tags.contains(tag) for tag in tag_list]
            q = q.filter(or_(*tag_filters))
    
    q = q.order_by(Item.importance.desc(), Item.mtime.desc())
    
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    
    items = q.all()
    return [data_from_item(i) for i in items]


def read_items_paginated_impl(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    category_id: Optional[int] = None,
    item_type: Optional[int] = None,
    state: Optional[int] = None,
    tags: Optional[str] = None,
    keyword: Optional[str] = None,
    sort_by: str = "mtime",
    sort_order: str = "desc",
) -> dict:
    """Read items with pagination"""
    q = db.query(Item)
    
    if category_id is not None:
        q = q.filter(Item.category_id == category_id)
    if item_type is not None:
        q = q.filter(Item.type == item_type)
    if state is not None:
        q = q.filter(Item.state == state)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            tag_filters = [Item.tags.contains(tag) for tag in tag_list]
            q = q.filter(or_(*tag_filters))
    if keyword:
        q = q.filter(or_(
            Item.name.ilike(f"%{keyword}%"),
            Item.description.ilike(f"%{keyword}%"),
            Item.brand.ilike(f"%{keyword}%"),
            Item.model.ilike(f"%{keyword}%"),
        ))
    
    # Get total count
    total = q.count()
    
    # Sorting
    sort_column = getattr(Item, sort_by, Item.mtime)
    if sort_order == "asc":
        q = q.order_by(sort_column.asc())
    else:
        q = q.order_by(sort_column.desc())
    
    # Pagination
    offset = (page - 1) * page_size
    q = q.offset(offset).limit(page_size)
    
    items = q.all()
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    
    return {
        "data": [data_from_item(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def update_item_impl(
    db: Session,
    item_id: int,
    data: ItemData,
) -> Optional[ItemData]:
    """Update an item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        return None
    
    item.name = data.name
    item.category_id = data.category_id
    item.type = data.type
    item.brand = data.brand
    item.model = data.model
    item.serial_number = data.serial_number
    item.description = data.description
    item.purchase_date = _timestamp_to_datetime(data.purchase_date)
    item.purchase_price = data.purchase_price
    item.warranty_until = _timestamp_to_datetime(data.warranty_until)
    item.expire_date = _timestamp_to_datetime(data.expire_date)
    item.importance = data.importance
    item.portability = data.portability
    item.tags = data.tags
    item.image_url = data.image_url
    item.state = data.state
    item.mtime = datetime.now()
    
    db.commit()
    db.refresh(item)
    return data_from_item(item)


def delete_item_impl(db: Session, item_id: int) -> Optional[dict]:
    """Delete an item"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        return None
    
    db.delete(item)
    db.commit()
    return {"id": item_id, "status": "deleted"}


def search_items_impl(
    db: Session,
    keyword: str,
    limit: int = 20,
) -> List[ItemData]:
    """Search items by keyword"""
    q = db.query(Item).filter(or_(
        Item.name.ilike(f"%{keyword}%"),
        Item.description.ilike(f"%{keyword}%"),
        Item.brand.ilike(f"%{keyword}%"),
        Item.model.ilike(f"%{keyword}%"),
        Item.tags.ilike(f"%{keyword}%"),
    ))
    
    items = q.limit(limit).all()
    return [data_from_item(i) for i in items]


def get_expiring_items_impl(
    db: Session,
    days_ahead: int = 30,
) -> List[dict]:
    """Get items that will expire within the specified days"""
    from datetime import timedelta
    threshold_date = datetime.now() + timedelta(days=days_ahead)
    
    items = db.query(Item).filter(
        Item.expire_date.isnot(None),
        Item.expire_date <= threshold_date,
        Item.state == 0,  # Only active items
    ).order_by(Item.expire_date.asc()).all()
    
    result = []
    for item in items:
        days_remaining = (item.expire_date - datetime.now()).days
        result.append({
            "item": data_from_item(item),
            "days_remaining": days_remaining,
            "severity": "urgent" if days_remaining <= 7 else "warning",
        })
    
    return result


def get_portable_items_impl(
    db: Session,
    min_portability: int = 4,
) -> List[ItemData]:
    """Get items that are highly portable (for travel suggestions)"""
    items = db.query(Item).filter(
        Item.portability >= min_portability,
        Item.state == 0,  # Only active items
    ).order_by(Item.importance.desc()).all()
    
    return [data_from_item(i) for i in items]
