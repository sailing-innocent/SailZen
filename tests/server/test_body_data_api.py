# -*- coding: utf-8 -*-
# @file test_body_data_api.py
# @brief Body Data API tests
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
身体数据模块 API 测试：
- CRUD（创建/读取/列表/更新/删除）
- 校验：data 为空 / 非法 key / 超范围 value / 非数值 value → 422
- 未测量语义：部分指标记录的 series 仅含已测点
- metrics 端点：内置注册表 + x_ 自定义指标动态发现（builtin=false）
- weight dual-write：创建回填 weightId、更新联动、删除级联
- backfill 迁移幂等：重复执行 0 新增
- analysis 端点：任意指标 trend 返回结构正确
"""
from datetime import datetime, timedelta

import pytest
from litestar import Litestar, Router
from litestar.di import Provide
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient
from sqlalchemy.orm import Session

from sail_server.controller.body_data import BodyDataController
from sail_server.infrastructure.orm.health import BodyData, Weight

pytestmark = pytest.mark.server

BASE = "/api/v1/health/body-data"


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """挂载 BodyDataController 的测试 App（db 依赖覆盖为内存 SQLite 会话）"""

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path="/api/v1/health",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[BodyDataController],
    )
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as c:
        yield c


def _ts(days_ago: float) -> float:
    """N 天前的时间戳（秒）"""
    return (datetime.now() - timedelta(days=days_ago)).timestamp()


# ============================================================================
# CRUD
# ============================================================================


class TestBodyDataCrud:
    def test_create_and_get(self, client: TestClient, db: Session):
        resp = client.post(
            f"{BASE}/",
            json={"htime": _ts(1), "data": {"weight": 70.5, "waist": 82.0}, "description": "晨练后"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] > 0
        assert data["data"] == {"weight": 70.5, "waist": 82.0}
        assert data["description"] == "晨练后"
        assert data["source"] == "manual"
        assert "chest" not in data["data"]  # 未测量 key 不出现在 payload

        # GET single
        rid = data["id"]
        resp2 = client.get(f"{BASE}/{rid}")
        assert resp2.status_code == 200
        assert resp2.json()["data"]["weight"] == 70.5

    def test_create_without_htime_uses_now(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"water": 1500}})
        assert resp.status_code == 201
        assert resp.json()["htime"] > 0

    def test_list_with_time_range_and_pagination(self, client: TestClient, db: Session):
        for i in range(5):
            client.post(f"{BASE}/", json={"htime": _ts(i), "data": {"water": 1000 + i}})
        resp = client.get(f"{BASE}/?skip=1&limit=2&start={_ts(4.5)}&end={_ts(0.5)}")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2
        # 按时间升序：skip=1 后应为第 2/3 条（水 1003 / 1002）
        assert [r["data"]["water"] for r in items] == [1003.0, 1002.0]

    def test_update_replaces_data(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"weight": 70.0, "waist": 80.0}}).json()["id"]
        resp = client.put(f"{BASE}/{rid}", json={"data": {"weight": 69.5}, "description": "改"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] == {"weight": 69.5}
        assert "waist" not in data["data"]
        assert data["description"] == "改"

    def test_update_not_found_returns_none(self, client: TestClient, db: Session):
        resp = client.put(f"{BASE}/9999", json={"description": "x"})
        assert resp.status_code == 200
        assert resp.json() is None

    def test_delete(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"water": 500}}).json()["id"]
        resp = client.delete(f"{BASE}/{rid}")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True, "id": rid}
        assert db.query(BodyData).filter(BodyData.id == rid).first() is None


# ============================================================================
# Validation → 422
# ============================================================================


class TestBodyDataValidation:
    def test_empty_data_rejected(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {}})
        assert resp.status_code == 422

    def test_unknown_key_rejected_with_allowed_keys(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"weigth": 70}})  # 拼写错误
        assert resp.status_code == 422
        detail = str(resp.json())
        assert "weight" in detail  # 合法 key 列表包含在内

    def test_out_of_range_value_rejected(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"weight": 9999}})
        assert resp.status_code == 422

    def test_non_finite_value_rejected(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"weight": "abc"}})
        assert resp.status_code == 422

    def test_custom_x_key_accepted(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"x_uric_acid": 420}})
        assert resp.status_code == 201

    def test_update_validation(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"water": 500}}).json()["id"]
        resp = client.put(f"{BASE}/{rid}", json={"data": {}})
        assert resp.status_code == 422


# ============================================================================
# 未测量语义 & series
# ============================================================================


class TestBodyDataSeries:
    def test_series_only_contains_measured_points(self, client: TestClient, db: Session):
        # 第 1 天：weight + waist；第 2 天：仅 waist；第 3 天：weight
        client.post(f"{BASE}/", json={"htime": _ts(3), "data": {"weight": 71.0, "waist": 83.0}})
        client.post(f"{BASE}/", json={"htime": _ts(2), "data": {"waist": 82.5}})
        client.post(f"{BASE}/", json={"htime": _ts(1), "data": {"weight": 70.0}})

        resp = client.get(f"{BASE}/series?metric=weight")
        assert resp.status_code == 200
        series = resp.json()
        assert series["metric"] == "weight"
        assert series["unit"] == "kg"
        assert len(series["points"]) == 2  # 缺测日不生成点

        resp2 = client.get(f"{BASE}/series?metric=waist")
        assert len(resp2.json()["points"]) == 2

    def test_list_metric_filter(self, client: TestClient, db: Session):
        client.post(f"{BASE}/", json={"data": {"weight": 70.0, "waist": 80.0}})
        client.post(f"{BASE}/", json={"data": {"waist": 81.0}})
        resp = client.get(f"{BASE}/?metric=weight")
        items = resp.json()
        assert len(items) == 1
        assert "weight" in items[0]["data"]


# ============================================================================
# Metrics registry
# ============================================================================


class TestBodyDataMetrics:
    def test_builtin_registry_returned(self, client: TestClient, db: Session):
        resp = client.get(f"{BASE}/metrics")
        assert resp.status_code == 200
        metrics = resp.json()
        keys = [m["key"] for m in metrics]
        for expected in ("weight", "height", "chest", "waist", "hip", "body_fat_pct",
                         "muscle_mass", "protein_powder", "creatine", "water", "caffeine"):
            assert expected in keys
        weight_def = next(m for m in metrics if m["key"] == "weight")
        assert weight_def["builtin"] is True
        assert weight_def["unit"] == "kg"
        assert weight_def["labelZh"] == "体重"
        assert weight_def["higherIsBetter"] is False

    def test_custom_metric_discovered(self, client: TestClient, db: Session):
        client.post(f"{BASE}/", json={"data": {"x_uric_acid": 420}})
        resp = client.get(f"{BASE}/metrics")
        metrics = resp.json()
        custom = next((m for m in metrics if m["key"] == "x_uric_acid"), None)
        assert custom is not None
        assert custom["builtin"] is False


# ============================================================================
# Weight dual-write
# ============================================================================


class TestBodyDataWeightDualWrite:
    def test_create_with_weight_dual_writes(self, client: TestClient, db: Session):
        resp = client.post(
            f"{BASE}/",
            json={"htime": _ts(1), "data": {"weight": 70.5, "water": 1500}, "description": "d"},
        )
        assert resp.status_code == 201
        data = resp.json()
        weight_id = data.get("weightId")
        assert weight_id is not None

        weight = db.query(Weight).filter(Weight.id == weight_id).first()
        assert weight is not None
        assert float(weight.value) == 70.5
        assert weight.description == "d"

    def test_create_without_weight_no_dual_write(self, client: TestClient, db: Session):
        resp = client.post(f"{BASE}/", json={"data": {"water": 1500}})
        assert resp.json()["weightId"] is None
        assert db.query(Weight).count() == 0

    def test_update_weight_value_syncs_weight_row(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"weight": 70.0}}).json()["id"]
        weight_id = db.query(BodyData).filter(BodyData.id == rid).first().weight_id
        resp = client.put(f"{BASE}/{rid}", json={"data": {"weight": 68.5}})
        assert resp.status_code == 200
        weight = db.query(Weight).filter(Weight.id == weight_id).first()
        assert float(weight.value) == 68.5

    def test_update_adding_weight_creates_weight_row(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"water": 1000}}).json()["id"]
        resp = client.put(f"{BASE}/{rid}", json={"data": {"weight": 72.0, "water": 1000}})
        weight_id = resp.json()["weightId"]
        assert weight_id is not None
        assert db.query(Weight).filter(Weight.id == weight_id).count() == 1

    def test_update_removing_weight_deletes_weight_row(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"weight": 70.0, "water": 1000}}).json()["id"]
        weight_id = db.query(BodyData).filter(BodyData.id == rid).first().weight_id
        resp = client.put(f"{BASE}/{rid}", json={"data": {"water": 1000}})
        assert resp.json()["weightId"] is None
        assert db.query(Weight).filter(Weight.id == weight_id).first() is None

    def test_delete_cascades_to_weight_row(self, client: TestClient, db: Session):
        rid = client.post(f"{BASE}/", json={"data": {"weight": 70.0}}).json()["id"]
        weight_id = db.query(BodyData).filter(BodyData.id == rid).first().weight_id
        client.delete(f"{BASE}/{rid}")
        assert db.query(Weight).filter(Weight.id == weight_id).first() is None


# ============================================================================
# Backfill 迁移幂等
# ============================================================================


class TestBodyDataBackfill:
    def test_backfill_idempotent(self, client: TestClient, db: Session):
        from sail_server.migration import _run_python_migration
        from pathlib import Path

        migration = Path("sail_server/migration/20260906_backfill_body_data.py")

        # 预置旧 weights 数据
        for i in range(3):
            db.add(Weight(value=str(70.0 + i), htime=datetime.now() - timedelta(days=i), tag="raw"))
        db.commit()

        _run_python_migration(db, migration)
        count1 = db.query(BodyData).filter(BodyData.source == "weight_backfill").count()
        assert count1 == 3
        # 全部关联回填
        assert db.query(BodyData).filter(BodyData.weight_id.isnot(None)).count() == 3

        # 第二次执行 0 新增
        _run_python_migration(db, migration)
        count2 = db.query(BodyData).filter(BodyData.source == "weight_backfill").count()
        assert count2 == 3

    def test_backfilled_weight_visible_in_series(self, client: TestClient, db: Session):
        from sail_server.migration import _run_python_migration
        from pathlib import Path

        migration = Path("sail_server/migration/20260906_backfill_body_data.py")
        db.add(Weight(value="70.5", htime=datetime.now() - timedelta(days=1), tag="raw"))
        db.commit()
        _run_python_migration(db, migration)

        resp = client.get(f"{BASE}/series?metric=weight")
        points = resp.json()["points"]
        assert len(points) == 1
        assert points[0]["value"] == 70.5


# ============================================================================
# Analysis（泛化回归）
# ============================================================================


class TestBodyDataAnalysis:
    def test_analysis_structure_for_any_metric(self, client: TestClient, db: Session):
        for i in range(4):
            client.post(f"{BASE}/", json={"htime": _ts(4 - i), "data": {"waist": 82.0 - i * 0.2}})
        resp = client.get(f"{BASE}/analysis?metric=waist&model_type=linear")
        assert resp.status_code == 200
        result = resp.json()
        assert result["metric"] == "waist"
        assert result["unit"] == "cm"
        assert result["current_trend"] == "decreasing"
        assert len(result["predicted_points"]) == 4 + 30  # actual + 30 天预测
        assert result["current_value"] == pytest.approx(81.4)

    def test_analysis_insufficient_data(self, client: TestClient, db: Session):
        client.post(f"{BASE}/", json={"data": {"creatine": 5}})
        resp = client.get(f"{BASE}/analysis?metric=creatine")
        result = resp.json()
        assert result["current_trend"] == "stable"
        assert result["predicted_points"] == []
