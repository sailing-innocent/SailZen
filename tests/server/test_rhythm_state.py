# -*- coding: utf-8 -*-
# @file test_rhythm_state.py
# @brief Rhythm 双生命周期状态机测试（一次性流 / 长期流 / fixed_plan 特例 / generic 门禁）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
状态机测试（设计文档 §4.3）

- 一次性流: INBOX→PLANNED→SCHEDULED→DOING→DONE (+DEFERRED/CANCELED)
- 长期流:   INBOX→ACTIVE⇄PAUSED→ARCHIVED (venture 可 GRADUATE→DONE)
- fixed_plan: confirm 直接钉入 SCHEDULED；defer 禁止
- generic: 未分拣禁止 confirm/start/finish/defer
- defer 必须携带 defer_to
- PAUSED 长期事务停止实例化（plan_day 不为其生成块）
"""

from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairAction,
    AffairCreateRequest,
    AffairKind,
    AffairState,
    AffairStateRequest,
    PlanDayRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmStateConflictError,
    create_affair_impl,
    transit_affair_state_impl,
)
from sail_server.infrastructure.orm.rhythm import RhythmAffair
from sail_server.model.rhythm_planner import plan_day_impl

from .conftest import TEST_DATE, dt

pytestmark = pytest.mark.server


def _transit(db: Session, affair_id: int, action: AffairAction, **kwargs):
    return transit_affair_state_impl(
        db, affair_id, AffairStateRequest(action=action, **kwargs)
    )


def _confirmed_task(db: Session, title="写季度总结", **kwargs) -> int:
    affair = create_affair_impl(
        db,
        AffairCreateRequest(title=title, kind=AffairKind.TASK_ONEOFF, domain="work", **kwargs),
    )
    return _transit(db, affair.id, AffairAction.CONFIRM).id


# ============================================================================
# 一次性流
# ============================================================================


class TestOneoffFlow:
    def test_happy_path(self, db: Session):
        affair_id = _confirmed_task(db)
        assert db is not None
        # PLANNED → SCHEDULED（plan_day 排程职责，这里直接 start 合法: PLANNED/SCHEDULED → DOING）
        doing = _transit(db, affair_id, AffairAction.START)
        assert doing.state == AffairState.DOING
        done = _transit(db, affair_id, AffairAction.FINISH)
        assert done.state == AffairState.DONE

    def test_finish_from_planned_conflict(self, db: Session):
        affair_id = _confirmed_task(db)
        with pytest.raises(RhythmStateConflictError):
            _transit(db, affair_id, AffairAction.FINISH)

    def test_done_is_terminal(self, db: Session):
        affair_id = _confirmed_task(db)
        _transit(db, affair_id, AffairAction.START)
        _transit(db, affair_id, AffairAction.FINISH)
        with pytest.raises(RhythmStateConflictError):
            _transit(db, affair_id, AffairAction.START)

    def test_defer_requires_defer_to(self, db: Session):
        affair_id = _confirmed_task(db)
        with pytest.raises(RhythmBadRequestError):
            _transit(db, affair_id, AffairAction.DEFER)

    def test_defer_and_replan(self, db: Session):
        affair_id = _confirmed_task(db)
        new_start = dt(TEST_DATE, "09:00") + timedelta(days=3)
        deferred = _transit(db, affair_id, AffairAction.DEFER, defer_to=new_start)
        assert deferred.state == AffairState.DEFERRED
        assert deferred.window_start == new_start
        replanned = _transit(db, affair_id, AffairAction.REPLAN)
        assert replanned.state == AffairState.PLANNED

    def test_cancel(self, db: Session):
        affair_id = _confirmed_task(db)
        canceled = _transit(db, affair_id, AffairAction.CANCEL)
        assert canceled.state == AffairState.CANCELED
        with pytest.raises(RhythmStateConflictError):
            _transit(db, affair_id, AffairAction.CONFIRM)


# ============================================================================
# generic 门禁
# ============================================================================


class TestGenericGate:
    def test_generic_confirm_blocked(self, db: Session):
        affair = create_affair_impl(db, AffairCreateRequest(title="一句话捕获"))
        with pytest.raises(RhythmStateConflictError):
            _transit(db, affair.id, AffairAction.CONFIRM)

    def test_generic_dismiss_allowed(self, db: Session):
        affair = create_affair_impl(db, AffairCreateRequest(title="噪音"))
        dismissed = _transit(db, affair.id, AffairAction.DISMISS)
        assert dismissed.state == AffairState.CANCELED


# ============================================================================
# fixed_plan 特例
# ============================================================================


class TestFixedPlan:
    def _create_fixed(self, db: Session) -> int:
        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title="周四高铁赴沪",
                kind=AffairKind.FIXED_PLAN,
                domain="life",
                kind_meta={
                    "fixed_start": dt(TEST_DATE, "14:00").isoformat(),
                    "fixed_end": dt(TEST_DATE, "18:00").isoformat(),
                },
            ),
        )
        return affair.id

    def test_confirm_pins_scheduled(self, db: Session):
        """fixed_plan confirm → SCHEDULED + 立即钉 pinned 块"""
        affair_id = self._create_fixed(db)
        confirmed = _transit(db, affair_id, AffairAction.CONFIRM)
        assert confirmed.state == AffairState.SCHEDULED

        from sail_server.infrastructure.orm.rhythm import RhythmTimeBlock

        blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.affair_id == affair_id,
                RhythmTimeBlock.block_type == "fixed",
            )
            .all()
        )
        assert len(blocks) == 1
        assert blocks[0].pinned is True
        assert blocks[0].start_time == dt(TEST_DATE, "14:00")

    def test_defer_forbidden(self, db: Session):
        affair_id = self._create_fixed(db)
        _transit(db, affair_id, AffairAction.CONFIRM)
        with pytest.raises(RhythmStateConflictError):
            _transit(db, affair_id, AffairAction.DEFER, defer_to=dt(TEST_DATE, "15:00"))

    def test_confirm_without_fixed_time_400(self, db: Session):
        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title="无时间刚性", kind=AffairKind.FIXED_PLAN, kind_meta={}
            ),
        )
        with pytest.raises(RhythmBadRequestError):
            _transit(db, affair.id, AffairAction.CONFIRM)


# ============================================================================
# 长期流
# ============================================================================


class TestLongtermFlow:
    def _active_habit(self, db: Session, title="每周运动3次") -> int:
        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title=title,
                kind=AffairKind.HABIT,
                domain="life",
                kind_meta={"freq_per_week": 3, "min_session_minutes": 30,
                           "preferred_slots": ["19:00-21:00"]},
            ),
        )
        return _transit(db, affair.id, AffairAction.CONFIRM).id

    def test_confirm_to_active(self, db: Session):
        affair_id = self._active_habit(db)
        affair = db.query(RhythmAffair).filter_by(id=affair_id).first()
        assert affair.state == "ACTIVE"

    def test_pause_resume_archive(self, db: Session):
        affair_id = self._active_habit(db)
        paused = _transit(db, affair_id, AffairAction.PAUSE)
        assert paused.state == AffairState.PAUSED
        resumed = _transit(db, affair_id, AffairAction.RESUME)
        assert resumed.state == AffairState.ACTIVE
        archived = _transit(db, affair_id, AffairAction.ARCHIVE)
        assert archived.state == AffairState.ARCHIVED

    def test_longterm_no_oneoff_actions(self, db: Session):
        """长期流不支持 start/finish/defer"""
        affair_id = self._active_habit(db)
        with pytest.raises(RhythmBadRequestError):
            _transit(db, affair_id, AffairAction.START)
        with pytest.raises(RhythmBadRequestError):
            _transit(db, affair_id, AffairAction.DEFER, defer_to=dt(TEST_DATE, "10:00"))

    def test_paused_habit_not_instantiated(self, db: Session):
        """PAUSED 停实例化：plan_day 不为 PAUSED habit 生成块"""
        affair_id = self._active_habit(db)
        _transit(db, affair_id, AffairAction.PAUSE)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habit_blocks = [b for b in resp.blocks if b.block_type == "habit"]
        assert habit_blocks == []

    def test_active_habit_instantiated(self, db: Session):
        affair_id = self._active_habit(db)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habit_blocks = [b for b in resp.blocks if b.block_type == "habit" and b.affair_id == affair_id]
        assert len(habit_blocks) == 1

    def test_venture_graduate(self, db: Session):
        venture = create_affair_impl(
            db,
            AffairCreateRequest(
                title="独立游戏上线",
                kind=AffairKind.VENTURE,
                domain="career",
                kind_meta={"target_date": "2027-04-01", "weekly_budget_hours": 8,
                           "total_est_hours": 300},
            ),
        )
        _transit(db, venture.id, AffairAction.CONFIRM)
        graduated = _transit(db, venture.id, AffairAction.GRADUATE)
        assert graduated.state == AffairState.DONE

    def test_habit_graduate_400(self, db: Session):
        affair_id = self._active_habit(db)
        with pytest.raises(RhythmBadRequestError):
            _transit(db, affair_id, AffairAction.GRADUATE)
