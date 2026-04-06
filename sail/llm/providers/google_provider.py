# -*- coding: utf-8 -*-
# @file google_provider.py
# @brief Google Gemini Provider Implementation
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


class GoogleProvider(BaseProvider):
    """Google Gemini Provider 实现"""

    _use_legacy: bool = False

    @property
    def provider_name(self) -> str:
        return "google"

    def _init_client(self):
        """初始化 Google 客户端"""
        try:
            # 尝试新版 API (google-genai)
            from google import genai

            self._client = genai.Client(api_key=self.config.api_key)
            self._use_legacy = False
        except ImportError:
            # 回退到旧版 API
            try:
                import google.generativeai as genai_old

                genai_old.configure(api_key=self.config.api_key)
                self._client = genai_old
                self._use_legacy = True
                logger.warning(
                    "Using deprecated google.generativeai. Consider upgrading to google-genai."
                )
            except ImportError:
                raise ProviderError(
                    "Google genai package not installed. Run: pip install google-genai"
                )

    async def _do_complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """调用 Google Gemini API"""
        if self._client is None:
            self._init_client()

        if self._use_legacy:
            return await self._do_complete_legacy(prompt, system, **kwargs)

        try:
            from google.genai import types

            # 构建配置
            config = types.GenerateContentConfig(
                temperature=kwargs.get("temperature", self.config.temperature),
                max_output_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                system_instruction=system if system else None,
            )

            loop = asyncio.get_event_loop()

            def call_gemini():
                return self._client.models.generate_content(
                    model=self.config.model,
                    contents=prompt,
                    config=config,
                )

            response = await loop.run_in_executor(None, call_gemini)

            # 提取文本内容
            text_content = ""
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    if hasattr(candidate.content, "parts") and candidate.content.parts:
                        text_content = candidate.content.parts[0].text
                elif hasattr(response, "text"):
                    text_content = response.text

            # 提取 usage
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(
                    response.usage_metadata, "prompt_token_count", 0
                )
                completion_tokens = getattr(
                    response.usage_metadata, "candidates_token_count", 0
                )
                total_tokens = getattr(response.usage_metadata, "total_token_count", 0)

            # 提取 finish_reason
            finish_reason = None
            if response.candidates and len(response.candidates) > 0:
                fr = getattr(response.candidates[0], "finish_reason", None)
                if fr:
                    finish_reason = fr.name if hasattr(fr, "name") else str(fr)

            return ProviderResponse(
                content=text_content,
                model=self.config.model,
                provider=self.provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                finish_reason=finish_reason,
                raw_response={
                    "candidates_count": len(response.candidates)
                    if response.candidates
                    else 0,
                },
            )

        except Exception as e:
            error_str = str(e).lower()

            if "rate limit" in error_str or "quota" in error_str:
                raise ProviderRateLimitError(str(e))
            elif "api key" in error_str or "permission" in error_str:
                raise ProviderAuthError(str(e))

            raise ProviderError(f"Google API error: {e}", retryable=True)

    async def _do_complete_legacy(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """使用旧版 API 调用"""
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        loop = asyncio.get_event_loop()

        def call_gemini():
            model = self._client.GenerativeModel(
                model_name=self.config.model,
                generation_config=generation_config,
                system_instruction=system if system else None,
            )
            return model.generate_content(prompt)

        response = await loop.run_in_executor(None, call_gemini)

        # 提取 usage
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(
                    response.usage_metadata, "prompt_token_count", 0
                ),
                "completion_tokens": getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                "total_tokens": getattr(
                    response.usage_metadata, "total_token_count", 0
                ),
            }

        finish_reason = None
        if response.candidates and len(response.candidates) > 0:
            finish_reason = (
                response.candidates[0].finish_reason.name
                if response.candidates[0].finish_reason
                else None
            )

        return ProviderResponse(
            content=response.text,
            model=self.config.model,
            provider=self.provider_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            finish_reason=finish_reason,
        )
