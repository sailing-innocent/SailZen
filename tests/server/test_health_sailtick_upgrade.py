# -*- coding: utf-8 -*-
# @file test_health_sailtick_upgrade.py
# @brief SailTick 驱动的健康管理升级端到端 API 回归测试
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""覆盖健康管理升级核心后端契约：
1. AI 动态体重计划（ai-sync 幂等更新、daily_targets 分段插值、自适应 tolerance_kg、Dashboard AI 评语）
2. 饮食时间戳范围查询（GET /health/diet?start=&end=）
3. 用户主动静默餐饮/状态上报（POST /tick/messages 自动落 DietLog + 幂等 ingest）
4. 每日睡前体重与健康日报（POST/GET /tick/reports 幂等 upsert + 防重复推送 Reminder）
5. 票据与真实 Reminder 联动（创建写 Reminder，回复自动关闭关联 Reminder）
6. 健康页聚合接口（GET /tick/health-summary）
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from litestar import Litestar, Router
from litestar.di import Provide
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sail_server.controller.health import (
    DietController,
    HealthDashboardController,
    WeightController,
    WeightPlanController,
)
from sail_server.controller.tick import TicketController
from sailzen_orm.orm_base import ORMBase


@pytest.fixture
def db_and_client():
    # 导入全部关联 ORM 确保建表完整
    import sailzen_orm  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    def dep():
        def gen():
            yield session

        return gen()

    health_router = Router(
        path="/health",
        dependencies={"router_dependency": Provide(dep)},
        route_handlers=[
            WeightController,
            WeightPlanController,
            DietController,
            HealthDashboardController,
        ],
    )
    tick_router = Router(
        path="/tick",
        dependencies={"router_dependency": Provide(dep)},
        route_handlers=[TicketController],
    )
    api_router = Router(path="/api/v1", route_handlers=[health_router, tick_router])
    app = Litestar(
        route_handlers=[api_router],
        plugins=[PydanticPlugin(prefer_alias=True)],
    )

    with TestClient(app=app) as client:
        yield session, client

    session.close()
    engine.dispose()


class TestAIDynamicWeightPlan:
    def test_ai_sync_creates_and_interpolates_dynamic_targets(self, db_and_client):
        db, client = db_and_client
        today = date.today()
        d_prev = (today - timedelta(days=2)).isoformat()
        d_next = (today + timedelta(days=2)).isoformat()

        # 先记一条体重
        r_w = client.post(
            "/api/v1/health/weight/",
            json={"value": 74.6, "htime": datetime.now().timestamp(), "tag": "raw"},
        )
        assert r_w.status_code == 201

        # SailTick 同步 AI 动态计划：两天前 75.0，两天后 74.2 → 今天插值应为 74.6
        r_sync = client.post(
            "/api/v1/health/weight/plan/ai-sync",
            json={
                "target_weight": "70.0",
                "plan_version": "v1.1",
                "phase_name": "稳态减脂期",
                "phase_rationale": "作息规律，温和每周降 0.5kg",
                "focus_notes": "午餐足量蛋白+晚餐少精制碳水",
                "tolerance_kg": 0.8,
                "ai_summary": "近3天稳步下降，节奏很舒服",
                "daily_targets": {d_prev: 75.0, d_next: 74.2},
            },
        )
        assert r_sync.status_code == 201
        plan = r_sync.json()
        assert plan["managedBy"] == "sailtick"
        assert plan["curveType"] == "ai_dynamic"
        assert plan["phaseName"] == "稳态减脂期"
        assert plan["toleranceKg"] == pytest.approx(0.8)

        # 验证 /weight/target 走 AI 动态节点插值而非死板线性
        r_target = client.get(f"/api/v1/health/weight/target?date={today.isoformat()}")
        assert r_target.status_code == 200
        assert r_target.json()["value"] == pytest.approx(74.6, abs=0.05)
        assert r_target.json()["managed_by"] == "sailtick"

        # 验证 /weight/plan/expected 与 /progress 正常返回
        start_ts = (datetime.now() - timedelta(days=2)).timestamp()
        end_ts = (datetime.now() + timedelta(days=2)).timestamp()
        r_exp = client.get(f"/api/v1/health/weight/plan/expected?start={start_ts}&end={end_ts}")
        assert r_exp.status_code == 200
        assert len(r_exp.json()["points"]) >= 4

        r_prog = client.get("/api/v1/health/weight/plan/progress")
        assert r_prog.status_code == 200
        assert r_prog.json()["expected_current_weight"] == pytest.approx(74.6, abs=0.05)

        # 幂等再次 ai-sync：合并 daily_targets，不新建重复计划
        d_future = (today + timedelta(days=7)).isoformat()
        r_sync2 = client.post(
            "/api/v1/health/weight/plan/ai-sync",
            json={
                "plan_version": "v1.2",
                "phase_name": "平台期缓冲",
                "tolerance_kg": 1.0,
                "ai_summary": "进入小平台期，放宽波动容忍度",
                "daily_targets": {d_future: 73.8},
            },
        )
        assert r_sync2.status_code == 201
        plan2 = r_sync2.json()
        assert plan2["id"] == plan["id"]
        assert plan2["planVersion"] == "v1.2"
        assert d_prev in plan2["dailyTargets"]
        assert d_future in plan2["dailyTargets"]

        # 验证 Dashboard 使用 AI 教练评语而非机械化警告
        r_dash = client.get("/api/v1/health/dashboard")
        assert r_dash.status_code == 200
        warnings = r_dash.json()["warnings"]
        assert any("AI 教练：" in w for w in warnings)
        assert not any("精制碳水" in w for w in warnings)


class TestSilentMessagesAndDailyReports:
    def test_proactive_diet_message_auto_logs_diet_and_ingests(self, db_and_client):
        db, client = db_and_client
        # 用户主动发一条餐饮消息（无需等待 AI 即时回复）
        r = client.post(
            "/api/v1/tick/messages",
            json={
                "category": "diet",
                "content": "午饭吃了食堂鸡胸肉+半碗米饭+西兰花",
                "meta": {"meal_type": "lunch"},
                "source_channel": "android",
                "auto_log_diet": True,
            },
        )
        assert r.status_code == 201
        msg = r.json()
        assert msg["status"] == "unread"
        assert msg["meta"].get("linked_diet_id") is not None

        # 验证饮食范围查询能立刻查到该条记录
        start_ts = (datetime.now() - timedelta(days=1)).timestamp()
        end_ts = (datetime.now() + timedelta(days=1)).timestamp()
        r_diets = client.get(f"/api/v1/health/diet?start={start_ts}&end={end_ts}")
        assert r_diets.status_code == 200
        assert any("鸡胸肉" in d["description"] for d in r_diets.json())

        # SailTick SCAN 拉取 unread 并标记 ingested（幂等）
        unread = client.get("/api/v1/tick/messages?status=unread").json()
        assert len(unread) == 1
        r_ing = client.post(
            "/api/v1/tick/messages/ingest",
            json={"message_ids": [msg["id"]], "tick_id": "tick_test_1"},
        )
        assert r_ing.status_code == 201
        assert r_ing.json()["ingested"] == 1
        # 重复 ingest 返回 0
        r_ing2 = client.post(
            "/api/v1/tick/messages/ingest",
            json={"message_ids": [msg["id"]], "tick_id": "tick_test_2"},
        )
        assert r_ing2.json()["ingested"] == 0

    def test_daily_report_upsert_and_health_summary(self, db_and_client):
        db, client = db_and_client
        from sailzen_orm.reminder import Reminder

        today_str = date.today().isoformat()
        r1 = client.post(
            "/api/v1/tick/reports",
            json={
                "report_date": today_str,
                "tick_id": "t_sleep_1",
                "title": f"{today_str} 睡前体重与健康日报",
                "summary": "今日体重 74.6kg，饮食结构均衡，早点休息。",
                "body_markdown": "## 今日体重\n- 74.6kg",
                "weight_snapshot": {"latest_kg": 74.6},
                "diet_summary": {"count": 2},
                "tomorrow_focus": ["明早称重", "午饭多蔬菜"],
                "push": True,
            },
        )
        assert r1.status_code == 201
        rep = r1.json()
        assert rep["pushed"] is True

        # 确认持久化了一条真实 source='agent' 的 Reminder 供 Android 离线/在线可靠接收
        rems = db.query(Reminder).filter(Reminder.type == "tick.daily_report").all()
        assert len(rems) == 1
        assert rems[0].source == "agent"

        # 同一天重复 upsert 更新内容，但不重复轰炸推送
        r2 = client.post(
            "/api/v1/tick/reports",
            json={
                "report_date": today_str,
                "tick_id": "t_sleep_2",
                "title": f"{today_str} 睡前体重与健康日报（更新）",
                "summary": "补充了晚间加餐记录，整体仍在舒适区间。",
                "push": True,
            },
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == rep["id"]
        assert db.query(Reminder).filter(Reminder.type == "tick.daily_report").count() == 1

        # 读取 latest 与 health-summary
        latest = client.get("/api/v1/tick/reports/latest").json()
        assert latest["report_date"] == today_str
        summary = client.get("/api/v1/tick/health-summary").json()
        assert summary["latest_report"]["report_date"] == today_str

    def test_ticket_reply_resolves_linked_agent_reminder(self, db_and_client):
        db, client = db_and_client
        from sailzen_orm.reminder import Reminder

        r_t = client.post(
            "/api/v1/tick/tickets",
            json={
                "type": "question",
                "topic": "wake_time",
                "title": "平时几点起床？",
                "body": "帮我避开安静时段打扰",
                "priority": "normal",
                "push": "force",
                "meta": {"quick_replies": ["7:30", "8:00"]},
            },
        )
        assert r_t.status_code == 201
        tid = r_t.json()["id"]
        assert r_t.json()["topic"] == "wake_time"
        assert r_t.json()["meta"]["quick_replies"] == ["7:30", "8:00"]

        rems = db.query(Reminder).filter(Reminder.source == "agent").all()
        assert len(rems) == 1
        assert rems[0].payload["ticket_id"] == tid

        # 回复票据后，关联的 agent Reminder 自动转 RESOLVED
        r_rep = client.post(f"/api/v1/tick/tickets/{tid}/reply", json={"reply": "7:30"})
        assert r_rep.status_code == 201
        db.expire_all()
        rem = db.get(Reminder, rems[0].id)
        assert rem.state == "RESOLVED"
