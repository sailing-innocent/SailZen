# -*- coding: utf-8 -*-
# @file shell_node.py
# @brief Shell 命令节点
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""执行本地 Shell 命令的节点。

参数::

    {
        "command": "echo hello",     # 必需
        "cwd": "",                   # 可选，工作目录
        "env": {},                   # 可选，环境变量
        "timeout": 300,              # 可选，秒
        "shell": true                # 可选，是否使用 shell
    }
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class ShellNode(NodeExecutor):
    """执行 Shell 命令的节点。"""

    node_type = "shell"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("command"):
            return "Missing required param: command"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        command = ctx.params.get("command")
        cwd = ctx.params.get("cwd") or ctx.working_dir or None
        env = ctx.params.get("env", {})
        timeout = ctx.params.get("timeout", 300)
        use_shell = ctx.params.get("shell", True)

        # 合并环境变量
        run_env = {**os.environ, **env}

        logger.info("ShellNode %s: executing command: %s", ctx.node_id, command[:80])

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env,
            ) if use_shell else await asyncio.create_subprocess_exec(
                *command.split(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=run_env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # 保存日志
            if ctx.store:
                ctx.store.write_log(ctx.run_id, f"{ctx.node_id}_stdout.log", stdout_text)
                ctx.store.write_log(ctx.run_id, f"{ctx.node_id}_stderr.log", stderr_text)

            if proc.returncode == 0:
                return NodeResult.ok(
                    data={"returncode": 0, "stderr": stderr_text},
                    output=stdout_text,
                )
            else:
                return NodeResult.fail(
                    f"Exit code {proc.returncode}",
                    data={"returncode": proc.returncode, "stdout": stdout_text, "stderr": stderr_text},
                )

        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return NodeResult.fail(f"Command timeout after {timeout}s")
        except Exception as exc:
            logger.exception("ShellNode execute error")
            return NodeResult.fail(str(exc))
