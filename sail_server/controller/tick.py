# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket Controller (REST)
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据控制器。

REST 契约（/api/v1/tick）:
- GET  /tickets               列表（status/channel 过滤）
- POST /tickets               创建（SailTick agent / 手工）
- GET  /tickets/{id}          详情
- POST /tickets/{id}/reply    用户回复
- POST /tickets/{id}/resolve  关闭
- POST /tickets/{id}/snooze   暂缓
- GET  /replies?since=        增量拉取已回复/关闭票据（agent SCAN 用）
- POST /expire-overdue        超期票据置 expired（幂等）

鉴权：复用 SAILZEN_API_TOKEN 可选 Bearer 模式（未配置则放行）。
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Optional

from litestar import Controller, Request, get, post
from litestar.exceptions import ClientException, NotAuthorizedException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.tick import (
    TicketCreateRequest,
    TicketReplyRequest,
    TicketResolveRequest,
    TicketResponse,
    TicketSnoozeRequest,
)
from sail_server.model.tick import (
    TicketBadRequestError,
    TicketNotFoundError,
    TicketStateConflictError,
    create_ticket_impl,
    expire_overdue_impl,
    get_ticket_impl,
    list_replies_since_impl,
    list_tickets_impl,
    reply_ticket_impl,
    resolve_ticket_impl,
    snooze_ticket_impl,
)

logger = logging.getLogger(__name__)


def _check_auth(request: Request) -> None:
    """可选 Bearer Token 鉴权：env SAILZEN_API_TOKEN 未设置则放行。"""
    expected = os.environ.get("SAILZEN_API_TOKEN", "")
    if not expected:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {expected}":
        raise NotAuthorizedException(detail="invalid or missing bearer token")


@contextmanager
def _map_errors():
    """model 层异常 → HTTP 状态码（404/409/400）。"""
    try:
        yield
    except TicketNotFoundError as e:
        raise NotFoundException(detail=str(e)) from e
    except TicketStateConflictError as e:
        raise ClientException(status_code=409, detail=str(e)) from e
    except TicketBadRequestError as e:
        raise ClientException(status_code=400, detail=str(e)) from e


class TicketController(Controller):
    """SailTick 票据 REST 控制器。"""

    path = "/"

    @get("/tickets")
    async def list_tickets(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        status: Optional[str] = None,
        channel: Optional[str] = None,
        type: Optional[str] = None,
        limit: int = 100,
    ) -> List[TicketResponse]:
        """列出票据，默认按期待回复时间升序（最急最前）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return list_tickets_impl(db, status=status, channel=channel, type_=type, limit=limit)

    @post("/tickets")
    async def create_ticket(
        self,
        data: TicketCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return create_ticket_impl(db, data)

    @get("/tickets/{ticket_id:int}")
    async def get_ticket(
        self,
        ticket_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return get_ticket_impl(db, ticket_id)

    @post("/tickets/{ticket_id:int}/reply")
    async def reply_ticket(
        self,
        ticket_id: int,
        data: TicketReplyRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return reply_ticket_impl(db, ticket_id, data.reply)

    @post("/tickets/{ticket_id:int}/resolve")
    async def resolve_ticket(
        self,
        ticket_id: int,
        data: TicketResolveRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return resolve_ticket_impl(db, ticket_id, data.resolution)

    @post("/tickets/{ticket_id:int}/snooze")
    async def snooze_ticket(
        self,
        ticket_id: int,
        data: TicketSnoozeRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> TicketResponse:
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return snooze_ticket_impl(db, ticket_id, data.hours)

    @get("/replies")
    async def list_replies(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        since: Optional[str] = None,
    ) -> List[TicketResponse]:
        """增量拉取已回复/关闭票据（agent SCAN 同步用）。since 为 ISO-8601。"""
        _check_auth(request)
        db = next(router_dependency)
        since_dt: Optional[datetime] = None
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            if since_dt.tzinfo is not None:
                since_dt = since_dt.astimezone().replace(tzinfo=None)
        with _map_errors():
            return list_replies_since_impl(db, since=since_dt)

    @post("/expire-overdue")
    async def expire_overdue(
        self, request: Request, router_dependency: Generator[Session, None, None]
    ) -> dict:
        """超期 pending 票据置 expired（幂等）。"""
        _check_auth(request)
        db = next(router_dependency)
        with _map_errors():
            return {"expired": expire_overdue_impl(db)}
