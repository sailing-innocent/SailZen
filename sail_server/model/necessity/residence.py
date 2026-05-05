# -*- coding: utf-8 -*-
# @file residence.py
# @brief Residence model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.infrastructure.orm.necessity import (
    Residence,
    ResidenceType,
)
from sail_server.application.dto.necessity import (
    ResidenceCreateRequest,
    ResidenceUpdateRequest,
    ResidenceResponse,
)
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_residence_impl",
    "read_residence_impl",
    "read_residences_impl",
    "update_residence_impl",
    "delete_residence_impl",
    "get_portable_residence_impl",
]


def _residence_to_response(residence: Residence) -> ResidenceResponse:
    """Convert Residence ORM object to ResidenceResponse"""
    return ResidenceResponse(
        id=residence.id,
        name=residence.name,
        code=residence.code or "",
        type=residence.type,
        address=residence.address or "",
        description=residence.description or "",
        is_portable=residence.is_portable or False,
        priority=residence.priority or 10,
        ctime=residence.ctime,
        mtime=residence.mtime,
    )


def create_residence_impl(
    db: Session, data: ResidenceCreateRequest
) -> ResidenceResponse:
    """Create a new residence"""
    residence = Residence(
        name=data.name,
        code=data.code,
        type=data.type,
        address=data.address,
        description=data.description,
        is_portable=data.is_portable,
        priority=data.priority,
    )
    db.add(residence)
    db.commit()
    db.refresh(residence)
    return _residence_to_response(residence)


def read_residence_impl(db: Session, residence_id: int) -> Optional[ResidenceResponse]:
    """Read a residence by ID"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None
    return _residence_to_response(residence)


def read_residences_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
    residence_type: Optional[int] = None,
) -> List[ResidenceResponse]:
    """Read all residences with optional filtering"""
    q = db.query(Residence)

    if residence_type is not None:
        q = q.filter(Residence.type == residence_type)

    q = q.order_by(Residence.priority.asc())

    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)

    residences = q.all()
    return [_residence_to_response(r) for r in residences]


def update_residence_impl(
    db: Session,
    residence_id: int,
    data: ResidenceUpdateRequest,
) -> Optional[ResidenceResponse]:
    """Update a residence"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None

    if data.name is not None:
        residence.name = data.name
    if data.code is not None:
        residence.code = data.code
    if data.type is not None:
        residence.type = data.type
    if data.address is not None:
        residence.address = data.address
    if data.description is not None:
        residence.description = data.description
    if data.is_portable is not None:
        residence.is_portable = data.is_portable
    if data.priority is not None:
        residence.priority = data.priority
    residence.mtime = datetime.now()

    db.commit()
    db.refresh(residence)
    return _residence_to_response(residence)


def delete_residence_impl(db: Session, residence_id: int) -> Optional[dict]:
    """Delete a residence"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None

    db.delete(residence)
    db.commit()
    return {"id": residence_id, "status": "deleted"}


def get_portable_residence_impl(db: Session) -> Optional[ResidenceResponse]:
    """Get the portable (随身携带) residence"""
    residence = db.query(Residence).filter(Residence.is_portable == True).first()
    if residence is None:
        return None
    return _residence_to_response(residence)
