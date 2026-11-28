# -*- coding: utf-8 -*-
# @file test_router_mount.py
# @brief Regression test ensuring all core API routers are mounted in server.py
# @author sailing-innocent
# @date 2026-11-22
# @version 1.0
# ---------------------------------
"""确保 server.py 注册了全部核心业务路由（防止 health_router 等被误删导致线上 404）。"""

import os
import tempfile

from server import SailServer


def test_core_routers_mounted(monkeypatch):
    db_path = os.path.join(tempfile.gettempdir(), "sailzen_test_router_mount.db")
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", db_path)

    srv = SailServer("127.0.0.1", 0)
    srv.init()
    assert srv.app is not None

    mounted = {route.path for route in srv.app.routes}

    required_paths = [
        "/api/v1/health",
        "/api/v1/health/weight",
        "/api/v1/health/body-data",
        "/api/v1/health/dashboard",
        "/api/v1/finance/account",
        "/api/v1/finance/transaction",
        "/api/v1/rhythm/affair",
        "/api/v1/rhythm/dashboard",
        "/api/v1/reminder/pending",
        "/api/v1/tick/tickets",
        "/api/v1/workbench/bootstrap",
        "/api/v1/workbench/release/latest",
        "/api/v1/workbench/release/latest.vsix",
        "/api/v1/life/weather",
        "/api/v1/necessity/residence",
        "/api/v1/text/work",
        "/api/v1/text/import/create",
        "/api/v1/text/import/epub",
        "/api/v1/text/import/pdf",
        "/api/v1/text/import/arxiv",
        "/api/v1/text/progress/overview",
        "/api/v1/text/topic",
        "/api/v1/text/asset",
        "/api/v1/text/vault/index",
        "/api/v1/history/event",
        "/api/v1/blog/list",
        "/api/v1/file-storage/list",
        "/api/v1/app/release/latest",
        "/api/v1/app/release/latest.apk",
        "/api/v1/telemetry/ai-traces",
        "/api/v1/telemetry/ai-traces/stats",
        "/api/v1/telemetry/profile/api",
        "/api/v1/telemetry/profile/modules",
        "/api/v1/telemetry/profile/runtime",
        "/api/v1/telemetry/sailtick/live",
    ]
    missing = [p for p in required_paths if p not in mounted]
    assert not missing, f"核心路由未挂载到 server.py: {missing}"
