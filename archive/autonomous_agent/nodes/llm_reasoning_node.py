# -*- coding: utf-8 -*-
# @file llm_reasoning_node.py
# @brief Direct LLM call for agent reasoning
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""LLMReasoningNode — direct LLM call for agent decision-making.

Parameters:
  prompt_template: Jinja2 template for the prompt
  provider: "kimi" | "deepseek"
  temperature: Sampling temperature
  max_tokens: Max output tokens
  system_prompt: Optional system prompt
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from jinja2 import Template, UndefinedError

from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult
from sailzen.autonomous_agent.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class LLMReasoningNode(NodeExecutor):
    """Direct LLM reasoning node."""

    node_type = "llm_reasoning"

    def __init__(self):
        # LLMGateway will be initialized per-execution or shared via context
        self._gateway: LLMGateway = None

    def validate_params(self, params: Dict[str, Any]) -> str:
        if not params.get("prompt_template"):
            return "Missing required param: prompt_template"
        return None

    async def execute(self, ctx: NodeContext) -> NodeResult:
        prompt_template = ctx.params.get("prompt_template", "")
        provider = ctx.params.get("provider", "kimi")
        temperature = ctx.params.get("temperature", 0.3)
        max_tokens = ctx.params.get("max_tokens", 2000)
        system_prompt = ctx.params.get("system_prompt", "")

        # Render prompt template with upstream results
        try:
            template = Template(prompt_template)
            rendered = template.render(upstream=ctx.upstream_results, **ctx.global_params)
        except UndefinedError as exc:
            logger.warning("Template rendering error: %s", exc)
            rendered = prompt_template
        except Exception as exc:
            return NodeResult.fail(error=f"Template rendering failed: {exc}")

        # Initialize gateway if needed
        if not self._gateway:
            from sailzen.autonomous_agent.config import load_agent_config
            cfg = load_agent_config()
            self._gateway = LLMGateway(cfg.llm)

        logger.info("LLMReasoningNode: provider=%s temp=%s tokens=%s",
                    provider, temperature, max_tokens)

        try:
            kwargs = {"temperature": temperature, "max_tokens": max_tokens}
            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self._gateway.reason(rendered, provider=provider, **kwargs)

            return NodeResult.ok(
                data={
                    "response": response.content,
                    "usage": response.usage,
                    "model": response.model,
                    "provider": response.provider,
                },
                output=response.content[:500] + "..." if len(response.content) > 500 else response.content,
            )

        except Exception as exc:
            logger.exception("LLM reasoning failed")
            return NodeResult.fail(error=f"LLM reasoning error: {exc}")
