# -*- coding: utf-8 -*-
# @file test_inbox_datascan.py
# @brief inbox 客户端（httpx MockTransport）+ datascan 截断测试
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
from datetime import datetime

import httpx
import pytest

from sailtick.datascan import DataScanner
from sailtick.inbox import TicketInbox


def make_inbox(handler) -> TicketInbox:
    """用 MockTransport 构造 inbox 客户端。"""
    inbox = TicketInbox("http://test/api/v1", auth_token="tok")
    inbox._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    return inbox


@pytest.mark.asyncio
async def test_inbox_crud_cycle():
    """创建 → 列表 → 回复 → 关闭 的客户端契约。"""
    state = {"tickets": [], "next_id": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if request.method == "GET" and url.endswith("/api/v1/tick/tickets"):
            return httpx.Response(200, json=list(state["tickets"]))
        if request.method == "POST" and url.endswith("/api/v1/tick/tickets"):
            payload = json.loads(request.content)
            payload["id"] = state["next_id"]
            state["next_id"] += 1
            payload["status"] = "pending"
            state["tickets"].append(payload)
            return httpx.Response(201, json=payload)
        if request.method == "POST" and "/reply" in url:
            tid = int(url.split("/tickets/")[1].split("/")[0])
            t = state["tickets"][tid - 1]
            t["status"] = "replied"
            t["reply"] = json.loads(request.content)["reply"]
            return httpx.Response(201, json=t)
        if request.method == "POST" and "/resolve" in url:
            tid = int(url.split("/tickets/")[1].split("/")[0])
            t = state["tickets"][tid - 1]
            t["status"] = "resolved"
            return httpx.Response(201, json=t)
        if request.method == "POST" and url.endswith("/expire-overdue"):
            return httpx.Response(201, json={"expired": 0})
        return httpx.Response(404, json={"detail": "not found"})

    inbox = make_inbox(handler)
    created = await inbox.create_ticket(
        tick_id="t1", ticket_type="question", title="体重？", body="为什么问：基线"
    )
    assert created["id"] == 1
    assert created["status"] == "pending"
    # expected_reply_by 默认按类型 48h
    assert created["expected_reply_by"] is not None

    pending = await inbox.pending_tickets()
    assert len(pending) == 1

    replied = await inbox.reply_ticket(1, "72.5")
    assert replied["status"] == "replied"

    resolved = await inbox.resolve_ticket(1, "已记录")
    assert resolved["status"] == "resolved"
    await inbox.close()


@pytest.mark.asyncio
async def test_inbox_health_unreachable():
    def handler(request):
        raise ConnectionError("refused")

    inbox = make_inbox(handler)
    assert await inbox.health() is False
    await inbox.close()


# ── datascan ────────────────────────────────────────────────────────────────


def test_truncate_respects_budget():
    """数据包截断：按优先级保留，超限的低优先信号被丢弃。"""
    scanner = DataScanner("http://x/api/v1", max_package_chars=800)
    package = {
        "collected_at": datetime.now().isoformat(),
        "window_days": 7,
        "weight": [{"date": f"2026-11-{i:02d}", "value": 70 + i} for i in range(1, 15)],
        "sleep": [{"date": f"d{i}", "hours": 7} for i in range(10)],
        "diet": [{"meal": "x" * 100} for _ in range(5)],
        "exercise": [{"e": "y" * 100} for _ in range(5)],
        "mood": [{"m": "z" * 100} for _ in range(5)],
        "finance_food": None,
        "rhythm_checkins": None,
        "notes": None,
    }
    out = scanner.truncate(package)
    assert out["weight"] is not None  # 最高优先保留
    size = len(json.dumps(out, ensure_ascii=False, default=str))
    assert size <= 800 + 200  # 允许边界误差


@pytest.mark.asyncio
async def test_scan_unhealthy_server():
    def handler(request):
        raise ConnectionError("down")

    scanner = DataScanner("http://test/api/v1")
    scanner._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    package = await scanner.scan()
    assert package["health_ok"] is False
    await scanner.close()


@pytest.mark.asyncio
async def test_scan_collect_and_describe():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        if "body_data/series" in url:
            return httpx.Response(200, json=[{"date": "2026-11-08", "value": 72.5}])
        if url.endswith("/api/v1/health"):
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(200, json=[])  # 其他源空

    scanner = DataScanner("http://test/api/v1")
    scanner._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://test"
    )
    package = await scanner.scan(days=7)
    assert package["health_ok"] is True
    desc = scanner.describe(package)
    assert "72.5" in desc
    await scanner.close()
