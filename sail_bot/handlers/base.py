# -*- coding: utf-8 -*-
# @file base.py
# @brief Handler base class and context
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Base handler class and context for all handlers.

This module provides the foundation for the handler pattern,
allowing clean separation of concerns in the bot agent.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Any

# Import types only for type checking to avoid circular imports
if TYPE_CHECKING:
    from sail_bot.messaging.client import FeishuMessagingClient
    from sail_bot.session_manager import OpenCodeSessionManager
    from sail_bot.config import AgentConfig
    from sail_bot.brain import BotBrain
    from sail_bot.context import ConversationContext
    from sail_bot.session_state import (
        SessionStateStore,
        OperationTracker,
        ConfirmationManager,
    )


@dataclass
class HandlerContext:
    """Context object passed to all handlers.

    This provides handlers with access to all necessary dependencies
    without creating tight coupling to the agent class.
    """

    # Messaging
    messaging: "FeishuMessagingClient"

    # Session management
    session_mgr: "OpenCodeSessionManager"
    state_store: "SessionStateStore"

    # Operation tracking
    op_tracker: "OperationTracker"
    confirm_mgr: "ConfirmationManager"

    # AI brain
    brain: "BotBrain"

    # Configuration
    config: "AgentConfig"

    # Self-update support
    self_update_enabled: bool = True

    # Bot reference for callbacks (optional)
    agent: Optional[Any] = None

    def get_or_create_context(self, chat_id: str) -> "ConversationContext":
        """Get or create conversation context for a chat.

        This is implemented by the agent and passed through.
        """
        if self.agent:
            return self.agent._get_context(chat_id)
        raise NotImplementedError("Agent reference not set")

    def save_contexts(self) -> None:
        """Save conversation contexts to disk."""
        if self.agent:
            self.agent._save_contexts()

    def request_self_update(
        self,
        trigger_source: str = "manual",
        reason: str = "User requested update",
        initiated_by: Optional[str] = None,
    ) -> Any:
        """Request self-update of the bot."""
        if self.agent:
            from sail_bot.async_task_manager import run_async

            return run_async(
                self.agent.request_self_update(
                    trigger_source=trigger_source,
                    reason=reason,
                    initiated_by=initiated_by,
                )
            )
        raise NotImplementedError("Agent reference not set")


class BaseHandler:
    """Base class for all handlers.

    Handlers encapsulate specific functionality and receive
    all dependencies through HandlerContext.
    """

    def __init__(self, ctx: HandlerContext):
        self.ctx = ctx

    def handle(self, *args, **kwargs) -> Any:
        """Main entry point for handling. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement handle()")
