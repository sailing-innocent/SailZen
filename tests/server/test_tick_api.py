# -*- coding: utf-8 -*-
# @file test_tick_api.py
# @brief SailTick 票据 API 集成测试（SQLite 内存库）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据路由集成测试。

覆盖设计文档 sailtick.md §6.3 验收:
- 全端点 curl 通过（GET/POST 列表、创建、回复、关闭、暂缓、增量拉取、超期处理）
- 状态机正确流转 + 幂等
- 高优先票据触发推送联动（mock push manager）
- 主库迁移幂等（重复建表不报错）
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from litestar import Litestar, Router
from litestar.di import Provide
from litestar.plugins.pydantic import PydanticPlugin
from litestar.testing import TestClient
from sqlalchemy.orm import Session

from sail_server.controller.tick import TicketController

pytestmark = pytest.mark.server

BASE = "/api/v1/tick"


@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    """挂载 ticket 控制器的测试 App（db 依赖覆盖为内存 SQLite 会话）。"""

    async def _test_db_dep():
        def _gen():
            yield db

        return _gen()

    router = Router(
        path=BASE,
        dependencies={"router_dependency": Provide(_test_db_dep)},
        route_handlers=[TicketController],
    )
    app = Litestar(route_handlers=[router], plugins=[PydanticPlugin(prefer_alias=True)])
    with TestClient(app=app) as client:
        yield client


def _create(client: TestClient, **kw) -> dict:
    payload = {
        "tick_id": "t1",
        "type": "question",
        "title": "现在的体重是多少？",
        "body": "为什么问这个：建立基线",
        "priority": "normal",
        "channel": "web",
        "expected_reply_by": (datetime.now() + timedelta(hours=48)).isoformat(),
        "fallback_assumption": "维持上次记录",
    }
    payload.update(kw)
    resp = client.post(f"{BASE}/tickets", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestTicketCRUD:
    def test_create_and_get(self, client: TestClient):
        t = _create(client)
        assert t["status"] == "pending"
        assert t["type"] == "question"
        assert t["expected_reply_by"] is not None

        got = client.get(f"{BASE}/tickets/{t['id']}")
        assert got.status_code == 200
        assert got.json()["title"] == t["title"]

    def test_create_invalid_type(self, client: TestClient):
        resp = client.post(
            f"{BASE}/tickets",
            json={"type": "bogus", "title": "x", "priority": "normal"},
        )
        assert resp.status_code == 400

    def test_list_with_status_filter(self, client: TestClient):
        _create(client, title="票A")
        _create(client, title="票B")
        resp = client.get(f"{BASE}/tickets", params={"status": "pending"})
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2

        resp2 = client.get(f"{BASE}/tickets", params={"status": "resolved"})
        assert resp2.json() == []

    def test_list_sorted_by_expected_reply(self, client: TestClient):
        later = (datetime.now() + timedelta(hours=72)).isoformat()
        sooner = (datetime.now() + timedelta(hours=12)).isoformat()
        _create(client, title="晚", expected_reply_by=later)
        _create(client, title="早", expected_reply_by=sooner)
        items = client.get(f"{BASE}/tickets").json()
        assert items[0]["title"] == "早"
        assert items[1]["title"] == "晚"

    def test_get_404(self, client: TestClient):
        resp = client.get(f"{BASE}/tickets/9999")
        assert resp.status_code == 404


class TestTicketStateMachine:
    def test_reply_resolve_flow(self, client: TestClient):
        t = _create(client)
        tid = t["id"]

        r = client.post(f"{BASE}/tickets/{tid}/reply", json={"reply": "72.5"})
        assert r.status_code == 201
        assert r.json()["status"] == "replied"
        assert r.json()["reply"] == "72.5"

        r2 = client.post(f"{BASE}/tickets/{tid}/resolve", json={"resolution": "已记录"})
        assert r2.status_code == 201
        assert r2.json()["status"] == "resolved"

    def test_reply_on_resolved_is_idempotent(self, client: TestClient):
        t = _create(client)
        tid = t["id"]
        client.post(f"{BASE}/tickets/{tid}/reply", json={"reply": "x"})
        client.post(f"{BASE}/tickets/{tid}/resolve", json={"resolution": "done"})

        r = client.post(f"{BASE}/tickets/{tid}/reply", json={"reply": "y"})
        # 终态幂等返回，不报 409
        assert r.status_code == 201
        assert r.json()["reply"] == "x"

    def test_snooze_extends_expected(self, client: TestClient):
        t = _create(client, expected_reply_by=(datetime.now() + timedelta(hours=24)).isoformat())
        tid = t["id"]
        before = datetime.fromisoformat(t["expected_reply_by"])

        r = client.post(f"{BASE}/tickets/{tid}/snooze", json={"hours": 24})
        assert r.status_code == 201
        assert r.json()["status"] == "snoozed"
        after = datetime.fromisoformat(r.json()["expected_reply_by"])
        assert (after - before) >= timedelta(hours=23)


class TestExpireAndSync:
    def test_expire_overdue(self, client: TestClient, db: Session):
        # 一张已超期（expected 在过去），一张未超期
        t1 = _create(client, title="超期票")
        t2 = _create(client, title="未超期票")
        # 直接改库把 t1 的 expected 拨到过去
        from sailzen_orm.tick import SailTickTicket

        row = db.get(SailTickTicket, t1["id"])
        row.expected_reply_by = datetime.now() - timedelta(hours=1)
        db.commit()

        r = client.post(f"{BASE}/expire-overdue")
        assert r.status_code == 201
        assert r.json() == {"expired": 1}

        items = client.get(f"{BASE}/tickets", params={"status": "expired"}).json()
        assert [i["id"] for i in items] == [t1["id"]]
        # 幂等：再来一次不重复处理
        r2 = client.post(f"{BASE}/expire-overdue")
        assert r2.json() == {"expired": 0}

    def test_replies_since(self, client: TestClient):
        t = _create(client)
        client.post(f"{BASE}/tickets/{t['id']}/reply", json={"reply": "ok"})

        r = client.get(f"{BASE}/replies")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["reply"] == "ok"

        # since 过滤：未来时刻 → 空
        future = (datetime.now() + timedelta(days=1)).isoformat()
        r2 = client.get(f"{BASE}/replies", params={"since": future})
        assert r2.json() == []


class TestPushLinkage:
    def test_high_priority_triggers_broadcast(self, client: TestClient, db: Session, monkeypatch):
        from sail_server.utils import reminder_ws

        calls = []

        class FakeManager:
            def __init__(self):
                self.broadcast_reminder = lambda payload: calls.append(payload)

        monkeypatch.setattr(reminder_ws, "_push_manager", FakeManager())

        _create(client, priority="high", title="urgent question")
        assert len(calls) == 1
        assert calls[0]["title"] == "urgent question"
        assert calls[0]["payload"]["ticket_type"] == "question"

        # normal 优先不推
        _create(client, priority="normal", title="normal info")
        assert len(calls) == 1

    def test_push_force_on_low(self, client: TestClient, db: Session, monkeypatch):
        from sail_server.utils import reminder_ws

        calls = []

        class FakeManager:
            def __init__(self):
                self.broadcast_reminder = lambda payload: calls.append(payload)

        monkeypatch.setattr(reminder_ws, "_push_manager", FakeManager())
        _create(client, priority="low", push="force", title="forced")
        assert len(calls) == 1

    def test_push_none_on_high(self, client: TestClient, db: Session, monkeypatch):
        from sail_server.utils import reminder_ws

        calls = []

        class FakeManager:
            def __init__(self):
                self.broadcast_reminder = lambda payload: calls.append(payload)

        monkeypatch.setattr(reminder_ws, "_push_manager", FakeManager())
        _create(client, priority="high", push="none", title="silent high")
        assert len(calls) == 0


class TestMigrationIdempotent:
    def test_create_all_twice(self, db: Session):
        """重复建表（重启场景）不报错。"""
        from sailzen_orm.orm_base import ORMBase

        engine = db.bind
        ORMBase.metadata.create_all(bind=engine)
        ORMBase.metadata.create_all(bind=engine)
        from sqlalchemy import inspect

        assert "sail_tick_tickets" in set(inspect(engine).get_table_names())
