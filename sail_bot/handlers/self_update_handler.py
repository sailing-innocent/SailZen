# -*- coding: utf-8 -*-
# @file self_update_handler.py
# @brief Self-update handler
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Self-update handler for bot self-update functionality.

This module handles the self-update confirmation and execution flow.
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
        trigger_source: str = "manual",
        reason: str = "User requested update",
    ) -> None:
        """Handle self-update request.

        Args:
            chat_id: Target chat ID
            message_id: Message to reply to
            ctx: Conversation context
            trigger_source: Source of update trigger
            reason: Human-readable reason
        """
        # Check if self-update is available
        if not self.ctx.self_update_enabled:
            self.ctx.messaging.reply_text(
                message_id,
                "❌ 自更新功能不可用。\n\n"
                "可能原因：\n"
                "- 缺少必要的依赖模块\n"
                "- 初始化失败\n\n"
                "请检查日志或联系管理员。",
            )
            return

        # Create pending action in confirm_mgr to get a proper pending_id
        from sail_bot.session_state import RiskLevel

        pending = self.ctx.confirm_mgr.create(
            action="confirm_self_update",
            params={
                "trigger_source": trigger_source,
                "reason": reason,
                "chat_id": chat_id,
                "message_id": message_id,
            },
            summary="确认更新 Bot",
            detail=f"更新原因: {reason}",
            risk_level=RiskLevel.CONFIRM_REQUIRED,
            timeout_seconds=300.0,
        )

        # Send confirmation card with the pending_id
        confirm_card = CardRenderer.confirmation(
            action_summary="🔄 确认更新 Bot",
            action_detail=f"**更新原因:** {reason}\n\n"
            "更新流程：\n"
            "1. 备份当前会话状态\n"
            "2. 断开飞书连接\n"
            "3. 启动新进程 (uv run)\n"
            "4. 恢复会话状态\n"
            "5. 优雅关闭旧进程\n\n"
            "⚠️ 更新期间 Bot 会短暂离线 (约 5-10 秒)",
            risk_level="confirm_required",
            timeout_minutes=5,
            pending_id=pending.pending_id,
        )

        self.ctx.messaging.reply_card(message_id, confirm_card)
        ctx.push("bot", "等待用户确认更新")
