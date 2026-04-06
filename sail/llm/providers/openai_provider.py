# -*- coding: utf-8 -*-
# @file openai_provider.py
# @brief OpenAI Provider Implementation
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


class OpenAIProvider(BaseProvider):
    """OpenAI Provider 实现"""

    @property
    def provider_name(self) -> str:
        return "openai"

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
        except ImportError:
            raise ProviderError("OpenAI package not installed. Run: pip install openai")

    async def _do_complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """调用 OpenAI API"""
        if self._client is None:
            self._init_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 构建参数
        call_kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        # 可选参数
        if "top_p" in kwargs:
            call_kwargs["top_p"] = kwargs["top_p"]
        if "presence_penalty" in kwargs:
            call_kwargs["presence_penalty"] = kwargs["presence_penalty"]
        if "frequency_penalty" in kwargs:
            call_kwargs["frequency_penalty"] = kwargs["frequency_penalty"]

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: self._client.chat.completions.create(**call_kwargs)
            )

            choice = response.choices[0]
            usage = response.usage

            return ProviderResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider_name,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump()
                if hasattr(response, "model_dump")
                else None,
            )

        except Exception as e:
            error_str = str(e).lower()

            # 分类错误
            if "rate limit" in error_str or "rate_limit" in error_str:
                raise ProviderRateLimitError(str(e))
            elif "authentication" in error_str or "api key" in error_str:
                raise ProviderAuthError(str(e))
            elif "quota" in error_str:
                from .base import ProviderQuotaError

                raise ProviderQuotaError(str(e))

            raise ProviderError(f"OpenAI API error: {e}", retryable=True)

    async def complete_stream(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ):
        """流式输出"""
        if self._client is None:
            self._init_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            loop = asyncio.get_event_loop()

            def stream_generator():
                return self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=kwargs.get("temperature", self.config.temperature),
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                    stream=True,
                )

            stream = await loop.run_in_executor(None, stream_generator)

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            raise ProviderError(f"OpenAI stream error: {e}", retryable=True)
