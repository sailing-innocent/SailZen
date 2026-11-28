# -*- coding: utf-8 -*-
# @file inbox.py
# @brief Unified UserInbox Model Layer (统一收件箱状态机、投影、单调游标同步与双向联动)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户收件箱业务模型层。

职责：
1. 维护 user_inbox_items 单调递增 sync_seq，提供基于游标的增量同步与全量 active_ids 对账；
2. 将 SailTickTicket、SailTickDailyReport、Reminder 等多路消息统一投影到 UserInboxItem；
3. 统一处理回复/完成/延后/忽略/已读动作，双向回写源表并通过 UserSyncHub 实时广播给全端；
4. 彻底消除多端消息状态割裂与 Android 本地缓存终态残留。
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from sail_server.application.dto.inbox import (
    InboxCreateRequest,
    InboxEventResponse,
    InboxItemResponse,
    InboxSummaryResponse,
    InboxSyncResponse,
)
from sail_server.model.user import is_user_in_quiet_hours
from sail_server.utils.user_sync_ws import get_user_sync_hub
from sailzen_orm.inbox import UserInboxEvent, UserInboxItem
from sailzen_orm.reminder import Device, Reminder, ReminderEvent
from sailzen_orm.tick import SailTickDailyReport, SailTickTicket

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_SNOOZED = "snoozed"
STATUS_OPENED = "opened"
STATUS_ANSWERED = "answered"
STATUS_RESOLVED = "resolved"
STATUS_DISMISSED = "dismissed"
STATUS_EXPIRED = "expired"
STATUS_CANCELED = "canceled"

ACTIVE_STATUSES = {STATUS_PENDING, STATUS_DELIVERED, STATUS_SNOOZED, STATUS_OPENED}
TERMINAL_STATUSES = {
    STATUS_ANSWERED,
    STATUS_RESOLVED,
    STATUS_DISMISSED,
    STATUS_EXPIRED,
    STATUS_CANCELED,
}

VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_TARGET_DOMAINS = {"health", "rhythm", "finance", "general", "system"}

_SEQ_LOCK = threading.Lock()


def resolve_domain_routing(
    *,
    domain: str = "",
    source_domain: str = "",
    topic: str = "",
    title: str = "",
    body: str = "",
    item_kind: str = "",
    ticket_type: str = "",
    ticket_id: Optional[int] = None,
    report_date: str = "",
    explicit_persona: str = "",
    explicit_clients: Optional[List[str]] = None,
    explicit_deep_link: str = "",
) -> Dict[str, Any]:
    """统一业务域、交互角色、目标终端与精确落地页深链推导器（彻底告别写死 /health/coach）。"""
    dom = (domain or "").strip().lower()
    if dom not in ("health", "rhythm", "finance", "general", "system"):
        if dom in ("diet", "weight", "sleep", "exercise", "mood"):
            dom = "health"
        elif dom in ("plan", "schedule", "project", "task", "work"):
            dom = "rhythm"
        elif dom in ("money", "bill", "budget", "account"):
            dom = "finance"
        else:
            dom = ""

    if not dom:
        if item_kind == "report" or topic == "daily_report":
            dom = "general"
        elif source_domain in ("health", "rhythm", "finance"):
            dom = source_domain
        else:
            t_low = (topic or "").strip().lower()
            combined = f"{t_low} {title} {body[:120]}".lower()
            if t_low.startswith(("diet", "weight", "sleep", "exercise", "mood", "health", "canteen", "dinner", "breakfast", "lunch", "gym", "height")):
                dom = "health"
            elif t_low.startswith(("rhythm", "project", "schedule", "focus", "wake", "spare", "meeting", "affair", "timeline", "task")):
                dom = "rhythm"
            elif t_low.startswith(("finance", "bill", "budget", "money", "account", "reconcile", "hygiene")):
                dom = "finance"
            elif any(k in combined for k in ("体重", "称重", "午饭", "晚饭", "早饭", "食堂", "饮食", "热量", "运动", "健身", "睡眠", "熬夜", "减脂", "聚餐")):
                dom = "health"
            elif any(k in combined for k in ("账单", "消费", "余额", "平账", "支出", "预算", "记账", "打标", "微信余额", "支付宝")):
                dom = "finance"
            elif any(k in combined for k in ("项目", "日程", "时间线", "里程碑", "待办", "排期", "开会", "专注", "工作时段", "下班", "起床", "作息", "ddl")):
                dom = "rhythm"
            elif source_domain == "system":
                dom = "system"
            else:
                dom = "general"

    persona = (explicit_persona or "").strip() or {
        "health": "health_coach",
        "rhythm": "rhythm_planner",
        "finance": "finance_secretary",
        "system": "system",
    }.get(dom, "chief_steward")

    if isinstance(explicit_clients, list) and explicit_clients:
        clients = [str(c) for c in explicit_clients if str(c).strip()]
    elif ticket_type == "approval" or item_kind == "approval":
        clients = ["web", "vscode", "android"]
    elif dom == "rhythm":
        clients = ["android", "web", "vscode"]
    else:
        clients = ["android", "web"]

    deep_link = (explicit_deep_link or "").strip()
    if not deep_link:
        if item_kind == "report" or topic == "daily_report":
            deep_link = f"/inbox/report/{report_date}" if report_date else "/tick"
        elif dom == "health":
            deep_link = f"/health/coach?ticket={ticket_id}" if ticket_id else "/health/coach"
        elif dom == "rhythm":
            deep_link = f"/rhythm?ticket={ticket_id}" if ticket_id else "/rhythm"
        elif dom == "finance":
            deep_link = f"/money?ticket={ticket_id}" if ticket_id else "/money"
        else:
            deep_link = f"/tick?ticket={ticket_id}" if ticket_id else "/tick"

    return {
        "target_domain": dom,
        "persona": persona,
        "target_clients": clients,
        "deep_link": deep_link,
    }


class InboxError(Exception):
    """收件箱业务错误基类。"""


class InboxNotFoundError(InboxError):
    """收件箱条目不存在。"""


class InboxBadRequestError(InboxError):
    """请求参数非法。"""


class InboxStateConflictError(InboxError):
    """状态机冲突。"""


# ============================================================================
# Monotonic sync_seq & Helpers
# ============================================================================


def next_sync_seq(db: Session) -> int:
    """获取严格单调递增的 sync_seq（PostgreSQL 优先走 sequence，SQLite 走锁内 MAX+1）。"""
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        try:
            val = db.execute(text("SELECT nextval('user_inbox_sync_seq')")).scalar()
            if val is not None:
                return int(val)
        except Exception as exc:
            logger.debug("[inbox] pg sequence fallback to MAX+1: %s", exc)

    with _SEQ_LOCK:
        cur_max = db.query(func.coalesce(func.max(UserInboxItem.sync_seq), 0)).scalar() or 0
        return int(cur_max) + 1


def _to_item_response(item: UserInboxItem) -> InboxItemResponse:
    src = item.source_domain or "system"
    tdom = getattr(item, "target_domain", None) or (
        src if src in ("health", "rhythm", "finance") else "general"
    )
    pers = getattr(item, "persona", None) or {
        "health": "health_coach",
        "rhythm": "rhythm_planner",
        "finance": "finance_secretary",
    }.get(tdom, "chief_steward")
    tclients = getattr(item, "target_clients", None)
    return InboxItemResponse(
        id=item.id,
        user_id=item.user_id or 1,
        sync_seq=int(item.sync_seq or 0),
        source_domain=src,
        target_domain=tdom,
        persona=pers,
        target_clients=list(tclients) if isinstance(tclients, list) else [],
        item_kind=item.item_kind or "notice",
        topic=item.topic or "",
        dedup_key=item.dedup_key or "",
        ref_type=item.ref_type or "",
        ref_id=item.ref_id,
        reminder_id=item.reminder_id,
        ticket_id=item.ticket_id,
        title=item.title,
        body=item.body or "",
        priority=item.priority or "normal",
        status=item.status or STATUS_DELIVERED,
        is_read=bool(item.is_read),
        read_at=item.read_at,
        action_schema=dict(item.action_schema) if isinstance(item.action_schema, dict) else {},
        reply_text=item.reply_text,
        resolution_source=item.resolution_source or "",
        resolution_summary=item.resolution_summary or "",
        resolution_ref=dict(item.resolution_ref) if isinstance(item.resolution_ref, dict) else {},
        trigger_at=item.trigger_at,
        snooze_until=item.snooze_until,
        expires_at=item.expires_at,
        delivered_at=item.delivered_at,
        resolved_at=item.resolved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_event_response(ev: UserInboxEvent) -> InboxEventResponse:
    return InboxEventResponse(
        id=ev.id,
        inbox_item_id=ev.inbox_item_id,
        user_id=ev.user_id or 1,
        event=ev.event,
        actor_client=ev.actor_client or "system",
        device_id=ev.device_id or "",
        detail=dict(ev.detail) if isinstance(ev.detail, dict) else {},
        created_at=ev.created_at,
    )


def _add_inbox_event(
    db: Session,
    item: UserInboxItem,
    event: str,
    *,
    actor_client: str = "system",
    device_id: str = "",
    detail: Optional[Dict[str, Any]] = None,
) -> UserInboxEvent:
    ev = UserInboxEvent(
        inbox_item_id=item.id,
        user_id=item.user_id or 1,
        event=event,
        actor_client=actor_client or "system",
        device_id=device_id or "",
        detail=detail or {},
        created_at=datetime.now(),
    )
    db.add(ev)
    return ev


def _broadcast_upserted(
    db: Session,
    item: UserInboxItem,
    *,
    notify: bool = True,
    exclude_device_id: Optional[str] = None,
) -> None:
    hub = get_user_sync_hub()
    should_notify = False
    if notify and item.status in (STATUS_DELIVERED, STATUS_OPENED):
        if item.priority == "urgent":
            should_notify = True
        else:
            should_notify = not is_user_in_quiet_hours(db, item.user_id or 1)
    dto = _to_item_response(item).model_dump(mode="json")
    raw_clients = getattr(item, "target_clients", None)
    client_types = [str(c) for c in raw_clients if str(c).strip()] if isinstance(raw_clients, list) and raw_clients else None
    hub.fire_and_forget(
        hub.broadcast_inbox_upserted(
            user_id=item.user_id or 1,
            item=dto,
            should_notify=should_notify,
            exclude_device_id=exclude_device_id,
            client_types=client_types,
        )
    )


def _broadcast_resolved(
    item: UserInboxItem,
    *,
    exclude_device_id: Optional[str] = None,
) -> None:
    hub = get_user_sync_hub()
    payload = {
        "inbox_item_id": item.id,
        "reminder_id": item.reminder_id,
        "ticket_id": item.ticket_id,
        "ref_type": item.ref_type or "",
        "ref_id": item.ref_id,
        "status": item.status,
        "sync_seq": int(item.sync_seq or 0),
        "resolution_source": item.resolution_source or "",
        "resolution_summary": item.resolution_summary or "",
        "reply_text": item.reply_text,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }
    hub.fire_and_forget(
        hub.broadcast_inbox_resolved(
            user_id=item.user_id or 1,
            payload=payload,
            exclude_device_id=exclude_device_id,
        )
    )


def _compute_snooze_until(option: Optional[str], hours: Optional[int], now: datetime) -> datetime:
    if option:
        opt = option.strip().lower()
        if opt == "15m":
            return now + timedelta(minutes=15)
        if opt == "1h":
            return now + timedelta(hours=1)
        if opt == "tonight":
            tonight = now.replace(hour=20, minute=0, second=0, microsecond=0)
            return tonight if tonight > now else now + timedelta(hours=1)
        if opt == "tomorrow":
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        if opt == "24h":
            return now + timedelta(hours=24)
        raise InboxBadRequestError(f"unknown snooze option: {option!r}")
    hrs = hours if (hours is not None and hours > 0) else 24
    return now + timedelta(hours=hrs)


# ============================================================================
# Creation & Projection (Producers -> UserInboxItem)
# ============================================================================


def infer_auto_resolve_signals(
    *,
    source_domain: str,
    topic: str = "",
    title: str = "",
    body: str = "",
    action_schema: Optional[Dict[str, Any]] = None,
    target_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """为未显式声明 auto_resolve_signals 的条目推导默认业务域消解规则。"""
    schema = action_schema or {}
    existing = schema.get("auto_resolve_signals")
    if isinstance(existing, list) and existing:
        return existing

    day_str = target_date or date.today().isoformat()
    combined = f"{topic} {title} {body}".lower()
    signals: List[Dict[str, Any]] = []

    meal_raw = str(schema.get("meal_type") or "").strip().lower()
    meal_map = {
        "早餐": "breakfast",
        "早饭": "breakfast",
        "breakfast": "breakfast",
        "午餐": "lunch",
        "午饭": "lunch",
        "中午": "lunch",
        "lunch": "lunch",
        "canteen": "lunch",
        "晚餐": "dinner",
        "晚饭": "dinner",
        "dinner": "dinner",
        "加餐": "snack",
        "零食": "snack",
        "snack": "snack",
    }
    inferred_meal = meal_map.get(meal_raw)
    if not inferred_meal:
        for kw, canonical in meal_map.items():
            if kw in combined:
                inferred_meal = canonical
                break

    if inferred_meal and any(
        k in combined for k in ("餐", "饭", "饮食", "diet", "meal", "canteen", "吃", "零食")
    ):
        signals.append(
            {
                "domain": "health",
                "event": "diet.logged",
                "meal_type": inferred_meal,
                "date": day_str,
            }
        )

    if any(k in combined for k in ("weight", "体重", "称重", "上秤")) and (
        source_domain in ("sailtick", "rhythm", "health")
    ):
        signals.append({"domain": "health", "event": "weight.logged", "date": day_str})

    if any(k in combined for k in ("rhythm.exercise", "exercise_checkin", "运动打卡")):
        signals.append({"domain": "health", "event": "exercise.logged", "date": day_str})

    if any(k in combined for k in ("rhythm.medication", "medication", "服药", "吃药")):
        signals.append({"domain": "health", "event": "medication.logged", "date": day_str})

    if schema.get("affair_id"):
        signals.append(
            {
                "domain": "rhythm",
                "event": "affair.done",
                "affair_id": int(schema["affair_id"]),
            }
        )

    return signals


def create_or_upsert_inbox_item_impl(
    db: Session,
    user_id: int,
    req: InboxCreateRequest,
    *,
    actor_client: str = "system",
    commit: bool = True,
) -> UserInboxItem:
    """创建或按 dedup_key / (ref_type, ref_id) 幂等合并收件箱条目。"""
    if req.priority not in VALID_PRIORITIES:
        raise InboxBadRequestError(f"invalid priority: {req.priority!r}")

    now = datetime.now()
    schema = dict(req.action_schema or {})
    inferred_signals = infer_auto_resolve_signals(
        source_domain=req.source_domain,
        topic=req.topic,
        title=req.title,
        body=req.body,
        action_schema=schema,
    )
    if inferred_signals and not schema.get("auto_resolve_signals"):
        schema["auto_resolve_signals"] = inferred_signals

    existing: Optional[UserInboxItem] = None
    if req.ref_type and req.ref_id is not None:
        existing = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.ref_type == req.ref_type,
                UserInboxItem.ref_id == req.ref_id,
            )
            .first()
        )
    if existing is None and req.dedup_key:
        existing = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.dedup_key == req.dedup_key,
                UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
            )
            .order_by(UserInboxItem.id.desc())
            .first()
        )

    routing = resolve_domain_routing(
        domain=req.target_domain,
        source_domain=req.source_domain,
        topic=req.topic,
        title=req.title,
        body=req.body,
        item_kind=req.item_kind,
        ticket_id=req.ticket_id,
        explicit_persona=req.persona,
        explicit_clients=req.target_clients or None,
        explicit_deep_link=str(schema.get("deep_link") or ""),
    )
    resolved_target_domain = routing["target_domain"]
    resolved_persona = routing["persona"]
    resolved_target_clients = routing["target_clients"]
    if not schema.get("deep_link"):
        schema["deep_link"] = routing["deep_link"]
    schema.setdefault("target_domain", resolved_target_domain)
    schema.setdefault("persona", resolved_persona)

    seq = next_sync_seq(db)
    if existing is not None:
        existing.title = req.title
        existing.body = req.body or existing.body or ""
        existing.priority = req.priority or existing.priority
        existing.topic = req.topic or existing.topic or ""
        existing.target_domain = resolved_target_domain
        existing.persona = resolved_persona
        existing.target_clients = resolved_target_clients
        if req.reminder_id is not None:
            existing.reminder_id = req.reminder_id
        if req.ticket_id is not None:
            existing.ticket_id = req.ticket_id
        if schema:
            merged_schema = dict(existing.action_schema or {})
            merged_schema.update(schema)
            existing.action_schema = merged_schema
        if req.status in ACTIVE_STATUSES and existing.status in ACTIVE_STATUSES:
            existing.status = req.status
        existing.sync_seq = seq
        existing.updated_at = now
        if req.status == STATUS_DELIVERED and existing.delivered_at is None:
            existing.delivered_at = now
        item = existing
    else:
        item = UserInboxItem(
            user_id=user_id,
            sync_seq=seq,
            source_domain=req.source_domain or "system",
            target_domain=resolved_target_domain,
            persona=resolved_persona,
            target_clients=resolved_target_clients,
            item_kind=req.item_kind or "notice",
            topic=req.topic or "",
            dedup_key=req.dedup_key or "",
            ref_type=req.ref_type or "",
            ref_id=req.ref_id,
            reminder_id=req.reminder_id,
            ticket_id=req.ticket_id,
            title=req.title,
            body=req.body or "",
            priority=req.priority or "normal",
            status=req.status or STATUS_DELIVERED,
            is_read=False,
            action_schema=schema,
            trigger_at=req.trigger_at or now,
            expires_at=req.expires_at,
            delivered_at=now if (req.status or STATUS_DELIVERED) == STATUS_DELIVERED else None,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.flush()
        _add_inbox_event(
            db,
            item,
            "created",
            actor_client=actor_client,
            detail={"source_domain": item.source_domain, "item_kind": item.item_kind},
        )

    if commit:
        db.commit()
        db.refresh(item)
        _broadcast_upserted(db, item, notify=req.notify)
    return item


def project_ticket_to_inbox(
    db: Session,
    ticket: SailTickTicket,
    *,
    reminder_id: Optional[int] = None,
    notify: bool = True,
) -> Optional[UserInboxItem]:
    """将 SailTickTicket 投影到统一 UserInboxItem，并回填 ticket.inbox_item_id。"""
    try:
        user_id = getattr(ticket, "user_id", None) or 1
        meta = dict(ticket.meta) if isinstance(ticket.meta, dict) else {}
        kind_map = {
            "question": "question",
            "task": "action_reminder",
            "approval": "approval",
            "info": "notice",
        }
        item_kind = kind_map.get(ticket.type or "question", "question")
        topic = (getattr(ticket, "topic", None) or "").strip()
        day_str = (ticket.created_at.date() if ticket.created_at else date.today()).isoformat()
        dedup_key = f"sailtick:{topic}:{day_str}" if topic else f"tick_ticket:{ticket.id}"

        routing = resolve_domain_routing(
            domain=getattr(ticket, "domain", None) or str(meta.get("domain") or ""),
            source_domain="sailtick",
            topic=topic,
            title=ticket.title or "",
            body=ticket.body or "",
            item_kind=item_kind,
            ticket_type=ticket.type or "question",
            ticket_id=ticket.id,
            explicit_persona=getattr(ticket, "persona", None) or str(meta.get("persona") or ""),
            explicit_clients=getattr(ticket, "target_clients", None) if isinstance(getattr(ticket, "target_clients", None), list) else None,
            explicit_deep_link=getattr(ticket, "deep_link", None) or "",
        )

        action_schema: Dict[str, Any] = {
            "quick_replies": meta.get("quick_replies", []) if isinstance(meta.get("quick_replies"), list) else [],
            "allow_text_reply": item_kind in ("question", "action_reminder", "approval"),
            "allow_image_reply": item_kind in ("question", "action_reminder") and routing["target_domain"] in ("health", "finance"),
            "deep_link": routing["deep_link"],
            "target_domain": routing["target_domain"],
            "persona": routing["persona"],
            "ticket_id": ticket.id,
            "ticket_type": ticket.type or "question",
            "topic": topic,
        }
        if isinstance(meta.get("auto_resolve_signals"), list):
            action_schema["auto_resolve_signals"] = meta["auto_resolve_signals"]
        if meta.get("target_profile_key"):
            action_schema["target_profile_key"] = meta["target_profile_key"]

        status = STATUS_DELIVERED
        if ticket.status == "snoozed":
            status = STATUS_SNOOZED
        elif ticket.status == "replied":
            status = STATUS_ANSWERED
        elif ticket.status == "resolved":
            status = STATUS_RESOLVED
        elif ticket.status == "expired":
            status = STATUS_EXPIRED

        item = create_or_upsert_inbox_item_impl(
            db,
            user_id=user_id,
            req=InboxCreateRequest(
                source_domain="sailtick",
                target_domain=routing["target_domain"],
                persona=routing["persona"],
                target_clients=routing["target_clients"],
                item_kind=item_kind,
                topic=topic,
                dedup_key=dedup_key,
                ref_type="tick_ticket",
                ref_id=ticket.id,
                reminder_id=reminder_id,
                ticket_id=ticket.id,
                title=ticket.title,
                body=ticket.body or "",
                priority=ticket.priority or "normal",
                status=status,
                action_schema=action_schema,
                trigger_at=ticket.created_at or datetime.now(),
                expires_at=ticket.expected_reply_by,
                notify=notify,
            ),
            actor_client="sailtick",
            commit=False,
        )
        if ticket.inbox_item_id != item.id:
            ticket.inbox_item_id = item.id
        db.commit()
        db.refresh(item)
        _broadcast_upserted(db, item, notify=notify)
        return item
    except Exception as exc:
        logger.warning("[inbox] project_ticket_to_inbox failed (non-fatal): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None


def project_daily_report_to_inbox(
    db: Session,
    report: SailTickDailyReport,
    *,
    reminder_id: Optional[int] = None,
    notify: bool = True,
) -> Optional[UserInboxItem]:
    """将 SailTickDailyReport 投影到统一 UserInboxItem。"""
    try:
        dedup_key = f"sailtick:daily_report:{report.report_date}"
        item = create_or_upsert_inbox_item_impl(
            db,
            user_id=1,
            req=InboxCreateRequest(
                source_domain="sailtick",
                target_domain="general",
                persona="chief_steward",
                target_clients=["android", "web"],
                item_kind="report",
                topic="daily_report",
                dedup_key=dedup_key,
                ref_type="tick_daily_report",
                ref_id=report.id,
                reminder_id=reminder_id,
                title=report.title,
                body=(report.summary or report.body_markdown or "")[:400],
                priority="normal",
                status=STATUS_DELIVERED,
                action_schema={
                    "deep_link": f"/inbox/report/{report.report_date}",
                    "target_domain": "general",
                    "persona": "chief_steward",
                    "report_date": report.report_date,
                    "report_id": report.id,
                    "kind": "daily_report",
                },
                notify=notify,
            ),
            actor_client="sailtick",
            commit=True,
        )
        return item
    except Exception as exc:
        logger.warning("[inbox] project_daily_report_to_inbox failed (non-fatal): %s", exc)
        return None


def project_reminder_to_inbox(
    db: Session,
    rem: Reminder,
    *,
    notify: bool = False,
) -> Optional[UserInboxItem]:
    """将普通 Reminder（非 ticket 镜像或已关联）投影到统一 UserInboxItem。"""
    try:
        payload = dict(rem.payload) if isinstance(rem.payload, dict) else {}
        ticket_id = payload.get("ticket_id")
        if ticket_id:
            # ticket 镜像提醒：优先挂接到已有 ticket 对应的 InboxItem，避免双份显示
            existing = (
                db.query(UserInboxItem)
                .filter(UserInboxItem.ticket_id == int(ticket_id))
                .order_by(UserInboxItem.id.desc())
                .first()
            )
            if existing is not None:
                existing.reminder_id = rem.id
                rem.inbox_item_id = existing.id
                db.commit()
                return existing

        user_id = getattr(rem, "user_id", None) or 1
        src = (rem.source or "manual").lower()
        rem_type = (rem.type or "").lower()
        if src.startswith("rhythm") or rem_type.startswith("rhythm."):
            source_domain = "rhythm"
        elif src == "agent" or rem_type.startswith("tick.") or rem_type.startswith("agent."):
            source_domain = "sailtick"
        elif rem_type.startswith("health.") or rem_type.startswith("diet."):
            source_domain = "health"
        else:
            source_domain = "system"

        state_map = {
            "PENDING": STATUS_PENDING,
            "DELIVERED": STATUS_DELIVERED,
            "SNOOZED": STATUS_SNOOZED,
            "OPENED": STATUS_OPENED,
            "RESOLVED": STATUS_RESOLVED,
            "IGNORED": STATUS_DISMISSED,
            "EXPIRED": STATUS_EXPIRED,
            "CANCELED": STATUS_CANCELED,
            "ARCHIVED": STATUS_EXPIRED,
        }
        status = state_map.get(rem.state or "PENDING", STATUS_PENDING)
        day_str = (rem.trigger_at.date() if getattr(rem, "trigger_at", None) else (rem.trigger_time.date() if rem.trigger_time else date.today())).isoformat()

        meal_tag = str(payload.get("meal_type") or "").strip()
        if rem_type == "rhythm.meal" and meal_tag:
            dedup_key = f"rhythm:meal:{meal_tag}:{day_str}"
            topic = f"diet_{meal_tag}"
        elif rem_type == "rhythm.weight":
            dedup_key = f"rhythm:weight:{day_str}"
            topic = "weight_checkin"
        else:
            dedup_key = f"reminder:{rem.id}"
            topic = rem_type

        rem_routing = resolve_domain_routing(
            domain=str(payload.get("domain") or ""),
            source_domain=source_domain,
            topic=topic,
            title=rem.title or "",
            body=rem.body or "",
            item_kind="report" if rem_type == "tick.daily_report" else "action_reminder",
            report_date=str(payload.get("report_date") or ""),
            explicit_deep_link=str(payload.get("deep_link") or ""),
        )
        action_schema: Dict[str, Any] = {
            **payload,
            "reminder_type": rem.type,
            "target_domain": rem_routing["target_domain"],
            "persona": rem_routing["persona"],
            "deep_link": rem_routing["deep_link"],
        }

        item = create_or_upsert_inbox_item_impl(
            db,
            user_id=user_id,
            req=InboxCreateRequest(
                source_domain=source_domain,
                target_domain=rem_routing["target_domain"],
                persona=rem_routing["persona"],
                target_clients=rem_routing["target_clients"],
                item_kind="report" if rem_type == "tick.daily_report" else "action_reminder",
                topic=topic,
                dedup_key=dedup_key,
                ref_type="reminder",
                ref_id=rem.id,
                reminder_id=rem.id,
                ticket_id=int(ticket_id) if ticket_id else None,
                title=rem.title,
                body=rem.body or "",
                priority=rem.priority or "normal",
                status=status,
                action_schema=action_schema,
                trigger_at=rem.trigger_time,
                expires_at=(
                    rem.trigger_time + timedelta(minutes=rem.expire_after_minutes or 240)
                    if rem.trigger_time
                    else None
                ),
                notify=notify,
            ),
            actor_client="system",
            commit=False,
        )
        if rem.inbox_item_id != item.id:
            rem.inbox_item_id = item.id
        db.commit()
        db.refresh(item)
        if notify or status == STATUS_DELIVERED:
            _broadcast_upserted(db, item, notify=notify)
        return item
    except Exception as exc:
        logger.warning("[inbox] project_reminder_to_inbox failed (non-fatal): %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None


# ============================================================================
# Query & Cursor Sync
# ============================================================================


def get_inbox_cursor_stats(db: Session, user_id: int) -> Dict[str, int]:
    """返回某用户的 latest_sync_seq、active_count、unread_count（供 bootstrap 与 WS 握手）。"""
    latest_seq = (
        db.query(func.coalesce(func.max(UserInboxItem.sync_seq), 0))
        .filter(UserInboxItem.user_id == user_id)
        .scalar()
        or 0
    )
    active_count = (
        db.query(UserInboxItem)
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
        )
        .count()
    )
    unread_count = (
        db.query(UserInboxItem)
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
            UserInboxItem.is_read == False,  # noqa: E712
        )
        .count()
    )
    return {
        "latest_sync_seq": int(latest_seq),
        "active_count": int(active_count),
        "unread_count": int(unread_count),
    }


def list_inbox_impl(
    db: Session,
    user_id: int,
    *,
    tab: str = "active",
    source_domain: Optional[str] = None,
    item_kind: Optional[str] = None,
    limit: int = 100,
) -> List[InboxItemResponse]:
    q = db.query(UserInboxItem).filter(UserInboxItem.user_id == user_id)
    if tab == "active":
        q = q.filter(UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)))
    elif tab == "history":
        q = q.filter(UserInboxItem.status.in_(sorted(TERMINAL_STATUSES)))
    if source_domain:
        q = q.filter(
            or_(
                UserInboxItem.target_domain == source_domain,
                UserInboxItem.source_domain == source_domain,
            )
        )
    if item_kind:
        q = q.filter(UserInboxItem.item_kind == item_kind)

    rows = (
        q.order_by(UserInboxItem.updated_at.desc(), UserInboxItem.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [_to_item_response(r) for r in rows]


def sync_inbox_impl(
    db: Session,
    user_id: int,
    *,
    since_seq: int = 0,
    limit: int = 200,
    device_id: str = "",
) -> InboxSyncResponse:
    """游标增量对账：返回 since_seq 之后的全部变更（含终态！）+ 当前全量 active_ids。"""
    stats = get_inbox_cursor_stats(db, user_id)
    active_id_rows = (
        db.query(UserInboxItem.id)
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
        )
        .all()
    )
    active_ids = [int(r[0]) for r in active_id_rows]

    if since_seq <= 0:
        active_items = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
            )
            .order_by(UserInboxItem.sync_seq.asc())
            .all()
        )
        recent_terminal = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.status.in_(sorted(TERMINAL_STATUSES)),
            )
            .order_by(UserInboxItem.sync_seq.desc())
            .limit(50)
            .all()
        )
        # 合并按 sync_seq 升序返回
        merged = sorted(active_items + recent_terminal, key=lambda x: (x.sync_seq or 0, x.id))
        changes = [_to_item_response(r) for r in merged]
    else:
        rows = (
            db.query(UserInboxItem)
            .filter(
                UserInboxItem.user_id == user_id,
                UserInboxItem.sync_seq > since_seq,
            )
            .order_by(UserInboxItem.sync_seq.asc(), UserInboxItem.id.asc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        changes = [_to_item_response(r) for r in rows]

    # 更新设备同步游标（非致命）
    if device_id:
        try:
            dev = db.query(Device).filter(Device.device_id == device_id).first()
            if dev is not None:
                dev.last_sync_seq = stats["latest_sync_seq"]
                dev.last_seen_at = datetime.now()
                db.commit()
        except Exception:
            pass

    return InboxSyncResponse(
        latest_seq=stats["latest_sync_seq"],
        unread_count=stats["unread_count"],
        active_count=stats["active_count"],
        active_ids=active_ids,
        changes=changes,
    )


def get_inbox_summary_impl(db: Session, user_id: int) -> InboxSummaryResponse:
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    active_rows = (
        db.query(UserInboxItem)
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
        )
        .all()
    )
    by_domain: Dict[str, int] = {}
    unread = 0
    for row in active_rows:
        dom = row.source_domain or "system"
        by_domain[dom] = by_domain.get(dom, 0) + 1
        if not row.is_read:
            unread += 1

    today_terminal = (
        db.query(UserInboxItem.status, func.count(UserInboxItem.id))
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(TERMINAL_STATUSES)),
            UserInboxItem.updated_at >= day_start,
            UserInboxItem.updated_at < day_end,
        )
        .group_by(UserInboxItem.status)
        .all()
    )
    counts = {st: int(cnt) for st, cnt in today_terminal}

    return InboxSummaryResponse(
        date=day_start.strftime("%Y-%m-%d"),
        active=len(active_rows),
        unread=unread,
        answered=counts.get(STATUS_ANSWERED, 0),
        resolved=counts.get(STATUS_RESOLVED, 0),
        dismissed=counts.get(STATUS_DISMISSED, 0),
        expired=counts.get(STATUS_EXPIRED, 0),
        by_domain=by_domain,
    )


def list_inbox_events_impl(
    db: Session, user_id: int, item_id: int
) -> List[InboxEventResponse]:
    item = _get_item_or_404(db, user_id, item_id)
    rows = (
        db.query(UserInboxEvent)
        .filter(UserInboxEvent.inbox_item_id == item.id)
        .order_by(UserInboxEvent.id.asc())
        .all()
    )
    return [_to_event_response(r) for r in rows]


# ============================================================================
# Mutations (Bidirectional sync to SailTickTicket & Reminder + WS broadcast)
# ============================================================================


def _get_item_or_404(db: Session, user_id: int, item_id: int) -> UserInboxItem:
    item = (
        db.query(UserInboxItem)
        .filter(UserInboxItem.id == item_id, UserInboxItem.user_id == user_id)
        .first()
    )
    if item is None:
        raise InboxNotFoundError(f"inbox item {item_id} not found")
    return item


def _close_linked_source_entities(
    db: Session,
    item: UserInboxItem,
    *,
    action: str,  # reply | resolve | dismiss | snooze | expire | cancel
    reply_text: Optional[str] = None,
    resolution_summary: str = "",
    snooze_until: Optional[datetime] = None,
    sync_ticket: bool = True,
    sync_reminder: bool = True,
) -> None:
    """在当前事务内同步更新关联的 SailTickTicket 与 Reminder（避免循环调用）。"""
    now = datetime.now()

    # 1. 同步 SailTickTicket
    ticket_id = item.ticket_id or (item.ref_id if item.ref_type == "tick_ticket" else None)
    if sync_ticket and ticket_id:
        ticket = db.get(SailTickTicket, int(ticket_id))
        if ticket is not None and ticket.status not in ("resolved", "expired"):
            if action == "reply":
                ticket.reply = reply_text or resolution_summary
                ticket.replied_at = now
                ticket.status = "replied"
                ticket.updated_at = now
            elif action in ("resolve", "dismiss"):
                ticket.status = "resolved"
                ticket.resolution = resolution_summary or action
                ticket.resolved_at = now
                ticket.updated_at = now
            elif action == "snooze":
                ticket.status = "snoozed"
                if snooze_until is not None:
                    ticket.expected_reply_by = snooze_until
                ticket.updated_at = now
            elif action == "expire":
                ticket.status = "expired"
                ticket.updated_at = now

    if not sync_reminder:
        return

    # 2. 同步 Reminder（按 reminder_id 或 ticket_id 匹配所有未终态影子提醒）
    rem_ids_done = set()
    candidates: List[Reminder] = []
    if item.reminder_id:
        rem = db.get(Reminder, int(item.reminder_id))
        if rem is not None:
            candidates.append(rem)
            rem_ids_done.add(rem.id)
    if item.ref_type == "reminder" and item.ref_id and int(item.ref_id) not in rem_ids_done:
        rem = db.get(Reminder, int(item.ref_id))
        if rem is not None:
            candidates.append(rem)
            rem_ids_done.add(rem.id)
    if ticket_id:
        active_agent_rems = (
            db.query(Reminder)
            .filter(
                Reminder.source == "agent",
                Reminder.state.in_(["PENDING", "DELIVERED", "SNOOZED", "OPENED"]),
            )
            .all()
        )
        for rem in active_agent_rems:
            if rem.id not in rem_ids_done and isinstance(rem.payload, dict) and rem.payload.get("ticket_id") == int(ticket_id):
                candidates.append(rem)
                rem_ids_done.add(rem.id)

    for rem in candidates:
        if rem.state in ("RESOLVED", "IGNORED", "CANCELED", "ARCHIVED"):
            continue
        if action in ("reply", "resolve"):
            rem.state = "RESOLVED"
            db.add(ReminderEvent(reminder_id=rem.id, event="resolved", detail={"via": "user_inbox"}))
        elif action == "dismiss":
            rem.state = "IGNORED"
            db.add(ReminderEvent(reminder_id=rem.id, event="dismissed", detail={"via": "user_inbox"}))
        elif action == "snooze" and snooze_until is not None:
            rem.state = "SNOOZED"
            rem.next_trigger_time = snooze_until
            rem.snooze_count = (rem.snooze_count or 0) + 1
            db.add(
                ReminderEvent(
                    reminder_id=rem.id,
                    event="snoozed",
                    detail={"via": "user_inbox", "next_trigger_time": snooze_until.isoformat()},
                )
            )
        elif action == "cancel":
            rem.state = "CANCELED"
            db.add(ReminderEvent(reminder_id=rem.id, event="canceled", detail={"via": "user_inbox"}))


def mark_inbox_read_impl(
    db: Session,
    user_id: int,
    item_id: int,
    *,
    actor_client: str = "web",
    device_id: str = "",
) -> InboxItemResponse:
    item = _get_item_or_404(db, user_id, item_id)
    if not item.is_read:
        now = datetime.now()
        item.is_read = True
        item.read_at = now
        item.sync_seq = next_sync_seq(db)
        item.updated_at = now
        _add_inbox_event(db, item, "read", actor_client=actor_client, device_id=device_id)
        db.commit()
        db.refresh(item)
        _broadcast_upserted(db, item, notify=False, exclude_device_id=device_id or None)
    return _to_item_response(item)


def mark_all_inbox_read_impl(
    db: Session,
    user_id: int,
    *,
    actor_client: str = "web",
    device_id: str = "",
) -> int:
    rows = (
        db.query(UserInboxItem)
        .filter(
            UserInboxItem.user_id == user_id,
            UserInboxItem.status.in_(sorted(ACTIVE_STATUSES)),
            UserInboxItem.is_read == False,  # noqa: E712
        )
        .all()
    )
    if not rows:
        return 0
    now = datetime.now()
    for item in rows:
        item.is_read = True
        item.read_at = now
        item.sync_seq = next_sync_seq(db)
        item.updated_at = now
        _add_inbox_event(db, item, "read", actor_client=actor_client, device_id=device_id)
    db.commit()
    for item in rows:
        _broadcast_upserted(db, item, notify=False, exclude_device_id=device_id or None)
    return len(rows)


def reply_inbox_item_impl(
    db: Session,
    user_id: int,
    item_id: int,
    reply: str,
    *,
    source: Optional[str] = None,
    actor_client: str = "web",
    device_id: str = "",
) -> InboxItemResponse:
    text_reply = (reply or "").strip()
    if not text_reply:
        raise InboxBadRequestError("reply cannot be empty")
    item = _get_item_or_404(db, user_id, item_id)
    if item.status in TERMINAL_STATUSES:
        return _to_item_response(item)

    now = datetime.now()
    item.status = STATUS_ANSWERED
    item.is_read = True
    item.read_at = item.read_at or now
    item.reply_text = text_reply
    item.resolution_source = source or f"{actor_client}:inbox"
    item.resolution_summary = f"已回复：{text_reply[:200]}"
    item.resolved_at = now
    item.sync_seq = next_sync_seq(db)
    item.updated_at = now
    _add_inbox_event(
        db,
        item,
        "answered",
        actor_client=actor_client,
        device_id=device_id,
        detail={"reply": text_reply[:300], "source": item.resolution_source},
    )
    _close_linked_source_entities(
        db,
        item,
        action="reply",
        reply_text=text_reply,
        resolution_summary=item.resolution_summary,
    )
    db.commit()
    db.refresh(item)
    _broadcast_resolved(item)
    return _to_item_response(item)


def resolve_inbox_item_impl(
    db: Session,
    user_id: int,
    item_id: int,
    *,
    resolution_source: Optional[str] = None,
    resolution_summary: str = "",
    resolution_ref: Optional[Dict[str, Any]] = None,
    actor_client: str = "web",
    device_id: str = "",
) -> InboxItemResponse:
    item = _get_item_or_404(db, user_id, item_id)
    if item.status in TERMINAL_STATUSES:
        return _to_item_response(item)

    now = datetime.now()
    item.status = STATUS_RESOLVED
    item.is_read = True
    item.read_at = item.read_at or now
    item.resolution_source = resolution_source or f"{actor_client}:inbox"
    item.resolution_summary = resolution_summary or "已处理"
    if resolution_ref:
        item.resolution_ref = dict(resolution_ref)
    item.resolved_at = now
    item.sync_seq = next_sync_seq(db)
    item.updated_at = now
    _add_inbox_event(
        db,
        item,
        "resolved",
        actor_client=actor_client,
        device_id=device_id,
        detail={"source": item.resolution_source, "summary": item.resolution_summary},
    )
    _close_linked_source_entities(
        db,
        item,
        action="resolve",
        resolution_summary=item.resolution_summary,
    )
    db.commit()
    db.refresh(item)
    _broadcast_resolved(item)
    return _to_item_response(item)


def snooze_inbox_item_impl(
    db: Session,
    user_id: int,
    item_id: int,
    *,
    option: Optional[str] = None,
    hours: Optional[int] = None,
    actor_client: str = "web",
    device_id: str = "",
) -> InboxItemResponse:
    item = _get_item_or_404(db, user_id, item_id)
    if item.status in TERMINAL_STATUSES:
        return _to_item_response(item)

    now = datetime.now()
    until = _compute_snooze_until(option, hours, now)
    item.status = STATUS_SNOOZED
    item.snooze_until = until
    item.sync_seq = next_sync_seq(db)
    item.updated_at = now
    _add_inbox_event(
        db,
        item,
        "snoozed",
        actor_client=actor_client,
        device_id=device_id,
        detail={"option": option, "hours": hours, "snooze_until": until.isoformat()},
    )
    _close_linked_source_entities(db, item, action="snooze", snooze_until=until)
    db.commit()
    db.refresh(item)
    _broadcast_upserted(db, item, notify=False)
    return _to_item_response(item)


def dismiss_inbox_item_impl(
    db: Session,
    user_id: int,
    item_id: int,
    *,
    reason: str = "",
    actor_client: str = "web",
    device_id: str = "",
) -> InboxItemResponse:
    item = _get_item_or_404(db, user_id, item_id)
    if item.status in TERMINAL_STATUSES:
        return _to_item_response(item)

    now = datetime.now()
    item.status = STATUS_DISMISSED
    item.is_read = True
    item.read_at = item.read_at or now
    item.resolution_source = f"{actor_client}:dismiss"
    item.resolution_summary = reason or "已忽略"
    item.resolved_at = now
    item.sync_seq = next_sync_seq(db)
    item.updated_at = now
    _add_inbox_event(
        db,
        item,
        "dismissed",
        actor_client=actor_client,
        device_id=device_id,
        detail={"reason": reason},
    )
    _close_linked_source_entities(
        db, item, action="dismiss", resolution_summary=item.resolution_summary
    )
    db.commit()
    db.refresh(item)
    _broadcast_resolved(item)
    return _to_item_response(item)


# ============================================================================
# Hooks called by Legacy Ticket & Reminder Models (keeps old REST routes in sync)
# ============================================================================


def sync_inbox_on_ticket_changed(
    db: Session,
    ticket: SailTickTicket,
    *,
    action: str,  # replied | resolved | snoozed | expired
    actor_client: str = "web",
    resolution_source: Optional[str] = None,
) -> Optional[UserInboxItem]:
    """当旧 /api/v1/tick/tickets/{id}/* 被调用时，同步更新 UserInboxItem 并全端广播撤回。"""
    try:
        item = None
        if ticket.inbox_item_id:
            item = db.get(UserInboxItem, int(ticket.inbox_item_id))
        if item is None:
            item = (
                db.query(UserInboxItem)
                .filter(UserInboxItem.ticket_id == ticket.id)
                .order_by(UserInboxItem.id.desc())
                .first()
            )
        if item is None:
            return None

        now = datetime.now()
        if action == "replied":
            item.status = STATUS_ANSWERED
            item.is_read = True
            item.read_at = item.read_at or now
            item.reply_text = ticket.reply
            item.resolution_source = resolution_source or f"{actor_client}:tick"
            item.resolution_summary = f"已回复：{(ticket.reply or '')[:200]}"
            item.resolved_at = now
        elif action == "resolved":
            item.status = STATUS_RESOLVED
            item.is_read = True
            item.read_at = item.read_at or now
            item.resolution_source = resolution_source or f"{actor_client}:tick"
            item.resolution_summary = ticket.resolution or "已关闭"
            item.resolved_at = now
        elif action == "snoozed":
            item.status = STATUS_SNOOZED
            item.snooze_until = ticket.expected_reply_by
        elif action == "expired":
            item.status = STATUS_EXPIRED
            item.resolution_source = "system:expired"
            item.resolution_summary = "已超时过期"
            item.resolved_at = now

        item.sync_seq = next_sync_seq(db)
        item.updated_at = now
        _add_inbox_event(
            db,
            item,
            action,
            actor_client=actor_client,
            detail={"ticket_id": ticket.id, "resolution_source": item.resolution_source},
        )
        # 仅同步关联 Reminder（ticket 状态已由调用方更新，禁止覆盖）
        if action in ("replied", "resolved", "snoozed", "expired"):
            rem_action = (
                "resolve"
                if action in ("replied", "resolved")
                else ("snooze" if action == "snoozed" else "cancel")
            )
            _close_linked_source_entities(
                db,
                item,
                action=rem_action,
                snooze_until=item.snooze_until,
                resolution_summary=item.resolution_summary,
                sync_ticket=False,
                sync_reminder=True,
            )
        db.commit()
        db.refresh(item)
        if item.status in TERMINAL_STATUSES:
            _broadcast_resolved(item)
        else:
            _broadcast_upserted(db, item, notify=False)
        return item
    except Exception as exc:
        logger.warning("[inbox] sync_inbox_on_ticket_changed failed (non-fatal): %s", exc)
        return None


def sync_inbox_on_reminder_changed(
    db: Session,
    rem: Reminder,
    *,
    action: str,  # delivered | open | resolve | dismiss | snooze | cancel | expire
    actor_client: str = "android",
) -> Optional[UserInboxItem]:
    """当旧 /api/v1/reminder/* 或调度器状态变更时，双向同步 UserInboxItem 与关联 Ticket 并广播。"""
    try:
        item = None
        if getattr(rem, "inbox_item_id", None):
            item = db.get(UserInboxItem, int(rem.inbox_item_id))
        if item is None:
            item = (
                db.query(UserInboxItem)
                .filter(UserInboxItem.reminder_id == rem.id)
                .order_by(UserInboxItem.id.desc())
                .first()
            )
        if item is None:
            payload = rem.payload if isinstance(rem.payload, dict) else {}
            if payload.get("ticket_id"):
                item = (
                    db.query(UserInboxItem)
                    .filter(UserInboxItem.ticket_id == int(payload["ticket_id"]))
                    .order_by(UserInboxItem.id.desc())
                    .first()
                )
        if item is None:
            return project_reminder_to_inbox(db, rem, notify=(action == "delivered"))

        now = datetime.now()
        if action == "delivered":
            if item.status in TERMINAL_STATUSES:
                return item
            item.status = STATUS_DELIVERED
            item.delivered_at = now
        elif action == "open":
            if item.status not in TERMINAL_STATUSES:
                item.status = STATUS_OPENED
                item.is_read = True
                item.read_at = item.read_at or now
        elif action == "resolve":
            item.status = STATUS_RESOLVED
            item.is_read = True
            item.read_at = item.read_at or now
            item.resolution_source = f"{actor_client}:reminder"
            item.resolution_summary = "已在提醒中完成"
            item.resolved_at = now
        elif action == "dismiss":
            item.status = STATUS_DISMISSED
            item.is_read = True
            item.read_at = item.read_at or now
            item.resolution_source = f"{actor_client}:reminder_dismiss"
            item.resolution_summary = "已在提醒中忽略"
            item.resolved_at = now
        elif action == "snooze":
            item.status = STATUS_SNOOZED
            item.snooze_until = rem.next_trigger_time
        elif action == "cancel":
            item.status = STATUS_CANCELED
            item.resolution_source = "system:canceled"
            item.resolved_at = now
        elif action == "expire":
            item.status = STATUS_EXPIRED
            item.resolution_source = "system:expired"
            item.resolved_at = now

        item.sync_seq = next_sync_seq(db)
        item.updated_at = now
        _add_inbox_event(
            db, item, action, actor_client=actor_client, detail={"reminder_id": rem.id}
        )

        # 若该提醒对应教练票据，双向同步回写 SailTickTicket（避免 Web 仍残留待回提问）
        if item.ticket_id and action in ("resolve", "dismiss", "snooze"):
            _close_linked_source_entities(
                db,
                item,
                action=action,
                resolution_summary=item.resolution_summary,
                snooze_until=item.snooze_until,
            )

        db.commit()
        db.refresh(item)
        if item.status in TERMINAL_STATUSES:
            _broadcast_resolved(item)
        else:
            _broadcast_upserted(db, item, notify=(action == "delivered"))
        return item
    except Exception as exc:
        logger.warning("[inbox] sync_inbox_on_reminder_changed failed (non-fatal): %s", exc)
        return None
