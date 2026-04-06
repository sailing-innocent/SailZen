# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Handlers package initialization
# @author sailing-innocent
# @date 2026-04-06
# @version 1.0
# ---------------------------------
"""Message and command handlers for Feishu Bot.

This package contains handlers for different types of bot interactions:
- MessageHandler: Handles incoming message parsing and routing
- CardActionHandler: Handles interactive card button clicks
- PlanExecutor: Routes ActionPlans to specific handlers
- Command handlers: HelpHandler, StatusHandler
- Workspace handlers: StartWorkspaceHandler, StopWorkspaceHandler, SwitchWorkspaceHandler
- TaskHandler: Handles task execution
- SelfUpdateHandler: Handles bot self-update
- LifecycleManager: Handles startup/shutdown/cleanup
- WelcomeHandler: Handles welcome messages for new P2P chats
"""

from sail_bot.handlers.base import HandlerContext, BaseHandler
from sail_bot.handlers.message_handler import MessageHandler
from sail_bot.handlers.card_action import CardActionHandler
from sail_bot.handlers.plan_executor import PlanExecutor
from sail_bot.handlers.command_handlers import HelpHandler, StatusHandler
from sail_bot.handlers.workspace_handlers import (
    StartWorkspaceHandler,
    StopWorkspaceHandler,
    SwitchWorkspaceHandler,
)
from sail_bot.handlers.task_handler import TaskHandler
from sail_bot.handlers.self_update_handler import SelfUpdateHandler
from sail_bot.handlers.lifecycle_manager import LifecycleManager
from sail_bot.handlers.welcome_handler import WelcomeHandler

__all__ = [
    "HandlerContext",
    "BaseHandler",
    "MessageHandler",
    "CardActionHandler",
    "PlanExecutor",
    "HelpHandler",
    "StatusHandler",
    "StartWorkspaceHandler",
    "StopWorkspaceHandler",
    "SwitchWorkspaceHandler",
    "TaskHandler",
    "SelfUpdateHandler",
    "LifecycleManager",
    "WelcomeHandler",
]
