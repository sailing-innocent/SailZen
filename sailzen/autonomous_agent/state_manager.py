# -*- coding: utf-8 -*-
# @file state_manager.py
# @brief Agent state machine, goals, and dependency health
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""StateManager — maintains the agent's internal state machine.

Tracks:
  - Active goals and their progress
  - Current "focus" (what the agent is working on)
  - Health of external dependencies (sail_server, OpenCode, Lark)
  - Recent anomalies detected
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sailzen.autonomous_agent.db import AgentDatabase
from sailzen.autonomous_agent.memory import AgentMemory

logger = logging.getLogger(__name__)


@dataclass
class DependencyHealth:
    """Health status of an external dependency."""
    name: str
    status: str = "unknown"  # ok | degraded | down | unknown
    last_check: Optional[str] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class StateManager:
    """Agent state manager."""

    def __init__(self, db: AgentDatabase, memory: AgentMemory):
        self.db = db
        self.memory = memory
        self._dependencies: Dict[str, DependencyHealth] = {}
        self._current_focus: Optional[str] = None
        self._anomalies: List[Dict[str, Any]] = []

    # ── Goals ─────────────────────────────────────────────────────────

    async def create_goal(self, title: str, description: str = "",
                          priority: int = 100, target_date: Optional[str] = None,
                          completion_criteria: Optional[dict] = None) -> dict:
        """Create a new agent goal."""
        data = {
            "title": title,
            "description": description,
            "priority": priority,
            "target_date": target_date,
            "completion_criteria": json.dumps(completion_criteria) if completion_criteria else None,
        }
        goal = await self.db.create_goal(data)
        logger.info("Created goal: %s (id=%s)", title, goal["id"])
        return goal

    async def list_goals(self, status: Optional[str] = "active") -> List[dict]:
        """List goals by status."""
        return await self.db.list_goals(status=status)

    async def complete_goal(self, goal_id: str) -> bool:
        """Mark a goal as completed."""
        success = await self.db.update_goal(goal_id, {"status": "completed"})
        if success:
            logger.info("Goal completed: %s", goal_id)
        return success

    async def pause_goal(self, goal_id: str) -> bool:
        """Pause a goal."""
        return await self.db.update_goal(goal_id, {"status": "paused"})

    # ── Focus ─────────────────────────────────────────────────────────

    def set_focus(self, focus: str) -> None:
        """Set the agent's current focus."""
        self._current_focus = focus
        logger.info("Agent focus set to: %s", focus)

    def get_focus(self) -> Optional[str]:
        """Get the agent's current focus."""
        return self._current_focus

    def clear_focus(self) -> None:
        """Clear the current focus."""
        self._current_focus = None

    # ── Dependency health ─────────────────────────────────────────────

    def update_dependency_health(self, name: str, status: str,
                                  latency_ms: Optional[float] = None,
                                  error: Optional[str] = None) -> None:
        """Update health status of an external dependency."""
        self._dependencies[name] = DependencyHealth(
            name=name,
            status=status,
            last_check=datetime.now().isoformat(),
            latency_ms=latency_ms,
            error=error,
        )
        if status != "ok":
            logger.warning("Dependency %s is %s: %s", name, status, error or "N/A")

    def get_dependency_health(self, name: str) -> DependencyHealth:
        """Get health status of a dependency."""
        return self._dependencies.get(name, DependencyHealth(name=name, status="unknown"))

    def all_dependencies_ok(self) -> bool:
        """Check if all tracked dependencies are healthy."""
        return all(d.status == "ok" for d in self._dependencies.values())

    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of all dependency health."""
        return {
            "dependencies": {
                name: {
                    "status": d.status,
                    "last_check": d.last_check,
                    "latency_ms": d.latency_ms,
                    "error": d.error,
                }
                for name, d in self._dependencies.items()
            },
            "all_ok": self.all_dependencies_ok(),
        }

    # ── Anomalies ─────────────────────────────────────────────────────

    def record_anomaly(self, source: str, description: str, severity: str = "warning",
                       data: Optional[dict] = None) -> None:
        """Record a detected anomaly."""
        anomaly = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "description": description,
            "severity": severity,
            "data": data or {},
        }
        self._anomalies.append(anomaly)
        # Keep only last 100 anomalies
        if len(self._anomalies) > 100:
            self._anomalies = self._anomalies[-100:]
        logger.warning("Anomaly recorded [%s]: %s - %s", severity, source, description)

    def get_recent_anomalies(self, limit: int = 20) -> List[dict]:
        """Get recent anomalies."""
        return self._anomalies[-limit:]

    def clear_anomalies(self) -> None:
        """Clear all recorded anomalies."""
        self._anomalies.clear()

    # ── State snapshot ────────────────────────────────────────────────

    async def get_state_snapshot(self) -> dict:
        """Get a complete snapshot of agent state."""
        active_goals = await self.list_goals("active")
        return {
            "current_focus": self._current_focus,
            "active_goals_count": len(active_goals),
            "active_goals": [{"id": g["id"], "title": g["title"]} for g in active_goals],
            "dependencies": self.get_health_summary(),
            "recent_anomalies": self.get_recent_anomalies(10),
            "timestamp": datetime.now().isoformat(),
        }
