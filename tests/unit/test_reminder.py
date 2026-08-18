# -*- coding: utf-8 -*-
# @file test_reminder.py
# @brief Unit tests for reminder module (状态机 / 反馈中枢 / 调度扫描 / 设备)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒模块单元测试（Android App M1）

覆盖：
- 创建提醒 + created 事件
- feedback 四动作（dismiss/snooze/open/resolve）状态机转移与事件日志
- snooze 升级策略（3 次升优先级、5 次 agent_review 事件）
- 终态幂等 / 冲突（409 语义，model 层为 ReminderStateConflictError）
- cancel / ack
- scan_once 调度扫描：到点投递、snooze 重投、OPENED 回落、过期重投/归档
- summary/today 计数
- 设备注册 upsert
- ReminderPushManager（fake socket）

使用 SQLite 内存数据库（StaticPool），不依赖 PostgreSQL。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Generator, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sail_server.application.dto.reminder import (
    DeviceRegisterRequest,
    FeedbackRequest,
    ReminderCreateRequest,
    ReminderRuleCreateRequest,
    ReminderSourceConfigCreateRequest,
    ReminderSourceConfigUpdateRequest,
)
from sail_server.infrastructure.orm.orm_base import ORMBase
from sail_server.infrastructure.orm.reminder import (
    Device,
    Reminder,
    ReminderEvent,
    ReminderRule,
    ReminderSourceConfig,
)
from sail_server.model import reminder as reminder_model
from sail_server.model.reminder import (
    ReminderBadRequestError,
    ReminderStateConflictError,
    ack_reminder_impl,
    cancel_reminder_impl,
    create_reminder_impl,
    create_rule_impl,
    create_source_config_impl,
    feedback_reminder_impl,
    get_source_config_impl,
    get_summary_today_impl,
    list_events_impl,
    list_pending_impl,
    list_source_configs_impl,
    register_device_impl,
    update_source_config_impl,
    upsert_source_config_impl,
)
from sail_server.model import reminder_scheduler
from sail_server.model.reminder_scheduler import scan_once
from sail_server.utils.reminder_ws import ReminderPushManager

pytestmark = pytest.mark.unit


@pytest.fixture(scope="function", autouse=True)
def disable_rhythm_daily_brief(monkeypatch):
    """单元测试里关闭 rhythm daily brief 生成，避免扫描时额外创建提醒干扰断言。"""
    monkeypatch.setattr(
        reminder_scheduler, "_generate_rhythm_daily_brief", lambda db, now: 0
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def reminder_engine():
    """SQLite 内存引擎（StaticPool 保证跨会话共享同一内存库）"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(reminder_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=reminder_engine)
    session = SessionLocal()
    # 默认屏蔽 rhythm 自动生成，避免 scan_once 相关测试因真实时间不同而产生数量抖动
    from sail_server.model.rhythm import get_or_create_profile

    profile = get_or_create_profile(session)
    profile.spare_time_windows = {"start": "00:00", "end": "23:59"}
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def db_factory(reminder_engine):
    """scan_once 需要的会话工厂"""
    return sessionmaker(bind=reminder_engine)


# ============================================================================
# Helpers
# ============================================================================


def _create(db: Session, **overrides):
    """通过 impl 创建提醒（默认立即可触发类型）"""
    payload = {
        "type": "test.ping",
        "title": "测试提醒",
        "body": "body",
        "trigger_time": datetime.now() + timedelta(hours=1),
    }
    payload.update(overrides)
    return create_reminder_impl(db, ReminderCreateRequest(**payload))


def _events(db: Session, reminder_id: int) -> List[str]:
    return [e.event for e in list_events_impl(db, reminder_id)]


def _set_state(db: Session, reminder_id: int, state: str, **fields):
    """直接把提醒置为指定状态（测试布景用）"""
    r = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    r.state = state
    for k, v in fields.items():
        setattr(r, k, v)
    db.commit()
    db.expire_all()
    return r


def _get(db: Session, reminder_id: int) -> Reminder:
    db.expire_all()
    return db.query(Reminder).filter(Reminder.id == reminder_id).first()


# ============================================================================
# 1. 创建
# ============================================================================


def test_create_reminder_pending_with_created_event(db):
    r = _create(db)
    assert r.state == "PENDING"
    assert r.id is not None
    assert _events(db, r.id) == ["created"]


# ============================================================================
# 2. snooze
# ============================================================================


def test_feedback_snooze_15m(db):
    r = _create(db)
    before = datetime.now()
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="15m"))
    assert res.state == "SNOOZED"
    assert res.snooze_count == 1
    assert res.next_trigger_time is not None
    # next_trigger_time ≈ +15min
    delta = res.next_trigger_time - before
    assert timedelta(minutes=14) < delta < timedelta(minutes=16)
    assert "snoozed" in _events(db, r.id)


def test_feedback_snooze_option_validation(db):
    r = _create(db)
    with pytest.raises(Exception):
        feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="3d"))
    with pytest.raises(Exception):
        feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze"))


# ============================================================================
# 3. snooze 升级策略
# ============================================================================


def test_snooze_escalation_priority_up(db):
    r = _create(db)
    assert r.priority == "normal"
    for i in range(3):
        res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="15m"))
    assert res.snooze_count == 3
    assert res.priority == "high"  # normal → high
    events = _events(db, r.id)
    assert "escalated" in events
    # 继续 snooze 到 5 次 → agent_review 事件
    for i in range(2):
        res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="15m"))
    assert res.snooze_count == 5
    details = [e for e in list_events_impl(db, r.id) if e.event == "escalated"]
    levels = {e.detail.get("level") for e in details}
    assert "priority_up" in levels
    assert "agent_review" in levels


# ============================================================================
# 4. open → resolve
# ============================================================================


def test_feedback_open_then_resolve(db):
    r = _create(db)
    # PENDING 未投递，open 拒绝
    with pytest.raises(ReminderStateConflictError):
        feedback_reminder_impl(db, r.id, FeedbackRequest(action="open"))
    # 置为 DELIVERED 后 open 成功
    _set_state(db, r.id, "DELIVERED", last_delivered_at=datetime.now())
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="open"))
    assert res.state == "OPENED"
    # 重复 open 幂等
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="open"))
    assert res.state == "OPENED"
    # resolve → 终态
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="resolve"))
    assert res.state == "RESOLVED"
    assert "opened" in _events(db, r.id)
    assert "resolved" in _events(db, r.id)


# ============================================================================
# 5. dismiss + 终态行为
# ============================================================================


def test_feedback_dismiss_terminal(db):
    r = _create(db)
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="dismiss"))
    assert res.state == "IGNORED"
    # 终态后 resolve → 409 语义
    with pytest.raises(ReminderStateConflictError):
        feedback_reminder_impl(db, r.id, FeedbackRequest(action="resolve"))
    # 终态后 snooze → 409 语义
    with pytest.raises(ReminderStateConflictError):
        feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="15m"))
    # 终态后 dismiss → 幂等返回（200，already_terminal）
    res = feedback_reminder_impl(db, r.id, FeedbackRequest(action="dismiss"))
    assert res.state == "IGNORED"
    last = list_events_impl(db, r.id)[-1]
    assert last.event == "dismissed"
    assert last.detail.get("already_terminal") is True


# ============================================================================
# 6. cancel
# ============================================================================


def test_cancel_reminder(db):
    r = _create(db)
    res = cancel_reminder_impl(db, r.id)
    assert res.state == "CANCELED"
    assert "canceled" in _events(db, r.id)
    # 终态后 cancel → 409 语义
    with pytest.raises(ReminderStateConflictError):
        cancel_reminder_impl(db, r.id)


# ============================================================================
# 7. scan_once：到点投递
# ============================================================================


def test_scan_once_delivers_due_pending(db, db_factory):
    r = _create(db, trigger_time=datetime.now() - timedelta(seconds=5))
    pushed: List[dict] = []
    stats = scan_once(db_factory, push=pushed.append)
    assert stats["delivered"] == 1
    assert len(pushed) == 1
    assert pushed[0]["id"] == r.id
    assert pushed[0]["state"] == "DELIVERED"
    assert _get(db, r.id).state == "DELIVERED"
    assert _get(db, r.id).last_delivered_at is not None
    assert "delivered" in _events(db, r.id)
    # 未到点的不投递
    r2 = _create(db, trigger_time=datetime.now() + timedelta(hours=2))
    stats = scan_once(db_factory, push=pushed.append)
    assert stats["delivered"] == 0
    assert _get(db, r2.id).state == "PENDING"


# ============================================================================
# 8. scan_once：snooze 到点重投
# ============================================================================


def test_scan_once_snooze_redelivery(db, db_factory):
    r = _create(db)
    feedback_reminder_impl(db, r.id, FeedbackRequest(action="snooze", option="15m"))
    pushed: List[dict] = []
    future = datetime.now() + timedelta(minutes=16)
    stats = scan_once(db_factory, push=pushed.append, now=future)
    assert stats["redelivered"] == 1
    assert len(pushed) == 1
    row = _get(db, r.id)
    assert row.state == "DELIVERED"
    assert row.next_trigger_time is None
    evs = [e for e in list_events_impl(db, r.id) if e.event == "delivered"]
    assert any(e.detail.get("redelivery") is True for e in evs)


# ============================================================================
# 9. scan_once：OPENED 回落
# ============================================================================


def test_scan_once_opened_fallback(db, db_factory):
    r = _create(db)
    old = datetime.now() - timedelta(minutes=40)
    _set_state(db, r.id, "OPENED", updated_at=old, last_delivered_at=old)
    pushed: List[dict] = []
    stats = scan_once(db_factory, push=pushed.append)
    assert stats["fallback"] == 1
    assert len(pushed) == 1
    assert _get(db, r.id).state == "DELIVERED"
    evs = [e for e in list_events_impl(db, r.id) if e.event == "redelivered"]
    assert any(e.detail.get("reason") == "open_timeout" for e in evs)


# ============================================================================
# 10. scan_once：过期 → 无 rule → ARCHIVED
# ============================================================================


def test_scan_once_expire_then_archive_without_rule(db, db_factory):
    r = _create(db, trigger_time=datetime.now() - timedelta(seconds=5))
    scan_once(db_factory)  # 投递
    assert _get(db, r.id).state == "DELIVERED"
    # 推进时间超过 expire_after_minutes（默认 240min）
    future = datetime.now() + timedelta(hours=5)
    stats = scan_once(db_factory, now=future)
    assert stats["expired"] == 1
    assert stats["archived"] == 1
    row = _get(db, r.id)
    assert row.state == "ARCHIVED"
    assert "expired" in _events(db, r.id)


# ============================================================================
# 11. scan_once：带 rule 的重投
# ============================================================================


def test_scan_once_expire_retry_with_rule(db, db_factory):
    rule = create_rule_impl(
        db,
        ReminderRuleCreateRequest(
            type="test.ping",
            retry_policy={"max_retry": 1, "retry_interval_minutes": 30},
        ),
    )
    r = _create(db, trigger_time=datetime.now() - timedelta(seconds=5), rule_id=rule.id)
    t0 = datetime.now()
    scan_once(db_factory, now=t0)  # 投递
    assert _get(db, r.id).state == "DELIVERED"
    # 第一次过期 → 回 PENDING，retry_count=1，trigger_time = now+30min
    t1 = t0 + timedelta(hours=5)
    stats = scan_once(db_factory, now=t1)
    assert stats["expired"] == 1
    assert stats["retried"] == 1
    row = _get(db, r.id)
    assert row.state == "PENDING"
    assert row.retry_count == 1
    assert row.trigger_time > t1
    # 到点重投
    t2 = row.trigger_time + timedelta(seconds=1)
    stats = scan_once(db_factory, now=t2)
    assert stats["delivered"] == 1
    assert _get(db, r.id).state == "DELIVERED"
    # 再次过期 → 重投耗尽 → ARCHIVED
    t3 = t2 + timedelta(hours=5)
    stats = scan_once(db_factory, now=t3)
    assert stats["expired"] == 1
    assert stats["archived"] == 1
    row = _get(db, r.id)
    assert row.state == "ARCHIVED"
    assert row.retry_count == 1


# ============================================================================
# 12. ack
# ============================================================================


def test_ack_writes_event(db):
    r = _create(db)
    ok = ack_reminder_impl(db, r.id, device_id="dev-1")
    assert ok is True
    evs = [e for e in list_events_impl(db, r.id) if e.event == "ack"]
    assert len(evs) == 1
    assert evs[0].detail.get("device_id") == "dev-1"


# ============================================================================
# 13. summary/today
# ============================================================================


def test_summary_today_counts(db, db_factory):
    # 用 day_start 固定偏移构造，注入扫描时间，避免真实时刻引起的边界抖动
    day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    r1 = _create(db, trigger_time=day_start + timedelta(hours=13))  # 今日 PENDING
    r2 = _create(db, trigger_time=day_start + timedelta(hours=11))
    scan_once(db_factory, now=day_start + timedelta(hours=12))  # 仅 r2 → DELIVERED
    r3 = _create(db)
    feedback_reminder_impl(db, r3.id, FeedbackRequest(action="resolve"))
    r4 = _create(db)
    feedback_reminder_impl(db, r4.id, FeedbackRequest(action="dismiss"))

    summary = get_summary_today_impl(db)
    assert summary.date == datetime.now().strftime("%Y-%m-%d")
    # pending = 今日 PENDING(r1) + DELIVERED(r2)
    assert summary.pending == 2
    assert summary.resolved == 1
    assert summary.ignored == 1
    assert summary.expired == 0
    assert summary.delivered_total == 1


# ============================================================================
# 14. 设备注册 upsert
# ============================================================================


def test_device_register_upsert(db):
    req = DeviceRegisterRequest(device_id="uuid-1", device_name="Pixel", app_version="0.1.0")
    d1 = register_device_impl(db, req)
    assert d1.device_id == "uuid-1"
    # 同 device_id 二次注册不产生重复行
    req2 = DeviceRegisterRequest(device_id="uuid-1", device_name="Pixel 8", app_version="0.2.0")
    d2 = register_device_impl(db, req2)
    assert d2.id == d1.id
    assert d2.device_name == "Pixel 8"
    assert d2.app_version == "0.2.0"
    count = db.query(Device).filter(Device.device_id == "uuid-1").count()
    assert count == 1


# ============================================================================
# 15. 补偿拉取 pending
# ============================================================================


def test_list_pending_active_states_only(db):
    r1 = _create(db)  # PENDING
    r2 = _create(db)
    feedback_reminder_impl(db, r2.id, FeedbackRequest(action="resolve"))  # 终态
    pending = list_pending_impl(db)
    ids = {p.id for p in pending}
    assert r1.id in ids
    assert r2.id not in ids


# ============================================================================
# 16. ReminderPushManager（fake socket）
# ============================================================================


class _FakeSocket:
    def __init__(self, fail: bool = False):
        self.sent: List[str] = []
        self.fail = fail

    async def send_text(self, text: str):
        if self.fail:
            raise RuntimeError("connection dead")
        self.sent.append(text)


def test_push_manager_broadcast():
    async def run():
        mgr = ReminderPushManager()
        good = _FakeSocket()
        bad = _FakeSocket(fail=True)
        mgr.register("dev-good", good)
        mgr.register("dev-bad", bad)
        assert mgr.online_count() == 2
        sent = await mgr.broadcast_reminder({"id": 1, "title": "t"})
        assert sent == 1
        assert len(good.sent) == 1
        assert '"reminder.delivered"' in good.sent[0]
        # 失败的设备被摘除
        assert mgr.online_count() == 1
        assert mgr.is_online("dev-good")
        mgr.unregister("dev-good")
        assert mgr.online_count() == 0

    asyncio.run(run())


# ============================================================================
# 17. 提醒来源配置 CRUD
# ============================================================================


def test_create_source_config(db):
    cfg = create_source_config_impl(
        db,
        ReminderSourceConfigCreateRequest(
            source="rhythm.daily_brief",
            source_type="rhythm",
            default_priority="high",
            allowed_channels={"notification": True, "popup": False},
            quiet_hours_override={"enabled": False},
            description="早安简报",
        ),
    )
    assert cfg.id is not None
    assert cfg.source == "rhythm.daily_brief"
    assert cfg.source_type == "rhythm"
    assert cfg.enabled is True
    assert cfg.default_priority == "high"
    assert cfg.allowed_channels == {"notification": True, "popup": False}
    assert cfg.quiet_hours_override == {"enabled": False}
    assert cfg.description == "早安简报"


def test_create_source_config_duplicate_source(db):
    create_source_config_impl(
        db, ReminderSourceConfigCreateRequest(source="rhythm.daily_brief")
    )
    with pytest.raises(ReminderBadRequestError):
        create_source_config_impl(
            db, ReminderSourceConfigCreateRequest(source="rhythm.daily_brief")
        )


def test_update_source_config(db):
    cfg = create_source_config_impl(
        db, ReminderSourceConfigCreateRequest(source="rhythm.meal")
    )
    updated = update_source_config_impl(
        db,
        cfg.id,
        ReminderSourceConfigUpdateRequest(
            default_priority="urgent", allowed_channels={"notification": True}
        ),
    )
    assert updated.default_priority == "urgent"
    assert updated.allowed_channels == {"notification": True}


def test_list_source_configs_returns_inserted_rows(db):
    create_source_config_impl(
        db, ReminderSourceConfigCreateRequest(source="rhythm.daily_brief")
    )
    create_source_config_impl(
        db, ReminderSourceConfigCreateRequest(source="rhythm.meal")
    )
    rows = list_source_configs_impl(db)
    assert len(rows) == 2
    assert {r.source for r in rows} == {"rhythm.daily_brief", "rhythm.meal"}


def test_invalid_priority_on_create_raises_error(db):
    with pytest.raises(ReminderBadRequestError):
        create_source_config_impl(
            db,
            ReminderSourceConfigCreateRequest(
                source="rhythm.test", default_priority="invalid"
            ),
        )


# ============================================================================
# 18. rhythm 提醒来源细分
# ============================================================================


def test_scan_once_uses_rhythm_reminders_with_expected_source(db, db_factory):
    from datetime import time as _time

    from sail_server.model.rhythm import get_or_create_profile

    profile = get_or_create_profile(db)
    profile.sleep_end = "07:00"
    profile.sleep_start = "23:30"
    profile.spare_time_windows = {}
    db.commit()

    now = datetime.combine(datetime.now().date(), _time(12, 0))
    stats = scan_once(db_factory, now=now)
    assert stats["rhythm_brief_created"] > 0

    rhythm_sources = {
        r.source for r in db.query(Reminder).filter(Reminder.type.like("rhythm.%")).all()
    }
    assert "rhythm.daily_brief" in rhythm_sources or "rhythm.meal" in rhythm_sources
    # 确保 wake_up 简报使用细分来源
    daily_brief = db.query(Reminder).filter(Reminder.type == "rhythm.daily_brief").first()
    if daily_brief is not None:
        assert daily_brief.source == "rhythm.daily_brief"
