# -*- coding: utf-8 -*-
# @file base.py
# @brief Base Provider Interface
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------
#
# LLM Provider 抽象基类

import abc
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, AsyncIterator
from enum import Enum

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Provider 错误基类"""

    def __init__(self, message: str, error_code: str = None, retryable: bool = False):
        self.message = message
        self.error_code = error_code
        self.retryable = retryable
        # Include error code in string representation for easier debugging
        if error_code:
            full_message = f"[{error_code}] {message}"
        else:
            full_message = message
        super().__init__(full_message)


class ProviderRateLimitError(ProviderError):
    """速率限制错误"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, "RATE_LIMIT", retryable=True)
        self.retry_after = retry_after


class ProviderAuthError(ProviderError):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_ERROR", retryable=False)


class ProviderQuotaError(ProviderError):
    """额度不足错误"""

    def __init__(self, message: str = "Quota exceeded"):
        super().__init__(message, "QUOTA_EXCEEDED", retryable=False)


class ProviderTimeoutError(ProviderError):
    """超时错误"""

    def __init__(self, message: str = "Request timeout"):
        super().__init__(message, "TIMEOUT", retryable=True)


@dataclass
class ProviderConfig:
    """Provider 配置"""

    provider_name: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0

    def validate(self) -> bool:
        """验证配置"""
        return True


@dataclass
class ProviderResponse:
    """Provider 响应"""

    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: Optional[str] = None
    latency_ms: int = 0
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def cost_usd(self) -> float:
        """计算成本（需要外部调用 pricing 计算）"""
        from ..pricing import calculate_cost

        try:
            return calculate_cost(
                self.model, self.prompt_tokens, self.completion_tokens
            )
        except Exception:
            return 0.0


@dataclass
class CircuitBreakerState:
    """熔断器状态"""

    failures: int = 0
    last_failure_time: Optional[float] = None
    state: str = "closed"  # closed | open | half_open

    # 熔断器配置
    failure_threshold: int = 5
    recovery_timeout: float = 60.0

    def record_success(self):
        """记录成功"""
        self.failures = 0
        self.state = "closed"

    def record_failure(self) -> bool:
        """记录失败，返回是否应该熔断"""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "open"
            return True
        return False

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == "closed":
            return True

        if self.state == "open":
            # 检查是否已经过了恢复时间
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) > self.recovery_timeout
            ):
                self.state = "half_open"
                return True
            return False

        return True  # half_open 允许执行


class BaseProvider(abc.ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.circuit_breaker = CircuitBreakerState()
        self._client = None

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Provider 名称"""
        pass

    @abc.abstractmethod
    def _init_client(self):
        """初始化底层客户端"""
        pass

    @abc.abstractmethod
    async def _do_complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """实际执行调用（子类实现）"""
        pass

    async def complete(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> ProviderResponse:
        """执行文本补全（带熔断器和重试）"""
        # 检查熔断器
        if not self.circuit_breaker.can_execute():
            raise ProviderError(
                f"Circuit breaker is open for {self.provider_name}",
                "CIRCUIT_OPEN",
                retryable=False,
            )

        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                start_time = time.time()
                response = await self._do_complete(prompt, system, **kwargs)
                latency_ms = int((time.time() - start_time) * 1000)
                response.latency_ms = latency_ms
                response.provider = self.provider_name

                # 记录成功
                self.circuit_breaker.record_success()

                return response

            except ProviderRateLimitError:
                # 速率限制，等待后重试
                wait_time = (attempt + 1) * self.config.retry_delay
                logger.warning(
                    f"Rate limited by {self.provider_name}, waiting {wait_time}s..."
                )
                await self._sleep(wait_time)
                continue

            except ProviderTimeoutError:
                # 超时，重试
                logger.warning(f"Timeout from {self.provider_name}, retrying...")
                continue

            except (ProviderAuthError, ProviderQuotaError) as e:
                # 认证或额度错误，不重试
                self.circuit_breaker.record_failure()
                raise

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt + 1} failed for {self.provider_name}: {e}"
                )

                # 检查是否应该熔断
                if self.circuit_breaker.record_failure():
                    logger.error(f"Circuit breaker opened for {self.provider_name}")
                    raise ProviderError(
                        f"Too many failures from {self.provider_name}",
                        "CIRCUIT_OPEN",
                        retryable=False,
                    )

                # 等待后重试
                if attempt < self.config.max_retries - 1:
                    await self._sleep(self.config.retry_delay * (attempt + 1))

        # 所有重试都失败了
        raise ProviderError(
            f"All {self.config.max_retries} attempts failed: {last_error}",
            "MAX_RETRIES_EXCEEDED",
            retryable=False,
        )

    async def complete_stream(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> AsyncIterator[str]:
        """流式输出（可选实现）"""
        # 默认实现：非流式，一次性返回
        response = await self.complete(prompt, system, **kwargs)
        yield response.content

    def estimate_tokens(self, text: str) -> int:
        """估算 token 数量"""
        # 简单估算
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态"""
        return {
            "provider": self.provider_name,
            "model": self.config.model,
            "circuit_state": self.circuit_breaker.state,
            "recent_failures": self.circuit_breaker.failures,
            "healthy": self.circuit_breaker.state == "closed",
        }

    async def _sleep(self, seconds: float):
        """异步等待"""
        import asyncio

        await asyncio.sleep(seconds)
