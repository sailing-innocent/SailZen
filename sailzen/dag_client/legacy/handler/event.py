"""Event log handlers."""

from __future__ import annotations

from sail.dag.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    async def handle_list_events(cmd: Command) -> CommandResult:
        events = await db.get_event_logs(
            entity_type=cmd.args.get("entity_type") or None,
            entity_id=cmd.args.get("entity_id") or None,
            limit=cmd.args.get("limit", 100),
        )
        return CommandResult.ok(data=events)

    return {
        "list_events": handle_list_events,
    }
