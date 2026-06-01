# -*- coding: utf-8 -*-
# @file python_node.py
# @brief Python 代码节点
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""执行 Python 代码的节点。

参数::

    {
        "code": "print(ctx.params['message'])",  # 必需
        "timeout": 300,
        "inject_ctx": true  # 是否将 ctx 注入为全局变量
    }
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class PythonNode(NodeExecutor):
    """执行 Python 代码的节点。"""

    node_type = "python"

    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        if not params.get("code"):
            return "Missing required param: code"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        code = ctx.params.get("code")
        timeout = ctx.params.get("timeout", 300)
        inject_ctx = ctx.params.get("inject_ctx", True)

        logger.info("PythonNode %s: executing code (%d chars)", ctx.node_id, len(code))

        # 在独立线程中运行 Python 代码（避免阻塞 event loop）
        def _run():
            local_ns: Dict[str, Any] = {}
            if inject_ctx:
                local_ns["ctx"] = ctx
                local_ns["upstream"] = ctx.upstream_results
                local_ns["params"] = ctx.params
                local_ns["global_params"] = ctx.global_params

            exec(code, {"__builtins__": __builtins__}, local_ns)
            return local_ns

        try:
            local_ns = await asyncio.wait_for(
                asyncio.to_thread(_run), timeout=timeout
            )

            result_data = {k: v for k, v in local_ns.items() if not k.startswith("_")}
            output = str(result_data.get("result", result_data))

            return NodeResult.ok(data=result_data, output=output)

        except asyncio.TimeoutError:
            return NodeResult.fail(f"Python code timeout after {timeout}s")
        except Exception as exc:
            logger.exception("PythonNode execute error")
            return NodeResult.fail(str(exc))
