# -*- coding: utf-8 -*-
# @file tag.py
# @brief Finance Tag Model Layer - CRUD + Seed
# @author sailing-innocent
# @date 2026-04-13
# @version 1.0
# ---------------------------------

"""
财务标签模型层

提供 FinanceTag 的 CRUD 操作和初始种子数据。
将原本硬编码在前端的标签列表迁移为数据库驱动。
"""

from datetime import datetime
from typing import List, Optional

import logging

from sail_server.infrastructure.orm.finance import FinanceTag
from sail_server.application.dto.finance import (
    FinanceTagCreateRequest,
    FinanceTagUpdateRequest,
    FinanceTagResponse,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 默认标签种子数据（从前端硬编码迁移）
# ============================================================================

DEFAULT_TAGS = [
    {"name": "零食", "color": "#8884d8", "category": "expense", "sort_order": 10},
    {"name": "交通", "color": "#82ca9d", "category": "expense", "sort_order": 20},
    {"name": "日用消耗", "color": "#ffc658", "category": "expense", "sort_order": 30},
    {"name": "娱乐休闲", "color": "#00ff00", "category": "expense", "sort_order": 40},
    {"name": "人际交往", "color": "#ff00ff", "category": "expense", "sort_order": 50},
    {"name": "医药健康", "color": "#00ffff", "category": "expense", "sort_order": 60},
    {"name": "衣物", "color": "#ff0080", "category": "expense", "sort_order": 70},
    {"name": "大宗电器", "color": "#ff7300", "category": "major", "sort_order": 80},
    {"name": "大宗收支", "color": "#8000ff", "category": "major", "sort_order": 90},
]


# ============================================================================
# Read Operations
# ============================================================================


def read_tag_impl(db, tag_id: int) -> Optional[FinanceTagResponse]:
    """读取单个标签"""
    tag = db.query(FinanceTag).filter(FinanceTag.id == tag_id).first()
    if tag is None:
        return None
    return _orm_to_response(tag)


def read_tag_by_name_impl(db, name: str) -> Optional[FinanceTagResponse]:
    """按名称读取标签"""
    tag = db.query(FinanceTag).filter(FinanceTag.name == name).first()
    if tag is None:
        return None
    return _orm_to_response(tag)


def read_tags_impl(
    db,
    category: Optional[str] = None,
    active_only: bool = True,
) -> List[FinanceTagResponse]:
    """
    读取标签列表

    Args:
        db: 数据库会话
        category: 按分类过滤（None=全部）
        active_only: 是否只返回启用的标签
    """
    q = db.query(FinanceTag)
    if active_only:
        q = q.filter(FinanceTag.is_active == 1)
    if category:
        q = q.filter(FinanceTag.category == category)
    q = q.order_by(FinanceTag.sort_order.asc(), FinanceTag.id.asc())
    tags = q.all()
    return [_orm_to_response(t) for t in tags]


# ============================================================================
# Write Operations
# ============================================================================


def create_tag_impl(db, req: FinanceTagCreateRequest) -> FinanceTagResponse:
    """创建标签"""
    # 检查名称唯一性
    existing = db.query(FinanceTag).filter(FinanceTag.name == req.name).first()
    if existing:
        raise ValueError(f"标签名称已存在: {req.name}")

    tag = FinanceTag(
        name=req.name,
        color=req.color,
        description=req.description,
        category=req.category,
        sort_order=req.sort_order,
        is_active=1,
        ctime=datetime.now(),
        mtime=datetime.now(),
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    logger.info(f"Created finance tag: {tag.name} (id={tag.id})")
    return _orm_to_response(tag)


def update_tag_impl(db, tag_id: int, req: FinanceTagUpdateRequest) -> Optional[FinanceTagResponse]:
    """更新标签"""
    tag = db.query(FinanceTag).filter(FinanceTag.id == tag_id).first()
    if tag is None:
        return None

    # 如果要更新名称，检查唯一性
    if req.name is not None and req.name != tag.name:
        existing = db.query(FinanceTag).filter(FinanceTag.name == req.name).first()
        if existing:
            raise ValueError(f"标签名称已存在: {req.name}")
        tag.name = req.name

    if req.color is not None:
        tag.color = req.color
    if req.description is not None:
        tag.description = req.description
    if req.category is not None:
        tag.category = req.category
    if req.sort_order is not None:
        tag.sort_order = req.sort_order
    if req.is_active is not None:
        tag.is_active = req.is_active

    tag.mtime = datetime.now()
    db.commit()
    db.refresh(tag)
    logger.info(f"Updated finance tag: {tag.name} (id={tag.id})")
    return _orm_to_response(tag)


def delete_tag_impl(db, tag_id: int) -> bool:
    """删除标签（硬删除）"""
    tag = db.query(FinanceTag).filter(FinanceTag.id == tag_id).first()
    if tag is None:
        return False
    name = tag.name
    db.delete(tag)
    db.commit()
    logger.info(f"Deleted finance tag: {name} (id={tag_id})")
    return True


# ============================================================================
# Seed / Init
# ============================================================================


def seed_default_tags_impl(db) -> int:
    """
    初始化默认标签（幂等操作）

    只会创建不存在的标签，不会修改已有标签。

    Returns:
        int: 新创建的标签数量
    """
    created_count = 0
    for tag_data in DEFAULT_TAGS:
        existing = db.query(FinanceTag).filter(FinanceTag.name == tag_data["name"]).first()
        if existing is None:
            tag = FinanceTag(
                name=tag_data["name"],
                color=tag_data["color"],
                description="",
                category=tag_data["category"],
                sort_order=tag_data["sort_order"],
                is_active=1,
                ctime=datetime.now(),
                mtime=datetime.now(),
            )
            db.add(tag)
            created_count += 1
            logger.info(f"Seeded default tag: {tag_data['name']}")

    if created_count > 0:
        db.commit()
        logger.info(f"Seeded {created_count} default finance tags")

    return created_count


# ============================================================================
# Internal Helpers
# ============================================================================


def _orm_to_response(tag: FinanceTag) -> FinanceTagResponse:
    """将 ORM 对象转换为响应 DTO"""
    return FinanceTagResponse(
        id=tag.id,
        name=tag.name,
        color=tag.color or "#888888",
        description=tag.description or "",
        category=tag.category or "expense",
        sort_order=tag.sort_order or 0,
        is_active=tag.is_active if tag.is_active is not None else 1,
    )
