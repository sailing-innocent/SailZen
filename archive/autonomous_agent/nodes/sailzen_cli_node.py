# -*- coding: utf-8 -*-
# @file sailzen_cli_node.py
# @brief Invoke sailzen CLI commands
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""SailZenCliNode — invokes `sailzen` CLI commands as DAG nodes.

Parameters:
  module: "finance" | "health"
  command: CLI subcommand
  args: List of arguments
  timeout: Max execution time in seconds
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class SailZenCliNode(NodeExecutor):
    """Execute sailzen CLI commands."""

    node_type = "sailzen_cli"

    def validate_params(self, params: Dict[str, Any]) -> str:
        module = params.get("module")
        if not module:
            return "Missing required param: module"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        module = ctx.params.get("module")
        command = ctx.params.get("command", "")
        args = ctx.params.get("args", [])
        timeout = ctx.params.get("timeout", 300)
        output_file = ctx.params.get("output_file", "")

        cmd = ["sailzen", module]
        if command:
            cmd.append(command)
        for arg in args:
            cmd.append(str(arg))

        logger.info("SailZenCliNode executing: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return NodeResult.fail(
                    error=f"Command failed with exit code {proc.returncode}: {stderr_text}",
                    data={"stdout": stdout_text, "stderr": stderr_text},
                )

            result_data = {"stdout": stdout_text, "stderr": stderr_text}

            # Save output to file if requested
            if output_file and ctx.store:
                ctx.store.save_artifact(ctx.run_id, output_file, stdout_text)
                result_data["output_file"] = output_file

            return NodeResult.ok(
                data=result_data,
                output=f"sailzen {module} {command} completed successfully",
            )

        except asyncio.TimeoutError:
            return NodeResult.fail(error=f"Command timed out after {timeout}s")
        except Exception as exc:
            return NodeResult.fail(error=f"Command execution error: {exc}")
