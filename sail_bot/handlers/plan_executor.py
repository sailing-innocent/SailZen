# -*- coding: utf-8 -*-
# @file plan_executor.py
# @brief Plan execution coordinator
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Plan execution coordinator.

This module coordinates the execution of ActionPlans by delegating
to specific handlers based on the action type.
"""

from typing import Optional

from .base import BaseHandler, HandlerContext
from ..context import ActionPlan, ConversationContext


class PlanExecutor(BaseHandler):
    """Executor for ActionPlans.

    Routes actions to appropriate handlers:
    - show_help -> HelpHandler
    - show_status -> StatusHandler
    - start_workspace -> StartWorkspaceHandler
    - stop_workspace -> StopWorkspaceHandler
    - switch_workspace -> SwitchWorkspaceHandler
    - send_task -> TaskHandler
    - self_update -> SelfUpdateHandler
    """

    def __init__(self, ctx: HandlerContext):
        super().__init__(ctx)
        # Initialize sub-handlers
        from .command_handlers import HelpHandler, StatusHandler
        from .workspace_handlers import (
            StartWorkspaceHandler,
            StopWorkspaceHandler,
            SwitchWorkspaceHandler,
        )
        from .task_handler import TaskHandler
        from .self_update_handler import SelfUpdateHandler

        self._help_handler = HelpHandler(ctx)
        self._status_handler = StatusHandler(ctx)
        self._start_handler = StartWorkspaceHandler(ctx)
        self._stop_handler = StopWorkspaceHandler(ctx)
        self._switch_handler = SwitchWorkspaceHandler(ctx)
        self._task_handler = TaskHandler(ctx)
        self._update_handler = SelfUpdateHandler(ctx)

    def execute(
        self,
        plan: ActionPlan,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        thinking_mid: Optional[str] = None,
    ) -> None:
        """Execute an ActionPlan.

        Args:
            plan: The action plan to execute
            chat_id: Target chat ID
            message_id: Message to reply to
            ctx: Conversation context
            thinking_mid: Optional thinking card message ID to update
        """
        action = plan.action
        params = plan.params

        # Handle simple commands
        if action == "show_help":
            self._help_handler.handle(chat_id, message_id)
            ctx.push("bot", "显示帮助信息")
            return

        if action == "show_status":
            self._status_handler.handle(chat_id, message_id, ctx)
            ctx.push("bot", "状态已显示")
            return

        if action == "switch_workspace":
            path = params.get("path")
            if path:
                self._switch_handler.handle(chat_id, message_id, ctx, path)
            else:
                self.ctx.messaging.reply_text(message_id, "请指定工作区路径")
            return

        if action == "start_workspace":
            project_slug = params.get("project")
            raw_path = params.get("path")
            self._start_handler.handle(
                chat_id, message_id, ctx, path=raw_path, project_slug=project_slug
            )
            return

        if action == "stop_workspace":
            raw_path = params.get("path")
            self._stop_handler.handle(chat_id, message_id, ctx, path=raw_path)
            return

        if action == "send_task":
            task_text = params.get("task", "")
            raw_path = params.get("path")
            self._task_handler.handle(
                chat_id, message_id, ctx, task_text, path=raw_path
            )
            return

        if action == "self_update":
            trigger_source = params.get("trigger_source", "manual")
            reason = params.get("reason", "User requested update")
            self._update_handler.handle(
                chat_id, message_id, ctx, trigger_source, reason
            )
            return

        # Unknown action
        self.ctx.messaging.reply_text(message_id, f"未知动作: {action}")
