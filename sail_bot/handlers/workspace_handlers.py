# -*- coding: utf-8 -*-
# @file workspace_handlers.py
# @brief Workspace operation handlers (start, stop, switch)
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Workspace operation handlers.

This module handles workspace lifecycle operations:
- start_workspace: Start a new workspace
- stop_workspace: Stop a running workspace
- switch_workspace: Switch to another workspace
"""

import time
import threading
from pathlib import Path
from typing import Optional

from .base import BaseHandler, HandlerContext
from ..context import ConversationContext
from ..card_renderer import CardRenderer
from ..session_state import SessionState
from ..task_logger import task_logger


class StartWorkspaceHandler(BaseHandler):
    """Handler for starting a workspace."""

    def handle(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        path: Optional[str] = None,
        project_slug: Optional[str] = None,
    ) -> None:
        """Start a workspace.

        Args:
            chat_id: Target chat ID
            message_id: Message to reply to
            ctx: Conversation context
            path: Direct path to workspace
            project_slug: Project slug to look up path
        """
        from ..session_manager import resolve_path

        # Resolve path from project or direct path
        if project_slug:
            path = resolve_path(project_slug, self.ctx.config.projects)
        elif path:
            path = resolve_path(path, self.ctx.config.projects)

        if not path:
            # Show workspace selection
            from ..session_manager import resolve_path

            projects = self.ctx.config.projects
            state_map = {}
            for s in self.ctx.session_mgr.list_sessions():
                state_map[s.path] = s.process_status
            card = CardRenderer.workspace_selection(projects, session_states=state_map)
            self.ctx.messaging.reply_card(message_id, card, "workspace_selection")
            return

        self.ctx.state_store.get_or_create(path, chat_id)
        op_id = self.ctx.op_tracker.start(path, "启动 " + Path(path).name, timeout=30.0)

        progress_card = CardRenderer.progress(
            "正在启动 " + Path(path).name, "初始化 OpenCode 服务..."
        )
        prog_mid = self.ctx.messaging.reply_card(
            message_id, progress_card, "progress", {"op_id": op_id, "path": path}
        )

        def do_start() -> None:
            ok, session, msg = self.ctx.session_mgr.ensure_running(path, chat_id)
            self.ctx.op_tracker.finish(op_id)

            if ok:
                ctx.mode = "coding"
                ctx.active_workspace = session.path
                self.ctx.save_contexts()

                entry = self.ctx.state_store.get(path)
                activities = entry.recent_activities() if entry else []

                result_card = CardRenderer.session_status(
                    path=session.path,
                    state="running",
                    port=session.port,
                    pid=session.pid,
                    activities=activities,
                )
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, result_card)
                else:
                    self.ctx.messaging.send_card(
                        chat_id, result_card, "session_status", {"path": path}
                    )

                # Send current workspace card
                workspace_card = CardRenderer.current_workspace(
                    session.path, mode="coding"
                )
                self.ctx.messaging.send_card(
                    chat_id, workspace_card, "current_workspace", {"path": path}
                )

                ctx.push("bot", "OpenCode 已启动: " + session.path)
            else:
                err_card = CardRenderer.error(
                    "启动失败",
                    msg,
                    context_path=path,
                    retry_action={"action": "start_workspace", "path": path},
                )
                if prog_mid:
                    self.ctx.messaging.update_card(prog_mid, err_card)
                else:
                    self.ctx.messaging.send_card(chat_id, err_card)

        threading.Thread(target=do_start, daemon=True).start()


class StopWorkspaceHandler(BaseHandler):
    """Handler for stopping a workspace."""

    def handle(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        path: Optional[str] = None,
    ) -> None:
        """Stop a workspace."""
        from ..session_manager import resolve_path

        if path:
            path = resolve_path(path, self.ctx.config.projects)

        undo_deadline = time.time() + 30.0

        if path:
            ok, msg = self.ctx.session_mgr.stop_session(path)
            if ok:
                ctx.mode = "idle"
                ctx.active_workspace = None
                self.ctx.save_contexts()

            result_card = CardRenderer.result(
                "已停止" if ok else "停止失败",
                Path(path).name + " 已停止。" if ok else msg,
                success=ok,
                can_undo=ok,
                undo_deadline=undo_deadline if ok else None,
                context_path=path,
            )
            self.ctx.messaging.reply_card(
                message_id,
                result_card,
                "stop_result",
                {"path": path, "undo_deadline": undo_deadline},
            )
            ctx.push("bot", "已停止: " + path)
        else:
            # Stop all sessions
            sessions = self.ctx.session_mgr.list_sessions()
            if not sessions:
                self.ctx.messaging.reply_text(message_id, "没有正在运行的会话。")
                return

            results = []
            for s in sessions:
                ok, msg = self.ctx.session_mgr.stop_session(s.path)
                results.append(Path(s.path).name + ": " + ("已停止" if ok else msg))

            ctx.mode = "idle"
            ctx.active_workspace = None
            self.ctx.save_contexts()

            result_card = CardRenderer.result(
                "全部停止", "\n".join(results), success=True
            )
            self.ctx.messaging.reply_card(message_id, result_card)
            ctx.push("bot", "全部停止")


class SwitchWorkspaceHandler(BaseHandler):
    """Handler for switching workspace."""

    def handle(
        self, chat_id: str, message_id: str, ctx: ConversationContext, path: str
    ) -> None:
        """Switch to a workspace."""
        if not path:
            self.ctx.messaging.reply_text(message_id, "请指定工作区路径")
            return

        # Update context
        ctx.mode = "coding"
        ctx.active_workspace = path
        self.ctx.save_contexts()

        # Get task history
        history_text = ""
        if task_logger:
            try:
                history = task_logger.get_task_history(path, limit=3)
                if history:
                    history_lines = []
                    for entry in history:
                        status_icon = {
                            "completed": "✅",
                            "error": "❌",
                            "cancelled": "🚫",
                            "timeout": "⏱️",
                        }.get(entry.status, "📝")
                        task_summary = (
                            entry.task_text[:50] + "..."
                            if len(entry.task_text) > 50
                            else entry.task_text
                        )
                        duration = (
                            f"({entry.duration_seconds:.0f}s)"
                            if entry.duration_seconds > 0
                            else ""
                        )
                        history_lines.append(f"{status_icon} {task_summary} {duration}")

                    if history_lines:
                        history_text = "\n\n**📜 最近任务:**\n" + "\n".join(
                            history_lines
                        )
            except Exception as exc:
                print(f"[SwitchWorkspace] Failed to get task history: {exc}")

        # Get active task
        active_task_text = ""
        if task_logger:
            try:
                active_task = task_logger.get_active_task_for_workspace(path)
                if active_task:
                    active_task_text = (
                        f"\n\n**⏳ 活跃任务:** {active_task.task_text[:60]}..."
                    )
            except Exception as exc:
                print(f"[SwitchWorkspace] Failed to get active task: {exc}")

        # Send switch card
        workspace_name = Path(path).name
        card_content = f"**工作区:** {workspace_name}\n**路径:** `{path}`{active_task_text}{history_text}"

        card = CardRenderer.result(
            title=f"🔄 已切换到工作区",
            content=card_content,
            success=True,
            context_path=path,
        )
        self.ctx.messaging.reply_card(
            message_id, card, "workspace_switched", {"path": path}
        )
        ctx.push("bot", f"已切换到工作区: {workspace_name}")
