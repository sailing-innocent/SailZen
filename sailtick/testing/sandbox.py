# -*- coding: utf-8 -*-
# @file sandbox.py
# @brief Layer 3: 接入真实 LLM API（如 Kimi）的短周期可控沙盒测试引擎
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""Live-LLM Fast-Cycle Sandbox — 真实 API 短唤醒周期可控沙盒测试。

设计要点:
  1. 强隔离：独立临时目录（sailtick.db / handoffs / logs / report）+ 内存态
     SimulatedSailServer，绝不触碰生产数据库、生产票据表或手机推送。
  2. 短周期：支持秒级唤醒间隔（默认 3s）与固定 Tick 数（默认 2~3 次），
     通过 idempotency_suffix 在几秒内连续跑通多个 slot。
  3. 任务简单可控：内置精选轻量场景（quick_ping / stress_override / canary_shadow_live），
     每 Tick 严格限制 token 上限与最大输出长度，并模拟用户自动回复。
  4. 自动质量评估：校验 JSON 协议合规、非降级率、票据节流（<=2）、温和语气守则、
     handoff 交接完整性、耗时与成本统计，并输出 JSON + Markdown 报告。
  5. 友好容错：未配置 Key 或网络/API 阻塞时返回 status='api_blocked' 并清晰报告原因。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from sailtick.canary import CanaryController, CanaryMonitor
from sailtick.config import (
    CanaryConfig,
    LLMConfig,
    LLMProviderConfig,
    SailServerConfig,
    SailTickConfig,
    TickConfig,
)
from sailtick.daemon import SailTickDaemon
from sailtick.llm import LLMGateway
from sailtick.testing.clock import VirtualClock
from sailtick.testing.fake_server import SimulatedSailServer

# 违反温和人设的禁用苛责词汇（用于基础语气护栏检查）
FORBIDDEN_HARSH_TERMS = ("懒惰", "废物", "太胖了", "自律太差", "必须绝食", "严厉警告")


@dataclass
class SandboxConfig:
    """沙盒测试配置。"""

    provider: str = "kimi"
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    scenario: str = "quick_ping"
    wake_interval_seconds: float = 2.0
    max_ticks: int = 2
    per_tick_token_cap: int = 20_000
    work_budget_minutes: int = 5
    workdir: Optional[str] = None
    keep_artifacts: bool = False
    http_transport: Optional[httpx.AsyncBaseTransport] = None  # 供单测注入 mock transport


@dataclass
class SandboxReport:
    """沙盒测试报告。"""

    status: str  # passed | failed | api_blocked
    scenario: str
    provider: str
    model: str
    total_duration_sec: float
    ticks: List[Dict[str, Any]] = field(default_factory=list)
    evaluations: List[Dict[str, Any]] = field(default_factory=list)
    tickets_created: List[Dict[str, Any]] = field(default_factory=list)
    monitor_snapshot: Dict[str, Any] = field(default_factory=dict)
    report_dir: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "scenario": self.scenario,
            "provider": self.provider,
            "model": self.model,
            "total_duration_sec": round(self.total_duration_sec, 3),
            "ticks": self.ticks,
            "evaluations": self.evaluations,
            "tickets_created": self.tickets_created,
            "monitor_snapshot": self.monitor_snapshot,
            "report_dir": self.report_dir,
            "error": self.error,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# SailTick Sandbox Report — {self.scenario}",
            "",
            f"- **Status**: `{self.status}`",
            f"- **Provider / Model**: `{self.provider}` / `{self.model}`",
            f"- **Duration**: `{self.total_duration_sec:.2f}s`",
            f"- **Ticks Executed**: `{len(self.ticks)}`",
            f"- **Tickets Created**: `{len(self.tickets_created)}`",
        ]
        if self.error:
            lines.append(f"- **Error**: `{self.error}`")
        lines.append("")
        lines.append("## Evaluation Checks")
        for ev in self.evaluations:
            mark = "PASS" if ev["passed"] else "FAIL"
            lines.append(f"- [{mark}] **{ev['name']}**: {ev['detail']}")
        lines.append("")
        lines.append("## Tick Trace")
        for i, t in enumerate(self.ticks, 1):
            lines.append(
                f"### Tick {i}: `{t.get('slot')}` (mode={t.get('mode')}, "
                f"source={t.get('plan_source')}, tokens={t.get('cost_tokens', 0)}, "
                f"dur={t.get('duration_sec', 0):.2f}s)"
            )
            lines.append(f"- Summary: {t.get('summary', '')}")
            lines.append(f"- Emitted tickets: {t.get('emitted_count', 0)}, Shadow tickets: {t.get('shadow_count', 0)}")
            lines.append(f"- Handoff: `{t.get('handoff_path', '')}`")
        return "\n".join(lines) + "\n"


def _read_dotenv_vars(env_path: Path) -> Dict[str, str]:
    """安全解析 .env 文件的键值对（绝不打印敏感内容）。"""
    out: Dict[str, str] = {}
    if not env_path.exists():
        return out
    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v:
                out[k] = v
    except OSError:
        pass
    return out


def resolve_live_credentials(
    provider: str = "kimi",
    repo_root: Optional[Path] = None,
    explicit_key: str = "",
    explicit_model: str = "",
    explicit_base_url: str = "",
) -> Tuple[str, str, str]:
    """解析真实 API 凭证：(api_key, model, base_url)。

    优先级: 显式传参 > 进程环境变量 > .env.dev（仅作兜底）。
    """
    root = repo_root or Path.cwd()
    dotenv_vars = _read_dotenv_vars(root / ".env.dev")

    def get_var(*names: str) -> str:
        for name in names:
            if val := os.environ.get(name):
                return val.strip()
        for name in names:
            if val := dotenv_vars.get(name):
                return val.strip()
        return ""

    if provider == "kimi":
        api_key = explicit_key or get_var("KIMI_API_KEY", "MOONSHOT_API_KEY")
        # 过滤模板占位符（如 sk-xxx）
        if api_key.startswith("sk-xxx"):
            api_key = ""
        is_coding_key = api_key.startswith("sk-kimi-")
        if is_coding_key:
            model = explicit_model or os.environ.get("KIMI_MODEL") or "kimi-for-coding"
            base_url = (
                explicit_base_url
                or os.environ.get("KIMI_API_BASE")
                or "https://api.kimi.com/coding/v1"
            )
        else:
            model = explicit_model or get_var("KIMI_MODEL", "MOONSHOT_MODEL") or "kimi-k2.5"
            base_url = (
                explicit_base_url
                or get_var("KIMI_API_BASE", "MOONSHOT_API_BASE")
                or "https://api.moonshot.cn/v1"
            )
        return api_key, model, base_url

    if provider == "deepseek":
        api_key = explicit_key or get_var("DEEPSEEK_API_KEY")
        model = explicit_model or get_var("DEEPSEEK_MODEL") or "deepseek-chat"
        base_url = explicit_base_url or get_var("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"
        return api_key, model, base_url

    api_key = explicit_key or get_var(f"{provider.upper()}_API_KEY")
    model = explicit_model or get_var(f"{provider.upper()}_MODEL")
    base_url = explicit_base_url or get_var(f"{provider.upper()}_API_BASE")
    return api_key, model, base_url


class SandboxEvaluator:
    """对沙盒真实 LLM 产出进行结构化质量评估。"""

    @staticmethod
    def evaluate(ticks: List[Dict[str, Any]], tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        checks: List[Dict[str, Any]] = []

        # 1. 所有 Tick 完成
        all_done = bool(ticks) and all(t.get("status") == "completed" for t in ticks)
        checks.append(
            {
                "name": "all_ticks_completed",
                "passed": all_done,
                "detail": f"{sum(1 for t in ticks if t.get('status') == 'completed')}/{len(ticks)} completed",
            }
        )

        # 2. 真实 LLM 非降级率（确保 JSON 解析与契约校验全部过关）
        llm_driven = sum(1 for t in ticks if t.get("plan_source") == "llm")
        checks.append(
            {
                "name": "llm_json_contract_passed",
                "passed": bool(ticks) and llm_driven == len(ticks),
                "detail": f"{llm_driven}/{len(ticks)} ticks used real LLM valid JSON",
            }
        )

        # 3. 票据节流硬约束（单 Tick <= 2 张）
        throttle_ok = all(
            (t.get("emitted_count", 0) <= 2 and t.get("shadow_count", 0) <= 2) for t in ticks
        )
        checks.append(
            {
                "name": "ticket_throttle_enforced",
                "passed": throttle_ok,
                "detail": "every tick emitted <= 2 tickets",
            }
        )

        # 4. Handoff 连续性与非空摘要
        handoffs_ok = all(
            bool(t.get("handoff_path")) and os.path.exists(t["handoff_path"]) and bool(t.get("summary"))
            for t in ticks
        )
        checks.append(
            {
                "name": "handoff_continuity",
                "passed": handoffs_ok,
                "detail": "all ticks produced non-empty handoff markdown files",
            }
        )

        # 5. 温和人设语气护栏（无苛责词、无过度感叹号施压）
        texts = [t.get("summary", "") for t in ticks] + [
            f"{tk.get('title', '')} {tk.get('body', '')}" for tk in tickets
        ]
        joined = "\n".join(texts)
        hits = [term for term in FORBIDDEN_HARSH_TERMS if term in joined]
        exclamations = len(re.findall(r"[!！]{2,}", joined))
        tone_ok = not hits and exclamations == 0
        checks.append(
            {
                "name": "gentle_coach_tone_guard",
                "passed": tone_ok,
                "detail": "clean" if tone_ok else f"harsh_terms={hits}, multi_exclam={exclamations}",
            }
        )

        return checks


SANDBOX_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "quick_ping": {
        "description": "最小可控闭环：2 次短周期 Tick（早间建基线 -> 模拟用户回复 74.2kg -> 午间跟进）",
        "slots": ["morning_checkin", "midday_checkin"],
        "modes": ["live", "live"],
        "seed_weights": [("2026-11-08", 74.6), ("2026-11-09", 74.4)],
        "seed_sleep": [{"date": "2026-11-09", "hours": 7.2}],
        "auto_reply_after_tick1": "今早体重 74.2kg，昨晚睡得还行，中午准备吃公司食堂。",
    },
    "stress_override": {
        "description": "压力优先场景：注入连续熬夜/高压力信号，验证真实 LLM 温和减负不施压",
        "slots": ["morning_checkin", "evening_review"],
        "modes": ["live", "live"],
        "seed_weights": [("2026-11-08", 74.2), ("2026-11-09", 74.7)],
        "seed_sleep": [{"date": "2026-11-08", "hours": 4.5}, {"date": "2026-11-09", "hours": 4.8}],
        "seed_mood": [{"date": "2026-11-09", "mood": "stressed", "note": "连续加班到凌晨，很疲惫"}],
        "auto_reply_after_tick1": "最近加班太狠了，昨晚只睡了不到 5 小时，情绪很低落。",
    },
    "canary_shadow_live": {
        "description": "真实 API 灰度切换演练：Tick 1 跑 shadow（零副作用）-> 一键切换 canary 跑 Tick 2（限流 1 张无推送）",
        "slots": ["morning_checkin", "midday_checkin"],
        "modes": ["shadow", "canary"],
        "seed_weights": [("2026-11-09", 73.9)],
        "seed_sleep": [{"date": "2026-11-09", "hours": 7.0}],
        "auto_reply_after_tick1": "",
    },
}


class LiveSandboxRunner:
    """短周期可控真实 API 沙盒测试运行器。"""

    def __init__(self, config: SandboxConfig):
        self.config = config

    async def probe_api(self, llm: LLMGateway) -> Tuple[bool, str]:
        """轻量探活：最小 token 检测 API 连通性与鉴权（给推理模型预留 reasoning 空间）。"""
        try:
            resp = await llm.chat(
                '回复 JSON: {"ok": true}',
                expect_json=True,
                max_tokens=512,
            )
            if not resp.content:
                return False, "empty response from LLM API"
            return True, f"ok ({resp.latency_ms:.0f}ms)"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    async def run(self) -> SandboxReport:
        t_start = time.perf_counter()
        scenario_def = SANDBOX_SCENARIOS.get(self.config.scenario)
        if scenario_def is None:
            return SandboxReport(
                status="failed",
                scenario=self.config.scenario,
                provider=self.config.provider,
                model=self.config.model,
                total_duration_sec=0.0,
                error=f"Unknown sandbox scenario: {self.config.scenario}. Available: {list(SANDBOX_SCENARIOS)}",
            )

        api_key, model, base_url = resolve_live_credentials(
            provider=self.config.provider,
            explicit_key=self.config.api_key,
            explicit_model=self.config.model,
            explicit_base_url=self.config.base_url,
        )
        if not api_key and self.config.http_transport is None:
            return SandboxReport(
                status="api_blocked",
                scenario=self.config.scenario,
                provider=self.config.provider,
                model=model,
                total_duration_sec=time.perf_counter() - t_start,
                error=(
                    f"No API key found for provider '{self.config.provider}' "
                    "(set KIMI_API_KEY / MOONSHOT_API_KEY or pass --api-key)"
                ),
            )

        temp_dir: Optional[tempfile.TemporaryDirectory] = None
        if self.config.workdir:
            base = Path(self.config.workdir)
            base.mkdir(parents=True, exist_ok=True)
        elif self.config.keep_artifacts:
            base = Path(tempfile.mkdtemp(prefix=f"sailtick_sandbox_{self.config.scenario}_"))
        else:
            temp_dir = tempfile.TemporaryDirectory(prefix=f"sailtick_sandbox_{self.config.scenario}_")
            base = Path(temp_dir.name)

        clock = VirtualClock(datetime(2026, 11, 9, 6, 0, 0))
        server = SimulatedSailServer(clock=clock)
        for d_str, w_val in scenario_def.get("seed_weights", []):
            server.seed_weight(d_str, w_val)
        for item in scenario_def.get("seed_sleep", []):
            server.seed_signal("sleep", item)
        for item in scenario_def.get("seed_mood", []):
            server.seed_signal("mood", item)

        cfg = SailTickConfig(
            name=f"sandbox-{self.config.scenario}",
            data_dir=str(base / "data"),
            db_path=str(base / "db" / "sailtick.db"),
            log_dir=str(base / "logs"),
            api_port=19079,
            sail_server=SailServerConfig(api_base="http://simulated-sail-server/api/v1"),
            tick=TickConfig(
                hours=[0, 6, 12, 18],
                work_budget_minutes=self.config.work_budget_minutes,
            ),
            llm=LLMConfig(
                default=self.config.provider,
                per_tick_token_cap=self.config.per_tick_token_cap,
                daily_token_cap=self.config.per_tick_token_cap * 5,
                providers={
                    self.config.provider: LLMProviderConfig(
                        api_key=api_key or "mock-sandbox-key",
                        model=model,
                        base_url=base_url,
                    )
                },
            ),
            canary=CanaryConfig(mode=scenario_def["modes"][0]),
            config_dir=os.getcwd(),
        )

        daemon = SailTickDaemon(cfg)
        if self.config.http_transport is not None:
            daemon.llm._clients[self.config.provider] = httpx.AsyncClient(
                transport=self.config.http_transport, timeout=30.0
            )
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
        daemon.engine.inbox = daemon.inbox
        daemon.engine.scanner = daemon.scanner
        daemon.engine.notifier = daemon.notifier
        daemon.engine.canary = daemon.canary
        daemon.engine._clock = clock

        await daemon.db.connect()
        await daemon.canary.load()

        # 初始化最小画像与计划 v0.1
        await daemon.memory.set_profile("goal_weight", "70kg", confidence=1.0, source="asked")
        await daemon.db.create_plan(
            "v0.1", "70kg", "# 沙盒测试计划 v0.1\n目标 70kg，温和渐进。", "sandbox init", active=True
        )

        try:
            # 1. 先探活 API（若网络或密钥阻塞，立即优雅降级为 api_blocked）
            probe_ok, probe_detail = await self.probe_api(daemon.llm)
            if not probe_ok:
                return SandboxReport(
                    status="api_blocked",
                    scenario=self.config.scenario,
                    provider=self.config.provider,
                    model=model,
                    total_duration_sec=time.perf_counter() - t_start,
                    report_dir=str(base),
                    error=f"LLM API probe failed: {probe_detail}",
                )

            slots = scenario_def["slots"][: max(1, self.config.max_ticks)]
            modes = scenario_def["modes"]
            tick_traces: List[Dict[str, Any]] = []

            for idx, slot in enumerate(slots):
                target_mode = modes[min(idx, len(modes) - 1)]
                if daemon.canary.mode != target_mode:
                    await daemon.canary.switch(
                        target_mode,
                        reason=f"sandbox step {idx + 1}",
                        actor="sandbox",
                        ticket_title_prefix="[Sandbox] " if target_mode == "canary" else "",
                    )

                if idx > 0:
                    if self.config.wake_interval_seconds > 0:
                        await asyncio.sleep(self.config.wake_interval_seconds)
                    clock.advance(hours=6)
                    if idx == 1 and scenario_def.get("auto_reply_after_tick1"):
                        server.simulate_user_reply_latest_pending(scenario_def["auto_reply_after_tick1"])

                t0 = time.perf_counter()
                result = await daemon.engine.run_tick(
                    slot,
                    tick_date=clock().strftime("%Y-%m-%d"),
                    idempotency_suffix=f"sb{idx + 1}",
                )
                dur = time.perf_counter() - t0
                tick_traces.append(
                    {
                        "index": idx + 1,
                        "slot": slot,
                        "mode": result.get("mode"),
                        "status": result.get("status"),
                        "plan_source": result.get("plan_source"),
                        "summary": (result.get("plan") or {}).get("summary", ""),
                        "emitted_count": len(result.get("emitted", [])),
                        "shadow_count": len(result.get("shadow_emitted", [])),
                        "handoff_path": result.get("handoff_path", ""),
                        "cost_tokens": result.get("cost_tokens", 0),
                        "duration_sec": round(dur, 3),
                    }
                )

            evaluations = SandboxEvaluator.evaluate(tick_traces, server.tickets)
            snap = await daemon.get_monitor_snapshot()
            all_passed = all(e["passed"] for e in evaluations)

            report = SandboxReport(
                status="passed" if all_passed else "failed",
                scenario=self.config.scenario,
                provider=self.config.provider,
                model=model,
                total_duration_sec=time.perf_counter() - t_start,
                ticks=tick_traces,
                evaluations=evaluations,
                tickets_created=list(server.tickets),
                monitor_snapshot=snap,
                report_dir=str(base),
            )

            # 持久化报告（如设置了 workdir 或 keep_artifacts）
            if self.config.workdir or self.config.keep_artifacts:
                (base / "sandbox_report.json").write_text(
                    json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
                (base / "sandbox_report.md").write_text(report.to_markdown(), encoding="utf-8")

            return report
        finally:
            await daemon.llm.close()
            await daemon.inbox.close()
            await daemon.scanner.close()
            await daemon.db.close()
            if temp_dir is not None:
                temp_dir.cleanup()
