# -*- coding: utf-8 -*-
# @file test_finance_account_archive.py
# @brief 账户归档/封存与解封（PUT /api/v1/finance/account/{id}）模型层与接口测试
# @author sailing-innocent
# @date 2026-11-28
# @version 1.0
# ---------------------------------

from __future__ import annotations

import pytest
from litestar import Litestar, Router
from litestar.di import Provide
from litestar.testing import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from sailzen_orm import ORMBase
from sail_server.application.dto.finance import AccountData, AccountUpdateRequest
from sail_server.controller.finance import AccountController
from sail_server.model.finance.account import (
    create_account_impl,
    read_accounts_impl,
    update_account_impl,
)
from sail_server.model.finance.hygiene import get_finance_overview_impl


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ORMBase.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_update_account_archive_unarchive_and_validation(db_session):
    """支持将账户封存(0->1)与解封(1->0)，非法 state 返回 ValueError，不存在账户返回 None。"""
    acc = create_account_impl(
        db_session,
        AccountData(name="测试银行卡", description="工资卡", balance="1200.00", state=0),
    )
    assert acc.state == 0

    # 1. 封存账户 (0 -> 1)
    archived = update_account_impl(db_session, acc.id, AccountUpdateRequest(state=1))
    assert archived is not None
    assert archived.state == 1
    assert archived.name == "测试银行卡"

    # 列表查询仍返回全部账户（含已封存），但概览 account_health 仅包含活跃账户
    all_accounts = read_accounts_impl(db_session, skip=0, limit=-1)
    assert len(all_accounts) == 1
    assert all_accounts[0].state == 1

    ov_archived = get_finance_overview_impl(db_session)
    assert all(a["id"] != acc.id for a in ov_archived["account_health"])

    # 2. 解封账户 (1 -> 0) 并修改描述
    unarchived = update_account_impl(
        db_session,
        acc.id,
        AccountUpdateRequest(state=0, description="恢复使用"),
    )
    assert unarchived is not None
    assert unarchived.state == 0
    assert unarchived.description == "恢复使用"

    ov_active = get_finance_overview_impl(db_session)
    assert any(a["id"] == acc.id for a in ov_active["account_health"])

    # 3. 非法 state / 空名称校验
    with pytest.raises(ValueError):
        update_account_impl(db_session, acc.id, AccountUpdateRequest(state=2))
    with pytest.raises(ValueError):
        update_account_impl(db_session, acc.id, AccountUpdateRequest(name="   "))

    # 4. 不存在的账户返回 None
    assert update_account_impl(db_session, 999999, AccountUpdateRequest(state=1)) is None


def test_put_account_http_endpoint(db_session):
    """验证 PUT /api/v1/finance/account/{id} HTTP 接口的封存、解封、400 与 404 行为。"""
    acc = create_account_impl(
        db_session,
        AccountData(name="旧饭卡", description="", balance="0.51", state=1),
    )

    async def _override_db():
        def _gen():
            yield db_session

        return _gen()

    finance_router = Router(
        path="/api/v1/finance",
        dependencies={"router_dependency": Provide(_override_db)},
        route_handlers=[AccountController],
    )
    app = Litestar(route_handlers=[finance_router])

    with TestClient(app=app) as client:
        # 解封 1 -> 0
        resp = client.put(f"/api/v1/finance/account/{acc.id}", json={"state": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == acc.id
        assert body["state"] == 0

        # 再次封存 0 -> 1
        resp2 = client.put(f"/api/v1/finance/account/{acc.id}", json={"state": 1})
        assert resp2.status_code == 200
        assert resp2.json()["state"] == 1

        # 非法状态 -> 400
        resp_bad = client.put(f"/api/v1/finance/account/{acc.id}", json={"state": 9})
        assert resp_bad.status_code == 400

        # 不存在账户 -> 404
        resp_404 = client.put("/api/v1/finance/account/999999", json={"state": 0})
        assert resp_404.status_code == 404
