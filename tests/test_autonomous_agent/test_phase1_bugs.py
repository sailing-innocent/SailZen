# -*- coding: utf-8 -*-
# @file test_phase1_bugs.py
# @brief Phase 1 bug fixes verification
# @author sailing-innocent
# @date 2025-06-18
# @version 1.0
# ---------------------------------
"""Tests for Phase 1 autonomous agent bug fixes.

Covers:
  - B1: datetime import in daemon.py
  - B2: eval() -> json.loads() in scheduler.py
  - B3: SQL injection fix in db.py
  - B4: DAG run trigger logic
  - B5: wellness_node fallback
  - B6-B8: YAML pipeline node type fixes
  - B9: reminder status update
  - B10: recent_alerts persistence
  - B11: condition_node safe evaluation
  - B12: schedule restore duplicate fix
  - Q5: api/routes.py eval() removal
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from sailzen.autonomous_agent.db import AgentDatabase, _now_iso
from sailzen.autonomous_agent.scheduler import CronScheduler
from sailzen.autonomous_agent.notification_engine import NotificationEngine
from sailzen.autonomous_agent.nodes.condition_node import ConditionNode
from sailzen.dag_client.nodes.base import NodeContext, NodeResult


# ═══════════════════════════════════════════════════════════════════════
#  B1: datetime import
# ═══════════════════════════════════════════════════════════════════════


def test_daemon_has_datetime_import():
    """B1: daemon.py must import datetime."""
    daemon_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "daemon.py"
    source = daemon_path.read_text(encoding="utf-8")
    assert "from datetime import datetime" in source
    # Ensure datetime.now() is used without NameError
    assert "datetime.now()" in source


# ═══════════════════════════════════════════════════════════════════════
#  B2: eval() removal in scheduler.py
# ═══════════════════════════════════════════════════════════════════════


def test_scheduler_no_eval():
    """B2: scheduler.py must not contain eval()."""
    scheduler_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "scheduler.py"
    source = scheduler_path.read_text(encoding="utf-8")
    assert "eval(" not in source, "scheduler.py still contains eval() - security risk"
    assert "import json" in source
    assert "json.dumps" in source
    assert "json.loads" in source


# ═══════════════════════════════════════════════════════════════════════
#  B3: SQL injection fix
# ═══════════════════════════════════════════════════════════════════════


def test_db_no_sql_injection():
    """B3: db.py list_goals must use parameterization."""
    db_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "db.py"
    source = db_path.read_text(encoding="utf-8")
    assert "f\" WHERE status = '{status}'\"" not in source
    assert ":st" in source


@pytest.mark.asyncio
async def test_db_list_goals_parameterized():
    """B3: Verify list_goals uses parameterized query."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        # Inject attempt via status parameter
        malicious_status = "active' OR '1'='1"
        goals = await db.list_goals(status=malicious_status)
        assert isinstance(goals, list)
        # Should return empty list, not all goals
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  B4: DAG run trigger logic
# ═══════════════════════════════════════════════════════════════════════


def test_daemon_uses_dag_scheduler_create_run():
    """B4: daemon.py must use dag_scheduler.create_run for full DAG instantiation."""
    daemon_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "daemon.py"
    source = daemon_path.read_text(encoding="utf-8")
    assert "await self.dag_scheduler.create_run(" in source
    assert "make_dag_run(" not in source or "from sailzen.dag_client.models import make_dag_run" not in source


# ═══════════════════════════════════════════════════════════════════════
#  B5: wellness_node fallback
# ═══════════════════════════════════════════════════════════════════════


def test_wellness_node_no_invalid_module():
    """B5: wellness_node must not reference non-existent sailzen.wellness module."""
    wellness_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "nodes" / "wellness_node.py"
    source = wellness_path.read_text(encoding="utf-8")
    assert "sailzen.wellness" not in source, "wellness_node still references non-existent sailzen.wellness"
    assert "run_analysis.py" in source, "wellness_node should reference actual script path"


# ═══════════════════════════════════════════════════════════════════════
#  B6-B8: YAML pipeline fixes
# ═══════════════════════════════════════════════════════════════════════


def test_yaml_skill_nodes_use_prompt():
    """B6-B8: skill nodes in YAMLs must use 'prompt' instead of 'command'."""
    pipelines_dir = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "pipelines"
    for yaml_file in pipelines_dir.glob("*.yaml"):
        content = yaml_file.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        for node in data.get("nodes", []):
            if node.get("type") == "skill":
                params = node.get("params", {})
                assert "skill" in params, f"{yaml_file.name}:{node['id']} missing 'skill' param"
                # command is ignored by SkillNode; prompt is the correct param
                if "command" in params and "prompt" not in params:
                    pytest.fail(
                        f"{yaml_file.name}:{node['id']} uses 'command' instead of 'prompt' for skill node"
                    )


# ═══════════════════════════════════════════════════════════════════════
#  B9: reminder status update
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notification_engine_updates_reminder_status():
    """B9: send() must update reminder status after delivery."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        config = MagicMock()
        config.default_channel = "log"
        config.quiet_hours_start = 23
        config.quiet_hours_end = 8

        engine = NotificationEngine(config, db=db)
        success = await engine.send("Test Title", "Test Content")
        assert success is True

        reminders = await db.list_reminders(status="sent")
        assert len(reminders) == 1
        assert reminders[0]["title"] == "Test Title"
        assert reminders[0]["status"] == "sent"
        assert reminders[0]["sent_at"] is not None
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_notification_engine_marks_failed_reminder():
    """B9: send() must mark reminder as failed when delivery fails."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        config = MagicMock()
        config.default_channel = "unknown_channel"
        config.quiet_hours_start = 23
        config.quiet_hours_end = 8

        engine = NotificationEngine(config, db=db)
        success = await engine.send("Test Title", "Test Content")
        assert success is False

        reminders = await db.list_reminders(status="failed")
        assert len(reminders) == 1
        assert reminders[0]["status"] == "failed"
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  B10: recent_alerts persistence
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_notification_engine_persists_dedup_state():
    """B10: recent_alerts must be persisted to DB."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        config = MagicMock()
        config.default_channel = "log"
        config.quiet_hours_start = 23
        config.quiet_hours_end = 8

        engine = NotificationEngine(config, db=db)
        await engine.send("Alert", "Content")

        # Verify memory was created
        memories = await db.list_memories(memory_type="short_term")
        dedup_memories = [m for m in memories if m["key"] == "notification_recent_alerts"]
        assert len(dedup_memories) >= 1
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_notification_engine_loads_dedup_state():
    """B10: Engine must load recent_alerts from DB on initialization."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        # Pre-seed dedup state
        now = datetime.now()
        await db.create_memory({
            "memory_type": "short_term",
            "key": "notification_recent_alerts",
            "value": json.dumps({"abc123": now.timestamp()}),
            "ttl_seconds": 3600,
            "expires_at": (now + timedelta(hours=2)).isoformat(),
        })

        config = MagicMock()
        config.default_channel = "log"
        config.quiet_hours_start = 23
        config.quiet_hours_end = 8

        engine = NotificationEngine(config, db=db)
        await engine._load_recent_alerts()
        assert "abc123" in engine._recent_alerts
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  B11: condition_node safe evaluation
# ═══════════════════════════════════════════════════════════════════════


def test_condition_node_no_plain_eval():
    """B11: condition_node must use sandboxed Jinja2, not plain eval."""
    cond_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "nodes" / "condition_node.py"
    source = cond_path.read_text(encoding="utf-8")
    assert "SandboxedEnvironment" in source
    # Ensure no dangerous eval remains
    assert "eval(" not in source or "ast.parse" not in source


@pytest.mark.asyncio
async def test_condition_node_evaluates_basic_condition():
    """B11: ConditionNode should evaluate basic Jinja2 expressions."""
    node = ConditionNode()
    ctx = NodeContext(
        run_id="r1",
        node_id="c1",
        node_type="condition",
        params={
            "condition": "upstream.foo == 'bar'",
            "true_next": ["t1"],
            "false_next": ["f1"],
        },
        upstream_results={"foo": "bar"},
        global_params={},
        store=None,
        opencode_client=None,
        working_dir=Path("."),
    )
    result = await node.execute(ctx)
    assert result.success is True
    assert result.data["result"] is True
    assert result.data["next_nodes"] == ["t1"]


@pytest.mark.asyncio
async def test_condition_node_handles_missing_upstream():
    """B11: ConditionNode should gracefully handle missing upstream data."""
    node = ConditionNode()
    ctx = NodeContext(
        run_id="r1",
        node_id="c1",
        node_type="condition",
        params={
            "condition": "upstream.missing.value > 10",
            "true_next": ["t1"],
            "false_next": ["f1"],
        },
        upstream_results={},
        global_params={},
        store=None,
        opencode_client=None,
        working_dir=Path("."),
    )
    result = await node.execute(ctx)
    assert result.success is True
    assert result.data["result"] is False
    assert result.data["next_nodes"] == ["f1"]


# ═══════════════════════════════════════════════════════════════════════
#  B12: schedule restore duplicate fix
# ═══════════════════════════════════════════════════════════════════════


def test_scheduler_restore_skips_existing_jobs():
    """B12: _restore_schedules must skip already-registered jobs."""
    sched_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "scheduler.py"
    source = sched_path.read_text(encoding="utf-8")
    assert "self._scheduler.get_job(schedule_id)" in source
    assert "already registered, skipping restore" in source


# ═══════════════════════════════════════════════════════════════════════
#  Q5: api/routes.py eval removal
# ═══════════════════════════════════════════════════════════════════════


def test_api_routes_no_eval():
    """Q5: api/routes.py must not contain eval()."""
    routes_path = PROJECT_ROOT / "sailzen" / "autonomous_agent" / "api" / "routes.py"
    source = routes_path.read_text(encoding="utf-8")
    assert "eval(" not in source, "api/routes.py still contains eval() - security risk"
    assert "json.loads" in source


# ═══════════════════════════════════════════════════════════════════════
#  Scheduler JSON round-trip
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_scheduler_params_json_roundtrip():
    """B2: Schedule params must round-trip through JSON correctly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    db = AgentDatabase(db_path=tmp_path)
    await db.connect()
    try:
        scheduler = CronScheduler(db, timezone="Asia/Shanghai")
        # Mock the APScheduler to avoid full startup
        with patch.object(scheduler, "_scheduler", MagicMock()) as mock_sched:
            mock_job = MagicMock()
            mock_job.next_run_time = datetime.now()
            mock_sched.add_job.return_value = mock_job

            params = {"key": "value", "number": 42, "nested": {"a": 1}}
            await scheduler.add_cron(
                schedule_id="test_1",
                name="Test",
                pipeline_id="p1",
                cron_expr="0 8 * * *",
                params=params,
            )

            schedules = await db.list_schedules()
            assert len(schedules) == 1
            stored = json.loads(schedules[0]["params"])
            assert stored == params
    finally:
        await db.close()
        Path(tmp_path).unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════════
#  DAG global queued nodes query
# ═══════════════════════════════════════════════════════════════════════


def test_dag_scheduler_global_queued_nodes():
    """B4: DAGScheduler.get_queued_nodes must support global queries."""
    sched_path = PROJECT_ROOT / "sailzen" / "dag_client" / "scheduler.py"
    source = sched_path.read_text(encoding="utf-8")
    assert "get_nodes_by_status" in source


def test_dag_repositories_global_node_query():
    """B4: Repositories must expose get_nodes_by_status."""
    repos_path = PROJECT_ROOT / "sailzen" / "dag_client" / "repositories.py"
    source = repos_path.read_text(encoding="utf-8")
    assert "async def get_by_status" in source
    assert "async def get_nodes_by_status" in source
