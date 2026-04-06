# -*- coding: utf-8 -*-
# @file message_handler.py
# @brief Message handling - routes incoming messages to appropriate handlers
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Message handler for processing incoming Feishu messages.

This module handles the message processing pipeline:
1. Parse incoming messages
2. Check for pending confirmations
3. Determine user intent via BotBrain
4. Route to appropriate executor
"""

import json
import re
import threading
import asyncio
import traceback
from typing import Optional, Tuple
from datetime import datetime

import lark_oapi as lark

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ActionPlan, ConversationContext
from sail_bot.card_renderer import CardRenderer
from sail_bot.session_state import RiskLevel, classify_risk


class MessageHandler(BaseHandler):
    """Handler for incoming Feishu messages.

    Responsibilities:
    - Parse and validate incoming messages
    - Check for pending confirmation replies
    - Determine user intent (via BotBrain)
    - Route actions to PlanExecutor
    """

    def handle(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        """Handle incoming Feishu message."""
        try:
            if not data or not data.event or not data.event.message:
                return

            message = data.event.message
            if message.message_type != "text":
                print(
                    f"[MessageHandler] Ignoring non-text message: {message.message_type}"
                )
                return

            try:
                content = json.loads(message.content or "{}")
            except json.JSONDecodeError:
                return

            text = content.get("text", "").strip()
            chat_id = message.chat_id
            message_id = message.message_id

            if not text or not chat_id:
                return

            print(f"\n[MessageHandler] Message from {chat_id}: {text[:80]}")

            # Handle in a background thread to avoid blocking the SDK
            threading.Thread(
                target=self._process_message,
                args=(text, chat_id, message_id),
                daemon=True,
            ).start()

        except Exception as exc:
            print(f"[MessageHandler] Error: {exc}")
            traceback.print_exc()

    def _process_message(self, text: str, chat_id: str, message_id: str) -> None:
        """Process a message (runs in background thread)."""
        text = re.sub(r"@\S+", "", text).strip()
        if not text:
            return

        ctx = self.ctx.get_or_create_context(chat_id)
        ctx.push("user", text)

        plan, thinking_mid = self._dispatch_message(text, chat_id, message_id, ctx)

        # Execute the plan if it's an actionable plan
        if plan.action not in ("noop", "chat", "clarify"):
            from sail_bot.handlers.plan_executor import PlanExecutor

            executor = PlanExecutor(self.ctx)
            executor.execute(plan, chat_id, message_id, ctx, thinking_mid)

    def _dispatch_message(
        self, text: str, chat_id: str, message_id: str, ctx: ConversationContext
    ) -> Tuple[ActionPlan, Optional[str]]:
        """Dispatch message to appropriate handler.

        Returns:
            Tuple of (ActionPlan, thinking_card_message_id or None)
        """
        force_flag = "--force" in text or "强制" in text

        # Check for pending confirmation reply
        if ctx.pending:
            decision = self.ctx.brain.check_confirmation_reply(text)
            if decision is True:
                plan = ActionPlan(action=ctx.pending.action, params=ctx.pending.params)
                ctx.clear_pending()
                return plan, None
            elif decision is False:
                ctx.clear_pending()
                card = CardRenderer.result("已取消", "操作已取消。", success=False)
                self.ctx.messaging.reply_card(message_id, card)
                ctx.push("bot", "已取消")
                return ActionPlan(action="noop"), None
            else:
                ctx.clear_pending()
                self.ctx.messaging.reply_text(
                    message_id, "确认已超时，请重新发起指令。"
                )
                return ActionPlan(action="noop"), None

        # Check for pending_id in text
        pending_id = self._find_pending_id_from_text(text)
        if pending_id:
            pending = self.ctx.confirm_mgr.consume(pending_id)
            if pending:
                plan = ActionPlan(action=pending.action, params=pending.params)
                return plan, None

        # Use async think_with_feedback to determine intent
        thinking_mid = None
        try:
            plan, thinking_mid = asyncio.run(
                self.ctx.brain.think_with_feedback(
                    text, ctx, chat_id, message_id, self.ctx.agent
                )
            )
        except Exception as exc:
            print(f"[{chat_id}] think_with_feedback failed: {exc}")
            plan = self.ctx.brain._think_deterministic(text, ctx)
            if thinking_mid:
                fallback_card = CardRenderer.result(
                    "已切换到备用模式",
                    "AI处理遇到问题，正在使用备用模式响应。",
                    success=True,
                )
                self.ctx.messaging.update_card(thinking_mid, fallback_card)

        # Handle simple responses directly
        if plan.action in ("chat", "clarify", "noop"):
            reply = plan.reply or "我不太确定你的意思，能再描述一下吗？"
            ctx.push("bot", reply[:200])
            if thinking_mid:
                chat_card = CardRenderer.result("回复", reply, success=True)
                self.ctx.messaging.update_card(thinking_mid, chat_card)
            else:
                self.ctx.messaging.reply_text(message_id, reply)
            return plan, thinking_mid

        # Check for risk level and confirmation requirements
        task_text = plan.params.get("task", "")
        has_running = any(
            s.process_status == "running" for s in self.ctx.session_mgr.list_sessions()
        )
        risk = classify_risk(plan.action, task_text, has_running)

        if (
            risk == RiskLevel.CONFIRM_REQUIRED
            and not force_flag
            and not self.ctx.confirm_mgr.should_bypass(plan.action)
        ):
            pending = self.ctx.confirm_mgr.create(
                action=plan.action,
                params=plan.params,
                summary=plan.confirm_summary or plan.action,
                risk_level=risk,
                can_undo=(plan.action == "stop_workspace"),
            )
            from sail_bot.context import PendingConfirmation

            ctx.pending = PendingConfirmation(
                action=plan.action,
                params=plan.params,
                summary=pending.summary,
                expires_at=datetime.now() + self.ctx.brain._CONFIRM_TTL,
            )
            card = CardRenderer.confirmation(
                action_summary=pending.summary,
                risk_level=risk.value,
                can_undo=pending.can_undo,
                pending_id=pending.pending_id,
            )
            if thinking_mid:
                self.ctx.messaging.update_card(thinking_mid, card)
                self.ctx.messaging.card_tracker.register(
                    thinking_mid, "confirmation", {"pending_id": pending.pending_id}
                )
            else:
                self.ctx.messaging.reply_card(
                    message_id, card, "confirmation", {"pending_id": pending.pending_id}
                )
            ctx.push("bot", "需要确认: " + pending.summary)
            return ActionPlan(action="noop"), thinking_mid

        if risk == RiskLevel.GUARDED and not force_flag:
            running_count = sum(
                1
                for s in self.ctx.session_mgr.list_sessions()
                if s.process_status == "running"
            )
            if running_count >= 3:
                card = CardRenderer.result(
                    "资源提示",
                    "当前已有 "
                    + str(running_count)
                    + " 个会话运行中，继续启动可能影响性能。\n回复「确认」继续，或「取消」放弃。",
                    success=False,
                )
                ctx.pending = PendingConfirmation(
                    action=plan.action,
                    params=plan.params,
                    summary="在资源紧张时启动新会话",
                    expires_at=datetime.now() + self.ctx.brain._CONFIRM_TTL,
                )
                if thinking_mid:
                    self.ctx.messaging.update_card(thinking_mid, card)
                else:
                    self.ctx.messaging.reply_card(message_id, card)
                return ActionPlan(action="noop"), thinking_mid

        return plan, thinking_mid

    def _find_pending_id_from_text(self, text: str) -> Optional[str]:
        """Extract pending_id from text."""
        m = re.search(r"pending_id[=:]\s*([a-f0-9]{12})", text)
        return m.group(1) if m else None
