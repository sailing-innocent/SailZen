# -*- coding: utf-8 -*-
# @file test_rhythm_v2.py
# @brief Rhythm v2 核心 API 与 AI 自主编排落库完整测试
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""Rhythm v2 服务端测试：
- 精简 3 表（rhythm_affairs / rhythm_time_blocks / rhythm_discipline_logs）
- 极简项目（venture）倒排与里程碑
- SailTick AI 自主编排落库（POST /timeline/ai-sync：保留 DONE/DOING/pinned、归档旧块、版本递增、自动推进事务状态）
- 时间块微调/删除/状态联动打卡 + 多日历史范围查询（供夜间分析）
- 临时占用（会议/请假）与精简聚合 Dashboard
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sail_server.application.dto.rhythm import (
    AITimelineBlockInput,
    AITimelineSyncRequest,
    AffairAction,
    AffairCreateRequest,
    AffairDomain,
    AffairKind,
    AffairState,
    AffairStateRequest,
    AffairUpdateRequest,
    BlockMoveRequest,
    BlockStatus,
    BlockStatusRequest,
    BlockType,
    CheckinRequest,
    CheckinResult,
    OccupancyCreateRequest,
    OccupancyType,
    TimeBlockCreateRequest,
    VentureMilestoneRequest,
)
from sail_server.model.rhythm import (
    RhythmBadRequestError,
    RhythmStateConflictError,
    add_milestone_impl,
    checkin_impl,
    create_affair_impl,
    create_block_impl,
    create_occupancy_impl,
    delete_affair_impl,
    delete_block_impl,
    delete_occupancy_impl,
    get_dashboard_impl,
    get_day_timeline_impl,
    get_rhythm_day_view_impl,
    list_active_projects_progress_impl,
    list_timeline_range_impl,
    milestone_done_impl,
    move_block_impl,
    set_block_status_impl,
    sync_ai_timeline_impl,
    transit_affair_state_impl,
    update_affair_impl,
    venture_progress_impl,
)
from sailzen_orm.orm_base import ORMBase


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    ORMBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_affair_minimal_create_and_state_flow(db):
    # task_oneoff 默认直接 PLANNED（不再卡 INBOX）
    task = create_affair_impl(db, AffairCreateRequest(title="写架构设计"))
    assert task.kind == AffairKind.TASK_ONEOFF
    assert task.state == AffairState.PLANNED
    assert task.domain == AffairDomain.WORK

    # 支持直接 finish，不要求繁琐中间确认
    done = transit_affair_state_impl(db, task.id, AffairStateRequest(action=AffairAction.FINISH))
    assert done.state == AffairState.DONE

    # 终态不允许再转移
    with pytest.raises(RhythmStateConflictError):
        transit_affair_state_impl(db, task.id, AffairStateRequest(action=AffairAction.START))


def test_venture_project_countdown_and_milestones(db):
    target_day = date.today() + timedelta(days=20)
    proj = create_affair_impl(
        db,
        AffairCreateRequest(
            title="SailZen 3.0 发布",
            kind=AffairKind.VENTURE,
            kind_meta={"target_date": target_day.isoformat()},
        ),
    )
    assert proj.state == AffairState.ACTIVE
    assert proj.urgency_ddl is not None
    assert proj.urgency_ddl.date() == target_day

    m1 = add_milestone_impl(db, proj.id, VentureMilestoneRequest(title="完成核心重构"))
    m2 = add_milestone_impl(db, proj.id, VentureMilestoneRequest(title="线上验收"))
    assert m1.parent_id == proj.id

    prog = venture_progress_impl(db, proj.id)
    assert prog.days_left == 20
    assert len(prog.milestones) == 2
    assert prog.completion_ratio == 0.0

    milestone_done_impl(db, m1.id)
    prog2 = venture_progress_impl(db, proj.id)
    assert prog2.completion_ratio == 0.5
    assert len(list_active_projects_progress_impl(db)) == 1

    # 更新清空目标日时联动清空
    updated = update_affair_impl(db, proj.id, AffairUpdateRequest(clear_urgency_ddl=True))
    assert updated is not None
    assert updated.urgency_ddl is None
    assert "target_date" not in updated.kind_meta

    deleted = delete_affair_impl(db, proj.id)
    assert deleted is not None
    assert list_active_projects_progress_impl(db) == []


def test_ai_timeline_sync_preserves_done_and_pinned_and_archives_old(db):
    today = date(2026, 11, 24)
    task_a = create_affair_impl(db, AffairCreateRequest(title="项目核心编码"))
    task_b = create_affair_impl(db, AffairCreateRequest(title="整理周报"))

    # 1. 钉入刚性会议占用
    occ = create_occupancy_impl(
        db,
        OccupancyCreateRequest(
            date=today,
            occupancy_type=OccupancyType.MEETING,
            start="14:00",
            end="15:30",
            label="产品评审会",
        ),
    )
    assert occ.label == "产品评审会"

    # 2. SailTick 首次写入今日日程 v2
    sync1 = sync_ai_timeline_impl(
        db,
        AITimelineSyncRequest(
            date=today,
            rationale="上午精力好先推核心编码，下午避开评审会留白收尾。",
            blocks=[
                AITimelineBlockInput(
                    title="项目核心编码",
                    start="09:30",
                    end="11:30",
                    block_type=BlockType.FOCUS,
                    affair_id=task_a.id,
                    note="优先完成主链路",
                ),
                AITimelineBlockInput(
                    title="整理周报",
                    start="16:00",
                    end="17:00",
                    block_type=BlockType.LIGHT,
                    affair_id=task_b.id,
                ),
            ],
        ),
    )
    assert sync1.created_count == 2
    assert sync1.preserved_count == 1  # 保留会议占用
    assert sync1.plan_version == 2
    assert sync1.ai_rationale.startswith("上午精力好")

    # 关联任务自动进入 SCHEDULED
    tl = get_day_timeline_impl(db, today)
    assert tl.ai_rationale.startswith("上午精力好")
    assert len(tl.blocks) == 3

    # 3. 用户完成第一个块
    focus_blk = next(b for b in tl.blocks if b.affair_id == task_a.id)
    set_block_status_impl(db, focus_blk.id, BlockStatusRequest(status=BlockStatus.DONE))

    # 4. SailTick 午间弹性重排：保留已 DONE 块与 pinned 会议块，归档未完成的“整理周报”，写入新块
    sync2 = sync_ai_timeline_impl(
        db,
        AITimelineSyncRequest(
            date=today,
            rationale="上午进展顺利，下午会后只保留 40 分钟轻收尾。",
            blocks=[
                AITimelineBlockInput(
                    title="轻收尾与散步",
                    start="16:15",
                    end="17:00",
                    block_type=BlockType.LIGHT,
                )
            ],
        ),
    )
    assert sync2.plan_version == 3
    assert sync2.preserved_count == 2  # DONE 块 + pinned 会议块
    assert sync2.archived_count == 1  # 旧的“整理周报”被归档为 MOVED
    assert sync2.created_count == 1

    tl2 = get_day_timeline_impl(db, today)
    assert len(tl2.blocks) == 3
    assert tl2.completed_minutes == 120
    assert tl2.ai_rationale == "上午进展顺利，下午会后只保留 40 分钟轻收尾。"


def test_block_move_delete_habit_checkin_and_range_and_dashboard(db):
    today = date(2026, 11, 24)
    habit = create_affair_impl(
        db,
        AffairCreateRequest(
            title="晚间快走",
            kind=AffairKind.HABIT,
            domain=AffairDomain.LIFE,
            kind_meta={"freq_per_week": 4},
        ),
    )
    blk = create_block_impl(
        db,
        TimeBlockCreateRequest(
            date=today,
            affair_id=habit.id,
            block_type=BlockType.HABIT,
            start_time=datetime(2026, 11, 24, 19, 0),
            end_time=datetime(2026, 11, 24, 19, 30),
        ),
    )
    moved = move_block_impl(
        db,
        blk.id,
        BlockMoveRequest(
            start_time=datetime(2026, 11, 24, 19, 30),
            end_time=datetime(2026, 11, 24, 20, 0),
        ),
    )
    assert moved.start_time.hour == 19 and moved.start_time.minute == 30

    # 完成 habit 块自动写入打卡日志
    set_block_status_impl(db, blk.id, BlockStatusRequest(status=BlockStatus.DONE))

    # 多日范围查询（供夜间分析引擎消费）
    rng = list_timeline_range_impl(db, today - timedelta(days=2), today)
    assert len(rng.days) == 1
    assert rng.days[0].done_count == 1
    assert rng.days[0].completed_minutes == 30

    # Dashboard & DayView 聚合正常无降级
    dash = get_dashboard_impl(db, today)
    assert dash.degraded == []
    assert dash.timeline.completed_minutes == 30
    assert len(dash.today_checkins.habits) == 1
    assert dash.today_checkins.habits[0].done_today is True

    dv = get_rhythm_day_view_impl(db, today)
    assert dv.day_id == dash.timeline.day_id

    # 手动打卡 + 删除块 + 占用删除
    checkin_impl(db, CheckinRequest(affair_id=habit.id, result=CheckinResult.DONE, log_date=today))
    delete_block_impl(db, blk.id)
    assert len(get_day_timeline_impl(db, today).blocks) == 0

    occ = create_occupancy_impl(
        db,
        OccupancyCreateRequest(
            date=today, occupancy_type=OccupancyType.LEAVE, whole_day=True, label="年假"
        ),
    )
    delete_occupancy_impl(db, occ.id)
    with pytest.raises(RhythmBadRequestError):
        sync_ai_timeline_impl(
            db,
            AITimelineSyncRequest(
                date=today,
                blocks=[AITimelineBlockInput(title="非法块", start="11:00", end="10:00")],
            ),
        )
