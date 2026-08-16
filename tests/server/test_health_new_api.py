# -*- coding: utf-8 -*-
# @file test_health_new_api.py
# @brief Health 模块升级 API 测试（Medication / Diet / Sleep / Dashboard）
# @author sailing-innocent
# @date 2026-11-20
# @version 1.0
# ---------------------------------

"""
覆盖 M1 新增后端接口：
- Medication CRUD / today / stats
- Diet CRUD / summary / goal
- Sleep / SleepSchedule
- HealthDashboard
- health_checkin_impl 双写专用表
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient

from sail_server.controller.health import (
    WeightController,
    WeightPlanController,
    ExerciseController,
    SleepController,
    SleepScheduleController,
    MedicationController,
    DietController,
    HealthDashboardController,
)
from sail_server.controller.rhythm import CheckinController
from sail_server.infrastructure.orm.health import Medication, DietLog, Sleep, SleepScheduleGoal

pytestmark = pytest.mark.server


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """挂载 health 全部控制器的测试 App"""

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path="/api/v1/health",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[
            WeightController,
            WeightPlanController,
            ExerciseController,
            SleepController,
            SleepScheduleController,
            MedicationController,
            DietController,
            HealthDashboardController,
        ],
    )
    rhythm_router = Router(
        path="/api/v1/rhythm",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[CheckinController],
    )
    app = Litestar(route_handlers=[router, rhythm_router])
    with TestClient(app=app) as client:
        yield client


BASE = "/api/v1/health"


class TestMedicationApi:
    def test_create_and_take_medication(self, client: TestClient, db: Session):
        today = datetime.now().date().isoformat()
        resp = client.post(
            f"{BASE}/medication",
            json={
                "name": "维生素 D",
                "dosage": "500mg",
                "frequency": "daily",
                "schedule_times": ["08:00"],
                "planned_date": today,
                "taken": False,
                "is_supplement": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "维生素 D"
        med_id = data["id"]

        resp = client.put(
            f"{BASE}/medication/{med_id}",
            json={"taken": True},
        )
        assert resp.status_code == 200
        assert resp.json()["taken"] is True

        orm = db.query(Medication).filter(Medication.id == med_id).first()
        assert orm is not None
        assert orm.taken is True

    def test_medication_today_and_stats(self, client: TestClient):
        today = datetime.now().date().isoformat()
        for i in range(2):
            client.post(
                f"{BASE}/medication",
                json={
                    "name": f"药{i}",
                    "planned_date": today,
                    "taken": i == 0,
                },
            )
        resp = client.get(f"{BASE}/medication/today", params={"date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["taken"] == 1
        assert data["compliance"] == 0.5

        resp = client.get(f"{BASE}/medication/stats", params={"days": 7, "end_date": today})
        assert resp.status_code == 200
        assert resp.json()["compliance"] == 0.5


class TestDietApi:
    def test_create_diet_and_summary(self, client: TestClient, db: Session):
        today = datetime.now().date().isoformat()
        resp = client.post(
            f"{BASE}/diet",
            json={
                "meal_type": "lunch",
                "description": "鸡胸肉沙拉",
                "calories": 450,
                "carbs": 30,
                "sugar": 5,
                "protein": 35,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["meal_type"] == "lunch"
        diet_id = data["id"]

        orm = db.query(DietLog).filter(DietLog.id == diet_id).first()
        assert orm is not None
        assert orm.calories == 450

        # 创建营养目标
        client.post(
            f"{BASE}/diet/goal",
            json={"date": today, "calories": 2000, "sugar": 50},
        )
        resp = client.get(f"{BASE}/diet/summary", params={"date": today})
        assert resp.status_code == 200
        summary = resp.json()
        assert summary["calories"]["actual"] == 450
        assert summary["calories"]["goal"] == 2000
        assert summary["sugar"]["actual"] == 5


class TestSleepApi:
    def test_create_sleep_and_goal(self, client: TestClient, db: Session):
        today = datetime.now().date().isoformat()
        resp = client.post(
            f"{BASE}/sleep",
            json={"hours": 7.5, "quality": 4},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["hours"] == 7.5
        sleep_id = data["id"]
        orm = db.query(Sleep).filter(Sleep.id == sleep_id).first()
        assert orm is not None
        assert orm.hours == 450  # 内部存储分钟

        resp = client.post(
            f"{BASE}/sleep-schedule",
            json={"date": today, "bed_time": "23:00", "wake_time": "07:00", "target_hours": 8.0},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bed_time"] == "23:00"
        orm_goal = db.query(SleepScheduleGoal).filter(SleepScheduleGoal.date == datetime.now().date()).first()
        assert orm_goal is not None


class TestDashboardApi:
    def test_dashboard_returns_summary(self, client: TestClient):
        today = datetime.now().date().isoformat()
        # 创建体重、运动、饮食、用药记录，验证 dashboard 聚合
        client.post(f"{BASE}/weight", json={"value": 70.5})
        client.post(
            f"{BASE}/exercise",
            json={"exercise_type": "跑步", "duration_minutes": 30, "calories": 300},
        )
        client.post(f"{BASE}/diet", json={"meal_type": "lunch", "calories": 1800})
        client.post(f"{BASE}/medication", json={"name": "维 C", "planned_date": today, "taken": True})

        resp = client.get(f"{BASE}/dashboard", params={"date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight"]["latest"] == 70.5
        assert data["exercise"]["today_minutes"] == 30
        assert data["diet"]["calories_actual"] == 1800
        assert data["medication"]["taken"] == 1


class TestHealthCheckinDualWrite:
    def test_meal_checkin_creates_diet_log(self, client: TestClient, db: Session):
        today = datetime.now().date().isoformat()
        resp = client.post(
            "/api/v1/rhythm/checkin/health",
            json={
                "collection_type": "meal",
                "log_date": today,
                "payload": {
                    "meal_type": "dinner",
                    "description": "米饭+青菜",
                    "calories": 600,
                },
                "note": "",
            },
        )
        assert resp.status_code == 201
        assert db.query(DietLog).filter(DietLog.meal_type == "dinner").count() >= 1

    def test_medication_checkin_creates_medication(self, client: TestClient, db: Session):
        today = datetime.now().date().isoformat()
        resp = client.post(
            "/api/v1/rhythm/checkin/health",
            json={
                "collection_type": "medication",
                "log_date": today,
                "payload": {"name": "钙片", "dosage": "600mg", "planned_date": today},
                "note": "",
            },
        )
        assert resp.status_code == 201
        assert db.query(Medication).filter(Medication.name == "钙片").count() >= 1
