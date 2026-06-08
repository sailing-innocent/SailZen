# -*- coding: utf-8 -*-
# @file state_check_node.py
# @brief HTTP health/state checks against sail_server
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""StateCheckNode — check server state before running dependent pipelines.

Parameters:
  endpoint: URL to check
  expected_status: Expected HTTP status code (default 200)
  extract_fields: JSON fields to extract from response
  timeout: Request timeout in seconds
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

logger = logging.getLogger(__name__)


class StateCheckNode(NodeExecutor):
    """HTTP health check node."""

    node_type = "state_check"

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("endpoint"):
            return "Missing required param: endpoint"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        endpoint = ctx.params.get("endpoint")
        expected_status = ctx.params.get("expected_status", 200)
        extract_fields = ctx.params.get("extract_fields", [])
        timeout = ctx.params.get("timeout", 10)

        logger.info("StateCheckNode: GET %s (expect %s)", endpoint, expected_status)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(endpoint)

            status_ok = response.status_code == expected_status
            data = {
                "status_code": response.status_code,
                "ok": status_ok,
                "latency_ms": response.elapsed.total_seconds() * 1000 if hasattr(response, 'elapsed') else None,
            }

            # Extract JSON fields if response is JSON
            if extract_fields and response.headers.get("content-type", "").startswith("application/json"):
                try:
                    json_body = response.json()
                    for field in extract_fields:
                        if field in json_body:
                            data[field] = json_body[field]
                except Exception as exc:
                    logger.warning("Failed to extract JSON fields: %s", exc)

            if status_ok:
                return NodeResult.ok(
                    data=data,
                    output=f"Health check passed: {endpoint} ({response.status_code})",
                )
            else:
                return NodeResult.fail(
                    error=f"Health check failed: expected {expected_status}, got {response.status_code}",
                    data=data,
                )

        except httpx.TimeoutException:
            return NodeResult.fail(
                error=f"Health check timed out after {timeout}s",
                data={"ok": False},
            )
        except Exception as exc:
            return NodeResult.fail(
                error=f"Health check error: {exc}",
                data={"ok": False},
            )
