# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm v2 Model Layer (极简项目/事务 + AI 自主排程时间线 + 占用 + 轻量打卡)
# @author sailing-innocent
# @date 2026-11-24
# @version 2.0
# ---------------------------------

"""
节奏（Rhythm v2）核心业务逻辑层

设计原则：
- Rhythm 退居为“结构化项目/任务事实库 + AI 可视化日程画布”。
- 不再包含确定性公式评分器、8 步硬排程器、精力画像/权重、DayTemplate 与 Policy。
- SailTick 智能体通过 HTTP API 自主编排日程（`sync_ai_timeline_impl`）、管理项目与里程碑、
  记录临时占用与打卡，前端只做极简可视化呈现与即时微调。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AITimelineSyncRequest,
    AITimelineSyncResponse,
    AffairAction,
    AffairCreateRequest,
    AffairDomain,
    AffairKind,
    AffairListResponse,
    AffairResponse,
    AffairSplitRequest,
    AffairState,
    AffairStateRequest,
    AffairUpdateRequest,
    BlockMoveRequest,
    BlockStatus,
    BlockStatusRequest,
    BlockType,
    CheckinLogResponse,
    CheckinRequest,
    CheckinResult,
    CheckinTodayItem,
    CheckinTodayResponse,
    ConfirmHintRequest,
    DayTimelineResponse,
    DomainMinutes,
    HealthCheckinRequest,
    HealthCheckinResponse,
    InfoCollectionType,
    LONGTERM_KINDS,
    OccupancyCreateRequest,
    OccupancyListResponse,
    OccupancyResponse,
    RhythmDashboardResponse,
    RhythmDayViewResponse,
    TERMINAL_STATES,
    TimeBlockCreateRequest,
    TimeBlockResponse,
    TimelineRangeDayItem,
    TimelineRangeResponse,
    VentureMilestoneRequest,
    VentureProgressResponse,
    is_longterm_kind,
    resolve_transition,
    validate_kind_meta,
)
from sailzen_orm.health import Exercise, HealthSignal, Weight
from sailzen_orm.life import Day
from sailzen_orm.rhythm import RhythmAffair, RhythmDisciplineLog, RhythmTimeBlock

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class RhythmError(Exception):
    """Rhythm 业务异常基类"""


class RhythmNotFoundError(RhythmError):
    """资源不存在 → HTTP 404"""


class RhythmStateConflictError(RhythmError):
    """状态/规则冲突 → HTTP 409"""


class RhythmBadRequestError(RhythmError):
    """参数非法 → HTTP 400"""


# ============================================================================
# Helpers
# ============================================================================

_DEFAULT_DOMAIN_BY_KIND: Dict[AffairKind, AffairDomain] = {
    AffairKind.BASE_RHYTHM: AffairDomain.LIFE,
    AffairKind.PRECEPT: AffairDomain.LIFE,
    AffairKind.HABIT: AffairDomain.LIFE,
    AffairKind.FIXED_PLAN: AffairDomain.LIFE,
    AffairKind.TASK_ONEOFF: AffairDomain.WORK,
    AffairKind.TASK_MAINTENANCE: AffairDomain.WORK,
    AffairKind.VENTURE: AffairDomain.CAREER,
    AffairKind.ASYNC_CALLBACK: AffairDomain.WORK,
    AffairKind.BUFFER: AffairDomain.LIFE,
    AffairKind.GENERIC: AffairDomain.WORK,
}

_OCCUPANCY_SOURCE = "occupancy_api"
_WHOLE_DAY_START = time(9, 0)
_WHOLE_DAY_END = time(19, 0)


def _now() -> datetime:
    return datetime.now()


def _today() -> date:
    return _now().date()


def _kind_of(affair: RhythmAffair) -> AffairKind:
    try:
        return AffairKind(affair.kind)
    except ValueError:
        return AffairKind.GENERIC


def week_range(d: date) -> Tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def week_cycle_key(d: date) -> str:
    iso = d.isocalendar()
    return f"W{iso.year}-{iso.week:02d}"


def _parse_hhmm(v: str) -> time:
    parts = str(v).strip().split(":")
    if len(parts) != 2:
        raise RhythmBadRequestError(f"时间格式应为 HH:MM: {v!r}")
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError as exc:
        raise RhythmBadRequestError(f"时间格式应为 HH:MM: {v!r}") from exc


def _parse_block_dt(target_date: date, raw: str) -> datetime:
    """支持 'HH:MM' 或 ISO datetime 字符串解析为本地 naive datetime。"""
    s = str(raw or "").strip()
    if not s:
        raise RhythmBadRequestError("时间不能为空")
    if len(s) <= 5 and ":" in s:
        t = _parse_hhmm(s)
        return datetime.combine(target_date, t)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError as exc:
        raise RhythmBadRequestError(f"无法解析时间: {raw!r}") from exc


def _get_or_create_day(db: Session, d: date) -> Day:
    day = db.query(Day).filter(Day.date == d).first()
    if day is None:
        day = Day(date=d)
        db.add(day)
        db.commit()
        db.refresh(day)
    return day


def _get_affair_or_404(db: Session, affair_id: int) -> RhythmAffair:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        raise RhythmNotFoundError(f"Affair {affair_id} not found")
    return affair


def _sync_venture_target_date(
    affair: RhythmAffair,
    *,
    touched: bool,
    ddl_wins: bool = False,
) -> None:
    """保持 venture 的 kind_meta.target_date 与 urgency_ddl 同步。"""
    if _kind_of(affair) != AffairKind.VENTURE or not touched:
        return
    meta = dict(affair.kind_meta or {})
    target_raw = meta.get("target_date")
    if ddl_wins:
        if affair.urgency_ddl is not None:
            meta["target_date"] = affair.urgency_ddl.date().isoformat()
            affair.kind_meta = meta
        return
    if target_raw:
        try:
            td = date.fromisoformat(str(target_raw)[:10])
            meta["target_date"] = td.isoformat()
            affair.kind_meta = meta
            affair.urgency_ddl = datetime.combine(td, time.min)
        except ValueError:
            pass
    elif affair.urgency_ddl is not None:
        meta["target_date"] = affair.urgency_ddl.date().isoformat()
        affair.kind_meta = meta


def affair_to_response(affair: RhythmAffair) -> AffairResponse:
    kind = _kind_of(affair)
    try:
        state = AffairState(affair.state)
    except ValueError:
        state = AffairState.PLANNED
    domain: Optional[AffairDomain] = None
    if affair.domain:
        try:
            domain = AffairDomain(affair.domain)
        except ValueError:
            domain = None
    info_type: Optional[InfoCollectionType] = None
    if affair.info_collection_type:
        try:
            info_type = InfoCollectionType(affair.info_collection_type)
        except ValueError:
            info_type = None
    return AffairResponse(
        id=affair.id,
        title=affair.title,
        description=affair.description or "",
        domain=domain,
        kind=kind,
        kind_meta=dict(affair.kind_meta or {}),
        state=state,
        importance=int(affair.importance or 3),
        urgency_ddl=affair.urgency_ddl,
        energy_cost=int(affair.energy_cost or 0),
        money_cost=float(affair.money_cost or 0),
        budget_id=affair.budget_id,
        est_minutes=int(affair.est_minutes or 0),
        window_start=affair.window_start,
        window_end=affair.window_end,
        splittable=bool(affair.splittable),
        min_chunk_minutes=int(affair.min_chunk_minutes or 30),
        fallback_plan=affair.fallback_plan or "",
        recurrence_rule_id=affair.recurrence_rule_id,
        day_id=affair.day_id,
        timespan_id=affair.timespan_id,
        parent_id=affair.parent_id,
        info_collection_type=info_type,
        ai_hint=dict(affair.ai_hint or {}),
        score=float(affair.score or 0),
        ref=dict(affair.ref or {}),
        ctime=affair.ctime,
        mtime=affair.mtime,
    )


def block_to_response(
    block: RhythmTimeBlock, affair: Optional[RhythmAffair] = None
) -> TimeBlockResponse:
    try:
        btype = BlockType(block.block_type)
    except ValueError:
        btype = BlockType.FOCUS
    try:
        bstatus = BlockStatus(block.status)
    except ValueError:
        bstatus = BlockStatus.PLANNED
    ref = dict(block.ref or {})
    title = affair.title if affair is not None else (ref.get("label") or None)
    affair_kind: Optional[AffairKind] = _kind_of(affair) if affair is not None else None
    affair_domain: Optional[AffairDomain] = None
    if affair is not None and affair.domain:
        try:
            affair_domain = AffairDomain(affair.domain)
        except ValueError:
            affair_domain = None
    return TimeBlockResponse(
        id=block.id,
        day_id=block.day_id,
        affair_id=block.affair_id,
        affair_title=title,
        affair_kind=affair_kind,
        affair_domain=affair_domain,
        block_type=btype,
        start_time=block.start_time,
        end_time=block.end_time,
        status=bstatus,
        pinned=bool(block.pinned),
        plan_version=int(block.plan_version or 1),
        ref=ref,
    )


def blocks_to_response(
    db: Session, blocks: List[RhythmTimeBlock]
) -> List[TimeBlockResponse]:
    affair_ids = {b.affair_id for b in blocks if b.affair_id is not None}
    affair_map: Dict[int, RhythmAffair] = {}
    if affair_ids:
        rows = db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all()
        affair_map = {a.id: a for a in rows}
    return [block_to_response(b, affair_map.get(b.affair_id) if b.affair_id else None) for b in blocks]


def _log_to_response(log: RhythmDisciplineLog) -> CheckinLogResponse:
    return CheckinLogResponse(
        id=log.id,
        affair_id=log.affair_id,
        log_date=log.log_date,
        cycle_key=log.cycle_key,
        result=CheckinResult(log.result),
        note=log.note or "",
        source=log.source or "manual",
        created_at=log.created_at,
    )


# ============================================================================
# Affair CRUD & State Machine
# ============================================================================


def _default_state_for_kind(kind: AffairKind) -> AffairState:
    if kind == AffairKind.GENERIC:
        return AffairState.INBOX
    if is_longterm_kind(kind):
        return AffairState.ACTIVE
    return AffairState.PLANNED


def create_affair_impl(db: Session, request: AffairCreateRequest) -> AffairResponse:
    if request.kind == AffairKind.BUFFER:
        raise RhythmBadRequestError("buffer 由系统保留，不可直接创建")
    domain = request.domain or _DEFAULT_DOMAIN_BY_KIND.get(request.kind, AffairDomain.WORK)
    state = request.state or _default_state_for_kind(request.kind)
    meta = validate_kind_meta(request.kind, request.kind_meta)

    affair = RhythmAffair(
        title=request.title.strip(),
        description=request.description or "",
        domain=domain.value,
        kind=request.kind.value,
        kind_meta=meta,
        state=state.value,
        importance=request.importance,
        urgency_ddl=request.urgency_ddl,
        energy_cost=request.energy_cost,
        money_cost=Decimal(str(request.money_cost)),
        budget_id=request.budget_id,
        est_minutes=request.est_minutes,
        window_start=request.window_start,
        window_end=request.window_end,
        splittable=request.splittable,
        min_chunk_minutes=request.min_chunk_minutes,
        fallback_plan=request.fallback_plan or "",
        day_id=request.day_id,
        timespan_id=request.timespan_id,
        parent_id=request.parent_id,
        info_collection_type=(
            request.info_collection_type.value if request.info_collection_type else None
        ),
        ref=dict(request.ref or {}),
    )
    _sync_venture_target_date(affair, touched=True, ddl_wins=False)
    db.add(affair)
    db.commit()
    db.refresh(affair)

    if request.kind == AffairKind.FIXED_PLAN and state == AffairState.SCHEDULED:
        if meta.get("fixed_start") and meta.get("fixed_end"):
            _pin_fixed_plan_blocks(db, affair)

    logger.info("[rhythm] affair created: #%s [%s/%s] %s", affair.id, affair.kind, affair.state, affair.title)
    return affair_to_response(affair)


def get_affair_impl(db: Session, affair_id: int) -> Optional[AffairResponse]:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    return affair_to_response(affair) if affair else None


def list_affairs_impl(
    db: Session,
    states: Optional[List[str]] = None,
    domains: Optional[List[str]] = None,
    kinds: Optional[List[str]] = None,
    day_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    urgency_ddl_before: Optional[datetime] = None,
    urgency_ddl_after: Optional[datetime] = None,
    skip: int = 0,
    limit: int = -1,
) -> List[AffairResponse]:
    query = db.query(RhythmAffair)
    if states:
        query = query.filter(RhythmAffair.state.in_(states))
    if domains:
        query = query.filter(RhythmAffair.domain.in_(domains))
    if kinds:
        query = query.filter(RhythmAffair.kind.in_(kinds))
    if day_id is not None:
        query = query.filter(RhythmAffair.day_id == day_id)
    if parent_id is not None:
        query = query.filter(RhythmAffair.parent_id == parent_id)
    if urgency_ddl_before is not None:
        query = query.filter(RhythmAffair.urgency_ddl <= urgency_ddl_before)
    if urgency_ddl_after is not None:
        query = query.filter(RhythmAffair.urgency_ddl >= urgency_ddl_after)
    query = query.order_by(RhythmAffair.id.desc())
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)
    return [affair_to_response(a) for a in query.all()]


def update_affair_impl(
    db: Session, affair_id: int, request: AffairUpdateRequest
) -> Optional[AffairResponse]:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        return None
    fields = request.model_fields_set

    if "kind" in fields and request.kind is not None:
        if request.kind == AffairKind.BUFFER:
            raise RhythmBadRequestError("禁止修改为 buffer")
        affair.kind = request.kind.value
    new_kind = _kind_of(affair)

    if "title" in fields and request.title is not None:
        affair.title = request.title.strip()
    if "description" in fields and request.description is not None:
        affair.description = request.description
    if "domain" in fields:
        affair.domain = request.domain.value if request.domain is not None else None
    if "importance" in fields and request.importance is not None:
        affair.importance = request.importance
    if "energy_cost" in fields and request.energy_cost is not None:
        affair.energy_cost = request.energy_cost
    if "money_cost" in fields and request.money_cost is not None:
        affair.money_cost = Decimal(str(request.money_cost))
    if "budget_id" in fields:
        affair.budget_id = request.budget_id
    if "est_minutes" in fields and request.est_minutes is not None:
        affair.est_minutes = request.est_minutes
    if "splittable" in fields and request.splittable is not None:
        affair.splittable = request.splittable
    if "min_chunk_minutes" in fields and request.min_chunk_minutes is not None:
        affair.min_chunk_minutes = request.min_chunk_minutes
    if "fallback_plan" in fields and request.fallback_plan is not None:
        affair.fallback_plan = request.fallback_plan
    if "day_id" in fields:
        affair.day_id = request.day_id
    if "timespan_id" in fields:
        affair.timespan_id = request.timespan_id
    if "parent_id" in fields:
        affair.parent_id = request.parent_id
    if "info_collection_type" in fields:
        affair.info_collection_type = (
            request.info_collection_type.value if request.info_collection_type else None
        )
    if "ai_hint" in fields and request.ai_hint is not None:
        affair.ai_hint = dict(request.ai_hint)
    if "ref" in fields and request.ref is not None:
        affair.ref = dict(request.ref)

    if request.clear_urgency_ddl:
        affair.urgency_ddl = None
        if new_kind == AffairKind.VENTURE:
            meta = dict(affair.kind_meta or {})
            meta.pop("target_date", None)
            affair.kind_meta = meta
    elif "urgency_ddl" in fields:
        affair.urgency_ddl = request.urgency_ddl

    if request.clear_window:
        affair.window_start = None
        affair.window_end = None
    else:
        if "window_start" in fields:
            affair.window_start = request.window_start
        if "window_end" in fields:
            affair.window_end = request.window_end

    meta_replaced = "kind_meta" in fields and request.kind_meta is not None
    if meta_replaced:
        affair.kind_meta = validate_kind_meta(new_kind, request.kind_meta)
        if new_kind == AffairKind.VENTURE and not affair.kind_meta.get("target_date"):
            affair.urgency_ddl = None
    elif "kind" in fields:
        affair.kind_meta = validate_kind_meta(new_kind, affair.kind_meta or {})

    ddl_touched = "urgency_ddl" in fields and not request.clear_urgency_ddl
    _sync_venture_target_date(
        affair,
        touched=meta_replaced or ddl_touched,
        ddl_wins=ddl_touched and not meta_replaced,
    )

    db.commit()
    db.refresh(affair)
    return affair_to_response(affair)


def delete_affair_impl(db: Session, affair_id: int) -> Optional[AffairResponse]:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        return None
    resp = affair_to_response(affair)
    children = db.query(RhythmAffair).filter(RhythmAffair.parent_id == affair_id).all()
    ids = [affair_id, *[c.id for c in children]]
    db.query(RhythmTimeBlock).filter(RhythmTimeBlock.affair_id.in_(ids)).delete(
        synchronize_session=False
    )
    db.query(RhythmDisciplineLog).filter(RhythmDisciplineLog.affair_id.in_(ids)).delete(
        synchronize_session=False
    )
    for c in children:
        db.delete(c)
    db.delete(affair)
    db.commit()
    return resp


def _pin_fixed_plan_blocks(db: Session, affair: RhythmAffair) -> None:
    meta = affair.kind_meta or {}
    fixed_start = meta.get("fixed_start")
    fixed_end = meta.get("fixed_end")
    if not fixed_start or not fixed_end:
        return
    fs = datetime.fromisoformat(str(fixed_start)) if isinstance(fixed_start, str) else fixed_start
    fe = datetime.fromisoformat(str(fixed_end)) if isinstance(fixed_end, str) else fixed_end
    if fe <= fs:
        raise RhythmBadRequestError("fixed_plan 的 fixed_end 必须晚于 fixed_start")

    cursor = fs.date()
    while cursor <= fe.date():
        day = _get_or_create_day(db, cursor)
        block_start = max(fs, datetime.combine(cursor, time.min))
        block_end = min(fe, datetime.combine(cursor, time.max).replace(microsecond=0))
        existing = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id == day.id,
                RhythmTimeBlock.affair_id == affair.id,
                RhythmTimeBlock.block_type == "fixed",
                RhythmTimeBlock.status != BlockStatus.MOVED.value,
            )
            .first()
        )
        if existing is None:
            db.add(
                RhythmTimeBlock(
                    day_id=day.id,
                    affair_id=affair.id,
                    block_type="fixed",
                    start_time=block_start,
                    end_time=block_end,
                    status=BlockStatus.PLANNED.value,
                    pinned=True,
                    plan_version=1,
                    ref={"label": affair.title, "source": "fixed_plan"},
                )
            )
        cursor += timedelta(days=1)
    db.commit()


def transit_affair_state_impl(
    db: Session, affair_id: int, request: AffairStateRequest
) -> AffairResponse:
    affair = _get_affair_or_404(db, affair_id)
    kind = _kind_of(affair)
    action = request.action
    current = AffairState(affair.state)

    if current in TERMINAL_STATES:
        raise RhythmStateConflictError(f"终态 {current.value} 不允许再转移")

    if kind == AffairKind.FIXED_PLAN and action == AffairAction.CONFIRM:
        if affair.domain is None:
            affair.domain = _DEFAULT_DOMAIN_BY_KIND[kind].value
        _pin_fixed_plan_blocks(db, affair)
        affair.state = AffairState.SCHEDULED.value
        db.commit()
        db.refresh(affair)
        return affair_to_response(affair)

    transition = resolve_transition(kind, action)
    if transition is None:
        raise RhythmBadRequestError(f"事务类型 {kind.value} 不支持动作 {action.value}")

    allowed_from, target = transition
    if current not in allowed_from:
        raise RhythmStateConflictError(
            f"状态 {current.value} 不允许执行 {action.value}（允许: {sorted(s.value for s in allowed_from)}）"
        )

    if action == AffairAction.DEFER:
        if request.defer_to is None:
            raise RhythmBadRequestError("defer 必须携带 defer_to")
        affair.window_start = request.defer_to
        affair.urgency_ddl = request.defer_to
        if request.defer_end is not None:
            affair.window_end = request.defer_end

    if action == AffairAction.CONFIRM and affair.domain is None:
        affair.domain = _DEFAULT_DOMAIN_BY_KIND.get(kind, AffairDomain.WORK).value

    affair.state = target.value
    db.commit()
    db.refresh(affair)
    return affair_to_response(affair)


def confirm_hint_impl(
    db: Session, affair_id: int, request: ConfirmHintRequest
) -> AffairResponse:
    affair = _get_affair_or_404(db, affair_id)
    hint = affair.ai_hint or {}
    if not hint:
        raise RhythmBadRequestError("该事务没有待确认的 AI 建议")

    if not request.accept:
        ref = dict(affair.ref or {})
        ref["rejected_hint"] = hint
        affair.ref = ref
        affair.ai_hint = {}
        db.commit()
        db.refresh(affair)
        return affair_to_response(affair)

    merged: Dict[str, Any] = dict(hint)
    if request.overrides:
        merged.update(request.overrides)

    new_kind = AffairKind(merged["kind"]) if merged.get("kind") else _kind_of(affair)
    if new_kind == AffairKind.BUFFER:
        raise RhythmBadRequestError("禁止改判为 buffer")
    affair.kind = new_kind.value
    if merged.get("domain"):
        affair.domain = AffairDomain(merged["domain"]).value
    elif affair.domain is None:
        affair.domain = _DEFAULT_DOMAIN_BY_KIND.get(new_kind, AffairDomain.WORK).value
    affair.kind_meta = validate_kind_meta(new_kind, merged.get("kind_meta") or affair.kind_meta or {})
    if merged.get("importance") is not None:
        affair.importance = max(1, min(5, int(merged["importance"])))
    if merged.get("est_minutes") is not None:
        affair.est_minutes = max(0, int(merged["est_minutes"]))
    affair.state = _default_state_for_kind(new_kind).value
    affair.ai_hint = {}
    _sync_venture_target_date(affair, touched=True, ddl_wins=False)
    db.commit()
    db.refresh(affair)
    return affair_to_response(affair)


def split_affair_impl(
    db: Session, affair_id: int, request: AffairSplitRequest
) -> AffairListResponse:
    parent = _get_affair_or_404(db, affair_id)
    created: List[RhythmAffair] = []
    for child in request.children:
        row = RhythmAffair(
            title=child.title.strip(),
            description=child.description or "",
            domain=parent.domain or AffairDomain.WORK.value,
            kind=AffairKind.TASK_ONEOFF.value,
            kind_meta={},
            state=AffairState.PLANNED.value,
            importance=child.importance or parent.importance or 3,
            est_minutes=child.est_minutes,
            energy_cost=child.energy_cost,
            urgency_ddl=child.urgency_ddl,
            timespan_id=child.timespan_id or parent.timespan_id,
            fallback_plan=child.fallback_plan or "",
            parent_id=parent.id,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return AffairListResponse(affairs=[affair_to_response(c) for c in created], total=len(created))


# ============================================================================
# Venture（重要项目倒排与里程碑）
# ============================================================================


def add_milestone_impl(
    db: Session, venture_id: int, request: VentureMilestoneRequest
) -> AffairResponse:
    venture = _get_affair_or_404(db, venture_id)
    if _kind_of(venture) != AffairKind.VENTURE:
        raise RhythmBadRequestError("仅 venture 项目可添加里程碑")
    sub = RhythmAffair(
        title=request.title.strip(),
        description=request.description or "",
        domain=venture.domain or AffairDomain.CAREER.value,
        kind=AffairKind.TASK_ONEOFF.value,
        kind_meta={},
        state=AffairState.PLANNED.value,
        importance=venture.importance or 4,
        est_minutes=request.est_minutes or 60,
        energy_cost=venture.energy_cost or 15,
        urgency_ddl=request.urgency_ddl,
        timespan_id=request.timespan_id,
        parent_id=venture.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return affair_to_response(sub)


def milestone_done_impl(db: Session, milestone_id: int) -> AffairResponse:
    milestone = _get_affair_or_404(db, milestone_id)
    if milestone.parent_id is None:
        raise RhythmBadRequestError("该事务不是里程碑（无 parent_id）")
    current = AffairState(milestone.state)
    if current in (AffairState.DONE, AffairState.CANCELED):
        return affair_to_response(milestone)
    milestone.state = AffairState.DONE.value
    db.commit()
    db.refresh(milestone)
    return affair_to_response(milestone)


def venture_progress_impl(db: Session, venture_id: int) -> VentureProgressResponse:
    venture = _get_affair_or_404(db, venture_id)
    if _kind_of(venture) != AffairKind.VENTURE:
        raise RhythmBadRequestError("仅 venture 有倒排进度")
    return _build_venture_progress(db, venture)


def _build_venture_progress(db: Session, venture: RhythmAffair) -> VentureProgressResponse:
    meta = venture.kind_meta or {}
    target_date: Optional[date] = None
    if meta.get("target_date"):
        try:
            target_date = date.fromisoformat(str(meta["target_date"])[:10])
        except ValueError:
            target_date = None
    elif venture.urgency_ddl:
        target_date = venture.urgency_ddl.date()

    weekly_budget = float(meta.get("weekly_budget_hours") or 0.0)
    total_est = float(meta.get("total_est_hours") or 0.0)

    today = _today()
    days_left: Optional[int] = (target_date - today).days if target_date else None
    weeks_left: Optional[float] = (
        round(max(days_left / 7.0, 0.0), 2) if days_left is not None else None
    )

    milestones = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.parent_id == venture.id)
        .order_by(RhythmAffair.id)
        .all()
    )
    affair_ids = [venture.id, *[m.id for m in milestones]]
    monday, sunday = week_range(today)
    recent_start = today - timedelta(days=13)

    day_rows = (
        db.query(Day.id, Day.date)
        .filter(Day.date >= min(monday, recent_start), Day.date <= max(sunday, today))
        .all()
    )
    day_date_by_id = {r.id: r.date for r in day_rows}

    blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.affair_id.in_(affair_ids),
            RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
        )
        .all()
    )
    week_minutes = 0
    recent_14d_minutes = 0
    total_done_minutes = 0
    for b in blocks:
        mins = max(0, int((b.end_time - b.start_time).total_seconds() // 60))
        bd = day_date_by_id.get(b.day_id)
        if b.status == "DONE":
            total_done_minutes += mins
            if bd and recent_start <= bd <= today:
                recent_14d_minutes += mins
        if bd and monday <= bd <= sunday:
            week_minutes += mins

    done_count = sum(1 for m in milestones if m.state == AffairState.DONE.value)
    completion = (done_count / len(milestones)) if milestones else 0.0

    return VentureProgressResponse(
        affair_id=venture.id,
        title=venture.title,
        description=venture.description or "",
        state=venture.state,
        target_date=target_date,
        days_left=days_left,
        weeks_left=weeks_left,
        weekly_budget_hours=weekly_budget,
        week_consumed_hours=round(week_minutes / 60.0, 2),
        recent_14d_hours=round(recent_14d_minutes / 60.0, 2),
        total_done_hours=round(total_done_minutes / 60.0, 2),
        total_est_hours=total_est,
        milestones=[affair_to_response(m) for m in milestones],
        completion_ratio=round(completion, 3),
    )


def list_active_projects_progress_impl(db: Session) -> List[VentureProgressResponse]:
    ventures = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.VENTURE.value,
            ~RhythmAffair.state.in_([s.value for s in TERMINAL_STATES]),
        )
        .order_by(RhythmAffair.urgency_ddl.asc().nullslast(), RhythmAffair.id.asc())
        .all()
    )
    return [_build_venture_progress(db, v) for v in ventures]


# ============================================================================
# Checkin & HealthCheckin（轻量打卡与健康速记）
# ============================================================================


def _habit_week_done_count(db: Session, affair_id: int, d: date) -> int:
    monday, sunday = week_range(d)
    return (
        db.query(RhythmDisciplineLog)
        .filter(
            RhythmDisciplineLog.affair_id == affair_id,
            RhythmDisciplineLog.result == CheckinResult.DONE.value,
            RhythmDisciplineLog.log_date >= monday,
            RhythmDisciplineLog.log_date <= sunday,
        )
        .count()
    )


def checkin_impl(db: Session, request: CheckinRequest) -> CheckinLogResponse:
    affair = _get_affair_or_404(db, request.affair_id)
    kind = _kind_of(affair)
    d = request.log_date or _today()
    meta = dict(affair.kind_meta or {})
    cycle_key = week_cycle_key(d) if meta.get("cycle") == "weekly" else d.isoformat()

    log = RhythmDisciplineLog(
        affair_id=affair.id,
        log_date=d,
        cycle_key=cycle_key,
        result=request.result.value,
        note=request.note or "",
        source=request.source or "manual",
    )
    db.add(log)

    if kind == AffairKind.HABIT and request.result == CheckinResult.DONE:
        meta["last_done_date"] = d.isoformat()
        meta["streak"] = int(meta.get("streak") or 0) + 1
        meta["best_streak"] = max(int(meta.get("best_streak") or 0), meta["streak"])
        affair.kind_meta = meta

    db.commit()
    db.refresh(log)
    return _log_to_response(log)


def list_checkins_impl(
    db: Session,
    affair_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    cycle_key: Optional[str] = None,
    skip: int = 0,
    limit: int = -1,
) -> List[CheckinLogResponse]:
    query = db.query(RhythmDisciplineLog)
    if affair_id is not None:
        query = query.filter(RhythmDisciplineLog.affair_id == affair_id)
    if start_date is not None:
        query = query.filter(RhythmDisciplineLog.log_date >= start_date)
    if end_date is not None:
        query = query.filter(RhythmDisciplineLog.log_date <= end_date)
    if cycle_key:
        query = query.filter(RhythmDisciplineLog.cycle_key == cycle_key)
    query = query.order_by(RhythmDisciplineLog.log_date.desc(), RhythmDisciplineLog.id.desc())
    if skip > 0:
        query = query.offset(skip)
    if limit > 0:
        query = query.limit(limit)
    return [_log_to_response(x) for x in query.all()]


def today_checkins_impl(db: Session, d: Optional[date] = None) -> CheckinTodayResponse:
    d = d or _today()
    actives = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind.in_([AffairKind.PRECEPT.value, AffairKind.HABIT.value]),
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    precepts: List[CheckinTodayItem] = []
    habits: List[CheckinTodayItem] = []
    for a in actives:
        meta = a.kind_meta or {}
        today_log = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id == a.id,
                RhythmDisciplineLog.log_date == d,
            )
            .order_by(RhythmDisciplineLog.id.desc())
            .first()
        )
        if _kind_of(a) == AffairKind.PRECEPT:
            precepts.append(
                CheckinTodayItem(
                    affair=affair_to_response(a),
                    done_today=today_log is not None,
                    last_result=CheckinResult(today_log.result) if today_log else None,
                )
            )
        else:
            habits.append(
                CheckinTodayItem(
                    affair=affair_to_response(a),
                    done_today=today_log is not None and today_log.result == "done",
                    last_result=CheckinResult(today_log.result) if today_log else None,
                    week_done_count=_habit_week_done_count(db, a.id, d),
                    week_target=int(meta.get("freq_per_week") or 3),
                )
            )
    return CheckinTodayResponse(date=d, precepts=precepts, habits=habits)


def _opt_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    return float(v)


def _get_or_create_health_affair(db: Session, collection_type: str) -> RhythmAffair:
    affair = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.info_collection_type == collection_type)
        .first()
    )
    if affair is not None:
        return affair
    label_map = {
        "weight": "体重记录",
        "meal": "饮食记录",
        "exercise": "运动记录",
        "medication": "用药记录",
        "sleep": "睡眠记录",
        "mood": "心情记录",
        "energy": "精力记录",
    }
    affair = RhythmAffair(
        title=label_map.get(collection_type, f"健康速记:{collection_type}"),
        domain=AffairDomain.LIFE.value,
        kind=AffairKind.HABIT.value,
        kind_meta={"freq_per_week": 7, "min_session_minutes": 5},
        state=AffairState.ACTIVE.value,
        info_collection_type=collection_type,
    )
    db.add(affair)
    db.flush()
    return affair


def health_checkin_impl(db: Session, request: HealthCheckinRequest) -> HealthCheckinResponse:
    """健康速记：双写 health 表、HealthSignal 与轻量打卡日志。"""
    from sail_server.application.dto.health import (
        DietCreateRequest,
        EnergyLevelCreateRequest,
        MealType,
        MedicationCreateRequest,
        MoodCreateRequest,
        SleepCreateRequest,
    )
    from sail_server.model.health import (
        create_diet_impl,
        create_energy_level_impl,
        create_medication_impl,
        create_mood_impl,
        create_sleep_impl,
    )

    log_date = request.log_date or _today()
    day = _get_or_create_day(db, log_date)
    now = _now()
    collection_type = request.collection_type.value
    ref_id: Optional[int] = None

    try:
        if collection_type == InfoCollectionType.WEIGHT.value:
            value_kg = float(request.payload.get("value_kg", 0))
            if value_kg <= 0:
                raise RhythmBadRequestError("weight 速记需提供正数 value_kg")
            measured_at = request.payload.get("measured_at")
            if measured_at is None or measured_at == "":
                htime = now
            elif isinstance(measured_at, (int, float)):
                htime = datetime.fromtimestamp(float(measured_at))
            else:
                s_ts = str(measured_at).strip()
                try:
                    htime = datetime.fromtimestamp(float(s_ts))
                except ValueError:
                    dt = datetime.fromisoformat(s_ts.replace("Z", "+00:00"))
                    htime = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
            record = Weight(value=str(value_kg), htime=htime, description=request.note)
            db.add(record)
            db.flush()
            ref_id = record.id
            db.add(
                HealthSignal(
                    signal_type="weight",
                    ref_id=record.id,
                    day_id=day.id,
                    htime=record.htime,
                    value_json={"value_kg": value_kg, "note": request.note},
                )
            )
        elif collection_type == InfoCollectionType.EXERCISE.value:
            record = Exercise(htime=now, description=request.payload.get("activity", ""))
            db.add(record)
            db.flush()
            ref_id = record.id
            db.add(
                HealthSignal(
                    signal_type="exercise",
                    ref_id=record.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        elif collection_type == InfoCollectionType.MEAL.value:
            meal_type = request.payload.get("meal_type", "snack")
            try:
                meal_enum = MealType(meal_type)
            except ValueError:
                meal_enum = MealType.SNACK
            diet = create_diet_impl(
                db,
                DietCreateRequest(
                    meal_type=meal_enum,
                    description=str(request.payload.get("description", "")),
                    calories=_opt_float(request.payload.get("calories")),
                    carbs=_opt_float(request.payload.get("carbs")),
                    sugar=_opt_float(request.payload.get("sugar")),
                    protein=_opt_float(request.payload.get("protein")),
                    fat=_opt_float(request.payload.get("fat")),
                    fiber=_opt_float(request.payload.get("fiber")),
                    sodium=_opt_float(request.payload.get("sodium")),
                    htime=_opt_float(request.payload.get("htime")),
                ),
            )
            ref_id = diet.id
            db.add(
                HealthSignal(
                    signal_type="meal",
                    ref_id=diet.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        elif collection_type == InfoCollectionType.MEDICATION.value:
            planned_date = log_date
            if request.payload.get("planned_date"):
                planned_date = datetime.fromisoformat(str(request.payload["planned_date"])).date()
            medication = create_medication_impl(
                db,
                MedicationCreateRequest(
                    name=str(request.payload.get("name", "")),
                    dosage=str(request.payload.get("dosage", "")),
                    frequency=str(request.payload.get("frequency", "daily")),
                    schedule_times=list(request.payload.get("schedule_times") or []),
                    planned_date=planned_date,
                    taken=bool(request.payload.get("taken", False)),
                    note=request.note,
                    is_supplement=bool(request.payload.get("is_supplement", False)),
                    htime=_opt_float(request.payload.get("htime")),
                    taken_at=_opt_float(request.payload.get("taken_at")),
                ),
            )
            ref_id = medication.id
            db.add(
                HealthSignal(
                    signal_type="medication",
                    ref_id=medication.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        elif collection_type == InfoCollectionType.SLEEP.value:
            sleep = create_sleep_impl(
                db,
                SleepCreateRequest(
                    hours=float(request.payload.get("hours", 0)),
                    quality=int(request.payload.get("quality", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=_opt_float(request.payload.get("htime")),
                ),
            )
            ref_id = sleep.id
            db.add(
                HealthSignal(
                    signal_type="sleep",
                    ref_id=sleep.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        elif collection_type == InfoCollectionType.MOOD.value:
            mood = create_mood_impl(
                db,
                MoodCreateRequest(
                    score=int(request.payload.get("score", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=_opt_float(request.payload.get("htime")),
                ),
            )
            ref_id = mood.id
            db.add(
                HealthSignal(
                    signal_type="mood",
                    ref_id=mood.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        elif collection_type == InfoCollectionType.ENERGY.value:
            energy = create_energy_level_impl(
                db,
                EnergyLevelCreateRequest(
                    score=int(request.payload.get("score", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=_opt_float(request.payload.get("htime")),
                ),
            )
            ref_id = energy.id
            db.add(
                HealthSignal(
                    signal_type="energy",
                    ref_id=energy.id,
                    day_id=day.id,
                    htime=now,
                    value_json=dict(request.payload),
                )
            )
        else:
            raise RhythmBadRequestError(f"未知 collection_type: {collection_type}")

        affair = _get_or_create_health_affair(db, collection_type)
        log = RhythmDisciplineLog(
            affair_id=affair.id,
            log_date=log_date,
            cycle_key=log_date.isoformat(),
            result=CheckinResult.DONE.value,
            note=request.note,
            source="health",
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return HealthCheckinResponse(
            id=log.id,
            collection_type=collection_type,
            log_date=log_date,
            ref_id=ref_id,
            affair_id=affair.id,
            note=request.note,
            created_at=log.created_at,
        )
    except RhythmError:
        db.rollback()
        raise
    except (ValueError, TypeError) as exc:
        db.rollback()
        raise RhythmBadRequestError(f"健康速记数据格式错误: {exc}") from exc


# ============================================================================
# Occupancy（会议/请假/出行刚性占用）
# ============================================================================


def _occupancy_to_response(block: RhythmTimeBlock, d: date) -> OccupancyResponse:
    ref = block.ref or {}
    return OccupancyResponse(
        id=block.id,
        date=d,
        start=block.start_time.strftime("%H:%M") if block.start_time else None,
        end=block.end_time.strftime("%H:%M") if block.end_time else None,
        whole_day=bool(ref.get("whole_day")),
        occupancy_type=ref.get("occupancy_type") or "other",
        label=ref.get("label") or "",
        note=ref.get("note") or "",
    )


def _iter_occupancy_blocks(db: Session, day_id: int) -> List[RhythmTimeBlock]:
    blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day_id,
            RhythmTimeBlock.block_type == BlockType.OCCUPIED.value,
            RhythmTimeBlock.status != BlockStatus.MOVED.value,
        )
        .order_by(RhythmTimeBlock.start_time)
        .all()
    )
    return [b for b in blocks if (b.ref or {}).get("source") == _OCCUPANCY_SOURCE]


def create_occupancy_impl(db: Session, request: OccupancyCreateRequest) -> OccupancyResponse:
    day = _get_or_create_day(db, request.date)
    whole_day = bool(request.whole_day)
    if whole_day or (request.start is None and request.end is None and request.occupancy_type.value == "leave"):
        whole_day = True
        start_dt = datetime.combine(request.date, _WHOLE_DAY_START)
        end_dt = datetime.combine(request.date, _WHOLE_DAY_END)
    else:
        if not request.start or not request.end:
            raise RhythmBadRequestError("非整日占用必须提供 start 与 end（HH:MM）")
        start_dt = datetime.combine(request.date, _parse_hhmm(request.start))
        end_dt = datetime.combine(request.date, _parse_hhmm(request.end))
    if end_dt <= start_dt:
        raise RhythmBadRequestError("占用结束时间必须晚于开始时间")

    # 幂等去重
    for existing in _iter_occupancy_blocks(db, day.id):
        ref = existing.ref or {}
        if (
            existing.start_time == start_dt
            and existing.end_time == end_dt
            and ref.get("occupancy_type") == request.occupancy_type.value
        ):
            return _occupancy_to_response(existing, request.date)

    label = request.label.strip() or request.occupancy_type.value
    block = RhythmTimeBlock(
        day_id=day.id,
        affair_id=None,
        block_type=BlockType.OCCUPIED.value,
        start_time=start_dt,
        end_time=end_dt,
        status=BlockStatus.PLANNED.value,
        pinned=True,
        plan_version=1,
        ref={
            "source": _OCCUPANCY_SOURCE,
            "occupancy_type": request.occupancy_type.value,
            "whole_day": whole_day,
            "label": label,
            "note": request.note or "",
        },
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return _occupancy_to_response(block, request.date)


def list_occupancies_impl(db: Session, d: date) -> OccupancyListResponse:
    day = db.query(Day).filter(Day.date == d).first()
    if day is None:
        return OccupancyListResponse(date=d, occupancies=[])
    blocks = _iter_occupancy_blocks(db, day.id)
    return OccupancyListResponse(
        date=d, occupancies=[_occupancy_to_response(b, d) for b in blocks]
    )


def delete_occupancy_impl(db: Session, block_id: int) -> None:
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"Occupancy block {block_id} not found")
    if (block.ref or {}).get("source") != _OCCUPANCY_SOURCE:
        raise RhythmBadRequestError("该时间块不是特殊占用块，不能经 /occupancy 删除")
    db.delete(block)
    db.commit()


# ============================================================================
# Timeline & SailTick AI Sync（核心画布读写）
# ============================================================================


def _compute_domain_minutes(blocks: List[TimeBlockResponse]) -> DomainMinutes:
    life = work = career = 0
    for b in blocks:
        if b.status in (BlockStatus.MOVED, BlockStatus.SKIPPED):
            continue
        mins = max(0, int((b.end_time - b.start_time).total_seconds() // 60))
        if b.affair_domain == AffairDomain.CAREER or b.block_type == BlockType.CAREER:
            career += mins
        elif b.affair_domain == AffairDomain.WORK or b.block_type in (
            BlockType.FOCUS,
            BlockType.WORK_WINDOW,
            BlockType.ASYNC_KICKOFF,
            BlockType.ASYNC_REVIEW,
        ):
            work += mins
        elif b.block_type not in (BlockType.SLEEP, BlockType.BUFFER, BlockType.OCCUPIED):
            life += mins
    return DomainMinutes(life=life, work=work, career=career)


def get_day_timeline_impl(
    db: Session, d: date, with_checkins: bool = True
) -> DayTimelineResponse:
    day = _get_or_create_day(db, d)
    raw_blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day.id,
            RhythmTimeBlock.status != BlockStatus.MOVED.value,
        )
        .order_by(RhythmTimeBlock.start_time.asc(), RhythmTimeBlock.id.asc())
        .all()
    )
    resp_blocks = blocks_to_response(db, raw_blocks)
    plan_version = max((b.plan_version for b in resp_blocks), default=0)

    ai_rationale = ""
    ai_updated_at: Optional[datetime] = None
    # 优先取最新版本块上的 ai_rationale
    for b in sorted(raw_blocks, key=lambda x: (x.plan_version or 0, x.id), reverse=True):
        ref = b.ref or {}
        if ref.get("ai_rationale"):
            ai_rationale = str(ref["ai_rationale"])
            ai_updated_at = b.mtime or b.ctime
            break

    completed_minutes = 0
    planned_minutes = 0
    for b in resp_blocks:
        mins = max(0, int((b.end_time - b.start_time).total_seconds() // 60))
        if b.status == BlockStatus.DONE:
            completed_minutes += mins
            planned_minutes += mins
        elif b.status in (BlockStatus.PLANNED, BlockStatus.DOING):
            planned_minutes += mins

    return DayTimelineResponse(
        date=d,
        day_id=day.id,
        plan_version=plan_version,
        ai_rationale=ai_rationale,
        ai_updated_at=ai_updated_at,
        blocks=resp_blocks,
        completed_minutes=completed_minutes,
        planned_minutes=planned_minutes,
        domain_minutes=_compute_domain_minutes(resp_blocks),
        checkins=today_checkins_impl(db, d) if with_checkins else None,
    )


def sync_ai_timeline_impl(
    db: Session, request: AITimelineSyncRequest
) -> AITimelineSyncResponse:
    """SailTick AI 自主编排某日时间线并落库。

    规则：
    1. 保留所有 DONE / DOING（preserve_done=True）和 pinned 块（preserve_pinned=True）；
    2. 将其余旧 PLANNED / SKIPPED 块标记为 MOVED（版本归档，plan_version + 1）；
    3. 写入 AI 新编排的时间块，附带 ai_rationale 与 source；
    4. 若新块关联了一次性 INBOX/PLANNED/DEFERRED 事务，自动将其状态推进到 SCHEDULED。
    """
    day = _get_or_create_day(db, request.date)
    existing = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day.id,
            RhythmTimeBlock.status != BlockStatus.MOVED.value,
        )
        .all()
    )
    max_ver = (
        db.query(func.max(RhythmTimeBlock.plan_version))
        .filter(RhythmTimeBlock.day_id == day.id)
        .scalar()
        or 0
    )
    next_version = int(max_ver) + 1

    preserved_blocks: List[RhythmTimeBlock] = []
    archived_count = 0
    for b in existing:
        keep_done = request.preserve_done and b.status in (
            BlockStatus.DONE.value,
            BlockStatus.DOING.value,
        )
        keep_pinned = request.preserve_pinned and bool(b.pinned)
        if keep_done or keep_pinned:
            preserved_blocks.append(b)
        else:
            b.status = BlockStatus.MOVED.value
            archived_count += 1

    now_iso = _now().isoformat()
    created_blocks: List[RhythmTimeBlock] = []
    touched_affair_ids: set[int] = set()

    for idx, item in enumerate(request.blocks):
        start_dt = _parse_block_dt(request.date, item.start)
        end_dt = _parse_block_dt(request.date, item.end)
        if end_dt <= start_dt:
            raise RhythmBadRequestError(
                f"时间块 '{item.title}' 结束时间 ({item.end}) 必须晚于开始时间 ({item.start})"
            )
        affair_id = item.affair_id
        if affair_id is not None:
            aff = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
            if aff is None:
                affair_id = None
            else:
                touched_affair_ids.add(aff.id)

        ref: Dict[str, Any] = {
            "label": item.title.strip(),
            "source": request.source or "sailtick",
            "ai_updated_at": now_iso,
        }
        if item.note:
            ref["note"] = item.note.strip()
        if request.rationale and idx == 0:
            ref["ai_rationale"] = request.rationale.strip()

        nb = RhythmTimeBlock(
            day_id=day.id,
            affair_id=affair_id,
            block_type=item.block_type.value,
            start_time=start_dt,
            end_time=end_dt,
            status=BlockStatus.PLANNED.value,
            pinned=bool(item.pinned),
            plan_version=next_version,
            ref=ref,
        )
        db.add(nb)
        created_blocks.append(nb)

    # 若 AI 刻意清空了所有块（例如提示休息）但给了 rationale，记录到保留块之一以便展示
    if not created_blocks and request.rationale and preserved_blocks:
        p0 = preserved_blocks[0]
        p_ref = dict(p0.ref or {})
        p_ref["ai_rationale"] = request.rationale.strip()
        p_ref["ai_updated_at"] = now_iso
        p0.ref = p_ref

    # 自动推进被排入日程的一次性事务状态到 SCHEDULED
    if touched_affair_ids:
        rows = db.query(RhythmAffair).filter(RhythmAffair.id.in_(touched_affair_ids)).all()
        for aff in rows:
            kind = _kind_of(aff)
            if not is_longterm_kind(kind) and aff.state in (
                AffairState.INBOX.value,
                AffairState.PLANNED.value,
                AffairState.DEFERRED.value,
            ):
                aff.state = AffairState.SCHEDULED.value

    db.commit()
    for nb in created_blocks:
        db.refresh(nb)

    active_blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day.id,
            RhythmTimeBlock.status != BlockStatus.MOVED.value,
        )
        .order_by(RhythmTimeBlock.start_time.asc(), RhythmTimeBlock.id.asc())
        .all()
    )
    logger.info(
        "[rhythm] AI timeline synced for %s (v%d): preserved=%d archived=%d created=%d",
        request.date,
        next_version,
        len(preserved_blocks),
        archived_count,
        len(created_blocks),
    )
    return AITimelineSyncResponse(
        date=request.date,
        day_id=day.id,
        plan_version=next_version,
        ai_rationale=request.rationale.strip(),
        preserved_count=len(preserved_blocks),
        archived_count=archived_count,
        created_count=len(created_blocks),
        blocks=blocks_to_response(db, active_blocks),
    )


def create_block_impl(db: Session, request: TimeBlockCreateRequest) -> TimeBlockResponse:
    if request.day_id is not None:
        day = db.query(Day).filter(Day.id == request.day_id).first()
        if day is None:
            raise RhythmNotFoundError(f"Day {request.day_id} not found")
    elif request.date is not None:
        day = _get_or_create_day(db, request.date)
    else:
        raise RhythmBadRequestError("day_id 与 date 至少提供一个")
    if request.end_time <= request.start_time:
        raise RhythmBadRequestError("end_time 必须晚于 start_time")

    block = RhythmTimeBlock(
        day_id=day.id,
        affair_id=request.affair_id,
        block_type=request.block_type.value,
        start_time=request.start_time,
        end_time=request.end_time,
        status=BlockStatus.PLANNED.value,
        pinned=request.pinned,
        plan_version=1,
        ref=dict(request.ref or {}),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    affair = (
        db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
        if block.affair_id
        else None
    )
    return block_to_response(block, affair)


def delete_block_impl(db: Session, block_id: int) -> None:
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"TimeBlock {block_id} not found")
    db.delete(block)
    db.commit()


def set_block_status_impl(
    db: Session, block_id: int, request: BlockStatusRequest
) -> TimeBlockResponse:
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"TimeBlock {block_id} not found")
    target = request.status
    if BlockStatus(block.status) == BlockStatus.MOVED:
        raise RhythmStateConflictError("MOVED 块属于旧计划版本，不可反馈")
    if BlockStatus(block.status) == target:
        affair = (
            db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
            if block.affair_id
            else None
        )
        return block_to_response(block, affair)

    block.status = target.value
    db.commit()

    affair = (
        db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
        if block.affair_id
        else None
    )
    if (
        target == BlockStatus.DONE
        and affair is not None
        and _kind_of(affair) == AffairKind.HABIT
        and block.block_type == BlockType.HABIT.value
    ):
        try:
            checkin_impl(
                db,
                CheckinRequest(
                    affair_id=affair.id,
                    result=CheckinResult.DONE,
                    log_date=block.start_time.date(),
                    source="auto",
                ),
            )
        except RhythmError as exc:
            logger.warning("[rhythm] habit auto-checkin failed: %s", exc)

    if (
        target == BlockStatus.DONE
        and affair is not None
        and _kind_of(affair) == AffairKind.TASK_MAINTENANCE
    ):
        meta = dict(affair.kind_meta or {})
        meta["last_done_at"] = _now().isoformat()
        affair.kind_meta = meta
        db.commit()

    db.refresh(block)
    return block_to_response(block, affair)


def move_block_impl(
    db: Session, block_id: int, request: BlockMoveRequest
) -> TimeBlockResponse:
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"TimeBlock {block_id} not found")
    if block.pinned:
        raise RhythmStateConflictError("pinned 块不可移动")
    if BlockStatus(block.status) == BlockStatus.MOVED:
        raise RhythmStateConflictError("MOVED 块不可移动")
    if request.end_time <= request.start_time:
        raise RhythmBadRequestError("end_time 必须晚于 start_time")
    block.start_time = request.start_time
    block.end_time = request.end_time
    db.commit()
    db.refresh(block)
    affair = (
        db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
        if block.affair_id
        else None
    )
    return block_to_response(block, affair)


def list_timeline_range_impl(
    db: Session, start_date: date, end_date: date
) -> TimelineRangeResponse:
    """批量拉取多日时间线执行情况（供 SailTick 夜间规律学习）。"""
    if end_date < start_date:
        raise RhythmBadRequestError("end_date 必须不早于 start_date")
    days = (
        db.query(Day)
        .filter(Day.date >= start_date, Day.date <= end_date)
        .order_by(Day.date.asc())
        .all()
    )
    if not days:
        return TimelineRangeResponse(start_date=start_date, end_date=end_date, days=[])

    day_ids = [d.id for d in days]
    raw_blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id.in_(day_ids),
            RhythmTimeBlock.status != BlockStatus.MOVED.value,
        )
        .order_by(RhythmTimeBlock.start_time.asc(), RhythmTimeBlock.id.asc())
        .all()
    )
    resp_blocks = blocks_to_response(db, raw_blocks)
    by_day: Dict[int, List[TimeBlockResponse]] = {}
    for b in resp_blocks:
        by_day.setdefault(b.day_id, []).append(b)

    items: List[TimelineRangeDayItem] = []
    for d_row in days:
        day_blocks = by_day.get(d_row.id, [])
        done_cnt = sum(1 for b in day_blocks if b.status == BlockStatus.DONE)
        skip_cnt = sum(1 for b in day_blocks if b.status == BlockStatus.SKIPPED)
        plan_cnt = sum(
            1 for b in day_blocks if b.status in (BlockStatus.PLANNED, BlockStatus.DOING)
        )
        comp_min = sum(
            max(0, int((b.end_time - b.start_time).total_seconds() // 60))
            for b in day_blocks
            if b.status == BlockStatus.DONE
        )
        items.append(
            TimelineRangeDayItem(
                date=d_row.date,
                blocks=day_blocks,
                done_count=done_cnt,
                skipped_count=skip_cnt,
                planned_count=plan_cnt,
                completed_minutes=comp_min,
            )
        )
    return TimelineRangeResponse(start_date=start_date, end_date=end_date, days=items)


# ============================================================================
# Unified View & Dashboard（可视化前端聚合入口）
# ============================================================================


def get_rhythm_day_view_impl(db: Session, d: date) -> RhythmDayViewResponse:
    timeline = get_day_timeline_impl(db, d, with_checkins=True)
    health_signals = (
        db.query(HealthSignal)
        .filter(HealthSignal.day_id == timeline.day_id)
        .order_by(HealthSignal.htime)
        .all()
    )
    insights = [timeline.ai_rationale] if timeline.ai_rationale else []
    return RhythmDayViewResponse(
        date=d,
        day_id=timeline.day_id,
        plan_version=timeline.plan_version,
        ai_rationale=timeline.ai_rationale,
        blocks=timeline.blocks,
        domain_minutes=timeline.domain_minutes,
        checkins=timeline.checkins,
        health_signals=[
            {
                "signal_type": s.signal_type,
                "ref_id": s.ref_id,
                "value_json": s.value_json or {},
                "htime": s.htime,
            }
            for s in health_signals
        ],
        insights=insights,
    )


def get_dashboard_impl(db: Session, d: date) -> RhythmDashboardResponse:
    """Rhythm v2 极简可视化聚合入口（时间线 + 重要项目倒排 + 焦点待办 + 占用 + 打卡）。"""
    degraded: List[str] = []

    def _safe(name: str, fn: Callable[[], Any], fallback: Any) -> Any:
        try:
            return fn()
        except Exception as exc:
            logger.warning("[rhythm] dashboard section %s degraded: %s", name, exc)
            degraded.append(name)
            return fallback

    day = _get_or_create_day(db, d)
    empty_checkins = CheckinTodayResponse(date=d)
    empty_timeline = DayTimelineResponse(date=d, day_id=day.id, checkins=empty_checkins)

    timeline = _safe("timeline", lambda: get_day_timeline_impl(db, d, with_checkins=True), empty_timeline)
    projects = _safe("projects", lambda: list_active_projects_progress_impl(db), [])
    occupancies = _safe("occupancies", lambda: list_occupancies_impl(db, d).occupancies, [])
    checkins = timeline.checkins or _safe("today_checkins", lambda: today_checkins_impl(db, d), empty_checkins)

    terminal_vals = [s.value for s in TERMINAL_STATES]
    now = _now()

    def _load_affairs() -> Tuple[List[AffairResponse], List[AffairResponse], List[AffairResponse]]:
        rows = (
            db.query(RhythmAffair)
            .filter(
                ~RhythmAffair.state.in_(terminal_vals),
                RhythmAffair.kind != AffairKind.VENTURE.value,
                RhythmAffair.parent_id.is_(None),
            )
            .order_by(RhythmAffair.urgency_ddl.asc().nullslast(), RhythmAffair.importance.desc(), RhythmAffair.id.desc())
            .limit(100)
            .all()
        )
        all_resp = [affair_to_response(r) for r in rows]
        inbox = [a for a in all_resp if a.state == AffairState.INBOX]
        overdue = [
            a
            for a in all_resp
            if a.urgency_ddl is not None and a.urgency_ddl < now and a.state != AffairState.INBOX
        ]
        focus = [
            a
            for a in all_resp
            if a.state in (AffairState.PLANNED, AffairState.SCHEDULED, AffairState.DOING, AffairState.ACTIVE)
            and a.kind not in (AffairKind.HABIT, AffairKind.PRECEPT)
        ][:20]
        return focus, overdue, inbox

    focus_affairs, overdue_affairs, inbox_affairs = _safe(
        "affairs", _load_affairs, ([], [], [])
    )

    return RhythmDashboardResponse(
        date=d,
        timeline=timeline,
        projects=projects,
        focus_affairs=focus_affairs,
        overdue_affairs=overdue_affairs,
        inbox_affairs=inbox_affairs,
        occupancies=occupancies,
        today_checkins=checkins,
        degraded=degraded,
    )
