# -*- coding: utf-8 -*-
# @file lark_notify_node.py
# @brief Send Lark IM / group messages
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""LarkNotifyNode — send Lark notifications from DAG pipelines.

Parameters:
  channel: "im" | "group"
  target: user_open_id or chat_id
  content: Message content (supports Jinja2 templating with upstream data)
  content_type: "text" | "markdown" | "post"
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from jinja2 import Template, UndefinedError

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class LarkNotifyNode(NodeExecutor):
    """Send Lark notifications."""

    node_type = "lark_notify"

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("content"):
            return "Missing required param: content"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        channel = ctx.params.get("channel", "im")
        target = ctx.params.get("target", "")
        content_template = ctx.params.get("content", "")
        content_type = ctx.params.get("content_type", "text")

        # Render Jinja2 template with upstream results
        try:
            template = Template(content_template)
            rendered = template.render(upstream=ctx.upstream_results, **ctx.global_params)
        except UndefinedError as exc:
            logger.warning("Template rendering error, using raw content: %s", exc)
            rendered = content_template
        except Exception as exc:
            return NodeResult.fail(error=f"Template rendering failed: {exc}")

        # Determine target
        if not target:
            target = ctx.global_params.get("lark_user_open_id", "")

        logger.info("LarkNotifyNode: channel=%s target=%s type=%s", channel, target, content_type)

        try:
            if channel == "im":
                cmd = [
                    "lark-cli", "im", "send-message",
                    "--receive-id", target,
                    "--content", rendered,
                ]
            elif channel == "group":
                cmd = [
                    "lark-cli", "im", "send-message",
                    "--receive-id-type", "chat_id",
                    "--receive-id", target,
                    "--content", rendered,
                ]
            else:
                return NodeResult.fail(error=f"Unknown channel: {channel}")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode != 0:
                return NodeResult.fail(
                    error=f"lark-cli failed: {stderr.decode('utf-8', errors='replace')}",
                )

            return NodeResult.ok(
                data={"channel": channel, "target": target, "content_length": len(rendered)},
                output=f"Lark message sent to {channel}",
            )

        except asyncio.TimeoutError:
            return NodeResult.fail(error="Lark notification timed out")
        except Exception as exc:
            return NodeResult.fail(error=f"Lark notification error: {exc}")
