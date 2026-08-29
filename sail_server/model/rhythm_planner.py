# -*- coding: utf-8 -*-
# @file rhythm_planner.py
# @brief Rhythm Planner (分类评分引擎 + 八步排程器 + 再平衡 + 侵占检测 + 节奏评分)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏排程与评分纯算法层（服务端确定性，AI 仅提供输入建议）

设计文档: doc/design/manager/rhythm.md §5

- §5.1 统一优先级评分（分类紧迫度 + 三域平衡加成 + 精力匹配 + 连续激励 + 生活地板）
- §5.2 精力模型（曲线匹配 + 过载告警）
- §5.3 财力校验（finance 预算剩余）
- §5.4 plan_day 八步铺底（睡眠→骨架→刚性钉→戒律→缓冲→事业→习惯/工作竞争）
- §5.5 侵占检测与再平衡
- §5.6 节奏评分（Review）
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairKind,
    AffairState,
    CheckinResult,
    CheckinTodayResponse,
    ConflictReportResponse,
    DayTimelineResponse,
    DomainMinutes,
    DomainTrendItem,
    DomainTrendResponse,
    EncroachmentItem,
    HabitHeatmapItem,
    HabitHeatmapResponse,
    PlanDayRequest,
    PlanDayResponse,
    PlanWarning,
    PriorityAffairItem,
    RebalanceRequest,
    ReviewResponse,
    RhythmDashboardResponse,
    TERMINAL_STATES,
    UnplacedItem,
    VentureBurndownResponse,
)
from sail_server.infrastructure.orm.finance import Budget, Transaction
from sail_server.infrastructure.orm.life import Day
from sail_server.infrastructure.orm.rhythm import (
    RhythmAffair,
    RhythmEnergyProfile,
    RhythmPolicy,
    RhythmReview,
    RhythmTimeBlock,
)
from sail_server.model.rhythm import (
    DEFAULT_SCORE_WEIGHTS,
    RhythmBadRequestError,
    _get_or_create_day,
    _kind_of,
    _now,
    _today,
    affair_to_response,
    blocks_to_response,
    get_active_template_for_date,
    get_energy_profile_impl,
    get_or_create_profile,
    list_affairs_impl,
    list_policies_impl,
    today_checkins_impl,
    week_cycle_key,
    week_range,
)

logger = logging.getLogger(__name__)

Interval = Tuple[datetime, datetime]


# ============================================================================
# 区间工具
# ============================================================================


def _overlap(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _clip(s: datetime, e: datetime, lo: datetime, hi: datetime) -> Optional[Interval]:
    ns, ne = max(s, lo), min(e, hi)
    return (ns, ne) if ns < ne else None


def _subtract(free: List[Interval], busy: Interval) -> List[Interval]:
    """从 free 区间集中扣除 busy"""
    out: List[Interval] = []
    for s, e in free:
        if not _overlap((s, e), busy):
            out.append((s, e))
            continue
        if s < busy[0]:
            out.append((s, min(e, busy[0])))
        if busy[1] < e:
            out.append((max(s, busy[1]), e))
    return [(s, e) for s, e in out if s < e]


def _minutes(iv: Interval) -> int:
    return int((iv[1] - iv[0]).total_seconds() // 60)


def _parse_hhmm(v: str, default: str) -> time:
    try:
        h, m = str(v or default).split(":")[:2]
        return time(int(h), int(m))
    except Exception:
        h, m = default.split(":")
        return time(int(h), int(m))


# ============================================================================
# §5.1 统一优先级评分
# ============================================================================


@dataclass
class ScoreContext:
    """评分上下文（plan_day 当日一次性构建）"""

    now: datetime
    target_date: date
    week_done_counts: Dict[int, int] = field(default_factory=dict)  # habit_id → 本周已打卡次数
    week_planned_counts: Dict[int, int] = field(default_factory=dict)  # habit_id → 本周已排块次数
    remaining_days_in_week: int = 1  # 含当日
    domain_boost: Dict[str, float] = field(default_factory=dict)  # domain → 0..1 欠投入度
    curve: List[float] = field(default_factory=list)  # 当日 24 段能量系数
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCORE_WEIGHTS))
    max_work_career_score: float = 0.0  # 生活地板参照


def compute_urgency(affair: RhythmAffair, ctx: ScoreContext) -> float:
    """分类紧迫度 u(kind)"""
    kind = _kind_of(affair)
    meta = affair.kind_meta or {}
    now = ctx.now

    if kind == AffairKind.TASK_ONEOFF:
        ddl = affair.urgency_ddl
        if ddl is None:
            return 0.2
        days = (ddl - now).total_seconds() / 86400.0
        if days <= 1:
            return 1.0
        if days <= 3:
            return 0.8
        if days <= 7:
            return 0.5
        return 0.2

    if kind == AffairKind.TASK_MAINTENANCE:
        interval = float(meta.get("interval_days") or 7)
        last_done = meta.get("last_done_at")
        if not last_done:
            return 1.0
        if isinstance(last_done, str):
            last_done = datetime.fromisoformat(last_done)
        elapsed = (now - last_done).total_seconds() / 86400.0
        return max(0.0, min(elapsed / interval, 1.2))

    if kind == AffairKind.HABIT:
        freq = int(meta.get("freq_per_week") or 3)
        done = ctx.week_done_counts.get(affair.id, 0)
        planned = ctx.week_planned_counts.get(affair.id, 0)
        remaining = max(freq - done - planned, 0)
        if remaining <= 0:
            return 0.0
        days_left = max(ctx.remaining_days_in_week, 1)
        return min(remaining / days_left, 1.2)

    if kind == AffairKind.VENTURE:
        weekly_budget = float(meta.get("weekly_budget_hours") or 0.0)
        total_est = float(meta.get("total_est_hours") or 0.0)
        target = meta.get("target_date")
        if not target and affair.urgency_ddl:
            target = affair.urgency_ddl.date().isoformat()
        # 配置缺失兜底：无目标日/预算/总估 → 中性紧迫度，进入排程竞争
        if not target or weekly_budget <= 0 or total_est <= 0:
            return 0.5
        if isinstance(target, str):
            target = date.fromisoformat(target[:10])
        weeks_left = max((target - ctx.target_date).days / 7.0, 0.0)
        if weeks_left <= 0:
            return 1.2
        return min(total_est / (weeks_left * weekly_budget), 1.2)

    if kind == AffairKind.ASYNC_CALLBACK:
        # DELEGATED 阶段不占实时窗，不参与排程评分
        if affair.state == AffairState.DELEGATED.value:
            return 0.0
        # kickoff/review 阶段：按 ddl 紧迫度（与 task_oneoff 同口径），
        # 无 ddl 时按 review 提醒锚点 next_review_at 反推紧迫度
        ddl = affair.urgency_ddl
        if ddl is not None:
            days = (ddl - now).total_seconds() / 86400.0
            if days <= 1:
                return 1.0
            if days <= 3:
                return 0.8
            if days <= 7:
                return 0.5
            return 0.2
        # 无 ddl：用 next_review_at 作为软 ddl
        meta = affair.kind_meta or {}
        nxt = meta.get("next_review_at")
        if nxt:
            try:
                nxt_dt = datetime.fromisoformat(str(nxt))
                hours = (nxt_dt - now).total_seconds() / 3600.0
                if hours <= 6:
                    return 1.0
                if hours <= 24:
                    return 0.8
                if hours <= 72:
                    return 0.5
                return 0.2
            except (ValueError, TypeError):
                pass
        return 0.3

    # fixed_plan / precept / base_rhythm / buffer 不参与评分（刚性/规则铺底）
    return 0.0


def compute_domain_boost(db: Session, profile: RhythmEnergyProfile, d: date) -> Dict[str, float]:
    """三域平衡加成（欠投入域 +）：最近 7 天实际比与目标权重的偏离

    返回 domain → 0..1 的欠投入度（0 = 不欠）。
    "防工作侵占"的数学表达；career 权重独立，避免事业被工作与生活夹击清零。
    """
    start = d - timedelta(days=7)
    day_ids = [
        row.id for row in db.query(Day.id).filter(Day.date >= start, Day.date < d).all()
    ]
    minutes = {"life": 0, "work": 0, "career": 0}
    if day_ids:
        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id.in_(day_ids),
                RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
            )
            .all()
        )
        affair_ids = {b.affair_id for b in blocks if b.affair_id}
        affairs = {}
        if affair_ids:
            for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
                affairs[a.id] = a
        for b in blocks:
            dom = _block_domain(b, affairs.get(b.affair_id))
            minutes[dom] += _minutes((b.start_time, b.end_time))

    total = sum(minutes.values())
    weights = {
        "life": float(profile.life_weight or 1.0),
        "work": float(profile.work_weight or 1.0),
        "career": float(profile.career_weight or 0.6),
    }
    w_total = sum(weights.values()) or 1.0
    boost: Dict[str, float] = {}
    for dom in ("life", "work", "career"):
        target_share = weights[dom] / w_total
        actual_share = (minutes[dom] / total) if total > 0 else target_share
        boost[dom] = max(target_share - actual_share, 0.0) / max(target_share, 1e-6)
        boost[dom] = min(boost[dom], 1.0)
    return boost


def compute_score(affair: RhythmAffair, ctx: ScoreContext, hour: Optional[int] = None) -> float:
    """统一优先级评分（0-100+）

    score = 100 * (w_i*importance/5 + w_u*u + w_b*boost + w_e*energy_fit + w_s*streak)
    生活地板: 未达周目标的 habit 在 plan_day 中被抬升至当日 work/career 最高分之上。
    """
    w = ctx.weights
    importance_term = (affair.importance or 3) / 5.0
    urgency_term = compute_urgency(affair, ctx)
    boost_term = ctx.domain_boost.get(affair.domain or "life", 0.0)
    energy_fit = 1.0
    if hour is not None and ctx.curve:
        energy_fit = ctx.curve[min(max(hour, 0), 23)]
    streak_term = 0.0
    if _kind_of(affair) == AffairKind.HABIT:
        streak = int((affair.kind_meta or {}).get("streak") or 0)
        streak_term = 1.0 if streak >= 3 else 0.0

    score = 100.0 * (
        w.get("w_i", 0.30) * importance_term
        + w.get("w_u", 0.30) * urgency_term
        + w.get("w_b", 0.20) * boost_term
        + w.get("w_e", 0.15) * energy_fit
        + w.get("w_s", 0.05) * streak_term
    )
    return round(score, 4)


# ============================================================================
# §5.3 财力校验
# ============================================================================


def check_budget_remaining(db: Session, affair: RhythmAffair) -> Optional[float]:
    """返回预算剩余金额；无预算约束返回 None"""
    if not affair.budget_id or float(affair.money_cost or 0) <= 0:
        return None
    budget = db.query(Budget).filter(Budget.id == affair.budget_id).first()
    if budget is None:
        return None
    try:
        total = float(budget.total_amount or 0.0)
    except (TypeError, ValueError):
        total = 0.0
    consumed = 0.0
    for tx in db.query(Transaction).filter(Transaction.budget_id == budget.id).all():
        try:
            consumed += abs(float(tx.value or 0.0))
        except (TypeError, ValueError):
            continue
    return total - consumed


# ============================================================================
# §5.4 plan_day 八步排程器
# ============================================================================


@dataclass
class _PlanCtx:
    """排程上下文"""

    db: Session
    d: date
    day: Day
    profile: RhythmEnergyProfile
    new_version: int
    force: bool = False
    blocks: List[RhythmTimeBlock] = field(default_factory=list)  # 本次新创建
    warnings: List[PlanWarning] = field(default_factory=list)
    unplaced: List[UnplacedItem] = field(default_factory=list)
    energy_spent: int = 0
    energy_overload_warned: bool = False

    def add_block(
        self,
        block_type: str,
        start: datetime,
        end: datetime,
        affair: Optional[RhythmAffair] = None,
        pinned: bool = False,
        ref: Optional[Dict[str, Any]] = None,
        status: str = "PLANNED",
    ) -> Optional[RhythmTimeBlock]:
        """创建块（对 affair 块按 day+affair+type 幂等去重）"""
        if affair is not None:
            dup = (
                self.db.query(RhythmTimeBlock)
                .filter(
                    RhythmTimeBlock.day_id == self.day.id,
                    RhythmTimeBlock.affair_id == affair.id,
                    RhythmTimeBlock.block_type == block_type,
                    RhythmTimeBlock.status != "MOVED",
                )
                .first()
            )
            if dup is not None:
                return dup
        block = RhythmTimeBlock(
            day_id=self.day.id,
            affair_id=affair.id if affair else None,
            block_type=block_type,
            start_time=start,
            end_time=end,
            status=status,
            pinned=pinned,
            plan_version=self.new_version,
            ref=ref or {},
        )
        self.db.add(block)
        self.db.flush()
        self.blocks.append(block)
        if affair is not None:
            self.energy_spent += affair.energy_cost or 0
            self._check_energy_overload()
        return block

    def _check_energy_overload(self) -> None:
        budget = int(self.profile.daily_energy_budget or 100)
        if not self.energy_overload_warned and self.energy_spent > budget * 1.1:
            self.energy_overload_warned = True
            self.warnings.append(
                PlanWarning(
                    code="energy_overload",
                    message=f"当日精力消耗预计 {self.energy_spent} 点，超过预算 {budget} 的 110%，"
                    "建议启用 fallback 或推迟低分工作块",
                )
            )


def _existing_blocks(db: Session, day_id: int) -> List[RhythmTimeBlock]:
    return (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day_id,
            RhythmTimeBlock.status != "MOVED",
        )
        .order_by(RhythmTimeBlock.start_time)
        .all()
    )


def _occupied_intervals(blocks: List[RhythmTimeBlock]) -> List[Interval]:
    """占用区间

    不占用排程空间的块:
    - informational 微休息提示块（允许 focus 跨越）
    - work_window 骨架块（工作窗是“容器”，focus/light 块排入其中，而非被它占住）
    """
    out = []
    for b in blocks:
        ref = b.ref or {}
        if ref.get("informational"):
            continue
        if b.block_type == "work_window":
            continue
        out.append((b.start_time, b.end_time))
    out.sort()
    return out


def _free_intervals(
    awake: Interval, occupied: List[Interval], extra_busy: Optional[List[Interval]] = None
) -> List[Interval]:
    """清醒窗内的自由区间。

    extra_busy: 额外禁排区间（如 habit/buffer/venture 需避开 work_window 内部）。
    """
    free = [awake]
    for busy in occupied:
        free = _subtract(free, busy)
    for busy in extra_busy or []:
        free = _subtract(free, busy)
    free.sort()
    return free


def _place_in_free(
    free: List[Interval],
    duration_min: int,
    candidates: Optional[List[Interval]] = None,
) -> Optional[Interval]:
    """在 free（可选 candidates 子区间）中找首个能容纳 duration 的位置"""
    search = free
    if candidates:
        clipped: List[Interval] = []
        for c in candidates:
            for f in free:
                iv = _clip(c[0], c[1], f[0], f[1])
                if iv:
                    clipped.append(iv)
        search = sorted(clipped)
    for s, e in search:
        if _minutes((s, e)) >= duration_min:
            return (s, s + timedelta(minutes=duration_min))
    return None


def plan_day_impl(db: Session, request: PlanDayRequest) -> PlanDayResponse:
    """生成/重生成日计划（八步铺底，顺序即优先级）"""
    d = request.date
    day = _get_or_create_day(db, d)
    profile = get_or_create_profile(db)

    # ---- 版本推进：旧 PLANNED 非 pinned 块置 MOVED（保留可回滚）----
    old_blocks = _existing_blocks(db, day.id)
    max_version = max([b.plan_version or 1 for b in old_blocks], default=0)
    new_version = max_version + 1
    for b in old_blocks:
        if b.pinned:
            continue  # pinned 冻结
        if b.status in ("DONE", "DOING") and request.preserve_done:
            continue  # 执行反馈冻结
        if b.status == "PLANNED":
            b.status = "MOVED"
    db.commit()

    ctx = _PlanCtx(db=db, d=d, day=day, profile=profile, new_version=new_version, force=request.force)

    # 启用的守护策略（模板生成骨架，policy 校验约束）
    policies = db.query(RhythmPolicy).filter(RhythmPolicy.enabled.is_(True)).all()
    max_focus_min: Optional[int] = None
    domain_caps: List[Dict[str, Any]] = []
    for p in policies:
        if p.rule_type == "max_consecutive_focus":
            max_focus_min = int((p.params or {}).get("minutes", 120))
        elif p.rule_type == "domain_cap":
            domain_caps.append(p.params or {})

    sleep_start_t = _parse_hhmm(profile.sleep_start, "23:30")
    sleep_end_t = _parse_hhmm(profile.sleep_end, "07:00")
    day_start = datetime.combine(d, time.min)
    day_end = day_start + timedelta(days=1)
    awake: Interval = (
        datetime.combine(d, sleep_end_t),
        datetime.combine(d, sleep_start_t),
    )

    # 当前有效块（冻结的 pinned/DONE/DOING 已存在）
    live_blocks = _existing_blocks(db, day.id)

    def has_block(block_type: str, start: datetime, end: datetime) -> bool:
        return any(
            b.block_type == block_type
            and b.start_time == start
            and b.end_time == end
            for b in live_blocks
        )

    # ---- Step 1: 睡眠守护 ----
    sleep_ivs = [
        (day_start, datetime.combine(d, sleep_end_t)),
        (datetime.combine(d, sleep_start_t), day_end),
    ]
    for s, e in sleep_ivs:
        if s < e and not has_block("sleep", s, e):
            blk = RhythmTimeBlock(
                day_id=day.id, affair_id=None, block_type="sleep",
                start_time=s, end_time=e, status="PLANNED",
                pinned=True, plan_version=new_version, ref={"label": "睡眠守护"},
            )
            db.add(blk)
            db.flush()
            ctx.blocks.append(blk)
    live_blocks = _existing_blocks(db, day.id)

    # ---- Step 2: 基础节奏骨架（DayTemplate 实例化）----
    template = get_active_template_for_date(db, d)
    work_windows: List[Interval] = []
    if template is not None:
        for slot in template.slots or []:
            st = _parse_hhmm(slot.get("start", "09:00"), "09:00")
            et = _parse_hhmm(slot.get("end", "18:00"), "18:00")
            s, e = datetime.combine(d, st), datetime.combine(d, et)
            if e <= s:
                continue
            btype = slot.get("block_type", "rest")
            if has_block(btype, s, e):
                if btype == "work_window":
                    work_windows.append((s, e))
                continue
            blk = RhythmTimeBlock(
                day_id=day.id, affair_id=None, block_type=btype,
                start_time=s, end_time=e, status="PLANNED", pinned=True,
                plan_version=new_version,
                ref={"label": slot.get("label", btype), "template_id": template.id,
                     "micro_cycle": slot.get("micro_cycle")},
            )
            db.add(blk)
            db.flush()
            ctx.blocks.append(blk)
            if btype == "work_window":
                work_windows.append((s, e))
            # 微节律提示块（informational，不占用排程空间，允许 focus 跨越）
            mc = slot.get("micro_cycle")
            if btype == "work_window" and mc:
                work_min = int(mc.get("work_min") or 90)
                rest_min = int(mc.get("rest_min") or 15)
                cursor = s + timedelta(minutes=work_min)
                idx = 1
                while cursor + timedelta(minutes=rest_min) <= e:
                    if not has_block("micro_rest", cursor, cursor + timedelta(minutes=rest_min)):
                        mrb = RhythmTimeBlock(
                            day_id=day.id, affair_id=None, block_type="micro_rest",
                            start_time=cursor, end_time=cursor + timedelta(minutes=rest_min),
                            status="PLANNED", pinned=False, plan_version=new_version,
                            ref={"label": f"微休息 #{idx}", "informational": True,
                                 "micro_cycle": idx},
                        )
                        db.add(mrb)
                        db.flush()
                        ctx.blocks.append(mrb)
                    cursor += timedelta(minutes=work_min + rest_min)
                    idx += 1
    live_blocks = _existing_blocks(db, day.id)

    # ---- Step 3: 刚性钉（fixed_plan，冲突只报警不移动）----
    fixed_affairs = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.FIXED_PLAN.value,
            RhythmAffair.state == AffairState.SCHEDULED.value,
        )
        .all()
    )
    for fa in fixed_affairs:
        meta = fa.kind_meta or {}
        if not meta.get("fixed_start") or not meta.get("fixed_end"):
            continue
        fs = datetime.fromisoformat(str(meta["fixed_start"]))
        fe = datetime.fromisoformat(str(meta["fixed_end"]))
        iv = _clip(fs, fe, day_start, day_end)
        if iv is None:
            continue
        fixed_block = ctx.add_block(
            "fixed", iv[0], iv[1], affair=fa, pinned=True, ref={"label": fa.title}
        )
        # 与骨架/其他块冲突 → 仅报警，刚性钉不移动
        for b in live_blocks:
            if fixed_block is not None and b.id == fixed_block.id:
                continue
            if (b.ref or {}).get("informational") or b.block_type == "sleep":
                continue
            if _overlap((b.start_time, b.end_time), iv):
                ctx.warnings.append(
                    PlanWarning(
                        code="fixed_conflict",
                        message=f"刚性规划「{fa.title}」与 {b.block_type} 块 "
                        f"({b.start_time:%H:%M}-{b.end_time:%H:%M}) 冲突，刚性块不移动",
                        affair_id=fa.id,
                    )
                )
        live_blocks = _existing_blocks(db, day.id)

    # ---- Step 4: 戒律打卡块（soft precept 轻量块）----
    precepts = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.PRECEPT.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    for p in precepts:
        meta = p.kind_meta or {}
        mask = meta.get("weekday_mask") or [1] * 7
        if len(mask) == 7 and mask[d.weekday()] != 1:
            continue
        block_minutes = int(meta.get("block_minutes") or 0)
        if block_minutes <= 0:
            continue  # 仅核销提醒（经 reminder 投递），不占块
        check_t = _parse_hhmm(meta.get("check_time", "22:30"), "22:30")
        start = datetime.combine(d, check_t)
        occupied = _occupied_intervals(live_blocks)
        free = _free_intervals(awake, occupied, extra_busy=work_windows)
        placed = _place_in_free(free, block_minutes, candidates=[(start, start + timedelta(minutes=block_minutes))])
        if placed is None:
            placed = _place_in_free(free, block_minutes)
        if placed is not None:
            ctx.add_block("precept", placed[0], placed[1], affair=p, ref={"label": p.title})
        else:
            ctx.unplaced.append(UnplacedItem(affair_id=p.id, title=p.title, reason="窗口冲突"))
        live_blocks = _existing_blocks(db, day.id)

    # ---- Step 5: 缓冲扣除（min_buffer_ratio，分散插入）----
    awake_minutes = _minutes(awake)
    buffer_ratio = float(profile.min_buffer_ratio or 0.15)
    buffer_target = int(awake_minutes * buffer_ratio)
    existing_buffer = sum(
        _minutes((b.start_time, b.end_time)) for b in live_blocks if b.block_type == "buffer"
    )
    buffer_remaining = max(buffer_target - existing_buffer, 0)
    if buffer_remaining > 0:
        # 两个锚点：最后一个工作窗结束后、晚间睡前
        anchors: List[datetime] = []
        if work_windows:
            anchors.append(max(we for _, we in work_windows))
        anchors.append(datetime.combine(d, sleep_start_t) - timedelta(hours=1))
        for anchor in anchors:
            if buffer_remaining < 15:
                break
            chunk = min(buffer_remaining, 60)
            occupied = _occupied_intervals(live_blocks)
            free = _free_intervals(awake, occupied, extra_busy=work_windows)
            placed = _place_in_free(
                free, chunk, candidates=[(anchor, anchor + timedelta(hours=2))]
            )
            if placed is not None:
                ctx.add_block(
                    "buffer", placed[0], placed[1], pinned=False, ref={"label": "弹性缓冲"}
                )
                buffer_remaining -= _minutes(placed)
                live_blocks = _existing_blocks(db, day.id)
        if buffer_remaining >= 15:
            ctx.warnings.append(
                PlanWarning(
                    code="buffer_short",
                    message=f"缓冲不足：目标 {buffer_target}min，仍有 {buffer_remaining}min 无法安排",
                )
            )

    # ---- Step 6: 事业块（仅业余时间区）----
    monday, sunday = week_range(d)
    week_day_ids = [
        row.id for row in db.query(Day.id).filter(Day.date >= monday, Day.date <= sunday).all()
    ]
    ventures = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.VENTURE.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    spare_cfg = profile.spare_time_windows or {}
    spare_key = "weekday" if d.weekday() < 5 else "weekend"
    spare_windows: List[Interval] = []
    for rng in spare_cfg.get(spare_key, []):
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            st = _parse_hhmm(rng[0], "19:30")
            et = _parse_hhmm(rng[1], "22:30")
            spare_windows.append((datetime.combine(d, st), datetime.combine(d, et)))

    for v in ventures:
        meta = v.kind_meta or {}
        weekly_budget_min = int(float(meta.get("weekly_budget_hours") or 0.0) * 60)
        consumed = _venture_week_minutes(db, v, week_day_ids)
        remaining = weekly_budget_min - consumed
        if remaining <= 0:
            ctx.unplaced.append(
                UnplacedItem(affair_id=v.id, title=v.title, reason="周预算耗尽")
            )
            continue
        if meta.get("spare_time_only", True) and not spare_windows:
            ctx.unplaced.append(
                UnplacedItem(affair_id=v.id, title=v.title, reason="业余时间区未配置")
            )
            continue
        duration = min(int(v.est_minutes or 60), remaining)
        duration = max(duration, int(v.min_chunk_minutes or 30))
        if duration > remaining:
            duration = remaining
        occupied = _occupied_intervals(live_blocks)
        free = _free_intervals(awake, occupied, extra_busy=work_windows)
        placed = _place_in_free(free, duration, candidates=spare_windows)
        if placed is None and not meta.get("spare_time_only", True):
            placed = _place_in_free(free, duration)
        if placed is not None:
            ctx.add_block("career", placed[0], placed[1], affair=v, ref={"label": v.title})
            live_blocks = _existing_blocks(db, day.id)
        else:
            ctx.unplaced.append(
                UnplacedItem(affair_id=v.id, title=v.title, reason="业余时间区窗口冲突")
            )

    # ---- Step 6.5: async_callback DELEGATED 阶段 informational 提醒块 ----
    # DELEGATED 阶段不占实时窗，仅在 next_review_at 落点画一个 informational 块提醒"去 review"。
    # work_hours_only 事务的 next_review_at 已被推到工作窗，此处直接用该锚点。
    delegated_asyncs = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.ASYNC_CALLBACK.value,
            RhythmAffair.state == AffairState.DELEGATED.value,
        )
        .all()
    )
    for a in delegated_asyncs:
        meta = a.kind_meta or {}
        nxt = meta.get("next_review_at")
        if not nxt:
            continue
        try:
            anchor = datetime.fromisoformat(str(nxt))
        except (ValueError, TypeError):
            continue
        # 仅画在当日范围内的提醒块
        if not (day_start <= anchor < day_end):
            continue
        # 幂等：当日已有该 affair 的 async_wait 块则跳过
        existing = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id == day.id,
                RhythmTimeBlock.affair_id == a.id,
                RhythmTimeBlock.block_type == "async_wait",
                RhythmTimeBlock.status != "MOVED",
            )
            .first()
        )
        if existing is not None:
            continue
        # informational 块：30 分钟窗（不占排程空间，允许 focus 跨越）
        end_anchor = anchor + timedelta(minutes=30)
        blk = RhythmTimeBlock(
            day_id=day.id, affair_id=a.id, block_type="async_wait",
            start_time=anchor, end_time=end_anchor, status="PLANNED",
            pinned=False, plan_version=new_version,
            ref={
                "label": f"审阅提醒: {a.title}",
                "informational": True,
                "phase": "delegated",
                "round": meta.get("round", 1),
                "delegate_to": meta.get("delegate_to", "ai"),
            },
        )
        db.add(blk)
        db.flush()
        ctx.blocks.append(blk)
        live_blocks = _existing_blocks(db, day.id)

    # ---- Step 7: 习惯与工作任务竞争（生活地板优先于工作）----
    score_ctx = _build_score_context(db, d, profile, week_day_ids)

    # 7a. 习惯（周缺口压力，生活地板：先于工作任务排程）
    habits = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.HABIT.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    for h in habits:
        meta = h.kind_meta or {}
        freq = int(meta.get("freq_per_week") or 3)
        done = score_ctx.week_done_counts.get(h.id, 0)
        planned = score_ctx.week_planned_counts.get(h.id, 0)
        if freq - done - planned <= 0:
            continue
        duration = int(meta.get("min_session_minutes") or 30)
        preferred: List[Interval] = []
        for slot in meta.get("preferred_slots") or []:
            if isinstance(slot, str) and "-" in slot:
                st_s, et_s = slot.split("-", 1)
                preferred.append(
                    (
                        datetime.combine(d, _parse_hhmm(st_s.strip(), "19:00")),
                        datetime.combine(d, _parse_hhmm(et_s.strip(), "21:00")),
                    )
                )
        occupied = _occupied_intervals(live_blocks)
        free = _free_intervals(awake, occupied, extra_busy=work_windows)
        placed = _place_in_free(free, duration, candidates=preferred or None)
        if placed is None:
            placed = _place_in_free(free, duration)
        if placed is not None:
            hour = placed[0].hour
            h.score = compute_score(h, score_ctx, hour=hour)
            # 生活地板：未达周目标的 habit 抬升至当日 work/career 最高分之上
            h.score = max(float(h.score or 0), score_ctx.max_work_career_score + 1)
            ctx.add_block("habit", placed[0], placed[1], affair=h, ref={"label": h.title})
            live_blocks = _existing_blocks(db, day.id)
        else:
            ctx.unplaced.append(UnplacedItem(affair_id=h.id, title=h.title, reason="窗口冲突"))

    # 7b. 工作任务（task_oneoff PLANNED + task_maintenance due，按 score 降序）
    day_tasks = _collect_competing_tasks(db, d, score_ctx)
    # 生活地板已完成（habit 先排），这里按分数贪心
    for task, score in day_tasks:
        task.score = score
        # 财力校验
        remaining_budget = check_budget_remaining(db, task)
        if remaining_budget is not None and float(task.money_cost or 0) > remaining_budget:
            ctx.warnings.append(
                PlanWarning(
                    code="budget_insufficient",
                    message=f"「{task.title}」预估 ¥{float(task.money_cost or 0):.2f} 超预算剩余 "
                    f"¥{remaining_budget:.2f}（可 fallback/改期/force）",
                    affair_id=task.id,
                )
            )
            if not request.force:
                ctx.unplaced.append(
                    UnplacedItem(affair_id=task.id, title=task.title, reason="预算不足")
                )
                continue
        duration = int(task.est_minutes or 30)
        occupied = _occupied_intervals(live_blocks)
        # async_callback: kickoff/review 阶段专用 block_type，work_hours_only 时仅进 work_window
        task_kind = _kind_of(task)
        is_async = task_kind == AffairKind.ASYNC_CALLBACK
        async_meta = task.kind_meta or {} if is_async else {}
        work_only = bool(async_meta.get("work_hours_only", False)) if is_async else False
        cur_phase = async_meta.get("current_phase") if is_async else None
        if is_async:
            # DELEGATED 阶段不排实时窗（应由 informational 块处理，这里跳过）
            if cur_phase == "delegated":
                continue
            block_type = "async_review" if cur_phase == "review" else "async_kickoff"
        else:
            block_type = "focus"
        # 工作窗内部的可排空间（work_window 是容器，focus 排入其中）
        free_in_work = _free_intervals(awake, occupied)
        # work_hours_only 时禁止超窗（async 对外业务回调必须工作时间内进行）
        # work_only 且无工作窗 → 直接 unplaced（不进任意自由区、不超窗）
        if work_only and not work_windows:
            ctx.unplaced.append(
                UnplacedItem(
                    affair_id=task.id, title=task.title,
                    reason="无工作窗模板（work_hours_only 禁止超窗）",
                )
            )
            continue
        candidates = work_windows or None
        placed = _place_in_free(free_in_work, duration, candidates=candidates)
        overtime = False
        if placed is None and work_windows and not work_only:
            # 工作窗放不下 → 超窗排程（侵占可视化）
            free_outside = _free_intervals(awake, occupied, extra_busy=work_windows)
            placed = _place_in_free(free_outside, duration)
            overtime = placed is not None
        elif placed is None and not work_only:
            # 无工作窗模板：清醒窗内任意自由区
            placed = _place_in_free(free_in_work, duration)
        # work_hours_only 且无工作窗/工作窗放不下 → unplaced（不超窗）
        if placed is None and work_only:
            ctx.unplaced.append(
                UnplacedItem(affair_id=task.id, title=task.title, reason="工作窗放不下（work_hours_only 禁止超窗）")
            )
            continue
        if placed is not None:
            ref: Dict[str, Any] = {"label": task.title}
            if overtime:
                ref["overtime"] = True
                ctx.warnings.append(
                    PlanWarning(
                        code="overtime",
                        message=f"「{task.title}」工作窗放不下，超窗排程（侵占可视化）",
                        affair_id=task.id,
                    )
                )
            if is_async:
                ref["phase"] = cur_phase
                ref["round"] = async_meta.get("round", 1)
            ctx.add_block(block_type, placed[0], placed[1], affair=task, ref=ref)
            live_blocks = _existing_blocks(db, day.id)
            # 连续专注上限：超长 focus 后强制插 rest（max_consecutive_focus policy）
            if max_focus_min is not None and duration >= max_focus_min:
                occupied = _occupied_intervals(live_blocks)
                free = _free_intervals(awake, occupied)
                rest_placed = _place_in_free(
                    free, 15,
                    candidates=[(placed[1], placed[1] + timedelta(minutes=60))],
                )
                if rest_placed is not None:
                    ctx.add_block(
                        "rest", rest_placed[0], rest_placed[1],
                        ref={"label": "强制休息(连续专注上限)"},
                    )
                    live_blocks = _existing_blocks(db, day.id)
        else:
            ctx.unplaced.append(UnplacedItem(affair_id=task.id, title=task.title, reason="窗口冲突/精力不足"))

    # ---- domain_cap 校验（域时长上限，如 work≤8h/日；容器块 work_window 不计）----
    if domain_caps:
        final_live = _existing_blocks(db, day.id)
        affair_ids = {b.affair_id for b in final_live if b.affair_id}
        affairs: Dict[int, RhythmAffair] = {}
        if affair_ids:
            for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
                affairs[a.id] = a
        for cap in domain_caps:
            dom = str(cap.get("domain", "work"))
            cap_hours = float(cap.get("hours", 8))
            used = 0
            for b in final_live:
                if b.block_type in ("work_window", "micro_rest", "buffer", "sleep"):
                    continue  # 容器/系统块不计实际占用
                if (b.ref or {}).get("informational"):
                    continue
                if _block_domain(b, affairs.get(b.affair_id) if b.affair_id else None) == dom:
                    used += _minutes((b.start_time, b.end_time))
            if used > cap_hours * 60:
                ctx.warnings.append(
                    PlanWarning(
                        code="domain_cap_exceeded",
                        message=f"{dom} 域当日排程 {used}min 超上限 {cap_hours}h"
                        "（建议 defer 低分块或启用 fallback）",
                    )
                )

    db.commit()

    # ---- Step 8: 产出 ----
    final_blocks = _existing_blocks(db, day.id)
    return PlanDayResponse(
        date=d,
        day_id=day.id,
        plan_version=new_version,
        blocks=blocks_to_response(db, final_blocks),
        warnings=ctx.warnings,
        unplaced=ctx.unplaced,
    )


def _venture_week_minutes(db: Session, venture: RhythmAffair, week_day_ids: List[int]) -> int:
    if not week_day_ids:
        return 0
    child_ids = [
        x.id for x in db.query(RhythmAffair.id).filter(RhythmAffair.parent_id == venture.id).all()
    ]
    ids = [venture.id, *child_ids]
    blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id.in_(week_day_ids),
            RhythmTimeBlock.affair_id.in_(ids),
            RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
        )
        .all()
    )
    return sum(_minutes((b.start_time, b.end_time)) for b in blocks)


def _build_score_context(
    db: Session, d: date, profile: RhythmEnergyProfile, week_day_ids: List[int]
) -> ScoreContext:
    """构建评分上下文（周缺口/剩余天数/三域偏离/能量曲线/工作生活地板参照）"""
    now = _now()
    habits = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.HABIT.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    habit_ids = [h.id for h in habits]
    week_done: Dict[int, int] = {hid: 0 for hid in habit_ids}
    if habit_ids:
        from sail_server.infrastructure.orm.rhythm import RhythmDisciplineLog

        monday, sunday = week_range(d)
        logs = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id.in_(habit_ids),
                RhythmDisciplineLog.result == "done",
                RhythmDisciplineLog.log_date >= monday,
                RhythmDisciplineLog.log_date <= sunday,
            )
            .all()
        )
        for log in logs:
            week_done[log.affair_id] = week_done.get(log.affair_id, 0) + 1

    week_planned: Dict[int, int] = {hid: 0 for hid in habit_ids}
    if habit_ids and week_day_ids:
        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id.in_(week_day_ids),
                RhythmTimeBlock.affair_id.in_(habit_ids),
                RhythmTimeBlock.block_type == "habit",
                RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
            )
            .all()
        )
        for b in blocks:
            week_planned[b.affair_id] = week_planned.get(b.affair_id, 0) + 1

    curve_cfg = profile.curve_template or {}
    curve = curve_cfg.get("weekday" if d.weekday() < 5 else "weekend") or [0.5] * 24

    weights = dict(DEFAULT_SCORE_WEIGHTS)
    weights.update(profile.score_weights or {})

    ctx = ScoreContext(
        now=now,
        target_date=d,
        week_done_counts=week_done,
        week_planned_counts=week_planned,
        remaining_days_in_week=max(7 - d.weekday(), 1),
        domain_boost=compute_domain_boost(db, profile, d),
        curve=list(curve),
        weights=weights,
    )

    # 生活地板参照：当日 work/career 竞争事务的最高分
    tasks = _collect_competing_tasks(db, d, ctx, compute_scores=False)
    max_wc = 0.0
    for task, _ in tasks:
        s = compute_score(task, ctx)
        if s > max_wc:
            max_wc = s
    ctx.max_work_career_score = max_wc
    return ctx


def _collect_competing_tasks(
    db: Session, d: date, ctx: ScoreContext, compute_scores: bool = True
) -> List[Tuple[RhythmAffair, float]]:
    """收集当日竞争工作任务（task_oneoff PLANNED 窗口覆盖 + task_maintenance due）"""
    day_start = datetime.combine(d, time.min)
    day_end = day_start + timedelta(days=1)
    tasks: List[RhythmAffair] = []

    oneoffs = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.TASK_ONEOFF.value,
            RhythmAffair.state == AffairState.PLANNED.value,
        )
        .all()
    )
    for t in oneoffs:
        if t.window_start is not None and t.window_start >= day_end:
            continue
        if t.window_end is not None and t.window_end < day_start:
            continue
        # 当日已有该事务块 → 不再重复竞争
        dup = (
            db.query(RhythmTimeBlock)
            .join(Day, Day.id == RhythmTimeBlock.day_id)
            .filter(
                Day.date == d,
                RhythmTimeBlock.affair_id == t.id,
                RhythmTimeBlock.status != "MOVED",
            )
            .first()
        )
        if dup is not None:
            continue
        tasks.append(t)

    maints = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.TASK_MAINTENANCE.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    now = ctx.now
    for m in maints:
        meta = m.kind_meta or {}
        interval = float(meta.get("interval_days") or 7)
        last_done = meta.get("last_done_at")
        due = True
        if last_done:
            if isinstance(last_done, str):
                last_done = datetime.fromisoformat(last_done)
            due = (now - last_done).total_seconds() / 86400.0 >= max(interval - 1, 0)
        if not due:
            continue
        dup = (
            db.query(RhythmTimeBlock)
            .join(Day, Day.id == RhythmTimeBlock.day_id)
            .filter(
                Day.date == d,
                RhythmTimeBlock.affair_id == m.id,
                RhythmTimeBlock.status != "MOVED",
            )
            .first()
        )
        if dup is not None:
            continue
        tasks.append(m)

    # async_callback 的 kickoff(ACTIVE) / review(REVIEWING) 阶段需排实时窗
    asyncs = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.ASYNC_CALLBACK.value,
            RhythmAffair.state.in_([
                AffairState.ACTIVE.value,
                AffairState.REVIEWING.value,
            ]),
        )
        .all()
    )
    for a in asyncs:
        # 窗口过滤（与 oneoff 同口径）
        if a.window_start is not None and a.window_start >= day_end:
            continue
        if a.window_end is not None and a.window_end < day_start:
            continue
        dup = (
            db.query(RhythmTimeBlock)
            .join(Day, Day.id == RhythmTimeBlock.day_id)
            .filter(
                Day.date == d,
                RhythmTimeBlock.affair_id == a.id,
                RhythmTimeBlock.status != "MOVED",
            )
            .first()
        )
        if dup is not None:
            continue
        tasks.append(a)

    scored = [(t, compute_score(t, ctx)) for t in tasks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def rebalance_impl(db: Session, request: RebalanceRequest) -> PlanDayResponse:
    """再平衡：defer/新事务插入/超时后增量重跑 plan_day

    pinned 块与 DONE/DOING 块冻结；旧 PLANNED 非 pinned 块置 MOVED（diff 可由
    plan_version 推导：新版本块 vs MOVED 块）。
    """
    return plan_day_impl(db, PlanDayRequest(date=request.date, preserve_done=True))


# ============================================================================
# §5.5 侵占检测
# ============================================================================


def detect_conflicts_impl(db: Session, d: date) -> List[EncroachmentItem]:
    """当日侵占检测报告"""
    day = db.query(Day).filter(Day.date == d).first()
    if day is None:
        return []
    blocks = _existing_blocks(db, day.id)
    profile = get_or_create_profile(db)
    policies = (
        db.query(RhythmPolicy).filter(RhythmPolicy.enabled.is_(True)).all()
    )
    out: List[EncroachmentItem] = []

    affair_ids = {b.affair_id for b in blocks if b.affair_id}
    affairs: Dict[int, RhythmAffair] = {}
    if affair_ids:
        for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
            affairs[a.id] = a

    # 1. protect_window 禁排窗被工作/事业块穿透
    for policy in policies:
        if policy.rule_type != "protect_window":
            continue
        params = policy.params or {}
        st = _parse_hhmm(params.get("start", "22:00"), "22:00")
        et = _parse_hhmm(params.get("end", "23:59"), "23:59")
        win: Interval = (datetime.combine(d, st), datetime.combine(d, et))
        for b in blocks:
            if b.block_type in ("sleep", "buffer", "micro_rest"):
                continue
            affair = affairs.get(b.affair_id) if b.affair_id else None
            dom = _block_domain(b, affair)
            if dom not in ("work", "career"):
                continue
            if _overlap((b.start_time, b.end_time), win):
                out.append(
                    EncroachmentItem(
                        type="protect_window_violation",
                        message=f"{b.block_type} 块 ({b.start_time:%H:%M}-{b.end_time:%H:%M}) "
                        f"穿透守护窗「{policy.name}」({params.get('start')}-{params.get('end')})",
                        block_id=b.id,
                        affair_id=b.affair_id,
                        date=d,
                    )
                )

    # 2. career 块越界进非业余时间区
    spare_cfg = profile.spare_time_windows or {}
    spare_key = "weekday" if d.weekday() < 5 else "weekend"
    spare_windows: List[Interval] = []
    for rng in spare_cfg.get(spare_key, []):
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            spare_windows.append(
                (
                    datetime.combine(d, _parse_hhmm(rng[0], "19:30")),
                    datetime.combine(d, _parse_hhmm(rng[1], "22:30")),
                )
            )
    # spare_time_guard 默认启用（§4.1 policies）；显式禁用 policy 才跳过
    guard_enabled = True
    for p in policies:
        if p.rule_type == "spare_time_guard" and not p.enabled:
            guard_enabled = False
            break
    if guard_enabled:
        for b in blocks:
            if b.block_type != "career":
                continue
            # 无业余时间区配置时，career 块只要存在即越界
            fully_inside = any(
                b.start_time >= w[0] and b.end_time <= w[1] for w in spare_windows
            )
            if not fully_inside:
                out.append(
                    EncroachmentItem(
                        type="career_out_of_spare",
                        message=f"事业块 ({b.start_time:%H:%M}-{b.end_time:%H:%M}) 越出业余时间区",
                        block_id=b.id,
                        affair_id=b.affair_id,
                        date=d,
                    )
                )

    # 3. 刚性块被挤（非 pinned 块与 fixed 钉重叠）
    fixed_blocks = [b for b in blocks if b.block_type == "fixed" and b.pinned]
    for fb in fixed_blocks:
        for b in blocks:
            if b.id == fb.id or b.pinned or (b.ref or {}).get("informational"):
                continue
            if _overlap((b.start_time, b.end_time), (fb.start_time, fb.end_time)):
                out.append(
                    EncroachmentItem(
                        type="fixed_conflict",
                        message=f"块 #{b.id} ({b.block_type}) 与刚性钉「"
                        f"{(fb.ref or {}).get('label', 'fixed')}」重叠",
                        block_id=b.id,
                        affair_id=b.affair_id,
                        date=d,
                    )
                )

    # 4. 加班（overtime 标记块）
    for b in blocks:
        if (b.ref or {}).get("overtime"):
            out.append(
                EncroachmentItem(
                    type="overtime",
                    message=f"「{(b.ref or {}).get('label', '')}」超窗加班 "
                    f"({b.start_time:%H:%M}-{b.end_time:%H:%M})",
                    block_id=b.id,
                    affair_id=b.affair_id,
                    date=d,
                )
            )
    return out


# ============================================================================
# 时间线查询
# ============================================================================


def _block_domain(block: RhythmTimeBlock, affair: Optional[RhythmAffair]) -> str:
    """块归属域：有事务按事务域；无事务按块类型默认映射"""
    if affair is not None and affair.domain:
        return affair.domain
    if block.block_type == "work_window":
        return "work"
    if block.block_type == "career":
        return "career"
    return "life"


def get_day_timeline_impl(db: Session, d: date, with_checkins: bool = True) -> DayTimelineResponse:
    day = _get_or_create_day(db, d)
    profile = get_or_create_profile(db)
    blocks = _existing_blocks(db, day.id)

    affair_ids = {b.affair_id for b in blocks if b.affair_id}
    affairs: Dict[int, RhythmAffair] = {}
    if affair_ids:
        for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
            affairs[a.id] = a

    domain_minutes = DomainMinutes()
    energy_consumed = 0
    for b in blocks:
        if b.status not in ("PLANNED", "DOING", "DONE"):
            continue
        affair = affairs.get(b.affair_id) if b.affair_id else None
        dom = _block_domain(b, affair)
        setattr(domain_minutes, dom, getattr(domain_minutes, dom) + _minutes((b.start_time, b.end_time)))
        if b.status == "DONE" and affair is not None:
            energy_consumed += affair.energy_cost or 0

    buffer_blocks = [b for b in blocks if b.block_type == "buffer" and b.status != "MOVED"]
    buffer_total = sum(_minutes((b.start_time, b.end_time)) for b in buffer_blocks)
    others = [
        (b.start_time, b.end_time)
        for b in blocks
        if b.block_type != "buffer" and not (b.ref or {}).get("informational")
    ]
    buffer_free = 0
    for bb in buffer_blocks:
        free_parts: List[Interval] = [(bb.start_time, bb.end_time)]
        for occ in others:
            free_parts = _subtract(free_parts, occ)
        buffer_free += sum(_minutes(iv) for iv in free_parts)

    plan_version = max([b.plan_version or 1 for b in blocks], default=0)
    checkins: Optional[CheckinTodayResponse] = (
        today_checkins_impl(db, d) if with_checkins else None
    )

    return DayTimelineResponse(
        date=d,
        day_id=day.id,
        plan_version=plan_version,
        blocks=blocks_to_response(db, blocks),
        domain_minutes=domain_minutes,
        energy_consumed=energy_consumed,
        energy_budget=int(profile.daily_energy_budget or 100),
        buffer_total_minutes=buffer_total,
        buffer_free_minutes=buffer_free,
        checkins=checkins,
        warnings=[],
    )


# ============================================================================
# §5.6 节奏评分（Review）
# ============================================================================


def _compute_review_for_range(
    db: Session, start: date, end: date, scope: str, period_key: str
) -> ReviewResponse:
    """计算 [start, end] 区间的节奏评分"""
    from sail_server.infrastructure.orm.rhythm import RhythmDisciplineLog

    profile = get_or_create_profile(db)
    day_ids = [
        row.id for row in db.query(Day.id).filter(Day.date >= start, Day.date <= end).all()
    ]
    blocks: List[RhythmTimeBlock] = []
    if day_ids:
        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id.in_(day_ids),
                RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
            )
            .all()
        )
    affair_ids = {b.affair_id for b in blocks if b.affair_id}
    affairs: Dict[int, RhythmAffair] = {}
    if affair_ids:
        for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
            affairs[a.id] = a

    # 三域投入
    domain_minutes = {"life": 0, "work": 0, "career": 0}
    for b in blocks:
        dom = _block_domain(b, affairs.get(b.affair_id) if b.affair_id else None)
        domain_minutes[dom] += _minutes((b.start_time, b.end_time))

    # 戒律合规率 = kept/(kept+violated)
    precept_ids = [
        a.id
        for a in db.query(RhythmAffair)
        .filter(RhythmAffair.kind == AffairKind.PRECEPT.value)
        .all()
    ]
    kept = violated = 0
    if precept_ids:
        logs = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id.in_(precept_ids),
                RhythmDisciplineLog.log_date >= start,
                RhythmDisciplineLog.log_date <= end,
            )
            .all()
        )
        kept = sum(1 for x in logs if x.result == "kept")
        violated = sum(1 for x in logs if x.result == "violated")
    precept_rate = kept / (kept + violated) if (kept + violated) > 0 else 1.0

    # 睡眠窗守约（hard precept 中睡眠相关：rule_text 含「睡」或 check_time>=22:00）
    sleep_kept = sleep_violated = 0
    if precept_ids:
        sleep_precepts = (
            db.query(RhythmAffair)
            .filter(
                RhythmAffair.kind == AffairKind.PRECEPT.value,
                RhythmAffair.state.in_([AffairState.ACTIVE.value, AffairState.PAUSED.value]),
            )
            .all()
        )
        def _is_sleep_precept(a: RhythmAffair) -> bool:
            meta = a.kind_meta or {}
            if meta.get("severity") != "hard":
                return False
            rule_text = str(meta.get("rule_text", ""))
            if "睡" in rule_text or "sleep" in rule_text.lower():
                return True
            # check_time 在睡眠窗内（22:00 次日 07:00）也视作睡眠戒律
            try:
                h, _ = str(meta.get("check_time", "22:30")).split(":")[:2]
                return int(h) >= 22 or int(h) < 7
            except (ValueError, IndexError):
                return False

        sleep_ids = [a.id for a in sleep_precepts if _is_sleep_precept(a)]
        if sleep_ids:
            sleep_logs = (
                db.query(RhythmDisciplineLog)
                .filter(
                    RhythmDisciplineLog.affair_id.in_(sleep_ids),
                    RhythmDisciplineLog.log_date >= start,
                    RhythmDisciplineLog.log_date <= end,
                )
                .all()
            )
            sleep_kept = sum(1 for x in sleep_logs if x.result == "kept")
            sleep_violated = sum(1 for x in sleep_logs if x.result == "violated")
    sleep_keeping = (
        sleep_kept / (sleep_kept + sleep_violated)
        if (sleep_kept + sleep_violated) > 0
        else 1.0
    )

    # 习惯达标率
    habits = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.HABIT.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    habit_ratios: List[float] = []
    for h in habits:
        freq = int((h.kind_meta or {}).get("freq_per_week") or 3)
        # 含首尾日的周数（Mon..Sun = 7 天 = 1 周）
        weeks = max(((end - start).days + 1) / 7.0, 1 / 7)
        # target 用真实计算值，不再 floor 到 1：避免"1 次达成即满分"高估
        target = freq * weeks
        done = (
            db.query(RhythmDisciplineLog)
            .filter(
                RhythmDisciplineLog.affair_id == h.id,
                RhythmDisciplineLog.result == "done",
                RhythmDisciplineLog.log_date >= start,
                RhythmDisciplineLog.log_date <= end,
            )
            .count()
        )
        habit_ratios.append(min(done / target, 1.0))
    habit_consistency = (
        sum(habit_ratios) / len(habit_ratios) if habit_ratios else 1.0
    )

    # 事业周预算达成率
    ventures = (
        db.query(RhythmAffair)
        .filter(
            RhythmAffair.kind == AffairKind.VENTURE.value,
            RhythmAffair.state == AffairState.ACTIVE.value,
        )
        .all()
    )
    venture_fulfillment = 0.0
    if ventures:
        budget_min = sum(
            float((v.kind_meta or {}).get("weekly_budget_hours") or 0.0) * 60
            for v in ventures
        )
        weeks = max(((end - start).days + 1) / 7.0, 1 / 7)
        budget_min *= weeks
        career_min = domain_minutes["career"]
        venture_fulfillment = (
            min(career_min / budget_min, 1.2) if budget_min > 0 else 0.0
        )

    # 缓冲消耗
    buffer_blocks = [b for b in blocks if b.block_type == "buffer"]
    buffer_total = sum(_minutes((b.start_time, b.end_time)) for b in buffer_blocks)
    buffer_free = 0
    others = [
        (b.start_time, b.end_time)
        for b in blocks
        if b.block_type != "buffer" and not (b.ref or {}).get("informational")
    ]
    for bb in buffer_blocks:
        free_parts: List[Interval] = [(bb.start_time, bb.end_time)]
        for occ in others:
            free_parts = _subtract(free_parts, occ)
        buffer_free += sum(_minutes(iv) for iv in free_parts)
    buffer_consumed = (
        (buffer_total - buffer_free) / buffer_total if buffer_total > 0 else 0.0
    )

    # 三域偏离度
    weights = {
        "life": float(profile.life_weight or 1.0),
        "work": float(profile.work_weight or 1.0),
        "career": float(profile.career_weight or 0.6),
    }
    w_total = sum(weights.values()) or 1.0
    total_min = sum(domain_minutes.values())
    deviation = 0.0
    if total_min > 0:
        for dom in ("life", "work", "career"):
            deviation += abs(domain_minutes[dom] / total_min - weights[dom] / w_total)
        deviation /= 2.0  # 归一化到 0..1

    # 综合评分（无 ACTIVE venture 时事业权重并入三域偏离项）
    if ventures:
        score = (
            0.25 * precept_rate
            + 0.20 * habit_consistency
            + 0.15 * sleep_keeping
            + 0.15 * (1 - deviation)
            + 0.15 * min(venture_fulfillment, 1.0)
            + 0.10 * (1 - buffer_consumed)
        )
    else:
        score = (
            0.25 * precept_rate
            + 0.20 * habit_consistency
            + 0.15 * sleep_keeping
            + 0.30 * (1 - deviation)
            + 0.10 * (1 - buffer_consumed)
        )

    # 侵占事件（区间内逐日聚合，日评仅当日）
    encroachments: List[Dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        for item in detect_conflicts_impl(db, cursor):
            encroachments.append(item.model_dump(mode="json"))
        cursor += timedelta(days=1)

    return ReviewResponse(
        scope=scope,
        period_key=period_key,
        rhythm_score=round(score * 100, 2),
        domain_minutes=domain_minutes,
        precept_compliance_rate=round(precept_rate, 4),
        habit_consistency=round(habit_consistency, 4),
        sleep_window_keeping=round(sleep_keeping, 4),
        venture_budget_fulfillment=round(venture_fulfillment, 4),
        buffer_consumed=round(buffer_consumed, 4),
        encroachments=encroachments,
    )


def _save_review(db: Session, resp: ReviewResponse) -> RhythmReview:
    row = (
        db.query(RhythmReview)
        .filter(
            RhythmReview.scope == resp.scope,
            RhythmReview.period_key == resp.period_key,
        )
        .first()
    )
    if row is None:
        row = RhythmReview(scope=resp.scope, period_key=resp.period_key)
        db.add(row)
    row.rhythm_score = resp.rhythm_score
    row.domain_minutes = resp.domain_minutes
    row.precept_compliance_rate = resp.precept_compliance_rate
    row.habit_consistency = resp.habit_consistency
    row.sleep_window_keeping = resp.sleep_window_keeping
    row.venture_budget_fulfillment = resp.venture_budget_fulfillment
    row.buffer_consumed = resp.buffer_consumed
    row.encroachments = resp.encroachments
    db.commit()
    db.refresh(row)
    return row


def get_day_review_impl(db: Session, d: date, persist: bool = True) -> ReviewResponse:
    """日评分（无则即时计算并落库）"""
    resp = _compute_review_for_range(db, d, d, "day", d.isoformat())
    if persist:
        row = _save_review(db, resp)
        resp.id = row.id
        resp.ai_summary = row.ai_summary or ""
        resp.created_at = row.created_at
    return resp


def _to_priority_items(
    affairs: List[Any], reason_template: str
) -> List[PriorityAffairItem]:
    """将 AffairResponse 列表包装为 PriorityAffairItem（兼容 ORM/Response 对象）"""
    out: List[PriorityAffairItem] = []
    for a in affairs:
        resp = affair_to_response(a) if isinstance(a, RhythmAffair) else a
        suggested: Optional[str] = None
        meta = resp.kind_meta or {}
        if resp.kind == AffairKind.HABIT.value and meta.get("preferred_slots"):
            suggested = meta["preferred_slots"][0]
        out.append(
            PriorityAffairItem(
                affair=resp,
                reason=reason_template,
                suggested_slot=suggested,
            )
        )
    return out


def get_dashboard_impl(db: Session, d: date) -> RhythmDashboardResponse:
    """Dashboard 与 Android 提醒端共享的聚合入口。

    一次性返回当日时间线、日/周评分、待打卡、精力画像、策略、冲突、
    以及 INBOX / 逾期 / 今日截止三类优先级事务摘要。
    """
    timeline = get_day_timeline_impl(db, d)
    day_review = get_day_review_impl(db, d)
    week_review = get_week_review_impl(db, d)
    checkins = today_checkins_impl(db, d)
    profile = get_energy_profile_impl(db)
    policies = list_policies_impl(db, enabled_only=True)
    conflicts = ConflictReportResponse(date=d, encroachments=detect_conflicts_impl(db, d))

    # INBOX 摘要：所有 kind 的 INBOX 非终态事务
    inbox_affairs = list_affairs_impl(
        db, state=AffairState.INBOX.value, limit=50
    )
    inbox_summary = _to_priority_items(inbox_affairs, "INBOX 待分拣")

    # 逾期摘要：ddl < now 且未终态
    now = _now()
    overdue_affairs = list_affairs_impl(
        db,
        urgency_ddl_before=now,
        limit=50,
    )
    overdue_summary = [
        item
        for item in _to_priority_items(overdue_affairs, "已逾期")
        if item.affair.state not in TERMINAL_STATES
    ]

    # 今日截止摘要：ddl 落在当日内
    day_start = datetime.combine(d, time.min)
    day_end = day_start + timedelta(days=1)
    today_due_affairs = list_affairs_impl(
        db,
        urgency_ddl_after=day_start,
        urgency_ddl_before=day_end,
        limit=50,
    )
    today_due_summary = _to_priority_items(today_due_affairs, "今日截止")

    return RhythmDashboardResponse(
        date=d,
        timeline=timeline,
        day_review=day_review,
        week_review=week_review,
        today_checkins=checkins,
        energy_profile=profile,
        policies=policies,
        conflicts=conflicts,
        inbox_summary=inbox_summary,
        overdue_summary=overdue_summary,
        today_due_summary=today_due_summary,
    )
def get_week_review_impl(
    db: Session, span: Optional[Union[str, date]] = None, persist: bool = True
) -> ReviewResponse:
    """周评分。span 支持 W2026-44 或日期（取所在周）；缺省为本周。"""
    if span:
        if isinstance(span, date):
            monday, _ = week_range(span)
            period_key = week_cycle_key(span)
        else:
            s = span.strip()
            if s.upper().startswith("W") and "-" in s:
                try:
                    year = int(s[1:].split("-")[0])
                    week = int(s.split("-")[1])
                    monday = date.fromisocalendar(year, week, 1)
                    period_key = f"W{year}-{week:02d}"
                except (ValueError, IndexError) as e:
                    raise RhythmBadRequestError(f"非法周键 {span!r}，应为 W2026-44 格式: {e}")
            else:
                try:
                    d = date.fromisoformat(s[:10])
                except ValueError as e:
                    raise RhythmBadRequestError(f"非法日期 {span!r}: {e}")
                monday, _ = week_range(d)
                period_key = week_cycle_key(d)
    else:
        monday, _ = week_range(_today())
        period_key = week_cycle_key(_today())
    sunday = monday + timedelta(days=6)

    resp = _compute_review_for_range(db, monday, sunday, "week", period_key)
    if persist:
        row = _save_review(db, resp)
        resp.id = row.id
        resp.ai_summary = row.ai_summary or ""
        resp.created_at = row.created_at
    return resp


def update_review_summary_impl(
    db: Session, scope: str, period_key: str, ai_summary: str
) -> Optional[ReviewResponse]:
    """Agent 写回周评语"""
    row = (
        db.query(RhythmReview)
        .filter(
            RhythmReview.scope == scope,
            RhythmReview.period_key == period_key,
        )
        .first()
    )
    if row is None:
        return None
    row.ai_summary = ai_summary
    db.commit()
    db.refresh(row)
    return ReviewResponse(
        id=row.id,
        scope=row.scope,
        period_key=row.period_key,
        rhythm_score=float(row.rhythm_score or 0),
        domain_minutes=row.domain_minutes or {},
        precept_compliance_rate=float(row.precept_compliance_rate or 0),
        habit_consistency=float(row.habit_consistency or 0),
        sleep_window_keeping=float(row.sleep_window_keeping or 0),
        venture_budget_fulfillment=float(row.venture_budget_fulfillment or 0),
        buffer_consumed=float(row.buffer_consumed or 0),
        encroachments=row.encroachments or [],
        ai_summary=row.ai_summary or "",
        created_at=row.created_at,
    )


def list_encroachments_impl(
    db: Session, start: Optional[date] = None, end: Optional[date] = None
) -> List[EncroachmentItem]:
    """侵占事件列表（默认最近 7 天，逐日检测）"""
    end = end or _today()
    start = start or (end - timedelta(days=7))
    out: List[EncroachmentItem] = []
    cursor = start
    while cursor <= end:
        out.extend(detect_conflicts_impl(db, cursor))
        cursor += timedelta(days=1)
    return out
def get_habit_heatmap_impl(
    db: Session, affair_id: int, start_date: date, end_date: date
) -> HabitHeatmapResponse:
    """habit/precept 在日期范围内的每日打卡结果矩阵。"""
    from sail_server.infrastructure.orm.rhythm import RhythmDisciplineLog

    if start_date > end_date:
        raise RhythmBadRequestError("start_date 不能晚于 end_date")

    logs = (
        db.query(RhythmDisciplineLog)
        .filter(
            RhythmDisciplineLog.affair_id == affair_id,
            RhythmDisciplineLog.log_date >= start_date,
            RhythmDisciplineLog.log_date <= end_date,
        )
        .order_by(RhythmDisciplineLog.log_date)
        .all()
    )
    log_by_date = {log.log_date: log for log in logs}

    days: List[HabitHeatmapItem] = []
    cursor = start_date
    while cursor <= end_date:
        log = log_by_date.get(cursor)
        days.append(
            HabitHeatmapItem(
                date=cursor,
                cycle_key=log.cycle_key if log else cursor.isoformat(),
                result=CheckinResult(log.result) if log else None,
                done=log is not None and log.result == CheckinResult.DONE.value,
            )
        )
        cursor += timedelta(days=1)

    return HabitHeatmapResponse(
        affair_id=affair_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


def get_domain_trend_impl(
    db: Session, start_date: date, end_date: date
) -> DomainTrendResponse:
    """按天返回三域投入分钟数（最近 N 天趋势）。"""
    if start_date > end_date:
        raise RhythmBadRequestError("start_date 不能晚于 end_date")

    days_map: Dict[date, DomainTrendItem] = {}
    cursor = start_date
    while cursor <= end_date:
        days_map[cursor] = DomainTrendItem(date=cursor)
        cursor += timedelta(days=1)

    day_rows = (
        db.query(Day)
        .filter(Day.date >= start_date, Day.date <= end_date)
        .all()
    )
    day_ids = [d.id for d in day_rows]

    if day_ids:
        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id.in_(day_ids),
                RhythmTimeBlock.status.in_(["PLANNED", "DOING", "DONE"]),
            )
            .all()
        )
        block_day_ids = {b.day_id for b in blocks}
        date_by_day_id = {d.id: d.date for d in day_rows if d.id in block_day_ids}
        affair_ids = {b.affair_id for b in blocks if b.affair_id}
        affairs: Dict[int, RhythmAffair] = {}
        if affair_ids:
            for a in db.query(RhythmAffair).filter(RhythmAffair.id.in_(affair_ids)).all():
                affairs[a.id] = a

        for b in blocks:
            d = date_by_day_id.get(b.day_id)
            if d is None:
                continue
            dom = _block_domain(b, affairs.get(b.affair_id) if b.affair_id else None)
            item = days_map.get(d)
            if item is not None:
                setattr(item, dom, getattr(item, dom) + _minutes((b.start_time, b.end_time)))

    return DomainTrendResponse(
        start_date=start_date,
        end_date=end_date,
        days=list(days_map.values()),
    )


def get_venture_burndown_impl(
    db: Session, venture_id: int
) -> VentureBurndownResponse:
    """长期事业燃尽图：每周计划/实际投入小时 + 里程碑完成数。"""
    from sail_server.model.rhythm import _get_affair_or_404, _kind_of

    venture = _get_affair_or_404(db, venture_id)
    if _kind_of(venture) != AffairKind.VENTURE:
        raise RhythmBadRequestError("仅 venture 支持燃尽图")

    child_ids = [
        x.id for x in db.query(RhythmAffair.id).filter(RhythmAffair.parent_id == venture_id).all()
    ]
    affair_ids = [venture_id, *child_ids]
    blocks = (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.affair_id.in_(affair_ids),
            RhythmTimeBlock.status != "MOVED",
        )
        .order_by(RhythmTimeBlock.start_time)
        .all()
    )

    weekly_planned: Dict[str, float] = {}
    weekly_actual: Dict[str, float] = {}
    for b in blocks:
        if b.start_time is None:
            continue
        iso = b.start_time.isocalendar()
        week_key = f"W{iso[0]}-{iso[1]:02d}"
        hours = _minutes((b.start_time, b.end_time)) / 60.0
        weekly_planned[week_key] = weekly_planned.get(week_key, 0.0) + hours
        if b.status == "DONE":
            weekly_actual[week_key] = weekly_actual.get(week_key, 0.0) + hours

    milestones = (
        db.query(RhythmAffair)
        .filter(RhythmAffair.parent_id == venture_id)
        .all()
    )
    weekly_milestones: Dict[str, int] = {}
    for m in milestones:
        if m.state == AffairState.DONE.value and m.mtime:
            iso = m.mtime.isocalendar()
            week_key = f"W{iso[0]}-{iso[1]:02d}"
            weekly_milestones[week_key] = weekly_milestones.get(week_key, 0) + 1

    weeks = sorted(set(weekly_planned.keys()) | set(weekly_actual.keys()) | set(weekly_milestones.keys()))
    return VentureBurndownResponse(
        affair_id=venture_id,
        title=venture.title,
        weeks=weeks,
        planned=[round(weekly_planned.get(w, 0.0), 2) for w in weeks],
        actual=[round(weekly_actual.get(w, 0.0), 2) for w in weeks],
        milestones_done=[weekly_milestones.get(w, 0) for w in weeks],
    )