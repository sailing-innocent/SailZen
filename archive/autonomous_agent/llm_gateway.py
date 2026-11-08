# -*- coding: utf-8 -*-
# @file llm_gateway.py
# @brief Direct LLM clients for agent reasoning
# @author sailing-innocent
# @date 2025-06-02
# @version 1.0
# ---------------------------------
"""LLMGateway — direct LLM clients for Kimi and DeepSeek.

Independent of sail_server.utils.llm. Used for agent-specific reasoning.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    usage: Optional[Dict[str, Any]] = None
    model: str = ""
    provider: str = ""


class LLMGateway:
    """Direct LLM gateway for the autonomous agent.

    Usage::

        gateway = LLMGateway(config.llm)
        response = await gateway.reason("Analyze this data...", provider="kimi")
        response = await gateway.generate("Write a summary...", provider="deepseek")
    """

    def __init__(self, config):
        self.config = config
        self._clients: Dict[str, httpx.AsyncClient] = {}

    def _get_client(self, provider: str) -> httpx.AsyncClient:
        if provider not in self._clients:
            self._clients[provider] = httpx.AsyncClient(timeout=120.0)
        return self._clients[provider]

    def _get_provider_config(self, provider: str) -> Any:
        if provider not in self.config.providers:
            raise ValueError(f"Unknown LLM provider: {provider}. "
                             f"Configured: {list(self.config.providers.keys())}")
        return self.config.providers[provider]

    async def reason(self, prompt: str, provider: Optional[str] = None, **kwargs) -> LLMResponse:
        """Agent reasoning — low temperature, deterministic.

        Args:
            prompt: The reasoning prompt.
            provider: LLM provider name. Defaults to config.default_reasoning.
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse
        """
        provider = provider or self.config.default_reasoning
        kwargs.setdefault("temperature", 0.3)
        kwargs.setdefault("max_tokens", 2000)
        return await self._chat_complete(prompt, provider, **kwargs)

    async def generate(self, prompt: str, provider: Optional[str] = None, **kwargs) -> LLMResponse:
        """Creative generation — higher temperature.

        Args:
            prompt: The generation prompt.
            provider: LLM provider name. Defaults to config.default_generation.
            **kwargs: Additional parameters.

        Returns:
            LLMResponse
        """
        provider = provider or self.config.default_generation
        kwargs.setdefault("temperature", 0.7)
        kwargs.setdefault("max_tokens", 4000)
        return await self._chat_complete(prompt, provider, **kwargs)

    async def _chat_complete(self, prompt: str, provider: str, **kwargs) -> LLMResponse:
        prov_cfg = self._get_provider_config(provider)
        api_key = prov_cfg.api_key or os.environ.get(f"{provider.upper()}_API_KEY", "")
        if not api_key:
            raise ValueError(f"No API key configured for provider: {provider}")

        model = prov_cfg.model or kwargs.pop("model", self._default_model(provider))
        base_url = prov_cfg.base_url or self._default_base_url(provider)

        messages = [{"role": "user", "content": prompt}]
        if provider == "kimi" and kwargs.get("system"):
            messages.insert(0, {"role": "system", "content": kwargs.pop("system")})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client(provider)
        url = f"{base_url.rstrip('/')}/chat/completions"

        logger.debug("LLM request to %s: model=%s", provider, model)
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"] if data.get("choices") else ""
            usage = data.get("usage")

            logger.debug("LLM response from %s: tokens=%s", provider, usage)
            return LLMResponse(
                content=content,
                usage=usage,
                model=model,
                provider=provider,
            )
        except httpx.HTTPStatusError as exc:
            logger.error("LLM HTTP error from %s: %s - %s", provider, exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("LLM error from %s: %s", provider, exc)
            raise

    def _default_model(self, provider: str) -> str:
        defaults = {
            "kimi": "kimi-k2.5",
            "deepseek": "deepseek-chat",
        }
        return defaults.get(provider, "unknown")

    def _default_base_url(self, provider: str) -> str:
        defaults = {
            "kimi": "https://api.moonshot.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }
        return defaults.get(provider, "")

    async def close(self) -> None:
        """Close all HTTP clients."""
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    # ── Cost guardrails ───────────────────────────────────────────────

    def estimate_cost(self, response: LLMResponse) -> float:
        """Rough cost estimation in USD."""
        if not response.usage:
            return 0.0
        prompt_tokens = response.usage.get("prompt_tokens", 0)
        completion_tokens = response.usage.get("completion_tokens", 0)
        # Rough pricing per 1K tokens
        pricing = {
            "kimi": {"prompt": 0.002, "completion": 0.006},
            "deepseek": {"prompt": 0.0014, "completion": 0.0028},
        }
        p = pricing.get(response.provider, {"prompt": 0.01, "completion": 0.03})
        return (prompt_tokens / 1000 * p["prompt"] +
                completion_tokens / 1000 * p["completion"])
