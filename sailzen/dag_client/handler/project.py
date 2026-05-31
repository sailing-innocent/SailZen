"""Project & Workspace handlers."""

from __future__ import annotations

from bot_server.models import make_project, make_workspace
from cube.command_bus import Command, CommandResult


def register(bus, db, scheduler) -> dict:
    """返回 {command_name: handler_fn} 映射。"""

    # ── Projects ───────────────────────────────────────────────────

    async def handle_list_projects(cmd: Command) -> CommandResult:
        projects = await db.get_projects()
        text = "\n".join(f"  • {p['name']} ({p['id'][:8]})" for p in projects) or "无项目"
        return CommandResult.ok(data=projects, text=f"📋 项目 ({len(projects)}):\n{text}")

    async def handle_get_project(cmd: Command) -> CommandResult:
        p = await db.get_project(cmd.args["project_id"])
        if not p:
            return CommandResult.fail("项目不存在")
        return CommandResult.ok(data=p, text=f"📋 {p['name']}")

    async def handle_create_project(cmd: Command) -> CommandResult:
        project = make_project(cmd.args.get("name", "unnamed"),
                               cmd.args.get("description", ""))
        await db.upsert_project(project)
        return CommandResult.ok(
            data=project,
            text=f"✅ 项目已创建: {project['name']}",
            events=[{"type": "project.created", "entity_type": "project",
                     "entity_id": project["id"], "data": project}],
        )

    # ── Workspaces ─────────────────────────────────────────────────

    async def handle_list_workspaces(cmd: Command) -> CommandResult:
        pid = cmd.args.get("project_id", "")
        if pid:
            ws_list = await db.get_workspaces(pid)
        else:
            projects = await db.get_projects()
            ws_list = []
            for p in projects:
                ws_list.extend(await db.get_workspaces(p["id"]))
        return CommandResult.ok(data=ws_list)

    async def handle_create_workspace(cmd: Command) -> CommandResult:
        ws = make_workspace(
            project_id=cmd.args["project_id"],
            name=cmd.args.get("name", "workspace"),
            repo_path=cmd.args.get("repo_path", ""),
            locked_files=cmd.args.get("locked_files"),
            mirror_rules=cmd.args.get("mirror_rules"),
            config=cmd.args.get("config"),
        )
        await db.upsert_workspace(ws)
        return CommandResult.ok(data=ws, text=f"✅ 工作空间已创建: {ws['name']}")

    return {
        "list_projects": handle_list_projects,
        "get_project": handle_get_project,
        "create_project": handle_create_project,
        "list_workspaces": handle_list_workspaces,
        "create_workspace": handle_create_workspace,
    }
