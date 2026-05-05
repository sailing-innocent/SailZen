# -*- coding: utf-8 -*-
# @file journey.py
# @brief Journey model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.infrastructure.orm.necessity import (
    Journey,
    JourneyItem,
    JourneyStatus,
    JourneyItemStatus,
    Inventory,
    Residence,
)
from sail_server.application.dto.necessity import (
    JourneyCreateRequest,
    JourneyUpdateRequest,
    JourneyResponse,
    JourneyItemCreateRequest,
    JourneyItemResponse,
)
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_journey_impl",
    "read_journey_impl",
    "read_journeys_impl",
    "update_journey_impl",
    "delete_journey_impl",
    "start_journey_impl",
    "complete_journey_impl",
    "cancel_journey_impl",
    "add_journey_item_impl",
    "remove_journey_item_impl",
    "pack_journey_item_impl",
    "unpack_journey_item_impl",
]


def _journey_item_to_response(journey_item: JourneyItem) -> JourneyItemResponse:
    """Convert JourneyItem ORM object to JourneyItemResponse"""
    return JourneyItemResponse(
        id=journey_item.id,
        journey_id=journey_item.journey_id,
        item_id=journey_item.item_id,
        quantity=journey_item.quantity or Decimal("1"),
        is_return=journey_item.is_return or False,
        from_container_id=journey_item.from_container_id,
        to_container_id=journey_item.to_container_id,
        status=journey_item.status,
        notes=journey_item.notes or "",
        ctime=journey_item.ctime,
        mtime=journey_item.mtime,
        item_name=journey_item.item.name if journey_item.item else "",
    )


def _journey_to_response(
    journey: Journey,
    include_items: bool = False,
) -> JourneyResponse:
    """Convert Journey ORM object to JourneyResponse"""
    response = JourneyResponse(
        id=journey.id,
        from_residence_id=journey.from_residence_id,
        to_residence_id=journey.to_residence_id,
        depart_time=journey.depart_time,
        arrive_time=journey.arrive_time,
        status=journey.status,
        transport_mode=journey.transport_mode or "",
        notes=journey.notes or "",
        ctime=journey.ctime,
        mtime=journey.mtime,
        from_residence_name=journey.from_residence.name
        if journey.from_residence
        else "",
        to_residence_name=journey.to_residence.name if journey.to_residence else "",
    )

    # Note: items are not part of JourneyResponse, but can be fetched separately
    # or returned as part of a different response structure
    return response


def create_journey_impl(db: Session, data: JourneyCreateRequest) -> JourneyResponse:
    """Create a new journey"""
    journey = Journey(
        from_residence_id=data.from_residence_id,
        to_residence_id=data.to_residence_id,
        depart_time=data.depart_time,
        arrive_time=data.arrive_time,
        status=data.status,
        transport_mode=data.transport_mode,
        notes=data.notes,
    )
    db.add(journey)
    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey)


def read_journey_impl(
    db: Session,
    journey_id: int,
    include_items: bool = True,
) -> Optional[JourneyResponse]:
    """Read a journey by ID"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        return None
    return _journey_to_response(journey, include_items=include_items)


def read_journeys_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
    status: Optional[int] = None,
    from_residence_id: Optional[int] = None,
    to_residence_id: Optional[int] = None,
) -> List[JourneyResponse]:
    """Read journeys with optional filtering"""
    q = db.query(Journey)

    if status is not None:
        q = q.filter(Journey.status == status)
    if from_residence_id is not None:
        q = q.filter(Journey.from_residence_id == from_residence_id)
    if to_residence_id is not None:
        q = q.filter(Journey.to_residence_id == to_residence_id)

    q = q.order_by(Journey.depart_time.desc())

    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)

    journeys = q.all()
    return [_journey_to_response(j) for j in journeys]


def update_journey_impl(
    db: Session,
    journey_id: int,
    data: JourneyUpdateRequest,
) -> Optional[JourneyResponse]:
    """Update a journey"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        return None

    if data.depart_time is not None:
        journey.depart_time = data.depart_time
    if data.arrive_time is not None:
        journey.arrive_time = data.arrive_time
    if data.status is not None:
        journey.status = data.status
    if data.transport_mode is not None:
        journey.transport_mode = data.transport_mode
    if data.notes is not None:
        journey.notes = data.notes
    journey.mtime = datetime.now()

    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey)


def delete_journey_impl(db: Session, journey_id: int) -> Optional[dict]:
    """Delete a journey"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        return None

    db.delete(journey)
    db.commit()
    return {"id": journey_id, "status": "deleted"}


def _get_portable_residence(db: Session) -> Optional[Residence]:
    """Get the portable residence"""
    return db.query(Residence).filter(Residence.is_portable == True).first()


def start_journey_impl(db: Session, journey_id: int) -> JourneyResponse:
    """Start a journey - move items to portable residence"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found")

    if journey.status != JourneyStatus.PLANNED:
        raise ValueError("Journey is not in PLANNED status")

    portable_residence = _get_portable_residence(db)
    if portable_residence is None:
        raise ValueError("Portable residence not found")

    # Move items from source to portable
    for journey_item in journey.items:
        # Find source inventory
        source_inv = (
            db.query(Inventory)
            .filter(
                Inventory.item_id == journey_item.item_id,
                Inventory.residence_id == journey.from_residence_id,
            )
            .first()
        )

        if source_inv:
            qty = journey_item.quantity or Decimal(1)
            if source_inv.quantity >= qty:
                source_inv.quantity -= qty

                # Find or create portable inventory
                portable_inv = (
                    db.query(Inventory)
                    .filter(
                        Inventory.item_id == journey_item.item_id,
                        Inventory.residence_id == portable_residence.id,
                    )
                    .first()
                )

                if portable_inv:
                    portable_inv.quantity += qty
                else:
                    portable_inv = Inventory(
                        item_id=journey_item.item_id,
                        residence_id=portable_residence.id,
                        quantity=qty,
                        unit=source_inv.unit,
                    )
                    db.add(portable_inv)

        journey_item.status = JourneyItemStatus.PACKED
        journey_item.mtime = datetime.now()

    journey.status = JourneyStatus.IN_TRANSIT
    journey.depart_time = datetime.now()
    journey.mtime = datetime.now()

    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey, include_items=True)


def complete_journey_impl(db: Session, journey_id: int) -> JourneyResponse:
    """Complete a journey - move items to destination"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found")

    if journey.status != JourneyStatus.IN_TRANSIT:
        raise ValueError("Journey is not in IN_TRANSIT status")

    portable_residence = _get_portable_residence(db)
    if portable_residence is None:
        raise ValueError("Portable residence not found")

    # Move items from portable to destination
    for journey_item in journey.items:
        # Find portable inventory
        portable_inv = (
            db.query(Inventory)
            .filter(
                Inventory.item_id == journey_item.item_id,
                Inventory.residence_id == portable_residence.id,
            )
            .first()
        )

        if portable_inv:
            qty = journey_item.quantity or Decimal(1)
            if portable_inv.quantity >= qty:
                portable_inv.quantity -= qty

                # Find or create destination inventory
                dest_inv = (
                    db.query(Inventory)
                    .filter(
                        Inventory.item_id == journey_item.item_id,
                        Inventory.residence_id == journey.to_residence_id,
                    )
                    .first()
                )

                if dest_inv:
                    dest_inv.quantity += qty
                else:
                    dest_inv = Inventory(
                        item_id=journey_item.item_id,
                        residence_id=journey.to_residence_id,
                        container_id=journey_item.to_container_id,
                        quantity=qty,
                        unit=portable_inv.unit,
                    )
                    db.add(dest_inv)

        journey_item.status = JourneyItemStatus.TRANSFERRED
        journey_item.mtime = datetime.now()

    journey.status = JourneyStatus.COMPLETED
    journey.arrive_time = datetime.now()
    journey.mtime = datetime.now()

    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey, include_items=True)


def cancel_journey_impl(db: Session, journey_id: int) -> JourneyResponse:
    """Cancel a journey"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found")

    if journey.status == JourneyStatus.COMPLETED:
        raise ValueError("Cannot cancel a completed journey")

    # If in transit, return items to source
    if journey.status == JourneyStatus.IN_TRANSIT:
        portable_residence = _get_portable_residence(db)
        if portable_residence:
            for journey_item in journey.items:
                portable_inv = (
                    db.query(Inventory)
                    .filter(
                        Inventory.item_id == journey_item.item_id,
                        Inventory.residence_id == portable_residence.id,
                    )
                    .first()
                )

                if portable_inv:
                    qty = journey_item.quantity or Decimal(1)
                    portable_inv.quantity -= qty

                    # Return to source
                    source_inv = (
                        db.query(Inventory)
                        .filter(
                            Inventory.item_id == journey_item.item_id,
                            Inventory.residence_id == journey.from_residence_id,
                        )
                        .first()
                    )

                    if source_inv:
                        source_inv.quantity += qty
                    else:
                        source_inv = Inventory(
                            item_id=journey_item.item_id,
                            residence_id=journey.from_residence_id,
                            quantity=qty,
                        )
                        db.add(source_inv)

    journey.status = JourneyStatus.CANCELLED
    journey.mtime = datetime.now()

    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey, include_items=True)


def add_journey_item_impl(
    db: Session,
    journey_id: int,
    data: JourneyItemCreateRequest,
) -> JourneyResponse:
    """Add an item to a journey"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found")

    if journey.status != JourneyStatus.PLANNED:
        raise ValueError("Can only add items to PLANNED journeys")

    journey_item = JourneyItem(
        journey_id=journey_id,
        item_id=data.item_id,
        quantity=data.quantity,
        is_return=data.is_return,
        from_container_id=data.from_container_id,
        to_container_id=data.to_container_id,
        status=JourneyItemStatus.PENDING,
        notes=data.notes,
    )
    db.add(journey_item)
    db.commit()
    db.refresh(journey)
    return _journey_to_response(journey, include_items=True)


def remove_journey_item_impl(
    db: Session,
    journey_id: int,
    item_id: int,
) -> JourneyResponse:
    """Remove an item from a journey"""
    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found")

    if journey.status != JourneyStatus.PLANNED:
        raise ValueError("Can only remove items from PLANNED journeys")

    journey_item = (
        db.query(JourneyItem)
        .filter(
            JourneyItem.journey_id == journey_id,
            JourneyItem.item_id == item_id,
        )
        .first()
    )

    if journey_item:
        db.delete(journey_item)
        db.commit()

    db.refresh(journey)
    return _journey_to_response(journey, include_items=True)


def pack_journey_item_impl(
    db: Session,
    journey_id: int,
    item_id: int,
) -> JourneyResponse:
    """Mark a journey item as packed"""
    journey_item = (
        db.query(JourneyItem)
        .filter(
            JourneyItem.journey_id == journey_id,
            JourneyItem.item_id == item_id,
        )
        .first()
    )

    if journey_item is None:
        raise ValueError("Journey item not found")

    journey_item.status = JourneyItemStatus.PACKED
    journey_item.mtime = datetime.now()

    db.commit()

    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    return _journey_to_response(journey, include_items=True)


def unpack_journey_item_impl(
    db: Session,
    journey_id: int,
    item_id: int,
) -> JourneyResponse:
    """Mark a journey item as unpacked"""
    journey_item = (
        db.query(JourneyItem)
        .filter(
            JourneyItem.journey_id == journey_id,
            JourneyItem.item_id == item_id,
        )
        .first()
    )

    if journey_item is None:
        raise ValueError("Journey item not found")

    journey_item.status = JourneyItemStatus.UNPACKED
    journey_item.mtime = datetime.now()

    db.commit()

    journey = db.query(Journey).filter(Journey.id == journey_id).first()
    return _journey_to_response(journey, include_items=True)
