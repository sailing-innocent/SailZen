# -*- coding: utf-8 -*-
# @file inventory.py
# @brief Inventory model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.data.necessity import (
    Inventory,
    InventoryData,
    Consumption,
    ConsumptionData,
    Replenishment,
    ReplenishmentData,
    Item,
    Residence,
    Container,
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


def _str_to_decimal(s: str) -> Decimal:
    """Convert string to Decimal safely"""
    try:
        return Decimal(s)
    except:
        return Decimal(0)


def _decimal_to_str(d) -> str:
    """Convert Decimal to string"""
    if d is None:
        return "0"
    return str(d)


def inventory_from_data(data: InventoryData) -> Inventory:
    """Convert InventoryData to Inventory ORM object"""
    return Inventory(
        item_id=data.item_id,
        residence_id=data.residence_id,
        container_id=data.container_id,
        quantity=_str_to_decimal(data.quantity),
        unit=data.unit,
        min_quantity=_str_to_decimal(data.min_quantity),
        max_quantity=_str_to_decimal(data.max_quantity),
        notes=data.notes,
    )


def data_from_inventory(
    inventory: Inventory,
    include_names: bool = True,
) -> InventoryData:
    """Convert Inventory ORM object to InventoryData"""
    data = InventoryData(
        id=inventory.id,
        item_id=inventory.item_id,
        residence_id=inventory.residence_id,
        container_id=inventory.container_id,
        quantity=_decimal_to_str(inventory.quantity),
        unit=inventory.unit or "个",
        min_quantity=_decimal_to_str(inventory.min_quantity),
        max_quantity=_decimal_to_str(inventory.max_quantity),
        last_check_time=inventory.last_check_time.timestamp() if inventory.last_check_time else None,
        notes=inventory.notes or "",
        ctime=inventory.ctime,
        mtime=inventory.mtime,
    )
    
    if include_names:
        if inventory.item:
            data.item_name = inventory.item.name
        if inventory.residence:
            data.residence_name = inventory.residence.name
        if inventory.container:
            data.container_name = inventory.container.name
    
    return data


def create_inventory_impl(db: Session, data: InventoryData) -> InventoryData:
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
        existing.quantity = _str_to_decimal(existing.quantity) + _str_to_decimal(data.quantity)
        existing.mtime = datetime.now()
        db.commit()
        db.refresh(existing)
        return data_from_inventory(existing)
    
    inventory = inventory_from_data(data)
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return data_from_inventory(inventory)


def read_inventory_impl(db: Session, inventory_id: int) -> Optional[InventoryData]:
    """Read an inventory record by ID"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        return None
    return data_from_inventory(inventory)


def read_inventories_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
) -> List[InventoryData]:
    """Read all inventory records"""
    q = db.query(Inventory)
    
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    
    inventories = q.all()
    return [data_from_inventory(i) for i in inventories]


def read_inventories_by_residence_impl(
    db: Session,
    residence_id: int,
) -> List[InventoryData]:
    """Read all inventory records for a residence"""
    inventories = db.query(Inventory).filter(
        Inventory.residence_id == residence_id
    ).all()
    return [data_from_inventory(i) for i in inventories]


def read_inventories_by_item_impl(
    db: Session,
    item_id: int,
) -> List[InventoryData]:
    """Read all inventory records for an item (locations)"""
    inventories = db.query(Inventory).filter(
        Inventory.item_id == item_id
    ).all()
    return [data_from_inventory(i) for i in inventories]


def update_inventory_impl(
    db: Session,
    inventory_id: int,
    data: InventoryData,
) -> Optional[InventoryData]:
    """Update an inventory record"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        return None
    
    inventory.item_id = data.item_id
    inventory.residence_id = data.residence_id
    inventory.container_id = data.container_id
    inventory.quantity = _str_to_decimal(data.quantity)
    inventory.unit = data.unit
    inventory.min_quantity = _str_to_decimal(data.min_quantity)
    inventory.max_quantity = _str_to_decimal(data.max_quantity)
    inventory.notes = data.notes
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    return data_from_inventory(inventory)


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
    quantity: str,
    reason: str = "",
) -> InventoryData:
    """Record consumption and update inventory"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        raise ValueError(f"Inventory {inventory_id} not found")
    
    consume_qty = _str_to_decimal(quantity)
    
    # Create consumption record
    consumption = Consumption(
        inventory_id=inventory_id,
        quantity=consume_qty,
        reason=reason,
        htime=datetime.now(),
    )
    db.add(consumption)
    
    # Update inventory quantity
    inventory.quantity = inventory.quantity - consume_qty
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    
    return data_from_inventory(inventory)


def record_replenishment_impl(
    db: Session,
    inventory_id: int,
    data: ReplenishmentData,
) -> InventoryData:
    """Record replenishment and update inventory"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if inventory is None:
        raise ValueError(f"Inventory {inventory_id} not found")
    
    replenish_qty = _str_to_decimal(data.quantity)
    
    # Create replenishment record
    replenishment = Replenishment(
        inventory_id=inventory_id,
        quantity=replenish_qty,
        source=data.source,
        source_residence_id=data.source_residence_id,
        cost=data.cost,
        transaction_id=data.transaction_id,
        notes=data.notes,
        htime=datetime.now(),
    )
    db.add(replenishment)
    
    # Update inventory quantity
    inventory.quantity = inventory.quantity + replenish_qty
    inventory.mtime = datetime.now()
    
    db.commit()
    db.refresh(inventory)
    
    return data_from_inventory(inventory)


def transfer_inventory_impl(
    db: Session,
    item_id: int,
    from_residence_id: int,
    to_residence_id: int,
    quantity: str,
    from_container_id: Optional[int] = None,
    to_container_id: Optional[int] = None,
) -> dict:
    """Transfer inventory from one residence to another"""
    transfer_qty = _str_to_decimal(quantity)
    
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
    
    if source_inv.quantity < transfer_qty:
        raise ValueError("Insufficient quantity in source inventory")
    
    # Decrease source inventory
    source_inv.quantity = source_inv.quantity - transfer_qty
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
        dest_inv.quantity = dest_inv.quantity + transfer_qty
        dest_inv.mtime = datetime.now()
    else:
        dest_inv = Inventory(
            item_id=item_id,
            residence_id=to_residence_id,
            container_id=to_container_id,
            quantity=transfer_qty,
            unit=source_inv.unit,
        )
        db.add(dest_inv)
    
    db.commit()
    
    return {
        "source": data_from_inventory(source_inv),
        "destination": data_from_inventory(dest_inv),
        "transferred_quantity": quantity,
    }


def get_low_stock_impl(
    db: Session,
    residence_id: Optional[int] = None,
) -> List[InventoryData]:
    """Get inventory records where quantity is below min_quantity"""
    q = db.query(Inventory).filter(
        Inventory.quantity <= Inventory.min_quantity,
        Inventory.min_quantity > 0,
    )
    
    if residence_id:
        q = q.filter(Inventory.residence_id == residence_id)
    
    inventories = q.all()
    return [data_from_inventory(i) for i in inventories]


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
