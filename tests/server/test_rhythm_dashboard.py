# -*- coding: utf-8 -*-
# @file test_rhythm_dashboard.py
# @brief Rhythm Dashboard aggregate API tests
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
测试 /api/v1/rhythm/dashboard 聚合接口。
"""

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient

from sail_server.controller.rhythm import (
    AffairController,
    AdminController,
    CheckinController,
    DashboardController,
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
    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path="/api/v1/rhythm",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[
            DashboardController,
            AdminController,
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


class TestDashboard:
    def test_dashboard_aggregate(self, client: TestClient):
        """dashboard 聚合接口应返回时间线、评分、打卡、画像、策略、冲突、优先级事务"""
        client.post(f"{BASE}/template/", json=make_template_payload())
        client.post(
            f"{BASE}/affair/",
            json={"title": "每周运动3次", "kind": "habit", "kind_meta": {
                "freq_per_week": 3, "min_session_minutes": 30, "preferred_slots": ["19:00-21:00"]
            }},
        )
        client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})

        resp = client.get(f"{BASE}/dashboard", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == str(TEST_DATE)
        assert "timeline" in data
        assert "day_review" in data
        assert "week_review" in data
        assert "today_checkins" in data
        assert "energy_profile" in data
        assert "policies" in data
        assert "conflicts" in data
        assert "inbox_summary" in data
        assert "overdue_summary" in data
        assert "today_due_summary" in data
        assert data["energy_profile"]["is_default"] is True

    def test_dashboard_includes_inbox_summary(self, client: TestClient):
        client.post(f"{BASE}/affair/", json={"title": "待分拣事务"})
        resp = client.get(f"{BASE}/dashboard", params={"date": str(TEST_DATE)})
        assert resp.status_code == 200
        summaries = resp.json()["inbox_summary"]
        assert any(item["affair"]["title"] == "待分拣事务" for item in summaries)
