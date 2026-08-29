# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm Pydantic DTOs (事务分类学 + 双生命周期状态机 + 全部请求/响应)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏（Rhythm）模块 Pydantic DTOs

设计文档: doc/design/manager/rhythm.md

核心内容:
- 枚举: AffairDomain / AffairKind(9类) / AffairState / BlockType(12类) /
        BlockStatus / PolicyRuleType / CheckinResult
- kind_meta 分类型校验器: 每个 kind 一个 pydantic 子模型，写入时按 kind 分发校验
- 双生命周期状态机: 一次性流 / 长期流 两套合法转移表
- 全部端点的请求/响应 DTO
"""

from datetime import date as date_type
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================================
# Enums
# ============================================================================


class AffairDomain(str, Enum):
    """事务域（三域平衡计量）"""

    LIFE = "life"
    WORK = "work"
    CAREER = "career"


class InfoCollectionType(str, Enum):
    """信息收集类型（健康速记等跨 kind 场景）"""

    WEIGHT = "weight"
    MEAL = "meal"
    EXERCISE = "exercise"
    MEDICATION = "medication"
    SLEEP = "sleep"
    MOOD = "mood"
    ENERGY = "energy"


class AffairKind(str, Enum):
    """事务种类（10 类，决定生命周期形态/排程行为/元数据 schema/复盘指标）"""

    BASE_RHYTHM = "base_rhythm"  # 基础节奏（每日骨架，由模板实例化）
    PRECEPT = "precept"  # 戒律（按日/按周规则，打卡核销）
    HABIT = "habit"  # 习惯养成（频率目标制）
    FIXED_PLAN = "fixed_plan"  # 刚性规划（不可移动钉）
    TASK_ONEOFF = "task_oneoff"  # 一次性工作任务
    TASK_MAINTENANCE = "task_maintenance"  # 长期维护任务（SLA 周期制）
    VENTURE = "venture"  # 长期事业（目标日倒排，仅业余时间区）
    ASYNC_CALLBACK = "async_callback"  # 异步回调（多阶段：构思→委托→审阅→返工）
    BUFFER = "buffer"  # 系统缓冲（只读）
    GENERIC = "generic"  # 未分类（捕获默认，待 AI 分拣 + 人确认）


#: 一次性流 kind（fixed_plan / task_oneoff / generic / venture 里程碑子项）
ONEOFF_KINDS = {AffairKind.FIXED_PLAN, AffairKind.TASK_ONEOFF, AffairKind.GENERIC}
#: 长期流 kind（持续生成 occurrence，不产生 DONE；venture 可毕业，async_callback 走独立阶段机）
LONGTERM_KINDS = {
    AffairKind.BASE_RHYTHM,
    AffairKind.PRECEPT,
    AffairKind.HABIT,
    AffairKind.TASK_MAINTENANCE,
    AffairKind.VENTURE,
    AffairKind.ASYNC_CALLBACK,
}


class AffairState(str, Enum):
    """事务状态（双生命周期 + async_callback 阶段机）"""

    INBOX = "INBOX"
    PLANNED = "PLANNED"
    SCHEDULED = "SCHEDULED"
    DOING = "DOING"
    DONE = "DONE"  # 终态
    DEFERRED = "DEFERRED"
    CANCELED = "CANCELED"  # 终态
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ARCHIVED = "ARCHIVED"  # 终态
    # async_callback 专属阶段状态（长期流子集，ACTIVE 时进入 KICKOFF）
    KICKOFF = "KICKOFF"
    DELEGATED = "DELEGATED"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"  # async_callback 终态


#: 终态集合
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
    # async_callback 阶段推进动作
    HANDOFF = "handoff"  # KICKOFF → DELEGATED（委托交付）
    RETURN_REVIEW = "return_review"  # DELEGATED → REVIEWING（结果返回待审）
    APPROVE = "approve"  # REVIEWING → COMPLETED（采纳结果）
    REQUEST_REVISION = "request_revision"  # REVIEWING → DELEGATED（不满意，启下一轮）


class BlockType(str, Enum):
    """时间线块类型（13 类）"""

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
    # async_callback 专用块
    ASYNC_KICKOFF = "async_kickoff"  # 构思/沟通阶段块（占实时窗，进 work_window 或业余区）
    ASYNC_REVIEW = "async_review"  # 审阅阶段块（占实时窗）
    ASYNC_WAIT = "async_wait"  # DELEGATED 等待期提示块（informational，0 精力，不占实时窗）


class BlockStatus(str, Enum):
    """时间线块状态"""

    PLANNED = "PLANNED"
    DOING = "DOING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    MOVED = "MOVED"


class PolicyRuleType(str, Enum):
    """守护策略规则类型"""

    PROTECT_WINDOW = "protect_window"  # 时间窗禁排
    DOMAIN_CAP = "domain_cap"  # 域时长上限
    KIND_MIN_FREQ = "kind_min_freq"  # 种类周下限
    MAX_CONSECUTIVE_FOCUS = "max_consecutive_focus"  # 连续专注上限
    SPARE_TIME_GUARD = "spare_time_guard"  # 事业仅占业余时间区


class CheckinResult(str, Enum):
    """打卡结果（precept: kept/violated/exempt; habit: done/missed/exempt）"""

    KEPT = "kept"
    VIOLATED = "violated"
    DONE = "done"
    MISSED = "missed"
    EXEMPT = "exempt"


#: precept 合法打卡结果
PRECEPT_RESULTS = {CheckinResult.KEPT, CheckinResult.VIOLATED, CheckinResult.EXEMPT}
#: habit 合法打卡结果
HABIT_RESULTS = {CheckinResult.DONE, CheckinResult.MISSED, CheckinResult.EXEMPT}


# ============================================================================
# kind_meta 分类型元数据（写入时按 kind 分发校验）
# ============================================================================


class BaseRhythmMeta(BaseModel):
    """base_rhythm 元数据：引用骨架模板"""

    template_id: Optional[int] = Field(default=None, description="引用 rhythm_day_templates.id")


class PreceptMeta(BaseModel):
    """precept 戒律元数据"""

    rule_text: str = Field(default="", description="戒律描述，如 '23:30前入睡'")
    cycle: str = Field(default="daily", description="daily | weekly")
    weekday_mask: List[int] = Field(
        default_factory=lambda: [1, 1, 1, 1, 1, 1, 1],
        description="适用星期（周一为索引 0）",
    )
    check_time: str = Field(default="22:30", description="核销提醒时间 HH:MM")
    severity: str = Field(default="soft", description="hard（参与铺底）| soft")
    block_minutes: int = Field(default=0, description="打卡块时长（0=仅核销提醒）")


class HabitMeta(BaseModel):
    """habit 习惯元数据"""

    freq_per_week: int = Field(default=3, description="每周目标次数")
    min_session_minutes: int = Field(default=30, description="单次最小时长（分钟）")
    preferred_slots: List[str] = Field(
        default_factory=list, description="偏好时段，如 ['19:00-21:00']"
    )
    streak: int = Field(default=0, description="当前连续达成（周）")
    best_streak: int = Field(default=0, description="最佳连续")
    last_done_date: Optional[str] = Field(default=None, description="最近完成日 ISO 日期")


class MaintenanceMeta(BaseModel):
    """task_maintenance 维护任务元数据（SLA 周期制）"""

    interval_days: int = Field(default=7, description="维护周期（天）")
    last_done_at: Optional[datetime] = Field(default=None, description="上次完成时间")
    session_minutes: int = Field(default=60, description="单次时长（分钟）")


class VentureMeta(BaseModel):
    """venture 长期事业元数据（目标日倒排）"""

    target_date: Optional[date_type] = Field(default=None, description="目标日")
    weekly_budget_hours: float = Field(default=8.0, description="每周业余小时预算")
    spare_time_only: bool = Field(default=True, description="仅排业余时间区")
    total_est_hours: float = Field(default=0.0, description="总预估工时（倒排压力用）")


class FixedPlanMeta(BaseModel):
    """fixed_plan 刚性规划元数据"""

    immovable: bool = Field(default=True, description="不可移动")
    fixed_start: Optional[datetime] = Field(default=None, description="固定开始")
    fixed_end: Optional[datetime] = Field(default=None, description="固定结束")
    legs: List[int] = Field(default_factory=list, description="子事务（行程段）ID 列表")


class AsyncCallbackPhase(BaseModel):
    """async_callback 单阶段预算（精力点数粗刻度见 §4.2）"""

    name: str = Field(description="阶段名 kickoff/delegated/review")
    est_minutes: int = Field(default=30, ge=0, description="单次实时窗时长")
    energy_cost: int = Field(default=10, ge=0, description="单次精力点数")


class AsyncCallbackMeta(BaseModel):
    """async_callback 异步回调元数据

    生命周期: INBOX→ACTIVE(=KICKOFF)→DELEGATED→REVIEWING→COMPLETED，
    REVIEWING 可 REQUEST_REVISION 回 DELEGATED（round+1），最多 max_rounds 轮。
    work_hours_only=true 时 kickoff/review 块只进 work_window（如需对接他人/外部系统）。
    """

    phases: List[AsyncCallbackPhase] = Field(
        default_factory=lambda: [
            AsyncCallbackPhase(name="kickoff", est_minutes=30, energy_cost=25),
            AsyncCallbackPhase(name="delegated", est_minutes=0, energy_cost=0),
            AsyncCallbackPhase(name="review", est_minutes=20, energy_cost=15),
        ],
        description="阶段定义（kickoff/delegated/review 三段）",
    )
    current_phase: str = Field(default="kickoff", description="当前阶段名")
    round: int = Field(default=1, ge=1, description="当前轮次（1 起，不满意 +1）")
    max_rounds: int = Field(default=3, ge=1, description="最大轮次上限")
    work_hours_only: bool = Field(
        default=False,
        description="true 时 kickoff/review 仅排 work_window（如对外业务回调，需上班时间进行）",
    )
    delegate_to: str = Field(default="ai", description="委托对象 ai|human:xxx|system:yyy")
    est_wait_hours: float = Field(
        default=24.0, ge=0, description="DELEGATED 阶段预期等待时长（小时，到点提醒去 review）"
    )
    last_handoff_at: Optional[datetime] = Field(default=None, description="最近一次 HANDOFF 时间")
    last_return_at: Optional[datetime] = Field(default=None, description="最近一次 RETURN_REVIEW 时间")
    next_review_at: Optional[datetime] = Field(
        default=None, description="下次 review 提醒时间（HANDOFF 时计算：now+est_wait_hours，work_hours_only 推到下个工作窗）"
    )


#: kind → kind_meta 校验模型 分发表
KIND_META_MODELS: Dict[AffairKind, type[BaseModel]] = {
    AffairKind.BASE_RHYTHM: BaseRhythmMeta,
    AffairKind.PRECEPT: PreceptMeta,
    AffairKind.HABIT: HabitMeta,
    AffairKind.TASK_MAINTENANCE: MaintenanceMeta,
    AffairKind.VENTURE: VentureMeta,
    AffairKind.FIXED_PLAN: FixedPlanMeta,
    AffairKind.ASYNC_CALLBACK: AsyncCallbackMeta,
}


def validate_kind_meta(kind: AffairKind, meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """按 kind 校验并规范化 kind_meta。

    M1 宽松校验：缺字段给默认值；类型错误抛 ValueError（controller 映射 400）。
    task_oneoff / generic / buffer 无额外约束，原样返回（默认 {}）。
    """
    meta = dict(meta or {})
    model = KIND_META_MODELS.get(kind)
    if model is None:
        return meta
    try:
        validated = model(**meta)
    except Exception as e:
        raise ValueError(f"kind_meta 校验失败 (kind={kind.value}): {e}") from e
    return validated.model_dump(mode="json")


# ============================================================================
# 双生命周期状态机
# ============================================================================

#: 一次性流合法转移: action → (允许的前置状态集合, 目标状态)
ONEOFF_TRANSITIONS: Dict[AffairAction, tuple[set[AffairState], AffairState]] = {
    AffairAction.CONFIRM: ({AffairState.INBOX, AffairState.DEFERRED}, AffairState.PLANNED),
    AffairAction.START: ({AffairState.SCHEDULED, AffairState.PLANNED}, AffairState.DOING),
    AffairAction.FINISH: ({AffairState.DOING, AffairState.SCHEDULED}, AffairState.DONE),
    AffairAction.DEFER: (
        {AffairState.PLANNED, AffairState.SCHEDULED},
        AffairState.DEFERRED,
    ),
    AffairAction.REPLAN: ({AffairState.DEFERRED}, AffairState.PLANNED),
    AffairAction.CANCEL: (
        {AffairState.INBOX, AffairState.PLANNED, AffairState.SCHEDULED, AffairState.DEFERRED},
        AffairState.CANCELED,
    ),
    AffairAction.DISMISS: ({AffairState.INBOX}, AffairState.CANCELED),
}

#: 长期流合法转移
LONGTERM_TRANSITIONS: Dict[AffairAction, tuple[set[AffairState], AffairState]] = {
    AffairAction.CONFIRM: ({AffairState.INBOX}, AffairState.ACTIVE),
    AffairAction.PAUSE: ({AffairState.ACTIVE}, AffairState.PAUSED),
    AffairAction.RESUME: ({AffairState.PAUSED}, AffairState.ACTIVE),
    AffairAction.ARCHIVE: (
        {AffairState.ACTIVE, AffairState.PAUSED},
        AffairState.ARCHIVED,
    ),
    AffairAction.CANCEL: ({AffairState.INBOX}, AffairState.CANCELED),
    AffairAction.DISMISS: ({AffairState.INBOX}, AffairState.CANCELED),
    # venture 限定：达成目标毕业（model 层校验 kind==venture）
    AffairAction.GRADUATE: ({AffairState.ACTIVE}, AffairState.DONE),
}

#: async_callback 阶段状态机（长期流子集，CONFIRM→ACTIVE=KICKOFF 起步）。
#: REVIEWING → REQUEST_REVISION → DELEGATED 时 round+1，max_rounds 上限由 model 层校验。
ASYNC_CALLBACK_TRANSITIONS: Dict[AffairAction, tuple[set[AffairState], AffairState]] = {
    AffairAction.CONFIRM: ({AffairState.INBOX}, AffairState.ACTIVE),
    # ACTIVE 即 KICKOFF 阶段：HANDOFF 进入委托等待
    AffairAction.HANDOFF: ({AffairState.ACTIVE, AffairState.KICKOFF}, AffairState.DELEGATED),
    # DELEGATED 等待期结束、结果返回 → 进入审阅
    AffairAction.RETURN_REVIEW: ({AffairState.DELEGATED}, AffairState.REVIEWING),
    # REVIEWING 满意 → 完成
    AffairAction.APPROVE: ({AffairState.REVIEWING}, AffairState.COMPLETED),
    # REVIEWING 不满意 → 返工回 DELEGATED（round+1，model 层校验不超 max_rounds）
    AffairAction.REQUEST_REVISION: ({AffairState.REVIEWING}, AffairState.DELEGATED),
    # 通用长期流动作（兼容）
    AffairAction.PAUSE: (
        {AffairState.ACTIVE, AffairState.DELEGATED, AffairState.REVIEWING},
        AffairState.PAUSED,
    ),
    AffairAction.RESUME: ({AffairState.PAUSED}, AffairState.ACTIVE),
    AffairAction.ARCHIVE: (
        {AffairState.ACTIVE, AffairState.PAUSED, AffairState.DELEGATED, AffairState.REVIEWING},
        AffairState.ARCHIVED,
    ),
    AffairAction.CANCEL: ({AffairState.INBOX}, AffairState.CANCELED),
    AffairAction.DISMISS: ({AffairState.INBOX}, AffairState.CANCELED),
}


def is_longterm_kind(kind: AffairKind) -> bool:
    return kind in LONGTERM_KINDS


def resolve_transition(
    kind: AffairKind, action: AffairAction
) -> Optional[tuple[set[AffairState], AffairState]]:
    """按 kind 生命周期形态解析 action 对应的 (前置状态集, 目标状态)。

    async_callback 走独立阶段机（KICKOFF/DELEGATED/REVIEWING/COMPLETED）；
    其余长期流走通用 LONGTERM_TRANSITIONS。
    """
    if kind == AffairKind.ASYNC_CALLBACK:
        return ASYNC_CALLBACK_TRANSITIONS.get(action)
    if is_longterm_kind(kind):
        return LONGTERM_TRANSITIONS.get(action)
    return ONEOFF_TRANSITIONS.get(action)


# ============================================================================
# Affair DTOs
# ============================================================================


class AffairCreateRequest(BaseModel):
    """快速捕获/创建事务（仅 title 必填，kind 默认 generic 进 INBOX）"""

    title: str = Field(description="标题（捕获时唯一必填）")
    description: str = Field(default="", description="详情")
    domain: Optional[AffairDomain] = Field(default=None, description="域 life/work/career")
    kind: AffairKind = Field(default=AffairKind.GENERIC, description="事务种类")
    kind_meta: Dict[str, Any] = Field(default_factory=dict, description="分类型元数据")
    importance: int = Field(default=3, ge=1, le=5, description="重要性 1-5")
    urgency_ddl: Optional[datetime] = Field(default=None, description="截止时间")
    energy_cost: int = Field(default=10, ge=0, description="单次预估精力点数")
    money_cost: float = Field(default=0.0, ge=0, description="预估花费")
    budget_id: Optional[int] = Field(default=None, description="关联 finance 预算")
    est_minutes: int = Field(default=30, ge=0, description="单次预估时长（分钟）")
    window_start: Optional[datetime] = Field(default=None, description="弹性窗口开始")
    window_end: Optional[datetime] = Field(default=None, description="弹性窗口结束")
    splittable: bool = Field(default=False, description="是否可拆分")
    min_chunk_minutes: int = Field(default=30, ge=0, description="最小连续块（分钟）")
    fallback_plan: str = Field(default="", description="备用方案（Plan B）")
    recurrence_rule_id: Optional[int] = Field(default=None, description="关联 reminder 规则")
    day_id: Optional[int] = Field(default=None, description="目标日锚点（life.days）")
    timespan_id: Optional[int] = Field(default=None, description="目标 TimeSpan")
    parent_id: Optional[int] = Field(default=None, description="父事务（拆分树/里程碑链）")
    info_collection_type: Optional[InfoCollectionType] = Field(
        default=None, description="信息收集类型（健康速记）"
    )
    ref: Dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class AffairUpdateRequest(BaseModel):
    """编辑事务（含 kind 改判 + kind_meta 校验 + ai_hint 更新）"""

    title: Optional[str] = Field(default=None, description="标题")
    description: Optional[str] = Field(default=None, description="详情")
    domain: Optional[AffairDomain] = Field(default=None, description="域")
    kind: Optional[AffairKind] = Field(default=None, description="kind 改判")
    kind_meta: Optional[Dict[str, Any]] = Field(default=None, description="分类型元数据")
    importance: Optional[int] = Field(default=None, ge=1, le=5, description="重要性")
    urgency_ddl: Optional[datetime] = Field(default=None, description="截止时间")
    energy_cost: Optional[int] = Field(default=None, ge=0, description="精力点数")
    money_cost: Optional[float] = Field(default=None, ge=0, description="预估花费")
    budget_id: Optional[int] = Field(default=None, description="关联预算")
    est_minutes: Optional[int] = Field(default=None, ge=0, description="预估时长")
    window_start: Optional[datetime] = Field(default=None, description="弹性窗口开始")
    window_end: Optional[datetime] = Field(default=None, description="弹性窗口结束")
    splittable: Optional[bool] = Field(default=None, description="是否可拆分")
    min_chunk_minutes: Optional[int] = Field(default=None, ge=0, description="最小连续块")
    fallback_plan: Optional[str] = Field(default=None, description="备用方案")
    recurrence_rule_id: Optional[int] = Field(default=None, description="关联 reminder 规则")
    day_id: Optional[int] = Field(default=None, description="目标日锚点")
    timespan_id: Optional[int] = Field(default=None, description="目标 TimeSpan")
    parent_id: Optional[int] = Field(default=None, description="父事务")
    info_collection_type: Optional[InfoCollectionType] = Field(
        default=None, description="信息收集类型（健康速记）"
    )
    ai_hint: Optional[Dict[str, Any]] = Field(default=None, description="AI 建议快照")
    ref: Optional[Dict[str, Any]] = Field(default=None, description="扩展字段")


class AffairResponse(BaseModel):
    """事务响应"""

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


class AffairStateRequest(BaseModel):
    """状态转移请求"""

    action: AffairAction = Field(description="转移动作")
    defer_to: Optional[datetime] = Field(
        default=None, description="defer 的新窗口起点（defer 必填）"
    )
    defer_end: Optional[datetime] = Field(default=None, description="defer 的新窗口终点")
    force: bool = Field(default=False, description="人工强制（如预算不足仍钉入）")
    # async_callback 阶段参数
    handoff_now: bool = Field(
        default=True,
        description="HANDOFF 时是否立即推进 DELEGATED（false 仅写元数据，等排程触发）",
    )
    revision_note: str = Field(
        default="", description="REQUEST_REVISION 时的不满意说明（写入 kind_meta.ref）"
    )
    est_wait_hours: Optional[float] = Field(
        default=None,
        ge=0,
        description="HANDOFF 时覆盖 kind_meta.est_wait_hours（本次预期等待时长）",
    )


class ConfirmHintRequest(BaseModel):
    """采纳/驳回 AI 建议"""

    accept: bool = Field(description="采纳 true / 驳回 false")
    overrides: Optional[Dict[str, Any]] = Field(
        default=None, description="采纳时的覆盖字段（含 kind/kind_meta 改判确认）"
    )


class AffairSplitChild(BaseModel):
    """拆分子事务"""

    title: str
    kind: Optional[AffairKind] = None
    domain: Optional[AffairDomain] = None
    kind_meta: Dict[str, Any] = Field(default_factory=dict)
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    est_minutes: Optional[int] = Field(default=None, ge=0)
    energy_cost: Optional[int] = Field(default=None, ge=0)
    urgency_ddl: Optional[datetime] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    timespan_id: Optional[int] = None
    description: str = ""


class AffairSplitRequest(BaseModel):
    """拆分请求（AI 建议经确认后落地）"""

    children: List[AffairSplitChild] = Field(description="子事务数组")


# ============================================================================
# DayTemplate DTOs
# ============================================================================


class TemplateSlot(BaseModel):
    """骨架槽位"""

    label: str = Field(description="槽位名，如 '通勤'")
    start: str = Field(description="开始 HH:MM")
    end: str = Field(description="结束 HH:MM")
    block_type: BlockType = Field(description="块类型")
    micro_cycle: Optional[Dict[str, int]] = Field(
        default=None, description="微节律 {'work_min':90,'rest_min':15}"
    )

    @field_validator("start", "end")
    @classmethod
    def _check_hhmm(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError(f"时间格式应为 HH:MM: {v!r}")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"时间超出范围: {v!r}")
        return v


class DayTemplateUpsertRequest(BaseModel):
    """模板创建/更新请求"""

    name: str = Field(description="模板名（weekday/weekend/travel_day）")
    description: str = Field(default="", description="描述")
    weekday_mask: List[int] = Field(
        default_factory=lambda: [1, 1, 1, 1, 1, 0, 0],
        description="适用星期（周一为索引 0，长度 7）",
    )
    slots: List[TemplateSlot] = Field(default_factory=list, description="骨架槽位")
    enabled: bool = Field(default=True)
    priority: int = Field(default=0, description="多模板冲突时取高")

    @field_validator("weekday_mask")
    @classmethod
    def _check_mask(cls, v: List[int]) -> List[int]:
        if len(v) != 7 or any(x not in (0, 1) for x in v):
            raise ValueError("weekday_mask 应为长度 7 的 0/1 数组")
        return v


class DayTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str = ""
    weekday_mask: List[int] = Field(default_factory=list)
    slots: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    priority: int = 0
    ctime: Optional[datetime] = None
    mtime: Optional[datetime] = None


class DayTemplateListResponse(BaseModel):
    templates: List[DayTemplateResponse]
    total: int


# ============================================================================
# Checkin DTOs
# ============================================================================


class CheckinRequest(BaseModel):
    """打卡请求"""

    affair_id: int = Field(description="precept/habit 事务 ID")
    result: CheckinResult = Field(description="kept/violated/exempt（戒律）| done/missed/exempt（习惯）")
    log_date: Optional[date_type] = Field(default=None, description="归属日（默认今天）")
    note: str = Field(default="", description="备注（破戒原因等）")
    source: str = Field(default="manual", description="manual/agent/auto")


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
    """今日待打卡项"""

    affair: AffairResponse
    done_today: bool = Field(description="今日是否已打卡")
    last_result: Optional[CheckinResult] = None
    week_done_count: int = Field(default=0, description="本周已达成次数（habit 用）")
    week_target: int = Field(default=0, description="本周目标次数（habit 用）")


class CheckinTodayResponse(BaseModel):
    date: date_type
    precepts: List[CheckinTodayItem] = Field(default_factory=list)
    habits: List[CheckinTodayItem] = Field(default_factory=list)


# ============================================================================
# Venture DTOs
# ============================================================================


class VentureMilestoneRequest(BaseModel):
    """添加里程碑子事务"""

    title: str = Field(description="里程碑标题")
    timespan_id: Optional[int] = Field(default=None, description="锚定 TimeSpan（双周/季度）")
    urgency_ddl: Optional[datetime] = Field(default=None, description="截止时间")
    est_minutes: Optional[int] = Field(default=None, ge=0)
    description: str = ""


class VentureProgressResponse(BaseModel):
    """长期事业倒排进度"""

    affair_id: int
    title: str
    target_date: Optional[date_type] = None
    weeks_left: Optional[float] = Field(default=None, description="剩余周数")
    weekly_budget_hours: float = 0.0
    week_consumed_hours: float = Field(default=0.0, description="本周已消耗事业块小时")
    total_done_hours: float = Field(default=0.0, description="累计事业块小时")
    total_est_hours: float = 0.0
    countdown_pressure: Optional[float] = Field(
        default=None, description="倒排压力 >1.0 表示按当前节奏无法按期"
    )
    milestones: List[AffairResponse] = Field(default_factory=list)
    completion_ratio: float = Field(default=0.0, description="里程碑完成度 0-1")


# ============================================================================
# TimeBlock / Timeline DTOs
# ============================================================================


class TimeBlockCreateRequest(BaseModel):
    """手动创建时间线块"""

    day_id: Optional[int] = Field(default=None, description="所属自然日（与 date 二选一）")
    date: Optional[date_type] = Field(default=None, description="所属日期")
    affair_id: Optional[int] = None
    block_type: BlockType
    start_time: datetime
    end_time: datetime
    pinned: bool = False
    ref: Dict[str, Any] = Field(default_factory=dict)


class TimeBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_id: int
    affair_id: Optional[int] = None
    block_type: BlockType
    start_time: datetime
    end_time: datetime
    status: BlockStatus = BlockStatus.PLANNED
    pinned: bool = False
    plan_version: int = 1
    ref: Dict[str, Any] = Field(default_factory=dict)
    affair_title: Optional[str] = Field(default=None, description="关联事务标题（冗余）")
    affair_kind: Optional[AffairKind] = Field(default=None, description="关联事务种类（冗余）")
    energy_cost: int = Field(default=0, description="关联事务精力点数（冗余）")
    ctime: Optional[datetime] = None
    mtime: Optional[datetime] = None


class BlockStatusRequest(BaseModel):
    """块反馈"""

    status: BlockStatus = Field(description="done/skipped/doing/planned")


class BlockMoveRequest(BaseModel):
    """手动拖改块"""

    start_time: datetime
    end_time: datetime


class DomainMinutes(BaseModel):
    life: int = 0
    work: int = 0
    career: int = 0


class DayTimelineResponse(BaseModel):
    """日时间线（blocks + 三域余量统计 + 待打卡清单）"""

    date: date_type
    day_id: int
    plan_version: int = 0
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    domain_minutes: DomainMinutes = Field(default_factory=DomainMinutes)
    energy_consumed: int = Field(default=0, description="当日 DONE 块精力消耗")
    energy_budget: int = Field(default=100, description="当日精力预算")
    buffer_total_minutes: int = Field(default=0, description="当日缓冲总分钟")
    buffer_free_minutes: int = Field(default=0, description="缓冲剩余分钟")
    checkins: Optional[CheckinTodayResponse] = Field(
        default=None, description="当日戒律/习惯待打卡清单"
    )
    warnings: List[str] = Field(default_factory=list)


class HealthSignalItem(BaseModel):
    """当日健康信号条目"""

    signal_type: str
    ref_id: int
    value_json: Dict[str, Any] = Field(default_factory=dict)
    htime: Optional[datetime] = None


class RhythmDayViewResponse(BaseModel):
    """统一日视图（PEMS day view 合并进 Rhythm）"""

    date: date_type
    day_id: int
    plan_version: int = 0
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    domain_minutes: DomainMinutes = Field(default_factory=DomainMinutes)
    energy_consumed: int = Field(default=0)
    energy_budget: int = Field(default=100)
    energy_available: int = Field(default=100, description="剩余可用精力预算")
    buffer_total_minutes: int = Field(default=0)
    buffer_free_minutes: int = Field(default=0)
    checkins: Optional[CheckinTodayResponse] = None
    health_signals: List[HealthSignalItem] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    note: Optional[str] = Field(default=None, description="日复盘备注")


class PriorityAffairItem(BaseModel):
    """日仪表板优先级事务项"""

    affair: AffairResponse
    reason: str = Field(default="", description="入选原因，如 '高优先级 / 今日到期 / 精力充沛时'")
    suggested_slot: Optional[str] = Field(default=None, description="建议时段，如 09:00-10:30")


class RhythmDayDashboardResponse(BaseModel):
    """统一日仪表板：时间线 + 精力 + 打卡 + 优先级事务"""

    date: date_type
    day_id: int
    plan_version: int = 0
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    domain_minutes: DomainMinutes = Field(default_factory=DomainMinutes)
    energy_budget: int = 100
    energy_consumed: int = 0
    energy_available: int = 100
    buffer_total_minutes: int = 0
    buffer_free_minutes: int = 0
    checkins: Optional[CheckinTodayResponse] = None
    priorities: List[PriorityAffairItem] = Field(default_factory=list)
    insights: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# ============================================================================
# Plan DTOs
# ============================================================================


class PlanDayRequest(BaseModel):
    """生成/重生成日计划"""

    date: date_type = Field(description="目标日期")
    preserve_done: bool = Field(default=True, description="保留 DONE/DOING 块")
    force: bool = Field(default=False, description="忽略预算不足等软警告")


class PlanWarning(BaseModel):
    code: str = Field(description="警告码，如 budget_insufficient / fixed_conflict / overtime")
    message: str
    affair_id: Optional[int] = None


class UnplacedItem(BaseModel):
    affair_id: int
    title: str
    reason: str = Field(description="窗口冲突/精力不足/预算不足/周预算耗尽...")


class PlanDayResponse(BaseModel):
    date: date_type
    day_id: int
    plan_version: int
    blocks: List[TimeBlockResponse] = Field(default_factory=list)
    warnings: List[PlanWarning] = Field(default_factory=list)
    unplaced: List[UnplacedItem] = Field(default_factory=list)


class RebalanceRequest(BaseModel):
    """再平衡请求"""

    date: date_type
    trigger: str = Field(
        default="manual", description="defer | new_affair | manual | checkin_missed"
    )


class EncroachmentItem(BaseModel):
    """侵占事件"""

    type: str = Field(description="protect_window_violation / career_out_of_spare / fixed_conflict / overtime ...")
    message: str
    block_id: Optional[int] = None
    affair_id: Optional[int] = None
    date: Optional[date_type] = None


class ConflictReportResponse(BaseModel):
    date: date_type
    encroachments: List[EncroachmentItem] = Field(default_factory=list)


class EnsureTemplatesResponse(BaseModel):
    created: int = 0
    updated: int = 0
    templates: List[DayTemplateResponse] = Field(default_factory=list)


# ============================================================================
# EnergyProfile / Policy DTOs
# ============================================================================


class EnergyProfileUpsertRequest(BaseModel):
    """精力画像 upsert（单行）"""

    name: str = Field(default="default")
    daily_energy_budget: Optional[int] = Field(default=None, ge=1)
    curve_template: Optional[Dict[str, List[float]]] = None
    sleep_start: Optional[str] = Field(default=None, description="HH:MM")
    sleep_end: Optional[str] = Field(default=None, description="HH:MM")
    work_hours_cap: Optional[float] = Field(default=None, gt=0)
    spare_time_windows: Optional[Dict[str, List[List[str]]]] = None
    min_buffer_ratio: Optional[float] = Field(default=None, ge=0, le=0.5)
    life_weight: Optional[float] = Field(default=None, ge=0)
    work_weight: Optional[float] = Field(default=None, ge=0)
    career_weight: Optional[float] = Field(default=None, ge=0)
    score_weights: Optional[Dict[str, float]] = None


class EnergyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str = "default"
    is_default: bool = Field(default=True, description="是否为首次导入的默认画像，未校准")
    daily_energy_budget: int = 100
    curve_template: Dict[str, Any] = Field(default_factory=dict)
    sleep_start: str = "23:30"
    sleep_end: str = "07:00"
    work_hours_cap: float = 8.0
    spare_time_windows: Dict[str, Any] = Field(default_factory=dict)
    min_buffer_ratio: float = 0.15
    life_weight: float = 1.0
    work_weight: float = 1.0
    career_weight: float = 0.6
    score_weights: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[datetime] = None


class PolicyCreateRequest(BaseModel):
    name: str
    rule_type: PolicyRuleType
    params: Dict[str, Any] = Field(default_factory=dict)
    scope: str = Field(default="day", description="day | week")
    enabled: bool = True


class PolicyUpdateRequest(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[PolicyRuleType] = None
    params: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None
    enabled: Optional[bool] = None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool = True
    rule_type: PolicyRuleType
    params: Dict[str, Any] = Field(default_factory=dict)
    scope: str = "day"
    ctime: Optional[datetime] = None
    mtime: Optional[datetime] = None


class PolicyListResponse(BaseModel):
    policies: List[PolicyResponse]
    total: int


# ============================================================================
# Review DTOs
# ============================================================================


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    scope: str
    period_key: str
    rhythm_score: float = 0.0
    domain_minutes: Dict[str, Any] = Field(default_factory=dict)
    precept_compliance_rate: float = 0.0
    habit_consistency: float = 0.0
    sleep_window_keeping: float = 0.0
    venture_budget_fulfillment: float = 0.0
    buffer_consumed: float = 0.0
    encroachments: List[Any] = Field(default_factory=list)
    ai_summary: str = ""
    created_at: Optional[datetime] = None


class ReviewSummaryUpdateRequest(BaseModel):
    """Agent 写回周评语"""

    ai_summary: str


class RhythmDashboardResponse(BaseModel):
    """Dashboard 与 Android 提醒端共享的唯一聚合入口"""

    date: date_type
    timeline: DayTimelineResponse
    day_review: ReviewResponse
    week_review: ReviewResponse
    today_checkins: CheckinTodayResponse
    energy_profile: EnergyProfileResponse
    policies: List[PolicyResponse] = Field(default_factory=list)
    conflicts: ConflictReportResponse
    inbox_summary: List[PriorityAffairItem] = Field(default_factory=list)
    overdue_summary: List[PriorityAffairItem] = Field(default_factory=list)
    today_due_summary: List[PriorityAffairItem] = Field(default_factory=list)


class HabitHeatmapItem(BaseModel):
    """habit 热力图单日项"""

    date: date_type
    cycle_key: str
    result: Optional[CheckinResult] = None
    done: bool = Field(default=False, description="是否已打卡完成")


class HabitHeatmapResponse(BaseModel):
    affair_id: int
    start_date: date_type
    end_date: date_type
    days: List[HabitHeatmapItem] = Field(default_factory=list)


class DomainTrendItem(BaseModel):
    date: date_type
    life: int = 0
    work: int = 0
    career: int = 0


class DomainTrendResponse(BaseModel):
    start_date: date_type
    end_date: date_type
    days: List[DomainTrendItem] = Field(default_factory=list)


class VentureBurndownResponse(BaseModel):
    affair_id: int
    title: str
    weeks: List[str] = Field(default_factory=list)
    planned: List[float] = Field(default_factory=list)
    actual: List[float] = Field(default_factory=list)
    milestones_done: List[int] = Field(default_factory=list)


# ============================================================================
# HealthCheckin DTOs
# ============================================================================


class WeightPayload(BaseModel):
    value_kg: float = Field(description="体重（kg）")
    measured_at: Optional[datetime] = Field(default=None, description="测量时间 ISO")


class MealPayload(BaseModel):
    meal_type: str = Field(description="breakfast | lunch | dinner | snack")
    foods: Optional[List[str]] = Field(default=None, description="食物列表")
    estimated_calories: Optional[int] = Field(default=None, ge=0)


class ExercisePayload(BaseModel):
    activity: str = Field(description="运动项目")
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    intensity: Optional[str] = Field(default="moderate", description="light | moderate | vigorous")


class MedicationPayload(BaseModel):
    name: str = Field(description="药品名")
    dose: Optional[str] = Field(default=None)
    taken_at: Optional[datetime] = Field(default=None)


class HealthCheckinRequest(BaseModel):
    """健康速记请求（Android 提醒闭环入口）"""

    collection_type: InfoCollectionType
    log_date: Optional[date_type] = Field(default=None, description="归属日（默认今天）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="具体数据")
    note: str = Field(default="", description="备注")


class HealthCheckinResponse(BaseModel):
    """健康速记响应"""

    id: int
    collection_type: str
    log_date: date_type
    ref_id: Optional[int] = Field(default=None, description="health 表记录 ID")
    affair_id: Optional[int] = Field(default=None, description="关联 rhythm_affairs.id")
    note: str = ""
    created_at: Optional[datetime] = None


# ============================================================================
# Timespan Review DTOs
# ============================================================================


class ReviewTimespanResponse(ReviewResponse):
    """周期复盘视图（PEMS timespan review 合并进 Rhythm）"""

    timespan_id: int
