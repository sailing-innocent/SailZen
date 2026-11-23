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
import time
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
    latency_ms: float = 0.0
    finish_reason: str = ""
    reasoning_content: str = ""
    cost_usd: float = 0.0


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
        self._tick_usd = 0.0
        self._cost_recorded_by_sink = False
        self._budget_exceeded = False

    def begin_tick(self) -> None:
        """每个 Tick 开始时重置计数。"""
        self._tick_tokens = 0
        self._tick_usd = 0.0
        self._cost_recorded_by_sink = False
        self._budget_exceeded = False

    @property
    def tick_tokens(self) -> int:
        return self._tick_tokens

    @property
    def tick_usd(self) -> float:
        return self._tick_usd

    @property
    def cost_recorded_by_sink(self) -> bool:
        return self._cost_recorded_by_sink

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

        if expect_json:
            kwargs.setdefault("expect_json", True)

        return await self._chat_messages(messages, provider, **kwargs)

    async def _chat_messages(
        self, messages: list, provider: str, **kwargs: Any
    ) -> LLMResponse:
        prov_cfg = self._provider_config(provider)
        if provider == "kimi":
            api_key = (
                prov_cfg.api_key
                or os.environ.get("KIMI_API_KEY", "")
                or os.environ.get("MOONSHOT_API_KEY", "")
            )
        else:
            api_key = prov_cfg.api_key or os.environ.get(f"{provider.upper()}_API_KEY", "")
        if not api_key:
            raise ValueError(f"No API key configured for provider: {provider}")

        model = prov_cfg.model or self._default_model(provider)
        base_url = prov_cfg.base_url or self._default_base_url(provider)

        # Kimi Coding Plan key（sk-kimi-...）默认路由至 api.kimi.com/coding/v1
        if provider == "kimi" and api_key.startswith("sk-kimi-") and not prov_cfg.base_url:
            base_url = "https://api.kimi.com/coding/v1"
            if not prov_cfg.model:
                model = "kimi-for-coding"

        model_lower = model.lower()
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = int(kwargs.get("max_tokens", 2000))
        expect_json = bool(kwargs.get("expect_json", False))

        # kimi-k2.5 / kimi-for-coding 等推理模型接口要求 temperature=1（传 0.3 会返回 400）
        if "k2.5" in model_lower or "kimi-for-coding" in model_lower:
            temperature = 1.0

        # deepseek-reasoner 等推理模型的 max_tokens 同时包含 reasoning_content 与最终 content，
        # 若 max_tokens 偏小会导致思维链耗尽额度、JSON 在中途被截断（Unterminated string）。
        is_reasoner = "reasoner" in model_lower or "deepseek-r1" in model_lower
        if is_reasoner:
            max_tokens = max(max_tokens, 8192)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if not is_reasoner:
            payload["temperature"] = temperature
        if expect_json and provider in ("deepseek", "kimi"):
            payload["response_format"] = {"type": "json_object"}

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if "api.kimi.com/coding" in base_url:
            headers["User-Agent"] = "KimiCLI/1.0"
        client = self._get_client(provider)
        url = f"{base_url.rstrip('/')}/chat/completions"

        logger.debug("LLM request to %s: model=%s max_tokens=%d", provider, model, max_tokens)
        t0 = time.perf_counter()
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        data = response.json()

        choice = data["choices"][0] if data.get("choices") else {}
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            logger.warning(
                "LLM response truncated by max_tokens=%d (provider=%s, model=%s)",
                max_tokens,
                provider,
                model,
            )
        message_obj = choice.get("message") or {}
        content = message_obj.get("content") or ""
        reasoning_content = message_obj.get("reasoning_content") or ""
        usage = data.get("usage") or {}
        total_tokens = usage.get("total_tokens", 0)

        result = LLMResponse(
            content=content,
            usage=usage,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
            finish_reason=str(finish_reason or ""),
            reasoning_content=str(reasoning_content or ""),
        )

        # 记账
        self._tick_tokens += total_tokens
        usd = self.estimate_cost(result)
        result.cost_usd = usd
        self._tick_usd += usd
        if self._cost_sink is not None:
            await self._cost_sink(total_tokens, usd)
            self._cost_recorded_by_sink = True

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
        if "flash" in (response.model or "").lower():
            return prompt_tokens / 1_000_000 * 0.30 + completion_tokens / 1_000_000 * 1.20
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
