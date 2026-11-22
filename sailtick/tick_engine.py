# -*- coding: utf-8 -*-
# @file tick_engine.py
# @brief TickEngine — SLEEP→WAKE→SCAN→PLAN→WORK→HANDOFF 状态机
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""TickEngine — SailTick 核心。

状态机（设计文档 §3）:
  WAKE   建 tick 实例（幂等键 slot:date）、加载 handoff、LLM begin_tick
  SCAN   依赖健康检查 + 数据扫描 + 票据收件箱同步
  PLAN   LLM 生成本窗口计划（超预算/不可用 → 规则模板降级）
  WORK   执行计划（建票据/写记忆）；硬截止 = 唤醒 + work_budget
  HANDOFF 写交接文档、压缩记忆、记录成本

上下文组装（设计文档 §4）: system prompt + 计划 + handoff + 记忆 + 数据包 + 待回票据。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from sailtick.canary import CanaryController
from sailtick.config import SailTickConfig
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
from sailtick.handoff import HandoffDoc, HandoffManager
from sailtick.inbox import TicketInbox
from sailtick.llm import LLMGateway
from sailtick.memory import AgentMemory
from sailtick.notify import NotificationEngine
from sailtick.state import DependencyState

logger = logging.getLogger(__name__)

# 无 LLM 时的规则模板（设计文档 §11 LLM 降级）
FALLBACK_PLANS: Dict[str, Dict[str, Any]] = {
    "morning_checkin": {
        "summary": "（规则模板）早间巡检：核对体重与睡眠",
        "tickets": [
            {
                "type": "question",
                "title": "今天早晨体重是多少？",
                "body": "规则模板提问：请直接回复数字（kg）。",
                "priority": "normal",
                "expected_reply_hours": 24,
                "fallback_assumption": "体重暂无更新，维持上次记录",
            }
        ],
        "actions": [],
        "unfinished": [],
        "next_tick_suggestions": ["等待体重回复后更新趋势"],
    },
    "midday_checkin": {
        "summary": "（规则模板）午间巡检",
        "tickets": [],
        "actions": [],
        "unfinished": [],
        "next_tick_suggestions": ["晚间复盘今日摄入与运动"],
    },
    "evening_review": {
        "summary": "（规则模板）晚间复盘",
        "tickets": [],
        "actions": [],
        "unfinished": [],
        "next_tick_suggestions": ["夜间维护窗口整理数据"],
    },
    "nightly_maintenance": {
        "summary": "（规则模板）夜间无声维护",
        "tickets": [],
        "actions": [{"kind": "episode", "content": "nightly_maintenance 规则模板执行（LLM 不可用）"}],
        "unfinished": [],
        "next_tick_suggestions": [],
    },
}

DEFAULT_FALLBACK_PLAN: Dict[str, Any] = {
    "summary": "（规则模板）基础巡检",
    "tickets": [],
    "actions": [],
    "unfinished": [],
    "next_tick_suggestions": [],
}


class TickEngine:
    """Tick 状态机。"""

    def __init__(
        self,
        config: SailTickConfig,
        db: TickDatabase,
        memory: AgentMemory,
        llm: LLMGateway,
        inbox: TicketInbox,
        scanner: DataScanner,
        notifier: NotificationEngine,
        handoffs: HandoffManager,
        state: DependencyState,
        dev_runner: Any = None,
        canary: Optional[CanaryController] = None,
        clock: Callable[[], datetime] = datetime.now,
    ):
        self.config = config
        self.db = db
        self.memory = memory
        self.llm = llm
        self.inbox = inbox
        self.scanner = scanner
        self.notifier = notifier
        self.handoffs = handoffs
        self.state = state
        self.dev_runner = dev_runner  # Phase 5: 自我开发执行器（可选）
        self.canary = canary          # 灰度/一键开关控制器（可选）
        self._clock = clock
        self._current_tick: Optional[dict] = None
        self._prompts_dir = config.prompts_dir

    # ── 入口 ──────────────────────────────────────────────────────────

    async def run_tick(
        self,
        slot: str,
        schedule_id: str = "",
        params: Optional[dict] = None,
        catch_up: bool = False,
        tick_date: Optional[str] = None,
        idempotency_suffix: Optional[str] = None,
    ) -> dict:
        """跑完整的一个 Tick。可被 scheduler 回调、CLI、管理 API 调用。"""
        # 灰度总闸与 slot 白名单检查
        if self.canary is not None:
            allowed, pause_reason = self.canary.should_run_slot(slot)
            if not allowed:
                logger.info("Tick PAUSED slot=%s mode=%s reason=%s", slot, self.canary.mode, pause_reason)
                await self.memory.save_episode(
                    None,
                    "canary_paused",
                    {"slot": slot, "mode": self.canary.mode, "reason": pause_reason},
                )
                return {
                    "status": "paused",
                    "reason": pause_reason,
                    "mode": self.canary.mode,
                    "slot": slot,
                }

        now = self._clock()
        tick_date = tick_date or now.strftime("%Y-%m-%d")
        idem_key = f"{slot}:{tick_date}#{idempotency_suffix}" if idempotency_suffix else f"{slot}:{tick_date}"
        mode = self.canary.mode if self.canary is not None else "live"

        logger.info("═" * 60)
        logger.info("Tick START slot=%s date=%s mode=%s catch_up=%s", slot, tick_date, mode, catch_up)

        tick = await self.db.create_tick(slot, tick_date, idempotency_key=idem_key)
        if tick["state"] == "running" and self._current_tick is not None:
            logger.warning("Tick %s already running, skip duplicate", tick["idempotency_key"])
            await self.db.update_tick(tick["id"], state="skipped", error="duplicate")
            return {"status": "skipped", "reason": "duplicate"}
        if tick["state"] == "completed":
            logger.info("Tick %s already completed, skip", tick["idempotency_key"])
            return {"status": "skipped", "reason": "already_completed"}

        self._current_tick = tick
        self.llm.begin_tick()
        deadline = self._clock() + timedelta(
            minutes=self.config.tick.work_budget_minutes
        )

        context: Dict[str, Any] = {
            "slot": slot,
            "tick_id": tick["id"],
            "mode": mode,
            "params": params or {},
        }
        try:
            await self._wake(context, tick)
            await self._scan(context, tick)
            plan = await self._plan(context, tick)
            context["plan"] = plan
            await self._work(context, tick, deadline)
            handoff_path = await self._handoff(context, tick)
            await self.db.update_tick(
                tick["id"], state="completed", ended_at=self._clock().isoformat()
            )
            downgraded = None
            if self.canary is not None:
                downgraded = await self.canary.record_tick_outcome(
                    success=True,
                    plan_source=context.get("plan_source", "fallback"),
                    tick_id=tick["id"],
                    error=context.get("llm_error"),
                )
            logger.info("Tick END slot=%s id=%s cost=%d tokens", slot, tick["id"], self.llm.tick_tokens)
            return {
                "status": "completed",
                "tick_id": tick["id"],
                "plan": plan,
                "plan_source": context.get("plan_source", "fallback"),
                "mode": mode,
                "emitted": context.get("emitted", []),
                "shadow_emitted": context.get("shadow_emitted", []),
                "handoff_path": handoff_path,
                "cost_tokens": self.llm.tick_tokens,
                "downgraded": downgraded,
            }
        except Exception as exc:
            logger.exception("Tick FAILED slot=%s", slot)
            await self.db.update_tick(
                tick["id"], state="failed", error=str(exc), ended_at=self._clock().isoformat()
            )
            if self.canary is not None:
                await self.canary.record_tick_outcome(
                    success=False,
                    plan_source=context.get("plan_source", "error"),
                    tick_id=tick["id"],
                    error=str(exc),
                )
            raise
        finally:
            self._current_tick = None

    async def interrupt_running_ticks(self) -> int:
        """daemon 重启时把残留 running 态 tick 标记 interrupted（设计文档 §3.3）。"""
        running = await self.db.get_running_ticks()
        for t in running:
            await self.db.update_tick(t["id"], state="interrupted", error="daemon restarted")
        return len(running)

    # ── WAKE ──────────────────────────────────────────────────────────

    async def _wake(self, context: Dict[str, Any], tick: dict) -> None:
        prev = await self.handoffs.read_latest()
        context["prev_handoff"] = prev
        context["active_plan"] = await self.db.get_active_plan()
        context["memory_summary"] = await self.memory.summary_for_prompt()
        await self.memory.save_episode(
            tick["id"], "wake", {"slot": tick["slot"], "mode": context.get("mode", "live")}
        )
        logger.info("WAKE ok: prev_handoff=%s", "yes" if prev else "no")

    # ── SCAN ──────────────────────────────────────────────────────────

    async def _scan(self, context: Dict[str, Any], tick: dict) -> None:
        # 1. 依赖健康
        server_ok = await self.inbox.health()
        self.state.update("sail_server", "ok" if server_ok else "down")
        llm_ready = bool(self.llm.config.providers)
        self.state.update("llm", "ok" if llm_ready else "down")

        # 2. 票据同步：超期处理 + 拉取回复
        tickets = []
        replies = []
        if server_ok:
            try:
                await self.inbox.expire_overdue()
                tickets = await self.inbox.pending_tickets()
                replies = await self.inbox.sync_replies_since()
            except Exception as exc:
                logger.warning("inbox sync failed (non-fatal): %s", exc)

        # 3. 数据扫描
        data_package = await self.scanner.scan(days=7)
        self.state.update(
            "datascan", "ok" if data_package.get("health_ok") else "degraded"
        )

        context.update(
            {
                "server_ok": server_ok,
                "pending_tickets": tickets,
                "new_replies": replies,
                "data_package": data_package,
                "data_summary": self.scanner.describe(data_package),
            }
        )
        await self.memory.save_episode(
            tick["id"], "scan",
            {
                "server_ok": server_ok,
                "pending_tickets": len(tickets),
                "new_replies": len(replies),
                "data_ok": bool(data_package.get("health_ok")),
            },
        )
        logger.info(
            "SCAN ok: server=%s tickets=%d replies=%d data_ok=%s",
            server_ok, len(tickets), len(replies), data_package.get("health_ok"),
        )

    def _policy(self) -> Dict[str, Any]:
        if self.canary is not None:
            return self.canary.effective_policy()
        return {
            "mode": "live",
            "allow_llm": True,
            "allow_ticket_create": True,
            "allow_push": True,
            "allow_self_dev": True,
            "max_tickets_per_tick": 2,
            "ticket_title_prefix": "",
        }

    # ── PLAN ──────────────────────────────────────────────────────────

    async def _plan(self, context: Dict[str, Any], tick: dict) -> Dict[str, Any]:
        import copy

        policy = self._policy()
        max_tickets = max(0, min(2, int(policy.get("max_tickets_per_tick", 2))))

        if (
            not policy.get("allow_llm", True)
            or self.llm.budget_exceeded
            or self.state.get("llm")["status"] != "ok"
        ):
            plan = copy.deepcopy(FALLBACK_PLANS.get(tick["slot"], DEFAULT_FALLBACK_PLAN))
            plan["tickets"] = plan.get("tickets", [])[:max_tickets]
            context["plan_source"] = "fallback"
            await self.memory.save_episode(
                tick["id"],
                "plan",
                {"source": "fallback", "mode": policy["mode"], "summary": plan.get("summary", "")},
            )
            await self.db.update_tick(tick["id"], plan=plan)
            return plan

        prompt = self._build_plan_prompt(context, tick)
        try:
            resp = await self.llm.chat(prompt, expect_json=True, max_tokens=3000)
            plan = json.loads(self._extract_json(resp.content))
            self._validate_plan(plan)
            context["plan_source"] = "llm"
            context["llm_latency_ms"] = getattr(resp, "latency_ms", 0.0)
        except Exception as exc:
            logger.warning("PLAN llm failed, fallback to rule template: %s", exc)
            plan = copy.deepcopy(FALLBACK_PLANS.get(tick["slot"], DEFAULT_FALLBACK_PLAN))
            context["plan_source"] = "fallback_error"
            context["llm_error"] = str(exc)

        # 票据节流：默认每 Tick 最多 2 张，灰度可收紧至 1 张
        tickets = plan.get("tickets", [])[:max_tickets]
        plan["tickets"] = tickets

        ep_payload: Dict[str, Any] = {
            "source": context["plan_source"],
            "mode": policy["mode"],
            "summary": plan.get("summary", ""),
        }
        if context.get("llm_error"):
            ep_payload["error"] = context["llm_error"]
        await self.memory.save_episode(tick["id"], "plan", ep_payload)
        await self.db.update_tick(tick["id"], plan=plan)
        logger.info("PLAN ok: source=%s tickets=%d", context["plan_source"], len(tickets))
        return plan

    def _build_plan_prompt(self, context: Dict[str, Any], tick: dict) -> str:
        system = self._load_prompt("coach/v1/system.md")
        # 同步拼装（各摘要已在前序阶段就绪）
        prev: Optional[HandoffDoc] = context.get("prev_handoff")
        prev_text = prev.prev_summary if prev else "(首个 Tick)"
        plan_doc = context.get("active_plan")
        plan_text = (
            f"{plan_doc['version']}\n{plan_doc['content'][:800]}" if plan_doc else "(尚无计划)"
        )
        mem = context.get("memory_summary") or {}
        profile_text = mem.get("profile", "(空)")
        semantic_text = mem.get("semantic", "(空)")
        tickets_text = "\n".join(
            f"- #{t.get('id')} [{t.get('type')}] {t.get('title')} (by {t.get('expected_reply_by')})"
            for t in context.get("pending_tickets", [])[:10]
        ) or "(无)"
        replies_text = "\n".join(
            f"- #{r.get('id')} {r.get('title')}: 用户回复「{r.get('reply', '')}」"
            for r in context.get("new_replies", [])[:10]
        ) or "(无)"

        return f"""{system}


# 当前计划
{plan_text}

# 用户画像与记忆
[Profile]
{profile_text}
[Semantic]
{semantic_text}

# 上 Tick 摘要
{prev_text}

# 用户状态数据
{context.get('data_summary', '(无数据)')}

# 新收到的用户回复
{replies_text}

# 待回复票据
{tickets_text}

# 任务
你是 SailTick 的 PLAN 阶段。基于以上信息为「{tick['slot']}」slot 生成本窗口计划。
只输出 JSON：
{{
  "summary": "本 Tick 要点（1-2 句）",
  "tickets": [
    {{
      "type": "question|task|info",
      "title": "票据标题（简短）",
      "body": "正文（含为什么问这个）",
      "priority": "low|normal|high",
      "expected_reply_hours": 48,
      "fallback_assumption": "用户不回复时采用的假设"
    }}
  ],
  "actions": [{{"kind": "episode", "content": "要记入事件流的内容"}}],
  "unfinished": [{{"task": "未完成事项", "reason": "原因"}}],
  "next_tick_suggestions": ["给下个 Tick 的建议"]
}}
票据最多 2 张；没有问题就留空数组；保持温和不苛责的语气。"""

    @staticmethod
    def _extract_json(content: str) -> str:
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        return content.strip()

    @staticmethod
    def _validate_plan(plan: Dict[str, Any]) -> None:
        if not isinstance(plan, dict):
            raise ValueError("plan is not a dict")
        for key in ("summary", "tickets", "actions", "unfinished", "next_tick_suggestions"):
            plan.setdefault(key, [] if key != "summary" else "")
        if not isinstance(plan["tickets"], list):
            raise ValueError("tickets must be list")

    # ── WORK ──────────────────────────────────────────────────────────

    async def _work(self, context: Dict[str, Any], tick: dict, deadline: datetime) -> None:
        plan = context["plan"]
        policy = self._policy()
        emitted: List[Dict[str, Any]] = []
        shadow_emitted: List[Dict[str, Any]] = []

        ticket_items = plan.get("tickets", [])
        action_items = plan.get("actions", [])

        # shadow 模式：完整记录拟发射票据与动作，不产生外部副作用
        if policy["mode"] == "shadow" or not policy.get("allow_ticket_create", True):
            for t in ticket_items:
                shadow_emitted.append(
                    {
                        "title": t.get("title", "(无标题)"),
                        "type": t.get("type", "question"),
                        "priority": t.get("priority", "normal"),
                        "body": t.get("body", ""),
                        "action": "shadow_simulated",
                    }
                )
            await self.memory.save_episode(
                tick["id"],
                "shadow_work",
                {
                    "mode": policy["mode"],
                    "tickets_simulated": len(shadow_emitted),
                    "tickets": shadow_emitted,
                    "actions_simulated": len(action_items),
                },
            )
            context["emitted"] = []
            context["shadow_emitted"] = shadow_emitted
            logger.info(
                "WORK [shadow]: simulated tickets=%d actions=%d (zero side effects)",
                len(shadow_emitted),
                len(action_items),
            )
            return

        prefix = policy.get("ticket_title_prefix") or ""
        suppress_push = not bool(policy.get("allow_push", True))

        for idx, t in enumerate(ticket_items):
            if self._clock() > deadline:
                # 预算耗尽：剩余全部票据记入未完成事项
                for rest in ticket_items[idx:]:
                    plan.setdefault("unfinished", []).append(
                        {"task": f"发票据: {rest.get('title')}", "reason": "预算耗尽", "priority": "high"}
                    )
                break
            raw_title = t.get("title", "(无标题)")
            title = f"{prefix}{raw_title}" if prefix and not raw_title.startswith(prefix) else raw_title
            result = await self.notifier.emit(
                title=title,
                content=t.get("body", ""),
                priority=t.get("priority", "normal"),
                ticket_type=t.get("type", "question"),
                tick_id=tick["id"],
                expected_reply_hours=t.get("expected_reply_hours"),
                fallback_assumption=t.get("fallback_assumption", ""),
                suppress_push=suppress_push,
            )
            emitted.append({"title": title, "result": result})
            if result.get("ticket_id"):
                await self.memory.save_episode(
                    tick["id"], "work", {"ticket_created": result["ticket_id"], "title": title}
                )

        for idx, a in enumerate(action_items):
            if self._clock() > deadline:
                for rest in action_items[idx:]:
                    plan.setdefault("unfinished", []).append(
                        {"task": f"动作: {rest.get('kind')}", "reason": "预算耗尽", "priority": "normal"}
                    )
                break
            if a.get("kind") == "episode":
                await self.memory.save_episode(tick["id"], "work", a.get("content"))
            elif a.get("kind") == "memory":
                await self.memory.save(
                    a.get("memory_type", "semantic"), a.get("key", "misc"), a.get("value")
                )
            elif a.get("kind") == "dev_task" and self.dev_runner is not None:
                if not policy.get("allow_self_dev", True):
                    await self.memory.save_episode(
                        tick["id"],
                        "dev_skipped",
                        {"task": a.get("task_id", ""), "reason": f"disabled_in_mode:{policy['mode']}"},
                    )
                    continue
                # Phase 5 自我开发：由 nightly slot 触发（LLM 产出 file_contents 后执行）
                from sailtick.dev.tasks import DevTask

                task = DevTask(
                    id=a.get("task_id", f"adhoc_{tick['id'][:8]}"),
                    title=a.get("title", "sailtick dev task"),
                    description=a.get("description", ""),
                    files=list(a.get("files", [])),
                )
                result = await self.dev_runner.run_task(
                    task, file_contents=dict(a.get("file_contents", {}))
                )
                await self.memory.save_episode(
                    tick["id"], "dev",
                    {"task": task.id, "success": result.success, "commit": result.commit,
                     "ticket": result.ticket_id, "error": result.error},
                )

        context["emitted"] = emitted
        context["shadow_emitted"] = shadow_emitted
        logger.info("WORK ok: emitted=%d", len(emitted))

    # ── HANDOFF ───────────────────────────────────────────────────────

    async def _handoff(self, context: Dict[str, Any], tick: dict) -> str:
        plan = context.get("plan", {})
        mode = context.get("mode", "live")
        summary_text = plan.get("summary", "")
        if mode == "shadow" and summary_text and not summary_text.startswith("[shadow]"):
            summary_text = f"[shadow] {summary_text}"
        doc = HandoffDoc(
            tick_id=tick["id"],
            slot=tick["slot"],
            tick_date=tick["tick_date"],
            prev_summary=summary_text,
            unfinished=plan.get("unfinished", []),
            plan_version=(context.get("active_plan") or {}).get("version", "(无)"),
            plan_change="见本 Tick 计划",
            pending_tickets=[
                {
                    "id": e.get("result", {}).get("ticket_id"),
                    "type": t.get("type"),
                    "title": t.get("title"),
                    "expected_reply_by": t.get("expected_reply_by"),
                    "fallback_assumption": t.get("fallback_assumption"),
                }
                for e, t in zip(context.get("emitted", []), plan.get("tickets", []))
                if e.get("result", {}).get("ticket_id")
            ],
            user_status=summary_text,
            next_tick_suggestions=plan.get("next_tick_suggestions", []),
        )
        path = await self.handoffs.write(doc)

        # 压缩记忆 + 成本记录（若 LLMGateway 已通过 cost_sink 记账则不重复叠加）
        await self.memory.cleanup_expired()
        if not getattr(self.llm, "cost_recorded_by_sink", False):
            await self.db.add_tick_cost(
                tick["id"], self.llm.tick_tokens, float(getattr(self.llm, "tick_usd", 0.0))
            )
        await self.memory.save_episode(
            tick["id"],
            "handoff",
            {"path": path, "cost_tokens": self.llm.tick_tokens, "mode": mode},
        )
        logger.info("HANDOFF ok: path=%s cost=%d tokens", path, self.llm.tick_tokens)
        return path

    # ── 工具 ──────────────────────────────────────────────────────────

    def _load_prompt(self, rel_path: str) -> str:
        path = os.path.join(self._prompts_dir, rel_path) if self._prompts_dir else ""
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return "(system prompt 未找到)"

    def current_tick(self) -> Optional[dict]:
        return self._current_tick
