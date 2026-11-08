# -*- coding: utf-8 -*-
# @file llm.py
# @brief SailTick LLM 网关（直连 deepseek/kimi + 每 Tick 成本记账与护栏）
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""LLMGateway — 从旧 autonomous_agent/llm_gateway.py 迁移修复。

变更:
  - 增加每 Tick token 记账（write_to=TickDatabase.add_tick_cost）
  - 增加每 Tick / 每日软上限（护栏，超限时调用方应降级或截断）
  - provider 默认 deepseek（flash 级视为无限量，仅防代码 bug 失控）
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """标准化 LLM 响应。"""

    content: str
    usage: Optional[Dict[str, Any]] = None
    model: str = ""
    provider: str = ""


class BudgetExceededError(RuntimeError):
    """当次调用会超出本 Tick token 预算。"""


class LLMGateway:
    """直连 LLM 网关，带成本记账与软上限。"""

    def __init__(self, config, cost_sink: Optional[Callable[[int, float], Any]] = None):
        """Args:
        config: sailtick.config.LLMConfig
        cost_sink: 异步回调 (tokens, usd) -> None，用于写入 st_ticks
        """
        self.config = config
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._cost_sink = cost_sink
        self._tick_tokens = 0
        self._budget_exceeded = False

    def begin_tick(self) -> None:
        """每个 Tick 开始时重置计数。"""
        self._tick_tokens = 0
        self._budget_exceeded = False

    @property
    def tick_tokens(self) -> int:
        return self._tick_tokens

    @property
    def budget_exceeded(self) -> bool:
        return self._budget_exceeded

    async def chat(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system: Optional[str] = None,
        expect_json: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """单轮对话。expect_json=True 时附加 JSON 输出约束。"""
        provider = provider or self.config.default
        kwargs.setdefault("temperature", 0.3)
        kwargs.setdefault("max_tokens", 2000)

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if expect_json:
            prompt = (
                prompt
                + "\n\n只输出 JSON（不要 markdown 代码围栏，不要任何其他文字）。"
            )
        messages.append({"role": "user", "content": prompt})

        return await self._chat_messages(messages, provider, **kwargs)

    async def _chat_messages(
        self, messages: list, provider: str, **kwargs: Any
    ) -> LLMResponse:
        prov_cfg = self._provider_config(provider)
        api_key = prov_cfg.api_key or os.environ.get(f"{provider.upper()}_API_KEY", "")
        if not api_key:
            raise ValueError(f"No API key configured for provider: {provider}")

        model = prov_cfg.model or self._default_model(provider)
        base_url = prov_cfg.base_url or self._default_base_url(provider)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        client = self._get_client(provider)
        url = f"{base_url.rstrip('/')}/chat/completions"

        logger.debug("LLM request to %s: model=%s", provider, model)
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"] if data.get("choices") else ""
        usage = data.get("usage") or {}
        total_tokens = usage.get("total_tokens", 0)

        result = LLMResponse(content=content, usage=usage, model=model, provider=provider)

        # 记账
        self._tick_tokens += total_tokens
        usd = self.estimate_cost(result)
        if self._cost_sink is not None:
            await self._cost_sink(total_tokens, usd)

        # 软上限检查
        if self._tick_tokens > self.config.per_tick_token_cap:
            self._budget_exceeded = True
            logger.warning(
                "Per-tick token cap exceeded: %d > %d",
                self._tick_tokens, self.config.per_tick_token_cap,
            )

        return result

    def _provider_config(self, provider: str) -> Any:
        if provider not in self.config.providers:
            raise ValueError(
                f"Unknown LLM provider: {provider}. Configured: {list(self.config.providers.keys())}"
            )
        return self.config.providers[provider]

    def _get_client(self, provider: str) -> httpx.AsyncClient:
        if provider not in self._clients:
            self._clients[provider] = httpx.AsyncClient(timeout=120.0)
        return self._clients[provider]

    @staticmethod
    def _default_model(provider: str) -> str:
        return {
            "kimi": "kimi-k2.5",
            "deepseek": "deepseek-chat",
        }.get(provider, "deepseek-chat")

    @staticmethod
    def _default_base_url(provider: str) -> str:
        return {
            "kimi": "https://api.moonshot.cn/v1",
            "deepseek": "https://api.deepseek.com/v1",
        }.get(provider, "")

    def estimate_cost(self, response: LLMResponse) -> float:
        """粗略成本估算（USD）。"""
        if not response.usage:
            return 0.0
        prompt_tokens = response.usage.get("prompt_tokens", 0)
        completion_tokens = response.usage.get("completion_tokens", 0)
        pricing = {
            "kimi": {"prompt": 0.002, "completion": 0.006},
            "deepseek": {"prompt": 0.0014, "completion": 0.0028},
        }
        p = pricing.get(response.provider, {"prompt": 0.01, "completion": 0.03})
        return prompt_tokens / 1000 * p["prompt"] + completion_tokens / 1000 * p["completion"]

    async def close(self) -> None:
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
