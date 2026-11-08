# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket 业务逻辑（票据状态机）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据业务实现。

状态机（设计文档 sailtick.md §6.2）:
  pending → replied → resolved
  pending → expired       （超 expected_reply_by）
  pending → snoozed → pending

幂等性: reply/resolve/snooze 对终态票据幂等返回当前状态。
推送联动: 创建 high/urgent（或 push=force）票据时广播 reminder_ws（Android）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from sail_server.application.dto.tick import (
    TicketCreateRequest,
    TicketResponse,
)
from sailzen_orm.tick import SailTickTicket

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_REPLIED = "replied"
STATUS_RESOLVED = "resolved"
STATUS_EXPIRED = "expired"
STATUS_SNOOZED = "snoozed"

TERMINAL_STATUSES = {STATUS_RESOLVED, STATUS_EXPIRED}
VALID_TYPES = {"question", "task", "approval", "info"}
VALID_PRIORITY = {"low", "normal", "high", "urgent"}


class TicketError(Exception):
    """票据业务错误基类。"""


class TicketNotFoundError(TicketError):
    """票据不存在。"""


class TicketBadRequestError(TicketError):
    """请求参数非法。"""


class TicketStateConflictError(TicketError):
    """状态冲突。"""


def _get_or_404(db: Session, ticket_id: int) -> SailTickTicket:
    t = db.get(SailTickTicket, ticket_id)
    if not t:
        raise TicketNotFoundError(f"ticket {ticket_id} not found")
    return t


def _to_response(t: SailTickTicket) -> TicketResponse:
    return TicketResponse.model_validate(t)


def _push_if_needed(t: SailTickTicket) -> None:
    """高优先/强制推送的票据广播给在线 Android 设备（失败仅告警）。"""
    should_push = t.push == "force" or (
        t.push == "auto" and t.priority in ("high", "urgent")
    )
    if not should_push:
        return
    try:
        import asyncio

        from sail_server.utils.reminder_ws import get_reminder_push_manager

        manager = get_reminder_push_manager()
        payload = {
            "id": t.id,
            "type": f"tick.ticket.{t.type}",
            "title": t.title,
            "body": t.body[:200],
            "priority": t.priority,
            "source": "agent",
            "payload": {"ticket_id": t.id, "ticket_type": t.type},
            "state": STATUS_PENDING,
        }
        # 同步上下文里可能没有事件循环（如 pytest），退化为 fire-and-forget task
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(manager.broadcast_reminder(payload))
        except RuntimeError:
            logger.debug("no running loop, skip push broadcast for ticket %s", t.id)
    except Exception as exc:
        logger.warning("ticket push broadcast failed (non-fatal): %s", exc)


# ── CRUD ────────────────────────────────────────────────────────────────


def create_ticket_impl(db: Session, req: TicketCreateRequest) -> TicketResponse:
    """创建票据。"""
    if req.type not in VALID_TYPES:
        raise TicketBadRequestError(f"invalid type: {req.type!r}")
    if req.priority not in VALID_PRIORITY:
        raise TicketBadRequestError(f"invalid priority: {req.priority!r}")

    t = SailTickTicket(
        tick_id=req.tick_id,
        type=req.type,
        title=req.title,
        body=req.body,
        priority=req.priority,
        channel=req.channel,
        expected_reply_by=req.expected_reply_by,
        fallback_assumption=req.fallback_assumption,
        push=req.push,
        status=STATUS_PENDING,
    )
    db.add(t)
    db.flush()
    db.commit()
    db.refresh(t)
    _push_if_needed(t)
    logger.info("[tick] ticket %s created: type=%s priority=%s", t.id, t.type, t.priority)
    return _to_response(t)


def get_ticket_impl(db: Session, ticket_id: int) -> TicketResponse:
    return _to_response(_get_or_404(db, ticket_id))


def list_tickets_impl(
    db: Session,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    type_: Optional[str] = None,
    limit: int = 100,
) -> List[TicketResponse]:
    """列出票据，默认按期待回复时间升序（最急最前）。"""
    q = db.query(SailTickTicket)
    if status:
        q = q.filter(SailTickTicket.status == status)
    if channel:
        q = q.filter(SailTickTicket.channel == channel)
    if type_:
        q = q.filter(SailTickTicket.type == type_)
    rows = (
        q.order_by(SailTickTicket.expected_reply_by.asc().nullslast(), SailTickTicket.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_response(r) for r in rows]


# ── 状态机 ──────────────────────────────────────────────────────────────


def reply_ticket_impl(db: Session, ticket_id: int, reply: str) -> TicketResponse:
    """用户回复。pending/snoozed → replied。"""
    t = _get_or_404(db, ticket_id)
    if t.status in TERMINAL_STATUSES:
        # 幂等返回
        return _to_response(t)
    if t.status not in (STATUS_PENDING, STATUS_SNOOZED):
        raise TicketStateConflictError(f"ticket {ticket_id} status={t.status}, cannot reply")
    t.reply = reply
    t.replied_at = datetime.now()
    t.status = STATUS_REPLIED
    db.commit()
    db.refresh(t)
    logger.info("[tick] ticket %s replied", t.id)
    return _to_response(t)


def resolve_ticket_impl(db: Session, ticket_id: int, resolution: str = "") -> TicketResponse:
    """关闭票据（ replied/pending → resolved ）。终态幂等。"""
    t = _get_or_404(db, ticket_id)
    if t.status == STATUS_RESOLVED:
        return _to_response(t)
    if t.status == STATUS_EXPIRED:
        raise TicketStateConflictError(f"ticket {ticket_id} already expired")
    t.status = STATUS_RESOLVED
    t.resolution = resolution
    t.resolved_at = datetime.now()
    db.commit()
    db.refresh(t)
    logger.info("[tick] ticket %s resolved", t.id)
    return _to_response(t)


def snooze_ticket_impl(db: Session, ticket_id: int, hours: int = 24) -> TicketResponse:
    """暂缓：pending → snoozed，期待回复时间顺延。"""
    t = _get_or_404(db, ticket_id)
    if t.status in TERMINAL_STATUSES:
        return _to_response(t)
    if t.status != STATUS_PENDING:
        raise TicketStateConflictError(f"ticket {ticket_id} status={t.status}, cannot snooze")
    t.status = STATUS_SNOOZED
    base = t.expected_reply_by or datetime.now()
    t.expected_reply_by = base + timedelta(hours=hours)
    db.commit()
    db.refresh(t)
    logger.info("[tick] ticket %s snoozed %dh", t.id, hours)
    return _to_response(t)


def expire_overdue_impl(db: Session) -> int:
    """把超期 pending 票据置为 expired（幂等）。返回处理数。"""
    now = datetime.now()
    rows = (
        db.query(SailTickTicket)
        .filter(
            SailTickTicket.status == STATUS_PENDING,
            SailTickTicket.expected_reply_by.isnot(None),
            SailTickTicket.expected_reply_by < now,
        )
        .all()
    )
    for t in rows:
        t.status = STATUS_EXPIRED
    db.commit()
    if rows:
        logger.info("[tick] expired %d overdue tickets", len(rows))
    return len(rows)


def list_replies_since_impl(db: Session, since: Optional[datetime] = None) -> List[TicketResponse]:
    """拉取自 since 以来被回复/关闭的票据（agent SCAN 同步用）。"""
    q = db.query(SailTickTicket).filter(
        SailTickTicket.status.in_([STATUS_REPLIED, STATUS_RESOLVED])
    )
    if since is not None:
        q = q.filter(SailTickTicket.updated_at >= since)
    rows = q.order_by(SailTickTicket.updated_at.asc()).limit(200).all()
    return [_to_response(r) for r in rows]
