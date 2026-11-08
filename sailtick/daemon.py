# -*- coding: utf-8 -*-
# @file daemon.py
# @brief SailTickDaemon — 常驻生命周期编排
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTickDaemon — 24h 常驻 daemon。

职责:
  - 初始化隔离 DB / 各子系统
  - TickScheduler 6h 唤醒注册（00/06/12/18）
  - 心跳循环 + 收件箱轮询 + 依赖健康
  - 管理 API（:9070）
  - 优雅停机

修复自旧 daemon 的问题（迁移说明 B1/B2/B3/B5）:
  - db_compat 使用生产模式 DatabaseCompat（不直接传裸 Database）
  - 不调用 DAGScheduler 不存在的 start/stop
  - OpencodeAsyncClient 从 sail.opencode.client 导入
  - 触发回调用 fallback 语义
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime
from typing import Any, Optional

from sailtick.config import SailTickConfig, load_config
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
from sailtick.handoff import HandoffManager
from sailtick.inbox import TicketInbox
from sailtick.llm import LLMGateway
from sailtick.memory import AgentMemory
from sailtick.notify import NotificationEngine
from sailtick.scheduler import TickScheduler
from sailtick.state import DependencyState
from sailtick.tick_engine import TickEngine

logger = logging.getLogger(__name__)


class SailTickDaemon:
    """SailTick 常驻 daemon。"""

    def __init__(self, config: Optional[SailTickConfig] = None):
        self.config = config or load_config()
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._api_server: Any = None
        self._api_task: Optional[asyncio.Task] = None
        self._inbox_task: Optional[asyncio.Task] = None

        # 子系统
        self.db = TickDatabase(self.config.db_path)
        self.memory = AgentMemory(self.db)
        self.llm = LLMGateway(
            self.config.llm,
            cost_sink=self._record_cost,
        )
        self.inbox = TicketInbox(
            self.config.sail_server.api_base, self.config.sail_server.auth_token
        )
        self.scanner = DataScanner(
            self.config.sail_server.api_base, self.config.sail_server.auth_token
        )
        self.notifier = NotificationEngine(self.config.notify, inbox=self.inbox)
        self.handoffs = HandoffManager(self.db, self.config.handoffs_dir)
        self.state = DependencyState()

        # Phase 5: 自我开发执行器（配置了 repo_dir 才启用）
        dev_runner = None
        if self.config.self_dev.repo_dir:
            from sailtick.dev.tasks import DevTaskRunner

            dev_runner = DevTaskRunner(self.config.self_dev, inbox=self.inbox)
            logger.info("Self-dev enabled: repo=%s branch=%s",
                        self.config.self_dev.repo_dir, self.config.self_dev.branch)

        self.engine = TickEngine(
            config=self.config,
            db=self.db,
            memory=self.memory,
            llm=self.llm,
            inbox=self.inbox,
            scanner=self.scanner,
            notifier=self.notifier,
            handoffs=self.handoffs,
            state=self.state,
            dev_runner=dev_runner,
        )
        self.scheduler = TickScheduler(self.db, timezone=self.config.timezone)

    async def _record_cost(self, tokens: int, usd: float) -> None:
        """LLM 成本写入当前 tick（若正在跑）。"""
        tick = self.engine.current_tick()
        if tick:
            await self.db.add_tick_cost(tick["id"], tokens, usd)

    # ── 生命周期 ──────────────────────────────────────────────────────

    async def start(self) -> None:
        logger.info("=" * 60)
        logger.info("SailTick Daemon starting (name=%s)", self.config.name)
        logger.info("DB: %s", self.config.db_path)
        logger.info("API: %s:%d", self.config.api_host, self.config.api_port)
        logger.info("=" * 60)

        await self.db.connect()
        stats = await self.db.get_stats()
        logger.info("DB stats: %s", stats)

        # 崩溃恢复：残留 running tick → interrupted
        interrupted = await self.engine.interrupt_running_ticks()
        if interrupted:
            logger.warning("Interrupted %d stale running ticks", interrupted)

        # 注册唤醒 slot（00/06/12/18）
        for hour in sorted(self.config.tick.hours):
            sid = f"tick_{hour:02d}"
            slot = self._slot_name(hour)
            await self.scheduler.add_slot(sid, f"Tick {slot}", slot, hour)

        # 触发回调：精确 slot 注册 + 默认 fallback
        self.scheduler.register_default_callback(self._on_tick_trigger)

        await self.scheduler.start()

        # 管理 API
        await self._start_api()

        self._running = True
        self._setup_signals()
        logger.info("SailTick Daemon started")

        # 收件箱轮询（轻量，同步票据回复到本地记忆）
        self._inbox_task = asyncio.create_task(self._inbox_loop())

        await self._main_loop()

    async def stop(self) -> None:
        logger.info("SailTick Daemon shutting down...")
        self._running = False
        self._shutdown_event.set()

        if self._inbox_task:
            self._inbox_task.cancel()
            try:
                await self._inbox_task
            except asyncio.CancelledError:
                pass

        await self.scheduler.stop()
        if self._api_server is not None:
            self._api_server.should_exit = True
            self._api_server = None
        if self._api_task is not None:
            try:
                await self._api_task
            except asyncio.CancelledError:
                pass
            self._api_task = None
        await self.llm.close()
        await self.inbox.close()
        await self.scanner.close()
        await self.db.close()
        logger.info("SailTick Daemon stopped")

    def _setup_signals(self) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                if sig == signal.SIGINT:
                    def _win_handler(signum, frame):
                        import threading
                        if threading.current_thread() is threading.main_thread():
                            asyncio.create_task(self.stop())
                    signal.signal(signal.SIGINT, _win_handler)

    @staticmethod
    def _slot_name(hour: int) -> str:
        return {
            0: "nightly_maintenance",
            6: "morning_checkin",
            12: "midday_checkin",
            18: "evening_review",
        }.get(hour, f"tick_{hour:02d}")

    async def _on_tick_trigger(self, slot: str, schedule_id: str, params: dict) -> None:
        """scheduler 触发回调（默认 + 精确均走这里）。"""
        await self.engine.run_tick(slot, schedule_id=schedule_id, params=params)

    # ── 主循环 ────────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        while self._running:
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.config.heartbeat_interval)
                break
            except asyncio.TimeoutError:
                pass
            try:
                await self._heartbeat()
            except Exception as exc:
                logger.exception("Heartbeat error: %s", exc)

    async def _heartbeat(self) -> None:
        await self.memory.cleanup_expired()
        deps = self.state.snapshot()
        logger.debug(
            "heartbeat: deps=%s tick=%s",
            {k: v.get("status") for k, v in deps.items()},
            (self.engine.current_tick() or {}).get("idempotency_key"),
        )

    async def _inbox_loop(self) -> None:
        """收件箱轮询：把用户回复同步进本地 episodic 记忆。"""
        while self._running:
            try:
                if await self.inbox.health():
                    replies = await self.inbox.sync_replies_since()
                    for r in replies:
                        await self.memory.save_episode(None, "user_reply", r)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("inbox poll error: %s", exc)
            await asyncio.sleep(self.config.inbox_poll_seconds)

    # ── 管理 API ──────────────────────────────────────────────────────

    async def _start_api(self) -> None:
        from sailtick.api.routes import create_app

        app = create_app(self)

        async def _serve() -> None:
            import uvicorn

            config = uvicorn.Config(
                app,
                host=self.config.api_host,
                port=self.config.api_port,
                log_level="warning",
            )
            server = uvicorn.Server(config)
            self._api_server = server
            await server.serve()

        self._api_task = asyncio.create_task(_serve())
        logger.info("Management API on http://%s:%d", self.config.api_host, self.config.api_port)

    # ── 查询 ──────────────────────────────────────────────────────────

    async def get_health(self) -> dict:
        stats = await self.db.get_stats()
        return {
            "status": "running" if self._running else "stopped",
            "version": __import__("sailtick").__version__,
            "time": datetime.now().isoformat(),
            "config": {
                "name": self.config.name,
                "db_path": self.config.db_path,
                "tick_hours": self.config.tick.hours,
                "timezone": self.config.timezone,
            },
            "db_stats": stats,
            "schedules": await self.scheduler.next_run_times(),
            "deps": self.state.snapshot(),
            "current_tick": self.engine.current_tick(),
            "daily_tokens": await self.db.sum_cost_today(),
        }
