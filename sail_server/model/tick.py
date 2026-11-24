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
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.application.dto.tick import (
    DailyReportResponse,
    DailyReportUpsertRequest,
    HealthCoachSummaryResponse,
    TickMessageCreateRequest,
    TickMessageResponse,
    TicketCreateRequest,
    TicketResponse,
)
from sailzen_orm.tick import SailTickDailyReport, SailTickMessage, SailTickTicket

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_REPLIED = "replied"
STATUS_RESOLVED = "resolved"
STATUS_EXPIRED = "expired"
STATUS_SNOOZED = "snoozed"

TERMINAL_STATUSES = {STATUS_RESOLVED, STATUS_EXPIRED}
VALID_TYPES = {"question", "task", "approval", "info"}
VALID_PRIORITY = {"low", "normal", "high", "urgent"}
VALID_MSG_DIRECTIONS = {"user_to_agent", "agent_to_user"}
VALID_MSG_CATEGORIES = {"diet", "weight", "daily_info", "mood", "exercise", "general"}


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
    return TicketResponse(
        id=t.id,
        tick_id=t.tick_id or "",
        type=t.type or "question",
        topic=getattr(t, "topic", None) or "",
        title=t.title,
        body=t.body or "",
        meta=getattr(t, "meta", None) if isinstance(getattr(t, "meta", None), dict) else {},
        status=t.status or STATUS_PENDING,
        expected_reply_by=t.expected_reply_by,
        replied_at=t.replied_at,
        reply=t.reply,
        resolved_at=t.resolved_at,
        resolution=t.resolution,
        fallback_assumption=t.fallback_assumption or "",
        priority=t.priority or "normal",
        channel=t.channel or "web",
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _create_and_push_agent_reminder(
    db: Session,
    rem_type: str,
    title: str,
    body: str,
    priority: str,
    payload: Dict[str, Any],
    expire_minutes: int = 720,
) -> Optional[int]:
    """持久化一条 source='agent' 的 Reminder 并向在线 Android 设备广播，返回新 Reminder ID。

    这样无论 Android 当前 WS 在线与否：
    - 在线设备通过 WS 立即收到通知；
    - 离线设备稍后通过 /api/v1/reminder/pending 或 /api/v1/inbox/sync 都能可靠补齐。
    """
    try:
        import asyncio

        from sail_server.application.dto.reminder import ReminderResponse
        from sail_server.utils.reminder_ws import get_reminder_push_manager
        from sailzen_orm.reminder import Reminder

        now = datetime.now()
        manager = get_reminder_push_manager()
        online_fn = getattr(manager, "online_device_ids", None)
        has_online = bool(online_fn()) if callable(online_fn) else True

        rem = Reminder(
            type=rem_type,
            title=title,
            body=body[:500],
            priority=priority if priority in VALID_PRIORITY else "normal",
            source="agent",
            state="DELIVERED" if has_online else "PENDING",
            trigger_time=now,
            expire_after_minutes=expire_minutes,
            last_delivered_at=now if has_online else None,
            payload=payload,
        )
        db.add(rem)
        db.commit()
        db.refresh(rem)

        ws_payload = ReminderResponse.model_validate(rem).model_dump(mode="json")
        try:
            loop = asyncio.get_running_loop()
            res = manager.broadcast_reminder(ws_payload)
            if asyncio.iscoroutine(res):
                loop.create_task(res)
        except RuntimeError:
            logger.debug("no running loop, reminder %s persisted for poll delivery", rem.id)
        return rem.id
    except Exception as exc:
        logger.warning("agent reminder persist/push failed (non-fatal): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _resolve_linked_ticket_reminders(db: Session, ticket_id: int) -> None:
    """票据已回复/关闭/过期时，同步关闭关联的未终态 agent Reminder，避免手机收件箱残留。"""
    try:
        from sailzen_orm.reminder import Reminder

        active_rems = (
            db.query(Reminder)
            .filter(
                Reminder.source == "agent",
                Reminder.state.in_(["PENDING", "DELIVERED", "SNOOZED", "OPENED"]),
            )
            .all()
        )
        changed = False
        for rem in active_rems:
            if isinstance(rem.payload, dict) and rem.payload.get("ticket_id") == ticket_id:
                rem.state = "RESOLVED"
                changed = True
        if changed:
            db.commit()
    except Exception as exc:
        logger.debug("resolve linked reminders skipped (non-fatal): %s", exc)


def _push_if_needed(db: Session, t: SailTickTicket) -> Optional[int]:
    """高优先/强制推送的票据落库 Reminder 并广播给在线 Android 设备（失败仅告警）。"""
    should_push = t.push == "force" or (
        t.push == "auto" and t.priority in ("high", "urgent")
    )
    if not should_push:
        return None
    return _create_and_push_agent_reminder(
        db=db,
        rem_type=f"tick.ticket.{t.type}",
        title=t.title,
        body=(t.body or "")[:300],
        priority=t.priority or "normal",
        payload={
            "ticket_id": t.id,
            "ticket_type": t.type,
            "topic": getattr(t, "topic", "") or "",
        },
        expire_minutes=1440,
    )


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
        topic=req.topic or "",
        title=req.title,
        body=req.body,
        meta=req.meta or {},
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
    rem_id = _push_if_needed(db, t)
    try:
        from sail_server.model.inbox import project_ticket_to_inbox

        should_notify = t.push == "force" or (
            t.push == "auto" and t.priority in ("high", "urgent")
        )
        project_ticket_to_inbox(db, t, reminder_id=rem_id, notify=should_notify)
        db.refresh(t)
    except Exception as exc:
        logger.debug("[tick] project_ticket_to_inbox skipped: %s", exc)
    logger.info("[tick] ticket %s created: type=%s topic=%s priority=%s", t.id, t.type, t.topic, t.priority)
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
    _resolve_linked_ticket_reminders(db, t.id)
    try:
        from sail_server.model.inbox import sync_inbox_on_ticket_changed

        sync_inbox_on_ticket_changed(db, t, action="replied")
    except Exception as exc:
        logger.debug("[tick] sync inbox on reply skipped: %s", exc)
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
    _resolve_linked_ticket_reminders(db, t.id)
    try:
        from sail_server.model.inbox import sync_inbox_on_ticket_changed

        sync_inbox_on_ticket_changed(db, t, action="resolved")
    except Exception as exc:
        logger.debug("[tick] sync inbox on resolve skipped: %s", exc)
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
    try:
        from sail_server.model.inbox import sync_inbox_on_ticket_changed

        sync_inbox_on_ticket_changed(db, t, action="snoozed")
    except Exception as exc:
        logger.debug("[tick] sync inbox on snooze skipped: %s", exc)
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
    for t in rows:
        _resolve_linked_ticket_reminders(db, t.id)
        try:
            from sail_server.model.inbox import sync_inbox_on_ticket_changed

            sync_inbox_on_ticket_changed(db, t, action="expired", actor_client="system")
        except Exception:
            pass
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


# ── 用户主动消息 / 静默餐饮收集 ──────────────────────────────────────────────


def _infer_meal_type(now: datetime, meta: Dict[str, Any]) -> str:
    raw = str(meta.get("meal_type") or "").strip().lower()
    if raw in ("breakfast", "lunch", "dinner", "snack"):
        return raw
    h = now.hour
    if 5 <= h < 10:
        return "breakfast"
    if 10 <= h < 15:
        return "lunch"
    if 16 <= h < 21:
        return "dinner"
    return "snack"


def _to_message_response(m: SailTickMessage) -> TickMessageResponse:
    return TickMessageResponse(
        id=m.id,
        direction=m.direction or "user_to_agent",
        category=m.category or "diet",
        content=m.content,
        meta=m.meta if isinstance(m.meta, dict) else {},
        source_channel=m.source_channel or "android",
        status=m.status or "unread",
        ingested_by_tick_id=m.ingested_by_tick_id,
        created_at=m.created_at,
        ingested_at=m.ingested_at,
    )


def create_message_impl(
    db: Session, req: TickMessageCreateRequest
) -> TickMessageResponse:
    """保存用户主动发送的餐饮/日常消息，无需等待 AI 实时回复。"""
    if req.direction not in VALID_MSG_DIRECTIONS:
        raise TicketBadRequestError(f"invalid direction: {req.direction!r}")
    if req.category not in VALID_MSG_CATEGORIES:
        raise TicketBadRequestError(f"invalid category: {req.category!r}")
    content = (req.content or "").strip()
    if not content:
        raise TicketBadRequestError("content cannot be empty")

    now = datetime.now()
    meta = dict(req.meta or {})

    # 餐饮类主动消息同步落库一条轻量 DietLog，使健康页饮食模块立即可见
    if req.direction == "user_to_agent" and req.category == "diet" and req.auto_log_diet:
        try:
            from sailzen_orm.health import DietLog

            meal_type = _infer_meal_type(now, meta)
            meta["meal_type"] = meal_type
            htime = now
            if meta.get("htime"):
                try:
                    htime = datetime.fromtimestamp(float(meta["htime"]))
                except (ValueError, TypeError):
                    htime = now
            calories = None
            if meta.get("calories") is not None:
                try:
                    calories = float(meta["calories"])
                except (ValueError, TypeError):
                    calories = None
            diet = DietLog(
                meal_type=meal_type,
                htime=htime,
                description=content,
                calories=calories,
            )
            db.add(diet)
            db.flush()
            meta["linked_diet_id"] = diet.id
        except Exception as exc:
            logger.warning("[tick] auto_log_diet failed (non-fatal): %s", exc)

    msg = SailTickMessage(
        direction=req.direction,
        category=req.category,
        content=content,
        meta=meta,
        source_channel=req.source_channel or "android",
        status="unread",
        created_at=now,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # 跨端自动消解：用户在 Web/Android 健康页发餐饮/体重/运动/睡眠消息时，自动消解匹配的待回提问与提醒
    if req.direction == "user_to_agent":
        try:
            from sail_server.model.inbox_resolver import reconcile_domain_signal

            actor = req.source_channel or "web"
            if req.category == "diet":
                meal_type = meta.get("meal_type") or _infer_meal_type(now, meta)
                reconcile_domain_signal(
                    db,
                    domain="health",
                    event="diet.logged",
                    payload={
                        "meal_type": meal_type,
                        "date": now.date().isoformat(),
                        "summary": content,
                        "message_id": msg.id,
                        "diet_id": meta.get("linked_diet_id"),
                    },
                    actor_client=actor,
                )
            elif req.category == "weight":
                reconcile_domain_signal(
                    db,
                    domain="health",
                    event="weight.logged",
                    payload={"date": now.date().isoformat(), "summary": content, "message_id": msg.id},
                    actor_client=actor,
                )
            elif req.category == "exercise":
                reconcile_domain_signal(
                    db,
                    domain="health",
                    event="exercise.logged",
                    payload={"date": now.date().isoformat(), "summary": content, "message_id": msg.id},
                    actor_client=actor,
                )
        except Exception as exc:
            logger.debug("[tick] message auto-resolve skipped: %s", exc)

    logger.info(
        "[tick] message %s saved: direction=%s category=%s channel=%s",
        msg.id,
        msg.direction,
        msg.category,
        msg.source_channel,
    )
    return _to_message_response(msg)


def list_messages_impl(
    db: Session,
    status: Optional[str] = None,
    category: Optional[str] = None,
    direction: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
) -> List[TickMessageResponse]:
    q = db.query(SailTickMessage)
    if status:
        q = q.filter(SailTickMessage.status == status)
    if category:
        q = q.filter(SailTickMessage.category == category)
    if direction:
        q = q.filter(SailTickMessage.direction == direction)
    if since is not None:
        q = q.filter(SailTickMessage.created_at >= since)
    rows = q.order_by(SailTickMessage.created_at.desc(), SailTickMessage.id.desc()).limit(limit).all()
    return [_to_message_response(r) for r in rows]


def ingest_messages_impl(
    db: Session, message_ids: List[int], tick_id: str = ""
) -> int:
    """标记一批用户消息已被 SailTick 吸收整合（幂等）。"""
    if not message_ids:
        return 0
    now = datetime.now()
    rows = (
        db.query(SailTickMessage)
        .filter(
            SailTickMessage.id.in_(message_ids),
            SailTickMessage.status == "unread",
        )
        .all()
    )
    for row in rows:
        row.status = "ingested"
        row.ingested_by_tick_id = tick_id or ""
        row.ingested_at = now
    db.commit()
    return len(rows)


# ── 每日睡前体重与健康日报 ────────────────────────────────────────────────────


def _to_report_response(r: SailTickDailyReport) -> DailyReportResponse:
    return DailyReportResponse(
        id=r.id,
        report_date=r.report_date,
        tick_id=r.tick_id or "",
        title=r.title,
        summary=r.summary or "",
        body_markdown=r.body_markdown or "",
        weight_snapshot=r.weight_snapshot if isinstance(r.weight_snapshot, dict) else {},
        diet_summary=r.diet_summary if isinstance(r.diet_summary, dict) else {},
        plan_update=r.plan_update if isinstance(r.plan_update, dict) else {},
        tomorrow_focus=r.tomorrow_focus if isinstance(r.tomorrow_focus, list) else [],
        pushed=bool(r.pushed),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def upsert_daily_report_impl(
    db: Session, req: DailyReportUpsertRequest
) -> DailyReportResponse:
    """幂等创建或更新某一天的睡前健康日报，按需向 Android 推送一次通知。"""
    report_date = (req.report_date or "").strip()[:10]
    if not report_date:
        raise TicketBadRequestError("report_date is required (YYYY-MM-DD)")

    now = datetime.now()
    rep = (
        db.query(SailTickDailyReport)
        .filter(SailTickDailyReport.report_date == report_date)
        .first()
    )
    already_pushed = bool(rep.pushed) if rep is not None else False
    if rep is None:
        rep = SailTickDailyReport(
            report_date=report_date,
            tick_id=req.tick_id or "",
            title=req.title,
            summary=req.summary or "",
            body_markdown=req.body_markdown or "",
            weight_snapshot=req.weight_snapshot or {},
            diet_summary=req.diet_summary or {},
            plan_update=req.plan_update or {},
            tomorrow_focus=list(req.tomorrow_focus or []),
            pushed=False,
            created_at=now,
            updated_at=now,
        )
        db.add(rep)
    else:
        rep.tick_id = req.tick_id or rep.tick_id
        rep.title = req.title
        rep.summary = req.summary or ""
        rep.body_markdown = req.body_markdown or ""
        rep.weight_snapshot = req.weight_snapshot or {}
        rep.diet_summary = req.diet_summary or {}
        rep.plan_update = req.plan_update or {}
        rep.tomorrow_focus = list(req.tomorrow_focus or [])
        rep.updated_at = now

    db.commit()
    db.refresh(rep)

    # 同一天日报避免重复轰炸推送
    rem_id: Optional[int] = None
    if req.push and not already_pushed:
        rem_id = _create_and_push_agent_reminder(
            db=db,
            rem_type="tick.daily_report",
            title=rep.title,
            body=(rep.summary or rep.body_markdown or "")[:300],
            priority="normal",
            payload={
                "report_date": rep.report_date,
                "report_id": rep.id,
                "kind": "daily_report",
            },
            expire_minutes=720,
        )
        if rem_id is not None:
            rep.pushed = True
            db.commit()
            db.refresh(rep)

    try:
        from sail_server.model.inbox import project_daily_report_to_inbox

        project_daily_report_to_inbox(
            db, rep, reminder_id=rem_id, notify=bool(req.push and not already_pushed)
        )
    except Exception as exc:
        logger.debug("[tick] project_daily_report_to_inbox skipped: %s", exc)

    logger.info("[tick] daily report upserted: date=%s pushed=%s", rep.report_date, rep.pushed)
    return _to_report_response(rep)


def list_daily_reports_impl(db: Session, limit: int = 14) -> List[DailyReportResponse]:
    rows = (
        db.query(SailTickDailyReport)
        .order_by(SailTickDailyReport.report_date.desc())
        .limit(limit)
        .all()
    )
    return [_to_report_response(r) for r in rows]


def get_latest_daily_report_impl(db: Session) -> Optional[DailyReportResponse]:
    row = (
        db.query(SailTickDailyReport)
        .order_by(SailTickDailyReport.report_date.desc())
        .first()
    )
    return _to_report_response(row) if row else None


def get_daily_report_by_date_impl(
    db: Session, report_date: str
) -> Optional[DailyReportResponse]:
    row = (
        db.query(SailTickDailyReport)
        .filter(SailTickDailyReport.report_date == report_date[:10])
        .first()
    )
    return _to_report_response(row) if row else None


def get_health_coach_summary_impl(db: Session) -> HealthCoachSummaryResponse:
    """聚合健康页所需的 AI 教练动态计划、最新睡前日报、待回复提问与今日主动记录。"""
    from sail_server.model.health import (
        get_active_weight_plan_impl,
        get_weight_plan_progress_impl,
    )

    active_plan = get_active_weight_plan_impl(db)
    plan_progress = get_weight_plan_progress_impl(db) if active_plan else None
    latest_report = get_latest_daily_report_impl(db)
    pending_tickets = list_tickets_impl(db, status=STATUS_PENDING, limit=10)

    today_start = datetime.combine(date.today(), datetime.min.time())
    today_messages = list_messages_impl(
        db,
        direction="user_to_agent",
        since=today_start,
        limit=30,
    )

    from sail_server.model.tick_intake import list_image_intake_drafts_impl

    pending_drafts = list_image_intake_drafts_impl(db, status="pending_confirm", limit=5)

    return HealthCoachSummaryResponse(
        active_plan=active_plan.model_dump(mode="json") if active_plan else None,
        plan_progress=plan_progress,
        latest_report=latest_report,
        pending_tickets=pending_tickets[:5],
        pending_ticket_count=len(pending_tickets),
        today_messages=today_messages,
        pending_intake_drafts=pending_drafts,
    )
