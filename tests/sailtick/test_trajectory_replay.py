# -*- coding: utf-8 -*-
# @file test_trajectory_replay.py
# @brief Layer 2: Mock LLM 轨迹回放测试（周边硬组件全链路确定性验证）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from sailtick.config import SelfDevConfig
from sailtick.dev.tasks import DevTaskRunner
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer
from sailtick.testing.trajectory import (
    BUILTIN_SCENARIOS,
    TrajectoryRunner,
    TrajectoryScenario,
    TrajectoryStep,
    TrajectoryTickSpec,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_name", list(BUILTIN_SCENARIOS.keys()))
async def test_builtin_trajectory_scenarios(scenario_name: str, tmp_path: Path):
    """批量验证所有内置 Mock LLM 轨迹场景。"""
    runner = TrajectoryRunner(workdir=tmp_path)
    report = await runner.run(BUILTIN_SCENARIOS[scenario_name]())
    assert report.passed, f"{report.to_summary()}"


@pytest.mark.asyncio
async def test_trajectory_shadow_canary_live_matrix(tmp_path: Path):
    """同一条 LLM 轨迹在 shadow / canary / live 三种模式下的精确副作用矩阵。"""

    def make_plan_step() -> TrajectoryStep:
        return TrajectoryStep(
            label="two_high_tickets",
            response={
                "summary": "生成 2 张高优先票据验证模式隔离",
                "tickets": [
                    {
                        "type": "question",
                        "title": "问题一",
                        "body": "正文一",
                        "priority": "high",
                        "expected_reply_hours": 24,
                        "fallback_assumption": "假设一",
                    },
                    {
                        "type": "question",
                        "title": "问题二",
                        "body": "正文二",
                        "priority": "high",
                        "expected_reply_hours": 24,
                        "fallback_assumption": "假设二",
                    },
                ],
                "actions": [],
                "unfinished": [],
                "next_tick_suggestions": [],
            },
        )

    runner = TrajectoryRunner(workdir=tmp_path)

    # 1. shadow: 0 张真实票据，2 张影子模拟
    r_shadow = await runner.run(
        TrajectoryScenario(
            name="matrix_shadow",
            description="shadow isolation",
            start_time=datetime(2026, 11, 9, 12, 0, 0),
            canary_mode="shadow",
            steps=[make_plan_step()],
            ticks=[TrajectoryTickSpec(slot="midday_checkin")],
        )
    )
    assert r_shadow.passed
    assert len(r_shadow.tickets) == 0
    assert len(r_shadow.tick_results[0]["shadow_emitted"]) == 2
    assert r_shadow.monitor_snapshot["metrics"]["shadow_tickets_simulated"] == 2

    # 2. canary: 限流 1 张、带前缀、禁止手机强推（降级 normal）
    r_canary = await runner.run(
        TrajectoryScenario(
            name="matrix_canary",
            description="canary caps",
            start_time=datetime(2026, 11, 9, 12, 0, 0),
            canary_mode="canary",
            canary_overrides={"ticket_title_prefix": "[Canary] "},
            steps=[make_plan_step()],
            ticks=[TrajectoryTickSpec(slot="midday_checkin")],
        )
    )
    assert r_canary.passed
    assert len(r_canary.tickets) == 1
    assert r_canary.tickets[0]["title"].startswith("[Canary] ")
    assert r_canary.tickets[0]["priority"] == "normal"
    assert r_canary.tick_results[0]["emitted"][0]["result"]["push"] is False

    # 3. live: 放行 2 张且白天高优先允许推送
    r_live = await runner.run(
        TrajectoryScenario(
            name="matrix_live",
            description="live full",
            start_time=datetime(2026, 11, 9, 12, 0, 0),
            canary_mode="live",
            steps=[make_plan_step()],
            ticks=[TrajectoryTickSpec(slot="midday_checkin")],
        )
    )
    assert r_live.passed
    assert len(r_live.tickets) == 2
    assert r_live.tickets[0]["priority"] == "high"
    assert r_live.tick_results[0]["emitted"][0]["result"]["push"] is True


@pytest.mark.asyncio
async def test_trajectory_self_dev_guardrails_end_to_end(tmp_path: Path):
    """夜间 Tick 轨迹同时包含非法与合法 dev_task：非法被护栏拦截，合法提交 dev 分支并开 approval 票据。"""
    repo = tmp_path / "dev_repo"
    repo.mkdir()

    def _git(*args: str) -> str:
        res = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        assert res.returncode == 0, res.stderr
        return res.stdout.strip()

    _git("init", "-b", "main")
    _git("config", "user.email", "traj@test")
    _git("config", "user.name", "traj")
    (repo / "sailtick").mkdir()
    (repo / "sailtick" / "__init__.py").write_text("# init\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=keep\n", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "-m", "init")

    dev_cfg = SelfDevConfig(
        repo_dir=str(repo),
        branch="agent/sailtick-dev",
        whitelist_dirs=["sailtick", "tests/sailtick"],
        protected_paths=["data", ".env", ".git"],
    )

    def setup(daemon, server: SimulatedSailServer, _clock: VirtualClock) -> None:
        dev_runner = DevTaskRunner(dev_cfg, inbox=daemon.inbox)
        dev_runner._run_tests = lambda task: (True, "ok")
        daemon.engine.dev_runner = dev_runner

    async def verify(report, daemon, server: SimulatedSailServer) -> None:
        assert report.tick_results[0]["status"] == "completed"
        # .env 未被篡改
        assert (repo / ".env").read_text(encoding="utf-8") == "SECRET=keep\n"
        # 合法任务提交到 agent/sailtick-dev 且开了 approval 票据，main 保持干净
        assert _git("branch", "--show-current") == "agent/sailtick-dev"
        assert "add_helper" in _git("log", "--oneline")
        assert "add_helper" not in _git("log", "--oneline", "main")
        assert any(t["type"] == "approval" for t in server.tickets)
        dev_eps = [e for e in await daemon.memory.list_episodes() if e["kind"] == "dev"]
        assert len(dev_eps) == 2
        statuses = {e["content"]["task"]: e["content"]["success"] for e in dev_eps}
        assert statuses["illegal_env"] is False
        assert statuses["add_helper"] is True

    scenario = TrajectoryScenario(
        name="self_dev_guardrail",
        description="nightly dev_task 护栏轨迹验证",
        start_time=datetime(2026, 11, 10, 0, 0, 0),
        canary_mode="live",
        setup=setup,
        steps=[
            TrajectoryStep(
                label="nightly_dev",
                response={
                    "summary": "夜间维护执行两个自研任务（一非法一合法）",
                    "tickets": [],
                    "actions": [
                        {
                            "kind": "dev_task",
                            "task_id": "illegal_env",
                            "title": "hack env",
                            "description": "should fail",
                            "files": [".env"],
                            "file_contents": {".env": "PWNED=1"},
                        },
                        {
                            "kind": "dev_task",
                            "task_id": "add_helper",
                            "title": "add_helper module",
                            "description": "safe helper",
                            "files": ["sailtick/demo_helper.py"],
                            "file_contents": {"sailtick/demo_helper.py": "VALUE = 42\n"},
                        },
                    ],
                    "unfinished": [],
                    "next_tick_suggestions": [],
                },
            )
        ],
        ticks=[TrajectoryTickSpec(slot="nightly_maintenance")],
        verify=verify,
    )

    runner = TrajectoryRunner(workdir=tmp_path)
    report = await runner.run(scenario)
    assert report.passed, report.to_summary()


@pytest.mark.asyncio
async def test_trajectory_cost_accounting_no_double_count(tmp_path: Path):
    """验证通过 cost_sink 记账后 HANDOFF 不重复叠加 token 成本。"""
    scenario = TrajectoryScenario(
        name="cost_exact",
        description="验证单 Tick 记账精确性",
        per_tick_token_cap=500,
        steps=[
            TrajectoryStep(
                label="exact_320",
                tokens=320,
                cost_usd=0.0012,
                response={"summary": "ok", "tickets": [], "actions": []},
            )
        ],
        ticks=[TrajectoryTickSpec(slot="morning_checkin")],
    )
    runner = TrajectoryRunner(workdir=tmp_path)
    report = await runner.run(scenario)
    assert report.passed
    assert report.tick_results[0]["cost_tokens"] == 320
    # 若存在重复叠加，这里会变成 640
    assert report.monitor_snapshot["metrics"]["daily_tokens"] == 320
