# -*- coding: utf-8 -*-
# @file test_rhythm_scheduler_v2.py
# @brief Rhythm 排程 v2 测试（纯算法内核 + plan_day 端到端集成矩阵）
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
排程器 v2 测试（设计文档 §4.4 ADR；分两层）

一、纯算法层（不触 DB）：sail_server.model.rhythm_scheduler 直接确定性断言
- 区间基础工具（overlap / subtract / minutes_of / parse_hhmm / clip_to_candidates）
- 工作窗权威解析（profile > 模板 > 空）与早间健康窗
- 职业缓冲截断（end ≤ sleep_start - buffer）
- 占用扣除 → 有效工作窗；整日请假判定
- focus 落位：best-fit 精力曲线排序 + 最早落位
- 可拆分任务跨片段规划（chunk_min / 片段内 gap / 放不下返回 None）
- DayTimeline：gap 预留只挡 focus、收尾物化 ≥10min 任务间缓冲

二、plan_day 端到端集成（SQLite 内存库，复用 conftest fixtures）
覆盖计划 §4.4.1 典型用例矩阵：force 超窗、focus 间隙、跨窗免隙、
早间健康 habit、睡前副业缓冲、拆分跨窗、占用幂等重排等。
"""

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairAction,
    AffairCreateRequest,
    AffairKind,
    AffairStateRequest,
    DayTemplateUpsertRequest,
    EnergyProfileUpsertRequest,
    OccupancyCreateRequest,
    OccupancyType,
    PlanDayRequest,
)
from sail_server.model import rhythm_scheduler as sched
from sail_server.model.rhythm import (
    create_affair_impl,
    create_occupancy_impl,
    transit_affair_state_impl,
    upsert_energy_profile_impl,
    upsert_template_impl,
)
from sail_server.model.rhythm_planner import get_day_timeline_impl, plan_day_impl

from .conftest import TEST_DATE, dt, make_template_payload

pytestmark = pytest.mark.server


def _iv(d: date, s: str, e: str) -> sched.Interval:
    return (dt(d, s), dt(d, e))


# ============================================================================
# 区间基础工具
# ============================================================================


class TestIntervalUtils:
    def test_overlap_boundary_not_counted(self):
        a = _iv(TEST_DATE, "10:00", "11:00")
        b = _iv(TEST_DATE, "11:00", "12:00")
        assert not sched.overlap(a, b)

    def test_overlap_partial(self):
        a = _iv(TEST_DATE, "10:00", "11:30")
        b = _iv(TEST_DATE, "11:00", "12:00")
        assert sched.overlap(a, b)

    def test_subtract_splits_into_two(self):
        free = [_iv(TEST_DATE, "10:00", "19:00")]
        busy = _iv(TEST_DATE, "12:00", "14:00")
        out = sched.subtract(free, busy)
        assert out == [_iv(TEST_DATE, "10:00", "12:00"), _iv(TEST_DATE, "14:00", "19:00")]

    def test_subtract_prefix(self):
        free = [_iv(TEST_DATE, "10:00", "13:00")]
        busy = _iv(TEST_DATE, "12:00", "14:00")
        assert sched.subtract(free, busy) == [_iv(TEST_DATE, "10:00", "12:00")]

    def test_subtract_disjoint_keeps(self):
        free = [_iv(TEST_DATE, "10:00", "12:00")]
        busy = _iv(TEST_DATE, "14:00", "15:00")
        assert sched.subtract(free, busy) == free

    def test_minutes_of(self):
        assert sched.minutes_of(_iv(TEST_DATE, "10:00", "11:15")) == 75

    def test_parse_hhmm_valid_and_fallback(self):
        assert sched.parse_hhmm("07:30", "10:00") == time(7, 30)
        assert sched.parse_hhmm(None, "10:00") == time(10, 0)
        assert sched.parse_hhmm("垃圾", "09:15") == time(9, 15)

    def test_clip_to_candidates(self):
        free = [_iv(TEST_DATE, "10:00", "13:00"), _iv(TEST_DATE, "14:00", "19:00")]
        candidates = [_iv(TEST_DATE, "12:30", "14:30")]
        out = sched.clip_to_candidates(free, candidates)
        assert out == [_iv(TEST_DATE, "12:30", "13:00"), _iv(TEST_DATE, "14:00", "14:30")]


# ============================================================================
# 配置解析（工作窗 / 早间健康窗 / 职业缓冲）
# ============================================================================


class TestResolveWindows:
    def test_profile_windows_win_over_template(self):
        profile_cfg = {"weekday": [["09:00", "12:00"]], "weekend": []}
        template = [_iv(TEST_DATE, "10:00", "13:00")]
        out = sched.resolve_work_windows(profile_cfg, template, TEST_DATE)
        assert out == [_iv(TEST_DATE, "09:00", "12:00")]

    def test_template_fallback_when_profile_empty(self):
        out = sched.resolve_work_windows({"weekday": []}, [_iv(TEST_DATE, "10:00", "13:00")], TEST_DATE)
        assert out == [_iv(TEST_DATE, "10:00", "13:00")]

    def test_weekend_key_selection(self):
        profile_cfg = {
            "weekday": [["10:00", "13:00"]],
            "weekend": [["11:00", "12:00"]],
        }
        sat = TEST_DATE + timedelta(days=5)
        out = sched.resolve_work_windows(profile_cfg, [], sat)
        assert out == [_iv(sat, "11:00", "12:00")]

    def test_invalid_range_in_profile_ignored(self):
        profile_cfg = {"weekday": [["19:00", "10:00"], ["08:00", "09:00"]]}
        out = sched.resolve_work_windows(profile_cfg, [], TEST_DATE)
        assert out == [_iv(TEST_DATE, "08:00", "09:00")]

    def test_morning_window_clipped_by_sleep_end(self):
        out = sched.resolve_morning_window(
            {"start": "07:00", "end": "10:00"}, time(8, 30), TEST_DATE
        )
        assert out == [_iv(TEST_DATE, "08:30", "10:00")]

    def test_morning_window_empty_when_no_room(self):
        out = sched.resolve_morning_window(
            {"start": "07:00", "end": "07:30"}, time(7, 30), TEST_DATE
        )
        assert out == []

    def test_career_buffer_truncates_spare(self):
        spare = [_iv(TEST_DATE, "19:00", "23:30")]
        out = sched.clip_by_career_buffer(spare, dt(TEST_DATE, "23:30"), 45)
        assert out == [_iv(TEST_DATE, "19:00", "22:45")]

    def test_career_buffer_drops_fully_clipped(self):
        spare = [_iv(TEST_DATE, "23:00", "23:30")]
        out = sched.clip_by_career_buffer(spare, dt(TEST_DATE, "23:30"), 45)
        assert out == []

    def test_career_buffer_zero_means_no_clip(self):
        spare = [_iv(TEST_DATE, "19:00", "23:30")]
        assert sched.clip_by_career_buffer(spare, dt(TEST_DATE, "23:30"), 0) == spare


# ============================================================================
# 占用扣除 / 整日请假
# ============================================================================


class _FakeBlock:
    def __init__(self, ref):
        self.ref = ref


class TestOccupancyDeduction:
    def test_effective_windows_subtract_and_split(self):
        base = [_iv(TEST_DATE, "10:00", "13:00"), _iv(TEST_DATE, "14:00", "19:00")]
        occ = [_iv(TEST_DATE, "12:00", "14:30")]
        out = sched.compute_effective_windows(base, occ)
        assert out == [_iv(TEST_DATE, "10:00", "12:00"), _iv(TEST_DATE, "14:30", "19:00")]

    def test_effective_windows_empty_when_covered(self):
        base = [_iv(TEST_DATE, "10:00", "13:00")]
        occ = [_iv(TEST_DATE, "09:00", "19:00")]
        assert sched.compute_effective_windows(base, occ) == []

    def test_full_day_leave_whole_day_ref(self):
        blocks = [_FakeBlock({"whole_day": True, "occupancy_type": "meeting"})]
        assert sched.is_full_day_leave(blocks, [])

    def test_full_day_leave_type_leave(self):
        blocks = [_FakeBlock({"whole_day": False, "occupancy_type": "leave"})]
        assert sched.is_full_day_leave(blocks, [])

    def test_not_full_day_when_effective_remains(self):
        blocks = [_FakeBlock({"whole_day": True, "occupancy_type": "leave"})]
        assert not sched.is_full_day_leave(blocks, [_iv(TEST_DATE, "10:00", "11:00")])

    def test_not_full_day_for_plain_meeting(self):
        blocks = [_FakeBlock({"whole_day": False, "occupancy_type": "meeting"})]
        assert not sched.is_full_day_leave(blocks, [])

    def test_not_full_day_when_no_occupancy(self):
        assert not sched.is_full_day_leave([], [])


# ============================================================================
# focus 落位（best-fit / 拆分）
# ============================================================================


class TestFocusPlacement:
    def test_order_by_curve_desc_fit(self):
        d = TEST_DATE
        segs = [_iv(d, "14:00", "19:00"), _iv(d, "10:00", "13:00"), _iv(d, "20:00", "21:00")]
        curve = [0.5] * 10 + [0.9] * 3 + [0.4] * 11  # 10/11/12 点高峰
        out = sched.order_segments_by_curve(segs, curve)
        assert out[0] == _iv(d, "10:00", "13:00")  # 起始 10 点 fit 最高
        assert out[-1] == _iv(d, "20:00", "21:00")  # 20 点最低

    def test_order_tie_breaks_earliest(self):
        d = TEST_DATE
        segs = [_iv(d, "14:00", "19:00"), _iv(d, "10:00", "13:00")]
        curve = [0.7] * 24
        out = sched.order_segments_by_curve(segs, curve)
        assert out == [_iv(d, "10:00", "13:00"), _iv(d, "14:00", "19:00")]

    def test_order_no_curve_is_time_sorted(self):
        d = TEST_DATE
        segs = [_iv(d, "14:00", "19:00"), _iv(d, "10:00", "13:00")]
        assert sched.order_segments_by_curve(segs, None) == sorted(segs)

    def test_place_single_earliest_in_first_fit(self):
        d = TEST_DATE
        segs = [_iv(d, "10:00", "13:00"), _iv(d, "14:00", "19:00")]
        placed, seg = sched.place_single(segs, 60)
        assert placed == _iv(d, "10:00", "11:00")
        assert seg == _iv(d, "10:00", "13:00")

    def test_place_single_none_when_too_big(self):
        segs = [_iv(TEST_DATE, "10:00", "10:30")]
        assert sched.place_single(segs, 60) is None

    def test_plan_split_across_segments(self):
        d = TEST_DATE
        segs = [_iv(d, "10:00", "13:00"), _iv(d, "14:00", "19:00")]
        out = sched.plan_split(segs, 300, gap_min=15, chunk_min=30)
        assert out is not None
        chunks = [iv for iv, _ in out]
        assert chunks[0] == _iv(d, "10:00", "13:00")  # 180min 吃满上午窗
        assert chunks[1] == _iv(d, "14:00", "16:00")  # 剩余 120min 落下午窗
        total = sum(sched.minutes_of(c) for c in chunks)
        assert total == 300

    def test_plan_split_skips_middle_segment_below_chunk_min(self):
        d = TEST_DATE
        # 中间片段只有 15min（< chunk_min）→ 跳过，不被当作中间段
        segs = [_iv(d, "10:00", "11:00"), _iv(d, "11:30", "11:45"), _iv(d, "14:00", "16:00")]
        out = sched.plan_split(segs, 150, gap_min=0, chunk_min=30)
        assert out is not None
        chunks = [iv for iv, _ in out]
        assert chunks == [_iv(d, "10:00", "11:00"), _iv(d, "14:00", "15:30")]
        assert sum(sched.minutes_of(c) for c in chunks) == 150

    def test_plan_split_tail_below_chunk_min_returns_none(self):
        d = TEST_DATE
        # 上午窗 180min 吃满后剩 5min 尾段 < chunk_min → 整体失败（None）
        segs = [_iv(d, "10:00", "13:00"), _iv(d, "14:00", "19:00")]
        assert sched.plan_split(segs, 185, gap_min=15, chunk_min=30) is None

    def test_plan_split_tail_below_chunk_min_rejected(self):
        d = TEST_DATE
        # 两个片段各 45min，任务 80min：45+35 → 尾段 35 < 40 → None
        segs = [_iv(d, "10:00", "10:45"), _iv(d, "14:00", "14:45")]
        assert sched.plan_split(segs, 80, gap_min=0, chunk_min=40) is None

    def test_plan_split_single_chunk_may_shrink_below_chunk_min(self):
        d = TEST_DATE
        # 唯一例外：整体单段可放下时不受 chunk_min 限制
        segs = [_iv(d, "10:00", "11:00")]
        out = sched.plan_split(segs, 45, gap_min=0, chunk_min=60)
        assert out is not None and sched.minutes_of(out[0][0]) == 45

    def test_plan_split_none_when_insufficient_total(self):
        d = TEST_DATE
        segs = [_iv(d, "10:00", "10:30"), _iv(d, "14:00", "14:30")]
        assert sched.plan_split(segs, 90, gap_min=0, chunk_min=10) is None

    def test_plan_split_does_not_mutate_input(self):
        d = TEST_DATE
        segs = [_iv(d, "10:00", "13:00")]
        snapshot = list(segs)
        sched.plan_split(segs, 120, gap_min=15, chunk_min=30)
        assert segs == snapshot


# ============================================================================
# DayTimeline：自由区视图 + gap 预留 + 收尾物化
# ============================================================================


def _timeline(gap_min: int = 15) -> sched.DayTimeline:
    d = TEST_DATE
    return sched.DayTimeline(
        awake=_iv(d, "07:00", "23:00"),
        occupied=[_iv(d, "12:00", "13:00")],
        gap_min=gap_min,
    )


class TestDayTimeline:
    def test_init_subtracts_occupied(self):
        tl = _timeline()
        assert tl.general_free() == [
            _iv(TEST_DATE, "07:00", "12:00"),
            _iv(TEST_DATE, "13:00", "23:00"),
        ]

    def test_place_focus_registers_gap_clipped_to_segment(self):
        tl = _timeline()
        seg = _iv(TEST_DATE, "10:00", "11:00")
        tl.place_focus(_iv(TEST_DATE, "10:00", "11:00"), seg, after_label="任务A")
        # gap 11:00-11:15 仍在 10:00-11:00 片段内？否：gap_end=min(11:15, seg.end=11:00)=11:00 → 无预留
        assert tl.gaps == []

    def test_place_focus_gap_extends_into_free(self):
        tl = _timeline()
        seg = _iv(TEST_DATE, "13:00", "16:00")
        tl.place_focus(_iv(TEST_DATE, "13:00", "14:00"), seg, after_label="任务B")
        assert len(tl.gaps) == 1
        assert tl.gaps[0].interval == _iv(TEST_DATE, "14:00", "14:15")
        assert tl.gaps[0].after_label == "任务B"

    def test_focus_free_excludes_gap_general_free_keeps(self):
        tl = _timeline()
        seg = _iv(TEST_DATE, "13:00", "16:00")
        tl.place_focus(_iv(TEST_DATE, "13:00", "14:00"), seg, after_label="任务B")
        gap = _iv(TEST_DATE, "14:00", "14:15")
        # 14:00-14:15 对 focus 不可见（被 gap 预留挡住），但对 general 可见
        assert not any(sched.overlap(iv, gap) for iv in tl.focus_free())
        assert any(iv[0] <= gap[0] and gap[1] <= iv[1] for iv in tl.general_free())

    def test_materialize_gaps_emits_rest_specs(self):
        tl = _timeline()
        seg = _iv(TEST_DATE, "13:00", "16:00")
        tl.place_focus(_iv(TEST_DATE, "13:00", "14:00"), seg, after_label="任务B")
        tl.place_focus(_iv(TEST_DATE, "14:15", "15:00"), seg, after_label="任务C")
        specs = tl.materialize_gaps(min_minutes=10)
        # 两个 gap（14:00-14:15 / 15:00-15:15）均仍空闲 → 全部物化
        assert [(s.start, s.end, s.gap_of) for s in specs] == [
            (dt(TEST_DATE, "14:00"), dt(TEST_DATE, "14:15"), "任务B"),
            (dt(TEST_DATE, "15:00"), dt(TEST_DATE, "15:15"), "任务C"),
        ]
        # 物化后占用空间：general_free 不再覆盖 14:00-14:15
        gap = _iv(TEST_DATE, "14:00", "14:15")
        assert not any(sched.overlap(iv, gap) for iv in tl.general_free())

    def test_materialize_gaps_skips_when_consumed(self):
        tl = _timeline()
        seg = _iv(TEST_DATE, "13:00", "16:00")
        tl.place_focus(_iv(TEST_DATE, "13:00", "14:00"), seg, after_label="任务B")
        # 另一 focus 直接落在 gap 上（habit/light 允许占用 gap 空间）→ 物化时跳过
        tl.subtract(_iv(TEST_DATE, "14:00", "14:15"))
        tl.place_focus(_iv(TEST_DATE, "14:00", "14:30"), seg, after_label="任务D")
        specs = tl.materialize_gaps(min_minutes=10)
        assert all(not (s.start == dt(TEST_DATE, "14:00") and s.end == dt(TEST_DATE, "14:15")) for s in specs)

    def test_materialize_gaps_below_min_minutes_skipped(self):
        tl = sched.DayTimeline(
            awake=_iv(TEST_DATE, "07:00", "23:00"),
            occupied=[_iv(TEST_DATE, "12:00", "13:00")],
            gap_min=5,
        )
        seg = _iv(TEST_DATE, "13:00", "16:00")
        tl.place_focus(_iv(TEST_DATE, "13:00", "14:00"), seg, after_label="任务E")
        specs = tl.materialize_gaps(min_minutes=10)
        assert specs == []  # gap 仅 5min < 10min


# ============================================================================
# plan_day v2 端到端集成（计划 §4.4.1 典型用例矩阵）
# ============================================================================


def _setup_template(db: Session) -> None:
    upsert_template_impl(db, DayTemplateUpsertRequest(**make_template_payload()))


def _confirm(db: Session, affair_id: int):
    return transit_affair_state_impl(
        db, affair_id, AffairStateRequest(action=AffairAction.CONFIRM)
    )


def _task(db: Session, title: str, est_minutes: int, *, importance: int = 3, **kw) -> int:
    t = create_affair_impl(
        db,
        AffairCreateRequest(
            title=title,
            kind=AffairKind.TASK_ONEOFF,
            domain="work",
            importance=importance,
            est_minutes=est_minutes,
            **kw,
        ),
    )
    _confirm(db, t.id)
    return t.id


def _focus_of(plan, aid: int):
    return sorted(
        [b for b in plan.blocks if b.block_type == "focus" and b.affair_id == aid],
        key=lambda b: b.start_time,
    )


def _gap_rests(plan):
    return sorted(
        [
            b
            for b in plan.blocks
            if b.block_type == "rest" and (b.ref or {}).get("label") == "任务间缓冲"
        ],
        key=lambda b: b.start_time,
    )


class TestForceEscapeHatch:
    def _fill_both_windows(self, db: Session) -> int:
        """8h 可拆分任务占满上午+下午有效工作窗（180+300，贪心按能量曲线序）"""
        return _task(db, "占满窗", 480, splittable=True, min_chunk_minutes=60)

    def test_work_window_full_unplaced_by_default(self, db: Session):
        _setup_template(db)
        self._fill_both_windows(db)
        aid = _task(db, "塞不下", 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        unplaced = [u for u in plan.unplaced if u.affair_id == aid]
        assert len(unplaced) == 1 and unplaced[0].reason == "工作窗放不下"
        assert _focus_of(plan, aid) == []
        assert any(w.code == "work_window_full" for w in plan.warnings)

    def test_force_true_places_overtime_marked(self, db: Session):
        _setup_template(db)
        filler = self._fill_both_windows(db)
        aid = _task(db, "塞不下", 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE, force=True))
        focus = _focus_of(plan, aid)
        assert len(focus) == 1
        assert focus[0].ref.get("overtime") is True
        # 逃生舱块不与已占窗块重叠（落自由区，如午休/晚间）
        filler_blocks = _focus_of(plan, filler)
        for fb in filler_blocks:
            assert fb.end_time <= focus[0].start_time or focus[0].end_time <= fb.start_time
        assert any(w.code == "overtime" for w in plan.warnings)


class TestFocusGap:
    def test_gap_between_focus_blocks_materialized(self, db: Session):
        _setup_template(db)
        a = _task(db, "任务A", 60)
        b = _task(db, "任务B", 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        fa, fb = _focus_of(plan, a), _focus_of(plan, b)
        assert len(fa) == 1 and len(fb) == 1
        first, second = sorted(fa + fb, key=lambda x: x.start_time)
        # 两块 focus 之间恰好物化一个 gap 休息（尾部 gap 在窗内也会物化，另计）
        between = [
            r
            for r in _gap_rests(plan)
            if r.start_time == first.end_time and r.end_time == second.start_time
        ]
        assert len(between) == 1
        r = between[0]
        assert (r.end_time - r.start_time) >= timedelta(minutes=10)
        assert r.ref.get("gap_of") == first.ref.get("label")
        # gap 休息计入任务间缓冲统计（经当日时间线统计核对）
        timeline = get_day_timeline_impl(db, TEST_DATE)
        assert timeline.buffer_total_minutes >= 15
        tl = get_day_timeline_impl(db, TEST_DATE)
        assert tl.buffer_total_minutes >= 15

    def test_gap_not_required_across_work_windows(self, db: Session):
        _setup_template(db)
        a = _task(db, "填满上午", 180, importance=5)
        b = _task(db, "下午任务", 60, importance=1)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        fa, fb = _focus_of(plan, a), _focus_of(plan, b)
        assert len(fa) == 1 and len(fb) == 1
        assert fa[0].end_time <= dt(TEST_DATE, "13:00")
        # 跨工作窗（午休分隔）不要求 gap：下午任务直接从 14:00 起
        assert fb[0].start_time == dt(TEST_DATE, "14:00")
        # 午休边界 13:00-14:00 之间不物化任何任务间缓冲
        lunch = (dt(TEST_DATE, "13:00"), dt(TEST_DATE, "14:00"))
        assert all(
            not (r.start_time < lunch[1] and r.end_time > lunch[0])
            for r in _gap_rests(plan)
        )


class TestMorningHealthHabit:
    def _habit(self, db: Session, title: str, *, category: str = "life") -> int:
        h = create_affair_impl(
            db,
            AffairCreateRequest(
                title=title,
                kind=AffairKind.HABIT,
                domain="life",
                importance=2,
                kind_meta={
                    "freq_per_week": 3,
                    "min_session_minutes": 30,
                    "category": category,
                    "preferred_slots": ["19:00-21:00"],
                },
            ),
        )
        _confirm(db, h.id)
        return h.id

    def test_health_habit_lands_in_morning_window(self, db: Session):
        _setup_template(db)
        aid = self._habit(db, "晨练", category="health")
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habits = [b for b in plan.blocks if b.block_type == "habit" and b.affair_id == aid]
        assert len(habits) == 1
        assert habits[0].start_time >= dt(TEST_DATE, "07:00")
        assert habits[0].end_time <= dt(TEST_DATE, "10:00")

    def test_normal_habit_avoids_morning_window(self, db: Session):
        _setup_template(db)
        aid = self._habit(db, "读书", category="mind")
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habits = [b for b in plan.blocks if b.block_type == "habit" and b.affair_id == aid]
        assert len(habits) == 1
        # 不抢占早间健康窗：要么完全在 10:00 前结束不可能（窗在 07-10），要么 10:00 后
        assert habits[0].start_time >= dt(TEST_DATE, "10:00")
        assert not any(w.code == "morning_health_unplaced" for w in plan.warnings)


class TestCareerSleepBuffer:
    def _venture(self, db: Session, est_minutes: int, **meta) -> int:
        v = create_affair_impl(
            db,
            AffairCreateRequest(
                title="独立游戏开发",
                kind=AffairKind.VENTURE,
                domain="career",
                est_minutes=est_minutes,
                kind_meta={
                    "target_date": "2027-04-01",
                    "weekly_budget_hours": 8,
                    "total_est_hours": 300,
                    **meta,
                },
            ),
        )
        _confirm(db, v.id)
        return v.id

    def test_career_block_ends_before_sleep_buffer(self, db: Session):
        _setup_template(db)
        aid = self._venture(db, 120)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        career = [b for b in plan.blocks if b.block_type == "career" and b.affair_id == aid]
        assert len(career) == 1
        # sleep_start 23:30 - career_buffer 45min → end ≤ 22:45
        assert career[0].end_time <= dt(TEST_DATE, "22:45")

    def test_career_shortens_to_min_chunk_when_window_small(self, db: Session):
        _setup_template(db)
        # 业余区 22:00-22:45（其中 22:30-22:45 落在弹性缓冲已占区之外、且 end 被
        # 睡前缓冲截到 22:45）→ 自由部分仅 30min，60min 放不下，
        # 缩短至 min_chunk 30min 后落位
        upsert_energy_profile_impl(
            db,
            EnergyProfileUpsertRequest(
                spare_time_windows={"weekday": [["22:00", "22:45"]], "weekend": []},
                career_buffer_minutes=45,
            ),
        )
        aid = self._venture(db, 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        career = [b for b in plan.blocks if b.block_type == "career" and b.affair_id == aid]
        assert len(career) == 1
        assert (career[0].end_time - career[0].start_time).total_seconds() == 30 * 60
        assert career[0].end_time <= dt(TEST_DATE, "22:45")

    def test_career_buffer_insufficient_unplaced(self, db: Session):
        _setup_template(db)
        # 业余区整段落在缓冲带内 → 截断为空 → unplaced + warning
        upsert_energy_profile_impl(
            db,
            EnergyProfileUpsertRequest(
                spare_time_windows={"weekday": [["23:00", "23:30"]], "weekend": []},
                career_buffer_minutes=45,
            ),
        )
        aid = self._venture(db, 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        assert [b for b in plan.blocks if b.block_type == "career" and b.affair_id == aid] == []
        unplaced = [u for u in plan.unplaced if u.affair_id == aid]
        assert len(unplaced) == 1
        assert unplaced[0].reason == "睡前缓冲不足/业余时间区窗口冲突"
        assert any(w.code == "career_buffer_insufficient" for w in plan.warnings)


class TestSplittableTask:
    def test_split_across_work_windows_with_chunk_refs(self, db: Session):
        _setup_template(db)
        aid = _task(db, "大任务", 360, splittable=True, min_chunk_minutes=60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        chunks = _focus_of(plan, aid)
        assert len(chunks) == 2
        sizes = sorted(
            int((c.end_time - c.start_time).total_seconds() // 60) for c in chunks
        )
        assert sizes == [180, 180]  # 上午窗 + 下午窗，各 ≥ min_chunk 60
        for c in chunks:
            assert c.ref.get("chunk_index") in (1, 2)
            assert c.ref.get("chunks_total") == 2
            assert c.ref.get("overtime") is not True
        # 两 chunk 各自落在不同的有效工作窗内
        assert all(
            (c.end_time <= dt(TEST_DATE, "13:00")) or (c.start_time >= dt(TEST_DATE, "14:00"))
            for c in chunks
        )


class TestBestFitByCurve:
    def test_task_placed_in_higher_energy_segment(self, db: Session):
        _setup_template(db)
        # 构造能量曲线：14 点高峰、10 点低谷 → 60min 任务应落下午窗
        weekday = [0.5] * 24
        weekday[10] = 0.1
        weekday[14] = 0.95
        upsert_energy_profile_impl(
            db,
            EnergyProfileUpsertRequest(
                curve_template={"weekday": weekday, "weekend": list(weekday)}
            ),
        )
        aid = _task(db, "高优任务", 60)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = _focus_of(plan, aid)
        assert len(focus) == 1
        assert dt(TEST_DATE, "14:00") <= focus[0].start_time
        assert focus[0].end_time <= dt(TEST_DATE, "19:00")


class TestReplanWithOccupancy:
    def test_replan_idempotent_occupancy_and_skeleton(self, db: Session):
        _setup_template(db)
        aid = _task(db, "写总结", 60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        plan1 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        plan2 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        # 占用块不重复（幂等 + pinned 冻结）
        occ1 = [b for b in plan1.blocks if b.block_type == "occupied"]
        occ2 = [b for b in plan2.blocks if b.block_type == "occupied"]
        assert len(occ1) == 1 and len(occ2) == 1
        assert occ1[0].id == occ2[0].id
        # 骨架（通勤/午餐）不重复实例化
        for bt in ("commute", "meal"):
            assert len([b for b in plan2.blocks if b.block_type == bt]) == 1
        # 重排后任务仍避开占用段，且块数稳定（无泄漏增长）
        focus2 = _focus_of(plan2, aid)
        assert len(focus2) == 1
        assert focus2[0].start_time >= dt(TEST_DATE, "12:00")
        assert plan2.plan_version > plan1.plan_version
