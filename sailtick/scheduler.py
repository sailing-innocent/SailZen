# -*- coding: utf-8 -*-
# @file scheduler.py
# @brief TickScheduler — APScheduler 6h 唤醒 + fallback 触发回调
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""TickScheduler — 从旧 autonomous_agent/scheduler.py 迁移修复。

修复点（迁移说明 B3）:
  - 旧实现 ``register_trigger_callback("*", cb)`` 与精确查找不匹配，定时触发永不生效；
    本实现提供 ``register_default_callback``，触发时先精确查找，未命中走默认回调。
  - jobstore 指向 sailtick.db（apscheduler_jobs 表），重启不丢排程。
  - 增加 missed-tick 检测与补跑（最多补 1 个，设计文档 §3.3）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sailtick.db import TickDatabase

logger = logging.getLogger(__name__)


class TickScheduler:
    """SailTick 唤醒排程器。"""

    def __init__(self, db: TickDatabase, timezone: str = "Asia/Shanghai"):
        self.db = db
        self.timezone = timezone
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._callbacks: Dict[str, Callable] = {}
        self._default_callback: Optional[Callable] = None

    def register_callback(self, slot: str, callback: Callable) -> None:
        """按 slot 精确注册触发回调。"""
        self._callbacks[slot] = callback

    def register_default_callback(self, callback: Callable) -> None:
        """默认回调：精确匹配未命中时使用（修复 B3 的关键）。"""
        self._default_callback = callback

    # ── 生命周期 ──────────────────────────────────────────────────────

    async def start(self) -> None:
        # 排程元数据与 last_run_time 持久化在 st_schedules（走 aiosqlite），
        # APScheduler 本身使用默认 MemoryJobStore，避免：
        # 1) SQLAlchemyJobStore 同步调用 aiosqlite sync_engine 报 MissingGreenlet；
        # 2) SQLAlchemyJobStore pickle 绑定方法 self._on_trigger 报 PicklingError；
        # 3) 双驱动并发写同一 SQLite 文件产生 database is locked。
        self._scheduler = AsyncIOScheduler(timezone=self.timezone)
        self._scheduler.start()
        logger.info("TickScheduler started (timezone=%s)", self.timezone)
        await self._restore_schedules()
        await self.catch_up_missed_ticks()

    async def stop(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=True)
            self._scheduler = None
            logger.info("TickScheduler stopped")

    # ── 排程管理 ──────────────────────────────────────────────────────

    async def add_slot(
        self,
        schedule_id: str,
        name: str,
        slot: str,
        hour: int,
        minute: int = 0,
        **params: Any,
    ) -> dict:
        """注册一个定时唤醒 slot（支持分钟级精度，如 hour=21, minute=45 → 21:45）。"""
        if not self._scheduler:
            raise RuntimeError("Scheduler not started")
        trigger = CronTrigger(minute=minute, hour=hour, timezone=self.timezone)
        job = self._scheduler.add_job(
            func=self._on_trigger,
            trigger=trigger,
            id=schedule_id,
            name=name,
            replace_existing=True,
            kwargs={"schedule_id": schedule_id, "slot": slot, "params": params},
        )
        data = {
            "id": schedule_id,
            "name": name,
            "slot": slot,
            "enabled": True,
            "params": {**params, "hour": hour, "minute": minute},
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        await self.db.create_schedule(data)
        logger.info("Added slot %s (%02d:%02d)", schedule_id, hour, minute)
        return data

    async def list_schedules(self) -> List[dict]:
        return await self.db.list_schedules(enabled_only=False)

    async def remove(self, schedule_id: str) -> bool:
        if self._scheduler:
            try:
                self._scheduler.remove_job(schedule_id)
            except Exception:
                pass
        return await self.db.delete_schedule(schedule_id)

    async def next_run_times(self) -> List[dict]:
        if not self._scheduler:
            return []
        out = []
        for job in self._scheduler.get_jobs():
            nrt = job.next_run_time
            out.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": nrt.isoformat() if nrt else None,
                }
            )
        return out

    # ── 触发 ──────────────────────────────────────────────────────────

    async def _on_trigger(self, schedule_id: str, slot: str, params: dict) -> None:
        logger.info("Tick triggered: schedule=%s slot=%s", schedule_id, slot)
        await self.db.update_schedule(schedule_id, {
            "last_run_time": datetime.now().isoformat(),
            "last_run_status": "started",
        })
        callback = self._callbacks.get(slot) or self._default_callback
        if callback is None:
            logger.warning("No callback for slot=%s and no default callback", slot)
            await self.db.update_schedule(schedule_id, {"last_run_status": "failed"})
            return
        try:
            await callback(slot=slot, schedule_id=schedule_id, params=params)
            await self.db.update_schedule(schedule_id, {"last_run_status": "success"})
        except Exception:
            logger.exception("Tick callback failed for slot=%s", slot)
            await self.db.update_schedule(schedule_id, {
                "last_run_status": "failed",
                "params": params,
            })

    async def trigger_now(self, slot: str, params: Optional[dict] = None) -> None:
        """手动触发（CLI / 管理 API）。"""
        await self._on_trigger(
            schedule_id=f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            slot=slot,
            params=params or {},
        )

    # ── 恢复与补跑 ────────────────────────────────────────────────────

    async def _restore_schedules(self) -> None:
        """从 DB 恢复排程（APScheduler jobstore 已自动恢复，此处同步元数据）。"""
        schedules = await self.db.list_schedules(enabled_only=False)
        for s in schedules:
            if not s.get("enabled"):
                continue
            job = self._scheduler.get_job(s["id"]) if self._scheduler else None
            if job:
                await self.db.update_schedule(s["id"], {
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                })
                logger.info("Restored schedule %s", s["id"])

    async def catch_up_missed_ticks(self, tick_engine: Any = None) -> int:
        """补跑错过的 tick（最多补 1 个）。

        比较各 slot 的 last_run_time 与本日应触发时刻；若最近 slot 已过且未跑，
        交给 tick_engine 补跑。返回补跑数。
        """
        engine = tick_engine or getattr(self, "_tick_engine", None)
        if engine is None:
            return 0
        now = datetime.now()
        caught = 0
        for hour in sorted(engine.config.tick.hours):
            expected = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if expected >= now:
                continue
            schedules = await self.db.list_schedules(enabled_only=True)
            slot_name = next((s["slot"] for s in schedules if s["id"].endswith(f"_{hour:02d}")), None)
            if not slot_name:
                continue
            last = next((s.get("last_run_time") for s in schedules if s["slot"] == slot_name), None)
            if last:
                last_dt = datetime.fromisoformat(last)
                if last_dt >= expected:
                    continue  # 已跑
            if caught >= 1:
                logger.info("Missed tick for slot=%s skipped (catch-up limit=1)", slot_name)
                continue
            logger.warning("Missed tick detected: slot=%s expected=%s", slot_name, expected)
            await engine.run_tick(slot_name, catch_up=True)
            caught += 1
        return caught
