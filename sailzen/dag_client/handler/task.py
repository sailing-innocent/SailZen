"""Task handlers."""

from __future__ import annotations

from bot_server.models import TaskStatus, now_iso
from sail.dag.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    async def handle_list_tasks(cmd: Command) -> CommandResult:
        tasks = await db.get_tasks(
            sub_batch_id=cmd.args.get("sub_batch_id") or None,
            status=cmd.args.get("status") or None,
            task_type=cmd.args.get("type") or None,
        )
        return CommandResult.ok(data=tasks)

    async def handle_get_task(cmd: Command) -> CommandResult:
        t = await db.get_task(cmd.args["task_id"])
        if not t:
            return CommandResult.fail("Task 不存在")
        return CommandResult.ok(data=t, text=f"Task {t['type']} [{t['status']}]")

    async def handle_complete_task(cmd: Command) -> CommandResult:
        success = cmd.args.get("success", False)
        result_data = cmd.args.get("result")
        error = cmd.args.get("error")
        task_id = cmd.args["task_id"]
        await scheduler.on_task_completed(task_id, success, result_data, error)
        task = await db.get_task(task_id)
        events = []
        if task and task["status"] == TaskStatus.BLOCKED.value:
            events.append({
                "type": "task.blocked",
                "entity_type": "task",
                "entity_id": task_id,
                "run_id": None,  # will be resolved
                "data": {"type": task["type"], "error": error},
            })
        return CommandResult.ok(
            text="✅ Task 已更新",
            events=events,
        )

    async def handle_retry_task(cmd: Command) -> CommandResult:
        task_id = cmd.args["task_id"]
        task = await db.get_task(task_id)
        if not task:
            return CommandResult.fail("Task 不存在")
        await db.update_task_status(
            task_id,
            TaskStatus.QUEUED.value,
            expected_statuses=[TaskStatus.BLOCKED.value, TaskStatus.CANCELLED.value, TaskStatus.PENDING.value],
            queued_at=now_iso(),
            started_at=None,
            completed_at=None,
            error=None,
        )
        return CommandResult.ok(
            data={"ok": True, "status": "queued"},
            text=f"🔄 Task {task_id[:8]} 已重新排队",
        )

    async def handle_resolve_task(cmd: Command) -> CommandResult:
        task_id = cmd.args["task_id"]
        await scheduler.on_task_completed(task_id, success=True,
                                           result={"resolved_by": cmd.actor})
        return CommandResult.ok(
            text=f"✅ Task {task_id[:8]} 已标记为解决",
            events=[{
                "type": "task.resolved",
                "entity_type": "task",
                "entity_id": task_id,
                "data": {"resolved_by": cmd.actor},
            }],
        )

    async def handle_skip_task(cmd: Command) -> CommandResult:
        task_id = cmd.args["task_id"]
        task = await db.get_task(task_id)
        if not task:
            return CommandResult.fail("Task 不存在")
        await db.update_task_status(
            task_id,
            TaskStatus.CANCELLED.value,
            expected_statuses=[TaskStatus.QUEUED.value, TaskStatus.ASSIGNED.value,
                               TaskStatus.RUNNING.value, TaskStatus.PENDING.value,
                               TaskStatus.BLOCKED.value],
            completed_at=now_iso(),
        )
        await scheduler.on_task_completed(task_id, success=True,
                                           result={"skipped": True})
        return CommandResult.ok(text=f"⏭️ Task {task_id[:8]} 已跳过")

    async def handle_blocked(cmd: Command) -> CommandResult:
        tasks = await db.get_tasks(status="blocked")
        lines = [f"  🚫 {t['type']} ({t['id'][:8]}) - {t.get('error', '?')}"
                 for t in tasks]
        return CommandResult.ok(
            data=tasks,
            text=f"🚫 BLOCKED 任务 ({len(tasks)}):\n" + "\n".join(lines) if lines else "无 BLOCKED 任务 ✅",
        )

    return {
        "list_tasks": handle_list_tasks,
        "get_task": handle_get_task,
        "complete_task": handle_complete_task,
        "retry_task": handle_retry_task,
        "resolve_task": handle_resolve_task,
        "skip_task": handle_skip_task,
        "blocked": handle_blocked,
    }
