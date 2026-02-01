# -*- coding: utf-8 -*-
# @file residence.py
# @brief Residence model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.data.necessity import (
    Residence,
    ResidenceData,
    ResidenceType,
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


def residence_from_data(data: ResidenceData) -> Residence:
    """Convert ResidenceData to Residence ORM object"""
    return Residence(
        name=data.name,
        code=data.code,
        type=data.type,
        address=data.address,
        description=data.description,
        is_portable=data.is_portable,
        priority=data.priority,
    )


def data_from_residence(residence: Residence) -> ResidenceData:
    """Convert Residence ORM object to ResidenceData"""
    return ResidenceData(
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


def create_residence_impl(db: Session, data: ResidenceData) -> ResidenceData:
    """Create a new residence"""
    residence = residence_from_data(data)
    db.add(residence)
    db.commit()
    db.refresh(residence)
    return data_from_residence(residence)


def read_residence_impl(db: Session, residence_id: int) -> Optional[ResidenceData]:
    """Read a residence by ID"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None
    return data_from_residence(residence)


def read_residences_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
    residence_type: Optional[int] = None,
) -> List[ResidenceData]:
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
    return [data_from_residence(r) for r in residences]


def update_residence_impl(
    db: Session,
    residence_id: int,
    data: ResidenceData,
) -> Optional[ResidenceData]:
    """Update a residence"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None
    
    residence.name = data.name
    residence.code = data.code
    residence.type = data.type
    residence.address = data.address
    residence.description = data.description
    residence.is_portable = data.is_portable
    residence.priority = data.priority
    residence.mtime = datetime.now()
    
    db.commit()
    db.refresh(residence)
    return data_from_residence(residence)


def delete_residence_impl(db: Session, residence_id: int) -> Optional[dict]:
    """Delete a residence"""
    residence = db.query(Residence).filter(Residence.id == residence_id).first()
    if residence is None:
        return None
    
    db.delete(residence)
    db.commit()
    return {"id": residence_id, "status": "deleted"}


def get_portable_residence_impl(db: Session) -> Optional[ResidenceData]:
    """Get the portable (随身携带) residence"""
    residence = db.query(Residence).filter(Residence.is_portable == True).first()
    if residence is None:
        return None
    return data_from_residence(residence)
