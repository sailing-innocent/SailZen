# -*- coding: utf-8 -*-
# @file openai_compat_provider.py
# @brief OpenAI Compatible Provider with Image Generation Support
# @author sailing-innocent
# @date 2025-07-20
# @version 1.0
# ---------------------------------
#
# 兼容 OpenAI API 的 Provider，支持文本补全和图像生成/编辑。
# 通过 _StainlessStrippingClient 移除 x-stainless-* telemetry headers，
# 可兼容 dogapi.cc 等代理服务。

import base64
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import httpx
import openai
import requests

from .base import (
    BaseProvider,
    ProviderConfig,
    ProviderResponse,
    ProviderError,
    ImageGenerationConfig,
    ImageResponse,
)

logger = logging.getLogger(__name__)


class _StainlessStrippingClient(httpx.Client):
    """Strip `x-stainless-*` telemetry headers; some proxies (e.g. dogapi.cc) reject them."""

    def send(self, request, **kwargs):
        for header in list(request.headers.keys()):
            if header.lower().startswith("x-stainless"):
                del request.headers[header]
        return super().send(request, **kwargs)


class OpenAICompatProvider(BaseProvider):
    """OpenAI 兼容 Provider，支持文本和图像生成"""

    @property
    def provider_name(self) -> str:
        return "openai_compat"

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        print("Initializing OpenAI Compatible Client with base URL:", self.config.api_base)
        self._client = openai.OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.api_base,
            http_client=_StainlessStrippingClient(
                timeout=httpx.Timeout(600.0, connect=30.0)
            ),
        )

    async def _do_complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """调用 OpenAI 兼容 API 进行文本补全"""
        import asyncio

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        call_kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        if "top_p" in kwargs:
            call_kwargs["top_p"] = kwargs["top_p"]
        if "response_format" in kwargs:
            call_kwargs["response_format"] = kwargs["response_format"]

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(**call_kwargs),
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

    # ------------------------------------------------------------------
    # Image Generation
    # ------------------------------------------------------------------

    def generate_image(
        self,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
        reference_media: Optional[Union[str, List[str]]] = None,
    ) -> ImageResponse:
        """生成图像"""
        config = config or ImageGenerationConfig()

        if reference_media is None and config.reference_media:
            reference_media = config.reference_media

        if reference_media:
            paths = (
                [reference_media]
                if isinstance(reference_media, str)
                else list(reference_media)
            )
            return self._call_edits(prompt=prompt, image_paths=paths, config=config)

        return self._call_generations(prompt=prompt, config=config)

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        """编辑图像"""
        config = config or ImageGenerationConfig()
        return self._call_edits(prompt=prompt, image_paths=[image_path], config=config)

    def _size_string(self, config: ImageGenerationConfig) -> str:
        return f"{config.width}x{config.height}"

    def _call_generations(
        self, prompt: str, config: ImageGenerationConfig
    ) -> ImageResponse:
        import time
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "n": config.num_images,
            "size": self._size_string(config),
        }
        url = f"{self.config.api_base.rstrip('/')}/images/generations"
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                try:
                    body = resp.json()
                except Exception:
                    raise ProviderError(f"Non-JSON response from image API: {resp.text[:500]}")
                print(f"[ImageGen] Response body preview: {str(body)[:300]}")
                return self._extract_image(body)
            except Exception as exc:
                last_err = exc
                print(f"[ImageGen] Attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_err

    def _call_edits(
        self,
        prompt: str,
        image_paths: List[str],
        config: ImageGenerationConfig,
    ) -> ImageResponse:
        import time
        files: List[Any] = []
        for path in image_paths:
            p = Path(path)
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            files.append(("image[]", (p.name, p.read_bytes(), mime)))

        data = {
            "model": self.config.model,
            "prompt": prompt,
            "n": str(config.num_images),
            "size": self._size_string(config),
        }
        url = f"{self.config.api_base.rstrip('/')}/images/edits"
        last_err = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                    files=files,
                    data=data,
                    timeout=120,
                )
                resp.raise_for_status()
                body = resp.json()
                return self._extract_image(body)
            except Exception as exc:
                last_err = exc
                print(f"[ImageGen] Edit attempt {attempt + 1}/3 failed: {exc}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise last_err

    def _extract_image(self, body: Dict[str, Any]) -> ImageResponse:
        data = body.get("data") or []
        if not data:
            raise ProviderError(f"No image data in response: {body}")
        first = data[0]

        b64 = first.get("b64_json")
        if b64:
            image_bytes = base64.b64decode(b64)
            mime = "image/png"
        else:
            image_url = first.get("url")
            if not image_url:
                raise ProviderError(
                    f"No url or b64_json in response item: {first}"
                )
            r = requests.get(image_url, timeout=120)
            r.raise_for_status()
            image_bytes = r.content
            mime = (
                r.headers.get("Content-Type", "image/png")
                .split(";")[0]
                .strip()
            )

        usage = body.get("usage") or {}
        return ImageResponse(
            image_bytes=image_bytes,
            mime_type=mime,
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            model=self.config.model,
            cost_usd=0.0,
        )
