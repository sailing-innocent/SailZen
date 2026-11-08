# -*- coding: utf-8 -*-
# @file condition_node.py
# @brief Branching logic based on state/memory
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""ConditionNode — branching logic with Jinja2 expressions.

Parameters:
  condition: Jinja2 expression evaluated against upstream results
  true_next: List of node IDs to execute if true
  false_next: List of node IDs to execute if false
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from jinja2 import UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class ConditionNode(NodeExecutor):
    """Conditional branching node."""

    node_type = "condition"

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("condition"):
            return "Missing required param: condition"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        condition_expr = ctx.params.get("condition", "")
        true_next = ctx.params.get("true_next", [])
        false_next = ctx.params.get("false_next", [])

        # Build evaluation context
        eval_ctx = {
            "upstream": ctx.upstream_results,
            **ctx.global_params,
        }

        # Evaluate condition safely using sandboxed Jinja2
        condition_met = False
        try:
            env = SandboxedEnvironment()
            template = env.from_string("{{ " + condition_expr + " }}")
            result_str = template.render(**eval_ctx).strip().lower()
            condition_met = result_str in ("true", "1", "yes", "ok")
        except UndefinedError:
            # If upstream data missing, treat as false
            condition_met = False
        except Exception as exc:
            logger.warning("Condition evaluation error: %s", exc)
            condition_met = False

        logger.info("ConditionNode: '%s' -> %s", condition_expr, condition_met)

        next_nodes = true_next if condition_met else false_next

        return NodeResult(
            success=True,
            data={
                "condition": condition_expr,
                "result": condition_met,
                "next_nodes": next_nodes,
            },
            output=f"Condition {'met' if condition_met else 'not met'}",
            next_nodes=[{"id": nid, "type": "skill", "name": nid} for nid in next_nodes],
        )
