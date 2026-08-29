# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm Model Layer (事务 CRUD + 双生命周期状态机 + 打卡 + 模板 + 事业 + 配置)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏（Rhythm）业务模型层

设计文档: doc/design/manager/rhythm.md

职责:
- Affair CRUD 与双生命周期状态机（一次性流 / 长期流）
- AI 建议（ai_hint）写回与采纳确认（含 kind 改判）
- 拆分落地（split）
- 基础节奏模板 CRUD 与命中查询
- 戒律/习惯打卡（DisciplineLog upsert 语义 + habit streak 联动）
- 长期事业（venture）里程碑与倒排进度
- 精力画像 / 守护策略 CRUD
- 时间线查询与块反馈（done/skip/move，habit 块 done 联动打卡）

排程/评分/再平衡/复盘等纯算法见 model/rhythm_planner.py。
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
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
    BlockStatus,
    BlockStatusRequest,
    BlockMoveRequest,
    CheckinRequest,
    CheckinLogResponse,
    CheckinResult,
    CheckinTodayItem,
    CheckinTodayResponse,
    ConfirmHintRequest,
    DayTemplateResponse,
    DayTemplateUpsertRequest,
    DomainMinutes,
    EnergyProfileResponse,
    EnergyProfileUpsertRequest,
    HABIT_RESULTS,
    HealthCheckinRequest,
    HealthCheckinResponse,
    InfoCollectionType,
    LONGTERM_KINDS,
    PolicyCreateRequest,
    PolicyResponse,
    PolicyUpdateRequest,
    PRECEPT_RESULTS,
    PriorityAffairItem,
    ProjectTimelineResponse,
    ReviewTimespanResponse,
    RhythmDayDashboardResponse,
    RhythmDayViewResponse,
    TERMINAL_STATES,
    TimeBlockCreateRequest,
    TimeBlockResponse,
    VentureMilestoneRequest,
    VentureProgressResponse,
    is_longterm_kind,
    resolve_transition,
    validate_kind_meta,
)
from sail_server.application.dto.health import (
    DietCreateRequest,
    EnergyLevelCreateRequest,
    MedicationCreateRequest,
    MoodCreateRequest,
    SleepCreateRequest,
)
from sail_server.infrastructure.orm.health import Exercise, HealthSignal, Medication, DietLog, Weight
from sail_server.model.health import (
    create_diet_impl,
    create_energy_level_impl,
    create_medication_impl,
    create_mood_impl,
    create_sleep_impl,
)
from sail_server.infrastructure.orm.life import Day, TimeSpan
from sail_server.infrastructure.orm.rhythm import (
    RhythmAffair,
    RhythmDayTemplate,
    RhythmDisciplineLog,
    RhythmEnergyProfile,
    RhythmPolicy,
    RhythmTimeBlock,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions（Controller 层映射为 HTTP 状态码）
# ============================================================================


class RhythmError(Exception):
    """节奏模块错误基类"""


class RhythmNotFoundError(RhythmError):
    """资源不存在 → 404"""


class RhythmStateConflictError(RhythmError):
    """状态机不允许的操作 → 409"""


class RhythmBadRequestError(RhythmError):
    """请求参数错误 → 400"""


# ============================================================================
# Internal helpers
# ============================================================================


def _now() -> datetime:
    """服务器本地 naive 时间（全链路统一口径，对齐 reminder 约定）"""
    return datetime.now()


def _today() -> date:
    return _now().date()


def week_cycle_key(d: date) -> str:
    """ISO 周周期键: W{year}-{week:02d}（如 W2026-44）"""
    iso = d.isocalendar()
    return f"W{iso[0]}-{iso[1]:02d}"


def week_range(d: date) -> tuple[date, date]:
    """d 所在周的 (周一, 周日)"""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def _kind_of(affair: RhythmAffair) -> AffairKind:
    try:
        return AffairKind(affair.kind)
    except ValueError:
        return AffairKind.GENERIC


def _get_affair_or_404(db: Session, affair_id: int) -> RhythmAffair:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        raise RhythmNotFoundError(f"Affair {affair_id} not found")
    return affair


def _get_or_create_day(db: Session, d: date) -> Day:
    """按日期取 Day 锚点；缺失时创建（days 表正常已预初始化 1999-2100）"""
    day = db.query(Day).filter(Day.date == d).first()
    if day is None:
        day = Day(date=d, ref={})
        db.add(day)
        db.commit()
        db.refresh(day)
    return day


def get_day_id_impl(db: Session, d: date) -> int:
    return _get_or_create_day(db, d).id


def _opt_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


#: confirm 时按 kind 推断默认 domain（分拣后必填，这里兜底）
_DEFAULT_DOMAIN_BY_KIND: Dict[AffairKind, AffairDomain] = {
    AffairKind.BASE_RHYTHM: AffairDomain.LIFE,
    AffairKind.PRECEPT: AffairDomain.LIFE,
    AffairKind.HABIT: AffairDomain.LIFE,
    AffairKind.FIXED_PLAN: AffairDomain.LIFE,
    AffairKind.TASK_ONEOFF: AffairDomain.WORK,
    AffairKind.TASK_MAINTENANCE: AffairDomain.WORK,
    AffairKind.VENTURE: AffairDomain.CAREER,
    AffairKind.ASYNC_CALLBACK: AffairDomain.WORK,
    AffairKind.GENERIC: AffairDomain.LIFE,
}


# ============================================================================
# DTO 转换
# ============================================================================


def affair_to_response(a: RhythmAffair) -> AffairResponse:
    return AffairResponse(
        id=a.id,
        title=a.title,
        description=a.description or "",
        domain=AffairDomain(a.domain) if a.domain else None,
        kind=_kind_of(a),
        kind_meta=a.kind_meta or {},
        state=AffairState(a.state),
        importance=a.importance or 3,
        urgency_ddl=a.urgency_ddl,
        energy_cost=a.energy_cost or 0,
        money_cost=float(a.money_cost or 0),
        budget_id=a.budget_id,
        est_minutes=a.est_minutes or 0,
        window_start=a.window_start,
        window_end=a.window_end,
        splittable=bool(a.splittable),
        min_chunk_minutes=a.min_chunk_minutes or 30,
        fallback_plan=a.fallback_plan or "",
        recurrence_rule_id=a.recurrence_rule_id,
        mission_id=a.mission_id,
        day_id=a.day_id,
        timespan_id=a.timespan_id,
        parent_id=a.parent_id,
        info_collection_type=InfoCollectionType(a.info_collection_type) if a.info_collection_type else None,
        ai_hint=a.ai_hint or {},
        score=float(a.score or 0),
        ref=a.ref or {},
        ctime=a.ctime,
        mtime=a.mtime,
    )


def block_to_response(
    b: RhythmTimeBlock, affair: Optional[RhythmAffair] = None
) -> TimeBlockResponse:
    return TimeBlockResponse(
        id=b.id,
        day_id=b.day_id,
        affair_id=b.affair_id,
        block_type=b.block_type,
        start_time=b.start_time,
        end_time=b.end_time,
        status=BlockStatus(b.status),
        pinned=bool(b.pinned),
        plan_version=b.plan_version or 1,
        ref=b.ref or {},
        affair_title=affair.title if affair else None,
        affair_kind=_kind_of(affair) if affair else None,
        energy_cost=(affair.energy_cost or 0) if affair else 0,
        ctime=b.ctime,
        mtime=b.mtime,
    )


def blocks_to_response(db: Session, blocks: List[RhythmTimeBlock]) -> List[TimeBlockResponse]:
    affair_ids = {b.affair_id for b in blocks if b.affair_id is not None}
    affairs: Dict[int, RhythmAffair] = {}
    if affair_ids:
        for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
            affairs[a.id] = a
    return [block_to_response(b, affairs.get(b.affair_id)) for b in blocks]


def _template_to_response(t: RhythmDayTemplate) -> DayTemplateResponse:
    return DayTemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description or "",
        weekday_mask=t.weekday_mask or [],
        slots=t.slots or [],
        enabled=bool(t.enabled),
        priority=t.priority or 0,
        ctime=t.ctime,
        mtime=t.mtime,
    )


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


def _profile_to_response(p: RhythmEnergyProfile) -> EnergyProfileResponse:
    return EnergyProfileResponse(
        id=p.id,
        name=p.name,
        daily_energy_budget=p.daily_energy_budget or 100,
        curve_template=p.curve_template or {},
        sleep_start=p.sleep_start or "23:30",
        sleep_end=p.sleep_end or "07:00",
        work_hours_cap=float(p.work_hours_cap or 8.0),
        spare_time_windows=p.spare_time_windows or {},
        min_buffer_ratio=float(p.min_buffer_ratio or 0.15),
        life_weight=float(p.life_weight or 1.0),
        work_weight=float(p.work_weight or 1.0),
        career_weight=float(p.career_weight or 0.6),
        score_weights=p.score_weights or {},
        updated_at=p.updated_at,
    )


def _policy_to_response(p: RhythmPolicy) -> PolicyResponse:
    return PolicyResponse(
        id=p.id,
        name=p.name,
        enabled=bool(p.enabled),
        rule_type=p.rule_type,
        params=p.params or {},
        scope=p.scope or "day",
        ctime=p.ctime,
        mtime=p.mtime,
    )


# ============================================================================
# Affair CRUD
# ============================================================================


def create_affair_impl(db: Session, request: AffairCreateRequest) -> AffairResponse:
    """快速捕获/创建事务（kind=generic 进 INBOX 等待分拣）"""
    kind = request.kind
    if kind == AffairKind.BUFFER:
        raise RhythmBadRequestError("buffer 由系统生成，禁止人工创建")
    kind_meta = validate_kind_meta(kind, request.kind_meta)

    affair = RhythmAffair(
        title=request.title,
        description=request.description,
        domain=request.domain.value if request.domain else None,
        kind=kind.value,
        kind_meta=kind_meta,
        state=AffairState.INBOX.value,
        importance=request.importance,
        urgency_ddl=request.urgency_ddl,
        energy_cost=request.energy_cost,
        money_cost=request.money_cost,
        budget_id=request.budget_id,
        est_minutes=request.est_minutes,
        window_start=request.window_start,
        window_end=request.window_end,
        splittable=request.splittable,
        min_chunk_minutes=request.min_chunk_minutes,
        fallback_plan=request.fallback_plan,
        recurrence_rule_id=request.recurrence_rule_id,
        mission_id=request.mission_id,
        day_id=request.day_id,
        timespan_id=request.timespan_id,
        parent_id=request.parent_id,
        info_collection_type=request.info_collection_type.value if request.info_collection_type else None,
        ref=request.ref or {},
    )
    db.add(affair)
    db.commit()
    db.refresh(affair)
    logger.info(f"[rhythm] affair created: #{affair.id} {affair.title} kind={kind.value}")
    return affair_to_response(affair)


def get_affair_impl(db: Session, affair_id: int) -> Optional[AffairResponse]:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    return affair_to_response(affair) if affair else None


def list_affairs_impl(
    db: Session,
    state: Optional[str] = None,
    domain: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    day_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    urgency_ddl_before: Optional[datetime] = None,
    urgency_ddl_after: Optional[datetime] = None,
    skip: int = 0,
    limit: int = -1,
) -> List[AffairResponse]:
    query = db.query(RhythmAffair)
    if state:
        query = query.filter(RhythmAffair.state == state)
    if domain:
        query = query.filter(RhythmAffair.domain == domain)
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

    old_kind = _kind_of(affair)
    # kind 改判
    if request.kind is not None:
        if affair.kind == AffairKind.BUFFER.value:
            raise RhythmBadRequestError("buffer 为系统事务，禁止改判")
        if request.kind == AffairKind.BUFFER:
            raise RhythmBadRequestError("禁止改判为 buffer（系统生成）")
        affair.kind = request.kind.value

    new_kind = _kind_of(affair)
    # kind_meta：显式传入时按（新）kind 校验；kind 改判但未传 meta 时按新 kind 重新校验旧 meta（宽松，补默认值）
    if request.kind_meta is not None:
        affair.kind_meta = validate_kind_meta(new_kind, request.kind_meta)
    elif request.kind is not None and request.kind != old_kind:
        affair.kind_meta = validate_kind_meta(new_kind, affair.kind_meta or {})

    simple_fields = [
        "title", "description", "importance", "urgency_ddl", "energy_cost",
        "money_cost", "budget_id", "est_minutes", "window_start", "window_end",
        "splittable", "min_chunk_minutes", "fallback_plan", "recurrence_rule_id",
        "mission_id", "day_id", "timespan_id", "parent_id", "ai_hint", "ref",
    ]
    if request.info_collection_type is not None:
        affair.info_collection_type = request.info_collection_type.value
    for field in simple_fields:
        value = getattr(request, field, None)
        if value is not None:
            setattr(affair, field, value)
    if request.domain is not None:
        affair.domain = request.domain.value

    db.commit()
    db.refresh(affair)
    logger.info(f"[rhythm] affair updated: #{affair.id}")
    return affair_to_response(affair)


def delete_affair_impl(db: Session, affair_id: int) -> Optional[AffairResponse]:
    affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
    if affair is None:
        return None
    if affair.kind == AffairKind.BUFFER.value:
        raise RhythmBadRequestError("buffer 为系统事务，禁止删除")
    response = affair_to_response(affair)
    db.delete(affair)
    db.commit()
    return response


# ============================================================================
# 状态机
# ============================================================================


def _compute_next_review_window(now: datetime, est_wait_hours: float, work_hours_only: bool) -> datetime:
    """计算下次 review 提醒时间：now + est_wait_hours；work_hours_only 时推到下个工作窗内。

    工作窗口径（与 profile 默认一致，简化版）：工作日 09:00-12:00, 14:00-18:00；
    非工作窗或周末 → 顺延到下个工作日 09:00。仅作提醒锚点，不与排程器耦合。
    """
    from datetime import time as _time

    candidate = now + timedelta(hours=max(est_wait_hours, 0.0))
    if not work_hours_only:
        return candidate
    # work_hours_only：顺延到工作窗
    for _ in range(14 * 24):  # 最多扫两周
        wd = candidate.weekday()
        if wd < 5:  # 周一..周五
            t = candidate.time()
            if _time(9, 0) <= t < _time(12, 0) or _time(14, 0) <= t < _time(18, 0):
                return candidate
            if t < _time(9, 0):
                return candidate.replace(hour=9, minute=0, second=0, microsecond=0)
            if _time(12, 0) <= t < _time(14, 0):
                return candidate.replace(hour=14, minute=0, second=0, microsecond=0)
            # 18:00 之后 → 次日 09:00
            candidate = (candidate + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            # 周末 → 下周一 09:00
            days_to_mon = 7 - wd
            candidate = (candidate + timedelta(days=days_to_mon)).replace(hour=9, minute=0, second=0, microsecond=0)
    return candidate


def _advance_async_callback_phase(
    db: Session, affair: RhythmAffair, action: AffairAction, request: AffairStateRequest
) -> None:
    """async_callback 阶段推进时维护 kind_meta.current_phase/round/last_*/next_review_at。

    - HANDOFF: current_phase=delegated, last_handoff_at=now, next_review_at=计算
    - RETURN_REVIEW: current_phase=review, last_return_at=now
    - REQUEST_REVISION: round+1（校验不超 max_rounds）, current_phase=kickoff→delegated 的特殊路径，
      实际 kind_meta.current_phase 设回 delegated 等待下一轮委托
    - APPROVE: current_phase=done
    - CONFIRM: current_phase=kickoff（起步）
    """
    meta = dict(affair.kind_meta or {})
    now = _now()

    if action == AffairAction.CONFIRM:
        meta["current_phase"] = "kickoff"
        meta.setdefault("round", 1)
    elif action == AffairAction.HANDOFF:
        meta["current_phase"] = "delegated"
        meta["last_handoff_at"] = now.isoformat()
        if request.est_wait_hours is not None:
            meta["est_wait_hours"] = float(request.est_wait_hours)
        wait = float(meta.get("est_wait_hours") or 24.0)
        work_only = bool(meta.get("work_hours_only", False))
        meta["next_review_at"] = _compute_next_review_window(now, wait, work_only).isoformat()
    elif action == AffairAction.RETURN_REVIEW:
        meta["current_phase"] = "review"
        meta["last_return_at"] = now.isoformat()
        meta["next_review_at"] = None
    elif action == AffairAction.REQUEST_REVISION:
        round_n = int(meta.get("round") or 1)
        max_rounds = int(meta.get("max_rounds") or 3)
        if round_n >= max_rounds:
            raise RhythmBadRequestError(
                f"已达 max_rounds={max_rounds}，不可再 REQUEST_REVISION（建议 APPROVE 接受或 CANCEL）"
            )
        meta["round"] = round_n + 1
        meta["current_phase"] = "delegated"
        meta["last_handoff_at"] = now.isoformat()
        # 记录返工原因供 AI 复盘
        if request.revision_note:
            meta.setdefault("revision_history", []).append(
                {"round": round_n, "note": request.revision_note, "at": now.isoformat()}
            )
        wait = float(meta.get("est_wait_hours") or 24.0)
        work_only = bool(meta.get("work_hours_only", False))
        meta["next_review_at"] = _compute_next_review_window(now, wait, work_only).isoformat()
    elif action == AffairAction.APPROVE:
        meta["current_phase"] = "done"
        meta["next_review_at"] = None

    affair.kind_meta = meta
    # 写入 energy_cost/est_minutes 为当前阶段值（供排程器与精力预算消费）
    phases = {p.get("name"): p for p in meta.get("phases") or [] if isinstance(p, dict)}
    cur = meta.get("current_phase")
    if cur in phases:
        cur_phase = phases[cur]
        if action in (AffairAction.CONFIRM, AffairAction.HANDOFF, AffairAction.REQUEST_REVISION):
            # 进入 kickoff 或 delegated：affair 状态后续由 transition 设 ACTIVE/DELEGATED
            # 对 kickoff 阶段排程器需读 energy_cost/est_minutes
            if cur == "kickoff":
                affair.energy_cost = int(cur_phase.get("energy_cost") or 25)
                affair.est_minutes = int(cur_phase.get("est_minutes") or 30)
            elif cur == "delegated":
                # delegated 不占实时窗，energy_cost=0
                affair.energy_cost = 0
                affair.est_minutes = 0
        elif action == AffairAction.RETURN_REVIEW and cur == "review":
            affair.energy_cost = int(cur_phase.get("energy_cost") or 15)
            affair.est_minutes = int(cur_phase.get("est_minutes") or 20)


def _pin_fixed_plan_blocks(db: Session, affair: RhythmAffair) -> None:
    """fixed_plan confirm 后立即钉入刚性块（按日切片，跨天每天一块）。

    幂等：同一 (day_id, affair_id, block_type=fixed) 已存在则跳过。
    """
    meta = affair.kind_meta or {}
    fixed_start = meta.get("fixed_start")
    fixed_end = meta.get("fixed_end")
    if not fixed_start or not fixed_end:
        raise RhythmBadRequestError(
            "fixed_plan 缺少 kind_meta.fixed_start/fixed_end，无法钉入"
        )
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
                RhythmTimeBlock.status != "MOVED",
            )
            .first()
        )
        if existing is None:
            max_version = (
                db.query(RhythmTimeBlock.plan_version)
                .filter(RhythmTimeBlock.day_id == day.id)
                .order_by(RhythmTimeBlock.plan_version.desc())
                .first()
            )
            version = (max_version[0] if max_version else 0) or 1
            db.add(
                RhythmTimeBlock(
                    day_id=day.id,
                    affair_id=affair.id,
                    block_type="fixed",
                    start_time=block_start,
                    end_time=block_end,
                    status="PLANNED",
                    pinned=True,
                    plan_version=version,
                    ref={"label": affair.title},
                )
            )
        cursor += timedelta(days=1)
    db.commit()


def transit_affair_state_impl(
    db: Session, affair_id: int, request: AffairStateRequest
) -> AffairResponse:
    """状态转移中枢（双生命周期）

    特例:
    - fixed_plan: confirm 直接 → SCHEDULED 并钉块；defer 被禁止（刚性不可推迟）
    - generic: 需先分拣改判 kind 后才允许 confirm
    - DEFERRED 必须携带 defer_to（弹性显式化）
    - graduate 仅 venture 可用
    """
    affair = _get_affair_or_404(db, affair_id)
    kind = _kind_of(affair)
    action = request.action
    current = AffairState(affair.state)

    if current in {AffairState.DONE, AffairState.CANCELED, AffairState.ARCHIVED}:
        raise RhythmStateConflictError(f"终态 {current.value} 不允许再转移")

    # fixed_plan 特例
    if kind == AffairKind.FIXED_PLAN:
        if action == AffairAction.DEFER:
            raise RhythmStateConflictError(
                "fixed_plan 为刚性规划，不可 defer（只能 cancel 或人工修改 fixed_start/end）"
            )
        if action == AffairAction.CONFIRM:
            if current != AffairState.INBOX:
                raise RhythmStateConflictError(f"当前状态 {current.value} 不允许 confirm")
            if affair.domain is None:
                affair.domain = _DEFAULT_DOMAIN_BY_KIND[kind].value
            _pin_fixed_plan_blocks(db, affair)
            affair.state = AffairState.SCHEDULED.value
            db.commit()
            db.refresh(affair)
            return affair_to_response(affair)

    # generic 需先分拣
    if kind == AffairKind.GENERIC and action in (
        AffairAction.CONFIRM,
        AffairAction.START,
        AffairAction.FINISH,
        AffairAction.DEFER,
    ):
        raise RhythmStateConflictError(
            "generic 事务需先分拣（confirm-hint 改判 kind 或 PUT 修改 kind）后再确认"
        )

    # graduate 仅 venture
    if action == AffairAction.GRADUATE and kind != AffairKind.VENTURE:
        raise RhythmBadRequestError("graduate 仅 venture 可用")

    transition = resolve_transition(kind, action)
    if transition is None:
        flow = "长期流" if is_longterm_kind(kind) else "一次性流"
        raise RhythmBadRequestError(f"{flow}不支持动作 {action.value}")

    allowed_from, target = transition
    if current not in allowed_from:
        raise RhythmStateConflictError(
            f"状态 {current.value} 不允许执行 {action.value}（允许前置: "
            f"{sorted(s.value for s in allowed_from)}）"
        )

    # defer 必须显式新窗口
    if action == AffairAction.DEFER:
        if request.defer_to is None:
            raise RhythmBadRequestError("defer 必须携带 defer_to（新窗口起点）")
        affair.window_start = request.defer_to
        # 延期同时把截止时间移到新窗口起点，避免前端仍按旧 deadline 显示逾期
        affair.urgency_ddl = request.defer_to
        if request.defer_end is not None:
            affair.window_end = request.defer_end

    # confirm 时补默认 domain
    if action == AffairAction.CONFIRM and affair.domain is None:
        affair.domain = _DEFAULT_DOMAIN_BY_KIND[kind].value

    # async_callback 阶段推进：维护 current_phase/round/last_*/next_review_at
    if kind == AffairKind.ASYNC_CALLBACK:
        _advance_async_callback_phase(db, affair, action, request)

    affair.state = target.value
    db.commit()
    db.refresh(affair)
    logger.info(f"[rhythm] affair #{affair.id} {current.value} --{action.value}--> {target.value}")
    return affair_to_response(affair)


def confirm_hint_impl(
    db: Session, affair_id: int, request: ConfirmHintRequest
) -> AffairResponse:
    """采纳/驳回 AI 建议

    采纳: 应用 ai_hint 中的 kind 改判/domain/kind_meta 草案/重要性/精力/窗口/fallback，
          overrides 可逐项覆盖；随后事务仍处 INBOX，需 confirm 生效。
    驳回: 清空 ai_hint（标记 rejected 留痕于 ref）。
    """
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
        affair.domain = _DEFAULT_DOMAIN_BY_KIND[new_kind].value
    if merged.get("kind_meta") is not None:
        affair.kind_meta = validate_kind_meta(new_kind, merged["kind_meta"])
    else:
        affair.kind_meta = validate_kind_meta(new_kind, affair.kind_meta or {})
    # 校验 AI hint 覆盖的字段范围（绕过 DTO 的 ge/le 会入库非法值）
    if merged.get("importance") is not None:
        v = int(merged["importance"])
        if not 1 <= v <= 5:
            raise RhythmBadRequestError(f"importance 越界（1-5）: {v}")
        affair.importance = v
    if merged.get("energy_cost") is not None:
        v = int(merged["energy_cost"])
        if v < 0:
            raise RhythmBadRequestError(f"energy_cost 不能为负: {v}")
        affair.energy_cost = v
    if merged.get("money_cost") is not None:
        v = float(merged["money_cost"])
        if v < 0:
            raise RhythmBadRequestError(f"money_cost 不能为负: {v}")
        affair.money_cost = v
    if merged.get("est_minutes") is not None:
        v = int(merged["est_minutes"])
        if v < 0:
            raise RhythmBadRequestError(f"est_minutes 不能为负: {v}")
        affair.est_minutes = v
    for field in ("window_start", "window_end", "urgency_ddl", "fallback_plan"):
        if merged.get(field) is not None:
            setattr(affair, field, merged[field])

    affair.ai_hint = {}
    db.commit()
    db.refresh(affair)
    logger.info(f"[rhythm] hint accepted: affair #{affair.id} → kind={new_kind.value}")
    return affair_to_response(affair)


def split_affair_impl(
    db: Session, affair_id: int, request: AffairSplitRequest
) -> AffairListResponse:
    """拆分落地（AI 建议经确认后）。子事务继承父域/种类默认值，可各自覆盖。"""
    parent = _get_affair_or_404(db, affair_id)
    if not request.children:
        raise RhythmBadRequestError("children 不能为空")

    created: List[AffairResponse] = []
    for child in request.children:
        child_kind = child.kind or _kind_of(parent)
        if child_kind == AffairKind.BUFFER:
            raise RhythmBadRequestError("禁止拆出 buffer 子事务")
        kind_meta = validate_kind_meta(child_kind, child.kind_meta)
        sub = RhythmAffair(
            title=child.title,
            description=child.description,
            domain=(child.domain.value if child.domain else parent.domain),
            kind=child_kind.value,
            kind_meta=kind_meta,
            state=AffairState.INBOX.value,
            importance=child.importance or parent.importance or 3,
            est_minutes=child.est_minutes or parent.est_minutes or 30,
            energy_cost=child.energy_cost or parent.energy_cost or 10,
            urgency_ddl=child.urgency_ddl,
            window_start=child.window_start,
            window_end=child.window_end,
            timespan_id=child.timespan_id,
            parent_id=parent.id,
        )
        db.add(sub)
        db.flush()
        created.append(affair_to_response(sub))
    db.commit()
    logger.info(f"[rhythm] affair #{parent.id} split into {len(created)} children")
    return AffairListResponse(affairs=created, total=len(created))


# ============================================================================
# DayTemplate CRUD
# ============================================================================


def upsert_template_impl(
    db: Session, request: DayTemplateUpsertRequest
) -> DayTemplateResponse:
    """按 name upsert 模板"""
    tpl = (
        db.query(RhythmDayTemplate)
        .filter(RhythmDayTemplate.name == request.name)
        .first()
    )
    slots = [s.model_dump(mode="json") for s in request.slots]
    if tpl is None:
        tpl = RhythmDayTemplate(
            name=request.name,
            description=request.description,
            weekday_mask=request.weekday_mask,
            slots=slots,
            enabled=request.enabled,
            priority=request.priority,
        )
        db.add(tpl)
    else:
        tpl.description = request.description
        tpl.weekday_mask = request.weekday_mask
        tpl.slots = slots
        tpl.enabled = request.enabled
        tpl.priority = request.priority
    db.commit()
    db.refresh(tpl)
    logger.info(f"[rhythm] template upserted: {tpl.name} (id={tpl.id})")
    return _template_to_response(tpl)


def get_template_impl(db: Session, template_id: int) -> Optional[DayTemplateResponse]:
    tpl = db.query(RhythmDayTemplate).filter(RhythmDayTemplate.id == template_id).first()
    return _template_to_response(tpl) if tpl else None


def list_templates_impl(db: Session, enabled_only: bool = False) -> List[DayTemplateResponse]:
    query = db.query(RhythmDayTemplate)
    if enabled_only:
        query = query.filter(RhythmDayTemplate.enabled.is_(True))
    return [_template_to_response(t) for t in query.order_by(RhythmDayTemplate.priority.desc()).all()]


def delete_template_impl(db: Session, template_id: int) -> Optional[DayTemplateResponse]:
    tpl = db.query(RhythmDayTemplate).filter(RhythmDayTemplate.id == template_id).first()
    if tpl is None:
        return None
    resp = _template_to_response(tpl)
    db.delete(tpl)
    db.commit()
    return resp


def get_active_template_for_date(db: Session, d: date) -> Optional[RhythmDayTemplate]:
    """查询某日命中的模板（weekday_mask 命中，多命中取 priority 高者）"""
    weekday = d.weekday()  # 周一=0
    candidates = []
    for tpl in db.query(RhythmDayTemplate).filter(RhythmDayTemplate.enabled.is_(True)).all():
        mask = tpl.weekday_mask or []
        if len(mask) == 7 and mask[weekday] == 1:
            candidates.append(tpl)
    if not candidates:
        return None
    candidates.sort(key=lambda t: t.priority or 0, reverse=True)
    return candidates[0]


def get_active_template_impl(db: Session, d: date) -> Optional[DayTemplateResponse]:
    tpl = get_active_template_for_date(db, d)
    return _template_to_response(tpl) if tpl else None


# ============================================================================
# 打卡（戒律/习惯核销）
# ============================================================================


def checkin_impl(db: Session, request: CheckinRequest) -> CheckinLogResponse:
    """打卡核销

    upsert 语义:
    - precept daily:  (affair_id, log_date) 唯一，重复打卡覆盖
    - precept weekly: (affair_id, cycle_key) 唯一
    - habit done:     每次插入（多次达成计入周次数）
    - habit missed/exempt: (affair_id, log_date) 唯一
    """
    affair = _get_affair_or_404(db, request.affair_id)
    kind = _kind_of(affair)
    if kind not in (AffairKind.PRECEPT, AffairKind.HABIT):
        raise RhythmBadRequestError(f"仅 precept/habit 可打卡（当前 kind={kind.value}）")
    if AffairState(affair.state) not in (AffairState.ACTIVE, AffairState.PAUSED):
        raise RhythmStateConflictError(f"事务状态 {affair.state} 不允许打卡")

    result = request.result
    if kind == AffairKind.PRECEPT and result not in PRECEPT_RESULTS:
        raise RhythmBadRequestError(
            f"precept 合法结果: {sorted(r.value for r in PRECEPT_RESULTS)}"
        )
    if kind == AffairKind.HABIT and result not in HABIT_RESULTS:
        raise RhythmBadRequestError(
            f"habit 合法结果: {sorted(r.value for r in HABIT_RESULTS)}"
        )

    log_date = request.log_date or _today()
    meta = affair.kind_meta or {}
    cycle = meta.get("cycle", "daily") if kind == AffairKind.PRECEPT else "weekly"
    cycle_key = week_cycle_key(log_date) if cycle == "weekly" else log_date.isoformat()

    existing = None
    if kind == AffairKind.PRECEPT:
        if cycle == "weekly":
            existing = (
                db.query(RhythmDisciplineLog)
                .filter(
                    RhythmDisciplineLog.affair_id == affair.id,
                    RhythmDisciplineLog.cycle_key == cycle_key,
                )
                .first()
            )
        else:
            existing = (
                db.query(RhythmDisciplineLog)
                .filter(
                    RhythmDisciplineLog.affair_id == affair.id,
                    RhythmDisciplineLog.log_date == log_date,
                )
                .first()
            )
    elif result in (CheckinResult.MISSED, CheckinResult.EXEMPT):
        existing = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id == affair.id,
                RhythmDisciplineLog.log_date == log_date,
            )
            .first()
        )

    if existing is not None:
        existing.result = result.value
        existing.note = request.note
        existing.source = request.source
        db.commit()
        db.refresh(existing)
        log = existing
    else:
        log = RhythmDisciplineLog(
            affair_id=affair.id,
            log_date=log_date,
            cycle_key=cycle_key,
            result=result.value,
            note=request.note,
            source=request.source,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

    # habit streak / last_done_date 联动
    if kind == AffairKind.HABIT:
        meta = dict(affair.kind_meta or {})
        if result == CheckinResult.DONE:
            meta["streak"] = int(meta.get("streak") or 0) + 1
            meta["best_streak"] = max(int(meta.get("best_streak") or 0), meta["streak"])
            meta["last_done_date"] = log_date.isoformat()
        elif result == CheckinResult.MISSED:
            meta["streak"] = 0
        affair.kind_meta = meta
        db.commit()

    logger.info(
        f"[rhythm] checkin: affair #{affair.id} result={result.value} date={log_date}"
    )
    return _log_to_response(log)


#: 健康速记 collection_type → 标题映射
_HEALTH_AFFAIRS: Dict[str, str] = {
    InfoCollectionType.WEIGHT.value: "健康速记：体重",
    InfoCollectionType.MEAL.value: "健康速记：饮食",
    InfoCollectionType.EXERCISE.value: "健康速记：运动",
    InfoCollectionType.MEDICATION.value: "健康速记：用药",
    InfoCollectionType.SLEEP.value: "健康速记：睡眠",
    InfoCollectionType.MOOD.value: "健康速记：情绪",
    InfoCollectionType.ENERGY.value: "健康速记：精力",
}


def _get_or_create_health_affair(db: Session, collection_type: str) -> RhythmAffair:
    """为每种信息收集类型维护一个长期 precept 事务，用于 rhythm 打卡日志。"""
    affair = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.PRECEPT.value,
            RhythmAffair.info_collection_type == collection_type,
        )
        .first()
    )
    if affair is None:
        affair = RhythmAffair(
            title=_HEALTH_AFFAIRS.get(collection_type, f"健康速记：{collection_type}"),
            kind=AffairKind.PRECEPT.value,
            domain=AffairDomain.LIFE.value,
            state=AffairState.ACTIVE.value,
            info_collection_type=collection_type,
            kind_meta={"cycle": "daily", "rule_text": f"记录{collection_type}"},
        )
        db.add(affair)
        db.commit()
        db.refresh(affair)
    return affair


def health_checkin_impl(db: Session, request: HealthCheckinRequest) -> HealthCheckinResponse:
    """健康速记：写入 health.* 表 + RhythmDisciplineLog（同一事务）。"""
    collection_type = request.collection_type.value
    log_date = request.log_date or _today()
    day = _get_or_create_day(db, log_date)
    now = _now()
    ref_id: Optional[int] = None

    try:
        if collection_type == InfoCollectionType.WEIGHT.value:
            value_kg = float(request.payload.get("value_kg", 0))
            measured_at_raw = request.payload.get("measured_at")
            measured_at = None
            if measured_at_raw:
                try:
                    measured_at = datetime.fromtimestamp(float(measured_at_raw))
                except (ValueError, TypeError, OSError):
                    measured_at = datetime.fromisoformat(str(measured_at_raw))
            record = Weight(
                value=str(value_kg),
                htime=measured_at or now,
                description=request.note,
            )
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
            record = Exercise(
                htime=now,
                description=request.payload.get("activity", ""),
            )
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
                from sail_server.application.dto.health import MealType
                meal_type = MealType(meal_type).value
            except ValueError:
                meal_type = "snack"
            htime = None
            if request.payload.get("htime"):
                htime = float(request.payload.get("htime"))
            diet = create_diet_impl(
                db,
                DietCreateRequest(
                    meal_type=MealType(meal_type),
                    description=str(request.payload.get("description", "")),
                    calories=_opt_float(request.payload.get("calories")),
                    carbs=_opt_float(request.payload.get("carbs")),
                    sugar=_opt_float(request.payload.get("sugar")),
                    protein=_opt_float(request.payload.get("protein")),
                    fat=_opt_float(request.payload.get("fat")),
                    fiber=_opt_float(request.payload.get("fiber")),
                    sodium=_opt_float(request.payload.get("sodium")),
                    htime=htime,
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
            planned_date = request.log_date
            if request.payload.get("planned_date"):
                planned_date = datetime.fromisoformat(str(request.payload.get("planned_date"))).date()
            htime = None
            if request.payload.get("htime"):
                htime = float(request.payload.get("htime"))
            taken_at = None
            if request.payload.get("taken_at"):
                taken_at = float(request.payload.get("taken_at"))
            medication = create_medication_impl(
                db,
                MedicationCreateRequest(
                    name=str(request.payload.get("name", "")),
                    dosage=str(request.payload.get("dosage", "")),
                    frequency=str(request.payload.get("frequency", "daily")),
                    schedule_times=list(request.payload.get("schedule_times", [])) if request.payload.get("schedule_times") else [],
                    planned_date=planned_date,
                    taken=bool(request.payload.get("taken", False)),
                    note=request.note,
                    is_supplement=bool(request.payload.get("is_supplement", False)),
                    htime=htime,
                    taken_at=taken_at,
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
            htime = None
            if request.payload.get("htime"):
                htime = float(request.payload.get("htime"))
            sleep = create_sleep_impl(
                db,
                SleepCreateRequest(
                    hours=float(request.payload.get("hours", 0)),
                    quality=int(request.payload.get("quality", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=htime,
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
            htime = None
            if request.payload.get("htime"):
                htime = float(request.payload.get("htime"))
            mood = create_mood_impl(
                db,
                MoodCreateRequest(
                    score=int(request.payload.get("score", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=htime,
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
            htime = None
            if request.payload.get("htime"):
                htime = float(request.payload.get("htime"))
            energy = create_energy_level_impl(
                db,
                EnergyLevelCreateRequest(
                    score=int(request.payload.get("score", 3)),
                    description=str(request.payload.get("description", "")),
                    day_id=day.id,
                    htime=htime,
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

        # 双写 rhythm 打卡日志
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
    except (ValueError, TypeError) as e:
        db.rollback()
        raise RhythmBadRequestError(f"健康速记数据格式错误: {e}") from e


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


def today_checkins_impl(db: Session, d: Optional[date] = None) -> CheckinTodayResponse:
    """今日待打卡清单（时间线页/打卡中心用）"""
    d = d or _today()
    weekday = d.weekday()
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
        mask = meta.get("weekday_mask") or [1] * 7
        if len(mask) == 7 and mask[weekday] != 1:
            continue
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
            cycle = meta.get("cycle", "daily")
            if cycle == "weekly" and today_log is None:
                today_log = (
                    db.query(RhythmDisciplineLog)
                    .filter(
                        RhythmDisciplineLog.affair_id == a.id,
                        RhythmDisciplineLog.cycle_key == week_cycle_key(d),
                    )
                    .order_by(RhythmDisciplineLog.id.desc())
                    .first()
                )
            precepts.append(
                CheckinTodayItem(
                    affair=affair_to_response(a),
                    done_today=today_log is not None,
                    last_result=CheckinResult(today_log.result) if today_log else None,
                )
            )
        else:
            target = int(meta.get("freq_per_week") or 3)
            habits.append(
                CheckinTodayItem(
                    affair=affair_to_response(a),
                    done_today=today_log is not None and today_log.result == "done",
                    last_result=CheckinResult(today_log.result) if today_log else None,
                    week_done_count=_habit_week_done_count(db, a.id, d),
                    week_target=target,
                )
            )
    return CheckinTodayResponse(date=d, precepts=precepts, habits=habits)


# ============================================================================
# Venture（长期事业）
# ============================================================================


def add_milestone_impl(
    db: Session, venture_id: int, request: VentureMilestoneRequest
) -> AffairResponse:
    """添加里程碑子事务（一次性流，锚定 TimeSpan/QBW）"""
    venture = _get_affair_or_404(db, venture_id)
    if _kind_of(venture) != AffairKind.VENTURE:
        raise RhythmBadRequestError("仅 venture 可添加里程碑")
    sub = RhythmAffair(
        title=request.title,
        description=request.description,
        domain=AffairDomain.CAREER.value,
        kind=AffairKind.TASK_ONEOFF.value,
        kind_meta={},
        state=AffairState.PLANNED.value,
        importance=venture.importance or 3,
        est_minutes=request.est_minutes or 60,
        energy_cost=venture.energy_cost or 10,
        urgency_ddl=request.urgency_ddl,
        timespan_id=request.timespan_id,
        parent_id=venture.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    logger.info(f"[rhythm] venture #{venture_id} milestone added: #{sub.id} {sub.title}")
    return affair_to_response(sub)


def milestone_done_impl(db: Session, milestone_id: int) -> AffairResponse:
    """勾选里程碑完成（一次性流子事务的直接核销，等价 finish 的宽松入口）"""
    milestone = _get_affair_or_404(db, milestone_id)
    if milestone.parent_id is None:
        raise RhythmBadRequestError("该事务不是里程碑（无 parent_id）")
    current = AffairState(milestone.state)
    if current in (AffairState.DONE, AffairState.CANCELED):
        raise RhythmStateConflictError(f"里程碑已是终态 {current.value}")
    milestone.state = AffairState.DONE.value
    db.commit()
    db.refresh(milestone)
    return affair_to_response(milestone)


def venture_progress_impl(db: Session, venture_id: int) -> VentureProgressResponse:
    """倒排进度: weeks_left / 周预算消耗 / 里程碑完成度 / 倒排压力"""
    venture = _get_affair_or_404(db, venture_id)
    if _kind_of(venture) != AffairKind.VENTURE:
        raise RhythmBadRequestError("仅 venture 有倒排进度")

    meta = venture.kind_meta or {}
    target_date: Optional[date] = None
    if meta.get("target_date"):
        target_date = date.fromisoformat(str(meta["target_date"])[:10])
    weekly_budget = float(meta.get("weekly_budget_hours") or 0.0)
    total_est = float(meta.get("total_est_hours") or 0.0)

    today = _today()
    weeks_left: Optional[float] = None
    if target_date is not None:
        weeks_left = max((target_date - today).days / 7.0, 0.0)

    # 本周事业块消耗（含里程碑子事务的 career 块）
    monday, sunday = week_range(today)
    child_ids = [
        x.id
        for x in db.query(RhythmAffair.id).filter(RhythmAffair.parent_id == venture.id).all()
    ]
    affair_ids = [venture.id, *child_ids]
    day_ids = [row.id for row in db.query(Day.id).filter(Day.date >= monday, Day.date <= sunday).all()]
    week_minutes = 0
    total_minutes = 0
    if day_ids:
        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.affair_id.in_(affair_ids),
                RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
            )
            .all()
        )
        week_minutes = sum(
            int((b.end_time - b.start_time).total_seconds() // 60)
            for b in blocks
            if b.day_id in day_ids
        )
        total_minutes = sum(
            int((b.end_time - b.start_time).total_seconds() // 60)
            for b in blocks
            if b.status == "DONE"
        )

    milestones = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.parent_id == venture.id)
        .order_by(RhythmAffair.id)
        .all()
    )
    done_count = sum(1 for m in milestones if m.state == AffairState.DONE.value)
    completion = (done_count / len(milestones)) if milestones else 0.0

    countdown_pressure: Optional[float] = None
    if total_est > 0 and weeks_left is not None and weekly_budget > 0:
        remaining_hours = max(total_est - total_minutes / 60.0, 0.0)
        if weeks_left <= 0:
            countdown_pressure = 999.0 if remaining_hours > 0 else 0.0
        else:
            countdown_pressure = remaining_hours / (weeks_left * weekly_budget)

    return VentureProgressResponse(
        affair_id=venture.id,
        title=venture.title,
        target_date=target_date,
        weeks_left=round(weeks_left, 2) if weeks_left is not None else None,
        weekly_budget_hours=weekly_budget,
        week_consumed_hours=round(week_minutes / 60.0, 2),
        total_done_hours=round(total_minutes / 60.0, 2),
        total_est_hours=total_est,
        countdown_pressure=(
            round(countdown_pressure, 3) if countdown_pressure is not None else None
        ),
        milestones=[affair_to_response(m) for m in milestones],
        completion_ratio=round(completion, 3),
    )


# ============================================================================
# EnergyProfile / Policy
# ============================================================================

#: 默认 24 段能量系数（0-23 时），夜间低、上午与傍晚高
_DEFAULT_WEEKDAY_CURVE = [
    0.2, 0.1, 0.1, 0.1, 0.1, 0.2,  # 0-5
    0.4, 0.7, 0.9, 0.95, 0.9, 0.8,  # 6-11
    0.6, 0.5, 0.6, 0.7, 0.75, 0.7,  # 12-17
    0.65, 0.7, 0.75, 0.6, 0.4, 0.3,  # 18-23
]
_DEFAULT_WEEKEND_CURVE = [
    0.2, 0.1, 0.1, 0.1, 0.1, 0.2,  # 0-5
    0.3, 0.5, 0.7, 0.85, 0.9, 0.85,  # 6-11
    0.7, 0.6, 0.65, 0.7, 0.7, 0.65,  # 12-17
    0.6, 0.65, 0.7, 0.6, 0.4, 0.3,  # 18-23
]

_DEFAULT_SPARE_WINDOWS = {
    "weekday": [["19:30", "22:30"]],
    "weekend": [["09:00", "12:00"], ["14:00", "18:00"]],
}

#: 默认评分权重（见 planner §5.1）
DEFAULT_SCORE_WEIGHTS = {"w_i": 0.30, "w_u": 0.30, "w_b": 0.20, "w_e": 0.15, "w_s": 0.05}


def get_or_create_profile(db: Session) -> RhythmEnergyProfile:
    profile = (
        db.query(RhythmEnergyProfile)
        .filter(RhythmEnergyProfile.name == "default")
        .first()
    )
    if profile is None:
        profile = RhythmEnergyProfile(
            name="default",
            daily_energy_budget=100,
            curve_template={
                "weekday": _DEFAULT_WEEKDAY_CURVE,
                "weekend": _DEFAULT_WEEKEND_CURVE,
            },
            sleep_start="23:30",
            sleep_end="07:00",
            work_hours_cap=8.0,
            spare_time_windows=_DEFAULT_SPARE_WINDOWS,
            min_buffer_ratio=0.15,
            life_weight=1.0,
            work_weight=1.0,
            career_weight=0.6,
            score_weights=dict(DEFAULT_SCORE_WEIGHTS),
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_energy_profile_impl(db: Session) -> EnergyProfileResponse:
    return _profile_to_response(get_or_create_profile(db))


def upsert_energy_profile_impl(
    db: Session, request: EnergyProfileUpsertRequest
) -> EnergyProfileResponse:
    profile = (
        db.query(RhythmEnergyProfile)
        .filter(RhythmEnergyProfile.name == request.name)
        .first()
    )
    if profile is None:
        profile = RhythmEnergyProfile(
            name=request.name,
            curve_template={"weekday": _DEFAULT_WEEKDAY_CURVE, "weekend": _DEFAULT_WEEKEND_CURVE},
            spare_time_windows=_DEFAULT_SPARE_WINDOWS,
            score_weights=dict(DEFAULT_SCORE_WEIGHTS),
        )
        db.add(profile)
        db.flush()

    for field in (
        "daily_energy_budget", "curve_template", "sleep_start", "sleep_end",
        "work_hours_cap", "spare_time_windows", "min_buffer_ratio",
        "life_weight", "work_weight", "career_weight", "score_weights",
    ):
        value = getattr(request, field, None)
        if value is not None:
            setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    logger.info(f"[rhythm] energy profile upserted: {profile.name}")
    return _profile_to_response(profile)


def create_policy_impl(db: Session, request: PolicyCreateRequest) -> PolicyResponse:
    policy = RhythmPolicy(
        name=request.name,
        rule_type=request.rule_type.value,
        params=request.params or {},
        scope=request.scope,
        enabled=request.enabled,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return _policy_to_response(policy)


def list_policies_impl(db: Session, enabled_only: bool = False) -> List[PolicyResponse]:
    query = db.query(RhythmPolicy)
    if enabled_only:
        query = query.filter(RhythmPolicy.enabled.is_(True))
    return [_policy_to_response(p) for p in query.order_by(RhythmPolicy.id).all()]


def update_policy_impl(
    db: Session, policy_id: int, request: PolicyUpdateRequest
) -> Optional[PolicyResponse]:
    policy = db.query(RhythmPolicy).filter(RhythmPolicy.id == policy_id).first()
    if policy is None:
        return None
    if request.name is not None:
        policy.name = request.name
    if request.rule_type is not None:
        policy.rule_type = request.rule_type.value
    if request.params is not None:
        policy.params = request.params
    if request.scope is not None:
        policy.scope = request.scope
    if request.enabled is not None:
        policy.enabled = request.enabled
    db.commit()
    db.refresh(policy)
    return _policy_to_response(policy)


def delete_policy_impl(db: Session, policy_id: int) -> Optional[PolicyResponse]:
    policy = db.query(RhythmPolicy).filter(RhythmPolicy.id == policy_id).first()
    if policy is None:
        return None
    resp = _policy_to_response(policy)
    db.delete(policy)
    db.commit()
    return resp


# ============================================================================
# TimeBlock 反馈 / 时间线
# ============================================================================


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
        status="PLANNED",
        pinned=request.pinned,
        plan_version=1,
        ref=request.ref or {},
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    affair = None
    if block.affair_id:
        affair = db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
    return block_to_response(block, affair)


def set_block_status_impl(
    db: Session, block_id: int, request: BlockStatusRequest
) -> TimeBlockResponse:
    """块反馈 done/skipped/doing；habit 块 done 自动写 DisciplineLog（source=auto）"""
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"TimeBlock {block_id} not found")
    target = request.status
    if BlockStatus(block.status) == BlockStatus.MOVED:
        raise RhythmStateConflictError("MOVED 块属于旧计划版本，不可反馈")
    # 幂等：已经是目标状态则不重复触发副作用（避免 habit streak 重复 +1）
    if BlockStatus(block.status) == target:
        db.refresh(block)
        affair = None
        if block.affair_id:
            affair = db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
        return block_to_response(block, affair)

    block.status = target.value
    db.commit()

    affair = None
    if block.affair_id:
        affair = db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()

    # habit 块 done 联动打卡
    if (
        target == BlockStatus.DONE
        and affair is not None
        and _kind_of(affair) == AffairKind.HABIT
        and block.block_type == "habit"
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
        except RhythmError as e:
            logger.warning(f"[rhythm] habit auto-checkin failed: {e}")

    # task_maintenance 块 done → 更新 last_done_at
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
    """手动拖改（pinned 块拒绝，409）"""
    block = db.query(RhythmTimeBlock).filter(RhythmTimeBlock.id == block_id).first()
    if block is None:
        raise RhythmNotFoundError(f"TimeBlock {block_id} not found")
    if block.pinned:
        raise RhythmStateConflictError("pinned 块（骨架/刚性钉）不可移动")
    if BlockStatus(block.status) == BlockStatus.MOVED:
        raise RhythmStateConflictError("MOVED 块属于旧计划版本，不可移动")
    if request.end_time <= request.start_time:
        raise RhythmBadRequestError("end_time 必须晚于 start_time")
    block.start_time = request.start_time
    block.end_time = request.end_time
    db.commit()
    db.refresh(block)
    affair = None
    if block.affair_id:
        affair = db.query(RhythmAffair).filter(RhythmAffair.id == block.affair_id).first()
    return block_to_response(block, affair)


# ============================================================================
# 合并自 PEMS 的视图/复盘/健康
# ============================================================================


def _health_signal_item(signal: HealthSignal) -> Dict[str, Any]:
    return {
        "signal_type": signal.signal_type,
        "ref_id": signal.ref_id,
        "value_json": signal.value_json or {},
        "htime": signal.htime,
    }


def get_rhythm_day_view_impl(db: Session, d: date) -> RhythmDayViewResponse:
    """统一日视图：时间线 + 能量 + 打卡 + 健康信号。"""
    from sail_server.model.rhythm_planner import get_day_timeline_impl

    timeline = get_day_timeline_impl(db, d, with_checkins=True)
    health_signals = (
        db.query(HealthSignal)
        .filter(HealthSignal.day_id == timeline.day_id)
        .order_by(HealthSignal.htime)
        .all()
    )

    energy_available = max(timeline.energy_budget - timeline.energy_consumed, 0)
    insights: List[str] = []
    if energy_available < timeline.energy_budget * 0.2:
        insights.append(f"精力余量仅 {energy_available}，注意保留缓冲。")
    if timeline.buffer_free_minutes < 30:
        insights.append("缓冲时间不足 30 分钟，谨慎接受临时任务。")

    return RhythmDayViewResponse(
        date=d,
        day_id=timeline.day_id,
        plan_version=timeline.plan_version,
        blocks=timeline.blocks,
        domain_minutes=timeline.domain_minutes,
        energy_consumed=timeline.energy_consumed,
        energy_budget=timeline.energy_budget,
        energy_available=energy_available,
        buffer_total_minutes=timeline.buffer_total_minutes,
        buffer_free_minutes=timeline.buffer_free_minutes,
        checkins=timeline.checkins,
        health_signals=[_health_signal_item(s) for s in health_signals],
        insights=insights,
        warnings=timeline.warnings,
    )


def _format_time(t: Optional[datetime]) -> str:
    if t is None:
        return ""
    return t.strftime("%H:%M")


def _build_priority_reason(a: AffairResponse, d: date) -> str:
    reasons: List[str] = []
    if a.urgency_ddl is not None and a.urgency_ddl.date() == d:
        reasons.append("今日到期")
    if (a.energy_cost or 0) > 25:
        reasons.append("建议放在精力充沛时段")
    if a.domain == AffairDomain.CAREER:
        reasons.append("业余时间推进")
    if a.state == AffairState.INBOX:
        reasons.append("待分拣确认")
    if not reasons:
        reasons.append("高优先级")
    return " / ".join(reasons)


def _suggested_slot_for(a: AffairResponse) -> Optional[str]:
    if a.window_start and a.window_end:
        return f"{_format_time(a.window_start)}-{_format_time(a.window_end)}"
    if a.window_start:
        return _format_time(a.window_start)
    return None


def get_day_dashboard_impl(db: Session, d: date) -> RhythmDayDashboardResponse:
    """统一日仪表板：时间线 + 精力 + 打卡 + 优先级事务。"""
    day_view = get_rhythm_day_view_impl(db, d)

    day = _get_or_create_day(db, d)
    terminal_values = {s.value for s in TERMINAL_STATES}
    longterm_values = {k.value for k in LONGTERM_KINDS}

    start_dt = datetime.combine(d, time.min)
    end_dt = datetime.combine(d + timedelta(days=1), time.max)

    query = db.query(RhythmAffair).filter(
        or_(
            ~RhythmAffair.state.in_(terminal_values),
            RhythmAffair.day_id == day.id,
            (RhythmAffair.urgency_ddl >= start_dt) & (RhythmAffair.urgency_ddl <= end_dt),
            RhythmAffair.kind.in_(longterm_values) & (RhythmAffair.state == AffairState.ACTIVE.value),
        )
    )
    affairs = [affair_to_response(a) for a in query.all()]

    def sort_key(a: AffairResponse) -> tuple:
        urgency = a.urgency_ddl
        return (
            -(a.score or 0),
            -(a.importance or 0),
            (0, urgency) if urgency is not None else (1, datetime.max),
        )

    affairs.sort(key=sort_key)
    priorities: List[PriorityAffairItem] = []
    for a in affairs[:10]:
        priorities.append(
            PriorityAffairItem(
                affair=a,
                reason=_build_priority_reason(a, d),
                suggested_slot=_suggested_slot_for(a),
            )
        )

    return RhythmDayDashboardResponse(
        date=d,
        day_id=day_view.day_id,
        plan_version=day_view.plan_version,
        blocks=day_view.blocks,
        domain_minutes=day_view.domain_minutes,
        energy_budget=day_view.energy_budget,
        energy_consumed=day_view.energy_consumed,
        energy_available=day_view.energy_available,
        buffer_total_minutes=day_view.buffer_total_minutes,
        buffer_free_minutes=day_view.buffer_free_minutes,
        checkins=day_view.checkins,
        priorities=priorities,
        insights=day_view.insights,
        warnings=day_view.warnings,
    )


def review_timespan_impl(db: Session, timespan_id: int) -> ReviewTimespanResponse:
    """周期复盘：基于 TimeSpan 起止日调用日复盘聚合。"""
    from sail_server.model.rhythm_planner import get_day_review_impl

    span = db.query(TimeSpan).filter(TimeSpan.id == timespan_id).first()
    if span is None:
        raise RhythmNotFoundError(f"TimeSpan {timespan_id} not found")

    start = span.start_day.date if span.start_day else None
    end = span.end_day.date if span.end_day else None
    if start is None or end is None:
        raise RhythmBadRequestError(f"TimeSpan {timespan_id} 缺少起止日期")

    # 聚合区间内每日 ReviewResponse
    domain_minutes_acc = {"life": 0, "work": 0, "career": 0}
    total_score = 0.0
    count = 0
    precept_ok = precept_total = 0
    habit_done = habit_total = 0
    sleep_kept = sleep_total = 0
    venture_done = 0.0
    venture_est = 0.0
    all_encroachments: List[Any] = []
    day = start
    while day <= end:
        review = get_day_review_impl(db, day)
        total_score += review.rhythm_score
        count += 1
        dm = review.domain_minutes or {}
        for k in domain_minutes_acc:
            domain_minutes_acc[k] += int(dm.get(k, 0) or 0)
        # 近似指标：跨日复盘没有独立的 precept/habit/sleep 计数，
        # 这里使用 rhythm_score 作为整体健康度代理
        all_encroachments.extend(review.encroachments or [])
        day += timedelta(days=1)

    profile = get_or_create_profile(db)
    avg_score = total_score / count if count > 0 else 0.0
    return ReviewTimespanResponse(
        id=None,
        scope="timespan",
        period_key=span.name or f"TS{timespan_id}",
        timespan_id=timespan_id,
        rhythm_score=round(avg_score, 2),
        domain_minutes=domain_minutes_acc,
        precept_compliance_rate=0.0,
        habit_consistency=0.0,
        sleep_window_keeping=0.0,
        venture_budget_fulfillment=0.0,
        buffer_consumed=0.0,
        encroachments=all_encroachments,
        ai_summary="",
    )
