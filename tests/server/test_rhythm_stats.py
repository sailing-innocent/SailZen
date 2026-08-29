# -*- coding: utf-8 -*-
# @file test_rhythm_stats.py
# @brief Rhythm stats API tests (heatmap / domain trend / venture burndown)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
测试统计增强接口。
"""

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient

from sail_server.controller.rhythm import (
    AffairController,
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

from .conftest import TEST_DATE

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


class TestStats:
    def test_habit_heatmap(self, client: TestClient):
        create = client.post(
            f"{BASE}/affair/",
            json={"title": "每周运动3次", "kind": "habit", "kind_meta": {
                "freq_per_week": 3, "min_session_minutes": 30
            }},
        )
        affair_id = create.json()["id"]
        client.post(
            f"{BASE}/checkin/",
            json={"affair_id": affair_id, "result": "done", "log_date": str(TEST_DATE)},
        )

        resp = client.get(
            f"{BASE}/checkin/heatmap",
            params={"affair_id": affair_id, "start_date": str(TEST_DATE), "end_date": str(TEST_DATE)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["affair_id"] == affair_id
        assert len(data["days"]) == 1
        assert data["days"][0]["done"] is True

    def test_domain_trend(self, client: TestClient):
        client.post(f"{BASE}/template/", json={"name": "weekday", "slots": []})
        client.post(f"{BASE}/plan/day", json={"date": str(TEST_DATE)})

        resp = client.get(
            f"{BASE}/review/domain-trend",
            params={"start_date": str(TEST_DATE), "end_date": str(TEST_DATE)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["days"]) == 1
        assert "life" in data["days"][0]
        assert "work" in data["days"][0]
        assert "career" in data["days"][0]

    def test_venture_burndown(self, client: TestClient):
        create = client.post(
            f"{BASE}/affair/",
            json={
                "title": "写书",
                "kind": "venture",
                "kind_meta": {"target_date": str(TEST_DATE), "weekly_budget_hours": 6, "total_est_hours": 20},
            },
        )
        venture_id = create.json()["id"]
        resp = client.get(f"{BASE}/venture/{venture_id}/burndown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["affair_id"] == venture_id
        assert "weeks" in data
        assert "planned" in data
        assert "actual" in data
