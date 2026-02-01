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


class LLMProvider(Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"           # 本地 Ollama 等
    EXTERNAL = "external"     # 仅生成 Prompt，不调用 API


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
    def from_env(cls, provider: LLMProvider = LLMProvider.OPENAI) -> 'LLMConfig':
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
        else:
            return cls(provider=provider)
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if self.provider == LLMProvider.EXTERNAL:
            return True
        if self.provider in (LLMProvider.OPENAI, LLMProvider.ANTHROPIC):
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
        return self.usage.get('prompt_tokens', 0)
    
    @property
    def completion_tokens(self) -> int:
        return self.usage.get('completion_tokens', 0)
    
    @property
    def total_tokens(self) -> int:
        return self.usage.get('total_tokens', 0)


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
                {"role": "user", "content": self.user_prompt}
            ],
            "temperature": self.temperature,
        }
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """转换为 Anthropic API 格式"""
        return {
            "model": self.model_suggestion.replace("gpt-4", "claude-3-opus-20240229"),
            "system": self.system_prompt,
            "messages": [
                {"role": "user", "content": self.user_prompt}
            ],
            "temperature": self.temperature,
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
                "plain": self.to_plain_text(),
            }
        }


class LLMClient:
    """统一的 LLM 调用客户端"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """初始化底层客户端"""
        if self.config.provider == LLMProvider.OPENAI:
            try:
                import openai
                if self.config.api_base:
                    openai.api_base = self.config.api_base
                openai.api_key = self.config.api_key
                self._client = openai
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
    
    async def complete(
        self, 
        prompt: str, 
        system: Optional[str] = None
    ) -> LLMResponse:
        """执行文本补全"""
        start_time = datetime.utcnow()
        
        if self.config.provider == LLMProvider.EXTERNAL:
            raise ValueError("External mode does not support direct completion. Use generate_prompt_only() instead.")
        
        try:
            if self.config.provider == LLMProvider.OPENAI:
                response = await self._complete_openai(prompt, system)
            elif self.config.provider == LLMProvider.ANTHROPIC:
                response = await self._complete_anthropic(prompt, system)
            elif self.config.provider == LLMProvider.LOCAL:
                response = await self._complete_local(prompt, system)
            else:
                raise ValueError(f"Unsupported provider: {self.config.provider}")
            
            latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            response.latency_ms = latency
            return response
            
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise
    
    async def _complete_openai(self, prompt: str, system: Optional[str]) -> LLMResponse:
        """OpenAI API 调用"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # 使用同步调用并在线程池中执行
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.ChatCompletion.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
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
            raw_response=response.to_dict() if hasattr(response, 'to_dict') else None,
        )
    
    async def _complete_anthropic(self, prompt: str, system: Optional[str]) -> LLMResponse:
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
            None,
            lambda: self._client.messages.create(**kwargs)
        )
        
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            provider="anthropic",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
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
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            ) as resp:
                data = await resp.json()
                
        return LLMResponse(
            content=data.get("response", ""),
            model=self.config.model,
            provider="local",
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            },
        )
    
    async def complete_json(
        self, 
        prompt: str, 
        schema: Dict[str, Any],
        system: Optional[str] = None
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
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        return int(chinese_chars / 1.5 + other_chars / 4)
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（美元）"""
        # 基于 GPT-4 的定价估算
        if "gpt-4" in self.config.model:
            input_cost = input_tokens * 0.00003
            output_cost = output_tokens * 0.00006
        elif "gpt-3.5" in self.config.model:
            input_cost = input_tokens * 0.0000015
            output_cost = output_tokens * 0.000002
        elif "claude" in self.config.model:
            input_cost = input_tokens * 0.000015
            output_cost = output_tokens * 0.000075
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
    **kwargs
) -> LLMClient:
    """创建 LLM 客户端的便捷函数"""
    provider_enum = LLMProvider(provider) if provider else LLMProvider.EXTERNAL
    
    config = LLMConfig(
        provider=provider_enum,
        model=model,
        api_key=api_key or os.getenv(f"{provider.upper()}_API_KEY"),
        **kwargs
    )
    
    return LLMClient(config)
