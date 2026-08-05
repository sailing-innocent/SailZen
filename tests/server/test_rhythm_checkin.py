# -*- coding: utf-8 -*-
# @file test_rhythm_checkin.py
# @brief Rhythm 打卡测试（kept/violated 记录 / habit 块 done 联动 / 合规率与达标率 / streak）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
打卡与复盘测试（设计文档 §4.1 discipline_logs / §5.6 节奏评分）

- precept kept/violated upsert 语义（同日覆盖）
- weekly cycle precept 按 cycle_key 覆盖
- habit done 多次计入周次数；streak/best_streak 联动
- habit 时间线块 done → 自动写 DisciplineLog（source=auto）
- review: 戒律合规率 / 习惯达标率 / 三域投入 / 节奏分
"""

import pytest
from sqlalchemy.orm import Session

from sail_server.application.dto.rhythm import (
    AffairAction,
    AffairCreateRequest,
    AffairKind,
    AffairStateRequest,
    BlockStatus,
    BlockStatusRequest,
    CheckinRequest,
    CheckinResult,
    DayTemplateUpsertRequest,
    PlanDayRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    checkin_impl,
    create_affair_impl,
    get_affair_impl,
    list_checkins_impl,
    set_block_status_impl,
    today_checkins_impl,
    transit_affair_state_impl,
    upsert_template_impl,
)
from sail_server.model.rhythm_planner import (
    get_day_review_impl,
    get_week_review_impl,
    plan_day_impl,
)

from .conftest import TEST_DATE, make_template_payload

pytestmark = pytest.mark.server


def _confirm(db: Session, affair_id: int):
    return transit_affair_state_impl(
        db, affair_id, AffairStateRequest(action=AffairAction.CONFIRM)
    )


def _active_precept(db: Session, cycle="daily", severity="soft") -> int:
    affair = create_affair_impl(
        db,
        AffairCreateRequest(
            title="23:30前入睡" if severity == "hard" else "三餐定时",
            kind=AffairKind.PRECEPT,
            domain="life",
            kind_meta={
                "rule_text": "23:30前入睡" if severity == "hard" else "三餐定时",
                "cycle": cycle,
                "severity": severity,
                "check_time": "22:30",
            },
        ),
    )
    return _confirm(db, affair.id).id


def _active_habit(db: Session) -> int:
    affair = create_affair_impl(
        db,
        AffairCreateRequest(
            title="每周运动3次",
            kind=AffairKind.HABIT,
            domain="life",
            kind_meta={"freq_per_week": 3, "min_session_minutes": 30,
                       "preferred_slots": ["19:00-21:00"]},
        ),
    )
    return _confirm(db, affair.id).id


# ============================================================================
# precept 打卡
# ============================================================================


class TestPreceptCheckin:
    def test_kept_and_violated(self, db: Session):
        pid = _active_precept(db)
        log = checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.KEPT, log_date=TEST_DATE)
        )
        assert log.result == CheckinResult.KEPT
        assert log.cycle_key == "2026-10-26"

        from datetime import timedelta

        log2 = checkin_impl(
            db,
            CheckinRequest(
                affair_id=pid,
                result=CheckinResult.VIOLATED,
                log_date=TEST_DATE + timedelta(days=1),
                note="应酬破戒",
            ),
        )
        assert log2.result == CheckinResult.VIOLATED
        assert log2.note == "应酬破戒"

    def test_daily_upsert_same_day(self, db: Session):
        """daily precept 同日重复打卡覆盖"""
        pid = _active_precept(db)
        checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.VIOLATED, log_date=TEST_DATE)
        )
        log = checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.KEPT, log_date=TEST_DATE)
        )
        logs = list_checkins_impl(db, affair_id=pid)
        assert len(logs) == 1
        assert logs[0].result == CheckinResult.KEPT
        assert logs[0].id == log.id

    def test_weekly_cycle_key(self, db: Session):
        """weekly precept 按 cycle_key=W2026-44 覆盖"""
        pid = _active_precept(db, cycle="weekly")
        checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.VIOLATED, log_date=TEST_DATE)
        )
        from datetime import timedelta

        log = checkin_impl(
            db,
            CheckinRequest(
                affair_id=pid,
                result=CheckinResult.KEPT,
                log_date=TEST_DATE + timedelta(days=2),  # 同周周三
            ),
        )
        assert log.cycle_key == "W2026-44"
        logs = list_checkins_impl(db, affair_id=pid)
        assert len(logs) == 1
        assert logs[0].result == CheckinResult.KEPT

    def test_invalid_result_for_kind_400(self, db: Session):
        pid = _active_precept(db)
        with pytest.raises(RhythmBadRequestError):
            checkin_impl(
                db,
                CheckinRequest(affair_id=pid, result=CheckinResult.DONE, log_date=TEST_DATE),
            )

    def test_checkin_non_discipline_kind_400(self, db: Session):
        task = create_affair_impl(
            db,
            AffairCreateRequest(title="任务", kind=AffairKind.TASK_ONEOFF, domain="work"),
        )
        _confirm(db, task.id)
        with pytest.raises(RhythmBadRequestError):
            checkin_impl(
                db,
                CheckinRequest(affair_id=task.id, result=CheckinResult.KEPT, log_date=TEST_DATE),
            )


# ============================================================================
# habit 打卡与联动
# ============================================================================


class TestHabitCheckin:
    def test_done_counts_and_streak(self, db: Session):
        hid = _active_habit(db)
        for i in range(3):
            from datetime import timedelta

            checkin_impl(
                db,
                CheckinRequest(
                    affair_id=hid,
                    result=CheckinResult.DONE,
                    log_date=TEST_DATE + timedelta(days=i),
                ),
            )
        affair = get_affair_impl(db, hid)
        assert affair is not None
        assert affair.kind_meta["streak"] == 3
        assert affair.kind_meta["best_streak"] == 3
        assert affair.kind_meta["last_done_date"] == "2026-10-28"

        # missed 重置 streak
        from datetime import timedelta

        checkin_impl(
            db,
            CheckinRequest(
                affair_id=hid,
                result=CheckinResult.MISSED,
                log_date=TEST_DATE + timedelta(days=3),
            ),
        )
        affair = get_affair_impl(db, hid)
        assert affair is not None
        assert affair.kind_meta["streak"] == 0
        assert affair.kind_meta["best_streak"] == 3

    def test_today_checkin_list(self, db: Session):
        hid = _active_habit(db)
        _active_precept(db)
        resp = today_checkins_impl(db, TEST_DATE)
        assert len(resp.habits) == 1
        assert resp.habits[0].week_target == 3
        assert resp.habits[0].week_done_count == 0
        assert len(resp.precepts) == 1

        checkin_impl(
            db, CheckinRequest(affair_id=hid, result=CheckinResult.DONE, log_date=TEST_DATE)
        )
        resp2 = today_checkins_impl(db, TEST_DATE)
        assert resp2.habits[0].done_today is True
        assert resp2.habits[0].week_done_count == 1

    def test_habit_block_done_auto_checkin(self, db: Session):
        """habit 时间线块 done → 自动写 DisciplineLog（source=auto）"""
        upsert_template_impl(db, DayTemplateUpsertRequest(**make_template_payload()))
        hid = _active_habit(db)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habit_block = [b for b in resp.blocks if b.block_type == "habit"][0]
        set_block_status_impl(
            db, habit_block.id, BlockStatusRequest(status=BlockStatus.DONE)
        )
        logs = list_checkins_impl(db, affair_id=hid)
        assert len(logs) == 1
        assert logs[0].result == CheckinResult.DONE
        assert logs[0].source == "auto"


# ============================================================================
# 节奏评分（Review）
# ============================================================================


class TestReview:
    def test_day_review_components(self, db: Session):
        """日评：戒律合规率 + 三域投入 + 节奏分 0-100"""
        pid = _active_precept(db)
        checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.KEPT, log_date=TEST_DATE)
        )
        review = get_day_review_impl(db, TEST_DATE)
        assert review.scope == "day"
        assert review.period_key == "2026-10-26"
        assert review.precept_compliance_rate == 1.0
        assert 0.0 <= review.rhythm_score <= 100.0
        assert review.id is not None  # 已落库

    def test_week_review_compliance_rate(self, db: Session):
        """周评：kept/(kept+violated) 合规率"""
        pid = _active_precept(db)
        from datetime import timedelta

        checkin_impl(
            db, CheckinRequest(affair_id=pid, result=CheckinResult.KEPT, log_date=TEST_DATE)
        )
        checkin_impl(
            db,
            CheckinRequest(
                affair_id=pid,
                result=CheckinResult.VIOLATED,
                log_date=TEST_DATE + timedelta(days=1),
            ),
        )
        review = get_week_review_impl(db, "W2026-44")
        assert review.scope == "week"
        assert review.period_key == "W2026-44"
        assert review.precept_compliance_rate == 0.5

    def test_habit_consistency_in_week_review(self, db: Session):
        """习惯达标率 = 完成次数/频率目标（封顶 1.0）"""
        hid = _active_habit(db)
        from datetime import timedelta

        for i in range(2):  # 目标 3 次，完成 2 次
            checkin_impl(
                db,
                CheckinRequest(
                    affair_id=hid,
                    result=CheckinResult.DONE,
                    log_date=TEST_DATE + timedelta(days=i),
                ),
            )
        review = get_week_review_impl(db, "W2026-44")
        assert abs(review.habit_consistency - 2 / 3) < 1e-3

    def test_week_review_invalid_span_400(self, db: Session):
        from sail_server.model.rhythm import RhythmBadRequestError as RBE

        with pytest.raises(RBE):
            get_week_review_impl(db, "not-a-week")
