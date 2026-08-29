# -*- coding: utf-8 -*-
# @file test_rhythm_admin.py
# @brief Rhythm admin calibration API tests
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
测试 /api/v1/rhythm/admin/* 批量校准接口。
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


class TestAdminCalibration:
    def test_recalibrate_profile(self, client: TestClient):
        resp = client.post(
            f"{BASE}/admin/recalibrate-profile",
            json={"daily_energy_budget": 120, "life_weight": 1.2, "work_weight": 1.0, "career_weight": 0.8},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["daily_energy_budget"] == 120
        assert data["is_default"] is True

    def test_ensure_default_templates(self, client: TestClient):
        resp = client.post(f"{BASE}/admin/ensure-default-templates")
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] >= 0
        assert data["updated"] >= 0
        names = {t["name"] for t in data["templates"]}
        assert {"weekday", "weekend", "travel_day"}.issubset(names)

