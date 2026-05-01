# -*- coding: utf-8 -*-
# @file job_scheduler.py
# @brief Lightweight job scheduler using APScheduler
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import asyncio
import logging
from typing import Callable, Awaitable, Any
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self._handlers: dict[str, Callable[[], Awaitable[Any]]] = {}

    def add_interval(
        self,
        handler: Callable[[], Awaitable[Any]],
        minutes: int = 60,
        job_id: str = None,
    ):
        jid = job_id or handler.__name__
        self._handlers[jid] = handler
        self.scheduler.add_job(
            self._wrap(handler),
            IntervalTrigger(minutes=minutes),
            id=jid,
            replace_existing=True,
        )
        logger.info(f"[Scheduler] Added interval job '{jid}' every {minutes}m")

    def add_cron(
        self,
        handler: Callable[[], Awaitable[Any]],
        cron: str,
        job_id: str = None,
    ):
        jid = job_id or handler.__name__
        self._handlers[jid] = handler
        minute, hour, day, month, day_of_week = cron.split()
        self.scheduler.add_job(
            self._wrap(handler),
            CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            ),
            id=jid,
            replace_existing=True,
        )
        logger.info(f"[Scheduler] Added cron job '{jid}' at {cron}")

    def _wrap(self, handler: Callable[[], Awaitable[Any]]):
        async def wrapper():
            try:
                await handler()
            except Exception as e:
                logger.exception(f"[Scheduler] Job failed: {e}")
        return wrapper

    def start(self):
        self.scheduler.start()
        logger.info("[Scheduler] Started")

    def shutdown(self):
        self.scheduler.shutdown()
        logger.info("[Scheduler] Shutdown")

    async def trigger_now(self, job_id: str):
        handler = self._handlers.get(job_id)
        if not handler:
            raise ValueError(f"Job '{job_id}' not found")
        logger.info(f"[Scheduler] Manual trigger: {job_id}")
        await self._wrap(handler)()
