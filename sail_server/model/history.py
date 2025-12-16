# -*- coding: utf-8 -*-
# @file history.py
# @brief The History Events Model
# @author sailing-innocent
# @date 2025-10-12
# @version 1.0
# ---------------------------------

from sail_server.data.history import HistoryEvent, HistoryEventData
from datetime import datetime
from typing import Optional, List


def create_event_impl(db, event_create: HistoryEventData):
    """
    创建新的历史事件

    Args:
        db: 数据库会话
        event_create: 事件数据对象

    Returns:
        HistoryEventData: 创建的事件数据
    """
    event = event_create.create_event()
    db.add(event)
    db.commit()
    db.refresh(event)
    return HistoryEventData.read_from_orm(event)


def get_event_impl(db, event_id: int):
    """
    根据ID获取单个历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        HistoryEventData: 事件数据，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None
    return HistoryEventData.read_from_orm(event)


def get_events_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    parent_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
):
    """
    获取历史事件列表，支持多种过滤条件

    Args:
        db: 数据库会话
        skip: 跳过的记录数
        limit: 返回的最大记录数，-1表示不限制
        parent_id: 父事件ID，用于获取子事件
        start_time: 开始时间过滤
        end_time: 结束时间过滤
        tags: 标签过滤

    Returns:
        List[HistoryEventData]: 事件数据列表
    """
    query = db.query(HistoryEvent)

    # 按父事件过滤
    if parent_id is not None:
        query = query.filter(HistoryEvent.parent_event == parent_id)

    # 按开始时间过滤
    if start_time is not None:
        query = query.filter(HistoryEvent.start_time >= start_time)

    # 按结束时间过滤
    if end_time is not None:
        query = query.filter(HistoryEvent.end_time <= end_time)

    # 按标签过滤 - 使用PostgreSQL的数组包含操作
    if tags is not None and len(tags) > 0:
        for tag in tags:
            query = query.filter(HistoryEvent.tags.contains([tag]))

    # 按接收时间排序（最新的在前）
    query = query.order_by(HistoryEvent.receive_time.desc())

    # 分页
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    events = query.all()
    return [HistoryEventData.read_from_orm(event) for event in events]


def get_child_events_impl(db, parent_id: int):
    """
    获取指定父事件的所有子事件

    Args:
        db: 数据库会话
        parent_id: 父事件ID

    Returns:
        List[HistoryEventData]: 子事件列表
    """
    return get_events_impl(db, parent_id=parent_id)


def get_related_events_impl(db, event_id: int):
    """
    获取与指定事件相关的所有事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        List[HistoryEventData]: 相关事件列表
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event or not event.related_events:
        return []

    related = (
        db.query(HistoryEvent).filter(HistoryEvent.id.in_(event.related_events)).all()
    )

    return [HistoryEventData.read_from_orm(e) for e in related]


def update_event_impl(db, event_id: int, event_update: HistoryEventData):
    """
    更新历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID
        event_update: 更新的事件数据

    Returns:
        HistoryEventData: 更新后的事件数据，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None

    event_update.update_event(event)
    db.commit()
    db.refresh(event)
    return HistoryEventData.read_from_orm(event)


def delete_event_impl(db, event_id: int):
    """
    删除历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        HistoryEventData: 被删除的事件数据，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None

    event_data = HistoryEventData.read_from_orm(event)
    db.delete(event)
    db.commit()
    return event_data


def search_events_by_keyword_impl(db, keyword: str, skip: int = 0, limit: int = 10):
    """
    通过关键词搜索历史事件（在标题和描述中搜索）

    Args:
        db: 数据库会话
        keyword: 搜索关键词
        skip: 跳过的记录数
        limit: 返回的最大记录数

    Returns:
        List[HistoryEventData]: 匹配的事件列表
    """
    query = db.query(HistoryEvent).filter(
        (HistoryEvent.title.ilike(f"%{keyword}%"))
        | (HistoryEvent.description.ilike(f"%{keyword}%"))
    )

    query = query.order_by(HistoryEvent.receive_time.desc())

    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    events = query.all()
    return [HistoryEventData.read_from_orm(event) for event in events]
