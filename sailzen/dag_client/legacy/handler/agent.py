"""Agent handlers."""

from __future__ import annotations

from bot_server.models import AgentStatus, make_agent, new_id, now_iso
from bot_server.service.converter import task_type_to_capability
from sail.dag.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    async def handle_list_agents(cmd: Command) -> CommandResult:
        agents = await db.get_agents(status=cmd.args.get("status") or None)
        lines = [f"  {'🟢' if a['status']=='online' else '⚪'} {a['name']} ({a['id'][:8]})"
                 for a in agents]
        return CommandResult.ok(
            data=agents,
            text=f"🤖 Agents ({len(agents)}):\n" + "\n".join(lines) if lines else "无 Agent",
        )

    async def handle_register_agent(cmd: Command) -> CommandResult:
        agent = make_agent(
            agent_id=cmd.args.get("id", new_id()),
            name=cmd.args.get("name", "agent"),
            host=cmd.args.get("host", "127.0.0.1"),
            port=cmd.args.get("port", 9000),
            platform=cmd.args.get("platform", "windows"),
            capabilities=cmd.args.get("capabilities", []),
            config=cmd.args.get("config"),
        )
        agent["status"] = AgentStatus.ONLINE.value
        agent["heartbeat_at"] = now_iso()
        await db.upsert_agent(agent)
        return CommandResult.ok(data={
            "agent_id": agent["id"],
            "heartbeat_interval": 30,
            "config": {},
        })

    async def handle_heartbeat(cmd: Command) -> CommandResult:
        agent_id = cmd.args["agent_id"]
        agent = await db.get_agent(agent_id)
        if not agent:
            return CommandResult.fail("Agent 不存在")
        await db.update_agent_status(agent_id, cmd.args.get("status", "online"),
                                     heartbeat_at=now_iso())
        queued = await scheduler.get_queued_tasks(limit=5)
        pending = []
        for t in queued:
            cap = task_type_to_capability(t["type"])
            if cap and cap in (agent.get("capabilities") or []):
                pending.append({"task_id": t["id"], "type": t["type"]})
        return CommandResult.ok(data={"ack": True, "pending_tasks": pending, "commands": []})

    return {
        "list_agents": handle_list_agents,
        "register_agent": handle_register_agent,
        "heartbeat": handle_heartbeat,
    }
