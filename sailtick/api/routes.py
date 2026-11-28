# -*- coding: utf-8 -*-
# @file routes.py
# @brief SailTick 管理 API（:9070）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 管理 API。

端点:
  GET  /health           健康/统计/排程/依赖/成本
  POST /tick/{slot}      手动触发某 slot 的 Tick（异步执行）
  GET  /tick/current     当前运行中的 tick
  GET  /ticks            最近 tick 列表
  GET  /handoffs         最近 handoff 列表
  GET  /handoffs/latest  最新 handoff 文档内容
  GET  /plans            计划版本历史
  GET  /plans/active     当前生效计划
  GET  /memory           记忆检索
  GET  /profile          用户画像
  GET  /cost             成本统计
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from litestar import Litestar, Request, Router, get, post
from litestar.exceptions import NotAuthorizedException


def create_app(daemon: Any) -> Litestar:
    """创建管理 API Litestar app。"""

    @get("/health")
    async def health() -> Dict[str, Any]:
        return await daemon.get_health()

    @post("/tick/{slot:str}")
    async def trigger_tick(slot: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """异步触发一次 Tick。"""
        allowed = {
            "morning_checkin",
            "midday_checkin",
            "evening_review",
            "pre_sleep_report",
            "nightly_maintenance",
        }
        try:
            for s in daemon.config.tick.resolved_slots():
                if s.slot:
                    allowed.add(s.slot)
        except Exception:
            pass
        if slot not in allowed:
            return {"error": f"unknown slot: {slot}", "allowed": sorted(allowed)}
        import asyncio

        body = dict(data or {})
        idem_suffix = body.pop("idempotency_suffix", None)
        asyncio.create_task(
            daemon.engine.run_tick(
                slot,
                params=body,
                idempotency_suffix=str(idem_suffix) if idem_suffix else None,
            )
        )
        return {"status": "triggered", "slot": slot}

    @get("/tick/current")
    async def current_tick() -> Dict[str, Any]:
        return {"tick": daemon.engine.current_tick()}

    @get("/ticks")
    async def list_ticks(limit: int = 20) -> List[Dict[str, Any]]:
        return await daemon.db.list_ticks(limit=limit)

    @get("/handoffs")
    async def list_handoffs(limit: int = 20) -> List[Dict[str, Any]]:
        return await daemon.db.list_handoffs(limit=limit)

    @get("/handoffs/latest")
    async def latest_handoff() -> Dict[str, Any]:
        doc = await daemon.handoffs.read_latest()
        if not doc:
            return {}
        return {
            "tick_id": doc.tick_id,
            "slot": doc.slot,
            "tick_date": doc.tick_date,
            "summary": doc.prev_summary,
            "unfinished": doc.unfinished,
            "plan_version": doc.plan_version,
        }

    @get("/plans")
    async def list_plans(limit: int = 20) -> List[Dict[str, Any]]:
        return await daemon.db.list_plans(limit=limit)

    @get("/plans/active")
    async def active_plan() -> Dict[str, Any]:
        plan = await daemon.db.get_active_plan()
        return plan or {}

    @get("/memory")
    async def query_memory(
        memory_type: Optional[str] = None,
        key_prefix: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if memory_type:
            return await daemon.memory.list(memory_type, key_prefix=key_prefix, domain=domain)
        return await daemon.memory.list_episodes(limit=limit)

    @get("/memory/search")
    async def search_memory(
        q: str = "",
        domain: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """SQLite FTS5 毫秒级检索记忆/食物/知识。"""
        if not q.strip():
            return []
        return await daemon.memory.search(q, domain=domain, limit=limit)

    @get("/profile")
    async def list_profile() -> List[Dict[str, Any]]:
        return await daemon.memory.list_profile()

    @get("/cost")
    async def cost() -> Dict[str, Any]:
        ticks = await daemon.db.list_ticks(limit=100)
        return {
            "daily_tokens": await daemon.db.sum_cost_today(),
            "recent": [
                {
                    "slot": t["slot"],
                    "tick_date": t["tick_date"],
                    "state": t["state"],
                    "cost_tokens": t["cost_tokens"],
                    "cost_usd": t["cost_usd"],
                }
                for t in ticks
            ],
        }

    @get("/schedules")
    async def schedules() -> List[Dict[str, Any]]:
        return await daemon.scheduler.next_run_times()

    # ── 灰度一键开关与监控 ─────────────────────────────────────────────

    @get("/canary")
    async def canary_status() -> Dict[str, Any]:
        return daemon.canary.get_status()

    @post("/canary/switch")
    async def canary_switch(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = data or {}
        mode = body.get("mode")
        if not mode:
            return {"error": "mode is required (off|shadow|canary|live)"}
        reason = str(body.get("reason", ""))
        actor = str(body.get("actor", "api"))
        overrides = {
            k: v
            for k, v in body.items()
            if k not in ("mode", "reason", "actor")
        }
        try:
            return await daemon.canary.switch(mode, reason=reason, actor=actor, **overrides)
        except ValueError as exc:
            return {"error": str(exc)}

    @post("/canary/kill")
    async def canary_kill(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = data or {}
        return await daemon.canary.kill(
            reason=str(body.get("reason", "api kill-switch")),
            actor=str(body.get("actor", "api")),
        )

    @post("/canary/resume")
    async def canary_resume(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = data or {}
        target = str(body.get("mode", "canary"))
        reason = str(body.get("reason", "api resume"))
        actor = str(body.get("actor", "api"))
        overrides = {
            k: v
            for k, v in body.items()
            if k not in ("mode", "reason", "actor")
        }
        try:
            return await daemon.canary.resume(
                target_mode=target, reason=reason, actor=actor, **overrides
            )
        except ValueError as exc:
            return {"error": str(exc)}

    @get("/monitor")
    async def monitor(window_ticks: int = 50) -> Dict[str, Any]:
        return await daemon.get_monitor_snapshot(window_ticks=window_ticks)

    # ── AI Trace 查询（本地隔离库权威副本） ────────────────────────────

    @get("/traces")
    async def list_traces(
        limit: int = 50, slot: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return await daemon.db.list_traces(limit=limit, slot=slot, status=status)

    @get("/traces/{trace_id:str}")
    async def get_trace(trace_id: str) -> Dict[str, Any]:
        trace = await daemon.db.get_trace(trace_id)
        return trace or {"error": f"trace {trace_id} not found"}

    # ── 夜间专家结论 / 数学建模 / 食物与专业知识库 ─────────────────────

    @get("/expert/brief")
    async def expert_brief() -> Dict[str, Any]:
        """获取 SailTick 专家最新编译的简报（供快反助手与外部客户端秒级读取）。"""
        brief = await daemon.db.get_runtime_state("expert_brief")
        return brief or {}

    @get("/expert/brief/{domain:str}")
    async def expert_brief_by_domain(domain: str) -> Dict[str, Any]:
        """获取单域物化热视图（global_core | health | rhythm | finance）。"""
        if hasattr(daemon.db, "get_domain_brief"):
            item = await daemon.db.get_domain_brief(domain)
            if item:
                return item
        return {}

    @get("/modeling/latest")
    async def modeling_latest() -> Dict[str, Any]:
        snap = await daemon.db.get_latest_model_snapshot()
        return snap or {}

    @get("/modeling/history")
    async def modeling_history(limit: int = 14) -> List[Dict[str, Any]]:
        return await daemon.db.list_model_snapshots(limit=limit)

    @get("/knowledge/foods")
    async def list_foods(q: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        await daemon.knowledge.ensure_seeded()
        return await daemon.db.list_food_nutrition(limit=limit, query=q)

    @get("/knowledge/articles")
    async def list_knowledge(domain: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        await daemon.knowledge.ensure_seeded()
        return await daemon.db.list_knowledge_items(domain=domain, limit=limit)

    @post("/nightly/run")
    async def run_nightly(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """手动触发一次夜间深度自维护（长周期建模 + 食物查证 + 知识整理 + 刷新专家简报）。"""
        body = data or {}
        allow_llm = bool(body.get("allow_llm_research", True))
        return await daemon.nightly.run(allow_llm_research=allow_llm)

    # ── 白天快反对话 & QQ Bot (OneBot v11) ─────────────────────────────

    @post("/chat/quick")
    async def quick_chat(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """白天快速反应对话入口（支持 domain/persona 分域裁剪与跨端会话共享）。"""
        body = data or {}
        text = str(body.get("text") or body.get("message") or "").strip()
        channel = str(body.get("channel") or "api")
        user_id = str(body.get("user_id") or "owner")
        session_id = body.get("session_id")
        target_type = str(body.get("target_type") or "private")
        target_id = body.get("target_id")
        domain = str(body.get("domain") or "")
        surface = str(body.get("surface") or "")
        context_hints = body.get("context_hints") if isinstance(body.get("context_hints"), dict) else None
        return await daemon.quick_agent.handle_message(
            text=text,
            channel=channel,
            user_id=user_id,
            session_id=str(session_id) if session_id else None,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            domain=domain,
            surface=surface,
            context_hints=context_hints,
        )

    @get("/chat/quick/history")
    async def quick_chat_history(
        domain: str = "general",
        user_id: str = "owner",
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """拉取某业务域的跨端持久化快反对话历史。"""
        dom = daemon.quick_agent._resolve_domain(domain=domain)
        sess_key = session_id or f"{user_id or 'owner'}:{dom}"
        return await daemon.db.list_quick_chat_history(sess_key, limit=max(1, min(limit, 100)))

    @get("/nudges")
    async def list_nudges(limit: int = 30) -> List[Dict[str, Any]]:
        """查看待触发的本地提醒队列。"""
        return await daemon.db.list_pending_nudges(limit=limit)

    @post("/onebot/webhook")
    async def onebot_webhook(request: Request) -> Dict[str, Any]:
        """标准 OneBot v11 HTTP Post Webhook（直接对接 NapCat/Lagrange/LLOneBot）。"""
        raw_body = await request.body()
        sig = request.headers.get("X-Signature", "")
        if not daemon.qq_bot.verify_signature(raw_body, sig):
            raise NotAuthorizedException(detail="invalid X-Signature")
        import json as _json

        try:
            event = _json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            return {"status": "ignored", "reason": "invalid_json"}
        return await daemon.qq_bot.handle_event(event)

    router = Router(
        path="/",
        route_handlers=[
            health,
            trigger_tick,
            current_tick,
            list_ticks,
            list_handoffs,
            latest_handoff,
            list_plans,
            active_plan,
            query_memory,
            search_memory,
            list_profile,
            cost,
            schedules,
            canary_status,
            canary_switch,
            canary_kill,
            canary_resume,
            monitor,
            list_traces,
            get_trace,
            expert_brief,
            expert_brief_by_domain,
            modeling_latest,
            modeling_history,
            list_foods,
            list_knowledge,
            run_nightly,
            quick_chat,
            quick_chat_history,
            list_nudges,
            onebot_webhook,
        ],
    )
    return Litestar(route_handlers=[router], debug=False)
