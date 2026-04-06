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

import threading
import asyncio
from typing import Optional, Any, Dict

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ActionPlan, ConversationContext
from sail_bot.card_renderer import CardRenderer


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
        from sail_bot.handlers.command_handlers import HelpHandler, StatusHandler
        from sail_bot.handlers.workspace_handlers import (
            StartWorkspaceHandler,
            StopWorkspaceHandler,
            SwitchWorkspaceHandler,
        )
        from sail_bot.handlers.task_handler import TaskHandler
        from sail_bot.handlers.self_update_handler import SelfUpdateHandler

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

        if action == "confirm_self_update":
            # User confirmed self-update, execute it directly
            trigger_source = params.get("trigger_source", "manual")
            reason = params.get("reason", "User confirmed update")
            self._handle_confirmed_self_update(chat_id, message_id, trigger_source, reason)
            ctx.push("bot", "正在执行自更新...")
            return

        # Unknown action
        self.ctx.messaging.reply_text(message_id, f"未知动作: {action}")

    def _handle_confirmed_self_update(
        self,
        chat_id: str,
        message_id: str,
        trigger_source: str,
        reason: str,
    ) -> None:
        """Handle confirmed self-update request.

        This runs the self-update in a background thread to avoid blocking.
        """

        def do_self_update():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = self.ctx.request_self_update(
                    trigger_source=trigger_source,
                    reason=reason,
                    initiated_by=chat_id,
                )

                if result.get("success"):
                    # Send success message
                    success_card = CardRenderer.result(
                        "✅ 更新已启动",
                        f"阶段: {result.get('phase', 'unknown')}\n"
                        f"备份路径: {result.get('backup_path', 'N/A')}\n\n"
                        "旧进程即将退出，新进程将接管。",
                        success=True,
                    )
                    self.ctx.messaging.send_card(chat_id, success_card)
                else:
                    # Send error message
                    error_card = CardRenderer.result(
                        "❌ 更新失败",
                        result.get("error", "Unknown error"),
                        success=False,
                    )
                    self.ctx.messaging.send_card(chat_id, error_card)
            finally:
                loop.close()

        # Start self-update in background thread
        threading.Thread(target=do_self_update, daemon=True).start()

        # Send immediate acknowledgment
        self.ctx.messaging.reply_text(
            message_id, "🔄 正在启动更新，请稍候..."
        )
