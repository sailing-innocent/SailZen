# -*- coding: utf-8 -*-
# @file category.py
# @brief Item Category model implementation
# @author sailing-innocent
# @date 2026-02-01
# @version 1.0
# ---------------------------------

from sail_server.data.necessity import (
    ItemCategory,
)
from sail_server.application.dto.necessity import (
    ItemCategoryCreateRequest,
    ItemCategoryUpdateRequest,
    ItemCategoryResponse,
)
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

__all__ = [
    "create_category_impl",
    "read_category_impl",
    "read_categories_impl",
    "update_category_impl",
    "delete_category_impl",
    "get_category_tree_impl",
    "seed_default_categories_impl",
]


def _category_to_response(category: ItemCategory) -> ItemCategoryResponse:
    """Convert ItemCategory ORM object to ItemCategoryResponse"""
    return ItemCategoryResponse(
        id=category.id,
        parent_id=category.parent_id,
        name=category.name,
        code=category.code or "",
        icon=category.icon or "",
        is_consumable=category.is_consumable or False,
        default_unit=category.default_unit or "个",
        description=category.description or "",
        ctime=category.ctime,
        mtime=category.mtime,
    )


def create_category_impl(db: Session, data: ItemCategoryCreateRequest) -> ItemCategoryResponse:
    """Create a new category"""
    category = ItemCategory(
        parent_id=data.parent_id,
        name=data.name,
        code=data.code,
        icon=data.icon,
        is_consumable=data.is_consumable,
        default_unit=data.default_unit,
        description=data.description,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_to_response(category)


def read_category_impl(db: Session, category_id: int) -> Optional[ItemCategoryResponse]:
    """Read a category by ID"""
    category = db.query(ItemCategory).filter(ItemCategory.id == category_id).first()
    if category is None:
        return None
    return _category_to_response(category)


def read_categories_impl(
    db: Session,
    skip: int = 0,
    limit: int = -1,
) -> List[ItemCategoryResponse]:
    """Read all categories"""
    q = db.query(ItemCategory)
    
    if skip > 0:
        q = q.offset(skip)
    if limit > 0:
        q = q.limit(limit)
    
    categories = q.all()
    return [_category_to_response(c) for c in categories]


def update_category_impl(
    db: Session,
    category_id: int,
    data: ItemCategoryUpdateRequest,
) -> Optional[ItemCategoryResponse]:
    """Update a category"""
    category = db.query(ItemCategory).filter(ItemCategory.id == category_id).first()
    if category is None:
        return None
    
    if data.name is not None:
        category.name = data.name
    if data.code is not None:
        category.code = data.code
    if data.icon is not None:
        category.icon = data.icon
    if data.is_consumable is not None:
        category.is_consumable = data.is_consumable
    if data.default_unit is not None:
        category.default_unit = data.default_unit
    if data.description is not None:
        category.description = data.description
    category.mtime = datetime.now()
    
    db.commit()
    db.refresh(category)
    return _category_to_response(category)


def delete_category_impl(db: Session, category_id: int) -> Optional[dict]:
    """Delete a category"""
    category = db.query(ItemCategory).filter(ItemCategory.id == category_id).first()
    if category is None:
        return None
    
    db.delete(category)
    db.commit()
    return {"id": category_id, "status": "deleted"}


def get_category_tree_impl(db: Session) -> List[dict]:
    """Get category tree structure"""
    categories = db.query(ItemCategory).all()
    
    # Build tree structure
    category_map = {c.id: {
        "id": c.id,
        "name": c.name,
        "code": c.code or "",
        "icon": c.icon or "",
        "is_consumable": c.is_consumable or False,
        "default_unit": c.default_unit or "个",
        "parent_id": c.parent_id,
        "children": [],
    } for c in categories}
    
    tree = []
    for c in categories:
        if c.parent_id is None or c.parent_id not in category_map:
            tree.append(category_map[c.id])
        else:
            category_map[c.parent_id]["children"].append(category_map[c.id])
    
    return tree


def seed_default_categories_impl(db: Session) -> List[ItemCategoryResponse]:
    """Seed default categories if not exists"""
    # Check if categories already exist
    existing = db.query(ItemCategory).first()
    if existing:
        return read_categories_impl(db)
    
    # Default categories based on design doc
    default_categories = [
        # 一级类别
        {"name": "证件文件", "code": "DOCUMENT", "icon": "file-text", "is_consumable": False},
        {"name": "电子设备", "code": "ELECTRONICS", "icon": "smartphone", "is_consumable": False},
        {"name": "衣物", "code": "CLOTHING", "icon": "shirt", "is_consumable": False},
        {"name": "日用消耗", "code": "DAILY_CONSUMABLE", "icon": "package", "is_consumable": True},
        {"name": "家居用品", "code": "HOME", "icon": "home", "is_consumable": False},
        {"name": "健康护理", "code": "HEALTH", "icon": "heart", "is_consumable": True},
    ]
    
    created = []
    parent_map = {}
    
    # Create parent categories first
    for cat_data in default_categories:
        category = ItemCategory(
            name=cat_data["name"],
            code=cat_data["code"],
            icon=cat_data["icon"],
            is_consumable=cat_data["is_consumable"],
            default_unit="个",
        )
        db.add(category)
        db.flush()
        parent_map[cat_data["code"]] = category.id
        created.append(category)
    
    # Sub-categories
    sub_categories = [
        # 证件文件子类
        {"parent": "DOCUMENT", "name": "身份证件", "code": "ID_DOC"},
        {"parent": "DOCUMENT", "name": "金融卡证", "code": "FINANCE_DOC"},
        {"parent": "DOCUMENT", "name": "学历证件", "code": "EDU_DOC"},
        # 电子设备子类
        {"parent": "ELECTRONICS", "name": "通讯设备", "code": "COMM_DEVICE"},
        {"parent": "ELECTRONICS", "name": "计算设备", "code": "COMPUTE_DEVICE"},
        {"parent": "ELECTRONICS", "name": "娱乐设备", "code": "ENTERTAINMENT_DEVICE"},
        # 衣物子类
        {"parent": "CLOTHING", "name": "上装", "code": "TOPS"},
        {"parent": "CLOTHING", "name": "下装", "code": "BOTTOMS"},
        {"parent": "CLOTHING", "name": "内衣", "code": "UNDERWEAR"},
        {"parent": "CLOTHING", "name": "鞋袜", "code": "FOOTWEAR"},
        # 日用消耗子类
        {"parent": "DAILY_CONSUMABLE", "name": "洗漱用品", "code": "TOILETRY", "is_consumable": True},
        {"parent": "DAILY_CONSUMABLE", "name": "护理用品", "code": "CARE_PRODUCT", "is_consumable": True},
        {"parent": "DAILY_CONSUMABLE", "name": "清洁用品", "code": "CLEANING", "is_consumable": True},
        # 家居用品子类
        {"parent": "HOME", "name": "床上用品", "code": "BEDDING"},
        {"parent": "HOME", "name": "厨房用品", "code": "KITCHEN"},
        # 健康护理子类
        {"parent": "HEALTH", "name": "常备药品", "code": "MEDICINE", "is_consumable": True},
        {"parent": "HEALTH", "name": "护理器具", "code": "CARE_TOOL"},
    ]
    
    for sub_data in sub_categories:
        category = ItemCategory(
            parent_id=parent_map.get(sub_data["parent"]),
            name=sub_data["name"],
            code=sub_data["code"],
            is_consumable=sub_data.get("is_consumable", False),
            default_unit="个",
        )
        db.add(category)
        created.append(category)
    
    db.commit()
    
    return [_category_to_response(c) for c in created]
