# -*- coding: utf-8 -*-
# @file self_update_handler.py
# @brief Self-update handler (v2.0 simplified)
# @author sailing-innocent
# @date 2026-04-25
# @version 2.0
# ---------------------------------
"""Self-update handler for bot self-update functionality.

v2.0: 精简确认流程，使用简化后的 SelfUpdateOrchestrator (exit code 42)。
"""

from typing import Optional

from sail_bot.handlers.base import BaseHandler, HandlerContext
from sail_bot.context import ConversationContext
from sail_bot.card_renderer import CardRenderer


class SelfUpdateHandler(BaseHandler):
    """Handler for self-update requests."""

    def handle(
        self,
        chat_id: str,
        message_id: str,
        ctx: ConversationContext,
        reason: str = "用户手动触发",
    ) -> None:
        """Handle self-update request."""
        from sail_bot.session_state import RiskLevel

        pending = self.ctx.confirm_mgr.create(
            action="confirm_self_update",
            params={
                "reason": reason,
                "chat_id": chat_id,
            },
            summary="确认更新 Bot",
            detail=f"更新原因: {reason}",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            timeout_seconds=300.0,
        )

        confirm_card = CardRenderer.confirmation(
            action_summary="🔄 确认更新 Bot",
            action_detail=(
                f"**更新原因:** {reason}\n\n"
                "更新流程：\n"
                "1. Bot 退出 (exit code 42)\n"
                "2. Watcher 执行 git pull\n"
                "3. Watcher 重启 Bot\n\n"
                "⚠️ 更新期间 Bot 会短暂离线"
            ),
            risk_level="confirm_required",
            timeout_minutes=5,
            pending_id=pending.pending_id,
        )

        self.ctx.messaging.reply_card(message_id, confirm_card)
        ctx.push("bot", "等待用户确认更新")
