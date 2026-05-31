"""Health & Status handlers."""

from __future__ import annotations

from bot_server.deps import get_event_bus, get_popo_bridge
from bot_server.models import now_iso
from cube.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    async def handle_health(cmd: Command) -> CommandResult:
        integrity = await db.check_integrity()
        stats = await db.get_stats()
        return CommandResult.ok(data={
            "status": "ok" if integrity else "degraded",
            "timestamp": now_iso(),
            "db_integrity": integrity,
            "stats": stats,
            "scheduler_paused": scheduler.is_paused,
            "event_bus_subscribers": get_event_bus().subscriber_count,
            "popo_bridge": get_popo_bridge().status_dict if get_popo_bridge() else None,
        }, text="✅ 系统运行中" if integrity else "⚠️ 数据库异常")

    async def handle_status(cmd: Command) -> CommandResult:
        stats = await db.get_stats()
        active_batches = await db.get_batches(lifecycle="active")
        running = [b for b in active_batches if b["status"] == "running"]
        blocked_tasks = await db.get_tasks(status="blocked")

        lines = [
            "=== CubeClaw 状态 ===",
            f"📦 项目: {stats.get('projects', 0)}  工作空间: {stats.get('workspaces', 0)}",
            f"📋 Batches: {stats.get('batches', 0)} (运行中: {len(running)})",
            f"📝 Tasks: {stats.get('tasks', 0)}",
            f"🤖 Agents: {stats.get('agents', 0)}",
            f"🚫 BLOCKED: {len(blocked_tasks)}",
            f"⏸️ 调度器: {'暂停' if scheduler.is_paused else '运行中'}",
        ]

        popo = get_popo_bridge()
        if popo:
            lines.append(f"💬 POPO: {'连接' if popo.is_running else '断开'} "
                         f"(消息: {popo.status_dict.get('message_count', 0)})")

        return CommandResult.ok(
            data={"stats": stats, "running_batches": len(running),
                  "blocked_tasks": len(blocked_tasks)},
            text="\n".join(lines),
        )

    return {
        "health": handle_health,
        "status": handle_status,
    }
