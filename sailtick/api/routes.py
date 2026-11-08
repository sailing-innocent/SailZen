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

from litestar import Litestar, Router, get, post


def create_app(daemon: Any) -> Litestar:
    """创建管理 API Litestar app。"""

    @get("/health")
    async def health() -> Dict[str, Any]:
        return await daemon.get_health()

    @post("/tick/{slot:str}")
    async def trigger_tick(slot: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """异步触发一次 Tick。"""
        allowed = {"morning_checkin", "midday_checkin", "evening_review", "nightly_maintenance"}
        if slot not in allowed:
            return {"error": f"unknown slot: {slot}", "allowed": sorted(allowed)}
        import asyncio

        asyncio.create_task(daemon.engine.run_tick(slot, params=data or {}))
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
        memory_type: Optional[str] = None, key_prefix: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        if memory_type:
            return await daemon.memory.list(memory_type, key_prefix=key_prefix)
        return await daemon.memory.list_episodes(limit=limit)

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
            list_profile,
            cost,
            schedules,
        ],
    )
    return Litestar(route_handlers=[router], debug=False)
