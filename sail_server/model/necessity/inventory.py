# -*- coding: utf-8 -*-
# @file inventory.py
# @brief Inventory model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.infrastructure.orm.necessity import (
    Inventory,
    Consumption,
    Replenishment,
    Item,
    Residence,
    Container,
)
from sail_server.application.dto.necessity import (
    InventoryCreateRequest,
    InventoryUpdateRequest,
    InventoryResponse,
    ConsumptionCreateRequest,
    ConsumptionResponse,
    ReplenishmentCreateRequest,
    ReplenishmentResponse,
)
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_inventory_impl",
    "read_inventory_impl",
    "read_inventories_impl",
    "read_inventories_by_residence_impl",
    "read_inventories_by_item_impl",
    "update_inventory_impl",
    "delete_inventory_impl",
    "record_consumption_impl",
    "record_replenishment_impl",
    "transfer_inventory_impl",
    "get_low_stock_impl",
    "get_inventory_stats_impl",
]


def _inventory_to_response(inventory: Inventory) -> InventoryResponse:
    """Convert Inventory ORM object to InventoryResponse"""
    return InventoryResponse(
        id=inventory.id,
        item_id=inventory.item_id,
        residence_id=inventory.residence_id,
        container_id=inventory.container_id,
        quantity=inventory.quantity or Decimal("0"),
        unit=inventory.unit or "个",
        min_quantity=inventory.min_quantity or Decimal("0"),
        max_quantity=inventory.max_quantity or Decimal("0"),
        last_check_time=inventory.last_check_time,
        notes=inventory.notes or "",
        ctime=inventory.ctime,
        mtime=inventory.mtime,
        item_name=inventory.item.name if inventory.item else "",
        residence_name=inventory.residence.name if inventory.residence else "",
        container_name=inventory.container.name if inventory.container else "",
    )


def _consumption_to_response(consumption: Consumption) -> ConsumptionResponse:
    """Convert Consumption ORM object to ConsumptionResponse"""
    return ConsumptionResponse(
        id=consumption.id,
        inventory_id=consumption.inventory_id,
        quantity=consumption.quantity or Decimal("0"),
        htime=consumption.htime,
        reason=consumption.reason or "",
        ctime=consumption.ctime,
    )


def _replenishment_to_response(replenishment: Replenishment) -> ReplenishmentResponse:
    """Convert Replenishment ORM object to ReplenishmentResponse"""
    return ReplenishmentResponse(
        id=replenishment.id,
        inventory_id=replenishment.inventory_id,
        quantity=replenishment.quantity or Decimal("0"),
        source=replenishment.source or 0,
        source_residence_id=replenishment.source_residence_id,
        cost=replenishment.cost or "",
        transaction_id=replenishment.transaction_id,
        htime=replenishment.htime,
        notes=replenishment.notes or "",
        ctime=replenishment.ctime,
    )


def create_inventory_impl(db: Session, data: InventoryCreateRequest) -> InventoryResponse:
    """Create a new inventory record"""
    # Check if inventory already exists for this item/residence/container combination
    existing = db.query(Inventory).filter(
        and_(
            Inventory.item_id == data.item_id,
            Inventory.residence_id == data.residence_id,
            Inventory.container_id == data.container_id if data.container_id else Inventory.container_id.is_(None),
        )
    ).first()
    
    if existing:
        # Update existing inventory
        existing.quantity = (existing.quantity or Decimal("0")) + data.quantity
        existing.mtime = datetime.now()
        db.commit()
        db.refresh(existing)
        return _inventory_to_response(existing)
    
    inventory = Inventory(
        item_id=data.item_id,
        residence_id=data.residence_id,
        container_id=data.container_id,
        quantity=data.quantity,
        unit=data.unit,
        min_quantity=data.min_quantity,
        max_quantity=data.max_quantity,
        notes=data.notes,
    )
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return _inventory_to_response(inventory)


def read_inventory_impl(db: Session, inventory_id: int) -> Optional[InventoryResponse]:
    """Read an inventory record by ID"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        return None
    return _inventory_to_response(inventory)


def read_inventories_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
) -> List[InventoryResponse]:
    """Read all inventory records"""
    q = db.query(Inventory)
    
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    
    inventories = q.all()
    return [_inventory_to_response(i) for i in inventories]


def read_inventories_by_residence_impl(
    db: Session,
    residence_id: int,
) -> List[InventoryResponse]:
    """Read all inventory records for a residence"""
    inventories = db.query(Inventory).filter(
        Inventory.residence_id == residence_id
    ).all()
    return [_inventory_to_response(i) for i in inventories]


def read_inventories_by_item_impl(
    db: Session,
    item_id: int,
) -> List[InventoryResponse]:
    """Read all inventory records for an item (locations)"""
    inventories = db.query(Inventory).filter(
        Inventory.item_id == item_id
    ).all()
    return [_inventory_to_response(i) for i in inventories]


def update_inventory_impl(
    db: Session,
    inventory_id: int,
    data: InventoryUpdateRequest,
) -> Optional[InventoryResponse]:
    """Update an inventory record"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        return None
    
    if data.container_id is not None:
        inventory.container_id = data.container_id
    if data.quantity is not None:
        inventory.quantity = data.quantity
    if data.unit is not None:
        inventory.unit = data.unit
    if data.min_quantity is not None:
        inventory.min_quantity = data.min_quantity
    if data.max_quantity is not None:
        inventory.max_quantity = data.max_quantity
    if data.notes is not None:
        inventory.notes = data.notes
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    return _inventory_to_response(inventory)


def delete_inventory_impl(db: Session, inventory_id: int) -> Optional[dict]:
    """Delete an inventory record"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        return None
    
    db.delete(inventory)
    db.commit()
    return {"id": inventory_id, "status": "deleted"}


def record_consumption_impl(
    db: Session,
    inventory_id: int,
    data: ConsumptionCreateRequest,
) -> InventoryResponse:
    """Record consumption and update inventory"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        raise ValueError(f"Inventory {inventory_id} not found")
    
    # Create consumption record
    consumption = Consumption(
        inventory_id=inventory_id,
        quantity=data.quantity,
        reason=data.reason,
        htime=data.htime or datetime.now(),
    )
    db.add(consumption)
    
    # Update inventory quantity
    inventory.quantity = (inventory.quantity or Decimal("0")) - data.quantity
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    
    return _inventory_to_response(inventory)


def record_replenishment_impl(
    db: Session,
    inventory_id: int,
    data: ReplenishmentCreateRequest,
) -> InventoryResponse:
    """Record replenishment and update inventory"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        raise ValueError(f"Inventory {inventory_id} not found")
    
    # Create replenishment record
    replenishment = Replenishment(
        inventory_id=inventory_id,
        quantity=data.quantity,
        source=data.source,
        source_residence_id=data.source_residence_id,
        cost=data.cost,
        transaction_id=data.transaction_id,
        notes=data.notes,
        htime=data.htime or datetime.now(),
    )
    db.add(replenishment)
    
    # Update inventory quantity
    inventory.quantity = (inventory.quantity or Decimal("0")) + data.quantity
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    
    return _inventory_to_response(inventory)


def transfer_inventory_impl(
    db: Session,
    item_id: int,
    from_residence_id: int,
    to_residence_id: int,
    quantity: Decimal,
    from_container_id: Optional[int] = None,
    to_container_id: Optional[int] = None,
) -> dict:
    """Transfer inventory from one residence to another"""
    # Find source inventory
    source_filter = and_(
        Inventory.item_id == item_id,
        Inventory.residence_id == from_residence_id,
    )
    if from_container_id:
        source_filter = and_(source_filter, Inventory.container_id == from_container_id)
    
    source_inv = db.query(Inventory).filter(source_filter).first()
    if source_inv is None:
        raise ValueError("Source inventory not found")
    
    if source_inv.quantity < quantity:
        raise ValueError("Insufficient quantity in source inventory")
    
    # Decrease source inventory
    source_inv.quantity = source_inv.quantity - quantity
    source_inv.mtime = datetime.now()
    
    # Find or create destination inventory
    dest_filter = and_(
        Inventory.item_id == item_id,
        Inventory.residence_id == to_residence_id,
    )
    if to_container_id:
        dest_filter = and_(dest_filter, Inventory.container_id == to_container_id)
    else:
        dest_filter = and_(dest_filter, Inventory.container_id.is_(None))
    
    dest_inv = db.query(Inventory).filter(dest_filter).first()
    
    if dest_inv:
        dest_inv.quantity = dest_inv.quantity + quantity
        dest_inv.mtime = datetime.now()
    else:
        dest_inv = Inventory(
            item_id=item_id,
            residence_id=to_residence_id,
            container_id=to_container_id,
            quantity=quantity,
            unit=source_inv.unit,
        )
        db.add(dest_inv)
    
    db.commit()
    
    return {
        "source": _inventory_to_response(source_inv),
        "destination": _inventory_to_response(dest_inv),
        "transferred_quantity": str(quantity),
    }


def get_low_stock_impl(
    db: Session,
    residence_id: Optional[int] = None,
) -> List[InventoryResponse]:
    """Get inventory records where quantity is below min_quantity"""
    q = db.query(Inventory).filter(
        Inventory.quantity <= Inventory.min_quantity,
        Inventory.min_quantity > 0,
    )
    
    if residence_id:
        q = q.filter(Inventory.residence_id == residence_id)
    
    inventories = q.all()
    return [_inventory_to_response(i) for i in inventories]


def get_inventory_stats_impl(
    db: Session,
    residence_id: Optional[int] = None,
) -> dict:
    """Get inventory statistics"""
    q = db.query(Inventory)
    
    if residence_id:
        q = q.filter(Inventory.residence_id == residence_id)
    
    inventories = q.all()
    
    total_items = len(inventories)
    total_quantity = sum(float(i.quantity or 0) for i in inventories)
    low_stock_count = sum(
        1 for i in inventories
        if i.min_quantity and i.quantity <= i.min_quantity
    )
    
    return {
        "total_items": total_items,
        "total_quantity": str(total_quantity),
        "low_stock_count": low_stock_count,
    }
