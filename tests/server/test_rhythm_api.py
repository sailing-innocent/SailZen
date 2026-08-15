# -*- coding: utf-8 -*-
# @file test_rhythm_api.py
# @brief Rhythm HTTP API 测试（Litestar TestClient：400/404/409 映射 + plan/day 冒烟）
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
Rhythm REST API 测试

- 端到端：建模板 → capture → hint 改判 → confirm → plan/day → timeline → checkin → review
- 异常映射：非法 kind_meta → 400；不存在资源 → 404；状态机冲突 → 409
"""

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient

from sail_server.controller.rhythm import (
    AffairController,
    CheckinController,
    EnergyController,
    PlanController,
    PolicyController,
    ReviewController,
    TemplateController,
    TimelineController,
    VentureController,
)

from .conftest import TEST_DATE, make_template_payload

pytestmark = pytest.mark.server


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """挂载 rhythm 全部控制器的测试 App（db 依赖覆盖为内存 SQLite 会话）"""

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path="/api/v1/rhythm",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[
            AffairController,
            TimelineController,
            TemplateController,
            CheckinController,
            VentureController,
            EnergyController,
            PolicyController,
            PlanController,
            ReviewController,
        ],
    )
    app = Litestar(route_handlers=[router])
    with TestClient(app=app) as client:
        yield client


BASE = "/api/v1/rhythm"


# ============================================================================
# 异常映射
# ============================================================================


class TestErrorMapping:
    def test_invalid_kind_meta_400(self, client: TestClient):
        resp = client.post(
            f"{BASE}/affair/",
            json={"title": "bad habit", "kind": "habit",
                  "kind_meta": {"freq_per_week": "abc"}},
        )
        assert resp.status_code == 400

    def test_get_missing_affair_404(self, client: TestClient):
        resp = client.get(f"{BASE}/affair/99999")
        assert resp.status_code == 404

    def test_state_conflict_409(self, client: TestClient):
        create = client.post(f"{BASE}/affair/", json={"title": "一句话"})
        assert create.status_code == 201
        affair_id = create.json()["id"]
        # generic 未分拣 confirm → 409
        resp = client.post(
            f"{BASE}/affair/{affair_id}/state", json={"action": "confirm"}
        )
        assert resp.status_code == 409

    def test_move_pinned_block_409(self, client: TestClient):
        client.post(f"{BASE}/template/", json=make_template_payload())
        plan = client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})
        assert plan.status_code == 201
        pinned = [b for b in plan.json()["blocks"] if b["pinned"]]
        assert pinned
        resp = client.post(
            f"{BASE}/timeline/block/{pinned[0]['id']}/move",
            json={"start_time": "2026-10-26T10:00:00", "end_time": "2026-10-26T11:00:00"},
        )
        assert resp.status_code == 409


# ============================================================================
# 端到端主流程
# ============================================================================


class TestEndToEnd:
    def test_full_flow(self, client: TestClient):
        """建模板 → capture → AI hint → 采纳 → confirm → plan → timeline → checkin → review"""
        # 1. 模板
        resp = client.post(f"{BASE}/template/", json=make_template_payload())
        assert resp.status_code == 201
        assert resp.json()["name"] == "weekday"

        active = client.get(f"{BASE}/template/active", params={"date": str(TEST_DATE)})
        assert active.status_code == 200

        # 2. 捕获（generic → INBOX）
        resp = client.post(f"{BASE}/affair/", json={"title": "每周运动3次"})
        assert resp.status_code == 201
        affair = resp.json()
        assert affair["kind"] == "generic"
        assert affair["state"] == "INBOX"
        affair_id = affair["id"]

        # 3. AI 写回建议（PUT ai_hint）
        resp = client.put(
            f"{BASE}/affair/{affair_id}",
            json={
                "ai_hint": {
                    "kind": "habit",
                    "domain": "life",
                    "kind_meta": {"freq_per_week": 3, "min_session_minutes": 30,
                                  "preferred_slots": ["19:00-21:00"]},
                    "importance": 4,
                    "reason": "建设性目标 → habit",
                }
            },
        )
        assert resp.status_code == 200

        # 4. 采纳建议（kind 改判）
        resp = client.post(
            f"{BASE}/affair/{affair_id}/confirm-hint", json={"accept": True}
        )
        assert resp.status_code == 201
        assert resp.json()["kind"] == "habit"

        # 5. confirm → ACTIVE
        resp = client.post(
            f"{BASE}/affair/{affair_id}/state", json={"action": "confirm"}
        )
        assert resp.status_code == 201
        assert resp.json()["state"] == "ACTIVE"

        # 6. plan/day → 骨架 + buffer + habit 块
        resp = client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})
        assert resp.status_code == 201
        plan = resp.json()
        types = {b["block_type"] for b in plan["blocks"]}
        assert "sleep" in types
        assert "work_window" in types
        assert "buffer" in types
        assert "habit" in types

        # 7. timeline
        resp = client.get(f"{BASE}/timeline/day", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        timeline = resp.json()
        assert timeline["plan_version"] >= 1
        assert "life" in timeline["domain_minutes"]

        # 8. checkin
        resp = client.post(
            f"{BASE}/checkin/",
            json={"affair_id": affair_id, "result": "done", "log_date": str(TEST_DATE)},
        )
        assert resp.status_code == 201
        assert resp.json()["result"] == "done"

        today = client.get(f"{BASE}/checkin/today", params={"date": str(TEST_DATE)})
        assert today.status_code == 200
        assert today.json()["habits"][0]["week_done_count"] == 1

        # 9. review
        resp = client.get(f"{BASE}/review/day", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        assert 0 <= resp.json()["rhythm_score"] <= 100

        resp = client.get(f"{BASE}/review/week", params={"span": "W2026-44"})
        assert resp.status_code == 200
        assert resp.json()["habit_consistency"] > 0

    def test_venture_progress_flow(self, client: TestClient):
        """venture：confirm → milestone → progress → milestone done"""
        resp = client.post(
            f"{BASE}/affair/",
            json={
                "title": "2027-04 独立游戏上线",
                "kind": "venture",
                "domain": "career",
                "kind_meta": {"target_date": "2027-04-01",
                              "weekly_budget_hours": 8, "total_est_hours": 300},
            },
        )
        assert resp.status_code == 201
        vid = resp.json()["id"]
        client.post(f"{BASE}/affair/{vid}/state", json={"action": "confirm"})

        resp = client.post(
            f"{BASE}/venture/{vid}/milestone", json={"title": "demo 完成"}
        )
        assert resp.status_code == 201
        mid = resp.json()["id"]

        resp = client.get(f"{BASE}/venture/{vid}/progress")
        assert resp.status_code == 200
        progress = resp.json()
        assert progress["weekly_budget_hours"] == 8.0
        assert progress["weeks_left"] is not None
        assert len(progress["milestones"]) == 1
        assert progress["completion_ratio"] == 0.0

        resp = client.post(f"{BASE}/venture/milestone/{mid}/done")
        assert resp.status_code == 201
        resp = client.get(f"{BASE}/venture/{vid}/progress")
        assert resp.json()["completion_ratio"] == 1.0

    def test_policy_and_profile(self, client: TestClient):
        resp = client.get(f"{BASE}/energy/profile")
        assert resp.status_code == 200
        assert resp.json()["daily_energy_budget"] == 100

        resp = client.put(
            f"{BASE}/energy/profile",
            json={"name": "default", "work_hours_cap": 7.0, "career_weight": 0.8},
        )
        assert resp.status_code == 200
        assert resp.json()["work_hours_cap"] == 7.0

        resp = client.post(
            f"{BASE}/policy/",
            json={"name": "事业仅占业余时间区", "rule_type": "spare_time_guard",
                  "params": {}, "scope": "day"},
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]
        resp = client.put(f"{BASE}/policy/{pid}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_conflicts_endpoint(self, client: TestClient):
        client.post(f"{BASE}/template/", json=make_template_payload())
        client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})
        resp = client.get(f"{BASE}/plan/conflicts", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        assert "encroachments" in resp.json()


class TestMergedPEMSFeatures:
    def test_urgency_ddl_range_query(self, client: TestClient):
        """list_affairs 支持 urgency_ddl 范围过滤"""
        resp = client.post(
            f"{BASE}/affair/",
            json={
                "title": "DDL 今天",
                "kind": "task_oneoff",
                "urgency_ddl": f"{TEST_DATE}T23:59:00",
            },
        )
        assert resp.status_code == 201

        resp = client.get(
            f"{BASE}/affair/",
            params={
                "urgency_ddl_after": f"{TEST_DATE}T00:00:00",
                "urgency_ddl_before": f"{TEST_DATE}T23:59:59",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["affairs"]) >= 1
        titles = {a["title"] for a in data["affairs"]}
        assert "DDL 今天" in titles

    def test_health_checkin_weight(self, client: TestClient):
        """健康速记双写 health 表与 rhythm 打卡日志"""
        resp = client.post(
            f"{BASE}/checkin/health",
            json={
                "collection_type": "weight",
                "log_date": str(TEST_DATE),
                "payload": {"value_kg": 70.5},
                "note": "晨重",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["collection_type"] == "weight"
        assert data["affair_id"] is not None

    def test_day_view(self, client: TestClient):
        """统一日视图包含时间线、能量、打卡、健康信号"""
        client.post(f"{BASE}/template/", json=make_template_payload())
        client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})
        client.post(
            f"{BASE}/checkin/health",
            json={
                "collection_type": "exercise",
                "log_date": str(TEST_DATE),
                "payload": {"activity": "跑步", "duration_minutes": 30},
            },
        )
        resp = client.get(f"{BASE}/timeline/day-view", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        data = resp.json()
        assert "health_signals" in data
        assert data["energy_budget"] == 100
        assert data["energy_available"] >= 0
        assert any(s["signal_type"] == "exercise" for s in data["health_signals"])
