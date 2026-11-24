# -*- coding: utf-8 -*-
# @file inbox.py
# @brief Unified UserInbox REST Controller (/api/v1/inbox)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户收件箱 REST 控制器。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, List, Optional

from litestar import Controller, Request, get, post
from litestar.exceptions import ClientException, NotFoundException
from sqlalchemy.orm import Session

from sail_server.application.dto.inbox import (
    InboxCreateRequest,
    InboxDismissRequest,
    InboxEventResponse,
    InboxItemResponse,
    InboxReplyRequest,
    InboxResolveRequest,
    InboxSnoozeRequest,
    InboxSummaryResponse,
    InboxSyncResponse,
)
from sail_server.model.inbox import (
    InboxBadRequestError,
    InboxNotFoundError,
    InboxStateConflictError,
    _to_item_response,
    create_or_upsert_inbox_item_impl,
    dismiss_inbox_item_impl,
    get_inbox_summary_impl,
    list_inbox_events_impl,
    list_inbox_impl,
    mark_all_inbox_read_impl,
    mark_inbox_read_impl,
    reply_inbox_item_impl,
    resolve_inbox_item_impl,
    snooze_inbox_item_impl,
    sync_inbox_impl,
)
from sail_server.utils.user_context import resolve_user_context


@contextmanager
def _map_errors():
    try:
        yield
    except InboxNotFoundError as exc:
        raise NotFoundException(detail=str(exc)) from exc
    except InboxStateConflictError as exc:
        raise ClientException(status_code=409, detail=str(exc)) from exc
    except InboxBadRequestError as exc:
        raise ClientException(status_code=400, detail=str(exc)) from exc


class InboxController(Controller):
    path = "/"

    @get("/")
    async def list_items(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        tab: str = "active",
        domain: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 100,
    ) -> List[InboxItemResponse]:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return list_inbox_impl(
                db,
                ctx.user_id,
                tab=tab,
                source_domain=domain,
                item_kind=kind,
                limit=limit,
            )

    @post("/")
    async def create_item(
        self,
        data: InboxCreateRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            item = create_or_upsert_inbox_item_impl(
                db, ctx.user_id, data, actor_client=ctx.client_type
            )
            return _to_item_response(item)

    @get("/sync")
    async def sync_items(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
        since_seq: int = 0,
        limit: int = 200,
    ) -> InboxSyncResponse:
        """游标增量对账（返回 since_seq 之后的含终态变更 + 当前 active_ids）。"""
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return sync_inbox_impl(
                db,
                ctx.user_id,
                since_seq=since_seq,
                limit=limit,
                device_id=ctx.device_id,
            )

    @get("/summary")
    async def summary(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxSummaryResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return get_inbox_summary_impl(db, ctx.user_id)

    @post("/read-all")
    async def read_all(
        self,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> dict:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            count = mark_all_inbox_read_impl(
                db, ctx.user_id, actor_client=ctx.client_type, device_id=ctx.device_id
            )
            return {"ok": True, "marked_read": count}

    @get("/{item_id:int}/events")
    async def list_events(
        self,
        item_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> List[InboxEventResponse]:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return list_inbox_events_impl(db, ctx.user_id, item_id)

    @post("/{item_id:int}/read")
    async def mark_read(
        self,
        item_id: int,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return mark_inbox_read_impl(
                db,
                ctx.user_id,
                item_id,
                actor_client=ctx.client_type,
                device_id=ctx.device_id,
            )

    @post("/{item_id:int}/reply")
    async def reply_item(
        self,
        item_id: int,
        data: InboxReplyRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return reply_inbox_item_impl(
                db,
                ctx.user_id,
                item_id,
                data.reply,
                source=data.source,
                actor_client=ctx.client_type,
                device_id=ctx.device_id,
            )

    @post("/{item_id:int}/resolve")
    async def resolve_item(
        self,
        item_id: int,
        data: InboxResolveRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return resolve_inbox_item_impl(
                db,
                ctx.user_id,
                item_id,
                resolution_source=data.resolution_source,
                resolution_summary=data.resolution_summary,
                actor_client=ctx.client_type,
                device_id=ctx.device_id,
            )

    @post("/{item_id:int}/snooze")
    async def snooze_item(
        self,
        item_id: int,
        data: InboxSnoozeRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return snooze_inbox_item_impl(
                db,
                ctx.user_id,
                item_id,
                option=data.option,
                hours=data.hours,
                actor_client=ctx.client_type,
                device_id=ctx.device_id,
            )

    @post("/{item_id:int}/dismiss")
    async def dismiss_item(
        self,
        item_id: int,
        data: InboxDismissRequest,
        request: Request,
        router_dependency: Generator[Session, None, None],
    ) -> InboxItemResponse:
        db = next(router_dependency)
        ctx = resolve_user_context(request, db)
        with _map_errors():
            return dismiss_inbox_item_impl(
                db,
                ctx.user_id,
                item_id,
                reason=data.reason,
                actor_client=ctx.client_type,
                device_id=ctx.device_id,
            )
