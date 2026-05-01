# -*- coding: utf-8 -*-
# @file daemon.py
# @brief Shadow Agent Daemon — 24h automation controller
# @author sailing-innocent
# @date 2026-08-24
# @version 1.0
# ---------------------------------

import asyncio
import signal
import sys
import logging
from pathlib import Path
from typing import Optional

from sail_server.agent.config import AgentConfig
from sail_server.agent.job_scheduler import JobScheduler
from sail_server.agent.vault_sync import VaultSyncWorker
from sail_server.agent.note_analyzer import NoteAnalyzerWorker
from sail_server.agent.patch_generator import PatchGeneratorWorker
from sail_server.utils.logging_config import get_logger, setup_logging

logger = get_logger("agent.daemon")


class AgentDaemon:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.scheduler = JobScheduler()
        self.vault_sync = VaultSyncWorker(config.vaults)
        self.analyzer = NoteAnalyzerWorker(config.analysis, config.vaults)
        self.patch_gen = PatchGeneratorWorker(config.patch)
        self._shutdown_event = asyncio.Event()
        self._api_server = None

    async def start(self):
        logger.info(f"[Daemon] Starting Shadow Agent: {self.config.name}")

        # Register signals
        for sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_event_loop().add_signal_handler(sig, self._request_shutdown)

        # Setup scheduled jobs
        for vault in self.config.vaults:
            self.scheduler.add_interval(
                self.vault_sync.sync_all,
                minutes=vault.sync_interval_minutes,
                job_id=f"vault_sync_{vault.name}",
            )

        if self.config.analysis.enabled:
            self.scheduler.add_interval(
                self.analyzer.scan_and_create_tasks,
                minutes=self.config.analysis.scan_interval_minutes,
                job_id="note_analyzer",
            )

        if self.config.patch.enabled:
            self.scheduler.add_cron(
                self.patch_gen.generate_all,
                cron=self.config.patch.cron,
                job_id="patch_generator",
            )

        self.scheduler.start()

        # Optional: start admin API
        if self.config.admin_api.port:
            await self._start_admin_api()

        # Main loop
        logger.info("[Daemon] Running. Press Ctrl+C to stop.")
        await self._shutdown_event.wait()

        # Graceful shutdown
        self.scheduler.shutdown()
        if self._api_server:
            await self._api_server.stop()
        logger.info("[Daemon] Stopped.")

    def _request_shutdown(self):
        logger.info("[Daemon] Shutdown requested.")
        self._shutdown_event.set()

    async def _start_admin_api(self):
        try:
            from sail_server.agent.admin_api import AgentAdminAPI
            self._api_server = AgentAdminAPI(self)
            await self._api_server.start(
                host=self.config.admin_api.host,
                port=self.config.admin_api.port,
            )
        except Exception as e:
            logger.warning(f"[Daemon] Failed to start admin API: {e}")

    async def run_once(self, job_id: Optional[str] = None):
        """Run a single cycle (for CLI manual trigger)."""
        if job_id:
            await self.scheduler.trigger_now(job_id)
        else:
            await self.vault_sync.sync_all()
            if self.config.analysis.enabled:
                await self.analyzer.scan_and_create_tasks()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Shadow Agent Daemon")
    parser.add_argument("-c", "--config", default="agent.yaml", help="Config file path")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--job", help="Run specific job once and exit")
    args = parser.parse_args()

    setup_logging()
    config = AgentConfig.from_yaml(args.config)
    daemon = AgentDaemon(config)

    if args.once or args.job:
        asyncio.run(daemon.run_once(args.job))
    else:
        asyncio.run(daemon.start())


if __name__ == "__main__":
    main()
