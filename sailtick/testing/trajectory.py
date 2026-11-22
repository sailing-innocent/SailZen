# -*- coding: utf-8 -*-
# @file trajectory.py
# @brief Layer 2: Mock LLM 轨迹回放测试框架（确定性多 Tick 硬组件端到端验证）
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""Trajectory Replay Harness — Mock LLM 轨迹的周边硬组件测试。

为什么 LLM 产品需要轨迹回放测试:
  - 真实 LLM 输出具有随机性、耗时高、按次计费，不适合高频回归周边硬组件。
  - 单次 mock 单元测试无法覆盖“多 Tick 交接 -> 用户回复 -> 超期 fallback ->
    故障恢复 -> 预算熔断 -> 自我开发护栏”等跨时间窗口的状态演进。
  - 本模块将 LLM 抽象为可编程轨迹 (ScriptedLLM)，配合 VirtualClock 与
    SimulatedSailServer（经真实 httpx.MockTransport），在毫秒级确定性地把
    SailTick 所有硬组件（TickEngine/DB/Handoff/Memory/Inbox/DataScan/
    Notify/Canary/DevGuard）串起来验证。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from sailtick.canary import CanaryController, CanaryMonitor
from sailtick.config import CanaryConfig, LLMConfig, LLMProviderConfig, SailServerConfig, SailTickConfig, TickConfig
from sailtick.daemon import SailTickDaemon
from sailtick.llm import LLMResponse
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer


@dataclass
class TrajectoryStep:
    """单次 LLM 调用的脚本化输出与输入断言。"""

    response: Union[Dict[str, Any], str] = ""
    tokens: int = 250
    cost_usd: float = 0.0005
    raise_error: Optional[Exception] = None
    assert_prompt_contains: List[str] = field(default_factory=list)
    assert_prompt_not_contains: List[str] = field(default_factory=list)
    label: str = ""


class ScriptedLLM:
    """可编程轨迹 Mock LLM，兼容 LLMGateway 全部接口并完整录制 Prompt 轨迹。"""

    def __init__(
        self,
        steps: List[TrajectoryStep],
        per_tick_token_cap: int = 200_000,
        cost_sink: Optional[Callable[[int, float], Any]] = None,
    ):
        self._steps = list(steps)
        self._cursor = 0
        self._cost_sink = cost_sink
        self._tick_tokens = 0
        self._tick_usd = 0.0
        self._cost_recorded_by_sink = False
        self._budget_exceeded = False
        self.calls: List[Dict[str, Any]] = []
        self.config = LLMConfig(
            default="scripted",
            per_tick_token_cap=per_tick_token_cap,
            providers={"scripted": LLMProviderConfig(api_key="scripted-key", model="scripted-v1")},
        )

    def begin_tick(self) -> None:
        self._tick_tokens = 0
        self._tick_usd = 0.0
        self._cost_recorded_by_sink = False
        self._budget_exceeded = False

    @property
    def tick_tokens(self) -> int:
        return self._tick_tokens

    @property
    def tick_usd(self) -> float:
        return self._tick_usd

    @property
    def cost_recorded_by_sink(self) -> bool:
        return self._cost_recorded_by_sink

    @property
    def budget_exceeded(self) -> bool:
        return self._budget_exceeded

    async def chat(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system: Optional[str] = None,
        expect_json: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        if self._cursor >= len(self._steps):
            step = TrajectoryStep(
                response={"summary": "default scripted noop", "tickets": [], "actions": []}
            )
        else:
            step = self._steps[self._cursor]
            self._cursor += 1

        # 校验 Prompt 注入不变量（确保上下文组装器真正把 handoff / 回复 / 数据送进了 LLM）
        missing = [s for s in step.assert_prompt_contains if s not in prompt]
        forbidden = [s for s in step.assert_prompt_not_contains if s in prompt]
        call_record = {
            "index": len(self.calls),
            "label": step.label,
            "prompt": prompt,
            "prompt_chars": len(prompt),
            "expect_json": expect_json,
            "missing_assertions": missing,
            "forbidden_assertions": forbidden,
            "error": str(step.raise_error) if step.raise_error else None,
        }
        self.calls.append(call_record)

        if missing:
            raise AssertionError(f"Trajectory prompt missing expected substrings: {missing}")
        if forbidden:
            raise AssertionError(f"Trajectory prompt contained forbidden substrings: {forbidden}")

        if step.raise_error is not None:
            raise step.raise_error

        content = (
            json.dumps(step.response, ensure_ascii=False)
            if isinstance(step.response, dict)
            else str(step.response)
        )
        self._tick_tokens += step.tokens
        self._tick_usd += step.cost_usd
        if self._cost_sink is not None:
            await self._cost_sink(step.tokens, step.cost_usd)
            self._cost_recorded_by_sink = True

        if self._tick_tokens > self.config.per_tick_token_cap:
            self._budget_exceeded = True

        return LLMResponse(
            content=content,
            usage={"total_tokens": step.tokens, "prompt_tokens": step.tokens // 2, "completion_tokens": step.tokens - step.tokens // 2},
            model="scripted-v1",
            provider="scripted",
            latency_ms=1.0,
        )

    async def close(self) -> None:
        pass


@dataclass
class TrajectoryTickSpec:
    """轨迹中的单个 Tick 事件及前置/后置环境动作。"""

    slot: str
    advance_hours: int = 0
    advance_minutes: int = 0
    idempotency_suffix: Optional[str] = None
    before: Optional[Callable[[SailTickDaemon, SimulatedSailServer, VirtualClock], Any]] = None
    after: Optional[Callable[[Dict[str, Any], SailTickDaemon, SimulatedSailServer, VirtualClock], Any]] = None


@dataclass
class TrajectoryScenario:
    """完整的轨迹测试场景定义。"""

    name: str
    description: str
    start_time: datetime = field(default_factory=lambda: datetime(2026, 11, 9, 6, 0, 0))
    canary_mode: str = "live"
    canary_overrides: Dict[str, Any] = field(default_factory=dict)
    per_tick_token_cap: int = 200_000
    steps: List[TrajectoryStep] = field(default_factory=list)
    ticks: List[TrajectoryTickSpec] = field(default_factory=list)
    setup: Optional[Callable[[SailTickDaemon, SimulatedSailServer, VirtualClock], Any]] = None
    verify: Optional[Callable[["TrajectoryReport", SailTickDaemon, SimulatedSailServer], Any]] = None


@dataclass
class TrajectoryReport:
    """轨迹回放执行报告。"""

    scenario: str
    passed: bool
    tick_results: List[Dict[str, Any]]
    llm_calls: List[Dict[str, Any]]
    tickets: List[Dict[str, Any]]
    monitor_snapshot: Dict[str, Any]
    errors: List[str] = field(default_factory=list)

    def to_summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        m = self.monitor_snapshot.get("metrics", {})
        return (
            f"[{status}] {self.scenario}: ticks={len(self.tick_results)} "
            f"llm_calls={len(self.llm_calls)} tickets={len(self.tickets)} "
            f"fallback_rate={m.get('llm_fallback_rate', 0)*100:.0f}% "
            f"health={self.monitor_snapshot.get('overall_health')}"
            + (f" errors={self.errors}" if self.errors else "")
        )


class TrajectoryRunner:
    """确定性轨迹回放执行器。"""

    def __init__(self, workdir: Optional[Path] = None):
        self._workdir = workdir

    async def run(self, scenario: TrajectoryScenario) -> TrajectoryReport:
        temp_dir: Optional[tempfile.TemporaryDirectory] = None
        if self._workdir is not None:
            base = self._workdir / scenario.name
            base.mkdir(parents=True, exist_ok=True)
        else:
            temp_dir = tempfile.TemporaryDirectory(prefix=f"sailtick_traj_{scenario.name}_")
            base = Path(temp_dir.name)

        clock = VirtualClock(scenario.start_time)
        server = SimulatedSailServer(clock=clock)

        canary_cfg = CanaryConfig(mode=scenario.canary_mode, **scenario.canary_overrides)
        cfg = SailTickConfig(
            data_dir=str(base / "data"),
            db_path=str(base / "db" / "sailtick.db"),
            log_dir=str(base / "logs"),
            api_port=19075,
            sail_server=SailServerConfig(api_base="http://simulated-sail-server/api/v1"),
            tick=TickConfig(hours=[0, 6, 12, 18], work_budget_minutes=180),
            llm=LLMConfig(
                default="scripted",
                per_tick_token_cap=scenario.per_tick_token_cap,
                providers={"scripted": LLMProviderConfig(api_key="scripted-key", model="scripted-v1")},
            ),
            canary=canary_cfg,
            config_dir=os.getcwd(),
        )

        daemon = SailTickDaemon(cfg)
        daemon.inbox = server.create_inbox()
        daemon.scanner = server.create_scanner()
        daemon.notifier._clock = clock
        daemon.notifier.inbox = daemon.inbox
        daemon.canary = CanaryController(cfg.canary, daemon.db, clock=clock)
        daemon.monitor = CanaryMonitor(
            daemon.db,
            daemon.canary,
            daemon.state,
            daily_token_cap=cfg.llm.daily_token_cap,
            clock=clock,
        )

        scripted_llm = ScriptedLLM(
            steps=scenario.steps,
            per_tick_token_cap=scenario.per_tick_token_cap,
            cost_sink=daemon._record_cost,
        )
        daemon.llm = scripted_llm
        daemon.engine.llm = scripted_llm
        daemon.engine.inbox = daemon.inbox
        daemon.engine.scanner = daemon.scanner
        daemon.engine.notifier = daemon.notifier
        daemon.engine.canary = daemon.canary
        daemon.engine._clock = clock

        await daemon.db.connect()
        await daemon.canary.load()

        tick_results: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            if scenario.setup is not None:
                res = scenario.setup(daemon, server, clock)
                if hasattr(res, "__await__"):
                    await res

            for spec in scenario.ticks:
                if spec.advance_hours or spec.advance_minutes:
                    clock.advance(hours=spec.advance_hours, minutes=spec.advance_minutes)
                if spec.before is not None:
                    res = spec.before(daemon, server, clock)
                    if hasattr(res, "__await__"):
                        await res

                result = await daemon.engine.run_tick(
                    spec.slot,
                    tick_date=clock().strftime("%Y-%m-%d"),
                    idempotency_suffix=spec.idempotency_suffix,
                )
                tick_results.append(result)

                if spec.after is not None:
                    res = spec.after(result, daemon, server, clock)
                    if hasattr(res, "__await__"):
                        await res

            snap = await daemon.get_monitor_snapshot()
            report = TrajectoryReport(
                scenario=scenario.name,
                passed=True,
                tick_results=tick_results,
                llm_calls=list(scripted_llm.calls),
                tickets=list(server.tickets),
                monitor_snapshot=snap,
                errors=errors,
            )
            if scenario.verify is not None:
                try:
                    res = scenario.verify(report, daemon, server)
                    if hasattr(res, "__await__"):
                        await res
                except AssertionError as exc:
                    report.passed = False
                    report.errors.append(str(exc))
            return report
        except Exception as exc:
            snap = await daemon.get_monitor_snapshot()
            errors.append(f"{type(exc).__name__}: {exc}")
            return TrajectoryReport(
                scenario=scenario.name,
                passed=False,
                tick_results=tick_results,
                llm_calls=list(scripted_llm.calls),
                tickets=list(server.tickets),
                monitor_snapshot=snap,
                errors=errors,
            )
        finally:
            await daemon.inbox.close()
            await daemon.scanner.close()
            await daemon.db.close()
            if temp_dir is not None:
                temp_dir.cleanup()


# ═══════════════════════════════════════════════════════════════════════
#  内置轨迹测试场景库
# ═══════════════════════════════════════════════════════════════════════


def _scenario_onboarding_reply_loop() -> TrajectoryScenario:
    async def setup(d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        await d.memory.set_profile("goal_weight", "70kg", confidence=1.0, source="asked")
        await d.db.create_plan("v0.1", "70kg", "# 初版计划\n每天称重", "bootstrap", active=True)
        s.seed_weight("2026-11-08", 74.8)

    def reply_after_morning(_d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        s.simulate_user_reply_latest_pending("今天早晨 74.5kg，睡了 7 小时")
        s.seed_weight("2026-11-09", 74.5)

    async def verify(report: TrajectoryReport, d: SailTickDaemon, s: SimulatedSailServer) -> None:
        assert len(report.tick_results) == 3
        assert all(r["status"] == "completed" for r in report.tick_results)
        assert all(r["plan_source"] == "llm" for r in report.tick_results)
        assert len(s.tickets) == 1
        assert s.tickets[0]["status"] == "replied"
        assert await d.memory.get("semantic", "morning_habit") == "7h睡眠正常"
        handoffs = await d.db.list_handoffs()
        assert len(handoffs) == 3

    return TrajectoryScenario(
        name="onboarding_reply_loop",
        description="多 Tick 完整闭环：早间发票据 -> 用户回复+记体重 -> 午间 Prompt 注入回复与交接 -> 晚间落语义记忆",
        start_time=datetime(2026, 11, 9, 6, 0, 0),
        setup=setup,
        steps=[
            TrajectoryStep(
                label="morning",
                assert_prompt_contains=["70kg", "74.8kg"],
                response={
                    "summary": "早间建基线，询问今日体重与睡眠",
                    "tickets": [
                        {
                            "type": "question",
                            "title": "今早体重和睡眠如何？",
                            "body": "用于更新基线（为什么问：追踪每日波动）",
                            "priority": "normal",
                            "expected_reply_hours": 24,
                            "fallback_assumption": "维持 74.8kg",
                        }
                    ],
                    "actions": [{"kind": "episode", "content": "morning baseline checked"}],
                    "unfinished": [],
                    "next_tick_suggestions": ["午间检查回复"],
                },
            ),
            TrajectoryStep(
                label="midday",
                assert_prompt_contains=["早间建基线", "74.5kg", "今天早晨 74.5kg"],
                response={
                    "summary": "收到早间回复 74.5kg（较昨日下降 0.3kg），继续观察午餐",
                    "tickets": [],
                    "actions": [
                        {
                            "kind": "memory",
                            "memory_type": "semantic",
                            "key": "morning_habit",
                            "value": "7h睡眠正常",
                        }
                    ],
                    "unfinished": [],
                    "next_tick_suggestions": ["晚间温和复盘"],
                },
            ),
            TrajectoryStep(
                label="evening",
                assert_prompt_contains=["收到早间回复 74.5kg", "7h睡眠正常"],
                response={
                    "summary": "晚间复盘平稳，无额外打扰",
                    "tickets": [],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": ["明早继续称重"],
                },
            ),
        ],
        ticks=[
            TrajectoryTickSpec(slot="morning_checkin"),
            TrajectoryTickSpec(slot="midday_checkin", advance_hours=6, before=reply_after_morning),
            TrajectoryTickSpec(slot="evening_review", advance_hours=6),
        ],
        verify=verify,
    )


def _scenario_fault_injection_and_recovery() -> TrajectoryScenario:
    def server_down(_d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        s.reachable = False

    def server_up(_d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        s.reachable = True
        s.seed_weight("2026-11-10", 74.1)

    async def verify(report: TrajectoryReport, d: SailTickDaemon, _s: SimulatedSailServer) -> None:
        assert [r["status"] for r in report.tick_results] == [
            "completed",
            "completed",
            "completed",
            "completed",
        ]
        assert report.tick_results[0]["plan_source"] == "fallback_error"
        assert report.tick_results[1]["plan_source"] == "llm"
        assert report.tick_results[2]["plan_source"] == "fallback_error"
        assert report.tick_results[3]["plan_source"] == "llm"
        # 连续失败未达 3 次阈值（中间第 2 次成功重置），不应触发熔断
        assert d.canary.get_status()["circuit_breaker_open"] is False

    return TrajectoryScenario(
        name="fault_injection_and_recovery",
        description="故障注入与恢复：非法 JSON 降级 -> sail_server 宕机本地维护 -> LLM 503 降级 -> 双恢复",
        start_time=datetime(2026, 11, 9, 6, 0, 0),
        steps=[
            TrajectoryStep(label="bad_json", response="not valid json {{{{"),
            TrajectoryStep(
                label="server_down_ok_llm",
                assert_prompt_contains=["不可用"],
                response={
                    "summary": "服务端暂不可达，仅记录本地维护",
                    "tickets": [],
                    "actions": [{"kind": "episode", "content": "local maintenance"}],
                    "unfinished": [],
                    "next_tick_suggestions": ["服务端恢复后重新扫描"],
                },
            ),
            TrajectoryStep(label="llm_503", raise_error=RuntimeError("HTTP 503 overloaded")),
            TrajectoryStep(
                label="recovered",
                assert_prompt_contains=["74.1kg"],
                response={
                    "summary": "依赖全面恢复，记录最新体重 74.1kg",
                    "tickets": [],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": [],
                },
            ),
        ],
        ticks=[
            TrajectoryTickSpec(slot="morning_checkin"),
            TrajectoryTickSpec(slot="midday_checkin", advance_hours=6, before=server_down),
            TrajectoryTickSpec(slot="evening_review", advance_hours=6, before=server_up),
            TrajectoryTickSpec(slot="morning_checkin", advance_hours=12),
        ],
        verify=verify,
    )


def _scenario_quiet_hours_and_expiry() -> TrajectoryScenario:
    async def verify(report: TrajectoryReport, _d: SailTickDaemon, s: SimulatedSailServer) -> None:
        # 23:30 安静时段：normal 不推送，urgent 推送
        emitted = report.tick_results[0]["emitted"]
        assert len(emitted) == 2
        assert emitted[0]["result"]["quiet_hours"] is True
        assert emitted[0]["result"]["push"] is False
        assert emitted[1]["result"]["push"] is True
        # 推进 26 小时后下一次 Tick SCAN 自动触发 expire_overdue，24h 票据过期
        assert s.tickets[0]["status"] == "expired"
        assert s.tickets[1]["status"] == "pending"

    return TrajectoryScenario(
        name="quiet_hours_and_expiry",
        description="安静时段推送信令控制 + 虚拟时钟推进 26h 验证超期自动 expired",
        start_time=datetime(2026, 11, 9, 23, 30, 0),
        steps=[
            TrajectoryStep(
                label="late_night_emit",
                response={
                    "summary": "深夜巡检发出 1 条普通票据与 1 条紧急健康提示",
                    "tickets": [
                        {
                            "type": "question",
                            "title": "普通晚间确认",
                            "body": "明天方便回复即可",
                            "priority": "normal",
                            "expected_reply_hours": 24,
                            "fallback_assumption": "保持原计划",
                        },
                        {
                            "type": "info",
                            "title": "异常波动就医提醒",
                            "body": "连续异常掉秤建议关注身体",
                            "priority": "urgent",
                            "expected_reply_hours": 72,
                            "fallback_assumption": "继续关注",
                        },
                    ],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": [],
                },
            ),
            TrajectoryStep(
                label="after_26h",
                response={
                    "summary": "已按 fallback 假设推进",
                    "tickets": [],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": [],
                },
            ),
        ],
        ticks=[
            TrajectoryTickSpec(slot="evening_review"),
            TrajectoryTickSpec(slot="morning_checkin", advance_hours=26),
        ],
        verify=verify,
    )


def _scenario_canary_circuit_breaker() -> TrajectoryScenario:
    async def verify(report: TrajectoryReport, d: SailTickDaemon, s: SimulatedSailServer) -> None:
        # 连续 2 次 LLM 异常触发自动熔断降级至 shadow
        assert d.canary.mode == "shadow"
        assert d.canary.get_status()["circuit_breaker_open"] is True
        # 第 3 次在 shadow 模式下即使 LLM 恢复成功，也不创建真实票据
        assert report.tick_results[2]["mode"] == "shadow"
        assert len(report.tick_results[2]["shadow_emitted"]) == 1
        assert len(s.tickets) == 0
        codes = {a["code"] for a in report.monitor_snapshot["alerts"]}
        assert "CIRCUIT_BREAKER_OPEN" in codes

    return TrajectoryScenario(
        name="canary_circuit_breaker",
        description="灰度熔断演练：canary 模式下连续 2 次 LLM 异常自动降级 shadow，恢复后仅影子模拟不写主库",
        start_time=datetime(2026, 11, 9, 6, 0, 0),
        canary_mode="canary",
        canary_overrides={"auto_downgrade_failures": 2, "auto_downgrade_target": "shadow"},
        steps=[
            TrajectoryStep(label="fail_1", raise_error=RuntimeError("timeout 1")),
            TrajectoryStep(label="fail_2", response="broken json"),
            TrajectoryStep(
                label="recover_in_shadow",
                response={
                    "summary": "熔断后影子演练恢复正常",
                    "tickets": [
                        {
                            "type": "question",
                            "title": "影子票据不应落主库",
                            "body": "shadow check",
                            "priority": "high",
                        }
                    ],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": [],
                },
            ),
        ],
        ticks=[
            TrajectoryTickSpec(slot="midday_checkin"),
            TrajectoryTickSpec(slot="evening_review", advance_hours=6),
            TrajectoryTickSpec(slot="morning_checkin", advance_hours=12),
        ],
        verify=verify,
    )


def _scenario_health_coach_full_day_loop() -> TrajectoryScenario:
    """健康管理升级全天闭环：
    1) 早间巡检：监测到新体重 + 尝试提 2 个问题被防轰炸护栏限流为 1 个；
    2) 白天用户回复早间问题 + 在 Android 静默主动发送午饭/晚饭信息（无需 AI 即时回复）；
    3) 21:45 睡前日报：整合全部体重与主动餐饮消息 -> 写画像 -> 同步 AI 动态计划 -> 发布睡前日报 -> 吸收消息并关闭已答票据。
    """

    async def setup(d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        d.config.notify.max_questions_per_tick = 1
        await d.memory.set_profile("goal_weight", "70kg", confidence=1.0, source="asked")
        s.seed_weight("2026-11-21", 75.2)
        s.seed_weight("2026-11-22", 74.8)

    def user_daytime_activity(_d: SailTickDaemon, s: SimulatedSailServer, _c: VirtualClock) -> None:
        s.simulate_user_reply_latest_pending("工作日一般 7:30 起床，23:00 睡")
        s.simulate_user_message("午饭吃了食堂鸡胸肉+半碗米饭+西兰花", category="diet", meta={"meal_type": "lunch"})
        s.simulate_user_message("晚饭吃了番茄鸡蛋面少面+卤蛋", category="diet", meta={"meal_type": "dinner"})

    async def verify(report: TrajectoryReport, d: SailTickDaemon, s: SimulatedSailServer) -> None:
        assert len(report.tick_results) == 2
        assert all(r["status"] == "completed" for r in report.tick_results)
        # 1) 早间防轰炸：LLM 企图提 2 个问题，护栏严格截断为 1 个
        assert len(report.tick_results[0]["emitted"]) == 1
        assert len(s.tickets) == 1
        assert s.tickets[0]["status"] == "resolved"
        # 2) 画像更新生效
        prof = await d.memory.all_profile()
        assert prof.get("schedule_workday", {}).get("value") == "07:30-23:00"
        # 3) 用户主动发送的 2 条餐饮消息全部被标记 ingested
        assert len(s.messages) == 2
        assert all(m["status"] == "ingested" for m in s.messages)
        # 4) AI 动态体重计划已写回 sail_server
        assert s.weight_plan is not None
        assert s.weight_plan["managedBy"] == "sailtick"
        assert s.weight_plan["curveType"] == "ai_dynamic"
        assert s.weight_plan["phaseName"] == "基线观察与稳态起步"
        # 5) 睡前日报已发布并推送
        assert "2026-11-22" in s.daily_reports
        rep = s.daily_reports["2026-11-22"]
        assert rep["pushed"] is True
        assert "74.8" in rep["summary"]

    return TrajectoryScenario(
        name="health_coach_full_day_loop",
        description="健康管理全天闭环：体重监控 + 防轰炸渐进提问(限1题) + 静默餐饮收集 + AI 动态计划同步 + 睡前体重日报",
        start_time=datetime(2026, 11, 22, 8, 30, 0),
        setup=setup,
        steps=[
            TrajectoryStep(
                label="morning_progressive_question",
                assert_prompt_contains=["74.8kg", "有新的体重测量数据更新"],
                response={
                    "summary": "早间检测到体重降至 74.8kg，发起 1 个作息渐进提问",
                    "tickets": [
                        {
                            "type": "question",
                            "topic": "wake_time",
                            "title": "平时大概几点起床和睡觉？",
                            "body": "了解作息后，我可以把睡前日报和称重提醒安排在最不打扰你的时间。",
                            "priority": "normal",
                            "expected_reply_hours": 36,
                            "fallback_assumption": "暂按 08:00-23:00 估计",
                            "meta": {"quick_replies": ["7:30起/23:00睡", "8:00起/23:30睡"]},
                        },
                        {
                            "type": "question",
                            "topic": "canteen",
                            "title": "第二题应被防轰炸护栏拦截",
                            "body": "不应在同一次 Tick 发出第二道提问",
                            "priority": "normal",
                        },
                    ],
                    "actions": [],
                    "unfinished": [],
                    "next_tick_suggestions": ["睡前整合饮食并更新 AI 动态计划"],
                },
            ),
            TrajectoryStep(
                label="pre_sleep_report_and_plan_sync",
                assert_prompt_contains=["食堂鸡胸肉", "番茄鸡蛋面", "7:30 起床"],
                response={
                    "summary": "今日体重 74.8kg，整合 2 条餐饮记录并同步 AI 动态计划与睡前日报",
                    "tickets": [],
                    "actions": [
                        {
                            "kind": "profile_update",
                            "key": "schedule_workday",
                            "value": "07:30-23:00",
                            "confidence": 0.95,
                            "source": "asked",
                        },
                        {
                            "kind": "resolve_ticket",
                            "ticket_id": 1,
                            "resolution": "已写入作息画像",
                        },
                        {
                            "kind": "plan_update",
                            "plan_version": "v1.1",
                            "target_weight": "70.0",
                            "phase_name": "基线观察与稳态起步",
                            "phase_rationale": "近两天从 75.2 降至 74.8kg，蛋白与主食结构均衡，保持温和节奏",
                            "focus_notes": "继续午晚餐适量蛋白+半份主食，保证 23:00 前入睡",
                            "tolerance_kg": 0.7,
                            "ai_summary": "体重稳步下行至 74.8kg，饮食清淡均衡，状态很好",
                            "daily_targets": {"2026-11-22": 74.8, "2026-11-29": 74.3},
                        },
                        {
                            "kind": "daily_report",
                            "report_date": "2026-11-22",
                            "title": "2026-11-22 睡前体重与健康日报",
                            "summary": "今日体重 74.8kg（较昨日 -0.4kg），午晚餐结构均衡，已更新动态计划。",
                            "body_markdown": "## 今日体重\n- 74.8kg (-0.4kg)\n## 今日餐饮\n- 午餐：食堂鸡胸肉+半碗米饭+西兰花\n- 晚餐：番茄鸡蛋面少面+卤蛋",
                            "weight_snapshot": {"latest_kg": 74.8, "delta_from_prev": -0.4, "target_kg": 70.0},
                            "diet_summary": {"count": 2, "highlights": "蛋白质充足、主食克制"},
                            "plan_update": {"phase_name": "基线观察与稳态起步", "plan_version": "v1.1"},
                            "tomorrow_focus": ["明早 7:30 起床后空腹称重", "继续随手发一句午晚饭记录"],
                            "push": True,
                        },
                    ],
                    "unfinished": [],
                    "next_tick_suggestions": ["明早观察体重变化"],
                },
            ),
        ],
        ticks=[
            TrajectoryTickSpec(slot="morning_checkin"),
            TrajectoryTickSpec(
                slot="pre_sleep_report",
                advance_hours=13,
                advance_minutes=15,
                before=user_daytime_activity,
            ),
        ],
        verify=verify,
    )


BUILTIN_SCENARIOS: Dict[str, Callable[[], TrajectoryScenario]] = {
    "onboarding_reply_loop": _scenario_onboarding_reply_loop,
    "fault_injection_and_recovery": _scenario_fault_injection_and_recovery,
    "quiet_hours_and_expiry": _scenario_quiet_hours_and_expiry,
    "canary_circuit_breaker": _scenario_canary_circuit_breaker,
    "health_coach_full_day_loop": _scenario_health_coach_full_day_loop,
}
