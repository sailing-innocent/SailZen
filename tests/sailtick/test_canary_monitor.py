# -*- coding: utf-8 -*-
# @file test_canary_monitor.py
# @brief Layer 4: 一键开关、灰度放量、自动熔断与监控 API 测试
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------

from __future__ import annotations

import os
from datetime import datetime

import pytest
from litestar.testing import AsyncTestClient

from sailtick.api.routes import create_app
from sailtick.canary import CanaryController, CanaryMonitor
from sailtick.config import CanaryConfig, LLMConfig, LLMProviderConfig, SailServerConfig, SailTickConfig
from sailtick.daemon import SailTickDaemon
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer
from sailtick.testing.trajectory import ScriptedLLM, TrajectoryStep


def _build_daemon(tmp_path, mode: str = "live", steps=None):
    clock = VirtualClock(datetime(2026, 11, 9, 12, 0, 0))
    server = SimulatedSailServer(clock=clock)
    cfg = SailTickConfig(
        data_dir=str(tmp_path / "data"),
        db_path=str(tmp_path / "db" / "sailtick.db"),
        log_dir=str(tmp_path / "logs"),
        api_port=19077,
        sail_server=SailServerConfig(api_base="http://simulated-sail-server/api/v1"),
        llm=LLMConfig(
            default="scripted",
            per_tick_token_cap=50_000,
            daily_token_cap=100_000,
            providers={"scripted": LLMProviderConfig(api_key="k", model="m")},
        ),
        canary=CanaryConfig(mode=mode, auto_downgrade_failures=2, auto_downgrade_target="shadow"),
        config_dir=os.getcwd(),
    )
    daemon = SailTickDaemon(cfg)
    daemon.inbox = server.create_inbox()
    daemon.scanner = server.create_scanner()
    daemon.notifier._clock = clock
    daemon.notifier.inbox = daemon.inbox
    daemon.canary = CanaryController(cfg.canary, daemon.db, clock=clock)
    daemon.monitor = CanaryMonitor(
        daemon.db, daemon.canary, daemon.state, daily_token_cap=cfg.llm.daily_token_cap, clock=clock
    )
    llm = ScriptedLLM(steps or [], cost_sink=daemon._record_cost)
    daemon.llm = llm
    daemon.engine.llm = llm
    daemon.engine.inbox = daemon.inbox
    daemon.engine.scanner = daemon.scanner
    daemon.engine.notifier = daemon.notifier
    daemon.engine.canary = daemon.canary
    daemon.engine._clock = clock
    return daemon, server, clock


@pytest.mark.asyncio
async def test_canary_persistence_and_one_click_kill_resume(tmp_path):
    """开关状态持久化到 SQLite，重启加载不丢失；off 总闸跳过所有 Tick。"""
    daemon, server, _ = _build_daemon(tmp_path, mode="live")
    await daemon.db.connect()
    await daemon.canary.load()

    # 一键关停
    st = await daemon.canary.kill(reason="发布前演练停机", actor="ops")
    assert st["mode"] == "off"
    res = await daemon.engine.run_tick("midday_checkin")
    assert res["status"] == "paused"
    assert res["reason"] == "mode_off"
    assert len(daemon.llm.calls) == 0

    # 模拟进程重启：新建 CanaryController 从同一 DB 加载
    reloaded = CanaryController(CanaryConfig(mode="live"), daemon.db)
    await reloaded.load()
    assert reloaded.mode == "off"
    assert reloaded.get_status()["last_switch_reason"] == "发布前演练停机"

    # 恢复到 canary 并限定 slot 白名单
    await reloaded.resume(
        target_mode="canary",
        reason="灰度放量",
        allowed_slots=["midday_checkin"],
        ticket_title_prefix="[灰度] ",
    )
    assert reloaded.should_run_slot("midday_checkin") == (True, "")
    assert reloaded.should_run_slot("morning_checkin")[0] is False

    await daemon.inbox.close()
    await daemon.scanner.close()
    await daemon.db.close()


@pytest.mark.asyncio
async def test_management_api_canary_switches_and_monitor(tmp_path):
    """验证管理 API /canary/* 一键开关、熔断降级与 /monitor 监控快照。"""
    steps = [
        TrajectoryStep(label="bad1", raise_error=RuntimeError("api err 1")),
        TrajectoryStep(label="bad2", response="invalid json"),
        TrajectoryStep(
            label="ok3",
            tokens=500,
            response={
                "summary": "恢复正常",
                "tickets": [{"type": "info", "title": "状态良好", "body": "ok", "priority": "high"}],
                "actions": [],
            },
        ),
    ]
    daemon, server, clock = _build_daemon(tmp_path, mode="canary", steps=steps)
    await daemon.db.connect()
    await daemon.canary.load()

    app = create_app(daemon)
    async with AsyncTestClient(app=app) as client:
        # 1. 查询初始灰度状态
        r = await client.get("/canary")
        assert r.status_code == 200
        assert r.json()["mode"] == "canary"

        # 2. 连续 2 次 LLM 异常触发自动熔断 -> shadow
        await daemon.engine.run_tick("morning_checkin", idempotency_suffix="c1")
        await daemon.engine.run_tick("midday_checkin", idempotency_suffix="c2")

        r_mon = await client.get("/monitor")
        assert r_mon.status_code == 200
        snap = r_mon.json()
        assert snap["canary"]["mode"] == "shadow"
        assert snap["canary"]["circuit_breaker_open"] is True
        assert snap["overall_health"] == "critical"
        assert any(a["code"] == "CIRCUIT_BREAKER_OPEN" for a in snap["alerts"])

        # 3. 格式化终端简报不报错
        report_txt = CanaryMonitor.format_report(snap)
        assert "CIRCUIT_BREAKER_OPEN" in report_txt
        assert "mode: shadow" in report_txt

        # 4. API 一键恢复到 canary 并跑通第 3 个 Tick
        r_res = await client.post("/canary/resume", json={"mode": "canary", "reason": "api recovered"})
        assert r_res.status_code == 201
        assert r_res.json()["mode"] == "canary"
        assert r_res.json()["circuit_breaker_open"] is False

        res3 = await daemon.engine.run_tick("evening_review", idempotency_suffix="c3")
        assert res3["status"] == "completed"
        assert res3["plan_source"] == "llm"
        assert len(res3["emitted"]) == 1
        # Tick 1 morning_checkin 降级规则模板发了 1 张 + Tick 3 LLM 发了 1 张 = 共 2 张
        assert len(server.tickets) == 2

        # 5. API 一键 Kill Switch -> off
        r_kill = await client.post("/canary/kill", json={"reason": "emergency stop"})
        assert r_kill.status_code == 201
        assert r_kill.json()["mode"] == "off"

        r_mon2 = await client.get("/monitor")
        snap2 = r_mon2.json()
        assert snap2["canary"]["mode"] == "off"
        assert any(a["code"] == "MODE_PAUSED" for a in snap2["alerts"])

    await daemon.inbox.close()
    await daemon.scanner.close()
    await daemon.db.close()
