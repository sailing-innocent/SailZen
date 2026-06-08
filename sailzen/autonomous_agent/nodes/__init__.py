# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Agent-specific DAG node types
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""Agent-specific DAG node types for the autonomous agent.

These nodes extend NodeExecutor and are registered with NodeRegistry at daemon startup.
"""

from sailzen.autonomous_agent.nodes.sailzen_cli_node import SailZenCliNode
from sailzen.autonomous_agent.nodes.lark_notify_node import LarkNotifyNode
from sailzen.autonomous_agent.nodes.wellness_node import WellnessNode
from sailzen.autonomous_agent.nodes.state_check_node import StateCheckNode
from sailzen.autonomous_agent.nodes.llm_reasoning_node import LLMReasoningNode
from sailzen.autonomous_agent.nodes.reminder_emit_node import ReminderEmitNode
from sailzen.autonomous_agent.nodes.condition_node import ConditionNode

__all__ = [
    "SailZenCliNode",
    "LarkNotifyNode",
    "WellnessNode",
    "StateCheckNode",
    "LLMReasoningNode",
    "ReminderEmitNode",
    "ConditionNode",
]
