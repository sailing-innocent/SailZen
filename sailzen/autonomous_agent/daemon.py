# -*- coding: utf-8 -*-
# @file daemon.py
# @brief AgentDaemon — main lifecycle orchestrator
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""AgentDaemon — main lifecycle orchestrator for the autonomous agent.

Responsibilities:
  - Initialize isolated DB and workspace
  - Start CronScheduler
  - Start DAG Executor (reused from sailzen.dag_client)
  - Register agent-specific nodes into NodeRegistry
  - Run main event loop: process reminders, check goals, schedule pipelines
  - Graceful shutdown handling
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any, Dict, List, Optional

from sailzen.dag_client.config import load_config as load_dag_config
from sailzen.dag_client.database import Database as DAGDatabase
from sailzen.dag_client.executor import DAGExecutor
from sailzen.dag_client.nodes.registry import NodeRegistry
from sailzen.dag_client.scheduler import DAGScheduler
from sailzen.dag_client.store import DAGStore
from sailzen.dag_client.events import EventBus
from sailzen.dag_client.opencode_bridge import OpencodeAsyncClient

from sailzen.autonomous_agent.config import AgentConfig, load_agent_config
from sailzen.autonomous_agent.db import AgentDatabase
from sailzen.autonomous_agent.store import AgentStore
from sailzen.autonomous_agent.scheduler import CronScheduler
from sailzen.autonomous_agent.memory import AgentMemory
from sailzen.autonomous_agent.llm_gateway import LLMGateway
from sailzen.autonomous_agent.state_manager import StateManager
from sailzen.autonomous_agent.notification_engine import NotificationEngine

logger = logging.getLogger(__name__)


class AgentDaemon:
    """Autonomous Agent Daemon."""

    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_agent_config()
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Agent infrastructure
        self.db = AgentDatabase(self.config.db_path)
        self.store = AgentStore(self.config.data_dir)
        self.scheduler = CronScheduler(self.db, timezone=self.config.timezone)
        self.memory = AgentMemory(self.db)
        self.llm = LLMGateway(self.config.llm)
        self.state = StateManager(self.db, self.memory)
        self.notifier = NotificationEngine(self.config.notifications, db=self.db)

        # DAG Client infrastructure (reused)
        dag_cfg = load_dag_config()
        self.dag_db = DAGDatabase(dag_cfg.db_path)
        self.dag_store = DAGStore(dag_cfg.data_dir)
        self.event_bus = EventBus()
        self.dag_scheduler = DAGScheduler(self.dag_db, self.event_bus)

        # Node registry with agent-specific nodes
        self.node_registry = NodeRegistry()
        self._register_agent_nodes()

        self.opencode_client: Optional[OpencodeAsyncClient] = None
        self.executor: Optional[DAGExecutor] = None

    def _register_agent_nodes(self) -> None:
        """Register agent-specific DAG node types."""
        try:
            from sailzen.autonomous_agent.nodes.sailzen_cli_node import SailZenCliNode
            self.node_registry.register("sailzen_cli", SailZenCliNode)
        except Exception as exc:
            logger.warning("Failed to register sailzen_cli node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.lark_notify_node import LarkNotifyNode
            self.node_registry.register("lark_notify", LarkNotifyNode)
        except Exception as exc:
            logger.warning("Failed to register lark_notify node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.wellness_node import WellnessNode
            self.node_registry.register("wellness", WellnessNode)
        except Exception as exc:
            logger.warning("Failed to register wellness node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.state_check_node import StateCheckNode
            self.node_registry.register("state_check", StateCheckNode)
        except Exception as exc:
            logger.warning("Failed to register state_check node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.llm_reasoning_node import LLMReasoningNode
            self.node_registry.register("llm_reasoning", LLMReasoningNode)
        except Exception as exc:
            logger.warning("Failed to register llm_reasoning node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.reminder_emit_node import ReminderEmitNode
            self.node_registry.register("reminder_emit", ReminderEmitNode)
        except Exception as exc:
            logger.warning("Failed to register reminder_emit node: %s", exc)

        try:
            from sailzen.autonomous_agent.nodes.condition_node import ConditionNode
            self.node_registry.register("condition", ConditionNode)
        except Exception as exc:
            logger.warning("Failed to register condition node: %s", exc)

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the agent daemon."""
        logger.info("=" * 60)
        logger.info("Starting SailZen Autonomous Agent Daemon")
        logger.info("Name: %s", self.config.name)
        logger.info("DB: %s", self.config.db_path)
        logger.info("Data Dir: %s", self.config.data_dir)
        logger.info("=" * 60)

        # Connect agent DB
        await self.db.connect()
        db_stats = await self.db.get_stats()
        logger.info("Agent DB stats: %s", db_stats)

        # Connect DAG client DB
        await self.dag_db.connect()

        # Initialize OpenCode client
        try:
            self.opencode_client = OpencodeAsyncClient(
                host=self.config.opencode.host,
                port=self.config.opencode.port,
            )
        except Exception as exc:
            logger.warning("OpenCode client not available: %s", exc)

        # Initialize DAG executor
        self.executor = DAGExecutor(
            db_compat=self.dag_db,
            scheduler=self.dag_scheduler,
            event_bus=self.event_bus,
            node_registry=self.node_registry,
            store=self.dag_store,
            opencode_client=self.opencode_client,
        )

        # Start components
        await self.dag_scheduler.start()
        await self.executor.start()
        await self.scheduler.start()

        # Register pipeline trigger callback
        self.scheduler.register_trigger_callback("*", self._on_pipeline_trigger)

        self._running = True

        # Setup signal handlers
        self._setup_signals()

        logger.info("AgentDaemon started successfully")

        # Start main loop
        await self._main_loop()

    async def stop(self) -> None:
        """Graceful shutdown."""
        logger.info("AgentDaemon shutting down...")
        self._running = False
        self._shutdown_event.set()

        if self.scheduler:
            await self.scheduler.stop()
        if self.executor:
            await self.executor.stop()
        if self.dag_scheduler:
            await self.dag_scheduler.stop()
        if self.llm:
            await self.llm.close()
        if self.dag_db:
            await self.dag_db.close()
        if self.db:
            await self.db.close()

        logger.info("AgentDaemon stopped")

    def _setup_signals(self) -> None:
        """Setup OS signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

    # ── Main loop ─────────────────────────────────────────────────────

    async def _main_loop(self) -> None:
        """Main event loop."""
        while self._running:
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.config.heartbeat_interval)
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass

            try:
                await self._heartbeat_tick()
            except Exception as exc:
                logger.exception("Heartbeat tick error: %s", exc)

    async def _heartbeat_tick(self) -> None:
        """Periodic maintenance tasks."""
        # Cleanup expired memories
        await self.memory.cleanup_expired()

        # Flush notification queue
        await self.notifier.flush_queue()

        # Update dependency health
        await self._check_dependencies()

        # Log heartbeat
        logger.debug("Agent heartbeat: focus=%s deps_ok=%s",
                     self.state.get_focus(), self.state.all_dependencies_ok())

    async def _check_dependencies(self) -> None:
        """Quick health check of external dependencies."""
        import httpx

        # Check sail_server
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.config.sail_server.api_base}/health")
                self.state.update_dependency_health(
                    "sail_server",
                    "ok" if response.status_code == 200 else "degraded",
                    latency_ms=response.elapsed.total_seconds() * 1000 if hasattr(response, 'elapsed') else None,
                )
        except Exception as exc:
            self.state.update_dependency_health("sail_server", "down", error=str(exc))

        # Check OpenCode server
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"http://{self.config.opencode.host}:{self.config.opencode.port}/health"
                response = await client.get(url)
                self.state.update_dependency_health(
                    "opencode",
                    "ok" if response.status_code == 200 else "degraded",
                )
        except Exception as exc:
            self.state.update_dependency_health("opencode", "down", error=str(exc))

    # ── Pipeline execution ────────────────────────────────────────────

    async def _on_pipeline_trigger(self, schedule_id: str, pipeline_id: str, params: dict) -> None:
        """Handle pipeline trigger from scheduler."""
        logger.info("Executing pipeline: %s (schedule=%s)", pipeline_id, schedule_id)

        # Create run log entry
        log_entry = await self.db.create_run_log({
            "schedule_id": schedule_id,
            "pipeline_id": pipeline_id,
            "status": "started",
        })

        try:
            # Load pipeline definition
            pipeline_def = await self._load_pipeline_definition(pipeline_id)
            if not pipeline_def:
                raise ValueError(f"Pipeline definition not found: {pipeline_id}")

            # Create DAG run via dag_client scheduler
            from sailzen.dag_client.models import make_dag_run
            dag_run = make_dag_run(
                definition_id=pipeline_def["id"],
                name=f"{pipeline_id}_{schedule_id}",
                params={**pipeline_def.get("global_params", {}), **params},
            )
            await self.dag_db.create_run(dag_run)

            # Update log with dag_run_id
            await self.db.update_run_log(log_entry["id"], {
                "dag_run_id": dag_run["id"],
            })

            # TODO: The DAG scheduler needs to be told to execute this run.
            # For now, we rely on the DAGScheduler's own mechanism.
            logger.info("Pipeline %s scheduled as DAG run %s", pipeline_id, dag_run["id"])

            # Update schedule status
            await self.db.update_schedule(schedule_id, {
                "last_run_status": "success",
            })
            await self.db.update_run_log(log_entry["id"], {
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
            })

        except Exception as exc:
            logger.exception("Pipeline execution failed: %s", pipeline_id)
            await self.db.update_schedule(schedule_id, {
                "last_run_status": "failed",
            })
            await self.db.update_run_log(log_entry["id"], {
                "status": "failed",
                "error": str(exc),
                "completed_at": datetime.now().isoformat(),
            })

            # Emit failure notification for high-priority pipelines
            await self.notifier.send(
                title=f"Pipeline Failed: {pipeline_id}",
                content=f"Schedule: {schedule_id}\nError: {exc}",
                priority="high",
            )

    async def _load_pipeline_definition(self, pipeline_id: str) -> Optional[dict]:
        """Load pipeline definition from YAML files."""
        import yaml
        from pathlib import Path

        pipelines_dir = Path(self.config.pipelines_dir)
        if not pipelines_dir.exists():
            return None

        yaml_file = pipelines_dir / f"{pipeline_id}.yaml"
        if yaml_file.exists():
            with open(yaml_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        # Also check if already in dag_client DB
        # This would require dag_client's definition storage
        return None

    # ── Management API helpers ────────────────────────────────────────

    async def get_health(self) -> dict:
        """Get agent health status."""
        db_stats = await self.db.get_stats()
        schedules = await self.scheduler.list_schedules()
        return {
            "status": "running" if self._running else "stopped",
            "config": {
                "name": self.config.name,
                "db_path": self.config.db_path,
            },
            "db_stats": db_stats,
            "schedules_count": len(schedules),
            "next_scheduled_runs": [
                {"id": s["id"], "name": s["name"], "next_run_time": s.get("next_run_time")}
                for s in schedules[:5]
            ],
            "state": await self.state.get_state_snapshot(),
        }

    async def trigger_pipeline(self, pipeline_id: str, params: Optional[dict] = None) -> dict:
        """Manually trigger a pipeline."""
        await self.scheduler.trigger_now(pipeline_id, params or {})
        return {"pipeline_id": pipeline_id, "status": "triggered"}
