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

from sailtick.canary import CanaryController, CanaryMonitor
from sailtick.config import SailTickConfig, load_config
from sailtick.datascan import DataScanner
from sailtick.db import TickDatabase
from sailtick.finance_client import FinanceClient
from sailtick.handoff import HandoffManager
from sailtick.inbox import TicketInbox
from sailtick.knowledge import HealthKnowledgeManager
from sailtick.llm import LLMGateway
from sailtick.memory import AgentMemory
from sailtick.nightly import NightlySelfMaintenance
from sailtick.notify import NotificationEngine
from sailtick.qq_bot import OneBotQQAdapter
from sailtick.quick_agent import QuickCoachAgent
from sailtick.rhythm_client import RhythmClient
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
        self.rhythm = RhythmClient(
            self.config.sail_server.api_base, self.config.sail_server.auth_token
        )
        self.finance = FinanceClient(
            self.config.sail_server.api_base, self.config.sail_server.auth_token
        )
        self.notifier = NotificationEngine(self.config.notify, inbox=self.inbox)
        self.handoffs = HandoffManager(self.db, self.config.handoffs_dir)
        self.state = DependencyState()
        self.canary = CanaryController(self.config.canary, self.db)
        self.monitor = CanaryMonitor(
            self.db,
            self.canary,
            self.state,
            daily_token_cap=self.config.llm.daily_token_cap,
        )

        # Phase 5: 自我开发执行器（配置了 repo_dir 才启用）
        dev_runner = None
        if self.config.self_dev.repo_dir:
            from sailtick.dev.tasks import DevTaskRunner

            dev_runner = DevTaskRunner(self.config.self_dev, inbox=self.inbox)
            logger.info("Self-dev enabled: repo=%s branch=%s",
                        self.config.self_dev.repo_dir, self.config.self_dev.branch)

        self.knowledge = HealthKnowledgeManager(
            db=self.db,
            llm=self.llm,
            enable_web_search=self.config.nightly.enable_web_search,
            web_search_timeout=self.config.nightly.web_search_timeout,
        )
        self.nightly = NightlySelfMaintenance(
            config=self.config,
            db=self.db,
            memory=self.memory,
            scanner=self.scanner,
            llm=self.llm,
            knowledge=self.knowledge,
            finance_client=self.finance,
        )
        self.quick_agent = QuickCoachAgent(
            config=self.config,
            db=self.db,
            memory=self.memory,
            inbox=self.inbox,
            llm=self.llm,
            knowledge=self.knowledge,
            rhythm=self.rhythm,
            finance=self.finance,
        )
        self.qq_bot = OneBotQQAdapter(
            config=self.config.qq_bot,
            db=self.db,
            quick_agent=self.quick_agent,
        )

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
            canary=self.canary,
            nightly=self.nightly,
            rhythm=self.rhythm,
            finance=self.finance,
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
        await self.canary.load()
        stats = await self.db.get_stats()
        logger.info("DB stats: %s | canary_mode=%s", stats, self.canary.mode)

        # 崩溃恢复：残留 running tick → interrupted
        interrupted = await self.engine.interrupt_running_ticks()
        if interrupted:
            logger.warning("Interrupted %d stale running ticks", interrupted)

        # 触发回调：精确 slot 注册 + 默认 fallback
        self.scheduler.register_default_callback(self._on_tick_trigger)

        await self.scheduler.start()

        # 注册唤醒 slots（支持 00/06/12/18 + 21:45 睡前日报等分钟级排程）
        for s_cfg in self.config.tick.resolved_slots():
            sid = (
                f"tick_{s_cfg.hour:02d}_{s_cfg.minute:02d}_{s_cfg.slot}"
                if s_cfg.minute
                else f"tick_{s_cfg.hour:02d}"
            )
            await self.scheduler.add_slot(
                sid, f"Tick {s_cfg.slot}", s_cfg.slot, s_cfg.hour, minute=s_cfg.minute
            )

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
        await self.qq_bot.close()
        await self.llm.close()
        await self.inbox.close()
        await self.scanner.close()
        await self.rhythm.close()
        await self.finance.close()
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
        try:
            sent = await self.qq_bot.dispatch_due_nudges()
            if sent:
                logger.info("Dispatched %d due QQ reminder nudges", sent)
        except Exception as exc:
            logger.warning("dispatch_due_nudges error: %s", exc)
        deps = self.state.snapshot()
        logger.debug(
            "heartbeat: deps=%s tick=%s",
            {k: v.get("status") for k, v in deps.items()},
            (self.engine.current_tick() or {}).get("idempotency_key"),
        )

    async def _inbox_loop(self) -> None:
        """收件箱轮询：按游标增量同步用户回复进本地 episodic 记忆（避免重复刷库）。"""
        while self._running:
            try:
                if await self.inbox.health():
                    cursor_str = await self.db.get_runtime_state("inbox_poll_cursor")
                    since = datetime.fromisoformat(cursor_str) if cursor_str else None
                    replies = await self.inbox.sync_replies_since(since=since)
                    latest_ts = cursor_str
                    for r in replies:
                        await self.memory.save_episode(None, "user_reply", r)
                        ts = r.get("updated_at") or r.get("replied_at")
                        if ts and (not latest_ts or str(ts) > str(latest_ts)):
                            latest_ts = str(ts)
                    if replies and latest_ts:
                        # 向前推进 1 秒避免同一条边界反复拉取
                        try:
                            from datetime import timedelta
                            next_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
                            if next_dt.tzinfo is not None:
                                next_dt = next_dt.astimezone().replace(tzinfo=None)
                            await self.db.set_runtime_state(
                                "inbox_poll_cursor",
                                (next_dt + timedelta(seconds=1)).isoformat(),
                            )
                        except Exception:
                            await self.db.set_runtime_state(
                                "inbox_poll_cursor", datetime.now().isoformat()
                            )
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
            "canary": self.canary.get_status(),
            "db_stats": stats,
            "schedules": await self.scheduler.next_run_times(),
            "deps": self.state.snapshot(),
            "current_tick": self.engine.current_tick(),
            "daily_tokens": await self.db.sum_cost_today(),
        }

    async def get_monitor_snapshot(self, window_ticks: int = 50) -> dict:
        cur = self.engine.current_tick()
        return await self.monitor.snapshot(
            window_ticks=window_ticks,
            active_tick_id=cur["id"] if cur else None,
        )
