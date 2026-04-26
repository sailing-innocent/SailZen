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
import time
import traceback
from typing import Optional, Any

from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTriggerResponse,
)

import logging

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ActionPlan
from sail.feishu_card_kit.renderer import CardRenderer

logger = logging.getLogger(__name__)


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

            # Handle confirm_action (confirmation button clicks)
            if action_type == "confirm_action":
                return self._handle_confirm_action(value, chat_id, message_id)

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

    def _handle_confirm_action(self, value: dict, chat_id: str, message_id: str) -> Any:
        """Handle confirmation button clicks (confirm or cancel).

        Args:
            value: The action value dict containing pending_id and decision
            chat_id: The chat ID
            message_id: The message ID for updating the card

        Returns:
            P2CardActionTriggerResponse to acknowledge the action

        Note:
            Must return response within 3 seconds to avoid "invalid confirmation" error.
            All card updates and action execution are done in background threads.
        """
        pending_id = value.get("pending_id") if isinstance(value, dict) else None
        decision = value.get("decision") if isinstance(value, dict) else None

        if not pending_id:
            return P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "error",
                        "content": "无效的操作确认",
                        "i18n": {
                            "zh_cn": "无效的操作确认",
                            "en_us": "Invalid confirmation",
                        },
                    }
                }
            )

        # Get the pending action from ConfirmationManager
        pending = self.ctx.confirm_mgr.consume(pending_id)

        if not pending:
            # Pending action not found or expired - update card in background
            def show_expired():
                error_card = CardRenderer.result(
                    "操作已过期",
                    "该确认请求已过期或已被处理，请重新发起操作。",
                    success=False,
                )
                self.ctx.messaging.update_card(message_id, error_card)

            threading.Thread(target=show_expired, daemon=True).start()

            return P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "error",
                        "content": "确认已过期，请重新发起",
                        "i18n": {
                            "zh_cn": "确认已过期，请重新发起",
                            "en_us": "Confirmation expired, please retry",
                        },
                    }
                }
            )

        if decision == "cancel":
            # User cancelled the action - update card and clear context in background
            def do_cancel():
                cancel_card = CardRenderer.result(
                    "已取消",
                    f"操作「{pending.summary}」已取消。",
                    success=True,
                )
                self.ctx.messaging.update_card(message_id, cancel_card)

                # Clear pending from conversation context
                ctx = self.ctx.get_or_create_context(chat_id)
                if ctx.pending and ctx.pending.summary == pending.summary:
                    ctx.clear_pending()
                    self.ctx.save_contexts()

            threading.Thread(target=do_cancel, daemon=True).start()

            return P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "info",
                        "content": "操作已取消",
                        "i18n": {
                            "zh_cn": "操作已取消",
                            "en_us": "Operation cancelled",
                        },
                    }
                }
            )

        # decision == "confirm" or default - execute the action
        # IMPORTANT: Update card and execute action in background to meet 3s response time
        def execute_confirmed_action():
            try:
                # Update card to show processing state
                processing_card = CardRenderer.progress(
                    title="正在执行",
                    description=f"正在执行「{pending.summary}」...",
                )
                self.ctx.messaging.update_card(message_id, processing_card)

                # Create a plan from the pending action
                plan = ActionPlan(
                    action=pending.action,
                    params=pending.params,
                )

                # Get or create conversation context
                conv_ctx = self.ctx.get_or_create_context(chat_id)

                # Execute the plan using PlanExecutor
                from sail_bot.handlers.plan_executor import PlanExecutor

                executor = PlanExecutor(self.ctx)
                executor.execute(plan, chat_id, message_id, conv_ctx)

                # Update card with result (executor will handle this)
                print(
                    f"[CardActionHandler] Confirmed action completed: {pending.action}"
                )

            except Exception as exc:
                print(f"[CardActionHandler] Error executing confirmed action: {exc}")
                traceback.print_exc()
                error_card = CardRenderer.result(
                    "执行失败",
                    f"执行「{pending.summary}」时出错：{str(exc)}",
                    success=False,
                )
                self.ctx.messaging.update_card(message_id, error_card)

        threading.Thread(target=execute_confirmed_action, daemon=True).start()

        return P2CardActionTriggerResponse(
            {
                "toast": {
                    "type": "info",
                    "content": "正在执行操作...",
                    "i18n": {
                        "zh_cn": "正在执行操作...",
                        "en_us": "Executing operation...",
                    },
                }
            }
        )

    def _handle_cancel_task(self, value: dict, chat_id: str) -> Any:
        """Handle task cancellation request.

        Cancellation flow:
        1. Extract task_id from button value
        2. Call op_tracker.cancel(task_id) which:
           a. Sets op.cancelled = True
           b. Invokes the registered cancel callback (SessionRunner.cancel)
        3. SessionRunner.cancel() sets _cancel_event, causing the SSE loop to exit
        4. TaskHandler detects was_cancelled and updates card to "已取消"
        5. TaskHandler calls op_tracker.finish() to clean up
        """
        task_id = (
            value.get("task_id") or value.get("op_id")
            if isinstance(value, dict)
            else None
        )

        if not task_id:
            return P2CardActionTriggerResponse(
                {
                    "toast": {
                        "type": "error",
                        "content": "取消失败：缺少任务 ID",
                        "i18n": {
                            "zh_cn": "取消失败：缺少任务 ID",
                            "en_us": "Cancel failed: missing task ID",
                        },
                    }
                }
            )

        logger.info("[CardActionHandler] Cancel request for task: %s", task_id)
        cancelled = self.ctx.op_tracker.cancel(task_id)

        if cancelled:
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

        # Operation not found — it may have already completed or been cancelled
        return P2CardActionTriggerResponse(
            {
                "toast": {
                    "type": "warning",
                    "content": "任务可能已完成或已取消",
                    "i18n": {
                        "zh_cn": "任务可能已完成或已取消",
                        "en_us": "Task may have already finished or been cancelled",
                    },
                }
            }
        )

    def _handle_confirm_self_update(self, value: dict, chat_id: str) -> Any:
        """Handle self-update confirmation."""
        reason = value.get("reason", "用户确认更新")

        # Extract message_id from event context for updating the original card later
        # Note: message_id is captured from the card action event
        # We need to pass it through so the restarted bot can update the card
        # However, the message_id from card action is the *original* message that contains the card
        # After restart, we can only send a new message (cannot update old card without message_id)
        # So we save chat_id and reason; the restarted bot will send a new completion card

        # Save pending update context BEFORE starting the update
        # so that even if the process exits immediately, the context is persisted
        from sail_bot.self_update_orchestrator import SelfUpdateOrchestrator

        SelfUpdateOrchestrator.save_pending_update(
            chat_id=chat_id,
            reason=reason,
        )

        # Start self-update in background
        def do_self_update():
            try:
                # Give a moment for the save to complete and card response to return
                import time

                time.sleep(0.5)

                result = self.ctx.request_self_update(reason=reason)

                if result.get("success"):
                    success_card = CardRenderer.result(
                        "✅ 更新已启动",
                        f"{result.get('message', '')}\n\n即将退出并由 watcher 重启。",
                        success=True,
                    )
                    self.ctx.messaging.send_card(chat_id, success_card)
                else:
                    # Clear pending update on failure
                    SelfUpdateOrchestrator.load_and_clear_pending_update()
                    error_card = CardRenderer.error(
                        "❌ 更新失败",
                        result.get("message", "Unknown error"),
                    )
                    self.ctx.messaging.send_card(chat_id, error_card)
            except Exception as exc:
                logger.error("[SelfUpdate] Error: %s", exc, exc_info=True)
                # Clear pending update on exception
                SelfUpdateOrchestrator.load_and_clear_pending_update()

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
