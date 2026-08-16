# -*- coding: utf-8 -*-
# @file test_health_api.py
# @brief Health API tests (Weight Plan refactoring)
# @author sailing-innocent
# @date 2026-11-15
# @version 1.0
# ---------------------------------

"""
Health 模块 API 测试：
- 体重计划 CRUD（曲线类型、Rhythm 提醒与反馈）
- 目标体重计算不再硬编码
- 预期体重范围切分
- Rhythm 联动（affair 创建/归档、打卡日志）
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient
from litestar.plugins.pydantic import PydanticPlugin

from sail_server.controller.health import WeightController, WeightPlanController, ExerciseController
from sail_server.infrastructure.orm.rhythm import RhythmAffair, RhythmDisciplineLog

pytestmark = pytest.mark.server


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """挂载 health 全部控制器的测试 App（db 依赖覆盖为内存 SQLite 会话）"""

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
        ],
    )
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as client:
        yield client


BASE = "/api/v1/health"


# ============================================================================
# Plan CRUD
# ============================================================================


class TestWeightPlanCrud:
    def test_create_plan_with_curve_and_rhythm(self, client: TestClient, db: Session):
        start = datetime.now() - timedelta(days=7)
        target = datetime.now() + timedelta(days=90)
        resp = client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "75",
                "curve_type": "polynomial",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
                "description": "测试计划",
                "notify_enabled": True,
                "notify_time": "07:30",
                "feedback_enabled": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["targetWeight"] == "70"
        assert data["initialWeight"] == "75"
        assert data["curveType"] == "polynomial"
        assert data["notifyEnabled"] is True
        assert data["notifyTime"] == "07:30"
        assert data["feedbackEnabled"] is True
        assert data["rhythmAffairId"] is not None

        # 验证 rhythm_affairs 中存在对应 PRECEPT
        affair = db.query(RhythmAffair).filter(RhythmAffair.id == data["rhythmAffairId"]).first()
        assert affair is not None
        assert affair.kind == "precept"
        assert affair.state == "ACTIVE"
        assert affair.info_collection_type == "weight"

    def test_update_plan_changes_target_weight(self, client: TestClient, db: Session):
        start = datetime.now() - timedelta(days=7)
        target = datetime.now() + timedelta(days=90)
        create = client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )
        assert create.status_code == 201
        plan_id = create.json()["id"]

        update = client.put(
            f"{BASE}/weight/plan/{plan_id}",
            json={"target_weight": "68", "curve_type": "exponential"},
        )
        assert update.status_code == 200
        data = update.json()
        assert data["targetWeight"] == "68"
        assert data["curveType"] == "exponential"

        # 验证 target_weight 返回值同步变化
        today = datetime.now().date().isoformat()
        resp = client.get(f"{BASE}/weight/target", params={"date": today})
        assert resp.status_code == 200
        assert resp.json()["value"] < 75.0  # 从 initial 75 向 target 68 下降

    def test_delete_plan_archives_rhythm_affair(self, client: TestClient, db: Session):
        start = datetime.now() - timedelta(days=7)
        target = datetime.now() + timedelta(days=90)
        create = client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
                "notify_enabled": True,
            },
        )
        assert create.status_code == 201
        plan_id = create.json()["id"]
        affair_id = create.json()["rhythmAffairId"]

        resp = client.delete(f"{BASE}/weight/plan/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        affair = db.query(RhythmAffair).filter(RhythmAffair.id == affair_id).first()
        assert affair is not None
        assert affair.state == "ARCHIVED"


# ============================================================================
# Target weight calculation
# ============================================================================


class TestTargetWeight:
    def test_target_weight_not_hardcoded(self, client: TestClient):
        # 无计划时应返回 200 但响应体为空/None
        today = datetime.now().date().isoformat()
        resp = client.get(f"{BASE}/weight/target", params={"date": today})
        assert resp.status_code == 200
        assert resp.json() is None

    def test_linear_curve_expected(self, client: TestClient):
        start = datetime.now() - timedelta(days=10)
        target = datetime.now() + timedelta(days=20)
        client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "80",
                "curve_type": "linear",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )
        today = datetime.now().date().isoformat()
        resp = client.get(f"{BASE}/weight/target", params={"date": today})
        assert resp.status_code == 200
        data = resp.json()
        assert data["value"] == pytest.approx(76.67, abs=0.1)
        assert data["tag"] == "target"
        assert data["curve_type"] == "linear"
        assert data["plan_id"] > 0

    def test_polynomial_curve_before_target(self, client: TestClient):
        start = datetime.now() - timedelta(days=10)
        target = datetime.now() + timedelta(days=20)
        client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "80",
                "curve_type": "polynomial",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )
        today = datetime.now().date().isoformat()
        resp = client.get(f"{BASE}/weight/target", params={"date": today})
        assert resp.status_code == 200
        data = resp.json()
        # polynomial ease-out 前期下降更快，应小于线性值
        assert data["value"] < 76.67

    def test_target_before_plan_start_returns_none(self, client: TestClient):
        start = datetime.now() + timedelta(days=10)
        target = datetime.now() + timedelta(days=40)
        client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "80",
                "curve_type": "linear",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )
        today = datetime.now().date().isoformat()
        resp = client.get(f"{BASE}/weight/target", params={"date": today})
        assert resp.status_code == 200
        assert resp.json() is None


# ============================================================================
# Expected range slicing
# ============================================================================


class TestExpectedRange:
    def test_range_before_and_after_plan(self, client: TestClient):
        start = datetime.now()
        target = datetime.now() + timedelta(days=10)
        client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "80",
                "curve_type": "linear",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )

        range_start = datetime.now() - timedelta(days=3)
        range_end = datetime.now() + timedelta(days=13)
        resp = client.get(
            f"{BASE}/weight/plan/expected",
            params={
                "start": range_start.timestamp(),
                "end": range_end.timestamp(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        points = data["points"]
        assert len(points) == 17  # -3..13 inclusive
        # 计划前使用 initial_weight
        assert points[0]["expected_weight"] == pytest.approx(80.0, abs=0.01)
        # 计划后使用 target_weight
        assert points[-1]["expected_weight"] == pytest.approx(70.0, abs=0.01)


# ============================================================================
# Weights with status
# ============================================================================


class TestWeightsWithStatus:
    def test_weights_with_status_against_active_plan(self, client: TestClient):
        start = datetime.now() - timedelta(days=5)
        target = datetime.now() + timedelta(days=10)
        client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "80",
                "curve_type": "linear",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
            },
        )

        # 插入一条位于计划期内的体重记录
        resp = client.post(
            f"{BASE}/weight/",
            json={"value": 78.0, "htime": datetime.now().timestamp()},
        )
        assert resp.status_code == 201

        range_start = datetime.now() - timedelta(days=7)
        range_end = datetime.now() + timedelta(days=7)
        resp = client.get(
            f"{BASE}/weight/plan/weights-with-status",
            params={
                "start": range_start.timestamp(),
                "end": range_end.timestamp(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["value"] == pytest.approx(78.0, abs=0.01)
        assert "status" in data[0]
        assert "expected_value" in data[0]
        assert "diff" in data[0]


# ============================================================================
# Rhythm feedback
# ============================================================================


class TestRhythmFeedback:
    def test_checkin_status_after_weight_record(self, client: TestClient, db: Session):
        start = datetime.now() - timedelta(days=7)
        target = datetime.now() + timedelta(days=90)
        create = client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "75",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
                "feedback_enabled": True,
            },
        )
        assert create.status_code == 201
        plan_id = create.json()["id"]

        # 创建体重记录前：未打卡
        resp = client.get(f"{BASE}/weight/plan/checkin-status", params={"plan_id": plan_id})
        assert resp.status_code == 200
        assert resp.json()["today_done"] is False
        assert resp.json()["streak"] == 0

        # 创建体重记录
        resp = client.post(
            f"{BASE}/weight/",
            json={"value": 74.5, "htime": datetime.now().timestamp()},
        )
        assert resp.status_code == 201

        # 创建体重记录后：今日已打卡
        resp = client.get(f"{BASE}/weight/plan/checkin-status", params={"plan_id": plan_id})
        assert resp.status_code == 200
        assert resp.json()["today_done"] is True
        assert resp.json()["streak"] == 1

    def test_feedback_enabled_creates_checkin_log(self, client: TestClient, db: Session):
        start = datetime.now() - timedelta(days=7)
        target = datetime.now() + timedelta(days=90)
        create = client.post(
            f"{BASE}/weight/plan/",
            json={
                "target_weight": "70",
                "initial_weight": "75",
                "start_time": start.isoformat(),
                "target_time": target.isoformat(),
                "feedback_enabled": True,
            },
        )
        assert create.status_code == 201
        affair_id = create.json()["rhythmAffairId"]

        # 创建体重记录
        resp = client.post(
            f"{BASE}/weight/",
            json={"value": 74.5, "htime": datetime.now().timestamp()},
        )
        assert resp.status_code == 201

        # 验证 rhythm_discipline_logs 中存在 DONE 记录
        log = (
            db.query(RhythmDisciplineLog)
            .filter(RhythmDisciplineLog.affair_id == affair_id)
            .first()
        )
        assert log is not None
        assert log.result == "done"
        assert log.source == "weight_plan"
