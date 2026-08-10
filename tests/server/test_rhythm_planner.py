# -*- coding: utf-8 -*-
# @file test_rhythm_planner.py
# @brief Rhythm 排程器测试（八步铺底 / 评分 / 缓冲 / 生活地板 / 业余时间区 / 预算 / 版本回滚）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
排程器测试（设计文档 §5.4 八步顺序即优先级）

- 骨架铺底（睡眠 + 模板槽位 + 微节律提示块）
- fixed 钉不被移动，冲突只报警
- habit 周缺口提级（生活地板：score 抬升至 work/career 最高分之上）
- venture 仅入业余时间区
- 缓冲占比生成 buffer 块
- 预算不足 warning + unplaced；force 强制排入
- plan_version 回滚（重plan 旧非 pinned 块 MOVED）
- 再平衡冻结 DONE/pinned
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
    DayTemplateUpsertRequest,
    PlanDayRequest,
    RebalanceRequest,
)
from sail_server.infrastructure.orm.finance import Account, Budget, Transaction
from sail_server.infrastructure.orm.rhythm import RhythmAffair, RhythmTimeBlock
from sail_server.model.rhythm import (
    create_affair_impl,
    set_block_status_impl,
    transit_affair_state_impl,
    upsert_template_impl,
)
from sail_server.model.rhythm_planner import (
    get_day_timeline_impl,
    plan_day_impl,
    rebalance_impl,
)

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


def _blocks_of(db: Session, day_id: int, block_type: str):
    return (
        db.query(RhythmTimeBlock)
        .filter(
            RhythmTimeBlock.day_id == day_id,
            RhythmTimeBlock.block_type == block_type,
            RhythmTimeBlock.status != "MOVED",
        )
        .all()
    )


# ============================================================================
# Step 1-2: 睡眠守护 + 骨架铺底
# ============================================================================


class TestSkeleton:
    def test_sleep_and_skeleton_laid(self, db: Session):
        """睡眠块（晨/夜）+ 模板槽位（通勤/工作窗/午餐）+ 微节律提示块"""
        _setup_template(db)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))

        sleep_blocks = [b for b in resp.blocks if b.block_type == "sleep"]
        assert len(sleep_blocks) == 2  # 00:00-07:00 + 23:30-24:00
        assert all(b.pinned for b in sleep_blocks)

        types = {b.block_type for b in resp.blocks}
        assert "commute" in types
        assert "work_window" in types
        assert "meal" in types
        assert "micro_rest" in types  # 90/15 微节律提示

        # 工作窗 pinned
        work_windows = [b for b in resp.blocks if b.block_type == "work_window"]
        assert len(work_windows) == 2
        assert all(b.pinned for b in work_windows)

        # 微休息 informational（不占排程空间）
        micro = [b for b in resp.blocks if b.block_type == "micro_rest"]
        assert micro
        assert all((b.ref or {}).get("informational") for b in micro)

    def test_buffer_generated(self, db: Session):
        """Step 5: 缓冲块按 min_buffer_ratio 生成"""
        _setup_template(db)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        buffer_blocks = [b for b in resp.blocks if b.block_type == "buffer"]
        assert buffer_blocks, "应生成缓冲块"
        total = sum(
            int((b.end_time - b.start_time).total_seconds() // 60) for b in buffer_blocks
        )
        # 清醒窗 07:00-23:30 = 990min，目标 15% ≈ 148min，至少应排入 2×60min
        assert total >= 120


# ============================================================================
# Step 3: 刚性钉
# ============================================================================


class TestFixedPin:
    def _fixed_affair(self, db: Session) -> int:
        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title="家人旅行接送",
                kind=AffairKind.FIXED_PLAN,
                domain="life",
                kind_meta={
                    "fixed_start": dt(TEST_DATE, "10:00").isoformat(),
                    "fixed_end": dt(TEST_DATE, "11:30").isoformat(),
                },
            ),
        )
        _confirm(db, affair.id)
        return affair.id

    def test_fixed_pin_not_moved_on_replan(self, db: Session):
        """重 plan 时 fixed 钉保持原位（pinned 冻结）"""
        _setup_template(db)
        self._fixed_affair(db)
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        day_id = get_day_timeline_impl(db, TEST_DATE).day_id
        before = _blocks_of(db, day_id, "fixed")
        assert len(before) == 1
        start_before = before[0].start_time

        # 再 plan 两次
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        after = _blocks_of(db, day_id, "fixed")
        assert len(after) == 1
        assert after[0].start_time == start_before == dt(TEST_DATE, "10:00")
        assert after[0].pinned is True

    def test_fixed_conflict_warns_not_moves(self, db: Session):
        """fixed 与工作窗重叠 → warning，钉不动"""
        _setup_template(db)
        self._fixed_affair(db)  # 10:00-11:30 与上午工作窗重叠
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        conflict_warnings = [w for w in resp.warnings if w.code == "fixed_conflict"]
        assert conflict_warnings, "应产生 fixed_conflict 警告"
        fixed_block = [b for b in resp.blocks if b.block_type == "fixed"][0]
        assert fixed_block.start_time == dt(TEST_DATE, "10:00")  # 未被移动


# ============================================================================
# Step 6: venture 仅业余时间区
# ============================================================================


class TestVentureSpareOnly:
    def test_career_block_in_spare_window(self, db: Session):
        _setup_template(db)
        venture = create_affair_impl(
            db,
            AffairCreateRequest(
                title="独立游戏开发",
                kind=AffairKind.VENTURE,
                domain="career",
                est_minutes=60,
                kind_meta={"target_date": "2027-04-01", "weekly_budget_hours": 8,
                           "total_est_hours": 300},
            ),
        )
        _confirm(db, venture.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        career = [b for b in resp.blocks if b.block_type == "career"]
        assert len(career) == 1
        # 默认业余时间区 weekday 19:30-22:30
        assert career[0].start_time >= dt(TEST_DATE, "19:30")
        assert career[0].end_time <= dt(TEST_DATE, "22:30")

    def test_week_budget_exhausted_unplaced(self, db: Session):
        """周预算耗尽 → unplaced"""
        _setup_template(db)
        venture = create_affair_impl(
            db,
            AffairCreateRequest(
                title="独立游戏开发",
                kind=AffairKind.VENTURE,
                domain="career",
                est_minutes=60,
                kind_meta={"target_date": "2027-04-01", "weekly_budget_hours": 0.5,
                           "total_est_hours": 300},
            ),
        )
        _confirm(db, venture.id)
        # 周一排 30min（0.5h 预算）
        resp1 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        career1 = [b for b in resp1.blocks if b.block_type == "career"]
        assert len(career1) == 1
        # 周二再排 → 预算耗尽
        from datetime import timedelta

        resp2 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE + timedelta(days=1)))
        career2 = [b for b in resp2.blocks if b.block_type == "career"]
        assert career2 == []
        assert any(u.reason == "周预算耗尽" for u in resp2.unplaced)


# ============================================================================
# Step 7: 习惯/工作竞争 + 生活地板
# ============================================================================


class TestLifeFloor:
    def test_habit_boosted_above_work(self, db: Session):
        """生活地板：未达周目标的 habit score 抬升至当日 work 事务最高分之上"""
        _setup_template(db)
        habit = create_affair_impl(
            db,
            AffairCreateRequest(
                title="每周运动3次",
                kind=AffairKind.HABIT,
                domain="life",
                importance=2,
                kind_meta={"freq_per_week": 3, "min_session_minutes": 30,
                           "preferred_slots": ["19:00-21:00"]},
            ),
        )
        _confirm(db, habit.id)
        from datetime import timedelta

        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="紧急修复线上 bug",
                kind=AffairKind.TASK_ONEOFF,
                domain="work",
                importance=5,
                urgency_ddl=dt(TEST_DATE, "18:00") + timedelta(days=1),
                est_minutes=60,
            ),
        )
        _confirm(db, task.id)

        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        habit_block = [b for b in resp.blocks if b.block_type == "habit"]
        focus_block = [b for b in resp.blocks if b.block_type == "focus"]
        assert habit_block, "habit 应被排入"
        assert focus_block, "task 应被排入"

        habit_row = db.query(RhythmAffair).filter_by(id=habit.id).first()
        task_row = db.query(RhythmAffair).filter_by(id=task.id).first()
        assert float(habit_row.score) > float(task_row.score), "habit 被抬升至工作事务之上"

    def test_task_placed_in_work_window(self, db: Session):
        _setup_template(db)
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="写季度总结",
                kind=AffairKind.TASK_ONEOFF,
                domain="work",
                est_minutes=60,
            ),
        )
        _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = [b for b in resp.blocks if b.block_type == "focus"]
        assert len(focus) == 1
        # 应落在某个工作窗内
        in_morning = (
            dt(TEST_DATE, "09:00") <= focus[0].start_time
            and focus[0].end_time <= dt(TEST_DATE, "12:00")
        )
        in_afternoon = (
            dt(TEST_DATE, "13:00") <= focus[0].start_time
            and focus[0].end_time <= dt(TEST_DATE, "18:00")
        )
        assert in_morning or in_afternoon
        assert not (focus[0].ref or {}).get("overtime")

    def test_overtime_warning_when_work_window_full(self, db: Session):
        """工作窗放不下 → 超窗排程 + overtime warning"""
        _setup_template(db)
        # 塞满工作窗：8 小时工作窗（09-12, 13-18）放 9 个 60min 任务
        for i in range(9):
            task = create_affair_impl(
                db,
                AffairCreateRequest(
                    title=f"任务{i}",
                    kind=AffairKind.TASK_ONEOFF,
                    domain="work",
                    est_minutes=60,
                ),
            )
            _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        overtime_blocks = [b for b in resp.blocks if (b.ref or {}).get("overtime")]
        overtime_warnings = [w for w in resp.warnings if w.code == "overtime"]
        assert overtime_blocks or overtime_warnings or resp.unplaced, (
            "工作窗满时应加班/告警/搁置之一"
        )


# ============================================================================
# 财力校验
# ============================================================================


class TestBudgetCheck:
    def _setup_budget(self, db: Session, total: float, consumed: float) -> int:
        acc1 = Account(name="现金", description="", balance="0", state=0)
        acc2 = Account(name="支付宝", description="", balance="0", state=0)
        db.add_all([acc1, acc2])
        db.flush()
        budget = Budget(name="旅行预算", description="", total_amount=str(total), direction=0)
        db.add(budget)
        db.flush()
        tx = Transaction(
            from_acc_id=acc1.id, to_acc_id=acc2.id, budget_id=budget.id,
            value=str(consumed), prev_value="0", description="已花", tags="", state=1,
        )
        db.add(tx)
        db.commit()
        return budget.id

    def test_budget_insufficient_warning_and_unplaced(self, db: Session):
        _setup_template(db)
        budget_id = self._setup_budget(db, total=100.0, consumed=95.0)
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="买机票",
                kind=AffairKind.TASK_ONEOFF,
                domain="life",
                money_cost=50.0,
                budget_id=budget_id,
                est_minutes=30,
            ),
        )
        _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        warnings = [w for w in resp.warnings if w.code == "budget_insufficient"]
        assert warnings, "应产生预算不足警告"
        assert any(u.affair_id == task.id and u.reason == "预算不足" for u in resp.unplaced)

    def test_force_places_despite_budget(self, db: Session):
        _setup_template(db)
        budget_id = self._setup_budget(db, total=100.0, consumed=95.0)
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="买机票",
                kind=AffairKind.TASK_ONEOFF,
                domain="life",
                money_cost=50.0,
                budget_id=budget_id,
                est_minutes=30,
            ),
        )
        _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE, force=True))
        placed = [b for b in resp.blocks if b.affair_id == task.id and b.status != "MOVED"]
        assert placed, "force=true 时应强制排入"


# ============================================================================
# 守护策略与生活地板
# ============================================================================


class TestPoliciesAndFloor:
    def test_hard_precept_sleep_not_penetrated(self, db: Session):
        """生活地板不可穿透：工作溢出只会 overtime/unplaced，睡眠守护块永不被 focus 重叠"""
        _setup_template(db)
        # hard 睡眠戒律（参与铺底语义：睡眠窗由 profile 守护，戒律负责核销）
        precept = create_affair_impl(
            db,
            AffairCreateRequest(
                title="23:30前入睡",
                kind=AffairKind.PRECEPT,
                domain="life",
                kind_meta={"rule_text": "23:30前入睡", "severity": "hard",
                           "check_time": "23:00"},
            ),
        )
        _confirm(db, precept.id)
        # 塞爆工作窗：9 个 60min 任务（8h 工作窗必然溢出）
        for i in range(9):
            task = create_affair_impl(
                db,
                AffairCreateRequest(
                    title=f"任务{i}", kind=AffairKind.TASK_ONEOFF, domain="work",
                    est_minutes=60,
                ),
            )
            _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))

        sleep_blocks = [b for b in resp.blocks if b.block_type == "sleep"]
        assert len(sleep_blocks) == 2
        assert all(b.pinned for b in sleep_blocks)
        focus_blocks = [b for b in resp.blocks if b.block_type == "focus"]
        for fb in focus_blocks:
            for sb in sleep_blocks:
                overlap = fb.start_time < sb.end_time and sb.start_time < fb.end_time
                assert not overlap, f"focus 块 {fb.start_time}-{fb.end_time} 穿透睡眠守护"

    def test_max_consecutive_focus_inserts_rest(self, db: Session):
        """max_consecutive_focus policy：超长 focus 后强制插 rest 块"""
        from sail_server.application.dto.rhythm import PolicyCreateRequest
        from sail_server.model.rhythm import create_policy_impl

        _setup_template(db)
        create_policy_impl(
            db,
            PolicyCreateRequest(
                name="连续专注上限",
                rule_type="max_consecutive_focus",
                params={"minutes": 90},
                scope="day",
            ),
        )
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="深度重构", kind=AffairKind.TASK_ONEOFF, domain="work",
                est_minutes=120,
            ),
        )
        _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        rest_blocks = [b for b in resp.blocks if b.block_type == "rest"]
        assert rest_blocks, "超过连续专注上限应强制插入 rest 块"
        focus = [b for b in resp.blocks if b.block_type == "focus"][0]
        assert rest_blocks[0].start_time >= focus.end_time

    def test_domain_cap_warning(self, db: Session):
        """domain_cap policy：域时长超上限产生 domain_cap_exceeded warning"""
        from sail_server.application.dto.rhythm import PolicyCreateRequest
        from sail_server.model.rhythm import create_policy_impl

        _setup_template(db)
        create_policy_impl(
            db,
            PolicyCreateRequest(
                name="工作上限",
                rule_type="domain_cap",
                params={"domain": "work", "hours": 1},
                scope="day",
            ),
        )
        for i in range(2):
            task = create_affair_impl(
                db,
                AffairCreateRequest(
                    title=f"任务{i}", kind=AffairKind.TASK_ONEOFF, domain="work",
                    est_minutes=60,
                ),
            )
            _confirm(db, task.id)
        resp = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        cap_warnings = [w for w in resp.warnings if w.code == "domain_cap_exceeded"]
        assert cap_warnings, "2h 工作排程超 1h 上限应告警"


# ============================================================================
# plan_version 与再平衡
# ============================================================================


class TestPlanVersion:
    def test_replan_moves_old_unpinned_blocks(self, db: Session):
        """重 plan：旧 PLANNED 非 pinned 块 → MOVED；pinned 冻结；版本 +1"""
        _setup_template(db)
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="写周报", kind=AffairKind.TASK_ONEOFF, domain="work", est_minutes=45
            ),
        )
        _confirm(db, task.id)

        resp1 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        assert resp1.plan_version == 1
        focus1 = [b for b in resp1.blocks if b.block_type == "focus"]
        assert len(focus1) == 1

        resp2 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        assert resp2.plan_version == 2

        day_id = resp1.day_id
        moved = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id == day_id,
                RhythmTimeBlock.status == "MOVED",
                RhythmTimeBlock.block_type == "focus",
            )
            .all()
        )
        assert len(moved) == 1, "旧 focus 块应被置 MOVED（可回滚）"
        live_focus = _blocks_of(db, day_id, "focus")
        assert len(live_focus) == 1
        assert live_focus[0].plan_version == 2

        # 时间线不含 MOVED
        timeline = get_day_timeline_impl(db, TEST_DATE)
        assert timeline.plan_version == 2
        assert all(b.status != BlockStatus.MOVED for b in timeline.blocks)

    def test_rebalance_freezes_done_blocks(self, db: Session):
        """再平衡：DONE 块冻结不动"""
        _setup_template(db)
        task = create_affair_impl(
            db,
            AffairCreateRequest(
                title="写周报", kind=AffairKind.TASK_ONEOFF, domain="work", est_minutes=45
            ),
        )
        _confirm(db, task.id)
        resp1 = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        focus = [b for b in resp1.blocks if b.block_type == "focus"][0]
        set_block_status_impl(db, focus.id, BlockStatusRequest(status=BlockStatus.DONE))

        rebalance_impl(db, RebalanceRequest(date=TEST_DATE, trigger="manual"))
        day_id = resp1.day_id
        done_blocks = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id == day_id,
                RhythmTimeBlock.block_type == "focus",
                RhythmTimeBlock.status == "DONE",
            )
            .all()
        )
        assert len(done_blocks) == 1, "DONE 块在再平衡中冻结"
        moved_done = (
            db.query(RhythmTimeBlock)
            .filter(
                RhythmTimeBlock.day_id == day_id,
                RhythmTimeBlock.block_type == "focus",
                RhythmTimeBlock.status == "MOVED",
            )
            .all()
        )
        assert moved_done == []


# ============================================================================
# async_callback 排程（KICKOFF/REVIEWING 排实时窗 / DELEGATED informational 提醒块）
# ============================================================================


class TestAsyncCallbackPlan:
    def _create_async(self, db: Session, work_hours_only=False, est_wait_hours=2.0) -> int:
        from sail_server.application.dto.rhythm import AffairDomain

        affair = create_affair_impl(
            db,
            AffairCreateRequest(
                title="AI 文案",
                kind=AffairKind.ASYNC_CALLBACK,
                domain=AffairDomain.WORK,
                kind_meta={
                    "work_hours_only": work_hours_only,
                    "est_wait_hours": est_wait_hours,
                    "max_rounds": 3,
                },
            ),
        )
        return affair.id

    def test_kickoff_plans_async_kickoff_block_in_work_window(self, db: Session):
        """KICKOFF(ACTIVE) 阶段排 async_kickoff 块，落在 work_window 内"""
        _setup_template(db)
        aid = self._create_async(db)
        _confirm(db, aid)  # → ACTIVE(=KICKOFF)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        kickoff = [b for b in plan.blocks if b.block_type == "async_kickoff"]
        assert len(kickoff) == 1
        # work_hours_only=False 时仍优先排工作窗（09-12/13-18）
        s, e = kickoff[0].start_time, kickoff[0].end_time
        assert s.hour >= 9 and (s.hour < 12 or 13 <= s.hour < 18)
        assert kickoff[0].ref.get("phase") == "kickoff"
        assert kickoff[0].ref.get("round") == 1

    def test_delegated_plans_informational_async_wait_block(self, db: Session):
        """DELEGATED 阶段画 informational async_wait 提醒块，0 精力，不占排程空间"""
        _setup_template(db)
        aid = self._create_async(db, est_wait_hours=4.0)
        _confirm(db, aid)
        transit_affair_state_impl(
            db, aid, AffairStateRequest(action=AffairAction.HANDOFF, est_wait_hours=4.0)
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        wait = [b for b in plan.blocks if b.block_type == "async_wait"]
        # next_review_at 在 +4h，落在当日 TEST_DATE 内
        from datetime import datetime
        from sail_server.model.rhythm import get_affair_impl

        nxt_str = get_affair_impl(db, aid).kind_meta["next_review_at"]
        nxt = datetime.fromisoformat(nxt_str)
        if nxt.date() == TEST_DATE:
            assert len(wait) == 1
            assert wait[0].ref.get("informational") is True
            assert wait[0].ref.get("phase") == "delegated"
            # informational 块不进 _occupied_intervals，不被后续 focus 重复占用
            from sail_server.model.rhythm_planner import _occupied_intervals, _existing_blocks
            day_id = wait[0].day_id
            occupied = _occupied_intervals(_existing_blocks(db, day_id))
            assert not any(o[0] == wait[0].start_time and o[1] == wait[0].end_time for o in occupied)
        else:
            # 跨日时不画当日块
            assert len(wait) == 0

    def test_reviewing_plans_async_review_block(self, db: Session):
        """REVIEWING 阶段排 async_review 块"""
        _setup_template(db)
        aid = self._create_async(db)
        _confirm(db, aid)
        transit_affair_state_impl(
            db, aid, AffairStateRequest(action=AffairAction.HANDOFF, est_wait_hours=2.0)
        )
        transit_affair_state_impl(
            db, aid, AffairStateRequest(action=AffairAction.RETURN_REVIEW)
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        review = [b for b in plan.blocks if b.block_type == "async_review"]
        assert len(review) == 1
        assert review[0].ref.get("phase") == "review"

    def test_work_hours_only_blocks_outside_work_window_unplaced(self, db: Session):
        """work_hours_only=true 且无工作窗模板 → async_kickoff 排不下（unplaced）"""
        # 不建模板 → 无 work_window
        aid = self._create_async(db, work_hours_only=True)
        _confirm(db, aid)
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        kickoff = [b for b in plan.blocks if b.block_type == "async_kickoff"]
        assert len(kickoff) == 0
        unplaced_async = [u for u in plan.unplaced if u.affair_id == aid]
        assert len(unplaced_async) == 1

    def test_paused_async_no_blocks(self, db: Session):
        """PAUSED 的 async_callback 不生成块"""
        _setup_template(db)
        aid = self._create_async(db)
        _confirm(db, aid)
        transit_affair_state_impl(
            db, aid, AffairStateRequest(action=AffairAction.PAUSE)
        )
        plan = plan_day_impl(db, PlanDayRequest(date=TEST_DATE))
        async_blocks = [
            b for b in plan.blocks
            if b.affair_id == aid
            and b.block_type in ("async_kickoff", "async_review", "async_wait")
        ]
        assert async_blocks == []
