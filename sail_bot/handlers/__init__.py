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
"""

from .base import HandlerContext, BaseHandler
from .message_handler import MessageHandler
from .card_action import CardActionHandler
from .plan_executor import PlanExecutor
from .command_handlers import HelpHandler, StatusHandler
from .workspace_handlers import (
    StartWorkspaceHandler,
    StopWorkspaceHandler,
    SwitchWorkspaceHandler,
)
from .task_handler import TaskHandler
from .self_update_handler import SelfUpdateHandler
from .lifecycle_manager import LifecycleManager

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
]
