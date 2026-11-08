# -*- coding: utf-8 -*-
# @file reminder_emit_node.py
# @brief Emit a reminder to configured channels
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""ReminderEmitNode — emit reminders into the agent's notification queue.

Parameters:
  title: Reminder title
  content: Reminder body (supports Jinja2)
  priority: "low" | "normal" | "high" | "urgent"
  channel: "lark_im" | "lark_group" | "log"
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from jinja2 import Template, UndefinedError

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class ReminderEmitNode(NodeExecutor):
    """Emit reminders to notification queue."""

    node_type = "reminder_emit"

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("title"):
            return "Missing required param: title"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        title_template = ctx.params.get("title", "")
        content_template = ctx.params.get("content", "")
        priority = ctx.params.get("priority", "normal")
        channel = ctx.params.get("channel", "lark_im")

        # Render templates
        try:
            title = Template(title_template).render(
                upstream=ctx.upstream_results, **ctx.global_params
            )
            content = Template(content_template).render(
                upstream=ctx.upstream_results, **ctx.global_params
            )
        except UndefinedError:
            title = title_template
            content = content_template
        except Exception as exc:
            return NodeResult.fail(error=f"Template rendering failed: {exc}")

        logger.info("ReminderEmitNode: [%s] %s -> %s", priority, title, channel)

        # Store reminder in node result for downstream processing
        # In a real implementation, this would insert into agent_reminders table
        reminder_data = {
            "title": title,
            "content": content,
            "priority": priority,
            "channel": channel,
            "pipeline_run_id": ctx.run_id,
        }

        # Save to artifact for persistence
        if ctx.store:
            ctx.store.save_artifact(
                ctx.run_id,
                f"reminder_{ctx.node_id}.json",
                json.dumps(reminder_data, ensure_ascii=False, indent=2),
            )

        return NodeResult.ok(
            data=reminder_data,
            output=f"Reminder emitted: {title}",
        )
