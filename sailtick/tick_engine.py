# -*- coding: utf-8 -*-
# @file tick_engine.py
# @brief TickEngine — SLEEP→WAKE→SCAN→PLAN→WORK→HANDOFF 状态机（支持渐进提问、静默餐饮吸收、AI 动态计划维护与每日睡前日报）
# @author sailing-innocent
# @date 2026-10-27
# @version 2.0
# ---------------------------------
"""TickEngine — SailTick 核心状态机。

状态机（设计文档 §3）:
  WAKE    建 tick 实例（幂等键 slot:date）、加载 handoff / 计划 / 四层记忆
  SCAN    依赖健康检查 + 真实数据扫描 + 体重变化检测 + 票据回复与用户主动消息同步
  PLAN    组装完整上下文（system + slot 提示 + 渐进问卷切片 + 体重监控 + 主动餐饮消息），
          LLM 生成本窗口计划（超预算/不可用 → 规则模板降级）
  WORK    执行计划（防轰炸提问限流、建票据、写画像/记忆、记录饮食、同步 AI 动态计划、
          发布每日睡前体重报告、关闭已吸收票据、标记已吸收主动消息）
  HANDOFF 写交接文档、压缩记忆、推进游标与水位线、记录成本
"""

from __future__ import annotations

import copy
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import yaml

from sailtick.canary import CanaryController
from sailtick.config import SailTickConfig
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
from sailtick.handoff import HandoffDoc, HandoffManager
from sailtick.inbox import TicketInbox
from sailtick.llm import LLMGateway
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance
from sailtick.notify import NotificationEngine
from sailtick.state import DependencyState
from sailtick.tracer import TickTraceRecorder

logger = logging.getLogger(__name__)

# 无 LLM 时的规则模板（设计文档 §11 LLM 降级）
FALLBACK_PLANS: Dict[str, Dict[str, Any]] = {
    "morning_checkin": {
        "summary": "（规则模板）早间巡检：核对体重与睡眠",
        "tickets": [
            {
                "type": "question",
                "topic": "morning_weight",
                "title": "今天早晨体重是多少？",
                "body": "规则模板提问：请直接回复数字（kg），或在健康页随手记一下即可。",
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
        "next_tick_suggestions": ["睡前生成今日体重与健康日报"],
    },
    "pre_sleep_report": {
        "summary": "（规则模板）每日睡前体重与健康日报",
        "tickets": [],
        "actions": [],
        "unfinished": [],
        "next_tick_suggestions": ["明早继续轻量化观察体重与作息"],
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
        nightly: Optional[NightlySelfMaintenance] = None,
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
        self.dev_runner = dev_runner
        self.canary = canary
        self._nightly = nightly
        self._clock = clock
        self._current_tick: Optional[dict] = None
        self._prompts_dir = config.prompts_dir

    def _get_nightly(self) -> NightlySelfMaintenance:
        if self._nightly is None:
            self._nightly = NightlySelfMaintenance(
                config=self.config,
                db=self.db,
                memory=self.memory,
                scanner=self.scanner,
                llm=self.llm,
                clock=self._clock,
            )
        else:
            # 保持与可能被测试/热更新替换的 scanner/llm 同步
            self._nightly.scanner = self.scanner
            self._nightly.llm = self.llm
            self._nightly.knowledge.llm = self.llm
        return self._nightly

    async def _persist_and_report_trace(self, trace_dict: Dict[str, Any]) -> None:
        """本地落库 + 非致命上报至 sail_server（任何异常均不影响 Tick 主流程）。"""
        try:
            if hasattr(self.db, "save_trace") and getattr(self.db, "_engine", None) is not None:
                await self.db.save_trace(trace_dict)
        except Exception as exc:
            logger.warning("Trace local save failed (non-fatal): %s", exc)
        try:
            if hasattr(self.inbox, "report_ai_trace"):
                await self.inbox.report_ai_trace(trace_dict)
        except Exception as exc:
            logger.debug("Trace remote report failed (non-fatal): %s", exc)

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
        now = self._clock()
        tick_date = tick_date or now.strftime("%Y-%m-%d")
        mode = self.canary.mode if self.canary is not None else "live"
        raw_params = dict(params or {})
        trigger_source = str(
            raw_params.get("trigger_source")
            or ("catch_up" if catch_up else ("scheduler" if schedule_id else "manual"))
        )

        tracer = TickTraceRecorder(
            slot=slot,
            tick_date=tick_date,
            mode=mode,
            trigger_source=trigger_source,
            clock=self._clock,
        )
        tracer.meta["schedule_id"] = schedule_id
        tracer.meta["catch_up"] = catch_up

        if self.canary is not None:
            allowed, pause_reason = self.canary.should_run_slot(slot)
            if not allowed:
                logger.info("Tick PAUSED slot=%s mode=%s reason=%s", slot, self.canary.mode, pause_reason)
                tracer.record_instant_span(
                    "canary",
                    "canary_gate",
                    status="skipped",
                    output_summary=f"paused: {pause_reason}",
                    payload={"mode": self.canary.mode, "reason": pause_reason},
                )
                await self.memory.save_episode(
                    None,
                    "canary_paused",
                    {"slot": slot, "mode": self.canary.mode, "reason": pause_reason},
                )
                trace_dict = tracer.finish("paused", summary=f"Canary paused: {pause_reason}")
                await self._persist_and_report_trace(trace_dict)
                return {
                    "status": "paused",
                    "reason": pause_reason,
                    "mode": self.canary.mode,
                    "slot": slot,
                    "trace_id": tracer.trace_id,
                }

        idem_key = f"{slot}:{tick_date}#{idempotency_suffix}" if idempotency_suffix else f"{slot}:{tick_date}"

        logger.info("═" * 60)
        logger.info("Tick START slot=%s date=%s mode=%s catch_up=%s", slot, tick_date, mode, catch_up)

        tick = await self.db.create_tick(slot, tick_date, idempotency_key=idem_key)
        tracer.tick_id = str(tick["id"])
        tracer.meta["idempotency_key"] = idem_key
        if tick["state"] == "running" and self._current_tick is not None:
            logger.warning("Tick %s already running, skip duplicate", tick["idempotency_key"])
            await self.db.update_tick(tick["id"], state="skipped", error="duplicate")
            tracer.record_instant_span(
                "wake",
                "idempotency_check",
                status="skipped",
                output_summary="duplicate running tick",
            )
            trace_dict = tracer.finish("skipped", summary="Skipped: duplicate running tick")
            await self._persist_and_report_trace(trace_dict)
            return {"status": "skipped", "reason": "duplicate", "trace_id": tracer.trace_id}
        if tick["state"] == "completed":
            logger.info("Tick %s already completed, skip", tick["idempotency_key"])
            tracer.record_instant_span(
                "wake",
                "idempotency_check",
                status="skipped",
                output_summary="already completed",
            )
            trace_dict = tracer.finish("skipped", summary="Skipped: already completed")
            await self._persist_and_report_trace(trace_dict)
            return {"status": "skipped", "reason": "already_completed", "trace_id": tracer.trace_id}

        self._current_tick = tick
        self.llm.begin_tick()
        deadline = self._clock() + timedelta(
            minutes=self.config.tick.work_budget_minutes
        )

        context: Dict[str, Any] = {
            "slot": slot,
            "tick_id": tick["id"],
            "tick_date": tick_date,
            "mode": mode,
            "params": raw_params,
            "tracer": tracer,
        }
        try:
            with tracer.span("wake", "WAKE 装载上下文", input_summary=f"slot={slot} mode={mode}") as sp:
                await self._wake(context, tick)
                sp.set_output(
                    f"handoff={'yes' if context.get('prev_handoff') else 'no'}, "
                    f"plan={(context.get('active_plan') or {}).get('version', 'none')}, "
                    f"profile_keys={len(context.get('profile_dict') or {})}"
                )
                sp.set_payload(
                    {
                        "has_prev_handoff": bool(context.get("prev_handoff")),
                        "active_plan_version": (context.get("active_plan") or {}).get("version"),
                        "profile_keys": sorted((context.get("profile_dict") or {}).keys()),
                        "asked_topics_count": len(context.get("topic_history") or {}),
                    }
                )

            with tracer.span("scan", "SCAN 数据扫描与收件箱同步", input_summary="window=7d") as sp:
                await self._scan(context, tick)
                sp.set_output(
                    f"server_ok={context.get('server_ok')}, pending={len(context.get('pending_tickets', []))}, "
                    f"replies={len(context.get('new_replies', []))}, msgs={len(context.get('unread_messages', []))}, "
                    f"weight_updated={context.get('weight_updated')}"
                )
                sp.set_payload(
                    {
                        "server_ok": bool(context.get("server_ok")),
                        "data_ok": bool((context.get("data_package") or {}).get("health_ok")),
                        "pending_tickets": len(context.get("pending_tickets", [])),
                        "new_replies": len(context.get("new_replies", [])),
                        "unread_messages": len(context.get("unread_messages", [])),
                        "weight_updated": bool(context.get("weight_updated")),
                        "data_summary_preview": str(context.get("data_summary", ""))[:1500],
                    }
                )
                if not context.get("server_ok") or not (context.get("data_package") or {}).get("health_ok"):
                    sp.mark_status("degraded")

            with tracer.span("plan", "PLAN 上下文组装与决策", input_summary=f"slot={slot}") as sp:
                plan = await self._plan(context, tick)
                context["plan"] = plan
                tracer.plan_source = str(context.get("plan_source", "fallback"))
                sp.set_output(
                    f"source={tracer.plan_source}, tickets={len(plan.get('tickets', []))}, "
                    f"actions={len(plan.get('actions', []))}"
                )
                sp.set_payload(
                    {
                        "plan_source": tracer.plan_source,
                        "summary": plan.get("summary", ""),
                        "tickets_count": len(plan.get("tickets", [])),
                        "actions_count": len(plan.get("actions", [])),
                        "plan": plan,
                        "llm_error": context.get("llm_error"),
                    }
                )
                if tracer.plan_source == "fallback_error":
                    sp.mark_status("degraded", context.get("llm_error"))

            with tracer.span(
                "work",
                "WORK 执行票据与动作",
                input_summary=f"tickets={len(plan.get('tickets', []))}, actions={len(plan.get('actions', []))}",
            ) as sp:
                await self._work(context, tick, deadline)
                emitted_list = context.get("emitted", [])
                shadow_list = context.get("shadow_emitted", [])
                work_res = context.get("work_results", [])
                tracer.tickets_created = sum(
                    1 for e in emitted_list if (e.get("result") or {}).get("ticket_id")
                )
                tracer.actions_executed = len(work_res)
                tracer.actions_failed = sum(1 for r in work_res if r.get("ok") is False)
                sp.set_output(
                    f"emitted={tracer.tickets_created}, shadow={len(shadow_list)}, "
                    f"actions={tracer.actions_executed} (failed={tracer.actions_failed})"
                )
                sp.set_payload(
                    {
                        "mode": mode,
                        "emitted": emitted_list,
                        "shadow_emitted": shadow_list,
                        "work_results": work_res,
                    }
                )
                if tracer.actions_failed > 0:
                    sp.mark_status("degraded", f"{tracer.actions_failed} work action(s) failed")

            with tracer.span("handoff", "HANDOFF 交接与记账") as sp:
                handoff_path = await self._handoff(context, tick)
                sp.set_output(f"path={handoff_path}, cost={self.llm.tick_tokens} tokens")
                sp.set_payload({"handoff_path": handoff_path, "cost_tokens": self.llm.tick_tokens})

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
                if downgraded:
                    tracer.record_instant_span(
                        "canary",
                        "circuit_breaker_downgrade",
                        status="degraded",
                        output_summary=f"downgraded to {downgraded.get('mode')}",
                        payload={"downgraded": downgraded},
                    )
            tracer.meta.update(
                {
                    "handoff_path": handoff_path,
                    "downgraded": bool(downgraded),
                    "deps": self.state.snapshot() if self.state is not None else {},
                }
            )
            if tracer.total_tokens == 0 and self.llm.tick_tokens > 0:
                tracer.total_tokens = int(self.llm.tick_tokens)
                tracer.cost_usd = float(getattr(self.llm, "tick_usd", 0.0))
            trace_dict = tracer.finish(
                "completed",
                summary=str(plan.get("summary") or f"{slot} completed"),
                error=context.get("llm_error"),
            )
            await self._persist_and_report_trace(trace_dict)

            logger.info("Tick END slot=%s id=%s cost=%d tokens", slot, tick["id"], self.llm.tick_tokens)
            return {
                "status": "completed",
                "tick_id": tick["id"],
                "trace_id": tracer.trace_id,
                "plan": plan,
                "plan_source": context.get("plan_source", "fallback"),
                "mode": mode,
                "emitted": context.get("emitted", []),
                "shadow_emitted": context.get("shadow_emitted", []),
                "work_results": context.get("work_results", []),
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
            tracer.plan_source = str(context.get("plan_source", tracer.plan_source))
            trace_dict = tracer.finish("failed", summary=f"Tick failed: {exc}", error=str(exc))
            await self._persist_and_report_trace(trace_dict)
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
        context["profile_dict"] = await self.memory.all_profile()
        context["topic_history"] = (await self.db.get_runtime_state("asked_topics")) or {}
        context["expert_brief"] = await self.db.get_runtime_state("expert_brief")
        await self.memory.save_episode(
            tick["id"], "wake", {"slot": tick["slot"], "mode": context.get("mode", "live")}
        )
        logger.info("WAKE ok: prev_handoff=%s", "yes" if prev else "no")

    # ── SCAN ──────────────────────────────────────────────────────────

    async def _scan(self, context: Dict[str, Any], tick: dict) -> None:
        server_ok = await self.inbox.health()
        self.state.update("sail_server", "ok" if server_ok else "down")
        llm_ready = bool(self.llm.config.providers)
        self.state.update("llm", "ok" if llm_ready else "down")

        tickets: List[Dict[str, Any]] = []
        replies: List[Dict[str, Any]] = []
        unread_messages: List[Dict[str, Any]] = []
        if server_ok:
            try:
                await self.inbox.expire_overdue()
                tickets = await self.inbox.pending_tickets()
                reply_cursor = await self.db.get_runtime_state("tick_reply_cursor")
                since_dt = None
                if reply_cursor:
                    try:
                        since_dt = datetime.fromisoformat(str(reply_cursor))
                    except ValueError:
                        since_dt = None
                replies = await self.inbox.sync_replies_since(since=since_dt)
                if hasattr(self.inbox, "list_user_messages"):
                    unread_messages = await self.inbox.list_user_messages(status="unread", limit=50)
            except Exception as exc:
                logger.warning("inbox sync failed (non-fatal): %s", exc)

        data_package = await self.scanner.scan(days=7)
        self.state.update(
            "datascan", "ok" if data_package.get("health_ok") else "degraded"
        )

        # 检测自上次 Tick 以来是否有新的体重测量更新
        wm = data_package.get("weight_monitor") or {}
        last_seen_sig = await self.db.get_runtime_state("last_weight_watermark")
        current_sig = None
        if wm.get("latest_kg") is not None:
            current_sig = f"{wm.get('latest_id')}:{wm.get('latest_at')}:{wm.get('latest_kg')}"
        weight_updated = bool(current_sig and current_sig != last_seen_sig)
        wm["updated_since_last_tick"] = weight_updated

        # 如果 datascan 中没取到 unread_messages，用 inbox 的补齐
        if not unread_messages and isinstance(data_package.get("user_messages"), list):
            unread_messages = data_package["user_messages"]

        # 夜间自维护（阶段1，确定性无额外 LLM 调用）：长周期深度数据扫描 + 数学建模 + 编译专家简报
        if tick["slot"] == "nightly_maintenance" and self.config.nightly.enabled:
            try:
                stage1 = await self._get_nightly().run_modeling_stage(
                    tick_id=tick["id"],
                    tracer=context.get("tracer"),
                )
                context["nightly_stage1"] = stage1
                context["expert_brief"] = stage1.get("expert_brief")
            except Exception as exc:
                logger.warning("nightly modeling stage failed (non-fatal): %s", exc)
        elif not context.get("expert_brief") and self.config.nightly.enabled:
            try:
                await self._get_nightly().knowledge.ensure_seeded()
            except Exception:
                pass

        context.update(
            {
                "server_ok": server_ok,
                "pending_tickets": tickets,
                "new_replies": replies,
                "unread_messages": unread_messages,
                "data_package": data_package,
                "data_summary": self.scanner.describe(data_package),
                "weight_updated": weight_updated,
                "current_weight_watermark": current_sig,
            }
        )
        await self.memory.save_episode(
            tick["id"],
            "scan",
            {
                "server_ok": server_ok,
                "pending_tickets": len(tickets),
                "new_replies": len(replies),
                "unread_messages": len(unread_messages),
                "weight_updated": weight_updated,
                "data_ok": bool(data_package.get("health_ok")),
            },
        )
        logger.info(
            "SCAN ok: server=%s tickets=%d replies=%d msgs=%d weight_updated=%s data_ok=%s",
            server_ok,
            len(tickets),
            len(replies),
            len(unread_messages),
            weight_updated,
            data_package.get("health_ok"),
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

    # ── 渐进问卷切片 & 防轰炸限流 ───────────────────────────────────────

    def _select_candidate_questions(self, context: Dict[str, Any], slot: str) -> List[Dict[str, Any]]:
        """根据当前 slot、已掌握 profile 与话题冷却，挑出最多 2 个候选问题供 LLM 择 0-1 个提问。"""
        if slot in ("nightly_maintenance", "pre_sleep_report"):
            return []
        qpath = os.path.join(self._prompts_dir, "coach/v1/question_bank.yaml") if self._prompts_dir else ""
        if not qpath or not os.path.exists(qpath):
            return []
        try:
            with open(qpath, "r", encoding="utf-8") as f:
                bank = yaml.safe_load(f) or []
        except Exception:
            return []

        profile = context.get("profile_dict") or {}
        topic_history = context.get("topic_history") or {}
        now = self._clock()
        cooldown_hours = max(1, int(self.config.notify.topic_cooldown_hours))
        pending_topics = {
            (t.get("topic") or "").strip()
            for t in context.get("pending_tickets", [])
            if t.get("topic")
        }

        candidates: List[Dict[str, Any]] = []
        for q in bank:
            if not isinstance(q, dict):
                continue
            timing = q.get("timing") or []
            if timing and slot not in timing:
                continue
            pkey = q.get("target_profile_key", "")
            # 已经高置信度知道的字段不再重复问
            if pkey and pkey in profile and float(profile[pkey].get("confidence", 0)) >= 0.7:
                continue
            qid = str(q.get("id") or pkey)
            if qid in pending_topics:
                continue
            last_asked_str = topic_history.get(qid)
            if last_asked_str:
                try:
                    last_dt = datetime.fromisoformat(str(last_asked_str))
                    if (now - last_dt).total_seconds() < cooldown_hours * 3600:
                        continue
                except ValueError:
                    pass
            candidates.append(q)

        # minimum 优先，最多给 LLM 2 个候选，确保渐进细化不轰炸
        candidates.sort(key=lambda item: 0 if item.get("necessary") == "minimum" else 1)
        return candidates[:2]

    def _throttle_tickets(
        self,
        raw_tickets: List[Dict[str, Any]],
        context: Dict[str, Any],
        max_tickets: int,
    ) -> List[Dict[str, Any]]:
        """执行防轰炸护栏：
        - 每 Tick 最多 max_tickets 张票据；
        - 每 Tick 最多 max_questions_per_tick (默认 1) 张非 urgent 提问；
        - 若当前已有 >= max_pending_questions (默认 2) 张待回提问，暂缓新的非 urgent 提问；
        - 同 topic 冷却期内跳过重复提问。
        """
        pending_questions = [
            t for t in context.get("pending_tickets", [])
            if t.get("type") == "question"
        ]
        max_q_tick = max(1, int(self.config.notify.max_questions_per_tick))
        max_pending_q = max(1, int(self.config.notify.max_pending_questions))
        cooldown_hours = max(1, int(self.config.notify.topic_cooldown_hours))
        topic_history = context.get("topic_history") or {}
        now = self._clock()

        kept: List[Dict[str, Any]] = []
        dropped: List[Dict[str, Any]] = []
        q_count = 0
        for t in raw_tickets:
            title = str(t.get("title") or "(无标题)")
            if len(kept) >= max_tickets:
                dropped.append({"title": title, "topic": t.get("topic", ""), "reason": f"max_tickets_per_tick={max_tickets}"})
                continue
            ttype = t.get("type", "question")
            priority = t.get("priority", "normal")
            topic = str(t.get("topic") or "").strip()

            if ttype == "question" and priority != "urgent":
                if len(pending_questions) >= max_pending_q:
                    logger.info(
                        "Throttle question '%s': already %d pending questions",
                        title,
                        len(pending_questions),
                    )
                    dropped.append({"title": title, "topic": topic, "reason": f"pending_questions>={max_pending_q}"})
                    continue
                if q_count >= max_q_tick:
                    logger.info(
                        "Throttle question '%s': reached max_questions_per_tick=%d",
                        title,
                        max_q_tick,
                    )
                    dropped.append({"title": title, "topic": topic, "reason": f"max_questions_per_tick={max_q_tick}"})
                    continue
                if topic and topic in topic_history:
                    try:
                        last_dt = datetime.fromisoformat(str(topic_history[topic]))
                        if (now - last_dt).total_seconds() < cooldown_hours * 3600:
                            logger.info("Throttle question '%s': topic '%s' in cooldown", title, topic)
                            dropped.append({"title": title, "topic": topic, "reason": f"topic_cooldown({cooldown_hours}h)"})
                            continue
                    except ValueError:
                        pass
                q_count += 1
            kept.append(t)

        tracer: Optional[TickTraceRecorder] = context.get("tracer")
        if tracer is not None and (raw_tickets or dropped):
            tracer.tickets_throttled += len(dropped)
            tracer.record_instant_span(
                "throttle",
                "票据防轰炸限流",
                status="degraded" if dropped else "ok",
                input_summary=f"raw={len(raw_tickets)}, max={max_tickets}",
                output_summary=f"kept={len(kept)}, dropped={len(dropped)}",
                payload={"kept_titles": [t.get("title") for t in kept], "dropped": dropped},
            )
        return kept

    def _build_deterministic_daily_report_action(
        self, context: Dict[str, Any], tick: dict
    ) -> Dict[str, Any]:
        """当 pre_sleep_report 降级或 LLM 未显式输出 daily_report 时，基于真实扫描数据生成兜底睡前日报。"""
        report_date = tick.get("tick_date") or self._clock().strftime("%Y-%m-%d")
        pkg = context.get("data_package") or {}
        wm = pkg.get("weight_monitor") or {}
        ap = pkg.get("active_plan") or {}
        diets = pkg.get("diet") or []
        msgs = context.get("unread_messages") or []

        latest_kg = wm.get("latest_kg")
        delta = wm.get("delta_from_prev")
        avg_7d = wm.get("avg_7d")
        today_diet_items = [
            f"{d.get('meal_type', 'meal')}: {d.get('description', '')}"
            for d in diets
            if str(d.get("time") or "").startswith(report_date)
        ]
        today_msg_items = [
            f"[{m.get('category', 'note')}] {m.get('content', '')}"
            for m in msgs
        ]
        all_intake = today_diet_items + today_msg_items

        weight_line = (
            f"最新体重 {latest_kg}kg"
            + (f"（较上次 {delta:+.2f}kg）" if delta is not None else "")
            + (f"，7日均值 {avg_7d}kg" if avg_7d is not None else "")
            if latest_kg is not None
            else "今日暂无新体重记录，明天晨起方便时称一下即可"
        )
        intake_line = (
            f"共整合 {len(all_intake)} 条饮食/状态记录"
            if all_intake
            else "今日暂无饮食文字记录"
        )
        summary = f"{weight_line}；{intake_line}。早点休息，明天继续保持轻松节奏。"

        md_lines = [
            f"## {report_date} 睡前体重与健康日报",
            "",
            "### 1. 体重与趋势",
            f"- {weight_line}",
            "",
            "### 2. 今日餐饮与状态整合",
        ]
        if all_intake:
            md_lines.extend(f"- {item}" for item in all_intake[:12])
        else:
            md_lines.append("- 今日暂无饮食记录，平时随时发一句吃过什么即可，不用等回复。")
        md_lines.extend(
            [
                "",
                "### 3. 动态计划与明日建议",
                f"- 当前阶段：{ap.get('phase_name') or '动态适应期'}（目标 {ap.get('target_weight') or '70'}kg）",
                "- 明天晨起空腹称一次体重，午餐/晚餐随手发一条简短记录即可。",
            ]
        )

        return {
            "kind": "daily_report",
            "report_date": report_date,
            "title": f"{report_date} 睡前体重与健康日报",
            "summary": summary,
            "body_markdown": "\n".join(md_lines),
            "weight_snapshot": {
                "latest_kg": latest_kg,
                "delta_from_prev": delta,
                "avg_7d": avg_7d,
                "trend_7d": wm.get("trend_7d", "unknown"),
                "recorded_today": bool(wm.get("recorded_today")),
                "target_kg": ap.get("target_weight") or "70",
            },
            "diet_summary": {
                "count": len(all_intake),
                "items": all_intake[:10],
            },
            "plan_update": {
                "phase_name": ap.get("phase_name") or "动态适应期",
                "plan_version": ap.get("plan_version") or "",
                "ai_summary": ap.get("ai_summary") or "",
            },
            "tomorrow_focus": [
                "晨起空腹称一次体重",
                "白天吃过的正餐随手发一句文字记录",
                "保证今晚充足睡眠，压力优先于热量",
            ],
            "push": True,
        }

    # ── PLAN ──────────────────────────────────────────────────────────

    async def _plan(self, context: Dict[str, Any], tick: dict) -> Dict[str, Any]:
        policy = self._policy()
        max_tickets = max(0, min(2, int(policy.get("max_tickets_per_tick", 2))))

        if (
            not policy.get("allow_llm", True)
            or self.llm.budget_exceeded
            or self.state.get("llm")["status"] != "ok"
        ):
            plan = copy.deepcopy(FALLBACK_PLANS.get(tick["slot"], DEFAULT_FALLBACK_PLAN))
            plan["tickets"] = self._throttle_tickets(plan.get("tickets", []), context, max_tickets)
            if tick["slot"] == "pre_sleep_report" and not any(
                a.get("kind") == "daily_report" for a in plan.get("actions", [])
            ):
                plan.setdefault("actions", []).append(
                    self._build_deterministic_daily_report_action(context, tick)
                )
            context["plan_source"] = "fallback"
            await self.memory.save_episode(
                tick["id"],
                "plan",
                {"source": "fallback", "mode": policy["mode"], "summary": plan.get("summary", "")},
            )
            await self.db.update_tick(tick["id"], plan=plan)
            return plan

        prompt = self._build_plan_prompt(context, tick)
        tracer: Optional[TickTraceRecorder] = context.get("tracer")
        if tracer is not None:
            with tracer.span(
                "llm_call",
                "LLM 规划生成",
                input_summary=f"prompt_chars={len(prompt)} expect_json=True",
            ) as llm_sp:
                try:
                    resp = await self.llm.chat(prompt, expect_json=True, max_tokens=3000)
                    usage = getattr(resp, "usage", None) or {}
                    p_tok = int(usage.get("prompt_tokens", 0) or 0)
                    c_tok = int(usage.get("completion_tokens", 0) or 0)
                    t_tok = int(usage.get("total_tokens", 0) or (p_tok + c_tok))
                    cost_usd = float(getattr(resp, "cost_usd", 0.0) or 0.0)
                    tracer.add_llm_usage(p_tok, c_tok, t_tok, cost_usd)
                    raw_content = str(getattr(resp, "content", "") or "")
                    reasoning = str(getattr(resp, "reasoning_content", "") or "")
                    finish_reason = str(getattr(resp, "finish_reason", "") or "")
                    llm_sp.set_payload(
                        {
                            "provider": getattr(resp, "provider", ""),
                            "model": getattr(resp, "model", ""),
                            "latency_ms": float(getattr(resp, "latency_ms", 0.0) or 0.0),
                            "finish_reason": finish_reason,
                            "prompt_chars": len(prompt),
                            "response_chars": len(raw_content),
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                            "total_tokens": t_tok,
                            "cost_usd": cost_usd,
                            "prompt_text": prompt,
                            "response_text": raw_content,
                            "reasoning_content": reasoning,
                        }
                    )
                    plan = json.loads(self._extract_json(raw_content))
                    self._validate_plan(plan)
                    llm_sp.update_payload(parse_ok=True)
                    llm_sp.set_output(
                        f"model={getattr(resp, 'model', '')} tokens={t_tok} "
                        f"finish={finish_reason or 'stop'} parse=ok"
                    )
                    context["plan_source"] = "llm"
                    context["llm_latency_ms"] = getattr(resp, "latency_ms", 0.0)
                except Exception as exc:
                    logger.warning("PLAN llm failed, fallback to rule template: %s", exc)
                    llm_sp.update_payload(parse_ok=False, prompt_text=prompt)
                    llm_sp.mark_status("error", f"{type(exc).__name__}: {exc}")
                    llm_sp.set_output(f"fallback_error: {type(exc).__name__}")
                    plan = copy.deepcopy(FALLBACK_PLANS.get(tick["slot"], DEFAULT_FALLBACK_PLAN))
                    context["plan_source"] = "fallback_error"
                    context["llm_error"] = str(exc)
        else:
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

        # 票据节流 + 防轰炸护栏
        tickets = self._throttle_tickets(plan.get("tickets", []), context, max_tickets)
        plan["tickets"] = tickets

        # pre_sleep_report 兜底保障：确保每晚睡前一定产出一份结构化日报
        if tick["slot"] == "pre_sleep_report" and not any(
            a.get("kind") == "daily_report" for a in plan.get("actions", [])
        ):
            plan.setdefault("actions", []).append(
                self._build_deterministic_daily_report_action(context, tick)
            )

        ep_payload: Dict[str, Any] = {
            "source": context["plan_source"],
            "mode": policy["mode"],
            "summary": plan.get("summary", ""),
        }
        if context.get("llm_error"):
            ep_payload["error"] = context["llm_error"]
        await self.memory.save_episode(tick["id"], "plan", ep_payload)
        await self.db.update_tick(tick["id"], plan=plan)
        logger.info("PLAN ok: source=%s tickets=%d actions=%d", context["plan_source"], len(tickets), len(plan.get("actions", [])))
        return plan

    def _build_plan_prompt(self, context: Dict[str, Any], tick: dict) -> str:
        system = self._load_prompt("coach/v1/system.md")
        slot_guidance = self._load_prompt(f"coach/v1/slot_{tick['slot']}.md", default="")

        prev: Optional[HandoffDoc] = context.get("prev_handoff")
        prev_text = prev.prev_summary if prev else "(首个 Tick)"
        plan_doc = context.get("active_plan")
        plan_text = (
            f"{plan_doc['version']}\n{plan_doc['content'][:800]}" if plan_doc else "(尚无计划)"
        )
        mem = context.get("memory_summary") or {}
        profile_text = mem.get("profile", "(空)")
        semantic_text = mem.get("semantic", "(空)")
        procedural_text = mem.get("procedural", "(空)")

        tickets_text = "\n".join(
            f"- #{t.get('id')} [{t.get('type')}] topic={t.get('topic') or '-'} {t.get('title')} (by {t.get('expected_reply_by')})"
            for t in context.get("pending_tickets", [])[:10]
        ) or "(无)"
        replies_text = "\n".join(
            f"- #{r.get('id')} {r.get('title')}: 用户回复「{r.get('reply', '')}」"
            for r in context.get("new_replies", [])[:10]
        ) or "(无)"
        unread_msgs = context.get("unread_messages") or []
        msgs_text = "\n".join(
            f"- #{m.get('id')} [{m.get('category')}] ({str(m.get('created_at', ''))[:16]}): {m.get('content', '')}"
            for m in unread_msgs[:15]
        ) or "(无)"

        candidates = self._select_candidate_questions(context, tick["slot"])
        q_slice_text = "\n".join(
            f"- topic={q.get('id')} (profile_key={q.get('target_profile_key')}): {q.get('question')} | 原因: {q.get('why')}"
            for q in candidates
        ) or "(本窗口无需新提问，或已有待回复问题)"

        weight_update_note = (
            "【有新的体重测量数据更新！请结合新体重评估趋势，按需通过 plan_update 调整 AI 动态计划】"
            if context.get("weight_updated")
            else "（自上次 Tick 以来暂无新体重测量）"
        )
        expert_brief_text = NightlySelfMaintenance.format_brief_for_prompt(
            context.get("expert_brief")
        )

        return f"""{system}

{slot_guidance}

# 当前计划
{plan_text}

# 夜间数学建模与深度洞察（专家简报）
{expert_brief_text}

# 用户画像与记忆
[Profile]
{profile_text}
[Semantic]
{semantic_text}
[Procedural]
{procedural_text}

# 上 Tick 摘要
{prev_text}

# 用户状态数据
{weight_update_note}
{context.get('data_summary', '(无数据)')}

# 新收到的用户票据回复（请吸收到 profile/diet 并可输出 resolve_ticket 关闭）
{replies_text}

# 用户主动发来的饮食/日常消息（无需即时回复，请吸收并整合进每日睡前日报）
{msgs_text}

# 当前尚未回复的票据
{tickets_text}

# 本窗口可选的渐进提问候选（严禁一次问多个，最多选 0~1 个！）
{q_slice_text}

# 任务
你是 SailTick 的 PLAN 阶段。基于以上信息为「{tick['slot']}」（日期 {tick.get('tick_date')}）生成本窗口计划。
只输出严格合法的 JSON：
{{
  "summary": "本 Tick 要点（1-2 句）",
  "tickets": [
    {{
      "type": "question|task|info",
      "topic": "话题唯一键，如 weight_checkin / diet_lunch / profile_wake_time",
      "title": "票据标题（简短，推送通知标题）",
      "body": "正文（温和具体，含为什么问这个）",
      "priority": "low|normal|high",
      "expected_reply_hours": 36,
      "fallback_assumption": "用户不回复时采用的假设",
      "meta": {{"quick_replies": ["可选快捷回复1", "可选快捷回复2"]}}
    }}
  ],
  "actions": [
    {{"kind": "profile_update", "key": "wake_time", "value": "07:30", "confidence": 0.9, "source": "asked"}},
    {{"kind": "memory", "memory_type": "semantic", "key": "diet_pattern", "value": "..."}},
    {{"kind": "diet_log", "meal_type": "lunch", "description": "食堂鸡胸肉+米饭半碗", "calories": 550}},
    {{"kind": "plan_update", "plan_version": "v1.1", "target_weight": "70.0", "phase_name": "稳态适应期", "phase_rationale": "原因", "focus_notes": "关注点", "tolerance_kg": 0.7, "ai_summary": "健康页一句话评语", "daily_targets": {{"{tick.get('tick_date')}": 74.5}}, "content": "完整计划 Markdown"}},
    {{"kind": "daily_report", "report_date": "{tick.get('tick_date')}", "title": "{tick.get('tick_date')} 睡前体重与健康日报", "summary": "1-2句睡前摘要", "body_markdown": "完整日报 Markdown", "weight_snapshot": {{}}, "diet_summary": {{}}, "plan_update": {{}}, "tomorrow_focus": ["建议1", "建议2"], "push": true}},
    {{"kind": "resolve_ticket", "ticket_id": 1, "resolution": "已吸收至画像"}},
    {{"kind": "episode", "content": "要记入事件流的内容"}}
  ],
  "unfinished": [{{"task": "未完成事项", "reason": "原因"}}],
  "next_tick_suggestions": ["给下个 Tick 的建议"]
}}
注意：
1. actions 仅输出本窗口真正需要的项（不需要的类别直接不放）；
2. tickets 最多 1 张提问（总数最多 2 张）；若已有未回复提问或处于睡前/夜间窗口，tickets 留空 []；
3. 保持温和不苛责的语气，压力与睡眠优先于热量。"""

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
        work_results: List[Dict[str, Any]] = []

        ticket_items = plan.get("tickets", [])
        action_items = plan.get("actions", [])

        # shadow 模式：完整记录拟发射票据与动作，不产生外部副作用
        if policy["mode"] == "shadow" or not policy.get("allow_ticket_create", True):
            for t in ticket_items:
                shadow_emitted.append(
                    {
                        "title": t.get("title", "(无标题)"),
                        "type": t.get("type", "question"),
                        "topic": t.get("topic", ""),
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
                    "action_kinds": [a.get("kind") for a in action_items if isinstance(a, dict)],
                },
            )
            context["emitted"] = []
            context["shadow_emitted"] = shadow_emitted
            context["work_results"] = []
            logger.info(
                "WORK [shadow]: simulated tickets=%d actions=%d (zero side effects)",
                len(shadow_emitted),
                len(action_items),
            )
            return

        prefix = policy.get("ticket_title_prefix") or ""
        suppress_push = not bool(policy.get("allow_push", True))
        topic_history = dict(context.get("topic_history") or {})
        tracer: Optional[TickTraceRecorder] = context.get("tracer")

        for idx, t in enumerate(ticket_items):
            if self._clock() > deadline:
                for rest in ticket_items[idx:]:
                    plan.setdefault("unfinished", []).append(
                        {"task": f"发票据: {rest.get('title')}", "reason": "预算耗尽", "priority": "high"}
                    )
                break
            raw_title = t.get("title", "(无标题)")
            title = f"{prefix}{raw_title}" if prefix and not raw_title.startswith(prefix) else raw_title
            topic = str(t.get("topic") or "").strip()
            if tracer is not None:
                with tracer.span(
                    "ticket_emit",
                    f"发送票据: {title[:48]}",
                    input_summary=f"type={t.get('type', 'question')} priority={t.get('priority', 'normal')} topic={topic or '-'}",
                ) as tsp:
                    result = await self.notifier.emit(
                        title=title,
                        content=t.get("body", ""),
                        priority=t.get("priority", "normal"),
                        ticket_type=t.get("type", "question"),
                        tick_id=tick["id"],
                        channel=t.get("channel", "mobile"),
                        expected_reply_hours=t.get("expected_reply_hours"),
                        fallback_assumption=t.get("fallback_assumption", ""),
                        suppress_push=suppress_push,
                        topic=topic,
                        meta=t.get("meta") if isinstance(t.get("meta"), dict) else {},
                    )
                    tsp.set_output(f"ticket_id={result.get('ticket_id')} action={result.get('action', '')}")
                    tsp.set_payload({"title": title, "topic": topic, "result": result})
                    if not result.get("ticket_id"):
                        tsp.mark_status("degraded", str(result.get("reason") or "not created"))
            else:
                result = await self.notifier.emit(
                    title=title,
                    content=t.get("body", ""),
                    priority=t.get("priority", "normal"),
                    ticket_type=t.get("type", "question"),
                    tick_id=tick["id"],
                    channel=t.get("channel", "mobile"),
                    expected_reply_hours=t.get("expected_reply_hours"),
                    fallback_assumption=t.get("fallback_assumption", ""),
                    suppress_push=suppress_push,
                    topic=topic,
                    meta=t.get("meta") if isinstance(t.get("meta"), dict) else {},
                )
            emitted.append({"title": title, "result": result})
            if result.get("ticket_id"):
                if topic:
                    topic_history[topic] = self._clock().isoformat()
                await self.memory.save_episode(
                    tick["id"], "work", {"ticket_created": result["ticket_id"], "title": title, "topic": topic}
                )

        if topic_history != (context.get("topic_history") or {}):
            await self.db.set_runtime_state("asked_topics", topic_history)

        from contextlib import nullcontext

        for idx, a in enumerate(action_items):
            if self._clock() > deadline:
                for rest in action_items[idx:]:
                    plan.setdefault("unfinished", []).append(
                        {"task": f"动作: {rest.get('kind')}", "reason": "预算耗尽", "priority": "normal"}
                    )
                break
            if not isinstance(a, dict):
                continue
            kind = str(a.get("kind") or "unknown")
            before_len = len(work_results)

            span_ctx = (
                tracer.span("work_action", f"动作: {kind}", input_summary=str(a)[:240])
                if tracer is not None
                else nullcontext(None)
            )
            with span_ctx as asp:
                if kind == "episode":
                    await self.memory.save_episode(tick["id"], "work", a.get("content"))
                    work_results.append({"kind": "episode", "ok": True})

                elif kind == "memory":
                    await self.memory.save(
                        a.get("memory_type", "semantic"), a.get("key", "misc"), a.get("value")
                    )
                    work_results.append({"kind": "memory", "key": a.get("key"), "ok": True})

                elif kind == "profile_update":
                    pkey = str(a.get("key") or "").strip()
                    if pkey:
                        await self.memory.set_profile(
                            pkey,
                            a.get("value"),
                            confidence=float(a.get("confidence", 0.85)),
                            source=str(a.get("source", "asked")),
                        )
                        work_results.append({"kind": "profile_update", "key": pkey, "ok": True})

                elif kind == "diet_log" and context.get("server_ok"):
                    try:
                        diet_payload = {
                            "meal_type": a.get("meal_type", "snack"),
                            "description": str(a.get("description") or ""),
                        }
                        if a.get("calories") is not None:
                            diet_payload["calories"] = float(a["calories"])
                        if a.get("protein") is not None:
                            diet_payload["protein"] = float(a["protein"])
                        res = await self.inbox.create_diet_log(diet_payload)
                        work_results.append({"kind": "diet_log", "id": res.get("id"), "ok": True})
                    except Exception as exc:
                        logger.warning("WORK diet_log failed (non-fatal): %s", exc)
                        work_results.append({"kind": "diet_log", "ok": False, "error": str(exc)})

                elif kind == "plan_update":
                    # 1. 本地 st_plans 留档
                    version = str(a.get("plan_version") or f"v{self._clock().strftime('%m%d.%H')}")
                    goal = str(a.get("target_weight") or "70.0")
                    content_md = str(
                        a.get("content")
                        or f"# {a.get('phase_name', 'AI 动态计划')}\n\n{a.get('phase_rationale', '')}\n\n{a.get('focus_notes', '')}"
                    )
                    rationale = str(a.get("phase_rationale") or a.get("rationale") or "")
                    await self.db.create_plan(version, f"{goal}kg", content_md, rationale, active=True)
                    # 2. 同步写回 sail_server 健康页 AI 动态体重计划
                    if context.get("server_ok"):
                        try:
                            sync_payload = {
                                "target_weight": goal,
                                "plan_version": version,
                                "phase_name": str(a.get("phase_name") or "动态适应期"),
                                "phase_rationale": rationale,
                                "focus_notes": str(a.get("focus_notes") or ""),
                                "daily_targets": a.get("daily_targets") if isinstance(a.get("daily_targets"), dict) else {},
                                "tolerance_kg": float(a.get("tolerance_kg", 0.7)),
                                "ai_summary": str(a.get("ai_summary") or plan.get("summary") or ""),
                            }
                            if a.get("initial_weight"):
                                sync_payload["initial_weight"] = str(a["initial_weight"])
                            if a.get("description"):
                                sync_payload["description"] = str(a["description"])
                            synced = await self.inbox.sync_ai_weight_plan(sync_payload)
                            work_results.append({"kind": "plan_update", "plan_id": synced.get("id"), "version": version, "ok": True})
                        except Exception as exc:
                            logger.warning("WORK plan_update sync to sail_server failed: %s", exc)
                            work_results.append({"kind": "plan_update", "version": version, "ok": False, "error": str(exc)})
                    else:
                        work_results.append({"kind": "plan_update", "version": version, "ok": True, "local_only": True})

                elif kind == "daily_report" and context.get("server_ok"):
                    try:
                        report_date = str(a.get("report_date") or tick.get("tick_date") or self._clock().strftime("%Y-%m-%d"))
                        should_push = bool(a.get("push", True)) and not suppress_push and not self.notifier.in_quiet_hours()
                        rep_payload = {
                            "report_date": report_date,
                            "tick_id": tick["id"],
                            "title": str(a.get("title") or f"{report_date} 睡前体重与健康日报"),
                            "summary": str(a.get("summary") or plan.get("summary") or ""),
                            "body_markdown": str(a.get("body_markdown") or ""),
                            "weight_snapshot": a.get("weight_snapshot") if isinstance(a.get("weight_snapshot"), dict) else {},
                            "diet_summary": a.get("diet_summary") if isinstance(a.get("diet_summary"), dict) else {},
                            "plan_update": a.get("plan_update") if isinstance(a.get("plan_update"), dict) else {},
                            "tomorrow_focus": a.get("tomorrow_focus") if isinstance(a.get("tomorrow_focus"), list) else [],
                            "push": should_push,
                        }
                        rep = await self.inbox.upsert_daily_report(rep_payload)
                        work_results.append({"kind": "daily_report", "report_date": report_date, "id": rep.get("id"), "pushed": rep.get("pushed"), "ok": True})
                    except Exception as exc:
                        logger.warning("WORK daily_report failed (non-fatal): %s", exc)
                        work_results.append({"kind": "daily_report", "ok": False, "error": str(exc)})

                elif kind == "resolve_ticket" and context.get("server_ok"):
                    tid = a.get("ticket_id")
                    if tid is not None:
                        try:
                            await self.inbox.resolve_ticket(int(tid), str(a.get("resolution") or "已吸收"))
                            work_results.append({"kind": "resolve_ticket", "ticket_id": int(tid), "ok": True})
                        except Exception as exc:
                            logger.warning("WORK resolve_ticket #%s failed: %s", tid, exc)
                            work_results.append({"kind": "resolve_ticket", "ticket_id": tid, "ok": False, "error": str(exc)})

                elif kind == "dev_task" and self.dev_runner is not None:
                    if not policy.get("allow_self_dev", True):
                        await self.memory.save_episode(
                            tick["id"],
                            "dev_skipped",
                            {"task": a.get("task_id", ""), "reason": f"disabled_in_mode:{policy['mode']}"},
                        )
                        if asp is not None:
                            asp.mark_status("skipped", f"disabled_in_mode:{policy['mode']}")
                        continue
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
                        tick["id"],
                        "dev",
                        {
                            "task": task.id,
                            "success": result.success,
                            "commit": result.commit,
                            "ticket": result.ticket_id,
                            "error": result.error,
                        },
                    )
                    work_results.append({"kind": "dev_task", "task": task.id, "ok": result.success})

                elif kind == "nightly_food_research":
                    foods_list = list(a.get("foods") or [])
                    if foods_list:
                        await self._get_nightly().knowledge.enqueue_food_research(foods_list)
                    stage1 = context.get("nightly_stage1") or {}
                    res_food = await self._get_nightly().knowledge.run_nightly_food_research(
                        stage1.get("deep_pkg") or {},
                        max_foods=int(a.get("max_foods") or self.config.nightly.max_foods_per_night),
                    )
                    work_results.append({"kind": "nightly_food_research", **res_food, "ok": True})

                elif kind == "nightly_knowledge_curation":
                    domains = list(a.get("domains") or ["diet", "exercise", "psychology"])
                    stage1 = context.get("nightly_stage1") or {}
                    ins = ((stage1.get("modeling") or {}).get("insights")) or []
                    res_kn = await self._get_nightly().knowledge.run_nightly_knowledge_curation(
                        focus_domains=domains,
                        insights=ins,
                        max_items=int(a.get("max_items") or self.config.nightly.max_knowledge_per_night),
                    )
                    work_results.append({"kind": "nightly_knowledge_curation", **res_kn, "ok": True})

                if asp is not None:
                    if len(work_results) > before_len:
                        last_res = work_results[-1]
                        asp.set_payload({"action": a, "result": last_res})
                        asp.set_output(f"ok={last_res.get('ok')}")
                        if last_res.get("ok") is False:
                            asp.mark_status("error", str(last_res.get("error") or "failed"))
                    else:
                        asp.mark_status("skipped", "precondition_not_met")
                        asp.set_output("skipped")

        # 夜间自维护（阶段2）：自动完成未知食物热量查证 + 专业健康师知识整理 + 刷新专家简报
        # 仅在真实 LLMGateway 或显式 params.run_research=True 时执行，避免干扰 ScriptedLLM 单步回放测试
        if (
            tick["slot"] == "nightly_maintenance"
            and self.config.nightly.enabled
            and (
                isinstance(self.llm, LLMGateway)
                or bool((context.get("params") or {}).get("run_research"))
            )
            and self._clock() <= deadline
        ):
            try:
                stage1 = context.get("nightly_stage1") or {}
                stage2 = await self._get_nightly().run_research_stage(
                    deep_pkg=stage1.get("deep_pkg"),
                    model_result=stage1.get("modeling"),
                    saved_snapshot=stage1.get("saved_snapshot"),
                    tick_id=tick["id"],
                    tracer=tracer,
                )
                context["expert_brief"] = stage2.get("expert_brief")
                work_results.append(
                    {
                        "kind": "nightly_research",
                        "foods_researched": stage2["food_research"].get("researched_names", []),
                        "knowledge_curated": stage2["knowledge_curation"].get("curated_topics", []),
                        "ok": True,
                    }
                )
            except Exception as exc:
                logger.warning("WORK nightly research stage failed (non-fatal): %s", exc)
                work_results.append({"kind": "nightly_research", "ok": False, "error": str(exc)})

        # 标记本 Tick 已阅读并整合的用户主动消息（仅在真实执行模式下落库）
        unread_ids = [
            int(m["id"])
            for m in (context.get("unread_messages") or [])
            if isinstance(m, dict) and m.get("id") is not None
        ]
        if unread_ids and context.get("server_ok"):
            try:
                ingested_cnt = await self.inbox.ingest_user_messages(unread_ids, tick["id"])
                work_results.append({"kind": "ingest_messages", "count": ingested_cnt, "ok": True})
            except Exception as exc:
                logger.warning("WORK ingest_user_messages failed (non-fatal): %s", exc)

        # 推进体重水位线与回复同步游标
        if context.get("current_weight_watermark"):
            await self.db.set_runtime_state(
                "last_weight_watermark", context["current_weight_watermark"]
            )
        if context.get("new_replies"):
            latest_ts = max(
                (str(r.get("updated_at") or r.get("replied_at") or "") for r in context["new_replies"]),
                default="",
            )
            if latest_ts:
                try:
                    dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                    if dt.tzinfo is not None:
                        dt = dt.astimezone().replace(tzinfo=None)
                    await self.db.set_runtime_state(
                        "tick_reply_cursor", (dt + timedelta(seconds=1)).isoformat()
                    )
                except ValueError:
                    pass

        context["emitted"] = emitted
        context["shadow_emitted"] = shadow_emitted
        context["work_results"] = work_results
        logger.info("WORK ok: emitted=%d actions=%d", len(emitted), len(work_results))

    # ── HANDOFF ───────────────────────────────────────────────────────

    async def _handoff(self, context: Dict[str, Any], tick: dict) -> str:
        plan = context.get("plan", {})
        mode = context.get("mode", "live")
        summary_text = plan.get("summary", "")
        if mode == "shadow" and summary_text and not summary_text.startswith("[shadow]"):
            summary_text = f"[shadow] {summary_text}"
        latest_plan = await self.db.get_active_plan()
        doc = HandoffDoc(
            tick_id=tick["id"],
            slot=tick["slot"],
            tick_date=tick["tick_date"],
            prev_summary=summary_text,
            unfinished=plan.get("unfinished", []),
            plan_version=(latest_plan or context.get("active_plan") or {}).get("version", "(无)"),
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

    def _load_prompt(self, rel_path: str, default: str = "(system prompt 未找到)") -> str:
        path = os.path.join(self._prompts_dir, rel_path) if self._prompts_dir else ""
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return default

    def current_tick(self) -> Optional[dict]:
        return self._current_tick
