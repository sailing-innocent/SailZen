import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import httpx
import openai
import requests
from .base import (
    BaseLLMProvider,
    BaseImageProvider,
    LLMResponse,
    ImageResponse,
    GenerationConfig,
    ImageGenerationConfig,
)


class _StainlessStrippingClient(httpx.Client):
    """Strip `x-stainless-*` telemetry headers; some proxies (e.g. dogapi.cc) reject requests carrying them."""

    def send(self, request, **kwargs):
        for header in list(request.headers.keys()):
            if header.lower().startswith("x-stainless"):
                del request.headers[header]
        return super().send(request, **kwargs)


def _build_openai_client(api_key: str, base_url: str) -> openai.OpenAI:
    return openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
        http_client=_StainlessStrippingClient(timeout=httpx.Timeout(600.0, connect=30.0)),
    )


class OpenAICompatibleProvider(BaseLLMProvider, BaseImageProvider):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = _build_openai_client(api_key, base_url)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        config = config or GenerationConfig()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
        )

        text = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
            finish_reason=response.choices[0].finish_reason,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()
        config.temperature = 0.1

        json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        response = self.generate_text(json_prompt, system_prompt, config)

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        media_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        config = config or GenerationConfig()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def analyze_image(
        self, image_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        config = config or GenerationConfig()

        import base64

        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        text = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            },
            model=self.model,
        )

    def analyze_video(
        self, video_path: str, prompt: str, config: Optional[GenerationConfig] = None
    ) -> LLMResponse:
        raise NotImplementedError("Video analysis not supported by OpenAI provider yet")

    def generate_image(
        self,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
        reference_media: Optional[Union[str, List[str]]] = None,
    ) -> ImageResponse:
        config = config or ImageGenerationConfig()

        if reference_media is None and config.reference_media:
            reference_media = config.reference_media

        if reference_media:
            paths = [reference_media] if isinstance(reference_media, str) else list(reference_media)
            return self._call_edits(prompt=prompt, image_paths=paths, config=config)

        return self._call_generations(prompt=prompt, config=config)

    def edit_image(
        self,
        image_path: str,
        prompt: str,
        config: Optional[ImageGenerationConfig] = None,
    ) -> ImageResponse:
        config = config or ImageGenerationConfig()
        return self._call_edits(prompt=prompt, image_paths=[image_path], config=config)

    def _size_string(self, config: ImageGenerationConfig) -> str:
        return f"{config.width}x{config.height}"

    def _call_generations(
        self, prompt: str, config: ImageGenerationConfig
    ) -> ImageResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": config.num_images,
            "size": self._size_string(config),
        }
        url = f"{self.base_url.rstrip('/')}/images/generations"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=600,
        )
        resp.raise_for_status()
        body = resp.json()
        return self._extract_image(body)

    def _call_edits(
        self,
        prompt: str,
        image_paths: List[str],
        config: ImageGenerationConfig,
    ) -> ImageResponse:
        files: List[Any] = []
        for path in image_paths:
            p = Path(path)
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            files.append(("image[]", (p.name, p.read_bytes(), mime)))

        data = {
            "model": self.model,
            "prompt": prompt,
            "n": str(config.num_images),
            "size": self._size_string(config),
        }
        url = f"{self.base_url.rstrip('/')}/images/edits"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            files=files,
            data=data,
            timeout=600,
        )
        resp.raise_for_status()
        body = resp.json()
        return self._extract_image(body)

    def _extract_image(self, body: Dict[str, Any]) -> ImageResponse:
        data = body.get("data") or []
        if not data:
            raise ValueError(f"No image data in response: {body}")
        first = data[0]

        b64 = first.get("b64_json")
        if b64:
            image_bytes = base64.b64decode(b64)
            mime = "image/png"
        else:
            image_url = first.get("url")
            if not image_url:
                raise ValueError(f"No url or b64_json in response item: {first}")
            r = requests.get(image_url, timeout=120)
            r.raise_for_status()
            image_bytes = r.content
            mime = r.headers.get("Content-Type", "image/png").split(";")[0].strip()

        usage = body.get("usage") or {}
        return ImageResponse(
            image_bytes=image_bytes,
            mime_type=mime,
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            model=self.model,
            cost_usd=0.0,
        )