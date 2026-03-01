# -*- coding: utf-8 -*-
# @file history.py
# @brief History Events Controller
# @author sailing-innocent
# @date 2025-10-12
# @version 1.0
# ---------------------------------
from __future__ import annotations
from litestar import Controller, delete, get, post, put, Request
from litestar.exceptions import NotFoundException

from sail_server.application.dto.history import (
    HistoryEventCreateRequest,
    HistoryEventUpdateRequest,
    HistoryEventResponse,
)
from sail_server.model.history import (
    create_event_impl,
    get_event_impl,
    get_events_impl,
    get_child_events_impl,
    get_related_events_impl,
    update_event_impl,
    delete_event_impl,
    search_events_by_keyword_impl,
)
from sqlalchemy.orm import Session
from typing import Generator, List, Optional


class HistoryEventController(Controller):
    """历史事件控制器"""
    path = "/event"

    @get("")
    async def get_events(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        skip: int = 0,
        limit: int = 10,
        parent_id: Optional[int] = None,
        tags: Optional[str] = None,  # 逗号分隔的标签字符串
    ) -> List[HistoryEventResponse]:
        """
        获取历史事件列表
        
        Query Parameters:
        - skip: 跳过的记录数
        - limit: 返回的最大记录数
        - parent_id: 父事件ID，用于获取子事件
        - tags: 标签过滤，多个标签用逗号分隔
        """
        db = next(router_dependency)
        
        # 解析标签
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        events = get_events_impl(
            db, 
            skip=skip, 
            limit=limit, 
            parent_id=parent_id, 
            tags=tag_list
        )
        request.logger.info(f"Get events: {len(events)}")
        return events

    @get("/search")
    async def search_events(
        self,
        router_dependency: Generator[Session, None, None],
        request: Request,
        keyword: str,
        skip: int = 0,
        limit: int = 10,
    ) -> List[HistoryEventResponse]:
        """
        通过关键词搜索历史事件
        
        Query Parameters:
        - keyword: 搜索关键词
        - skip: 跳过的记录数
        - limit: 返回的最大记录数
        """
        db = next(router_dependency)
        events = search_events_by_keyword_impl(db, keyword, skip, limit)
        request.logger.info(f"Search events with keyword '{keyword}': {len(events)}")
        return events

    @get("/{event_id:int}")
    async def get_event(
        self,
        event_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> HistoryEventResponse:
        """
        根据ID获取单个历史事件
        """
        db = next(router_dependency)
        event = get_event_impl(db, event_id)
        request.logger.info(f"Get event {event_id}: {event}")
        if not event:
            raise NotFoundException(detail=f"Event with ID {event_id} not found")
        return event

    @get("/{event_id:int}/children")
    async def get_child_events(
        self,
        event_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[HistoryEventResponse]:
        """
        获取指定事件的所有子事件
        """
        db = next(router_dependency)
        # 先验证父事件存在
        parent_event = get_event_impl(db, event_id)
        if not parent_event:
            raise NotFoundException(detail=f"Parent event with ID {event_id} not found")
        
        children = get_child_events_impl(db, event_id)
        request.logger.info(f"Get child events for {event_id}: {len(children)}")
        return children

    @get("/{event_id:int}/related")
    async def get_related_events(
        self,
        event_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> List[HistoryEventResponse]:
        """
        获取与指定事件相关的所有事件
        """
        db = next(router_dependency)
        # 先验证事件存在
        event = get_event_impl(db, event_id)
        if not event:
            raise NotFoundException(detail=f"Event with ID {event_id} not found")
        
        related = get_related_events_impl(db, event_id)
        request.logger.info(f"Get related events for {event_id}: {len(related)}")
        return related

    @post("/")
    async def create_event(
        self,
        data: HistoryEventCreateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> HistoryEventResponse:
        """
        创建新的历史事件
        
        最低要求：title + description
        """
        db = next(router_dependency)
        event = create_event_impl(db, data)
        request.logger.info(f"Created event: {event.title}")
        return event

    @put("/{event_id:int}")
    async def update_event(
        self,
        event_id: int,
        data: HistoryEventUpdateRequest,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> HistoryEventResponse:
        """
        更新历史事件
        
        可以部分更新，补充其他信息
        """
        db = next(router_dependency)
        event = update_event_impl(db, event_id, data)
        request.logger.info(f"Updated event {event_id}: {event}")
        if not event:
            raise NotFoundException(detail=f"Event with ID {event_id} not found")
        return event

    @delete("/{event_id:int}", status_code=200)
    async def delete_event(
        self,
        event_id: int,
        router_dependency: Generator[Session, None, None],
        request: Request,
    ) -> HistoryEventResponse:
        """
        删除历史事件
        """
        db = next(router_dependency)
        event = delete_event_impl(db, event_id)
        request.logger.info(f"Deleted event {event_id}")
        if not event:
            raise NotFoundException(detail=f"Event with ID {event_id} not found")
        return event
