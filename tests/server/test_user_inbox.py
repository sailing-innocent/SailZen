# -*- coding: utf-8 -*-
# @file test_user_inbox.py
# @brief Unit & Integration Tests for UserProfile, UserInbox, Auto-Resolver & UserSyncHub
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一 UserProfile + UserInbox + 跨端自动消解引擎测试。

重点验证：
1. 单用户免登录自动引导（UserProfile id=1 / slug='owner' 幂等创建 & 配置更新广播）
2. 教练提问午餐（SailTickTicket）→ 投影到 UserInbox + 镜像 Reminder
3. 核心痛点场景：用户在 Web 健康页记午餐（POST /health/diet 或 /tick/messages）
   → 自动消解 UserInboxItem + 自动回复 SailTickTicket + 关闭 Reminder + WS 广播撤回！
4. 双向同步：Android 收件箱回复/忽略/延后 → 同步更新 SailTickTicket 与 Reminder
5. 单调游标同步（sync_inbox_impl(since_seq=N)）精确返回终态变更与 active_ids，杜绝 Room 残留
6. dedup_key 去重：同日同主题重复创建不产生多条未处理卡片
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sail_server.application.dto.health import DietCreateRequest, MealType
from sail_server.application.dto.reminder import FeedbackRequest, ReminderCreateRequest
from sail_server.application.dto.tick import TickMessageCreateRequest, TicketCreateRequest
from sail_server.application.dto.user import UserDeviceRegisterRequest, UserProfileUpdateRequest
from sail_server.model.health import create_diet_impl
from sail_server.model.inbox import (
    STATUS_ANSWERED,
    STATUS_DISMISSED,
    STATUS_RESOLVED,
    STATUS_SNOOZED,
    dismiss_inbox_item_impl,
    get_inbox_summary_impl,
    list_inbox_impl,
    reply_inbox_item_impl,
    snooze_inbox_item_impl,
    sync_inbox_impl,
)
from sail_server.model.reminder import create_reminder_impl, feedback_reminder_impl
from sail_server.model.tick import create_message_impl, create_ticket_impl, reply_ticket_impl
from sail_server.model.user import (
    ensure_default_user_profile,
    get_user_bootstrap_impl,
    is_user_in_quiet_hours,
    register_user_device_impl,
    update_user_profile_impl,
)
from sail_server.utils.user_context import UserContext
from sail_server.utils.user_sync_ws import UserSyncHub
from sailzen_orm import ORMBase
from sailzen_orm.inbox import UserInboxItem
from sailzen_orm.reminder import Reminder
from sailzen_orm.tick import SailTickTicket


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        ensure_default_user_profile(session)
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: List[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def test_user_bootstrap_single_user_auto(db: Session):
    """单用户默认 owner 自动引导，无需登录，支持资料修改与安静时段判断。"""
    ctx = UserContext(user_id=1, slug="owner", client_type="android", device_id="dev-1")
    boot = get_user_bootstrap_impl(db, ctx)

    assert boot.auth_mode == "single_user_auto"
    assert boot.requires_login is False
    assert boot.user.id == 1
    assert boot.user.slug == "owner"
    assert boot.user.quiet_hours["start"] == "23:00"
    assert boot.user.quiet_hours["end"] == "08:00"

    # 更新昵称与安静时段
    updated = update_user_profile_impl(
        db,
        1,
        UserProfileUpdateRequest(
            display_name="航行者",
            quiet_hours={"enabled": True, "start": "22:30", "end": "07:30"},
        ),
    )
    assert updated.display_name == "航行者"
    assert is_user_in_quiet_hours(db, 1, datetime(2026, 11, 24, 23, 0)) is True
    assert is_user_in_quiet_hours(db, 1, datetime(2026, 11, 24, 12, 0)) is False

    # 注册 Android 与 Web 终端
    dev_and = register_user_device_impl(
        db,
        1,
        UserDeviceRegisterRequest(
            device_id="android-uuid-1",
            device_name="Pixel 9",
            platform="android",
            client_type="android",
            app_version="1.2.0",
        ),
    )
    dev_web = register_user_device_impl(
        db,
        1,
        UserDeviceRegisterRequest(
            device_id="web-browser-1",
            device_name="Chrome Desktop",
            platform="web",
            client_type="web",
        ),
    )
    assert dev_and.user_id == 1
    assert dev_web.client_type == "web"


def test_lunch_question_auto_resolved_when_logged_in_health_tab(db: Session):
    """核心痛点：教练问中午午餐如何处理，用户在 Web 健康页记午餐 → 收件箱/票据/提醒全部自动关闭。"""
    # 1. SailTick 创建午餐提问票据（强制推送到 Android）
    ticket = create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="tick-midday-1",
            type="question",
            topic="diet_lunch",
            title="中午的午餐打算怎么安排？",
            body="今天上午有会议，午餐是吃食堂还是点外卖？",
            priority="high",
            push="force",
            meta={"quick_replies": ["食堂轻食", "点外卖沙拉", "已经吃过了"]},
        ),
    )

    # 确认投影到统一收件箱，且拿到初始 sync_seq
    sync_before = sync_inbox_impl(db, 1, since_seq=0)
    assert sync_before.active_count == 1
    assert sync_before.unread_count == 1
    assert len(sync_before.active_ids) == 1
    inbox_item = sync_before.changes[0]
    assert inbox_item.ticket_id == ticket.id
    assert inbox_item.reminder_id is not None
    assert inbox_item.source_domain == "sailtick"
    assert inbox_item.item_kind == "question"
    seq_after_create = sync_before.latest_seq

    # 2. 用户在 Web 健康 Tab 直接记录了一顿午餐（未在收件箱点回复！）
    create_diet_impl(
        db,
        DietCreateRequest(
            meal_type=MealType.LUNCH,
            description="食堂鸡胸肉+半碗米饭+西兰花",
            calories=520,
        ),
    )

    # 3. 验证：Android 用旧游标 seq_after_create 增量同步，能精确收到终态变更 + 空 active_ids！
    sync_after = sync_inbox_impl(db, 1, since_seq=seq_after_create)
    assert sync_after.active_count == 0
    assert sync_after.active_ids == []
    assert sync_after.latest_seq > seq_after_create
    assert len(sync_after.changes) == 1
    resolved_item = sync_after.changes[0]
    assert resolved_item.id == inbox_item.id
    assert resolved_item.status == STATUS_ANSWERED
    assert "午餐" in resolved_item.resolution_summary
    assert "食堂鸡胸肉" in resolved_item.resolution_summary

    # 4. 验证关联 SailTickTicket 已被自动回复（下轮 SCAN 可吸收，不会再重复提问）
    t_row = db.get(SailTickTicket, ticket.id)
    assert t_row is not None
    assert t_row.status == "replied"
    assert "食堂鸡胸肉" in (t_row.reply or "")

    # 5. 验证关联 Reminder 已关闭为 RESOLVED
    r_row = db.get(Reminder, inbox_item.reminder_id)
    assert r_row is not None
    assert r_row.state == "RESOLVED"


def test_lunch_question_auto_resolved_via_silent_coach_message(db: Session):
    """用户在 Web /health 面板发静默餐饮消息（POST /tick/messages）同样自动消解午餐提问。"""
    ticket = create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="tick-midday-2",
            type="question",
            topic="canteen",
            title="中午的午餐如何处理？",
            body="顺便了解一下你午饭的固定来源",
            priority="high",
            push="force",
        ),
    )

    assert len(list_inbox_impl(db, 1, tab="active")) == 1

    create_message_impl(
        db,
        TickMessageCreateRequest(
            direction="user_to_agent",
            category="diet",
            content="公司食堂番茄炒蛋+清炒油菜+半碗米饭",
            meta={"meal_type": "lunch"},
            source_channel="web",
            auto_log_diet=False,
        ),
    )

    assert len(list_inbox_impl(db, 1, tab="active")) == 0
    history = list_inbox_impl(db, 1, tab="history")
    assert len(history) == 1
    assert history[0].status == STATUS_ANSWERED
    assert history[0].resolution_source == "auto:web:health.diet.logged"

    t_row = db.get(SailTickTicket, ticket.id)
    assert t_row.status == "replied"


def test_bidirectional_sync_inbox_and_legacy_reminder_feedback(db: Session):
    """收件箱回复/暂缓/忽略 与 旧版 Reminder 反馈双向同步至 SailTickTicket。"""
    # 场景 A：通过统一收件箱回复
    t1 = create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="t1",
            type="question",
            topic="sleep_time",
            title="昨晚几点睡的？",
            priority="high",
            push="force",
        ),
    )
    items = list_inbox_impl(db, 1, tab="active")
    assert len(items) == 1
    res = reply_inbox_item_impl(
        db, 1, items[0].id, "昨晚 23:30 睡的", actor_client="android", device_id="and-1"
    )
    assert res.status == STATUS_ANSWERED
    assert db.get(SailTickTicket, t1.id).status == "replied"
    assert db.get(Reminder, res.reminder_id).state == "RESOLVED"

    # 场景 B：通过旧版 Reminder dismiss 反馈 → 同样关闭收件箱与 SailTickTicket
    t2 = create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="t2",
            type="question",
            topic="gym_access",
            title="附近有健身房吗？",
            priority="high",
            push="force",
        ),
    )
    active2 = list_inbox_impl(db, 1, tab="active")
    assert len(active2) == 1
    rem_id = active2[0].reminder_id
    feedback_reminder_impl(db, rem_id, FeedbackRequest(action="dismiss"))

    assert len(list_inbox_impl(db, 1, tab="active")) == 0
    assert db.get(UserInboxItem, active2[0].id).status == STATUS_DISMISSED
    assert db.get(SailTickTicket, t2.id).status == "resolved"


def test_inbox_dedup_and_summary(db: Session):
    """同日同 topic 不重复产生两条活跃卡片，且 summary 统计准确。"""
    create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="t-dup-1",
            type="question",
            topic="diet_dinner",
            title="今晚晚餐计划",
            priority="normal",
            push="none",
        ),
    )
    create_ticket_impl(
        db,
        TicketCreateRequest(
            tick_id="t-dup-2",
            type="question",
            topic="diet_dinner",
            title="今晚晚餐计划（补充）",
            priority="high",
            push="none",
        ),
    )

    active = list_inbox_impl(db, 1, tab="active")
    assert len(active) == 1
    assert active[0].title == "今晚晚餐计划（补充）"

    snooze_inbox_item_impl(db, 1, active[0].id, option="1h", actor_client="web")
    assert list_inbox_impl(db, 1, tab="active")[0].status == STATUS_SNOOZED

    dismiss_inbox_item_impl(db, 1, active[0].id, reason="不需要提醒", actor_client="web")
    summary = get_inbox_summary_impl(db, 1)
    assert summary.active == 0
    assert summary.dismissed == 1


def test_user_sync_hub_broadcasts_to_android_and_web():
    """UserSyncHub 按 user_id 同时向 Android 与 Web 终端广播撤回事件。"""
    hub = UserSyncHub()
    ws_android = FakeWebSocket()
    ws_web = FakeWebSocket()
    hub.register("android-1", ws_android, user_id=1, client_type="android")
    hub.register("web-1", ws_web, user_id=1, client_type="web")

    sent = asyncio.run(
        hub.broadcast_inbox_resolved(
            user_id=1,
            payload={"inbox_item_id": 10, "reminder_id": 20, "status": "answered", "sync_seq": 99},
        )
    )
    assert sent == 2
    assert ws_android.sent[0]["type"] == "inbox.item_resolved"
    assert ws_android.sent[0]["data"]["reminder_id"] == 20
    assert ws_web.sent[0]["type"] == "inbox.item_resolved"


def test_http_e2e_user_bootstrap_and_cross_channel_inbox_sync(db: Session):
    """端到端 HTTP 路由验证：免登录 bootstrap → 创建午餐提问 → Web 记午餐 → Android 游标对账清零。"""
    from litestar import Litestar, Router
    from litestar.di import Provide
    from litestar.plugins.pydantic import PydanticPlugin
    from litestar.testing import TestClient

    from sail_server.controller.health import DietController
    from sail_server.controller.inbox import InboxController
    from sail_server.controller.tick import TicketController
    from sail_server.controller.user import UserController

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    api_router = Router(
        path="/api/v1",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[
            Router(path="/user", route_handlers=[UserController]),
            Router(path="/inbox", route_handlers=[InboxController]),
            Router(path="/tick", route_handlers=[TicketController]),
            Router(path="/health", route_handlers=[DietController]),
        ],
    )
    app = Litestar(route_handlers=[api_router], plugins=[PydanticPlugin(prefer_alias=True)])

    with TestClient(app=app) as client:
        # 1. 免登录静默引导
        r_boot = client.get("/api/v1/user/bootstrap", headers={"X-SailZen-Client": "android"})
        assert r_boot.status_code == 200
        boot = r_boot.json()
        assert boot["requires_login"] is False
        assert boot["auth_mode"] == "single_user_auto"
        assert boot["user"]["slug"] == "owner"

        # 2. 更新 UserProfile
        r_patch = client.patch(
            "/api/v1/user/profile",
            json={"display_name": "测试用户", "quiet_hours": {"enabled": True, "start": "23:30", "end": "07:30"}},
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["display_name"] == "测试用户"

        # 3. 教练创建午餐提问
        r_ticket = client.post(
            "/api/v1/tick/tickets",
            json={
                "tick_id": "e2e-midday",
                "type": "question",
                "topic": "diet_lunch",
                "title": "中午午餐如何处理？",
                "body": "食堂还是外卖？",
                "priority": "high",
                "push": "force",
            },
        )
        assert r_ticket.status_code == 201

        # 4. Android 拉取统一收件箱
        r_sync1 = client.get("/api/v1/inbox/sync?since_seq=0")
        assert r_sync1.status_code == 200
        s1 = r_sync1.json()
        assert s1["active_count"] == 1
        seq1 = s1["latest_seq"]

        # 5. 用户在 Web 健康 Tab 记录午餐
        r_diet = client.post(
            "/api/v1/health/diet",
            headers={"X-SailZen-Client": "web"},
            json={"meal_type": "lunch", "description": "食堂牛肉面少油", "calories": 580},
        )
        assert r_diet.status_code == 201

        # 6. Android 用旧游标 seq1 对账：收到 answered 终态变更 + 空 active_ids！
        r_sync2 = client.get(f"/api/v1/inbox/sync?since_seq={seq1}")
        assert r_sync2.status_code == 200
        s2 = r_sync2.json()
        assert s2["active_count"] == 0
        assert s2["active_ids"] == []
        assert len(s2["changes"]) == 1
        assert s2["changes"][0]["status"] == "answered"
        assert "牛肉面" in s2["changes"][0]["resolution_summary"]


def test_device_identity_v2_fingerprint_takeover_and_cleanup(db: Session):
    """Device Identity v2：验证稳定指纹原地接管、旧版同型号防重与一键清理重复/模拟器/僵尸终端。"""
    from sail_server.application.dto.user import UserDeviceCleanupRequest
    from sail_server.model.user import cleanup_user_devices_impl, list_user_devices_impl
    from sailzen_orm.reminder import Device

    # 1. 模拟旧版历史残留：同一型号手机 PNM-AN10 多次重装产生 3 条离线记录 + 1 个模拟器 + 2 个重复 Chrome Web
    now = datetime.now()
    db.add_all(
        [
            Device(
                user_id=1,
                device_id="old-uuid-1",
                device_name="PNM-AN10",
                platform="android",
                client_type="android",
                app_version="0.1.0",
                is_active=True,
                last_seen_at=now - timedelta(days=60),
            ),
            Device(
                user_id=1,
                device_id="old-uuid-2",
                device_name="PNM-AN10",
                platform="android",
                client_type="android",
                app_version="0.3.0",
                is_active=True,
                last_seen_at=now - timedelta(hours=1),
            ),
            Device(
                user_id=1,
                device_id="emu-uuid-1",
                device_name="sdk_gphone64_x86_64",
                platform="android",
                client_type="android",
                app_version="0.2.0",
                is_active=True,
                last_seen_at=now - timedelta(hours=2),
            ),
            Device(
                user_id=1,
                device_id="web-old-1",
                device_name="Chrome Web",
                platform="web",
                client_type="web",
                app_version="site",
                is_active=True,
                last_seen_at=now - timedelta(hours=3),
            ),
            Device(
                user_id=1,
                device_id="web-old-2",
                device_name="Chrome Web",
                platform="web",
                client_type="web",
                app_version="site",
                is_active=True,
                last_seen_at=now - timedelta(minutes=5),
            ),
        ]
    )
    db.commit()

    # 2. 新版 Android 客户端携带稳定硬件指纹注册：原地接管最近 PNM-AN10 并停用旧重复记录
    d1 = register_user_device_impl(
        db,
        1,
        UserDeviceRegisterRequest(
            device_id="android-fp-aabbcc1122334455",
            device_name="HONOR PNM-AN10",
            platform="android",
            client_type="android",
            app_version="0.3.1",
            fingerprint="android:aabbcc1122334455",
            is_emulator=False,
            capabilities={"identity_v": 2, "model": "PNM-AN10"},
        ),
    )
    assert d1.device_id == "android-fp-aabbcc1122334455"
    assert d1.fingerprint == "android:aabbcc1122334455"

    # 即使再次换 device_id 但指纹一致，也必须原地接管同一行（不增加新行）
    d2 = register_user_device_impl(
        db,
        1,
        UserDeviceRegisterRequest(
            device_id="android-fp-reinstalled-id",
            device_name="HONOR PNM-AN10",
            platform="android",
            client_type="android",
            app_version="0.3.2",
            fingerprint="android:aabbcc1122334455",
            is_emulator=False,
            capabilities={"identity_v": 2, "model": "PNM-AN10"},
        ),
    )
    assert d2.id == d1.id
    assert d2.device_id == "android-fp-reinstalled-id"

    # 3. 执行一键去重清理：清除模拟器与重复 Chrome Web，仅保留 1 部手机 + 1 个 Chrome
    cleaned = cleanup_user_devices_impl(
        db,
        1,
        UserDeviceCleanupRequest(deduplicate=True, remove_emulators=True, stale_days=30),
    )
    assert cleaned.deactivated_count == 2  # emu-uuid-1 + web-old-1
    assert cleaned.remaining_count == 2
    remaining = list_user_devices_impl(db, 1, active_only=True)
    assert {r.device_id for r in remaining} == {"android-fp-reinstalled-id", "web-old-2"}


