# -*- coding: utf-8 -*-
# @file anthropic_provider.py
# @brief Anthropic Provider Implementation
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------

import asyncio
import logging
from typing import Optional

from .base import (
    BaseProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderError,
    ProviderRateLimitError,
    ProviderAuthError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic (Claude) Provider 实现"""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _init_client(self):
        """初始化 Anthropic 客户端"""
        try:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise ProviderError(
                "Anthropic package not installed. Run: pip install anthropic"
            )

    async def _do_complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """调用 Anthropic API"""
        if self._client is None:
            self._init_client()

        call_kwargs = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }

        # 可选参数
        if system:
            call_kwargs["system"] = system
        if "temperature" in kwargs or self.config.temperature != 0.3:
            call_kwargs["temperature"] = kwargs.get(
                "temperature", self.config.temperature
            )
        if "top_p" in kwargs:
            call_kwargs["top_p"] = kwargs["top_p"]

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self._client.messages.create(**call_kwargs)
            )

            content = ""
            if response.content and len(response.content) > 0:
                content = response.content[0].text

            usage = response.usage

            return ProviderResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                prompt_tokens=usage.input_tokens if usage else 0,
                completion_tokens=usage.output_tokens if usage else 0,
                total_tokens=(usage.input_tokens + usage.output_tokens) if usage else 0,
                finish_reason=response.stop_reason,
                raw_response={
                    "id": response.id,
                    "type": response.type,
                    "role": response.role,
                }
                if hasattr(response, "id")
                else None,
            )

        except Exception as e:
            error_str = str(e).lower()

            if "rate limit" in error_str:
                raise ProviderRateLimitError(str(e))
            elif "authentication" in error_str or "api key" in error_str:
                raise ProviderAuthError(str(e))

            raise ProviderError(f"Anthropic API error: {e}", retryable=True)

    async def complete_stream(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ):
        """流式输出"""
        if self._client is None:
            self._init_client()

        call_kwargs = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }

        if system:
            call_kwargs["system"] = system

        try:
            loop = asyncio.get_event_loop()

            def stream_generator():
                return self._client.messages.create(**call_kwargs)

            stream = await loop.run_in_executor(None, stream_generator)

            for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield event.delta.text

        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            raise ProviderError(f"Anthropic stream error: {e}", retryable=True)
