# -*- coding: utf-8 -*-
# @file base.py
# @brief Handler base class and context
# @author sailing-innocent
# @date 2026-04-25
# @version 2.0
# ---------------------------------
"""Base handler class and context for all handlers.

v2.0: 使用 sail.opencode 基础设施层替代旧的 session_manager/async_task_manager。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from sail_bot.messaging.client import FeishuMessagingClient
    from sail_bot.config import AgentConfig
    from sail_bot.brain import BotBrain
    from sail_bot.context import ConversationContext
    from sail_bot.session_state import (
        SessionStateStore,
        OperationTracker,
        ConfirmationManager,
    )
    from sail.opencode import OpenCodeProcessManager


@dataclass
class HandlerContext:
    """Context object passed to all handlers.
    所有 handler 通过此对象访问依赖，避免与 agent 类紧耦合。
    """
    messaging: "FeishuMessagingClient"
    process_mgr: "OpenCodeProcessManager"
    state_store: "SessionStateStore"

    # Operation tracking
    op_tracker: "OperationTracker"
    confirm_mgr: "ConfirmationManager"

    # AI brain
    brain: "BotBrain"

    # Configuration
    config: "AgentConfig"

    # Bot reference for callbacks
    agent: Optional[Any] = None

    def get_or_create_context(self, chat_id: str) -> "ConversationContext":
        """Get or create conversation context for a chat."""
        if self.agent:
            return self.agent._get_context(chat_id)
        raise NotImplementedError("Agent reference not set")

    def save_contexts(self) -> None:
        """Save conversation contexts to disk."""
        if self.agent:
            self.agent._save_contexts()

    def request_self_update(
        self,
        reason: str = "用户手动触发",
    ) -> dict:
        """Request self-update of the bot. Returns {"success": bool, "message": str}."""
        if self.agent and hasattr(self.agent, "_update_orchestrator"):
            return self.agent._update_orchestrator.request_update(reason=reason)
        return {"success": False, "message": "Self-update not available"}


class BaseHandler:
    """Base class for all handlers."""

    def __init__(self, ctx: HandlerContext):
        self.ctx = ctx

    def handle(self, *args, **kwargs) -> Any:
        """Main entry point for handling. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement handle()")
