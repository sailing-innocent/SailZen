# -*- coding: utf-8 -*-
# @file reminder.py
# @brief Reminder Model Layer (状态机 + 反馈中枢 + 查询/规则/设备)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒业务模型层（Android App M1 提醒闭环）

状态机（设计文档 §2.2）::

    PENDING ──投递──► DELIVERED ──dismiss──► IGNORED(终)
      ▲  ▲            │
      │  │            ├──snooze──► SNOOZED ──到点──► DELIVERED (snooze_count+1)
      │  │            │
      │  │            ├──open────► OPENED ──resolve──► RESOLVED(终)
      │  │            │              │
      │  │            │              └──30min 无完成──► DELIVERED (调度器回落)
      │  │            │
      │  │            └──超时无反馈──► EXPIRED ──按 retry_policy 重投/ARCHIVED(终)
      │  │
      │  └──EXPIRED 重投回 PENDING
      └──创建

反馈动作 → 状态转移表（feedback_reminder_impl 为闭环中枢）：

| 当前状态  | dismiss   | snooze            | open        | resolve   |
|-----------|-----------|-------------------|-------------|-----------|
| PENDING   | →IGNORED  | →SNOOZED          | 409(未投递) | →RESOLVED |
| DELIVERED | →IGNORED  | →SNOOZED          | →OPENED     | →RESOLVED |
| SNOOZED   | →IGNORED  | 重算 next_trigger | 409         | →RESOLVED |
| OPENED    | →IGNORED  | →SNOOZED          | 幂等返回    | →RESOLVED |
| EXPIRED   | →IGNORED  | →SNOOZED          | →OPENED     | →RESOLVED |
| 终态      | 幂等返回  | 409               | 409         | 409       |

注：EXPIRED 为调度器中间态（随后转 PENDING 或 ARCHIVED），用户的迟到反馈
按 DELIVERED 同等处理，避免竞态 409。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from sail_server.application.dto.reminder import (
    DeviceRegisterRequest,
    DeviceResponse,
    FeedbackRequest,
    ReminderCreateRequest,
    ReminderEventResponse,
    ReminderResponse,
    ReminderRuleCreateRequest,
    ReminderRuleResponse,
    ReminderRuleUpdateRequest,
    ReminderSummaryResponse,
)
from sail_server.infrastructure.orm.reminder import (
    Device,
    Reminder,
    ReminderEvent,
    ReminderRule,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

#: 非终态集合（可被反馈/调度驱动）
STATE_PENDING = "PENDING"
STATE_DELIVERED = "DELIVERED"
STATE_SNOOZED = "SNOOZED"
STATE_OPENED = "OPENED"
STATE_RESOLVED = "RESOLVED"  # 终态
STATE_IGNORED = "IGNORED"  # 终态
STATE_EXPIRED = "EXPIRED"
STATE_CANCELED = "CANCELED"  # 终态
STATE_ARCHIVED = "ARCHIVED"  # 终态

TERMINAL_STATES = {STATE_RESOLVED, STATE_IGNORED, STATE_CANCELED, STATE_ARCHIVED}
ACTIVE_STATES = {STATE_PENDING, STATE_DELIVERED, STATE_SNOOZED, STATE_OPENED}

PRIORITY_ORDER = ["low", "normal", "high", "urgent"]

#: snooze 升级阈值（设计文档 §2.3.2）
SNOOZED_PRIORITY_UP_AT = 3
SNOOZED_AGENT_REVIEW_AT = 5

VALID_ACTIONS = {"dismiss", "snooze", "open", "resolve"}
VALID_SNOOZE_OPTIONS = {"15m", "1h", "tonight", "tomorrow"}


# ============================================================================
# Exceptions（Controller 层映射为 HTTP 状态码）
# ============================================================================


class ReminderError(Exception):
    """提醒模块错误基类"""


class ReminderNotFoundError(ReminderError):
    """提醒不存在 → 404"""


class ReminderStateConflictError(ReminderError):
    """状态机不允许的操作 → 409"""


class ReminderBadRequestError(ReminderError):
    """请求参数错误 → 400"""


# ============================================================================
# Internal helpers
# ============================================================================


def _now() -> datetime:
    """服务器本地 naive 时间（全链路统一口径）"""
    return datetime.now()


def _add_event(
    db: Session,
    reminder_id: int,
    event: str,
    detail: Optional[Dict[str, Any]] = None,
    client_event_ts: Optional[datetime] = None,
) -> ReminderEvent:
    """追加不可变事件日志（不 commit，由调用方统一提交）"""
    ev = ReminderEvent(
        reminder_id=reminder_id,
        event=event,
        detail=detail or {},
        client_event_ts=client_event_ts,
    )
    db.add(ev)
    return ev


def _bump_priority(priority: str) -> str:
    """优先级升一级：low→normal→high→urgent（封顶）"""
    try:
        idx = PRIORITY_ORDER.index(priority)
    except ValueError:
        idx = PRIORITY_ORDER.index("normal")
    return PRIORITY_ORDER[min(idx + 1, len(PRIORITY_ORDER) - 1)]


def _compute_snooze_next_trigger(option: str, now: datetime) -> datetime:
    """snooze option → next_trigger_time（服务端本地时间换算表）

    - ``15m``      → now + 15 分钟
    - ``1h``       → now + 1 小时
    - ``tonight``  → 当日 20:00（已过则 now + 1 小时）
    - ``tomorrow`` → 次日 09:00
    """
    if option == "15m":
        return now + timedelta(minutes=15)
    if option == "1h":
        return now + timedelta(hours=1)
    if option == "tonight":
        tonight = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if tonight <= now:
            return now + timedelta(hours=1)
        return tonight
    if option == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)
    raise ReminderBadRequestError(
        f"unknown snooze option: {option!r}, expected one of {sorted(VALID_SNOOZE_OPTIONS)}"
    )


def read_from_reminder(r: Reminder) -> ReminderResponse:
    """Reminder ORM → ReminderResponse"""
    return ReminderResponse(
        id=r.id,
        type=r.type,
        title=r.title,
        body=r.body or "",
        priority=r.priority or "normal",
        source=r.source or "manual",
        state=r.state,
        trigger_time=r.trigger_time,
        expire_after_minutes=r.expire_after_minutes or 240,
        snooze_count=r.snooze_count or 0,
        retry_count=r.retry_count or 0,
        next_trigger_time=r.next_trigger_time,
        last_delivered_at=r.last_delivered_at,
        payload=r.payload or {},
        rule_id=r.rule_id,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def read_from_event(e: ReminderEvent) -> ReminderEventResponse:
    return ReminderEventResponse(
        id=e.id,
        reminder_id=e.reminder_id,
        event=e.event,
        detail=e.detail or {},
        client_event_ts=e.client_event_ts,
        created_at=e.created_at,
    )


def read_from_rule(rule: ReminderRule) -> ReminderRuleResponse:
    return ReminderRuleResponse(
        id=rule.id,
        type=rule.type,
        cron=rule.cron,
        enabled=bool(rule.enabled),
        priority=rule.priority or "normal",
        retry_policy=rule.retry_policy or {},
        quiet_hours=rule.quiet_hours,
        frequency_level=rule.frequency_level or 0,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def _get_reminder_or_404(db: Session, reminder_id: int) -> Reminder:
    r = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if r is None:
        raise ReminderNotFoundError(f"reminder {reminder_id} not found")
    return r


# ============================================================================
# Reminder CRUD & Feedback
# ============================================================================


def create_reminder_impl(db: Session, req: ReminderCreateRequest) -> ReminderResponse:
    """创建提醒：置 PENDING + created 事件。trigger_time 已过也允许（下轮即投递）"""
    if req.priority not in PRIORITY_ORDER:
        raise ReminderBadRequestError(f"invalid priority: {req.priority!r}")
    r = Reminder(
        type=req.type,
        title=req.title,
        body=req.body,
        priority=req.priority,
        source=req.source,
        state=STATE_PENDING,
        trigger_time=req.trigger_time,
        expire_after_minutes=req.expire_after_minutes,
        payload=req.payload or {},
        rule_id=req.rule_id,
    )
    db.add(r)
    db.flush()
    _add_event(db, r.id, "created", {"type": r.type, "source": r.source})
    db.commit()
    db.refresh(r)
    return read_from_reminder(r)


def get_reminder_impl(db: Session, reminder_id: int) -> ReminderResponse:
    return read_from_reminder(_get_reminder_or_404(db, reminder_id))


def feedback_reminder_impl(
    db: Session, reminder_id: int, req: FeedbackRequest
) -> ReminderResponse:
    """反馈中枢：dismiss / snooze / open / resolve 驱动状态机 + 事件日志"""
    action = req.action
    if action not in VALID_ACTIONS:
        raise ReminderBadRequestError(
            f"invalid action: {action!r}, expected one of {sorted(VALID_ACTIONS)}"
        )

    r = _get_reminder_or_404(db, reminder_id)
    state = r.state
    client_ts = req.client_event_ts

    # ---- 终态处理 ----
    if state in TERMINAL_STATES:
        if action == "dismiss":
            # 幂等返回当前状态，detail 标注 already_terminal
            _add_event(
                db,
                r.id,
                "dismissed",
                {"already_terminal": True, "state": state},
                client_ts,
            )
            db.commit()
            return read_from_reminder(r)
        raise ReminderStateConflictError(
            f"reminder {reminder_id} already in terminal state {state}, "
            f"action {action!r} rejected"
        )

    # ---- 非终态处理 ----
    if action == "dismiss":
        r.state = STATE_IGNORED
        _add_event(db, r.id, "dismissed", {"from_state": state}, client_ts)

    elif action == "resolve":
        r.state = STATE_RESOLVED
        _add_event(db, r.id, "resolved", {"from_state": state}, client_ts)

    elif action == "open":
        if state in (STATE_PENDING, STATE_SNOOZED):
            raise ReminderStateConflictError(
                f"reminder {reminder_id} in state {state}, not delivered yet"
            )
        if state == STATE_OPENED:
            # 幂等返回
            db.commit()
            return read_from_reminder(r)
        r.state = STATE_OPENED
        _add_event(db, r.id, "opened", {"from_state": state}, client_ts)

    elif action == "snooze":
        if not req.option:
            raise ReminderBadRequestError("snooze action requires option")
        now = _now()
        next_trigger = _compute_snooze_next_trigger(req.option, now)
        r.snooze_count = (r.snooze_count or 0) + 1
        r.state = STATE_SNOOZED
        r.next_trigger_time = next_trigger
        _add_event(
            db,
            r.id,
            "snoozed",
            {
                "option": req.option,
                "next_trigger_time": next_trigger.isoformat(),
                "snooze_count": r.snooze_count,
                "from_state": state,
            },
            client_ts,
        )
        # 升级策略（设计文档 §2.3.2）
        if r.snooze_count == SNOOZED_PRIORITY_UP_AT:
            new_priority = _bump_priority(r.priority)
            if new_priority != r.priority:
                r.priority = new_priority
                _add_event(
                    db,
                    r.id,
                    "escalated",
                    {
                        "level": "priority_up",
                        "priority": new_priority,
                        "snooze_count": r.snooze_count,
                    },
                    client_ts,
                )
        if r.snooze_count >= SNOOZED_AGENT_REVIEW_AT:
            # M1 仅落日志事件，Agent 联动属 M5
            _add_event(
                db,
                r.id,
                "escalated",
                {"level": "agent_review", "snooze_count": r.snooze_count},
                client_ts,
            )

    db.commit()
    db.refresh(r)
    return read_from_reminder(r)


def cancel_reminder_impl(db: Session, reminder_id: int) -> ReminderResponse:
    """撤销提醒：非终态 → CANCELED + canceled 事件；终态 → 409"""
    r = _get_reminder_or_404(db, reminder_id)
    if r.state in TERMINAL_STATES:
        raise ReminderStateConflictError(
            f"reminder {reminder_id} already in terminal state {r.state}"
        )
    r.state = STATE_CANCELED
    _add_event(db, r.id, "canceled", {})
    db.commit()
    db.refresh(r)
    return read_from_reminder(r)


def ack_reminder_impl(
    db: Session,
    reminder_id: int,
    device_id: str,
    client_event_ts: Optional[datetime] = None,
) -> bool:
    """投递确认：写 ack 事件（不改状态）"""
    _get_reminder_or_404(db, reminder_id)
    _add_event(db, reminder_id, "ack", {"device_id": device_id}, client_event_ts)
    db.commit()
    return True


# ============================================================================
# Query
# ============================================================================


def list_pending_impl(
    db: Session, since: Optional[datetime] = None
) -> List[ReminderResponse]:
    """补偿拉取：活跃状态提醒（since 增量同步用 updated_at 过滤）"""
    q = db.query(Reminder).filter(Reminder.state.in_(sorted(ACTIVE_STATES)))
    if since is not None:
        q = q.filter(Reminder.updated_at >= since)
    rows = q.order_by(Reminder.trigger_time).all()
    return [read_from_reminder(r) for r in rows]


def list_history_impl(
    db: Session, date: str, type: Optional[str] = None
) -> List[ReminderResponse]:
    """历史：按 trigger_time 当日过滤（含末态），可选类型筛选"""
    try:
        day = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ReminderBadRequestError(f"invalid date format: {date!r}, use YYYY-MM-DD")
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    q = db.query(Reminder).filter(
        Reminder.trigger_time >= day_start,
        Reminder.trigger_time < day_end,
    )
    if type:
        q = q.filter(Reminder.type == type)
    rows = q.order_by(Reminder.trigger_time).all()
    return [read_from_reminder(r) for r in rows]


def list_events_impl(db: Session, reminder_id: int) -> List[ReminderEventResponse]:
    """事件日志查询（验收核对用）"""
    _get_reminder_or_404(db, reminder_id)
    rows = (
        db.query(ReminderEvent)
        .filter(ReminderEvent.reminder_id == reminder_id)
        .order_by(ReminderEvent.id)
        .all()
    )
    return [read_from_event(e) for e in rows]


def get_summary_today_impl(db: Session) -> ReminderSummaryResponse:
    """当日小结：pending 取状态计数，其余取今日事件计数"""
    now = _now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # 待处理 = DELIVERED + OPENED + SNOOZED + 今日（含逾期）PENDING
    active_count = (
        db.query(Reminder)
        .filter(
            Reminder.state.in_([STATE_DELIVERED, STATE_SNOOZED, STATE_OPENED])
        )
        .count()
    )
    today_pending = (
        db.query(Reminder)
        .filter(
            Reminder.state == STATE_PENDING,
            Reminder.trigger_time < day_end,
        )
        .count()
    )

    def _event_count(event: str) -> int:
        return (
            db.query(ReminderEvent)
            .filter(
                ReminderEvent.event == event,
                ReminderEvent.created_at >= day_start,
                ReminderEvent.created_at < day_end,
            )
            .count()
        )

    return ReminderSummaryResponse(
        date=day_start.strftime("%Y-%m-%d"),
        pending=active_count + today_pending,
        resolved=_event_count("resolved"),
        ignored=_event_count("dismissed"),
        expired=_event_count("expired"),
        delivered_total=_event_count("delivered"),
    )


# ============================================================================
# Rules
# ============================================================================


def list_rules_impl(db: Session) -> List[ReminderRuleResponse]:
    rows = db.query(ReminderRule).order_by(ReminderRule.id).all()
    return [read_from_rule(r) for r in rows]


def create_rule_impl(
    db: Session, req: ReminderRuleCreateRequest
) -> ReminderRuleResponse:
    rule = ReminderRule(
        type=req.type,
        cron=req.cron,
        enabled=req.enabled,
        priority=req.priority,
        retry_policy=req.retry_policy or {},
        quiet_hours=req.quiet_hours,
        frequency_level=req.frequency_level,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return read_from_rule(rule)


def update_rule_impl(
    db: Session, rule_id: int, req: ReminderRuleUpdateRequest
) -> ReminderRuleResponse:
    rule = db.query(ReminderRule).filter(ReminderRule.id == rule_id).first()
    if rule is None:
        raise ReminderNotFoundError(f"reminder rule {rule_id} not found")
    data = req.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return read_from_rule(rule)


# ============================================================================
# Device
# ============================================================================


def register_device_impl(db: Session, req: DeviceRegisterRequest) -> DeviceResponse:
    """设备注册/心跳：按 device_id upsert，刷新 last_seen_at"""
    device = db.query(Device).filter(Device.device_id == req.device_id).first()
    if device is None:
        device = Device(device_id=req.device_id, platform="android")
        db.add(device)
    device.device_name = req.device_name
    device.app_version = req.app_version
    if req.push_token is not None:
        device.push_token = req.push_token
    device.last_seen_at = _now()
    db.commit()
    db.refresh(device)
    return DeviceResponse(
        id=device.id,
        device_id=device.device_id,
        device_name=device.device_name or "",
        platform=device.platform or "android",
        app_version=device.app_version or "",
        push_token=device.push_token,
        last_seen_at=device.last_seen_at,
    )
