# -*- coding: utf-8 -*-
# @file routes.py
# @brief Agent management API routes
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""Management API routes for the autonomous agent.

Endpoints:
  GET  /health          — Agent health, DB stats, next scheduled runs
  GET  /schedules       — List all schedules
  POST /schedules       — Create new schedule
  POST /schedules/{id}/trigger — Manual trigger
  DELETE /schedules/{id} — Delete schedule
  GET  /reminders       — List reminders
  POST /reminders/{id}/dismiss — Dismiss reminder
  GET  /memory          — Query memory by key/type
  POST /memory          — Write to memory
  GET  /runs            — Execution history
  GET  /goals           — List active goals
  POST /goals           — Create goal
  POST /goals/{id}/complete — Mark goal complete
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from litestar import Litestar, Router, get, post, delete
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_404_NOT_FOUND

from sailzen.autonomous_agent.daemon import AgentDaemon


def create_app(daemon: AgentDaemon) -> Litestar:
    """Create Litestar app with agent management routes."""

    @get("/health")
    async def health() -> dict:
        return await daemon.get_health()

    @get("/schedules")
    async def list_schedules() -> List[dict]:
        return await daemon.scheduler.list_schedules()

    @post("/schedules")
    async def create_schedule(data: dict) -> dict:
        schedule_type = data.get("schedule_type", "cron")
        if schedule_type == "cron":
            return await daemon.scheduler.add_cron(
                schedule_id=data["id"],
                name=data["name"],
                pipeline_id=data["pipeline_id"],
                cron_expr=data["schedule_expr"],
                params=data.get("params"),
                enabled=data.get("enabled", True),
            )
        else:
            return await daemon.scheduler.add_interval(
                schedule_id=data["id"],
                name=data["name"],
                pipeline_id=data["pipeline_id"],
                seconds=int(data["schedule_expr"]),
                params=data.get("params"),
                enabled=data.get("enabled", True),
            )

    @post("/schedules/{schedule_id:str}/trigger")
    async def trigger_schedule(schedule_id: str) -> dict:
        schedule = await daemon.db.get_schedule(schedule_id)
        if not schedule:
            return {"error": "Schedule not found"}, HTTP_404_NOT_FOUND
        await daemon.scheduler.trigger_now(
            pipeline_id=schedule["pipeline_id"],
            params=json.loads(schedule.get("params", "{}")),
            schedule_id=schedule_id,
        )
        return {"status": "triggered", "schedule_id": schedule_id}

    @delete("/schedules/{schedule_id:str}")
    async def delete_schedule(schedule_id: str) -> dict:
        success = await daemon.scheduler.remove_schedule(schedule_id)
        return {"deleted": success}

    @get("/reminders")
    async def list_reminders(status: Optional[str] = None, limit: int = 100) -> List[dict]:
        return await daemon.db.list_reminders(status=status, limit=limit)

    @post("/reminders/{reminder_id:str}/dismiss")
    async def dismiss_reminder(reminder_id: str) -> dict:
        success = await daemon.db.update_reminder(reminder_id, {"status": "dismissed"})
        return {"dismissed": success}

    @get("/memory")
    async def query_memory(memory_type: Optional[str] = None, key: Optional[str] = None) -> List[dict]:
        if memory_type and key:
            row = await daemon.db.get_memory(memory_type, key)
            return [row] if row else []
        return await daemon.db.list_memories(memory_type=memory_type)

    @post("/memory")
    async def write_memory(data: dict) -> dict:
        return await daemon.db.create_memory(data)

    @get("/runs")
    async def list_runs(schedule_id: Optional[str] = None, limit: int = 100) -> List[dict]:
        return await daemon.db.list_run_logs(schedule_id=schedule_id, limit=limit)

    @get("/goals")
    async def list_goals(status: Optional[str] = "active") -> List[dict]:
        return await daemon.state.list_goals(status=status)

    @post("/goals")
    async def create_goal(data: dict) -> dict:
        return await daemon.state.create_goal(
            title=data["title"],
            description=data.get("description", ""),
            priority=data.get("priority", 100),
            target_date=data.get("target_date"),
            completion_criteria=data.get("completion_criteria"),
        )

    @post("/goals/{goal_id:str}/complete")
    async def complete_goal(goal_id: str) -> dict:
        success = await daemon.state.complete_goal(goal_id)
        return {"completed": success}

    return Litestar(
        route_handlers=[
            Router(path="/", route_handlers=[
                health,
                list_schedules,
                create_schedule,
                trigger_schedule,
                delete_schedule,
                list_reminders,
                dismiss_reminder,
                query_memory,
                write_memory,
                list_runs,
                list_goals,
                create_goal,
                complete_goal,
            ]),
        ],
        debug=False,
    )
