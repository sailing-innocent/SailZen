# -*- coding: utf-8 -*-
# @file history.py
# @brief The History Events Model
# @author sailing-innocent
# @date 2025-10-12
# @version 2.0
# ---------------------------------

from datetime import datetime
from typing import Optional, List

from sail_server.infrastructure.orm.history import HistoryEvent, Person
from sail_server.application.dto.history import (
    HistoryEventCreateRequest,
    HistoryEventUpdateRequest,
    HistoryEventResponse,
    PersonCreateRequest,
    PersonUpdateRequest,
    PersonResponse,
)


def _orm_to_response(event: HistoryEvent) -> HistoryEventResponse:
    """
    将 ORM 模型转换为响应 DTO

    Args:
        event: HistoryEvent ORM 对象

    Returns:
        HistoryEventResponse: 响应 DTO
    """
    return HistoryEventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        rar_tags=event.rar_tags or [],
        tags=event.tags or [],
        start_time=event.start_time,
        end_time=event.end_time,
        related_events=event.related_events or [],
        parent_event=event.parent_event,
        details=event.details or {},
        receive_time=event.receive_time,
    )


def create_event_impl(
    db, event_create: HistoryEventCreateRequest
) -> HistoryEventResponse:
    """
    创建新的历史事件

    Args:
        db: 数据库会话
        event_create: 创建事件请求对象

    Returns:
        HistoryEventResponse: 创建的事件响应
    """
    event = HistoryEvent(
        title=event_create.title,
        description=event_create.description,
        rar_tags=event_create.rar_tags,
        tags=event_create.tags,
        start_time=event_create.start_time,
        end_time=event_create.end_time,
        related_events=event_create.related_events,
        parent_event=event_create.parent_event,
        details=event_create.details,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _orm_to_response(event)


def get_event_impl(db, event_id: int) -> Optional[HistoryEventResponse]:
    """
    根据ID获取单个历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        HistoryEventResponse: 事件响应，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None
    return _orm_to_response(event)


def get_events_impl(
    db,
    skip: int = 0,
    limit: int = -1,
    parent_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    tags: Optional[List[str]] = None,
) -> List[HistoryEventResponse]:
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
        List[HistoryEventResponse]: 事件响应列表
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
    return [_orm_to_response(event) for event in events]


def get_child_events_impl(db, parent_id: int) -> List[HistoryEventResponse]:
    """
    获取指定父事件的所有子事件

    Args:
        db: 数据库会话
        parent_id: 父事件ID

    Returns:
        List[HistoryEventResponse]: 子事件列表
    """
    return get_events_impl(db, parent_id=parent_id)


def get_related_events_impl(db, event_id: int) -> List[HistoryEventResponse]:
    """
    获取与指定事件相关的所有事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        List[HistoryEventResponse]: 相关事件列表
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event or not event.related_events:
        return []

    related = (
        db.query(HistoryEvent).filter(HistoryEvent.id.in_(event.related_events)).all()
    )

    return [_orm_to_response(e) for e in related]


def update_event_impl(
    db, event_id: int, event_update: HistoryEventUpdateRequest
) -> Optional[HistoryEventResponse]:
    """
    更新历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID
        event_update: 更新事件请求对象

    Returns:
        HistoryEventResponse: 更新后的事件响应，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None

    # 只更新提供的字段
    if event_update.title is not None:
        event.title = event_update.title
    if event_update.description is not None:
        event.description = event_update.description
    if event_update.rar_tags is not None:
        event.rar_tags = event_update.rar_tags
    if event_update.tags is not None:
        event.tags = event_update.tags
    if event_update.start_time is not None:
        event.start_time = event_update.start_time
    if event_update.end_time is not None:
        event.end_time = event_update.end_time
    if event_update.related_events is not None:
        event.related_events = event_update.related_events
    if event_update.parent_event is not None:
        event.parent_event = event_update.parent_event
    if event_update.details is not None:
        event.details = event_update.details

    db.commit()
    db.refresh(event)
    return _orm_to_response(event)


def delete_event_impl(db, event_id: int) -> Optional[HistoryEventResponse]:
    """
    删除历史事件

    Args:
        db: 数据库会话
        event_id: 事件ID

    Returns:
        HistoryEventResponse: 被删除的事件响应，如果不存在返回None
    """
    event = db.query(HistoryEvent).filter(HistoryEvent.id == event_id).first()
    if not event:
        return None

    event_data = _orm_to_response(event)
    db.delete(event)
    db.commit()
    return event_data


def search_events_by_keyword_impl(
    db, keyword: str, skip: int = 0, limit: int = 10
) -> List[HistoryEventResponse]:
    """
    通过关键词搜索历史事件（在标题和描述中搜索）

    Args:
        db: 数据库会话
        keyword: 搜索关键词
        skip: 跳过的记录数
        limit: 返回的最大记录数

    Returns:
        List[HistoryEventResponse]: 匹配的事件列表
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
    return [_orm_to_response(event) for event in events]


# ============================================================================
# Person CRUD Operations
# ============================================================================


def _person_to_response(person: Person) -> PersonResponse:
    """
    将 Person ORM 模型转换为响应 DTO

    Args:
        person: Person ORM 对象

    Returns:
        PersonResponse: 响应 DTO
    """
    return PersonResponse(
        id=person.id,
        name=person.name,
        data=person.data,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def create_person_impl(db, person_create: PersonCreateRequest) -> PersonResponse:
    """
    创建新的人物档案

    Args:
        db: 数据库会话
        person_create: 创建人物档案请求对象

    Returns:
        PersonResponse: 创建的人物档案响应
    """
    person = Person(
        name=person_create.name,
        data=person_create.data,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return _person_to_response(person)


def get_person_impl(db, person_id: int) -> Optional[PersonResponse]:
    """
    根据ID获取单个人物档案

    Args:
        db: 数据库会话
        person_id: 人物ID

    Returns:
        PersonResponse: 人物档案响应，如果不存在返回None
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return None
    return _person_to_response(person)


def get_persons_impl(
    db,
    skip: int = 0,
    limit: int = -1,
) -> List[PersonResponse]:
    """
    获取人物档案列表

    Args:
        db: 数据库会话
        skip: 跳过的记录数
        limit: 返回的最大记录数，-1表示不限制

    Returns:
        List[PersonResponse]: 人物档案响应列表
    """
    query = db.query(Person)

    # 按更新时间排序（最新的在前）
    query = query.order_by(Person.updated_at.desc())

    # 分页
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    persons = query.all()
    return [_person_to_response(person) for person in persons]


def update_person_impl(
    db, person_id: int, person_update: PersonUpdateRequest
) -> Optional[PersonResponse]:
    """
    更新人物档案

    Args:
        db: 数据库会话
        person_id: 人物ID
        person_update: 更新人物档案请求对象

    Returns:
        PersonResponse: 更新后的人物档案响应，如果不存在返回None
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return None

    # 只更新提供的字段
    if person_update.name is not None:
        person.name = person_update.name
    if person_update.data is not None:
        person.data = person_update.data

    db.commit()
    db.refresh(person)
    return _person_to_response(person)


def delete_person_impl(db, person_id: int) -> Optional[PersonResponse]:
    """
    删除人物档案

    Args:
        db: 数据库会话
        person_id: 人物ID

    Returns:
        PersonResponse: 被删除的人物档案响应，如果不存在返回None
    """
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        return None

    person_data = _person_to_response(person)
    db.delete(person)
    db.commit()
    return person_data


def search_persons_by_name_impl(
    db, keyword: str, skip: int = 0, limit: int = 10
) -> List[PersonResponse]:
    """
    通过姓名关键词搜索人物档案

    Args:
        db: 数据库会话
        keyword: 搜索关键词
        skip: 跳过的记录数
        limit: 返回的最大记录数

    Returns:
        List[PersonResponse]: 匹配的人物档案列表
    """
    query = db.query(Person).filter(Person.name.ilike(f"%{keyword}%"))

    query = query.order_by(Person.updated_at.desc())

    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)

    persons = query.all()
    return [_person_to_response(person) for person in persons]
