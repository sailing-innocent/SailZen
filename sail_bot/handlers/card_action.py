# -*- coding: utf-8 -*-
# @file card_action.py
# @brief Card action handler - handles interactive card button clicks
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Handler for interactive card button clicks.

This module extracts card action handling logic from FeishuBotAgent
and provides a clean, testable interface for processing button clicks.
"""

import json
import threading
import traceback
from typing import Optional, Any

# FIX: Move imports to top level
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTriggerResponse,
)

from .base import BaseHandler, HandlerContext
from ..context import ActionPlan, PendingConfirmation
from ..session_state import PendingAction, RiskLevel
from ..card_renderer import CardRenderer
from ..async_task_manager import task_manager


class CardActionHandler(BaseHandler):
    """Handler for card action (button click) events.

    Responsibilities:
    - Parse card action events
    - Handle cancel_task actions
    - Handle confirm_self_update actions
    - Route other actions to background execution
    """

    def handle(self, data: Any) -> Optional[Any]:
        """Handle a card button click action.

        Args:
            data: The P2CardActionTrigger event data

        Returns:
            P2CardActionTriggerResponse to acknowledge the action, or None
        """
        try:
            if not data or not data.event or not data.event.action:
                return None

            action = data.event.action
            value = action.value if hasattr(action, "value") else {}

            # value could be a dict or string
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = {}

            action_type = value.get("action") if isinstance(value, dict) else None
            path = value.get("path") if isinstance(value, dict) else None

            # Get context info
            event_context = (
                data.event.context if hasattr(data.event, "context") else None
            )
            chat_id = event_context.open_chat_id if event_context else None
            message_id = event_context.open_message_id if event_context else None

            if not chat_id or not action_type:
                print("[CardActionHandler] Missing chat_id or action_type")
                return None

            print(f"[CardActionHandler] {action_type} for {path} in {chat_id}")

            # Handle cancel_task action
            if action_type == "cancel_task":
                return self._handle_cancel_task(value, chat_id)

            # Handle confirm_self_update action
            if action_type == "confirm_self_update":
                return self._handle_confirm_self_update(value, chat_id)

            # Route other actions to background execution
            return self._route_to_background(action_type, path, chat_id, message_id)

        except Exception as exc:
            print(f"[CardActionHandler] Error: {exc}")
            # FIX: traceback imported at top level
            traceback.print_exc()
            return None

    def _handle_cancel_task(self, value: dict, chat_id: str) -> Any:
        """Handle task cancellation request."""
        task_id = value.get("task_id") if isinstance(value, dict) else None

        if task_id:
            print(f"[CardActionHandler] Cancelling task: {task_id}")
            success = task_manager.abort_task(task_id)

            if success:
                return P2CardActionTriggerResponse(
                    {
                        "toast": {
                            "type": "info",
                            "content": "正在取消任务...",
                            "i18n": {
                                "zh_cn": "正在取消任务...",
                                "en_us": "Cancelling task...",
                            },
                        }
                    }
                )
            else:
                return P2CardActionTriggerResponse(
                    {
                        "toast": {
                            "type": "error",
                            "content": "取消任务失败（任务可能已完成或不存在）",
                            "i18n": {
                                "zh_cn": "取消任务失败（任务可能已完成或不存在）",
                                "en_us": "Failed to cancel task (may already completed or not found)",
                            },
                        }
                    }
                )
        else:
            return P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "error",
                        "content": "取消任务失败（任务可能已完成或不存在）",
                        "i18n": {
                            "zh_cn": "取消任务失败（任务可能已完成或不存在）",
                            "en_us": "Failed to cancel task (may already completed or not found)",
                        },
                    }
                }
            )

    def _handle_confirm_self_update(self, value: dict, chat_id: str) -> Any:
        """Handle self-update confirmation."""
        trigger_source = value.get("trigger_source", "manual")
        reason = value.get("reason", "User confirmed update")

        # Start self-update in background
        def do_self_update():
            # FIX: asyncio imported at top level
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
                        f"新进程 PID: {result.get('new_pid')}\n"
                        f"备份路径: {result.get('backup_path', 'N/A')}\n\n"
                        "旧进程即将退出，新进程将接管。",
                        success=True,
                    )
                    self.ctx.messaging.send_card(chat_id, success_card)
                else:
                    # Send error message
                    error_card = CardRenderer.error(
                        "❌ 更新失败",
                        result.get("error", "Unknown error"),
                    )
                    self.ctx.messaging.send_card(chat_id, error_card)
            finally:
                loop.close()

        threading.Thread(target=do_self_update, daemon=True).start()

        # Return immediate response
        return P2CardActionTriggerResponse(
            {
                "toast": {
                    "type": "info",
                    "content": "正在启动更新...",
                    "i18n": {
                        "zh_cn": "正在启动更新...",
                        "en_us": "Starting update...",
                    },
                }
            }
        )

    def _route_to_background(
        self, action_type: str, path: Optional[str], chat_id: str, message_id: str
    ) -> Any:
        """Route action to background thread for execution."""
        ctx = self.ctx.get_or_create_context(chat_id)
        plan = ActionPlan(action=action_type, params={"path": path} if path else {})

        # Execute in background thread
        # Note: The actual execution should be handled by the agent
        # This is a placeholder that signals the action is being processed
        threading.Thread(
            target=self._execute_plan_background,
            args=(plan, chat_id, message_id, ctx),
            daemon=True,
        ).start()

        # Return success response to Feishu (required!)
        return P2CardActionTriggerResponse(
            {
                "toast": {
                    "type": "info",
                    "content": "处理中...",
                    "i18n": {"zh_cn": "处理中...", "en_us": "Processing..."},
                }
            }
        )

    def _execute_plan_background(
        self, plan: ActionPlan, chat_id: str, message_id: str, ctx: Any
    ) -> None:
        """Execute plan in background (placeholder for agent integration)."""
        # This method should be overridden or the agent should handle this
        # For now, just log that the action was received
        print(f"[CardActionHandler] Background execution: {plan.action}")
