# -*- coding: utf-8 -*-
# @file rhythm_scheduler.py
# @brief Rhythm 排程内核 v2（纯算法：有效工作窗 / 早间健康窗 / 职业缓冲 / focus 间隙预留 / best-fit / 拆分）
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
排程器 v2 纯算法层（不触 DB、不 import model.rhythm / model.rhythm_planner，
仅依赖 stdlib，保证可独立测试）。

设计文档: doc/design/sail_server/manager/rhythm.md §4.4
对应 ADR:
- 有效工作窗权威 = profile.work_windows > 模板 work_window 槽位 > 空
- 工作任务（work 域）只能排入有效工作窗（force=true 逃生舱除外）
- 同一片段内相邻 focus 块之间保留 work_gap_minutes 间隙（虚拟预留 → 物化 rest）
- 可拆分任务跨片段拆分，每段 ≥ min_chunk_minutes
- 多片段候选时按精力曲线 best-fit（片段起始小时），同分取最早（确定性）
- 事业块 end ≤ sleep_start - career_buffer_minutes

plan_day_impl 负责 DB 编排与块物化；本模块只操作区间。
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

Interval = Tuple[datetime, datetime]


# ============================================================================
# 区间基础工具
# ============================================================================


def overlap(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def subtract(free: List[Interval], busy: Interval) -> List[Interval]:
    """从 free 区间集中扣除 busy"""
    out: List[Interval] = []
    for s, e in free:
        if not overlap((s, e), busy):
            out.append((s, e))
            continue
        if s < busy[0]:
            out.append((s, min(e, busy[0])))
        if busy[1] < e:
            out.append((max(s, busy[1]), e))
    return [(s, e) for s, e in out if s < e]


def minutes_of(iv: Interval) -> int:
    return int((iv[1] - iv[0]).total_seconds() // 60)


def parse_hhmm(v: Any, default: str) -> time:
    try:
        h, m = str(v or default).split(":")[:2]
        return time(int(h), int(m))
    except Exception:
        h, m = default.split(":")
        return time(int(h), int(m))


def clip_to_candidates(free: List[Interval], candidates: List[Interval]) -> List[Interval]:
    """free ∩ candidates（切出候选窗内的自由片段）"""
    out: List[Interval] = []
    for c in candidates:
        for f in free:
            s, e = max(c[0], f[0]), min(c[1], f[1])
            if s < e:
                out.append((s, e))
    out.sort()
    return out


# ============================================================================
# 配置解析（profile → 当日区间）
# ============================================================================


def resolve_work_windows(
    profile_work_windows: Optional[Dict[str, Any]],
    template_windows: List[Interval],
    d: date,
) -> List[Interval]:
    """有效工作窗基准（未扣除占用）。

    权威优先级: profile.work_windows[weekday|weekend] > 模板 work_window 槽位 > 空。
    """
    key = "weekday" if d.weekday() < 5 else "weekend"
    out: List[Interval] = []
    cfg = profile_work_windows or {}
    for rng in cfg.get(key) or []:
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            st = parse_hhmm(rng[0], "10:00")
            et = parse_hhmm(rng[1], "19:00")
            s, e = datetime.combine(d, st), datetime.combine(d, et)
            if s < e:
                out.append((s, e))
    if out:
        return sorted(out)
    return sorted(template_windows)


def resolve_morning_window(
    morning_cfg: Optional[Dict[str, Any]], sleep_end_t: time, d: date
) -> List[Interval]:
    """早间健康窗 = [max(sleep_end, cfg.start), cfg.end)，供健康类 habit 优先落位。"""
    cfg = morning_cfg or {}
    start_t = parse_hhmm(cfg.get("start"), "07:00")
    end_t = parse_hhmm(cfg.get("end"), "10:00")
    s = max(datetime.combine(d, sleep_end_t), datetime.combine(d, start_t))
    e = datetime.combine(d, end_t)
    return [(s, e)] if s < e else []


def clip_by_career_buffer(
    spare_windows: List[Interval], sleep_start_dt: datetime, buffer_min: int
) -> List[Interval]:
    """业余窗按睡前缓冲截断：end ≤ sleep_start - buffer_min"""
    if buffer_min <= 0:
        return sorted(spare_windows)
    latest = sleep_start_dt - timedelta(minutes=buffer_min)
    out = [(s, min(e, latest)) for s, e in spare_windows]
    return sorted([(s, e) for s, e in out if s < e])


# ============================================================================
# 占用扣除（Step 2.5）
# ============================================================================


def compute_effective_windows(
    base_windows: List[Interval], occupancy_intervals: List[Interval]
) -> List[Interval]:
    """有效工作片段 = 基准工作窗 - 占用块（请假/会议等 occupied 块）"""
    out: List[Interval] = list(base_windows)
    for occ in occupancy_intervals:
        out = subtract(out, occ)
    out.sort()
    return out


def is_full_day_leave(
    occupancy_blocks: List[Any], effective_windows: List[Interval]
) -> bool:
    """整日请假/占用语义：占用块清空了全部有效工作窗，且其中含 leave/whole_day。"""
    if effective_windows or not occupancy_blocks:
        return False
    for b in occupancy_blocks:
        ref = getattr(b, "ref", None) or {}
        if ref.get("whole_day") or ref.get("occupancy_type") == "leave":
            return True
    return False


# ============================================================================
# focus 落位（best-fit / 拆分 / 间隙预留）
# ============================================================================


def order_segments_by_curve(
    segments: List[Interval], curve: Optional[List[float]]
) -> List[Interval]:
    """best-fit：按片段起始小时的精力系数降序，同分取最早（保持确定性）。

    无曲线时直接按时间升序（等价旧 first-fit 语义）。
    """
    if not curve:
        return sorted(segments)
    def _fit(iv: Interval) -> float:
        h = min(max(iv[0].hour, 0), 23)
        try:
            return float(curve[h])
        except (IndexError, TypeError):
            return 0.0
    return sorted(segments, key=lambda iv: (-_fit(iv), iv[0]))


def place_single(
    segments_ordered: List[Interval], duration_min: int
) -> Optional[Tuple[Interval, Interval]]:
    """在（已排序的）片段中找首个能容纳 duration 的位置，片段内最早落位。

    Returns:
        (placement, segment) 或 None
    """
    for seg in segments_ordered:
        if minutes_of(seg) >= duration_min:
            return (seg[0], seg[0] + timedelta(minutes=duration_min)), seg
    return None


def plan_split(
    segments: List[Interval],
    duration_min: int,
    gap_min: int,
    chunk_min: int,
) -> Optional[List[Tuple[Interval, Interval]]]:
    """可拆分任务跨片段规划（纯函数，不修改输入）。

    规则：
    - 每段 ≥ chunk_min（唯一例外：任务整体单段可放下时不受 chunk_min 限制）
    - 同片段连续两块之间扣掉 gap（跨片段本身已有自然间隔，不额外要求）
    - 片段用尽仍剩 → None
    """
    if duration_min <= 0:
        return None
    sim: List[Interval] = list(segments)
    remaining = duration_min
    out: List[Tuple[Interval, Interval]] = []
    while remaining > 0:
        progressed = False
        for idx, seg in enumerate(list(sim)):
            cap = minutes_of(seg)
            if cap <= 0:
                continue
            take = min(cap, remaining)
            if take < remaining and take < chunk_min:
                continue  # 中间段必须 ≥ chunk_min
            if out and take < chunk_min:
                continue  # 尾段也必须 ≥ chunk_min（拆分约束）
            s, e = seg
            iv: Interval = (s, s + timedelta(minutes=take))
            out.append((iv, seg))
            remaining -= take
            gap_end = min(iv[1] + timedelta(minutes=gap_min), e)
            sim[idx] = (gap_end, e)  # 扣除本块 + 片段内 gap
            progressed = True
            break
        if not progressed:
            return None
    return out


# ============================================================================
# DayTimeline：单日时间线分配器
# ============================================================================


@dataclass
class GapReservation:
    """focus 块后的间隙预留（仅挡后续 focus，不挡 habit/light/buffer）"""

    interval: Interval
    after_label: str


@dataclass
class RestBlockSpec:
    """收尾物化的任务间缓冲块"""

    start: datetime
    end: datetime
    gap_of: str


@dataclass
class DayTimeline:
    """单日时间线：自由区维护 + focus 间隙预留 + 收尾物化。

    与 plan_day 的 DB 编排配合：每次物化块后调用 subtract() 同步；
    focus 块落位用 place_focus()（自动登记 gap 预留）。
    """

    awake: Interval
    occupied: List[Interval] = field(default_factory=list)
    gap_min: int = 0
    _free: List[Interval] = field(init=False, default_factory=list)
    gaps: List[GapReservation] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        free: List[Interval] = [self.awake]
        for busy in self.occupied:
            free = subtract(free, busy)
        self._free = sorted(free)

    # -- 自由区视图 ----------------------------------------------------------

    def general_free(self, candidates: Optional[List[Interval]] = None) -> List[Interval]:
        """一般自由区（habit/light/buffer/逃生舱可见，含 gap 预留空间）"""
        if not candidates:
            return list(self._free)
        return clip_to_candidates(self._free, candidates)

    def focus_free(self, candidates: Optional[List[Interval]] = None) -> List[Interval]:
        """focus 自由区 = 一般自由区 - gap 预留（只挡 focus）"""
        free = list(self._free)
        for g in self.gaps:
            free = subtract(free, g.interval)
        if not candidates:
            return free
        return clip_to_candidates(free, candidates)

    # -- 落位 ----------------------------------------------------------------

    def subtract(self, busy: Interval) -> None:
        self._free = subtract(self._free, busy)

    def place_focus(
        self,
        iv: Interval,
        segment: Interval,
        after_label: str,
    ) -> None:
        """focus 块落位：扣除区间 + 登记片段内 gap 预留（裁剪到片段末）"""
        self.subtract(iv)
        if self.gap_min <= 0:
            return
        gap_end = min(iv[1] + timedelta(minutes=self.gap_min), segment[1])
        if iv[1] < gap_end:
            self.gaps.append(GapReservation((iv[1], gap_end), after_label))

    # -- 收尾 ----------------------------------------------------------------

    def materialize_gaps(self, min_minutes: int = 10) -> List[RestBlockSpec]:
        """将仍空闲的 gap（≥min_minutes）物化为任务间缓冲 rest 块（并占用空间）"""
        out: List[RestBlockSpec] = []
        for g in list(self.gaps):
            free_parts = _intersect_free([g.interval], self._free)
            for s, e in free_parts:
                if minutes_of((s, e)) >= min_minutes:
                    out.append(RestBlockSpec(start=s, end=e, gap_of=g.after_label))
                    self.subtract((s, e))
            self.gaps.remove(g)
        return out


def _intersect_free(parts: List[Interval], free: List[Interval]) -> List[Interval]:
    """parts ∩ free（保留仍空闲的部分）"""
    out: List[Interval] = []
    for p in parts:
        for f in free:
            s, e = max(p[0], f[0]), min(p[1], f[1])
            if s < e:
                out.append((s, e))
    out.sort()
    return out
