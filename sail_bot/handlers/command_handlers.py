# -*- coding: utf-8 -*-
# @file command_handlers.py
# @brief Simple command handlers (help, status)
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Command handlers for simple bot commands.

This module handles commands like:
- show_help: Display help information
- show_status: Display system status
"""

from pathlib import Path
from typing import Optional

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ConversationContext
from sail.feishu_card_kit.renderer import CardRenderer
from sail_bot.task_logger import task_logger
from sail.opencode import check_health_sync


class HelpHandler(BaseHandler):
    """Handler for help command."""

    def handle(self, chat_id: str, message_id: str) -> None:
        """Send help information."""
        help_card = CardRenderer.help(
            projects=self.ctx.config.projects,
            has_llm=self.ctx.brain._gw is not None,
            has_self_update=True,
        )
        self.ctx.messaging.reply_card(message_id, help_card, "help")


class StatusHandler(BaseHandler):
    """Handler for status command."""

    def handle(
        self, chat_id: str, message_id: str, ctx: Optional[ConversationContext] = None
    ) -> None:
        """Send detailed status report."""
        status_lines = []

        # 1. Current context state
        status_lines.append("📍 **当前状态**")
        if ctx and ctx.active_workspace:
            current_name = Path(ctx.active_workspace).name
            status_lines.append(f"💻 当前工作区: **{current_name}**")
            status_lines.append(f"   路径: `{ctx.active_workspace}`")

            # Show recent task history
            if task_logger:
                try:
                    history = task_logger.get_task_history(
                        ctx.active_workspace, limit=5
                    )
                    if history:
                        status_lines.append("\n   **📜 最近任务:**")
                        for entry in history:
                            status_icon = {
                                "completed": "✅",
                                "error": "❌",
                                "cancelled": "🚫",
                                "timeout": "⏱️",
                            }.get(entry.status, "📝")
                            task_summary = (
                                entry.task_text[:40] + "..."
                                if len(entry.task_text) > 40
                                else entry.task_text
                            )
                            duration = (
                                f"({entry.duration_seconds:.0f}s)"
                                if entry.duration_seconds > 0
                                else ""
                            )
                            tools = (
                                f"[{entry.tool_calls_count}tools]"
                                if entry.tool_calls_count > 0
                                else ""
                            )
                            status_lines.append(
                                f"   {status_icon} {task_summary} {duration} {tools}"
                            )
                except Exception as exc:
                    print(f"[StatusHandler] Failed to get task history: {exc}")
        else:
            status_lines.append("⚪ 当前工作区: 未选择")
        if ctx:
            status_lines.append(
                f"📝 模式: {'coding' if ctx.mode == 'coding' else 'idle'}"
            )
        status_lines.append("")

        # 2. Workspace connectivity status
        status_lines.append("🔍 **工作区连接状态**")
        procs = self.ctx.process_mgr.list_processes()

        if not procs:
            status_lines.append("❌ 没有运行中的工作区")
            status_lines.append(
                "💡 使用 `!启动 <项目名>` 或 `启动 <项目名>` 开启工作区"
            )
        else:
            for proc in procs:
                name = Path(proc.path).name
                port = proc.port

                # Test API health
                api_healthy = False
                if proc.is_alive:
                    try:
                        api_healthy = check_health_sync(port)
                    except Exception:
                        pass

                # Status icon
                if proc.is_alive and api_healthy:
                    icon = "✅"
                    status_desc = "运行正常"
                elif proc.is_alive and not api_healthy:
                    icon = "⚠️"
                    status_desc = "端口开放但 API 异常"
                else:
                    icon = "❌"
                    status_desc = "未运行"

                is_current = ctx and ctx.active_workspace == proc.path
                current_marker = " 👈 当前" if is_current else ""

                status_lines.append(f"{icon} **{name}**{current_marker}")
                status_lines.append(f"   路径: `{proc.path}`")
                status_lines.append(f"   端口: {port}")
                status_lines.append(f"   状态: {status_desc}")
                status_lines.append("")

        # 3. Configured projects
        if self.ctx.config.projects:
            status_lines.append("📁 **配置的项目**")
            for proj in self.ctx.config.projects:
                slug = proj.get("slug", "")
                path = proj.get("path", "")
                label = proj.get("label", slug)
                is_running = any(p.path == path for p in procs)
                run_icon = "✅" if is_running else "⚪"
                status_lines.append(f"{run_icon} {label} (`{slug}`)")
            status_lines.append("")

        # 4. Quick commands hint
        status_lines.append("💡 **快捷指令**")
        status_lines.append("• `!状态` - 刷新此状态")
        status_lines.append("• `!启动 <项目>` - 启动工作区")
        status_lines.append("• `!停止` - 停止当前工作区")
        status_lines.append("• `!切换 <项目>` - 切换到其他工作区")

        # Send status card
        full_status = "\n".join(status_lines)
        card = CardRenderer.result(
            title="📊 系统状态",
            content=full_status,
            success=True,
        )
        self.ctx.messaging.reply_card(message_id, card, "status_report")
