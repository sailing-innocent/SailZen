# -*- coding: utf-8 -*-
# @file gateway.py
# @brief Unified LLM Gateway
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------
#
# 统一 LLM 网关 - 支持多提供商、成本追踪、降级、熔断

import time
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .providers import (
    BaseProvider,
    ProviderConfig,
    ProviderError,
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    MoonshotProvider,
    DeepseekProvider,
)
from .pricing import PricingRegistry, calculate_cost

logger = logging.getLogger(__name__)


@dataclass
class LLMExecutionConfig:
    """LLM 执行配置"""

    provider: str  # 'google' | 'openai' | 'moonshot' | 'anthropic'
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 60
    retries: int = 3
    system_prompt: Optional[str] = None

    # 扩展配置
    enable_caching: bool = True
    enable_streaming: bool = False
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenBudget:
    """Token 预算控制"""

    max_tokens: int = 100000  # 单次调用最大 token
    max_cost: float = 1.0  # 单次调用最大成本（美元）
    warning_threshold: float = 0.8  # 警告阈值（百分比）

    def check_budget(
        self, estimated_input: int, estimated_output: int, cost: float
    ) -> tuple[bool, str]:
        """检查预算是否足够，返回 (是否通过, 消息)"""
        total_tokens = estimated_input + estimated_output

        if total_tokens > self.max_tokens:
            return (
                False,
                f"Estimated tokens ({total_tokens}) exceeds budget ({self.max_tokens})",
            )

        if cost > self.max_cost:
            return (
                False,
                f"Estimated cost (${cost:.4f}) exceeds budget (${self.max_cost:.4f})",
            )

        if cost > self.max_cost * self.warning_threshold:
            return (
                True,
                f"Warning: Cost (${cost:.4f}) exceeds warning threshold ({self.warning_threshold * 100:.0f}%)",
            )

        return True, "OK"


@dataclass
class LLMExecutionResult:
    """LLM 执行结果"""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    provider: str
    model: str
    latency_ms: int
    cached: bool = False
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": round(self.cost, 6),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "cached": self.cached,
            "finish_reason": self.finish_reason,
        }


@dataclass
class GatewayStats:
    """网关统计信息"""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cached_requests: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0

    # 按提供商统计
    provider_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def record_request(self, result: LLMExecutionResult, success: bool = True):
        """记录请求统计"""
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        if result.cached:
            self.cached_requests += 1

        self.total_cost += result.cost
        self.total_tokens += result.total_tokens

        # 更新平均延迟
        self.avg_latency_ms = (
            self.avg_latency_ms * (self.total_requests - 1) + result.latency_ms
        ) / self.total_requests

        # 按提供商统计
        provider = result.provider
        if provider not in self.provider_stats:
            self.provider_stats[provider] = {
                "requests": 0,
                "cost": 0.0,
                "tokens": 0,
            }

        self.provider_stats[provider]["requests"] += 1
        self.provider_stats[provider]["cost"] += result.cost
        self.provider_stats[provider]["tokens"] += result.total_tokens


class LLMCache:
    """LLM 请求缓存"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, prompt: str, config: LLMExecutionConfig) -> str:
        """生成缓存键"""
        key_data = (
            f"{prompt}:{config.model}:{config.temperature}:{config.system_prompt}"
        )
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(
        self, prompt: str, config: LLMExecutionConfig
    ) -> Optional[LLMExecutionResult]:
        """获取缓存结果"""
        if not config.enable_caching:
            return None

        key = self._make_key(prompt, config)
        cached = self._cache.get(key)

        if cached:
            # 检查是否过期
            if time.time() - cached["timestamp"] < self.ttl_seconds:
                result = cached["result"]
                result.cached = True
                return result
            else:
                # 过期删除
                del self._cache[key]

        return None

    def set(self, prompt: str, config: LLMExecutionConfig, result: LLMExecutionResult):
        """设置缓存"""
        if not config.enable_caching:
            return

        # 清理过期缓存
        self._cleanup()

        # 如果缓存已满，删除最旧的
        if len(self._cache) >= self.max_size:
            oldest_key = min(
                self._cache.keys(), key=lambda k: self._cache[k]["timestamp"]
            )
            del self._cache[oldest_key]

        key = self._make_key(prompt, config)
        self._cache[key] = {
            "result": result,
            "timestamp": time.time(),
        }

    def _cleanup(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items() if now - v["timestamp"] > self.ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self):
        """清空缓存"""
        self._cache.clear()


class LLMGateway:
    """统一 LLM 网关"""

    def __init__(
        self,
        default_budget: Optional[TokenBudget] = None,
        enable_cache: bool = True,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
    ):
        self._providers: Dict[str, BaseProvider] = {}
        self._budget = default_budget or TokenBudget()
        self._stats = GatewayStats()
        self._cache = (
            LLMCache(max_size=cache_size, ttl_seconds=cache_ttl)
            if enable_cache
            else None
        )
        self._fallback_chains: Dict[str, List[str]] = {}

    def register_provider(
        self, provider_name: str, config: ProviderConfig, provider_class: type = None
    ):
        """
        注册 Provider

        Args:
            provider_name: Provider 名称
            config: Provider 配置
            provider_class: Provider 类（默认根据名称自动选择）
        """
        if provider_class is None:
            # 根据名称自动选择 Provider 类
            provider_map = {
                "openai": OpenAIProvider,
                "anthropic": AnthropicProvider,
                "google": GoogleProvider,
                "moonshot": MoonshotProvider,
                "deepseek": DeepseekProvider,
            }
            provider_class = provider_map.get(provider_name)

            if provider_class is None:
                raise ValueError(f"Unknown provider: {provider_name}")

        provider = provider_class(config)
        self._providers[provider_name] = provider

        # 设置降级链
        self._fallback_chains[provider_name] = PricingRegistry.get_fallback_chain(
            config.model
        )

        logger.info(f"Registered provider: {provider_name} with model {config.model}")

    async def execute(
        self,
        prompt: str,
        config: LLMExecutionConfig,
        budget: Optional[TokenBudget] = None,
    ) -> LLMExecutionResult:
        """
        执行 LLM 调用

        Args:
            prompt: 用户提示
            config: 执行配置
            budget: Token 预算（覆盖默认）

        Returns:
            LLMExecutionResult: 执行结果
        """
        budget = budget or self._budget

        # 检查缓存
        if self._cache:
            cached = self._cache.get(prompt, config)
            if cached:
                logger.debug(f"Cache hit for prompt (first 50 chars): {prompt[:50]}...")
                self._stats.record_request(cached, success=True)
                return cached

        # 获取 Provider
        provider = self._providers.get(config.provider)
        if not provider:
            raise ProviderError(f"Provider not registered: {config.provider}")

        # 估算成本
        pricing = PricingRegistry.get_pricing(config.model)
        estimated_input = pricing.estimate_input_cost(prompt)
        estimated_output_cost = (
            (config.max_tokens or 1000) / 1000 * pricing.output_price
        )

        # 检查预算
        budget_ok, budget_msg = budget.check_budget(
            int(estimated_input * 1000 / pricing.input_price)
            if pricing.input_price > 0
            else 0,
            config.max_tokens or 1000,
            estimated_input + estimated_output_cost,
        )

        if not budget_ok:
            raise ProviderError(
                f"Budget check failed: {budget_msg}", error_code="BUDGET_EXCEEDED"
            )

        if budget_msg != "OK":
            logger.warning(budget_msg)

        # 执行调用
        start_time = time.time()

        try:
            response = await provider.complete(
                prompt=prompt,
                system=config.system_prompt,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                **config.extra_params,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # 计算实际成本
            actual_cost = calculate_cost(
                config.model, response.prompt_tokens, response.completion_tokens
            )

            result = LLMExecutionResult(
                content=response.content,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                cost=actual_cost,
                provider=config.provider,
                model=response.model or config.model,
                latency_ms=latency_ms,
                cached=False,
                finish_reason=response.finish_reason,
            )

            # 缓存结果
            if self._cache:
                self._cache.set(prompt, config, result)

            # 记录统计
            self._stats.record_request(result, success=True)

            return result

        except Exception as e:
            # 记录失败
            failed_result = LLMExecutionResult(
                content="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost=0.0,
                provider=config.provider,
                model=config.model,
                latency_ms=int((time.time() - start_time) * 1000),
                cached=False,
            )
            self._stats.record_request(failed_result, success=False)
            raise

    async def execute_with_fallback(
        self,
        prompt: str,
        configs: List[LLMExecutionConfig],
        budget: Optional[TokenBudget] = None,
    ) -> LLMExecutionResult:
        """
        带降级的多提供商调用

        Args:
            prompt: 用户提示
            configs: Provider 配置列表（按优先级排序）
            budget: Token 预算

        Returns:
            LLMExecutionResult: 第一个成功的结果
        """
        last_error = None

        for i, config in enumerate(configs):
            try:
                result = await self.execute(prompt, config, budget)

                if i > 0:
                    logger.info(
                        f"Fallback succeeded with {config.provider} after {i} retries"
                    )

                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Provider {config.provider} failed: {e}")

                # 继续尝试下一个
                continue

        # 所有 Provider 都失败了
        raise ProviderError(
            f"All {len(configs)} providers failed. Last error: {last_error}",
            error_code="ALL_PROVIDERS_FAILED",
        )

    async def execute_auto_fallback(
        self,
        prompt: str,
        primary_config: LLMExecutionConfig,
        budget: Optional[TokenBudget] = None,
    ) -> LLMExecutionResult:
        """
        自动降级调用

        根据 PricingRegistry 的降级链自动选择备用 Provider
        """
        # 构建降级配置列表
        fallback_models = self._fallback_chains.get(
            primary_config.provider, [primary_config.model]
        )

        configs = []
        for model in fallback_models:
            # 查找该模型对应的 Provider
            for provider_name, provider in self._providers.items():
                # 简单匹配：检查模型名是否匹配
                if model in provider.config.model or provider.config.model in model:
                    config = LLMExecutionConfig(
                        provider=provider_name,
                        model=model,
                        temperature=primary_config.temperature,
                        max_tokens=primary_config.max_tokens,
                        system_prompt=primary_config.system_prompt,
                        enable_caching=primary_config.enable_caching,
                    )
                    configs.append(config)
                    break

        # 如果找不到降级选项，只用主配置
        if not configs:
            configs = [primary_config]

        return await self.execute_with_fallback(prompt, configs, budget)

    def get_provider_health(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Provider 的健康状态"""
        return {
            name: provider.get_health_status()
            for name, provider in self._providers.items()
        }

    def get_stats(self) -> GatewayStats:
        """获取网关统计"""
        return self._stats

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        if self._cache:
            stats = self._cache.get_stats()
            stats["enabled"] = True
            return stats
        return {"enabled": False, "size": 0, "max_size": 0, "ttl_seconds": 0}

    def clear_cache(self):
        """清空缓存"""
        if self._cache:
            self._cache.clear()


# 便捷函数
def create_default_gateway() -> LLMGateway:
    """创建默认网关（从环境变量读取配置）"""
    import os

    gateway = LLMGateway()

    # 注册 OpenAI
    if os.getenv("OPENAI_API_KEY"):
        gateway.register_provider(
            "openai",
            ProviderConfig(
                provider_name="openai",
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=os.getenv("OPENAI_API_KEY"),
                api_base=os.getenv("OPENAI_API_BASE"),
            ),
        )

    # 注册 Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        gateway.register_provider(
            "anthropic",
            ProviderConfig(
                provider_name="anthropic",
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
                api_key=os.getenv("ANTHROPIC_API_KEY"),
            ),
        )

    # 注册 Google
    if os.getenv("GOOGLE_API_KEY"):
        gateway.register_provider(
            "google",
            ProviderConfig(
                provider_name="google",
                model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
                api_key=os.getenv("GOOGLE_API_KEY"),
            ),
        )

    # 注册 Moonshot
    if os.getenv("MOONSHOT_API_KEY"):
        gateway.register_provider(
            "moonshot",
            ProviderConfig(
                provider_name="moonshot",
                model=os.getenv("MOONSHOT_MODEL", "kimi-k2-5"),
                api_key=os.getenv("MOONSHOT_API_KEY"),
                api_base=os.getenv("MOONSHOT_API_BASE"),
            ),
        )

    # 注册 DeepSeek
    if os.getenv("DEEPSEEK_API_KEY"):
        gateway.register_provider(
            "deepseek",
            ProviderConfig(
                provider_name="deepseek",
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                api_base=os.getenv("DEEPSEEK_API_BASE"),
            ),
        )

    return gateway
