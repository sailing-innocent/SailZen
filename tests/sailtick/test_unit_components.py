# -*- coding: utf-8 -*-
# @file test_unit_components.py
# @brief Layer 1: SailTick 周边核心组件单元测试（LLMGateway / Notify / Memory / Executor Nodes）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from sailtick.config import (
    LLMConfig,
    LLMProviderConfig,
    NotifyConfig,
    QuietHoursConfig,
    load_config,
)
from sailtick.db import TickDatabase
from sailtick.executor.nodes import (
    ConditionNode,
    HandoffWriteNode,
    TicketEmitNode,
    TickPlanNode,
    TickScanNode,
    WeightTrendNode,
    register_all,
)
from sailtick.handoff import HandoffManager
from sailtick.llm import LLMGateway
from sailtick.memory import AgentMemory
from sailtick.notify import NotificationEngine
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer
from sailzen.dag_client.nodes.base import NodeContext
from sailzen.dag_client.nodes.registry import NodeRegistry


# ── LLMGateway 单元测试 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_gateway_kimi_payload_and_cost_accounting():
    """验证 Kimi provider 参数适配（k2.5 temperature=1）、记账与 token 软上限检测。"""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"summary": "ok", "tickets": []}'}}],
                "usage": {"prompt_tokens": 600, "completion_tokens": 500, "total_tokens": 1100},
            },
        )

    costs = []

    async def sink(tokens: int, usd: float) -> None:
        costs.append((tokens, usd))

    cfg = LLMConfig(
        default="kimi",
        per_tick_token_cap=1000,
        providers={
            "kimi": LLMProviderConfig(
                api_key="test-kimi-key",
                model="kimi-k2.5",
                base_url="https://api.moonshot.cn/v1",
            )
        },
    )
    gw = LLMGateway(cfg, cost_sink=sink)
    gw._clients["kimi"] = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    gw.begin_tick()
    resp = await gw.chat("你好", expect_json=True, temperature=0.3)

    assert captured["url"] == "https://api.moonshot.cn/v1/chat/completions"
    assert captured["auth"] == "Bearer test-kimi-key"
    assert captured["body"]["temperature"] == 1.0  # kimi-k2.5 自动对齐为 1.0
    assert "只输出 JSON" in captured["body"]["messages"][-1]["content"]
    assert resp.provider == "kimi"
    assert resp.latency_ms >= 0.0
    assert gw.tick_tokens == 1100
    assert gw.budget_exceeded is True
    assert gw.cost_recorded_by_sink is True
    assert len(costs) == 1 and costs[0][0] == 1100 and costs[0][1] > 0
    await gw.close()


def test_config_supports_kimi_api_key_env(tmp_path, monkeypatch):
    """环境变量 KIMI_API_KEY 自动挂入 kimi provider。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "sk-kimi-env-test")
    monkeypatch.setenv("SAILTICK_LLM_DEFAULT", "kimi")
    monkeypatch.setenv("SAILTICK_MODE", "shadow")

    cfg = load_config("nonexistent.yaml")
    assert cfg.llm.default == "kimi"
    assert cfg.llm.providers["kimi"].api_key == "sk-kimi-env-test"
    assert cfg.canary.mode == "shadow"


# ── NotificationEngine 单元测试 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notify_quiet_hours_dedup_and_suppress_push():
    clock = VirtualClock(datetime(2026, 11, 9, 23, 30, 0))
    server = SimulatedSailServer(clock=clock)
    inbox = server.create_inbox()
    notifier = NotificationEngine(
        NotifyConfig(
            quiet_hours=QuietHoursConfig(start=23, end=8),
            push_enabled=True,
            dedup_window_seconds=3600,
        ),
        inbox=inbox,
        clock=clock,
    )

    # 安静时段内：normal/high 不推，urgent 推
    r1 = await notifier.emit("标题A", "内容", priority="high", ticket_type="question", tick_id="t1")
    assert r1["quiet_hours"] is True
    assert r1["push"] is False
    assert r1["ticket_id"] == 1

    # 去重窗口内同标题被跳过
    r_dup = await notifier.emit("标题A", "重复", priority="high", ticket_type="question", tick_id="t1")
    assert r_dup["action"] == "dedup_skipped"

    # urgent 穿透安静时段
    r_urg = await notifier.emit("紧急提醒", "就医", priority="urgent", ticket_type="info", tick_id="t1")
    assert r_urg["push"] is True

    # 推进至白天（09:00）且过 1h 去重窗口：suppress_push=True（canary）仍压制推送并降级为 normal
    clock.set(datetime(2026, 11, 10, 9, 0, 0))
    r_canary = await notifier.emit(
        "标题A", "白天灰度", priority="high", ticket_type="question", tick_id="t2", suppress_push=True
    )
    assert r_canary["quiet_hours"] is False
    assert r_canary["push"] is False
    assert r_canary["priority"] == "normal"
    assert r_canary["push_suppressed"] is True

    # inbox 异常时降级为 log，绝不抛异常阻塞 Tick
    server.fail_ticket_create = True
    r_fail = await notifier.emit("写入失败测试", "内容", priority="normal", tick_id="t2")
    assert r_fail["action"] == "log"
    assert "error" in r_fail
    await inbox.close()


# ── AgentMemory 单元测试 ───────────────────────────────────────────────────


@pytest_asyncio.fixture()
async def mem_db(tmp_path):
    db = TickDatabase(str(tmp_path / "mem.db"))
    await db.connect()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_agent_memory_four_layers_and_ttl(mem_db):
    mem = AgentMemory(mem_db)
    await mem.set_profile("goal_weight", "70kg", confidence=1.0, source="asked")
    assert await mem.get_profile("goal_weight") == "70kg"

    await mem.save("semantic", "wednesday_pattern", "周三常聚餐")
    await mem.update("semantic", "wednesday_pattern", "周三聚餐偏多")
    assert await mem.get("semantic", "wednesday_pattern") == "周三聚餐偏多"

    await mem.save("procedural", "tone", "不要催促称重")
    await mem.save_episode("tick-1", "scan", {"ok": True})

    # 写入一条已过期记忆，验证 cleanup_expired 清理
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    await mem_db.create_memory("semantic", "expired_key", "old", ttl_seconds=1, expires_at=past)
    cleaned = await mem.cleanup_expired()
    assert cleaned == 1
    assert await mem.get("semantic", "expired_key") is None

    summary = await mem.summary_for_prompt()
    assert "goal_weight = 70kg" in summary["profile"]
    assert "周三聚餐偏多" in summary["semantic"]
    assert "不要催促称重" in summary["procedural"]


# ── Executor Nodes 单元测试 ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sailtick_executor_nodes(tmp_path):
    registry = NodeRegistry()
    register_all(registry)
    for t in ("tick_scan", "tick_plan", "ticket_emit", "weight_trend", "condition", "handoff_write"):
        assert t in registry.list_types()

    clock = VirtualClock(datetime(2026, 11, 9, 8, 0, 0))
    server = SimulatedSailServer(clock=clock)
    server.seed_weight("2026-11-01", 75.5)
    server.seed_weight("2026-11-09", 74.2)

    db = TickDatabase(str(tmp_path / "nodes.db"))
    await db.connect()
    handoffs = HandoffManager(db, str(tmp_path / "handoffs"))
    inbox = server.create_inbox()
    scanner = server.create_scanner()
    services = {"inbox": inbox, "scanner": scanner, "handoffs": handoffs}

    # 1. TickScanNode
    scan_res = await TickScanNode().execute(
        NodeContext(run_id="r1", node_id="n1", node_type="tick_scan", params={"days": 7, "_services": services})
    )
    assert scan_res.success and scan_res.data["data_ok"] is True

    # 2. WeightTrendNode（75.5 -> 74.2 判定下降）
    trend_res = await WeightTrendNode().execute(
        NodeContext(run_id="r1", node_id="n2", node_type="weight_trend", params={"days": 14, "_services": services})
    )
    assert trend_res.success and trend_res.data["trend"] == "down"
    assert trend_res.data["latest"] == 74.2

    # 3. TicketEmitNode 校验 + 执行
    emit_node = TicketEmitNode()
    assert emit_node.validate_params({}) is not None
    emit_res = await emit_node.execute(
        NodeContext(
            run_id="r1",
            node_id="n3",
            node_type="ticket_emit",
            params={"title": "节点测试票据", "body": "b", "tick_id": "t1", "_services": services},
        )
    )
    assert emit_res.success and emit_res.data["ticket_id"] == 1

    # 4. ConditionNode（分支求值）
    cond_res = await ConditionNode().execute(
        NodeContext(
            run_id="r1",
            node_id="n4",
            node_type="condition",
            params={
                "condition": "upstream.n2.count > 1",
                "true_next": ["go_true"],
                "false_next": ["go_false"],
            },
            upstream_results={"n2": {"count": 2}},
        )
    )
    assert cond_res.success and cond_res.data["value"] is True
    assert cond_res.next_nodes == ["go_true"]

    # 5. TickPlanNode 无 LLM 降级 noop
    plan_res = await TickPlanNode().execute(
        NodeContext(run_id="r1", node_id="n5", node_type="tick_plan", params={})
    )
    assert plan_res.success and plan_res.data["source"] == "noop"

    # 6. HandoffWriteNode
    ho_res = await HandoffWriteNode().execute(
        NodeContext(
            run_id="r1",
            node_id="n6",
            node_type="handoff_write",
            params={
                "tick_id": "t1",
                "slot": "morning_checkin",
                "tick_date": "2026-11-09",
                "summary": "节点测试交接",
                "_services": services,
            },
        )
    )
    assert ho_res.success and ho_res.data["path"]

    await inbox.close()
    await scanner.close()
    await db.close()
