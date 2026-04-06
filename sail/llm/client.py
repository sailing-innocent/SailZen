# -*- coding: utf-8 -*-
# @file client.py
# @brief LLM Client Wrapper - Unified interface for multiple LLM providers
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 支持多种 LLM 提供商的统一客户端封装
# 包括直接调用和"仅生成 Prompt"模式
#

import os
import json
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncIterator
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# Debug Logger Setup - 简化版，直接使用标准日志
# ============================================================================


def log_api_call(func_name: str, call_id: str, messages: List[Dict], **kwargs):
    """记录 API 调用详情 - 仅在 DEBUG 级别记录"""
    logger.debug(f"[LLM CALL] {call_id} - {func_name} - model={kwargs.get('model')}")


def log_api_response(
    call_id: str, duration: float, response: Any, error: Optional[str] = None
):
    """记录 API 响应详情 - 仅在 DEBUG 级别记录"""
    if error:
        logger.debug(f"[LLM RESPONSE] {call_id} - ERROR: {error}")
    else:
        usage = response.usage if response else None
        tokens = usage.total_tokens if usage else 0
        logger.debug(f"[LLM RESPONSE] {call_id} - {duration:.2f}s - {tokens} tokens")


class LLMProvider(Enum):
    """LLM 提供商"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"  # Google Gemini
    MOONSHOT = "moonshot"  # Moonshot (Kimi K2.5)
    DEEPSEEK = "deepseek"  # DeepSeek
    LOCAL = "local"  # 本地 Ollama 等
    EXTERNAL = "external"  # 仅生成 Prompt，不调用 API
    MOCK = "mock"  # 模拟模式，用于测试和演示


@dataclass
class LLMConfig:
    """LLM 配置"""

    provider: LLMProvider = LLMProvider.EXTERNAL
    model: str = "gpt-4"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120

    @classmethod
    def from_env(cls, provider: LLMProvider = LLMProvider.OPENAI) -> "LLMConfig":
        """从环境变量创建配置"""
        if provider == LLMProvider.OPENAI:
            return cls(
                provider=provider,
                model=os.getenv("OPENAI_MODEL", "gpt-4"),
                api_key=os.getenv("OPENAI_API_KEY"),
                api_base=os.getenv("OPENAI_API_BASE"),
            )
        elif provider == LLMProvider.ANTHROPIC:
            return cls(
                provider=provider,
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            )
        elif provider == LLMProvider.GOOGLE:
            return cls(
                provider=provider,
                model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
                api_key=os.getenv("GOOGLE_API_KEY"),
            )
        elif provider == LLMProvider.MOONSHOT:
            # 从环境变量读取超时，默认 300 秒（5分钟），长文本分析需要更多时间
            timeout = int(os.getenv("MOONSHOT_TIMEOUT", "300"))
            return cls(
                provider=provider,
                model=os.getenv("MOONSHOT_MODEL", "kimi-k2-5"),
                api_key=os.getenv("MOONSHOT_API_KEY"),
                api_base=os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1"),
                temperature=1.0,  # Kimi K2.5 要求 temperature 必须为 1
                max_tokens=16384,  # Kimi K2.5 支持 256K 上下文，设置较大的输出限制
                timeout=timeout,
            )
        elif provider == LLMProvider.DEEPSEEK:
            return cls(
                provider=provider,
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
                temperature=0.7,
                max_tokens=4096,  # DeepSeek API 限制 max_tokens <= 8192
                timeout=120,
            )
        else:
            return cls(provider=provider)

    def validate(self) -> bool:
        """验证配置是否有效"""
        if self.provider == LLMProvider.EXTERNAL:
            return True
        if self.provider in (
            LLMProvider.OPENAI,
            LLMProvider.ANTHROPIC,
            LLMProvider.GOOGLE,
        ):
            return self.api_key is not None
        return True


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    latency_ms: int = 0
    raw_response: Optional[Dict] = None

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class ExportedPrompt:
    """导出的 Prompt（用于外部 LLM 工具）"""

    task_id: int
    chunk_index: int
    total_chunks: int
    system_prompt: str
    user_prompt: str
    model_suggestion: str
    temperature: float
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI API 格式"""
        return {
            "model": self.model_suggestion,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self.user_prompt},
            ],
            "temperature": self.temperature,
        }

    def to_anthropic_format(self) -> Dict[str, Any]:
        """转换为 Anthropic API 格式"""
        return {
            "model": self.model_suggestion.replace("gpt-4", "claude-3-opus-20240229"),
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": self.user_prompt}],
            "temperature": self.temperature,
        }

    def to_google_format(self) -> Dict[str, Any]:
        """转换为 Google Gemini API 格式"""
        return {
            "model": "gemini-2.0-flash",
            "system_instruction": self.system_prompt,
            "contents": self.user_prompt,
            "generation_config": {
                "temperature": self.temperature,
            },
        }

    def to_plain_text(self) -> str:
        """转换为纯文本格式"""
        return f"""=== System Prompt ===
{self.system_prompt}

=== User Prompt ===
{self.user_prompt}
"""

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        return f"""# LLM Analysis Prompt

**Task ID:** {self.task_id}  
**Chunk:** {self.chunk_index + 1} / {self.total_chunks}  
**Suggested Model:** {self.model_suggestion}  
**Temperature:** {self.temperature}

---

## System Prompt

{self.system_prompt}

---

## User Prompt

{self.user_prompt}
"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "model_suggestion": self.model_suggestion,
            "temperature": self.temperature,
            "formats": {
                "openai": self.to_openai_format(),
                "anthropic": self.to_anthropic_format(),
                "google": self.to_google_format(),
                "plain": self.to_plain_text(),
            },
        }


class LLMClient:
    """统一的 LLM 调用客户端"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._use_legacy_google = False  # 是否使用旧版 Google API
        self._init_client()

    def _init_client(self):
        """初始化底层客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            try:
                from openai import OpenAI

                # OpenAI v1.x API: 使用 OpenAI 客户端类
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base,
                )
            except ImportError:
                logger.warning("OpenAI package not installed, using external mode")
                self.config.provider = LLMProvider.EXTERNAL

        elif self.config.provider == LLMProvider.ANTHROPIC:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.config.api_key)
            except ImportError:
                logger.warning("Anthropic package not installed, using external mode")
                self.config.provider = LLMProvider.EXTERNAL

        elif self.config.provider == LLMProvider.MOONSHOT:
            try:
                from openai import OpenAI

                # Moonshot 使用 OpenAI 兼容 API
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base or "https://api.moonshot.cn/v1",
                )
            except ImportError:
                logger.warning("OpenAI package not installed, using external mode")
                self.config.provider = LLMProvider.EXTERNAL

        elif self.config.provider == LLMProvider.DEEPSEEK:
            try:
                from openai import OpenAI

                # DeepSeek 使用 OpenAI 兼容 API
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.api_base or "https://api.deepseek.com",
                )
            except ImportError:
                logger.warning("OpenAI package not installed, using external mode")
                self.config.provider = LLMProvider.EXTERNAL

        elif self.config.provider == LLMProvider.GOOGLE:
            try:
                # 使用新的 google.genai 包 (google-genai)
                from google import genai

                self._client = genai.Client(api_key=self.config.api_key)
            except ImportError:
                # 回退到旧包（已弃用）
                try:
                    import google.generativeai as genai_old

                    genai_old.configure(api_key=self.config.api_key)
                    self._client = genai_old
                    self._use_legacy_google = True
                    logger.warning(
                        "Using deprecated google.generativeai package. Please upgrade to google-genai."
                    )
                except ImportError:
                    logger.warning(
                        "Google genai package not installed, using external mode"
                    )
                    self.config.provider = LLMProvider.EXTERNAL

    async def complete(self, prompt: str, system: Optional[str] = None) -> LLMResponse:
        """执行文本补全"""
        start_time = datetime.utcnow()
        logger.debug(
            f"LLM call: provider={self.config.provider.value}, model={self.config.model}"
        )

        if self.config.provider == LLMProvider.EXTERNAL:
            raise ValueError(
                "External mode does not support direct completion. Use generate_prompt_only() instead."
            )

        try:
            if self.config.provider == LLMProvider.MOCK:
                response = await self._complete_mock(prompt, system)
            elif self.config.provider == LLMProvider.OPENAI:
                response = await self._complete_openai(prompt, system)
            elif self.config.provider == LLMProvider.ANTHROPIC:
                response = await self._complete_anthropic(prompt, system)
            elif self.config.provider == LLMProvider.MOONSHOT:
                response = await self._complete_moonshot(prompt, system)
            elif self.config.provider == LLMProvider.GOOGLE:
                response = await self._complete_google(prompt, system)
            elif self.config.provider == LLMProvider.DEEPSEEK:
                response = await self._complete_deepseek(prompt, system)
            elif self.config.provider == LLMProvider.LOCAL:
                response = await self._complete_local(prompt, system)
            else:
                raise ValueError(f"Unsupported provider: {self.config.provider}")

            latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            response.latency_ms = latency

            logger.debug(f"LLM completed: {latency}ms, {response.total_tokens} tokens")
            return response

        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise

    async def _complete_openai(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """OpenAI API 调用 (v1.x API)"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # 使用同步调用并在线程池中执行 (OpenAI v1.x API)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            ),
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            raw_response=response.model_dump()
            if hasattr(response, "model_dump")
            else None,
        )

    async def _complete_moonshot(
        self, prompt: str, system: Optional[str]
    ) -> LLMResponse:
        """Moonshot (Kimi) API 调用 - 使用 OpenAI 兼容接口"""
        call_id = f"ms_{datetime.utcnow().strftime('%H%M%S')}_{id(prompt) % 10000}"

        logger.debug(f"[LLM] {call_id} Moonshot call: model={self.config.model}")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log_api_call("_complete_moonshot", call_id, messages, model=self.config.model)

        loop = asyncio.get_event_loop()

        def call_moonshot():
            start = datetime.utcnow()
            try:
                result = self._client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.timeout,
                    response_format={"type": "json_object"},
                )
                duration = (datetime.utcnow() - start).total_seconds()
                log_api_response(call_id, duration, result)
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start).total_seconds()
                logger.error(f"[LLM] {call_id} API call failed: {e}")
                log_api_response(call_id, duration, None, error=str(e))
                raise

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, call_moonshot),
                timeout=self.config.timeout + 5,
            )
        except asyncio.TimeoutError:
            logger.error(f"[LLM] {call_id} Timeout after {self.config.timeout + 5}s")
            raise asyncio.TimeoutError(
                f"Moonshot API call timed out after {self.config.timeout + 5}s"
            )

        content = response.choices[0].message.content if response.choices else ""
        usage = response.usage

        logger.debug(
            f"[LLM] {call_id} Response: {len(content)} chars, {usage.total_tokens if usage else 0} tokens"
        )

        return LLMResponse(
            content=content,
            model=response.model,
            provider="moonshot",
            usage={
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            finish_reason=response.choices[0].finish_reason
            if response.choices
            else None,
            raw_response=response.model_dump()
            if hasattr(response, "model_dump")
            else None,
        )

    async def _complete_deepseek(
        self, prompt: str, system: Optional[str]
    ) -> LLMResponse:
        """DeepSeek API 调用 - 使用 OpenAI 兼容接口"""
        call_id = f"ds_{datetime.utcnow().strftime('%H%M%S')}_{id(prompt) % 10000}"

        logger.debug(f"[LLM] {call_id} DeepSeek call: model={self.config.model}")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        log_api_call("_complete_deepseek", call_id, messages, model=self.config.model)

        loop = asyncio.get_event_loop()

        def call_deepseek():
            start = datetime.utcnow()
            try:
                call_kwargs = {
                    "model": self.config.model,
                    "messages": messages,
                    "max_tokens": self.config.max_tokens,
                    "timeout": self.config.timeout,
                }
                if "reasoner" not in self.config.model.lower():
                    call_kwargs["temperature"] = self.config.temperature

                result = self._client.chat.completions.create(**call_kwargs)
                duration = (datetime.utcnow() - start).total_seconds()
                log_api_response(call_id, duration, result)
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start).total_seconds()
                logger.error(f"[LLM] {call_id} API call failed: {e}")
                log_api_response(call_id, duration, None, error=str(e))
                raise

        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(None, call_deepseek),
                timeout=self.config.timeout + 5,
            )
        except asyncio.TimeoutError:
            logger.error(f"[LLM] {call_id} Timeout after {self.config.timeout + 5}s")
            raise asyncio.TimeoutError(
                f"DeepSeek API call timed out after {self.config.timeout + 5}s"
            )

        content = response.choices[0].message.content if response.choices else ""
        usage = response.usage

        logger.debug(
            f"[LLM] {call_id} Response: {len(content)} chars, {usage.total_tokens if usage else 0} tokens"
        )

        return LLMResponse(
            content=content,
            model=response.model,
            provider="deepseek",
            usage={
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            finish_reason=response.choices[0].finish_reason
            if response.choices
            else None,
            raw_response=response.model_dump()
            if hasattr(response, "model_dump")
            else None,
        )

    async def _complete_anthropic(
        self, prompt: str, system: Optional[str]
    ) -> LLMResponse:
        """Anthropic API 调用"""
        loop = asyncio.get_event_loop()

        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await loop.run_in_executor(
            None, lambda: self._client.messages.create(**kwargs)
        )

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            provider="anthropic",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens
                + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    async def _complete_google(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """Google Gemini API 调用"""
        loop = asyncio.get_event_loop()

        if self._use_legacy_google:
            # 使用旧版 API (google.generativeai) - 已弃用
            return await self._complete_google_legacy(prompt, system)

        # 使用新版 API (google.genai)
        from google.genai import types

        # 构建配置
        config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            system_instruction=system if system else None,
        )

        def call_gemini():
            return self._client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=config,
            )

        response = await loop.run_in_executor(None, call_gemini)

        # 提取 usage 信息
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

        # 获取文本内容
        text_content = ""
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content:
                if hasattr(candidate.content, "parts") and candidate.content.parts:
                    text_content = candidate.content.parts[0].text
            elif hasattr(response, "text"):
                text_content = response.text

        finish_reason = None
        if response.candidates and len(response.candidates) > 0:
            fr = getattr(response.candidates[0], "finish_reason", None)
            if fr:
                finish_reason = fr.name if hasattr(fr, "name") else str(fr)

        return LLMResponse(
            content=text_content,
            model=self.config.model,
            provider="google",
            usage=usage,
            finish_reason=finish_reason,
        )

    async def _complete_google_legacy(
        self, prompt: str, system: Optional[str]
    ) -> LLMResponse:
        """Google Gemini API 调用 (旧版 - 已弃用)"""
        loop = asyncio.get_event_loop()

        # 构建完整 prompt（Gemini 使用 system_instruction 作为系统提示）
        generation_config = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
        }

        def call_gemini():
            model = self._client.GenerativeModel(
                model_name=self.config.model,
                generation_config=generation_config,
                system_instruction=system if system else None,
            )
            return model.generate_content(prompt)

        response = await loop.run_in_executor(None, call_gemini)

        # 提取 usage 信息（如果可用）
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

        return LLMResponse(
            content=response.text,
            model=self.config.model,
            provider="google",
            usage=usage,
            finish_reason=response.candidates[0].finish_reason.name
            if response.candidates
            else None,
        )

    async def _complete_local(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """本地 LLM 调用（如 Ollama）"""
        import aiohttp

        base_url = self.config.api_base or "http://localhost:11434"

        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/api/generate",
                json={
                    "model": self.config.model,
                    "prompt": full_prompt,
                    "stream": False,
                },
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as resp:
                data = await resp.json()

        return LLMResponse(
            content=data.get("response", ""),
            model=self.config.model,
            provider="local",
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0)
                + data.get("eval_count", 0),
            },
        )

    async def _complete_mock(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """模拟 LLM 调用（用于测试和演示）"""
        import random

        # 模拟处理延迟（1-3秒）
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)

        # 根据任务类型生成模拟结果
        mock_response = self._generate_mock_response(prompt, system)

        # 估算 token 数量
        prompt_tokens = self.estimate_tokens(prompt + (system or ""))
        completion_tokens = self.estimate_tokens(mock_response)

        return LLMResponse(
            content=mock_response,
            model="mock-model",
            provider="mock",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            finish_reason="stop",
        )

    def _generate_mock_response(self, prompt: str, system: Optional[str]) -> str:
        """根据 prompt 内容生成模拟响应"""
        import random

        # 检测任务类型
        prompt_lower = prompt.lower()

        if "大纲" in prompt or "outline" in prompt_lower or "plot" in prompt_lower:
            return self._generate_mock_outline()
        elif "人物" in prompt or "character" in prompt_lower:
            return self._generate_mock_characters()
        elif "设定" in prompt or "setting" in prompt_lower:
            return self._generate_mock_settings()
        else:
            # 默认返回大纲
            return self._generate_mock_outline()

    def _generate_mock_outline(self) -> str:
        """生成模拟大纲分析结果"""
        import random

        plot_types = ["conflict", "revelation", "climax", "resolution", "setup"]
        importance_levels = ["critical", "major", "normal", "minor"]

        # 生成 2-5 个情节点
        num_points = random.randint(2, 5)
        plot_points = []

        for i in range(num_points):
            point = {
                "title": f"模拟情节点 {i + 1}",
                "type": random.choice(plot_types),
                "importance": random.choice(importance_levels),
                "summary": f"这是一个模拟生成的情节描述。主角在此处遇到了重要的转折，故事情节得到了推进。（模拟内容 #{random.randint(1000, 9999)}）",
                "chapter_number": random.randint(1, 100),
                "evidence": "「这是模拟的原文引用内容，用于验证分析结果的准确性。」",
                "characters": [
                    f"角色{random.randint(1, 5)}" for _ in range(random.randint(1, 3))
                ],
            }
            plot_points.append(point)

        result = {
            "plot_points": plot_points,
            "overall_summary": f"本段章节主要讲述了故事的发展过程，涉及 {num_points} 个关键情节点。（模拟分析结果，生成时间: {datetime.utcnow().isoformat()}）",
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    def _generate_mock_characters(self) -> str:
        """生成模拟人物识别结果"""
        import random

        role_types = [
            "protagonist",
            "antagonist",
            "deuteragonist",
            "supporting",
            "minor",
        ]

        # 生成 2-4 个人物
        num_chars = random.randint(2, 4)
        characters = []

        names = ["张三", "李四", "王五", "赵六", "孙七", "周八", "吴九", "郑十"]

        for i in range(num_chars):
            name = random.choice(names)
            names.remove(name)  # 避免重复

            char = {
                "canonical_name": name,
                "aliases": [f"{name}大人", f"小{name[1]}"]
                if random.random() > 0.5
                else [],
                "role_type": random.choice(role_types),
                "description": f"这是{name}的角色描述。是一个重要的角色，在故事中扮演着关键作用。（模拟数据）",
                "first_mention": f"第{random.randint(1, 10)}章首次出现",
                "actions": [f"动作描述{j + 1}" for j in range(random.randint(1, 3))],
                "mention_count": random.randint(5, 50),
            }
            characters.append(char)

        result = {"characters": characters}
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _generate_mock_settings(self) -> str:
        """生成模拟设定提取结果"""
        import random

        setting_types = ["item", "location", "organization", "concept"]
        importance_levels = ["critical", "major", "normal", "minor"]

        # 生成 2-4 个设定
        num_settings = random.randint(2, 4)
        settings = []

        for i in range(num_settings):
            setting_type = random.choice(setting_types)

            if setting_type == "item":
                names = ["天龙剑", "乾坤袋", "九转灵丹", "紫金葫芦"]
                categories = ["武器", "法宝", "丹药", "器物"]
            elif setting_type == "location":
                names = ["青云山", "玄天宗", "无尽森林", "龙渊深海"]
                categories = ["山脉", "门派", "秘境", "海域"]
            elif setting_type == "organization":
                names = ["天机阁", "暗影联盟", "圣光教会", "商会"]
                categories = ["势力", "暗组织", "宗教", "商业"]
            else:
                names = ["灵气", "境界", "功法", "天道"]
                categories = ["能量", "修炼", "技能", "法则"]

            setting = {
                "name": random.choice(names),
                "type": setting_type,
                "category": random.choice(categories),
                "description": f"这是一个模拟的{setting_type}设定描述，包含了详细的背景信息。",
                "attributes": {
                    "等级": f"{random.choice(['普通', '珍稀', '史诗', '传说'])}"
                },
                "related_characters": [f"角色{random.randint(1, 3)}"],
                "importance": random.choice(importance_levels),
                "evidence": "「原文中提到了这个设定的相关描述。」",
            }
            settings.append(setting)

        result = {"settings": settings}
        return json.dumps(result, ensure_ascii=False, indent=2)

    async def complete_json(
        self, prompt: str, schema: Dict[str, Any], system: Optional[str] = None
    ) -> Dict[str, Any]:
        """JSON 模式输出"""
        json_instruction = f"""
请以 JSON 格式输出结果，符合以下 Schema：
```json
{json.dumps(schema, ensure_ascii=False, indent=2)}
```

只输出 JSON，不要包含其他文本。
"""
        full_prompt = f"{prompt}\n\n{json_instruction}"

        response = await self.complete(full_prompt, system)

        # 尝试解析 JSON
        content = response.content.strip()

        # 移除可能的 markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response content: {content}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

    def generate_prompt_only(
        self,
        prompt: str,
        system: Optional[str] = None,
        task_id: int = 0,
        chunk_index: int = 0,
        total_chunks: int = 1,
    ) -> ExportedPrompt:
        """仅生成 Prompt（不调用 LLM），返回可导出的格式"""
        return ExportedPrompt(
            task_id=task_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            system_prompt=system or "",
            user_prompt=prompt,
            model_suggestion=self.config.model,
            temperature=self.config.temperature,
        )

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量（粗略估算）"""
        # 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars

        return int(chinese_chars / 1.5 + other_chars / 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（美元）"""
        # 基于各提供商的定价估算
        model_lower = self.config.model.lower()

        if "gpt-4" in model_lower:
            input_cost = input_tokens * 0.00003
            output_cost = output_tokens * 0.00006
        elif "gpt-3.5" in model_lower:
            input_cost = input_tokens * 0.0000015
            output_cost = output_tokens * 0.000002
        elif "claude" in model_lower:
            input_cost = input_tokens * 0.000015
            output_cost = output_tokens * 0.000075
        elif "gemini" in model_lower:
            # Gemini 2.0 Flash 定价 (相对便宜)
            input_cost = input_tokens * 0.0000001
            output_cost = output_tokens * 0.0000004
        elif "kimi" in model_lower or "moonshot" in model_lower:
            # Moonshot Kimi K2.5 定价 (参考价格，实际以官网为准)
            # 输入: ¥0.006 / 1K tokens, 输出: ¥0.006 / 1K tokens
            # 换算为美元 (约 7.2 汇率)
            input_cost = input_tokens * 0.00000083  # ¥0.006 / 7.2 / 1000
            output_cost = output_tokens * 0.00000083
        else:
            # 默认估算
            input_cost = input_tokens * 0.00001
            output_cost = output_tokens * 0.00003

        return input_cost + output_cost


# 便捷函数
def create_llm_client(
    provider: str = "external",
    model: str = "gpt-4",
    api_key: Optional[str] = None,
    **kwargs,
) -> LLMClient:
    """创建 LLM 客户端的便捷函数"""
    provider_enum = LLMProvider(provider) if provider else LLMProvider.EXTERNAL

    config = LLMConfig(
        provider=provider_enum,
        model=model,
        api_key=api_key or os.getenv(f"{provider.upper()}_API_KEY"),
        **kwargs,
    )

    return LLMClient(config)
