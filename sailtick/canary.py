# -*- coding: utf-8 -*-
# @file canary.py
# @brief SailTick 一键开关 / 灰度控制 / 熔断降级 / 运行监控体系
# @author sailing-innocent
# @date 2026-11-21
# @version 1.0
# ---------------------------------
"""SailTick 灰度发布、一键开关与可观测监控。

运行模式（四态渐进灰度）:
  off    紧急总闸（Kill-switch）：跳过所有 Tick，不调用 LLM，不发票据不推送
  shadow 影子模式（暗跑 / Dry-run）：完整执行 SCAN + PLAN（可接真实 LLM），
         WORK 阶段仅记录“将要创建的票据/动作”，不产生任何外部副作用
  canary 灰度模式（受控放量）：允许落库票据，但默认限流（1 张/Tick）、
         关闭手机强推、禁用自我开发、可选标题前缀与 slot 白名单
  live   全量生产模式：按正式配置运行

熔断自动降级:
  当连续失败（Tick 异常或 LLM 异常降级）达到阈值 auto_downgrade_failures 时，
  canary/live 自动降级为 auto_downgrade_target（默认 shadow），并发出告警。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from sailtick.config import CanaryConfig
from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)

VALID_MODES = ("off", "shadow", "canary", "live")
RUNTIME_STATE_KEY = "canary_state"

MODE_PRESETS: Dict[str, Dict[str, Any]] = {
    "off": {
        "allow_llm": False,
        "allow_ticket_create": False,
        "allow_push": False,
        "allow_self_dev": False,
        "max_tickets_per_tick": 0,
    },
    "shadow": {
        "allow_llm": True,
        "allow_ticket_create": False,
        "allow_push": False,
        "allow_self_dev": False,
        "max_tickets_per_tick": 2,
    },
    "canary": {
        "allow_llm": True,
        "allow_ticket_create": True,
        "allow_push": False,
        "allow_self_dev": False,
        "max_tickets_per_tick": 1,
    },
    "live": {
        "allow_llm": True,
        "allow_ticket_create": True,
        "allow_push": True,
        "allow_self_dev": True,
        "max_tickets_per_tick": 2,
    },
}


class CanaryController:
    """SailTick 一键开关与灰度策略控制器（状态持久化于 st_runtime_state）。"""

    def __init__(
        self,
        config: CanaryConfig,
        db: TickDatabase,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self._clock = clock
        self._state: Dict[str, Any] = self._initial_state(config)
        self._loaded = False

    def _initial_state(self, cfg: CanaryConfig) -> Dict[str, Any]:
        mode = cfg.mode if cfg.mode in VALID_MODES else "live"
        preset = dict(MODE_PRESETS[mode])
        # live 模式使用配置值；其余模式默认按安全预设，同时尊重显式配置覆盖
        if mode == "live":
            max_tickets = cfg.max_tickets_per_tick
            allow_push = cfg.allow_push
            allow_self_dev = cfg.allow_self_dev
        elif mode == "canary":
            max_tickets = min(cfg.max_tickets_per_tick, preset["max_tickets_per_tick"])
            allow_push = False if cfg.allow_push is True else cfg.allow_push
            allow_self_dev = False if cfg.allow_self_dev is True else cfg.allow_self_dev
        else:
            max_tickets = preset["max_tickets_per_tick"]
            allow_push = preset["allow_push"]
            allow_self_dev = preset["allow_self_dev"]

        return {
            "mode": mode,
            "allow_llm": preset["allow_llm"],
            "allow_ticket_create": preset["allow_ticket_create"],
            "allow_push": allow_push,
            "allow_self_dev": allow_self_dev,
            "max_tickets_per_tick": max_tickets,
            "allowed_slots": list(cfg.allowed_slots),
            "ticket_title_prefix": cfg.ticket_title_prefix,
            "auto_downgrade_failures": cfg.auto_downgrade_failures,
            "auto_downgrade_target": cfg.auto_downgrade_target,
            "consecutive_failures": 0,
            "circuit_breaker_open": False,
            "last_downgrade_reason": "",
            "last_switch_at": None,
            "last_switch_reason": "init",
            "last_switch_actor": "config",
            "history": [],
        }

    # ── 持久化加载/保存 ────────────────────────────────────────────────

    async def load(self) -> Dict[str, Any]:
        """从隔离 DB 恢复上次开关状态（重启不丢失开关）。"""
        saved = await self.db.get_runtime_state(RUNTIME_STATE_KEY)
        if isinstance(saved, dict) and saved.get("mode") in VALID_MODES:
            merged = dict(self._state)
            merged.update(saved)
            self._state = merged
        self._loaded = True
        return self.get_status()

    async def _persist(self) -> None:
        if getattr(self.db, "_engine", None) is not None:
            await self.db.set_runtime_state(RUNTIME_STATE_KEY, self._state)

    # ── 查询 ──────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return str(self._state.get("mode", "live"))

    def effective_policy(self) -> Dict[str, Any]:
        """返回当前生效的策略视图。"""
        mode = self.mode
        preset = MODE_PRESETS.get(mode, MODE_PRESETS["live"])
        return {
            "mode": mode,
            "allow_llm": bool(self._state.get("allow_llm", preset["allow_llm"])),
            "allow_ticket_create": bool(
                self._state.get("allow_ticket_create", preset["allow_ticket_create"])
            ),
            "allow_push": bool(self._state.get("allow_push", preset["allow_push"])),
            "allow_self_dev": bool(self._state.get("allow_self_dev", preset["allow_self_dev"])),
            "max_tickets_per_tick": int(
                self._state.get("max_tickets_per_tick", preset["max_tickets_per_tick"])
            ),
            "allowed_slots": list(self._state.get("allowed_slots") or []),
            "ticket_title_prefix": str(self._state.get("ticket_title_prefix") or ""),
            "auto_downgrade_failures": int(self._state.get("auto_downgrade_failures", 3)),
            "auto_downgrade_target": str(self._state.get("auto_downgrade_target", "shadow")),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "policy": self.effective_policy(),
            "consecutive_failures": int(self._state.get("consecutive_failures", 0)),
            "circuit_breaker_open": bool(self._state.get("circuit_breaker_open", False)),
            "last_downgrade_reason": self._state.get("last_downgrade_reason", ""),
            "last_switch_at": self._state.get("last_switch_at"),
            "last_switch_reason": self._state.get("last_switch_reason", ""),
            "last_switch_actor": self._state.get("last_switch_actor", ""),
            "history": list(self._state.get("history", []))[-20:],
        }

    def should_run_slot(self, slot: str) -> Tuple[bool, str]:
        """判断当前策略是否允许执行指定 slot。"""
        if self.mode == "off":
            return False, "mode_off"
        allowed = self._state.get("allowed_slots") or []
        if allowed and slot not in allowed:
            return False, f"slot_not_allowed:{slot}"
        return True, ""

    # ── 一键开关操作 ──────────────────────────────────────────────────

    async def switch(
        self,
        mode: str,
        reason: str = "",
        actor: str = "manual",
        **overrides: Any,
    ) -> Dict[str, Any]:
        """一键切换模式（支持附带细粒度开关覆盖）。"""
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid canary mode {mode!r}, expected one of {VALID_MODES}")

        prev_mode = self.mode
        preset = MODE_PRESETS[mode]
        now_iso = self._clock().isoformat()

        self._state["mode"] = mode
        self._state["allow_llm"] = preset["allow_llm"]
        self._state["allow_ticket_create"] = preset["allow_ticket_create"]
        self._state["allow_push"] = preset["allow_push"]
        self._state["allow_self_dev"] = preset["allow_self_dev"]
        self._state["max_tickets_per_tick"] = preset["max_tickets_per_tick"]

        # 显式细粒度覆盖（过滤 None）
        allowed_override_keys = {
            "allow_llm",
            "allow_ticket_create",
            "allow_push",
            "allow_self_dev",
            "max_tickets_per_tick",
            "allowed_slots",
            "ticket_title_prefix",
            "auto_downgrade_failures",
            "auto_downgrade_target",
        }
        for k, v in overrides.items():
            if k in allowed_override_keys and v is not None:
                self._state[k] = v

        # 手动恢复到 canary/live 时清除熔断标记
        if actor != "circuit_breaker" and mode in ("canary", "live"):
            self._state["circuit_breaker_open"] = False
            self._state["consecutive_failures"] = 0

        self._state["last_switch_at"] = now_iso
        self._state["last_switch_reason"] = reason or f"switch {prev_mode}->{mode}"
        self._state["last_switch_actor"] = actor
        history = list(self._state.get("history", []))
        history.append(
            {
                "at": now_iso,
                "from": prev_mode,
                "to": mode,
                "reason": self._state["last_switch_reason"],
                "actor": actor,
            }
        )
        self._state["history"] = history[-20:]

        await self._persist()
        if getattr(self.db, "_engine", None) is not None:
            await self.db.create_episode(
                None,
                "canary_switch",
                {
                    "from": prev_mode,
                    "to": mode,
                    "reason": self._state["last_switch_reason"],
                    "actor": actor,
                },
            )
        logger.warning(
            "Canary switch: %s -> %s (actor=%s reason=%s)",
            prev_mode,
            mode,
            actor,
            self._state["last_switch_reason"],
        )
        return self.get_status()

    async def kill(self, reason: str = "emergency kill-switch", actor: str = "manual") -> Dict[str, Any]:
        """紧急一键停机（切换至 off）。"""
        return await self.switch("off", reason=reason, actor=actor)

    async def resume(
        self,
        target_mode: str = "canary",
        reason: str = "manual resume",
        actor: str = "manual",
        **overrides: Any,
    ) -> Dict[str, Any]:
        """清除熔断并恢复到目标模式（默认恢复到更安全的 canary）。"""
        if target_mode not in ("shadow", "canary", "live"):
            raise ValueError(f"resume target must be shadow|canary|live, got {target_mode!r}")
        self._state["circuit_breaker_open"] = False
        self._state["consecutive_failures"] = 0
        self._state["last_downgrade_reason"] = ""
        return await self.switch(target_mode, reason=reason, actor=actor, **overrides)

    # ── 熔断器记录 ────────────────────────────────────────────────────

    async def record_tick_outcome(
        self,
        success: bool,
        plan_source: str,
        tick_id: str = "",
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """记录 Tick 结果并在连续失败超阈值时自动熔断降级。"""
        is_failure = (not success) or (plan_source == "fallback_error")
        if is_failure:
            self._state["consecutive_failures"] = int(self._state.get("consecutive_failures", 0)) + 1
        elif success and plan_source == "llm":
            self._state["consecutive_failures"] = 0

        threshold = int(self._state.get("auto_downgrade_failures", 3))
        target = str(self._state.get("auto_downgrade_target", "shadow"))
        if target not in ("off", "shadow"):
            target = "shadow"

        downgraded: Optional[Dict[str, Any]] = None
        if (
            is_failure
            and threshold > 0
            and self._state["consecutive_failures"] >= threshold
            and self.mode in ("canary", "live")
        ):
            reason = (
                f"circuit_breaker: {self._state['consecutive_failures']} consecutive failures "
                f"(last_tick={tick_id}, plan_source={plan_source}, error={error or 'llm_fallback'})"
            )
            self._state["circuit_breaker_open"] = True
            self._state["last_downgrade_reason"] = reason
            downgraded = await self.switch(target, reason=reason, actor="circuit_breaker")
            if getattr(self.db, "_engine", None) is not None:
                await self.db.create_episode(
                    tick_id or None,
                    "canary_downgrade",
                    {
                        "target": target,
                        "consecutive_failures": self._state["consecutive_failures"],
                        "reason": reason,
                    },
                )
        else:
            await self._persist()
        return downgraded


class CanaryMonitor:
    """SailTick 运行监控与灰度健康评估。"""

    def __init__(
        self,
        db: TickDatabase,
        canary: CanaryController,
        state: Any,
        daily_token_cap: int = 1_000_000,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.db = db
        self.canary = canary
        self.state = state
        self.daily_token_cap = daily_token_cap
        self._clock = clock

    async def snapshot(self, window_ticks: int = 50, active_tick_id: Optional[str] = None) -> Dict[str, Any]:
        """计算完整监控快照（指标 + 告警 + 综合健康判定）。"""
        ticks = await self.db.list_ticks(limit=window_ticks)
        episodes = await self.db.list_episodes(limit=300)
        handoffs = await self.db.list_handoffs(limit=window_ticks)
        today = self._clock().strftime("%Y-%m-%d")
        daily_tokens = await self.db.sum_cost_today(today=today)
        daily_cost_usd = await self.db.sum_cost_usd_today(today=today)
        canary_status = self.canary.get_status()
        deps = self.state.snapshot() if self.state is not None else {}

        total = len(ticks)
        completed = sum(1 for t in ticks if t["state"] == "completed")
        failed = sum(1 for t in ticks if t["state"] == "failed")
        skipped = sum(1 for t in ticks if t["state"] == "skipped")
        interrupted = sum(1 for t in ticks if t["state"] == "interrupted")
        running_stale = [
            t["id"]
            for t in ticks
            if t["state"] == "running" and t["id"] != active_tick_id
        ]

        # 计算平均耗时
        durations: List[float] = []
        for t in ticks:
            if t.get("started_at") and t.get("ended_at"):
                try:
                    dt = (
                        datetime.fromisoformat(t["ended_at"])
                        - datetime.fromisoformat(t["started_at"])
                    ).total_seconds()
                    if dt >= 0:
                        durations.append(dt)
                except ValueError:
                    pass

        # 统计 PLAN 来源、票据产出与影子模拟数
        plan_eps = [e for e in episodes if e["kind"] == "plan" and isinstance(e.get("content"), dict)]
        llm_plans = sum(1 for e in plan_eps if e["content"].get("source") == "llm")
        fallback_plans = sum(
            1 for e in plan_eps if str(e["content"].get("source", "")).startswith("fallback")
        )
        fallback_errors = sum(
            1 for e in plan_eps if e["content"].get("source") == "fallback_error"
        )
        total_plans = llm_plans + fallback_plans
        fallback_rate = round(fallback_plans / total_plans, 4) if total_plans else 0.0

        work_eps = [e for e in episodes if e["kind"] == "work" and isinstance(e.get("content"), dict)]
        tickets_emitted = sum(1 for e in work_eps if e["content"].get("ticket_created") is not None)
        shadow_eps = [
            e for e in episodes if e["kind"] == "shadow_work" and isinstance(e.get("content"), dict)
        ]
        shadow_tickets = sum(int(e["content"].get("tickets_simulated", 0)) for e in shadow_eps)

        # handoff 覆盖率（已完成的 tick 中存在有效 handoff 文件的比例）
        handoff_by_tick = {h["tick_id"]: h["path"] for h in handoffs}
        completed_ids = [t["id"] for t in ticks if t["state"] == "completed"]
        valid_handoffs = sum(
            1
            for tid in completed_ids
            if tid in handoff_by_tick and os.path.exists(handoff_by_tick[tid])
        )
        handoff_coverage = round(valid_handoffs / len(completed_ids), 4) if completed_ids else 1.0

        executed = completed + failed
        tick_success_rate = round(completed / executed, 4) if executed else 1.0
        token_util_pct = (
            round((daily_tokens / self.daily_token_cap) * 100.0, 2)
            if self.daily_token_cap > 0
            else 0.0
        )

        metrics = {
            "window_ticks": window_ticks,
            "total_ticks": total,
            "completed_ticks": completed,
            "failed_ticks": failed,
            "skipped_ticks": skipped,
            "interrupted_ticks": interrupted,
            "stale_running_ticks": len(running_stale),
            "tick_success_rate": tick_success_rate,
            "llm_plan_count": llm_plans,
            "fallback_plan_count": fallback_plans,
            "fallback_error_count": fallback_errors,
            "llm_fallback_rate": fallback_rate,
            "avg_tick_duration_sec": round(sum(durations) / len(durations), 3) if durations else 0.0,
            "daily_tokens": daily_tokens,
            "daily_token_cap": self.daily_token_cap,
            "daily_token_utilization_pct": token_util_pct,
            "daily_cost_usd": round(daily_cost_usd, 6),
            "tickets_emitted_total": tickets_emitted,
            "shadow_tickets_simulated": shadow_tickets,
            "handoff_coverage_rate": handoff_coverage,
            "consecutive_failures": canary_status["consecutive_failures"],
        }

        alerts: List[Dict[str, str]] = []
        if canary_status["circuit_breaker_open"]:
            alerts.append(
                {
                    "level": "critical",
                    "code": "CIRCUIT_BREAKER_OPEN",
                    "message": canary_status["last_downgrade_reason"] or "自动熔断已触发并降级",
                }
            )
        if canary_status["mode"] == "off":
            alerts.append(
                {
                    "level": "info",
                    "code": "MODE_PAUSED",
                    "message": f"SailTick 处于 off 总闸关闭态（{canary_status['last_switch_reason']}）",
                }
            )
        if total_plans >= 3 and fallback_rate >= 0.7:
            alerts.append(
                {
                    "level": "critical",
                    "code": "HIGH_FALLBACK_RATE",
                    "message": f"LLM 降级率过高: {fallback_rate * 100:.1f}% ({fallback_plans}/{total_plans})",
                }
            )
        elif total_plans >= 3 and fallback_rate >= 0.3:
            alerts.append(
                {
                    "level": "warning",
                    "code": "HIGH_FALLBACK_RATE",
                    "message": f"LLM 降级率偏高: {fallback_rate * 100:.1f}% ({fallback_plans}/{total_plans})",
                }
            )
        if executed >= 3 and tick_success_rate < 0.7:
            alerts.append(
                {
                    "level": "critical",
                    "code": "HIGH_TICK_FAILURE_RATE",
                    "message": f"Tick 成功率偏低: {tick_success_rate * 100:.1f}% ({completed}/{executed})",
                }
            )
        if token_util_pct >= 100.0:
            alerts.append(
                {
                    "level": "critical",
                    "code": "TOKEN_BUDGET_EXCEEDED",
                    "message": f"今日 Token 已超上限: {daily_tokens}/{self.daily_token_cap}",
                }
            )
        elif token_util_pct >= 80.0:
            alerts.append(
                {
                    "level": "warning",
                    "code": "TOKEN_BUDGET_HIGH",
                    "message": f"今日 Token 消耗已达 {token_util_pct:.1f}%",
                }
            )
        if running_stale:
            alerts.append(
                {
                    "level": "warning",
                    "code": "STALE_RUNNING_TICKS",
                    "message": f"存在 {len(running_stale)} 个残留 running 状态 Tick",
                }
            )
        for dep_name, dep_info in deps.items():
            if dep_info.get("status") == "down":
                alerts.append(
                    {
                        "level": "warning",
                        "code": f"DEPENDENCY_DOWN_{dep_name.upper()}",
                        "message": f"依赖 {dep_name} 状态异常 (down)",
                    }
                )

        levels = {a["level"] for a in alerts}
        if "critical" in levels:
            overall = "critical"
        elif canary_status["mode"] == "off":
            overall = "paused"
        elif "warning" in levels:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "timestamp": self._clock().isoformat(),
            "overall_health": overall,
            "canary": canary_status,
            "metrics": metrics,
            "deps": deps,
            "alerts": alerts,
        }

    @staticmethod
    def format_report(snap: Dict[str, Any]) -> str:
        """格式化终端监控简报。"""
        c = snap["canary"]
        m = snap["metrics"]
        p = c["policy"]
        lines = [
            "== SailTick Monitor ==",
            f"health: {snap['overall_health']} | mode: {c['mode']} | circuit_breaker: "
            f"{'OPEN' if c['circuit_breaker_open'] else 'closed'} (consecutive_failures={c['consecutive_failures']})",
            f"policy: llm={p['allow_llm']} ticket={p['allow_ticket_create']} "
            f"max_tickets={p['max_tickets_per_tick']} push={p['allow_push']} self_dev={p['allow_self_dev']}",
            f"ticks: total={m['total_ticks']} ok={m['completed_ticks']} failed={m['failed_ticks']} "
            f"success_rate={m['tick_success_rate']*100:.1f}% avg_dur={m['avg_tick_duration_sec']}s",
            f"llm: llm_plans={m['llm_plan_count']} fallback={m['fallback_plan_count']} "
            f"fallback_rate={m['llm_fallback_rate']*100:.1f}% tokens_today={m['daily_tokens']}/{m['daily_token_cap']} "
            f"({m['daily_token_utilization_pct']}%) usd=${m['daily_cost_usd']:.4f}",
            f"artifacts: emitted_tickets={m['tickets_emitted_total']} shadow_tickets={m['shadow_tickets_simulated']} "
            f"handoff_coverage={m['handoff_coverage_rate']*100:.1f}%",
        ]
        if snap["alerts"]:
            lines.append("alerts:")
            for a in snap["alerts"]:
                lines.append(f"  [{a['level'].upper()}] {a['code']}: {a['message']}")
        else:
            lines.append("alerts: none")
        return "\n".join(lines)
