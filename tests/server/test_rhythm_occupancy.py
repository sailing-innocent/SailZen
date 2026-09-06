# -*- coding: utf-8 -*-
# @file test_rhythm_occupancy.py
# @brief Rhythm 特殊占用测试（CRUD / 幂等 / 校验 / 排程扣除 / 整日请假 / 冲突检测）
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
特殊占用（Occupancy）测试（设计文档 §4.4 Step 2.5 / §6 占用接口）

- 创建：会议/预约精确起止；whole_day / 未给起止的 leave 覆盖工作时段 10:00-19:00
- 幂等：同日同起止同类型返回已有块
- 校验：HH:MM 格式、end>start、与睡眠守护窗重叠 → 400
- 查询 / 删除：仅 occupancy_api 来源的 occupied 块可删
- 排程集成：占用扣除有效工作窗；整日请假（whole_day/leave 清空全部工作窗）
  → 工作任务 unplaced「当日请假/占用」，force=true 也不救援
- 冲突检测：occupied_overlap_sleep / work_overlap_occupancy
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairAction,
    AffairCreateRequest,
    AffairKind,
    AffairStateRequest,
    DayTemplateUpsertRequest,
    OccupancyCreateRequest,
    OccupancyType,
    PlanDayRequest,
)
from sail_server.infrastructure.orm.life import Day
from sail_server.infrastructure.orm.rhythm import RhythmTimeBlock
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmNotFoundError,
    create_affair_impl,
    create_occupancy_impl,
    delete_occupancy_impl,
    list_occupancies_impl,
    transit_affair_state_impl,
    upsert_template_impl,
)
from sail_server.model.rhythm_planner import detect_conflicts_impl, plan_day_impl

from .conftest import TEST_DATE, dt, make_template_payload

pytestmark = pytest.mark.server


# ============================================================================
# Helpers
# ============================================================================


def _setup_template(db: Session) -> None:
    upsert_template_impl(db, DayTemplateUpsertRequest(**make_template_payload()))


def _confirm(db: Session, affair_id: int):
    return transit_affair_state_impl(
        db, affair_id, AffairStateRequest(action=AffairAction.CONFIRM)
    )


def _confirmed_work_task(db: Session, est_minutes: int = 60) -> int:
    task = create_affair_impl(
        db,
        AffairCreateRequest(
            title="写季度总结",
            kind=AffairKind.TASK_ONEOFF,
            domain="work",
            est_minutes=est_minutes,
        ),
    )
    _confirm(db, task.id)
    return task.id


def _occupancy_blocks(db: Session):
    day = db.query(Day).filter(Day.date == TEST_DATE).first()
    assert day is not None
    return (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day.id,
            RhythmTimeBlock.block_type == "occupied",
        )
        .all()
    )


def _add_block(
    db: Session,
    start: str,
    end: str,
    block_type: str,
    *,
    pinned: bool = False,
    affair_id=None,
    ref=None,
) -> RhythmTimeBlock:
    day = db.query(Day).filter(Day.date == TEST_DATE).first()
    assert day is not None
    block = RhythmTimeBlock(
        day_id=day.id,
        affair_id=affair_id,
        block_type=block_type,
        start_time=dt(TEST_DATE, start),
        end_time=dt(TEST_DATE, end),
        status="PLANNED",
        pinned=pinned,
        plan_version=1,
        ref=ref,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


# ============================================================================
# 创建
# ============================================================================


class TestCreateOccupancy:
    def test_create_meeting_creates_pinned_occupied_block(self, db: Session):
        resp = create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE,
                start="10:00",
                end="12:00",
                occupancy_type=OccupancyType.MEETING,
                label="季度对齐会",
            ),
        )
        assert resp.id > 0
        assert resp.start == "10:00" and resp.end == "12:00"
        assert resp.whole_day is False
        assert resp.occupancy_type == "meeting"
        assert resp.label == "季度对齐会"
        blocks = _occupancy_blocks(db)
        assert len(blocks) == 1
        b = blocks[0]
        assert b.pinned is True
        assert b.affair_id is None
        assert b.status == "PLANNED"
        assert b.ref["source"] == "occupancy_api"
        assert b.ref["occupancy_type"] == "meeting"

    def test_whole_day_covers_work_span(self, db: Session):
        resp = create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE,
                whole_day=True,
                occupancy_type=OccupancyType.OTHER,
                label="外出",
            ),
        )
        assert resp.start == "10:00" and resp.end == "19:00"
        assert resp.whole_day is True

    def test_leave_without_range_covers_work_span(self, db: Session):
        resp = create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE,
                occupancy_type=OccupancyType.LEAVE,
                label="年假",
            ),
        )
        assert resp.start == "10:00" and resp.end == "19:00"
        assert resp.whole_day is True
        assert resp.occupancy_type == "leave"

    def test_idempotent_same_date_range_type(self, db: Session):
        req = OccupancyCreateRequest(
            date=TEST_DATE,
            start="10:00",
            end="12:00",
            occupancy_type=OccupancyType.MEETING,
        )
        first = create_occupancy_impl(db, req)
        second = create_occupancy_impl(db, req)
        assert first.id == second.id
        assert len(_occupancy_blocks(db)) == 1

    def test_same_range_different_type_creates_new(self, db: Session):
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.TRAVEL
            ),
        )
        assert len(_occupancy_blocks(db)) == 2

    def test_invalid_hhmm_rejected_at_dto(self, db: Session):
        # DTO 层 HH:MM 校验先于 impl（REST 边界返回 422/400）
        with pytest.raises(ValidationError):
            OccupancyCreateRequest(
                date=TEST_DATE, start="25:00", end="26:00", occupancy_type=OccupancyType.MEETING
            )

    def test_end_not_after_start_raises_400(self, db: Session):
        with pytest.raises(RhythmBadRequestError):
            create_occupancy_impl(
                db,
                OccupancyCreateRequest(
                    date=TEST_DATE, start="12:00", end="12:00", occupancy_type=OccupancyType.MEETING
                ),
            )

    def test_missing_range_non_leave_raises_400(self, db: Session):
        with pytest.raises(RhythmBadRequestError):
            create_occupancy_impl(
                db,
                OccupancyCreateRequest(date=TEST_DATE, occupancy_type=OccupancyType.MEETING),
            )

    def test_overlap_sleep_window_raises_400(self, db: Session):
        # 默认画像 sleep_start=23:30，23:00-23:45 穿透睡眠守护窗
        with pytest.raises(RhythmBadRequestError):
            create_occupancy_impl(
                db,
                OccupancyCreateRequest(
                    date=TEST_DATE, start="23:00", end="23:45", occupancy_type=OccupancyType.MEETING
                ),
            )

    def test_early_morning_overlap_sleep_raises_400(self, db: Session):
        # 默认画像 sleep_end=07:00，06:30-07:30 穿透晨间睡眠守护窗
        with pytest.raises(RhythmBadRequestError):
            create_occupancy_impl(
                db,
                OccupancyCreateRequest(
                    date=TEST_DATE, start="06:30", end="07:30", occupancy_type=OccupancyType.TRAVEL
                ),
            )


# ============================================================================
# 查询 / 删除
# ============================================================================


class TestListAndDeleteOccupancy:
    def test_list_empty_day(self, db: Session):
        resp = list_occupancies_impl(db, TEST_DATE)
        assert resp.date == TEST_DATE
        assert resp.occupancies == []

    def test_list_returns_created_in_time_order(self, db: Session):
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="14:00", end="15:00", occupancy_type=OccupancyType.APPOINTMENT
            ),
        )
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        resp = list_occupancies_impl(db, TEST_DATE)
        assert [o.start for o in resp.occupancies] == ["10:00", "14:00"]

    def test_delete_removes_block(self, db: Session):
        resp = create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        delete_occupancy_impl(db, resp.id)
        assert _occupancy_blocks(db) == []
        assert list_occupancies_impl(db, TEST_DATE).occupancies == []

    def test_delete_missing_block_raises_404(self, db: Session):
        with pytest.raises(RhythmNotFoundError):
            delete_occupancy_impl(db, 999999)

    def test_delete_non_occupancy_source_raises_400(self, db: Session):
        _setup_template(db)
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))  # 建 Day + 骨架
        block = _add_block(
            db, "20:00", "21:00", "occupied", pinned=True, ref={"source": "manual"}
        )
        with pytest.raises(RhythmBadRequestError):
            delete_occupancy_impl(db, block.id)

    def test_delete_non_occupied_block_raises_404(self, db: Session):
        _setup_template(db)
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        block = _add_block(db, "20:00", "21:00", "rest", ref={"source": "occupancy_api"})
        with pytest.raises(RhythmNotFoundError):
            delete_occupancy_impl(db, block.id)


# ============================================================================
# 排程集成（Step 2.5 扣除 / 整日请假）
# ============================================================================


class TestOccupancyInPlanner:
    def test_meeting_carves_effective_work_window(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = [b for b in plan.blocks if b.block_type == "focus" and b.affair_id == aid]
        assert len(focus) == 1
        s, e = focus[0].start_time, focus[0].end_time
        # 不压 10:00-12:00 会议，且落在工作时段 12:00-13:00 / 14:00-19:00 内
        assert e <= dt(TEST_DATE, "12:00") or s >= dt(TEST_DATE, "12:00")
        in_windows = (dt(TEST_DATE, "12:00") <= s and e <= dt(TEST_DATE, "13:00")) or (
            dt(TEST_DATE, "14:00") <= s and e <= dt(TEST_DATE, "19:00")
        )
        assert in_windows

    def test_whole_day_leave_blocks_work_task_unplaced(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, whole_day=True, occupancy_type=OccupancyType.LEAVE
            ),
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = [b for b in plan.blocks if b.block_type == "focus" and b.affair_id == aid]
        assert focus == []
        unplaced = [u for u in plan.unplaced if u.affair_id == aid]
        assert len(unplaced) == 1
        assert unplaced[0].reason == "当日请假/占用"

    def test_whole_day_leave_force_does_not_rescue(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, whole_day=True, occupancy_type=OccupancyType.LEAVE
            ),
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE, force=True))
        focus = [b for b in plan.blocks if b.block_type == "focus" and b.affair_id == aid]
        assert focus == []
        unplaced = [u for u in plan.unplaced if u.affair_id == aid]
        assert unplaced[0].reason == "当日请假/占用"

    def test_half_day_meeting_is_not_day_leave(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="14:00", end="19:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = [b for b in plan.blocks if b.block_type == "focus" and b.affair_id == aid]
        assert len(focus) == 1
        # 仅剩上午有效工作窗 10:00-13:00
        assert focus[0].start_time >= dt(TEST_DATE, "10:00")
        assert focus[0].end_time <= dt(TEST_DATE, "13:00")

    def test_task_too_big_for_carved_window_unplaced(self, db: Session):
        _setup_template(db)
        # 会议占掉下午窗 14:00-19:00，仅剩上午有效工作窗 10:00-13:00（180min）；
        # 240min 任务单段放不下、拆分无第二片段 → unplaced「工作窗放不下」
        aid = _confirmed_work_task(db, est_minutes=240)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="14:00", end="19:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        unplaced = [u for u in plan.unplaced if u.affair_id == aid]
        assert len(unplaced) == 1
        assert unplaced[0].reason == "工作窗放不下"
        assert any(w.code == "work_window_full" for w in plan.warnings)


# ============================================================================
# 冲突检测（checks 5 / 6）
# ============================================================================


class TestOccupancyConflicts:
    def test_occupied_overlap_sleep_detected(self, db: Session):
        _setup_template(db)
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))  # 建 Day + 睡眠块
        _add_block(db, "23:00", "23:45", "occupied", pinned=True, ref={
            "source": "occupancy_api", "occupancy_type": "meeting", "label": "深夜会",
        })
        items = detect_conflicts_impl(db, TEST_DATE)
        assert any(i.type == "occupied_overlap_sleep" for i in items)

    def test_work_block_overlap_occupancy_detected(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        # 手工插入压占用的 work focus 块（模拟 force 超窗/历史数据）
        _add_block(db, "11:00", "12:00", "focus", affair_id=aid, ref={"label": "强制块"})
        items = detect_conflicts_impl(db, TEST_DATE)
        hits = [i for i in items if i.type == "work_overlap_occupancy"]
        assert len(hits) == 1
        assert hits[0].affair_id == aid

    def test_clean_day_has_no_occupancy_conflicts(self, db: Session):
        _setup_template(db)
        aid = _confirmed_work_task(db, est_minutes=60)
        create_occupancy_impl(
            db,
            OccupancyCreateRequest(
                date=TEST_DATE, start="10:00", end="12:00", occupancy_type=OccupancyType.MEETING
            ),
        )
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))  # 正常排程避开占用
        items = detect_conflicts_impl(db, TEST_DATE)
        assert [i for i in items if i.type in (
            "occupied_overlap_sleep", "work_overlap_occupancy"
        )] == []
