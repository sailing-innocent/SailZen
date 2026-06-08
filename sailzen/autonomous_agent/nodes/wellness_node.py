# -*- coding: utf-8 -*-
# @file wellness_node.py
# @brief Trigger sailzen-wellness skill
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""WellnessNode — trigger wellness analysis via OpenCode skill or direct script.

Parameters:
  start_date: Analysis start date
  end_date: Analysis end date
  label: Output label
  output_format: "markdown" | "json"
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class WellnessNode(NodeExecutor):
    """Run wellness analysis."""

    node_type = "wellness"

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("start_date"):
            return "Missing required param: start_date"
        if not params.get("end_date"):
            return "Missing required param: end_date"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        start_date = ctx.params.get("start_date")
        end_date = ctx.params.get("end_date")
        label = ctx.params.get("label", "wellness_analysis")
        output_format = ctx.params.get("output_format", "markdown")

        logger.info("WellnessNode: %s to %s, label=%s", start_date, end_date, label)

        # Try OpenCode skill first
        if ctx.opencode_client:
            try:
                result = await ctx.opencode_client.run_skill(
                    skill="sailzen-wellness",
                    params={
                        "start_date": start_date,
                        "end_date": end_date,
                        "label": label,
                        "output_format": output_format,
                    },
                )
                return NodeResult.ok(
                    data=result,
                    output=f"Wellness analysis completed: {label}",
                )
            except Exception as exc:
                logger.warning("OpenCode wellness skill failed, falling back: %s", exc)

        # Fallback: run underlying script directly
        try:
            cmd = [
                "uv", "run", "python", "-m", "sailzen.wellness",
                "--start", start_date,
                "--end", end_date,
                "--label", label,
                "--format", output_format,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300.0)

            stdout_text = stdout.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return NodeResult.fail(
                    error=f"Wellness script failed: {stderr.decode('utf-8', errors='replace')}",
                )

            return NodeResult.ok(
                data={"output": stdout_text},
                output=f"Wellness analysis completed: {label}",
            )

        except asyncio.TimeoutError:
            return NodeResult.fail(error="Wellness analysis timed out")
        except Exception as exc:
            return NodeResult.fail(error=f"Wellness analysis error: {exc}")
