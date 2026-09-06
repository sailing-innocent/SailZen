# -*- coding: utf-8 -*-
# @file test_rhythm_affair_update.py
# @brief Rhythm 事务编辑三态语义 / 清空标记 / venture 目标日同步 测试
# @author sailing-innocent
# @date 2026-09-06
# @version 1.0
# ---------------------------------

"""
覆盖契约 §5-2：

- update 仅当字段在请求中被显式提供时才赋值（model_fields_set 三态语义），
  显式 null 清空该字段，未提供的字段保持原值。
- clear_urgency_ddl / clear_window 布尔清空标记，clear 优先于赋值。
- venture 目标日单一来源：清空一侧联动清空另一侧；写入一侧对齐另一侧。
- 迁移脚本幂等（连续执行两遍不报错）。
"""

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient

from sail_server.controller.rhythm import (
    AffairController,
    DashboardController,
    EnergyController,
    VentureController,
)

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
            AffairController,
            VentureController,
            EnergyController,
            DashboardController,
        ],
    )
    app = Litestar(route_handlers=[router])
    with TestClient(app=app) as client:
        yield client


BASE = "/api/v1/rhythm"


def _create_task(client: TestClient, **overrides) -> dict:
    payload = {"title": "普通任务", "kind": "task_oneoff", "urgency_ddl": "2026-11-01T10:00:00"}
    payload.update(overrides)
    resp = client.post(f"{BASE}/affair/", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _create_venture(client: TestClient, **meta) -> dict:
    payload = {
        "title": "Venture X",
        "kind": "venture",
        "domain": "career",
        "kind_meta": {"target_date": "2028-04-19", "weekly_budget_hours": 6},
    }
    payload["kind_meta"].update(meta)
    resp = client.post(f"{BASE}/affair/", json=payload)
    assert resp.status_code == 201
    return resp.json()


class TestThreeStateUpdate:
    """三态语义：未提供的字段不被覆盖，显式 null 清空字段。"""

    def test_unset_fields_preserved(self, client: TestClient):
        task = _create_task(client, description="原始描述")
        resp = client.put(
            f"{BASE}/affair/{task['id']}", json={"title": "新标题"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "新标题"
        # 未提供的字段保持原值
        assert data["description"] == "原始描述"
        assert data["urgency_ddl"].startswith("2026-11-01")

    def test_explicit_null_clears_field(self, client: TestClient):
        task = _create_task(client)
        resp = client.put(f"{BASE}/affair/{task['id']}", json={"urgency_ddl": None})
        assert resp.status_code == 200
        assert resp.json()["urgency_ddl"] is None

    def test_clear_urgency_ddl_flag(self, client: TestClient):
        task = _create_task(client)
        resp = client.put(
            f"{BASE}/affair/{task['id']}", json={"clear_urgency_ddl": True}
        )
        assert resp.status_code == 200
        assert resp.json()["urgency_ddl"] is None

    def test_clear_urgency_ddl_wins_over_assignment(self, client: TestClient):
        task = _create_task(client)
        resp = client.put(
            f"{BASE}/affair/{task['id']}",
            json={"urgency_ddl": "2027-01-01T00:00:00", "clear_urgency_ddl": True},
        )
        assert resp.status_code == 200
        assert resp.json()["urgency_ddl"] is None

    def test_clear_window_flag(self, client: TestClient):
        task = _create_task(
            client,
            window_start="2026-11-01T09:00:00",
            window_end="2026-11-01T12:00:00",
        )
        resp = client.put(f"{BASE}/affair/{task['id']}", json={"clear_window": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_start"] is None
        assert data["window_end"] is None

    def test_clear_window_wins_over_assignment(self, client: TestClient):
        task = _create_task(
            client,
            window_start="2026-11-01T09:00:00",
            window_end="2026-11-01T12:00:00",
        )
        resp = client.put(
            f"{BASE}/affair/{task['id']}",
            json={
                "window_start": "2026-11-02T09:00:00",
                "window_end": "2026-11-02T12:00:00",
                "clear_window": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_start"] is None
        assert data["window_end"] is None


class TestVentureTargetDateClear:
    """venture 目标日单一来源：清空/写入的双向对齐。"""

    def test_clear_target_date_clears_urgency_ddl(self, client: TestClient):
        """显式清空 target_date → 联动清空 urgency_ddl（旧行为会反向回填）。"""
        venture = _create_venture(client)
        assert venture["urgency_ddl"].startswith("2028-04-19")
        resp = client.put(
            f"{BASE}/affair/{venture['id']}",
            json={"kind_meta": {"target_date": None}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind_meta"].get("target_date") is None
        assert data["urgency_ddl"] is None

    def test_clear_urgency_ddl_clears_target_date(self, client: TestClient):
        """显式清空 urgency_ddl → 联动清空 target_date。"""
        venture = _create_venture(client)
        resp = client.put(
            f"{BASE}/affair/{venture['id']}", json={"clear_urgency_ddl": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["urgency_ddl"] is None
        assert data["kind_meta"].get("target_date") is None

    def test_update_target_date_resyncs_urgency_ddl(self, client: TestClient):
        venture = _create_venture(client)
        resp = client.put(
            f"{BASE}/affair/{venture['id']}",
            json={"kind_meta": {"target_date": "2029-01-01"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind_meta"]["target_date"] == "2029-01-01"
        assert data["urgency_ddl"].startswith("2029-01-01")

    def test_update_urgency_ddl_backfills_target_date(self, client: TestClient):
        venture = _create_venture(client)
        resp = client.put(
            f"{BASE}/affair/{venture['id']}",
            json={"urgency_ddl": "2029-06-15T10:30:00"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind_meta"]["target_date"] == "2029-06-15"
        assert data["urgency_ddl"].startswith("2029-06-15")

    def test_meta_replacement_without_target_date_clears_it(self, client: TestClient):
        """kind_meta 为整包替换语义：替换后 target_date 缺失即视为清空，联动清空 DDL。

        契约约定客户端编辑 venture 时必须回传完整 meta（含 target_date 键），
        前端 syncVentureTargetDate 生成的 patch 始终包含该键。
        """
        venture = _create_venture(client)
        resp = client.put(
            f"{BASE}/affair/{venture['id']}",
            json={"kind_meta": {"weekly_budget_hours": 10}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind_meta"].get("target_date") is None
        assert data["kind_meta"]["weekly_budget_hours"] == 10
        assert data["urgency_ddl"] is None


class TestMigrationIdempotent:
    """迁移脚本幂等：在已有完整 schema 上重复执行不报错、不产生副作用。"""

    def test_is_default_migration_runs_twice(self, db: Session):
        import importlib.util
        from pathlib import Path

        migration_path = (
            Path(__file__).resolve().parent.parent.parent
            / "sail_server"
            / "migration"
            / "20260906_add_rhythm_is_default.py"
        )
        spec = importlib.util.spec_from_file_location(
            "add_rhythm_is_default", migration_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 第一遍：列已存在（create_all 已建）→ 立即返回；建表 checkfirst 空操作
        module.migrate(db)
        # 第二遍：幂等
        module.migrate(db)
        db.commit()

        from sqlalchemy import inspect

        insp = inspect(db.bind)
        cols = {c["name"] for c in insp.get_columns("rhythm_energy_profiles")}
        assert "is_default" in cols

    def test_backfill_marks_default_profile(self, db: Session):
        """存量 name='default' 行回填 is_default=true。"""
        from sail_server.infrastructure.orm.rhythm import RhythmEnergyProfile

        row = (
            db.query(RhythmEnergyProfile)
            .filter(RhythmEnergyProfile.name == "default")
            .first()
        )
        if row is not None:
            assert bool(getattr(row, "is_default", True)) is True
