# -*- coding: utf-8 -*-
# @file test_sandbox_live.py
# @brief Layer 3: 短周期可控沙盒测试（Mock Transport 验证 + 可选真实 Kimi API 验证）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from sailtick.testing.sandbox import (
    LiveSandboxRunner,
    SandboxConfig,
    SandboxEvaluator,
    resolve_live_credentials,
)


def _make_mock_llm_transport():
    """构造返回合规教练 JSON 的 MockTransport，验证沙盒全流程不依赖外网。"""
    call_idx = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_idx["n"] += 1
        # 第 1 次为 probe_api 探活
        if call_idx["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"ok": true}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        plan = {
            "summary": f"沙盒第 {call_idx['n'] - 1} 次巡检：体重趋势平稳，保持轻松节奏。",
            "tickets": [
                {
                    "type": "question",
                    "title": f"今日状态确认 #{call_idx['n'] - 1}",
                    "body": "方便时告诉我今天感觉怎么样（为什么问：调整明日建议）",
                    "priority": "normal",
                    "expected_reply_hours": 24,
                    "fallback_assumption": "默认一切平稳",
                }
            ],
            "actions": [{"kind": "episode", "content": "sandbox tick ok"}],
            "unfinished": [],
            "next_tick_suggestions": ["继续温和观察"],
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(plan, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 300, "completion_tokens": 180, "total_tokens": 480},
            },
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["quick_ping", "stress_override", "canary_shadow_live"])
async def test_sandbox_runner_scenarios_offline(scenario: str, tmp_path: Path):
    """离线验证沙盒引擎全部场景：短周期唤醒、隔离产物、质量评估与报告落盘。"""
    out_dir = tmp_path / f"sb_{scenario}"
    runner = LiveSandboxRunner(
        SandboxConfig(
            provider="kimi",
            model="kimi-k2.5",
            api_key="mock-key",
            scenario=scenario,
            wake_interval_seconds=0.05,
            max_ticks=2,
            workdir=str(out_dir),
            keep_artifacts=True,
            http_transport=_make_mock_llm_transport(),
        )
    )
    report = await runner.run()
    assert report.status == "passed", report.to_markdown()
    assert len(report.ticks) == 2
    assert all(e["passed"] for e in report.evaluations)
    assert (out_dir / "sandbox_report.json").exists()
    assert (out_dir / "sandbox_report.md").exists()
    if scenario == "canary_shadow_live":
        # Tick 1 为 shadow（0 真实票据），Tick 2 为 canary（1 张带 [Sandbox] 前缀）
        assert report.ticks[0]["mode"] == "shadow"
        assert report.ticks[0]["emitted_count"] == 0
        assert report.ticks[1]["mode"] == "canary"
        assert len(report.tickets_created) == 1
        assert report.tickets_created[0]["title"].startswith("[Sandbox] ")


@pytest.mark.asyncio
async def test_sandbox_graceful_api_blocked(tmp_path: Path):
    """API 连接受阻时优雅返回 status='api_blocked' 而非崩溃。"""

    def failing_handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unreachable")

    runner = LiveSandboxRunner(
        SandboxConfig(
            provider="kimi",
            model="kimi-k2.5",
            api_key="mock-key",
            scenario="quick_ping",
            wake_interval_seconds=0.0,
            http_transport=httpx.MockTransport(failing_handler),
        )
    )
    report = await runner.run()
    assert report.status == "api_blocked"
    assert "probe failed" in report.error


def test_sandbox_evaluator_catches_harsh_tone():
    """验证语气护栏能捕获违反温和教练人设的输出。"""
    checks = SandboxEvaluator.evaluate(
        ticks=[
            {
                "status": "completed",
                "plan_source": "llm",
                "emitted_count": 1,
                "shadow_count": 0,
                "handoff_path": __file__,
                "summary": "你自律太差！！",
            }
        ],
        tickets=[],
    )
    tone = next(c for c in checks if c["name"] == "gentle_coach_tone_guard")
    assert tone["passed"] is False


@pytest.mark.live_llm
@pytest.mark.asyncio
async def test_sandbox_live_kimi_api(tmp_path: Path):
    """真实 Kimi API 短周期可控沙盒测试（API 阻塞或未配置 Key 时自动 skip）。"""
    api_key, model, base_url = resolve_live_credentials("kimi")
    if not api_key:
        pytest.skip("KIMI_API_KEY / MOONSHOT_API_KEY not configured")

    out_dir = tmp_path / "live_kimi"
    runner = LiveSandboxRunner(
        SandboxConfig(
            provider="kimi",
            model=model,
            base_url=base_url,
            api_key=api_key,
            scenario="quick_ping",
            wake_interval_seconds=1.0,
            max_ticks=2,
            per_tick_token_cap=20_000,
            workdir=str(out_dir),
            keep_artifacts=True,
        )
    )
    report = await runner.run()
    if report.status == "api_blocked":
        pytest.skip(f"Kimi API blocked/unavailable: {report.error}")
    assert report.status == "passed", report.to_markdown()
