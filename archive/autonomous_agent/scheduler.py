# -*- coding: utf-8 -*-
# @file scheduler.py
# @brief CronScheduler — APScheduler wrapper for agent pipelines
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""CronScheduler — persistent scheduling for autonomous agent pipelines.

Uses APScheduler with SQLAlchemyJobStore pointing to agent.db.
Schedules survive daemon restarts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from sailzen.autonomous_agent.db import AgentDatabase

logger = logging.getLogger(__name__)


class CronScheduler:
    """APScheduler wrapper for agent pipeline scheduling."""

    def __init__(self, db: AgentDatabase, timezone: str = "Asia/Shanghai"):
        self.db = db
        self.timezone = timezone
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._trigger_callbacks: Dict[str, Callable] = {}

    async def start(self) -> None:
        """Start the scheduler with SQLAlchemy job store."""
        jobstores = {
            "default": SQLAlchemyJobStore(
                engine=self.db.engine.sync_engine,
                tablename="apscheduler_jobs",
            )
        }

        self._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=self.timezone,
        )
        self._scheduler.start()
        logger.info("CronScheduler started with timezone=%s", self.timezone)

        # Restore schedules from agent_schedules table
        await self._restore_schedules()

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=True)
            self._scheduler = None
            logger.info("CronScheduler stopped")

    def register_trigger_callback(self, pipeline_id: str, callback: Callable) -> None:
        """Register a callback function for when a pipeline is triggered."""
        self._trigger_callbacks[pipeline_id] = callback

    # ── Schedule management ───────────────────────────────────────────

    async def add_cron(self, schedule_id: str, name: str, pipeline_id: str,
                       cron_expr: str, params: Optional[dict] = None,
                       enabled: bool = True) -> dict:
        """Add a cron schedule.

        Args:
            schedule_id: Unique schedule ID
            name: Human-readable name
            pipeline_id: Target pipeline ID
            cron_expr: Cron expression (e.g. "0 8 * * 1-5")
            params: Runtime params for the pipeline
            enabled: Whether schedule is active
        """
        if not self._scheduler:
            raise RuntimeError("Scheduler not started")

        # Parse cron expression: minute hour day month day_of_week
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}. Expected 5 parts.")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=self.timezone,
        )

        job = self._scheduler.add_job(
            func=self._on_trigger,
            trigger=trigger,
            id=schedule_id,
            name=name,
            replace_existing=True,
            kwargs={
                "schedule_id": schedule_id,
                "pipeline_id": pipeline_id,
                "params": params or {},
            },
        )

        # Persist to agent_schedules table
        schedule_data = {
            "id": schedule_id,
            "name": name,
            "pipeline_id": pipeline_id,
            "schedule_type": "cron",
            "schedule_expr": cron_expr,
            "enabled": 1 if enabled else 0,
            "params": json.dumps(params or {}),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        await self.db.create_schedule(schedule_data)

        logger.info("Added cron schedule %s for pipeline %s: %s", schedule_id, pipeline_id, cron_expr)
        return schedule_data

    async def add_interval(self, schedule_id: str, name: str, pipeline_id: str,
                           seconds: int, params: Optional[dict] = None,
                           enabled: bool = True) -> dict:
        """Add an interval schedule."""
        if not self._scheduler:
            raise RuntimeError("Scheduler not started")

        trigger = IntervalTrigger(seconds=seconds, timezone=self.timezone)

        job = self._scheduler.add_job(
            func=self._on_trigger,
            trigger=trigger,
            id=schedule_id,
            name=name,
            replace_existing=True,
            kwargs={
                "schedule_id": schedule_id,
                "pipeline_id": pipeline_id,
                "params": params or {},
            },
        )

        schedule_data = {
            "id": schedule_id,
            "name": name,
            "pipeline_id": pipeline_id,
            "schedule_type": "interval",
            "schedule_expr": str(seconds),
            "enabled": 1 if enabled else 0,
            "params": json.dumps(params or {}),
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        await self.db.create_schedule(schedule_data)

        logger.info("Added interval schedule %s for pipeline %s: %ds", schedule_id, pipeline_id, seconds)
        return schedule_data

    async def trigger_now(self, pipeline_id: str, params: Optional[dict] = None,
                          schedule_id: Optional[str] = None) -> None:
        """Manually trigger a pipeline immediately."""
        sid = schedule_id or f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info("Manual trigger: pipeline=%s schedule=%s", pipeline_id, sid)
        await self._on_trigger(schedule_id=sid, pipeline_id=pipeline_id, params=params or {})

    async def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule."""
        if self._scheduler:
            try:
                self._scheduler.remove_job(schedule_id)
            except Exception:
                pass
        return await self.db.delete_schedule(schedule_id)

    async def list_schedules(self) -> List[dict]:
        """List all schedules."""
        return await self.db.list_schedules()

    async def pause_schedule(self, schedule_id: str) -> bool:
        """Pause a schedule."""
        if self._scheduler:
            try:
                self._scheduler.pause_job(schedule_id)
            except Exception:
                pass
        return await self.db.update_schedule(schedule_id, {"enabled": 0})

    async def resume_schedule(self, schedule_id: str) -> bool:
        """Resume a schedule."""
        if self._scheduler:
            try:
                self._scheduler.resume_job(schedule_id)
            except Exception:
                pass
        return await self.db.update_schedule(schedule_id, {"enabled": 1})

    # ── Internal ──────────────────────────────────────────────────────

    async def _on_trigger(self, schedule_id: str, pipeline_id: str, params: dict) -> None:
        """Called when a schedule triggers."""
        logger.info("Schedule triggered: %s -> pipeline=%s", schedule_id, pipeline_id)

        # Update last_run_time
        await self.db.update_schedule(schedule_id, {
            "last_run_time": datetime.now().isoformat(),
            "last_run_status": "started",
        })

        # Call registered callback
        callback = self._trigger_callbacks.get(pipeline_id)
        if callback:
            try:
                await callback(schedule_id=schedule_id, pipeline_id=pipeline_id, params=params)
            except Exception as exc:
                logger.exception("Pipeline callback error for %s: %s", pipeline_id, exc)
                await self.db.update_schedule(schedule_id, {
                    "last_run_status": "failed",
                })
        else:
            logger.warning("No callback registered for pipeline: %s", pipeline_id)
            await self.db.update_schedule(schedule_id, {
                "last_run_status": "failed",
            })

    async def _restore_schedules(self) -> None:
        """Restore schedules from DB on startup."""
        schedules = await self.db.list_schedules(enabled_only=False)
        for s in schedules:
            if not s.get("enabled"):
                continue
            schedule_id = s["id"]
            # Skip if already registered in APScheduler
            if self._scheduler.get_job(schedule_id):
                logger.debug("Schedule %s already registered, skipping restore", schedule_id)
                continue
            try:
                if s["schedule_type"] == "cron":
                    parts = s["schedule_expr"].split()
                    if len(parts) != 5:
                        raise ValueError(f"Invalid cron expression: {s['schedule_expr']}")
                    trigger = CronTrigger(
                        minute=parts[0],
                        hour=parts[1],
                        day=parts[2],
                        month=parts[3],
                        day_of_week=parts[4],
                        timezone=self.timezone,
                    )
                    self._scheduler.add_job(
                        func=self._on_trigger,
                        trigger=trigger,
                        id=schedule_id,
                        name=s["name"],
                        replace_existing=True,
                        kwargs={
                            "schedule_id": schedule_id,
                            "pipeline_id": s["pipeline_id"],
                            "params": json.loads(s.get("params", "{}")),
                        },
                    )
                    logger.info("Restored cron schedule %s", schedule_id)
                elif s["schedule_type"] == "interval":
                    trigger = IntervalTrigger(seconds=int(s["schedule_expr"]), timezone=self.timezone)
                    self._scheduler.add_job(
                        func=self._on_trigger,
                        trigger=trigger,
                        id=schedule_id,
                        name=s["name"],
                        replace_existing=True,
                        kwargs={
                            "schedule_id": schedule_id,
                            "pipeline_id": s["pipeline_id"],
                            "params": json.loads(s.get("params", "{}")),
                        },
                    )
                    logger.info("Restored interval schedule %s", schedule_id)
            except Exception as exc:
                logger.error("Failed to restore schedule %s: %s", schedule_id, exc)
