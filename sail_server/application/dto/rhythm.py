# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm v2 Pydantic DTOs (极简项目/事务 + AI 自主排程时间线 + 占用 + 轻量打卡)
# @author sailing-innocent
# @date 2026-11-24
# @version 2.0
# ---------------------------------

"""
节奏（Rhythm v2）模块 Pydantic DTOs

设计定位：
- Rhythm 退居为“结构化项目/任务事实库 + AI 可视化日程画布”。
- 移除旧版复杂权重、精力曲线、骨架模板、守护策略与公式评分 DTO。
- 核心面向 SailTick 智能体调度与极简前端可视化：
  1. 事务/项目（Affair / Venture + 里程碑）
  2. 日可视化时间线与 AI 自主落库（`POST /timeline/ai-sync`）
  3. 特殊占用（会议/请假/出行）
  4. 轻量习惯打卡与健康速记
  5. 精简聚合 Dashboard
"""

from datetime import date as date_type
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Enums
# ============================================================================


class AffairDomain(str, Enum):
    """事务域"""

    LIFE = "life"
    WORK = "work"
    CAREER = "career"


class InfoCollectionType(str, Enum):
    """健康速记类型"""

    WEIGHT = "weight"
    MEAL = "meal"
    EXERCISE = "exercise"
    MEDICATION = "medication"
    SLEEP = "sleep"
    MOOD = "mood"
    ENERGY = "energy"


class AffairKind(str, Enum):
    """事务种类（保留常用枚举，兼容历史数据）"""

    VENTURE = "venture"  # 重要/长期项目（支持目标日倒排 + 里程碑）
    TASK_ONEOFF = "task_oneoff"  # 一次性任务
    FIXED_PLAN = "fixed_plan"  # 刚性固定安排
    HABIT = "habit"  # 周期习惯
    PRECEPT = "precept"  # 长期戒律
    TASK_MAINTENANCE = "task_maintenance"  # 周期维护
    ASYNC_CALLBACK = "async_callback"  # 异步协作等待
    BASE_RHYTHM = "base_rhythm"  # 兼容历史
    BUFFER = "buffer"  # 兼容历史
    GENERIC = "generic"  # 一句话随手记


ONEOFF_KINDS = {AffairKind.FIXED_PLAN, AffairKind.TASK_ONEOFF, AffairKind.GENERIC}
LONGTERM_KINDS = {
    AffairKind.BASE_RHYTHM,
    AffairKind.PRECEPT,
    AffairKind.HABIT,
    AffairKind.TASK_MAINTENANCE,
    AffairKind.VENTURE,
    AffairKind.ASYNC_CALLBACK,
}


class AffairState(str, Enum):
    """事务状态"""

    INBOX = "INBOX"
    PLANNED = "PLANNED"
    SCHEDULED = "SCHEDULED"
    DOING = "DOING"
    DONE = "DONE"
    DEFERRED = "DEFERRED"
    CANCELED = "CANCELED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"
    # 兼容历史 async_callback
    KICKOFF = "KICKOFF"
    DELEGATED = "DELEGATED"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"


TERMINAL_STATES = {
    AffairState.DONE,
    AffairState.CANCELED,
    AffairState.ARCHIVED,
    AffairState.COMPLETED,
}


class AffairAction(str, Enum):
    """状态转移动作"""

    CONFIRM = "confirm"
    DEFER = "defer"
    REPLAN = "replan"
    CANCEL = "cancel"
    DISMISS = "dismiss"
    START = "start"
    FINISH = "finish"
    PAUSE = "pause"
    RESUME = "resume"
    ARCHIVE = "archive"
    GRADUATE = "graduate"
    HANDOFF = "handoff"
    RETURN_REVIEW = "return_review"
    APPROVE = "approve"
    REQUEST_REVISION = "request_revision"


class BlockType(str, Enum):
    """时间线块类型"""

    SLEEP = "sleep"
    COMMUTE = "commute"
    WORK_WINDOW = "work_window"
    MICRO_REST = "micro_rest"
    MEAL = "meal"
    PRECEPT = "precept"
    HABIT = "habit"
    FIXED = "fixed"
    FOCUS = "focus"
    LIGHT = "light"
    CAREER = "career"
    REST = "rest"
    BUFFER = "buffer"
    ASYNC_KICKOFF = "async_kickoff"
    ASYNC_REVIEW = "async_review"
    ASYNC_WAIT = "async_wait"
    OCCUPIED = "occupied"


class BlockStatus(str, Enum):
    """时间块状态"""

    PLANNED = "PLANNED"
    DOING = "DOING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    MOVED = "MOVED"


class CheckinResult(str, Enum):
    """打卡结果"""

    KEPT = "kept"
    VIOLATED = "violated"
    DONE = "done"
    MISSED = "missed"
    EXEMPT = "exempt"


class OccupancyType(str, Enum):
    """占用类型"""

    LEAVE = "leave"
    MEETING = "meeting"
    APPOINTMENT = "appointment"
    TRAVEL = "travel"
    OTHER = "other"


# ============================================================================
# Helpers
# ============================================================================


def _validate_hhmm(v: str) -> str:
    parts = str(v).split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"时间格式应为 HH:MM: {v!r}")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"时间越界: {v!r}")
    return f"{h:02d}:{m:02d}"


def _to_naive_local(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.astimezone().replace(tzinfo=None)
    return v


# ============================================================================
# kind_meta 轻量规范化（宽松：允许自由扩展，只校验关键字段）
# ============================================================================


def validate_kind_meta(kind: AffairKind, meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """宽松校验 kind_meta，保留关键结构而不强加 PM 填写门槛。"""
    cleaned = dict(meta or {})
    if kind == AffairKind.VENTURE:
        if cleaned.get("target_date") is not None:
            cleaned["target_date"] = str(cleaned["target_date"])[:10]
        cleaned.setdefault("weekly_budget_hours", 0.0)
        cleaned.setdefault("total_est_hours", 0.0)
    elif kind == AffairKind.HABIT:
        cleaned.setdefault("freq_per_week", 3)
        cleaned.setdefault("min_session_minutes", 30)
    elif kind == AffairKind.PRECEPT:
        cleaned.setdefault("cycle", "daily")
        cleaned.setdefault("severity", "soft")
    elif kind == AffairKind.TASK_MAINTENANCE:
        cleaned.setdefault("interval_days", 7)
        cleaned.setdefault("session_minutes", 30)
    elif kind == AffairKind.FIXED_PLAN:
        cleaned.setdefault("immovable", True)
    return cleaned


def is_longterm_kind(kind: AffairKind) -> bool:
    return kind in LONGTERM_KINDS


# ============================================================================
# 状态机转移表（精简宽松，支持快速推进）
# ============================================================================

ONEOFF_TRANSITIONS: Dict[AffairAction, tuple[set[AffairState], AffairState]] = {
    AffairAction.CONFIRM: ({AffairState.INBOX, AffairState.DEFERRED}, AffairState.PLANNED),
    AffairAction.START: ({AffairState.INBOX, AffairState.SCHEDULED, AffairState.PLANNED, AffairState.DEFERRED}, AffairState.DOING),
    AffairAction.FINISH: ({AffairState.INBOX, AffairState.PLANNED, AffairState.SCHEDULED, AffairState.DOING, AffairState.DEFERRED}, AffairState.DONE),
    AffairAction.DEFER: ({AffairState.INBOX, AffairState.PLANNED, AffairState.SCHEDULED, AffairState.DOING}, AffairState.DEFERRED),
    AffairAction.REPLAN: ({AffairState.DEFERRED}, AffairState.PLANNED),
    AffairAction.CANCEL: ({AffairState.INBOX, AffairState.PLANNED, AffairState.SCHEDULED, AffairState.DOING, AffairState.DEFERRED}, AffairState.CANCELED),
    AffairAction.DISMISS: ({AffairState.INBOX}, AffairState.CANCELED),
}

LONGTERM_TRANSITIONS: Dict[AffairAction, tuple[set[AffairState], AffairState]] = {
    AffairAction.CONFIRM: ({AffairState.INBOX}, AffairState.ACTIVE),
    AffairAction.PAUSE: ({AffairState.ACTIVE}, AffairState.PAUSED),
    AffairAction.RESUME: ({AffairState.PAUSED, AffairState.INBOX}, AffairState.ACTIVE),
    AffairAction.ARCHIVE: ({AffairState.ACTIVE, AffairState.PAUSED, AffairState.INBOX}, AffairState.ARCHIVED),
    AffairAction.CANCEL: ({AffairState.INBOX, AffairState.ACTIVE, AffairState.PAUSED}, AffairState.CANCELED),
    AffairAction.DISMISS: ({AffairState.INBOX}, AffairState.CANCELED),
    AffairAction.GRADUATE: ({AffairState.ACTIVE, AffairState.PAUSED}, AffairState.DONE),
    AffairAction.FINISH: ({AffairState.ACTIVE, AffairState.PAUSED}, AffairState.DONE),
}


def resolve_transition(
    kind: AffairKind, action: AffairAction
) -> Optional[tuple[set[AffairState], AffairState]]:
    if is_longterm_kind(kind):
        return LONGTERM_TRANSITIONS.get(action)
    return ONEOFF_TRANSITIONS.get(action)


# ============================================================================
# Affair DTOs
# ============================================================================


class AffairCreateRequest(BaseModel):
    """创建项目/任务/习惯/随手记（极简：只需 title，可选直接进入 PLANNED/ACTIVE）。"""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    domain: Optional[AffairDomain] = Field(default=None)
    kind: AffairKind = Field(default=AffairKind.TASK_ONEOFF)
    kind_meta: Dict[str, Any] = Field(default_factory=dict)
    state: Optional[AffairState] = Field(
        default=None,
        description="初始状态；缺省时 venture/habit/precept 自动为 ACTIVE，task_oneoff 为 PLANNED，generic 为 INBOX",
    )
    importance: int = Field(default=3, ge=1, le=5)
    urgency_ddl: Optional[datetime] = None
    energy_cost: int = Field(default=10, ge=0)
    money_cost: float = Field(default=0.0, ge=0)
    budget_id: Optional[int] = None
    est_minutes: int = Field(default=30, ge=0)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    splittable: bool = False
    min_chunk_minutes: int = Field(default=30, ge=5)
    fallback_plan: str = ""
    day_id: Optional[int] = None
    timespan_id: Optional[int] = None
    parent_id: Optional[int] = None
    info_collection_type: Optional[InfoCollectionType] = None
    ref: Dict[str, Any] = Field(default_factory=dict)

    _naive_dt = field_validator("urgency_ddl", "window_start", "window_end", mode="before")(
        _to_naive_local
    )


class AffairUpdateRequest(BaseModel):
    """编辑事务（支持三态更新 + clear_* 显式清除）。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    domain: Optional[AffairDomain] = None
    kind: Optional[AffairKind] = None
    kind_meta: Optional[Dict[str, Any]] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    urgency_ddl: Optional[datetime] = None
    clear_urgency_ddl: bool = False
    energy_cost: Optional[int] = Field(default=None, ge=0)
    money_cost: Optional[float] = Field(default=None, ge=0)
    budget_id: Optional[int] = None
    est_minutes: Optional[int] = Field(default=None, ge=0)
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    clear_window: bool = False
    splittable: Optional[bool] = None
    min_chunk_minutes: Optional[int] = Field(default=None, ge=5)
    fallback_plan: Optional[str] = None
    day_id: Optional[int] = None
    timespan_id: Optional[int] = None
    parent_id: Optional[int] = None
    info_collection_type: Optional[InfoCollectionType] = None
    ai_hint: Optional[Dict[str, Any]] = None
    ref: Optional[Dict[str, Any]] = None

    _naive_dt = field_validator("urgency_ddl", "window_start", "window_end", mode="before")(
        _to_naive_local
    )


class AffairStateRequest(BaseModel):
    """状态转移请求"""

    action: AffairAction
    defer_to: Optional[datetime] = None
    defer_end: Optional[datetime] = None
    force: bool = False
    revision_note: Optional[str] = None

    _naive_dt = field_validator("defer_to", "defer_end", mode="before")(_to_naive_local)


class ConfirmHintRequest(BaseModel):
    """采纳/驳回 AI 建议"""

    accept: bool = True
    overrides: Dict[str, Any] = Field(default_factory=dict)


class AffairSplitChild(BaseModel):
    """拆分出的子事务"""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    est_minutes: int = Field(default=30, ge=5)
    energy_cost: int = Field(default=10, ge=0)
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    urgency_ddl: Optional[datetime] = None
    timespan_id: Optional[int] = None
    fallback_plan: str = ""

    _naive_dt = field_validator("urgency_ddl", mode="before")(_to_naive_local)


class AffairSplitRequest(BaseModel):
    """拆分子任务/里程碑"""

    children: List[AffairSplitChild] = Field(min_length=1)


class AffairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str = ""
    domain: Optional[AffairDomain] = None
    kind: AffairKind
    kind_meta: Dict[str, Any] = Field(default_factory=dict)
    state: AffairState
    importance: int = 3
    urgency_ddl: Optional[datetime] = None
    energy_cost: int = 10
    money_cost: float = 0.0
    budget_id: Optional[int] = None
    est_minutes: int = 30
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    splittable: bool = False
    min_chunk_minutes: int = 30
    fallback_plan: str = ""
    recurrence_rule_id: Optional[int] = None
    day_id: Optional[int] = None
    timespan_id: Optional[int] = None
    parent_id: Optional[int] = None
    info_collection_type: Optional[InfoCollectionType] = None
    ai_hint: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    ref: Dict[str, Any] = Field(default_factory=dict)
    ctime: Optional[datetime] = None
    mtime: Optional[datetime] = None


class AffairListResponse(BaseModel):
    affairs: List[AffairResponse]
    total: int


# ============================================================================
# Venture（重要项目倒排与里程碑）DTOs
# ============================================================================


class VentureMilestoneRequest(BaseModel):
    """为项目添加里程碑子任务"""

    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    timespan_id: Optional[int] = None
    urgency_ddl: Optional[datetime] = None
    est_minutes: int = Field(default=60, ge=5)

    _naive_dt = field_validator("urgency_ddl", mode="before")(_to_naive_local)


class VentureProgressResponse(BaseModel):
    """项目倒排进度"""

    affair_id: int
    title: str
    description: str = ""
    state: str = "ACTIVE"
    target_date: Optional[date_type] = None
    days_left: Optional[int] = None
    weeks_left: Optional[float] = None
    weekly_budget_hours: float = 0.0
    week_consumed_hours: float = 0.0
    recent_14d_hours: float = 0.0
    total_done_hours: float = 0.0
    total_est_hours: float = 0.0
    milestones: List[AffairResponse] = Field(default_factory=list)
    completion_ratio: float = 0.0


# ============================================================================
# Checkin & HealthCheckin DTOs
# ============================================================================


class CheckinRequest(BaseModel):
    affair_id: int
    result: CheckinResult
    log_date: Optional[date_type] = None
    note: str = ""
    source: str = "manual"


class CheckinLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    affair_id: int
    log_date: date_type
    cycle_key: str
    result: CheckinResult
    note: str = ""
    source: str = "manual"
    created_at: Optional[datetime] = None


class CheckinListResponse(BaseModel):
    logs: List[CheckinLogResponse]
    total: int


class CheckinTodayItem(BaseModel):
    affair: AffairResponse
    done_today: bool = False
    last_result: Optional[CheckinResult] = None
    week_done_count: int = 0
    week_target: Optional[int] = None


class CheckinTodayResponse(BaseModel):
    date: date_type
    precepts: List[CheckinTodayItem] = Field(default_factory=list)
    habits: List[CheckinTodayItem] = Field(default_factory=list)


class HealthCheckinRequest(BaseModel):
    """健康速记请求"""

    collection_type: InfoCollectionType
    log_date: Optional[date_type] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class HealthCheckinResponse(BaseModel):
    id: int
    collection_type: str
    log_date: date_type
    ref_id: Optional[int] = None
    affair_id: Optional[int] = None
    note: str = ""
    created_at: Optional[datetime] = None


# ============================================================================
# Occupancy DTOs（会议/请假/出行等刚性占用）
# ============================================================================


class OccupancyCreateRequest(BaseModel):
    date: date_type
    start: Optional[str] = None
    end: Optional[str] = None
    whole_day: bool = False
    occupancy_type: OccupancyType = OccupancyType.MEETING
    label: str = ""
    note: str = ""

    @field_validator("start", "end")
    @classmethod
    def _check_hhmm(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_hhmm(v)


class OccupancyResponse(BaseModel):
    id: int
    date: date_type
    start: Optional[str] = None
    end: Optional[str] = None
    whole_day: bool = False
    occupancy_type: str = "other"
    label: str = ""
    note: str = ""


class OccupancyListResponse(BaseModel):
    date: date_type
    occupancies: List[OccupancyResponse] = Field(default_factory=list)


# ============================================================================
# Timeline & AI Sync DTOs（可视化日程画布核心）
# ============================================================================


class DomainMinutes(BaseModel):
    life: int = 0
    work: int = 0
    career: int = 0


class TimeBlockCreateRequest(BaseModel):
    day_id: Optional[int] = None
    date: Optional[date_type] = None
    affair_id: Optional[int] = None
    block_type: BlockType = BlockType.FOCUS
    start_time: datetime
    end_time: datetime
    pinned: bool = False
    ref: Dict[str, Any] = Field(default_factory=dict)

    _naive_dt = field_validator("start_time", "end_time", mode="before")(_to_naive_local)


class TimeBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_id: int
    affair_id: Optional[int] = None
    affair_title: Optional[str] = None
    affair_kind: Optional[AffairKind] = None
    affair_domain: Optional[AffairDomain] = None
    block_type: BlockType
    start_time: datetime
    end_time: datetime
    status: BlockStatus
    pinned: bool = False
    plan_version: int = 1
    ref: Dict[str, Any] = Field(default_factory=dict)


class BlockStatusRequest(BaseModel):
    status: BlockStatus


class BlockMoveRequest(BaseModel):
    start_time: datetime
    end_time: datetime

    _naive_dt = field_validator("start_time", "end_time", mode="before")(_to_naive_local)


_AI_BLOCK_TYPE_ALIASES: Dict[str, BlockType] = {
    "routine": BlockType.HABIT,
    "daily": BlockType.HABIT,
    "daily_routine": BlockType.HABIT,
    "exercise": BlockType.HABIT,
    "workout": BlockType.HABIT,
    "walk": BlockType.HABIT,
    "sport": BlockType.HABIT,
    "health": BlockType.HABIT,
    "dining": BlockType.MEAL,
    "food": BlockType.MEAL,
    "lunch": BlockType.MEAL,
    "dinner": BlockType.MEAL,
    "breakfast": BlockType.MEAL,
    "eat": BlockType.MEAL,
    "work": BlockType.WORK_WINDOW,
    "deep_work": BlockType.FOCUS,
    "study": BlockType.FOCUS,
    "learning": BlockType.FOCUS,
    "project": BlockType.FOCUS,
    "break": BlockType.MICRO_REST,
    "nap": BlockType.REST,
    "relax": BlockType.REST,
    "wind_down": BlockType.REST,
    "bedtime": BlockType.SLEEP,
    "meeting": BlockType.OCCUPIED,
    "travel": BlockType.OCCUPIED,
    "event": BlockType.FIXED,
    "chore": BlockType.LIGHT,
    "errand": BlockType.LIGHT,
    "admin": BlockType.LIGHT,
    "flex": BlockType.BUFFER,
    "flexible": BlockType.BUFFER,
    "free": BlockType.BUFFER,
}


class AITimelineBlockInput(BaseModel):
    """SailTick AI 编排输出的单个时间块。"""

    title: str = Field(min_length=1, max_length=200, description="展示标题")
    start: str = Field(description="开始时间 HH:MM 或 ISO datetime")
    end: str = Field(description="结束时间 HH:MM 或 ISO datetime")
    block_type: BlockType = Field(default=BlockType.FOCUS, description="块类型")
    affair_id: Optional[int] = Field(default=None, description="关联的事务/项目 ID（可选）")
    pinned: bool = Field(default=False, description="是否刚性固定")
    note: str = Field(default="", description="一句轻量提示/备用方案")

    @field_validator("block_type", mode="before")
    @classmethod
    def _coerce_ai_block_type(cls, v: Any) -> BlockType:
        if isinstance(v, BlockType):
            return v
        if v is None:
            return BlockType.FOCUS
        norm = str(v).strip().lower().replace("-", "_").replace(" ", "_")
        if not norm:
            return BlockType.FOCUS
        try:
            return BlockType(norm)
        except ValueError:
            return _AI_BLOCK_TYPE_ALIASES.get(norm, BlockType.LIGHT)


class AITimelineSyncRequest(BaseModel):
    """SailTick AI 自主编排某日时间线并直接落库（保留已完成与刚性钉）。"""

    date: date_type = Field(description="目标日期 YYYY-MM-DD")
    blocks: List[AITimelineBlockInput] = Field(default_factory=list, description="AI 编排的时间块列表")
    rationale: str = Field(default="", description="AI 对今日编排逻辑的简短温和说明")
    preserve_done: bool = Field(default=True, description="保留 DONE/DOING 块")
    preserve_pinned: bool = Field(default=True, description="保留 pinned 块（会议/刚性行程/占用）")
    source: str = Field(default="sailtick", description="编排来源标识")


class DayTimelineResponse(BaseModel):
    """某日可视化时间线"""

    date: date_type
    day_id: int
    plan_version: int = 0
    ai_rationale: str = ""
    ai_updated_at: Optional[datetime] = None
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    completed_minutes: int = 0
    planned_minutes: int = 0
    domain_minutes: DomainMinutes = Field(default_factory=DomainMinutes)
    checkins: Optional[CheckinTodayResponse] = None


class AITimelineSyncResponse(BaseModel):
    """AI 编排落库结果"""

    date: date_type
    day_id: int
    plan_version: int
    ai_rationale: str = ""
    preserved_count: int = 0
    archived_count: int = 0
    created_count: int = 0
    blocks: List[TimeBlockResponse] = Field(default_factory=list)


class TimelineRangeDayItem(BaseModel):
    """时间线范围统计中的单日执行记录（供 SailTick 夜间规律学习）。"""

    date: date_type
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    done_count: int = 0
    skipped_count: int = 0
    planned_count: int = 0
    completed_minutes: int = 0


class TimelineRangeResponse(BaseModel):
    """多日时间线执行历史（供 SailTick 夜间深度分析）。"""

    start_date: date_type
    end_date: date_type
    days: List[TimelineRangeDayItem] = Field(default_factory=list)


# ============================================================================
# Unified View & Dashboard DTOs
# ============================================================================


class RhythmDayViewResponse(BaseModel):
    """轻量日视图（兼容首页与 Android 端）。"""

    date: date_type
    day_id: int
    plan_version: int = 0
    ai_rationale: str = ""
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    domain_minutes: DomainMinutes = Field(default_factory=DomainMinutes)
    checkins: Optional[CheckinTodayResponse] = None
    health_signals: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)


class RhythmDashboardResponse(BaseModel):
    """Rhythm v2 极简可视化聚合入口（时间线 + 重要项目倒排 + 焦点待办 + 占用 + 打卡）。"""

    date: date_type
    timeline: DayTimelineResponse
    projects: List[VentureProgressResponse] = Field(default_factory=list)
    focus_affairs: List[AffairResponse] = Field(default_factory=list)
    overdue_affairs: List[AffairResponse] = Field(default_factory=list)
    inbox_affairs: List[AffairResponse] = Field(default_factory=list)
    occupancies: List[OccupancyResponse] = Field(default_factory=list)
    today_checkins: CheckinTodayResponse
    degraded: List[str] = Field(default_factory=list)
