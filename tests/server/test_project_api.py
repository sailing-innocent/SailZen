# -*- coding: utf-8 -*-
# @file test_project_api.py
# @brief Project/Mission API 测试
# @author sailing-innocent
# @date 2026-03-02
# @version 1.0
# ---------------------------------

"""
项目/任务模块 API 测试：
- Project CRUD
- Mission CRUD + 状态流转
- upcoming/overdue 查询
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient
from litestar.plugins.pydantic import PydanticPlugin

from sail_server.router.project import router as project_router

pytestmark = pytest.mark.server


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path="/api/v1",
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[project_router],
    )
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as client:
        yield client


BASE = "/api/v1/project"


class TestProjectCrud:
    def test_create_and_get_project(self, client: TestClient):
        resp = client.post(
            f"{BASE}/project/",
            json={"name": "测试项目", "description": "描述", "start_time_qbw": 20260101, "end_time_qbw": 20260199},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试项目"

        project_id = data["id"]
        resp = client.get(f"{BASE}/project/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    def test_list_projects(self, client: TestClient):
        client.post(f"{BASE}/project/", json={"name": "项目 A", "start_time_qbw": 20260101, "end_time_qbw": 20260199})
        client.post(f"{BASE}/project/", json={"name": "项目 B", "start_time_qbw": 20260101, "end_time_qbw": 20260199})
        resp = client.get(f"{BASE}/project/")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2


class TestMissionCrud:
    def test_create_mission_with_timestamp_ddl(self, client: TestClient):
        project = client.post(f"{BASE}/project/", json={"name": "DDL 测试项目", "start_time_qbw": 20260101, "end_time_qbw": 20260199}).json()
        ddl = (datetime.now() + timedelta(days=1)).timestamp()
        resp = client.post(
            f"{BASE}/mission/",
            json={"name": "DDL 任务", "project_id": project["id"], "ddl": ddl},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == project["id"]

    def test_mission_state_transitions(self, client: TestClient):
        project = client.post(f"{BASE}/project/", json={"name": "状态测试项目", "start_time_qbw": 20260101, "end_time_qbw": 20260199}).json()
        mission = client.post(
            f"{BASE}/mission/",
            json={"name": "状态任务", "project_id": project["id"]},
        ).json()
        assert mission["state"] == 0

        resp = client.post(f"{BASE}/mission/{mission['id']}/doing")
        assert resp.status_code == 200
        assert resp.json()["state"] == 2

        resp = client.post(f"{BASE}/mission/{mission['id']}/done")
        assert resp.status_code == 200
        assert resp.json()["state"] == 3

        resp = client.post(f"{BASE}/mission/{mission['id']}/postpone", params={"days": 3})
        assert resp.status_code == 200


class TestMissionReminderQueries:
    def test_upcoming_and_overdue_missions(self, client: TestClient):
        project = client.post(f"{BASE}/project/", json={"name": "提醒测试项目", "start_time_qbw": 20260101, "end_time_qbw": 20260199}).json()

        # 逾期任务
        overdue = client.post(
            f"{BASE}/mission/",
            json={
                "name": "逾期任务",
                "project_id": project["id"],
                "ddl": (datetime.now() - timedelta(hours=1)).timestamp(),
            },
        ).json()

        # 未来任务
        upcoming = client.post(
            f"{BASE}/mission/",
            json={
                "name": "即将到期",
                "project_id": project["id"],
                "ddl": (datetime.now() + timedelta(hours=2)).timestamp(),
            },
        ).json()

        # 已完成不应出现在逾期列表
        done = client.post(
            f"{BASE}/mission/",
            json={
                "name": "已完成任务",
                "project_id": project["id"],
                "ddl": (datetime.now() - timedelta(hours=2)).timestamp(),
            },
        ).json()
        client.post(f"{BASE}/mission/{done['id']}/done")

        overdue_list = client.get(f"{BASE}/mission/overdue").json()
        assert any(m["id"] == overdue["id"] for m in overdue_list)
        assert not any(m["id"] == done["id"] for m in overdue_list)

        upcoming_list = client.get(f"{BASE}/mission/upcoming", params={"hours": 24}).json()
        assert any(m["id"] == upcoming["id"] for m in upcoming_list)
