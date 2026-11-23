# -*- coding: utf-8 -*-
# @file deepseek_vision.py
# @brief DeepSeek 官方视觉多模态 (deepseek-flash) 与专用 OCR (/v1/tools/ocr) 客户端
# @author sailing-innocent
# @date 2026-11-23
# @version 1.0
# ---------------------------------
"""DeepSeek Vision & OCR 客户端。

能力：
1. 原生多模态视觉理解：POST /chat/completions，模型 deepseek-flash（支持 Base64 图片 + JSON 输出）。
2. 专用文档 OCR 工具：POST /v1/tools/ocr（multipart/form-data，适用于长截图/高密度文字菜单与文档）。
3. 组合式健康日常识图：优先 deepseek-flash 一步识图 + 结构化；对超长截图或显式开启 OCR 辅助时，
   先调 /v1/tools/ocr 提取高精度文本再联合图像交由 deepseek-flash 生成结构化健康草稿。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_VISION_MODEL = "deepseek-flash"

VALID_IMAGE_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}


class DeepSeekVisionError(RuntimeError):
    """DeepSeek 视觉/OCR 调用失败。"""


@dataclass
class OcrPage:
    index: int
    text: str
    finish_reason: str = "stop"


@dataclass
class OcrResult:
    id: str = ""
    purpose: str = "text_recognition"
    page_count: int = 0
    pages: List[OcrPage] = field(default_factory=list)
    full_text: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class VisionResult:
    content: str
    parsed_json: Optional[Dict[str, Any]] = None
    model: str = DEFAULT_DEEPSEEK_VISION_MODEL
    usage: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    finish_reason: str = ""


def _resolve_api_key(api_key: Optional[str] = None) -> str:
    key = (api_key or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    if not key:
        raise DeepSeekVisionError(
            "DEEPSEEK_API_KEY 未配置，请先在环境变量或 .env 中设置有效的 DeepSeek API Key。"
        )
    return key


def _normalize_base_url(base_url: Optional[str] = None) -> str:
    raw = (
        base_url
        or os.environ.get("DEEPSEEK_API_BASE")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or DEFAULT_DEEPSEEK_BASE_URL
    ).strip()
    raw = raw.rstrip("/")
    # 兼容同时传入 https://api.deepseek.com 或 https://api.deepseek.com/v1
    if raw.endswith("/v1"):
        raw = raw[:-3]
    return raw


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """从模型响应中宽松提取 JSON 对象（容忍 ```json 围栏或前后说明文字）。"""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _clean_ocr_text(raw: str) -> str:
    """清理 DeepSeek OCR 输出中可能附带的排版坐标标记。"""
    if not raw:
        return ""
    cleaned = re.sub(r"<｜[^｜]+｜>", "", raw)
    return cleaned.strip()


async def deepseek_ocr_file(
    file_bytes: bytes,
    filename: str = "image.jpg",
    mime_type: str = "image/jpeg",
    purpose: str = "text_recognition",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 90.0,
) -> OcrResult:
    """调用 DeepSeek 专用 OCR 工具端点 POST /v1/tools/ocr。

    Args:
        file_bytes: 文件字节流（图片或 PDF/Word/PPT）。
        filename: 带后缀的文件名。
        mime_type: MIME 类型。
        purpose: "text_recognition" 或 "rich_layout_recognition"。
    """
    key = _resolve_api_key(api_key)
    root = _normalize_base_url(base_url)
    url = f"{root}/v1/tools/ocr"
    if purpose not in ("text_recognition", "rich_layout_recognition"):
        purpose = "text_recognition"

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                data={"purpose": purpose},
                files={"file": (filename, file_bytes, mime_type)},
            )
    except httpx.HTTPError as exc:
        raise DeepSeekVisionError(f"DeepSeek OCR 网络请求失败: {exc}") from exc

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if resp.status_code >= 400:
        raise DeepSeekVisionError(
            f"DeepSeek OCR 返回 HTTP {resp.status_code}: {resp.text[:300]}"
        )

    # 官方文档说明：服务端可能在响应体前输出保活换行空白
    body_text = resp.text.strip()
    try:
        data = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise DeepSeekVisionError(f"DeepSeek OCR 返回非合法 JSON: {body_text[:200]}") from exc

    pages: List[OcrPage] = []
    text_parts: List[str] = []
    for p in data.get("pages") or []:
        page_text = _clean_ocr_text(str(p.get("text") or ""))
        pages.append(
            OcrPage(
                index=int(p.get("index", len(pages))),
                text=page_text,
                finish_reason=str(p.get("finish_reason") or "stop"),
            )
        )
        if page_text:
            text_parts.append(page_text)

    return OcrResult(
        id=str(data.get("id") or ""),
        purpose=str(data.get("purpose") or purpose),
        page_count=int(data.get("page_count") or len(pages)),
        pages=pages,
        full_text="\n\n".join(text_parts).strip(),
        usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
        latency_ms=latency_ms,
    )


async def deepseek_vision_chat(
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    system: str = "",
    model: Optional[str] = None,
    detail: str = "high",
    expect_json: bool = True,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: float = 90.0,
) -> VisionResult:
    """调用 DeepSeek 原生多模态视觉模型（默认 deepseek-flash）。"""
    key = _resolve_api_key(api_key)
    root = _normalize_base_url(base_url)
    use_model = (
        model
        or os.environ.get("DEEPSEEK_VISION_MODEL")
        or DEFAULT_DEEPSEEK_VISION_MODEL
    ).strip()
    url = f"{root}/chat/completions"

    norm_mime = mime_type.lower().strip()
    if norm_mime == "image/jpg":
        norm_mime = "image/jpeg"
    if norm_mime not in VALID_IMAGE_MIMES:
        norm_mime = "image/jpeg"

    b64 = base64.b64encode(image_bytes).decode("ascii")
    image_block: Dict[str, Any] = {
        "type": "image_url",
        "image_url": {
            "url": f"data:{norm_mime};base64,{b64}",
            "detail": detail if detail in ("low", "high") else "high",
        },
    }

    messages: List[Dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                image_block,
            ],
        }
    )

    payload: Dict[str, Any] = {
        "model": use_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise DeepSeekVisionError(f"DeepSeek Vision 网络请求失败: {exc}") from exc

    latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    if resp.status_code >= 400:
        raise DeepSeekVisionError(
            f"DeepSeek Vision 返回 HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = str(message.get("content") or "").strip()
    finish_reason = str(choice.get("finish_reason") or "")
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}

    parsed = _extract_json_object(content) if expect_json else None
    return VisionResult(
        content=content,
        parsed_json=parsed,
        model=use_model,
        usage=usage,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
    )
