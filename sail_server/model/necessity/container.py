# -*- coding: utf-8 -*-
# @file container.py
# @brief Container model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.data.necessity import (
    Container,
)
from sail_server.application.dto.necessity import (
    ContainerCreateRequest,
    ContainerUpdateRequest,
    ContainerResponse,
)
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_container_impl",
    "read_container_impl",
    "read_containers_impl",
    "read_containers_by_residence_impl",
    "update_container_impl",
    "delete_container_impl",
    "get_container_tree_impl",
]


def _container_to_response(container: Container) -> ContainerResponse:
    """Convert Container ORM object to ContainerResponse"""
    return ContainerResponse(
        id=container.id,
        residence_id=container.residence_id,
        parent_id=container.parent_id,
        name=container.name,
        type=container.type,
        description=container.description or "",
        capacity=container.capacity,
        ctime=container.ctime,
        mtime=container.mtime,
    )


def create_container_impl(db: Session, data: ContainerCreateRequest) -> ContainerResponse:
    """Create a new container"""
    container = Container(
        residence_id=data.residence_id,
        parent_id=data.parent_id,
        name=data.name,
        type=data.type,
        description=data.description,
        capacity=data.capacity,
    )
    db.add(container)
    db.commit()
    db.refresh(container)
    return _container_to_response(container)


def read_container_impl(db: Session, container_id: int) -> Optional[ContainerResponse]:
    """Read a container by ID"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if container is None:
        return None
    return _container_to_response(container)


def read_containers_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
) -> List[ContainerResponse]:
    """Read all containers"""
    q = db.query(Container)
    
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    
    containers = q.all()
    return [_container_to_response(c) for c in containers]


def read_containers_by_residence_impl(
    db: Session,
    residence_id: int,
) -> List[ContainerResponse]:
    """Read all containers in a residence"""
    containers = db.query(Container).filter(Container.residence_id == residence_id).all()
    return [_container_to_response(c) for c in containers]


def update_container_impl(
    db: Session,
    container_id: int,
    data: ContainerUpdateRequest,
) -> Optional[ContainerResponse]:
    """Update a container"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if container is None:
        return None
    
    if data.name is not None:
        container.name = data.name
    if data.type is not None:
        container.type = data.type
    if data.description is not None:
        container.description = data.description
    if data.capacity is not None:
        container.capacity = data.capacity
    container.mtime = datetime.now()
    
    db.commit()
    db.refresh(container)
    return _container_to_response(container)


def delete_container_impl(db: Session, container_id: int) -> Optional[dict]:
    """Delete a container"""
    container = db.query(Container).filter(Container.id == container_id).first()
    if container is None:
        return None
    
    db.delete(container)
    db.commit()
    return {"id": container_id, "status": "deleted"}


def get_container_tree_impl(db: Session, residence_id: int) -> List[dict]:
    """Get container tree structure for a residence"""
    containers = db.query(Container).filter(Container.residence_id == residence_id).all()
    
    # Build tree structure
    container_map = {c.id: {
        "id": c.id,
        "name": c.name,
        "type": c.type,
        "description": c.description or "",
        "parent_id": c.parent_id,
        "children": [],
    } for c in containers}
    
    tree = []
    for c in containers:
        if c.parent_id is None or c.parent_id not in container_map:
            tree.append(container_map[c.id])
        else:
            container_map[c.parent_id]["children"].append(container_map[c.id])
    
    return tree
