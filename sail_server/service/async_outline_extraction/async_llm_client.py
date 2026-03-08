# -*- coding: utf-8 -*-
# @file async_llm_client.py
# @brief Async LLM client with retry and connection pooling
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步 LLM 客户端

基于 httpx 的异步 HTTP 客户端，支持：
- HTTP/2 连接池
- 自动重试（指数退避）
- 请求/响应日志
- 取消机制
"""

import asyncio
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
import time

import httpx

from .exceptions import LLMError, TaskTimeoutError
from .rate_limiter import RateLimiter, Priority, get_priority_by_level
from .types import Task, TaskLevel

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """LLM 响应"""

    content: str
    usage: Dict[str, int]  # {prompt_tokens, completion_tokens, total_tokens}
    model: str
    latency_ms: float


class AsyncLLMClient:
    """异步 LLM 客户端"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        rate_limiter: Optional[RateLimiter] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base

        # 创建 httpx 客户端（HTTP/2 支持）
        limits = httpx.Limits(
            max_connections=100, max_keepalive_connections=20, keepalive_expiry=30.0
        )

        self.client = httpx.AsyncClient(
            http2=True,
            timeout=httpx.Timeout(timeout),
            limits=limits,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        self._closed = False

        logger.info(f"AsyncLLMClient initialized: base_url={base_url}, model={model}")

    async def complete(
        self,
        prompt: str,
        task: Optional[Task] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> LLMResponse:
        """调用 LLM 完成接口

        Args:
            prompt: 提示词
            task: 关联的任务（用于优先级和取消检查）
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            LLM 响应
        """
        # 估算 token 数
        estimated_tokens = len(prompt) // 4 + max_tokens

        # 获取优先级
        priority = Priority.LOW
        if task:
            priority = get_priority_by_level(task.level)

        # 等待速率限制槽位
        if self.rate_limiter:
            acquired = await self.rate_limiter.acquire_slot(
                priority=priority,
                estimated_tokens=estimated_tokens,
                timeout=self.timeout,
            )
            if not acquired:
                raise TaskTimeoutError(
                    task.id if task else "unknown",
                    self.timeout,
                    "Timeout waiting for rate limiter slot",
                )

        try:
            return await self._call_with_retry(
                prompt, temperature, max_tokens, task, **kwargs
            )
        finally:
            if self.rate_limiter:
                self.rate_limiter.release_slot()

    async def _call_with_retry(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        task: Optional[Task],
        **kwargs,
    ) -> LLMResponse:
        """带重试的调用"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # 检查任务是否被取消
                if task and task.status.value == "cancelled":
                    raise asyncio.CancelledError("Task was cancelled")

                return await self._call_api(prompt, temperature, max_tokens, **kwargs)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e

                # 检查是否是速率限制错误
                is_rate_limit = isinstance(e, LLMError) and e.status_code == 429

                if self.rate_limiter:
                    self.rate_limiter.report_error(is_rate_limit)

                # 最后一次尝试，不再重试
                if attempt == self.max_retries - 1:
                    break

                # 计算退避时间（指数退避 + 抖动）
                delay = self.retry_delay_base * (2**attempt)
                if is_rate_limit and hasattr(e, "retry_after") and e.retry_after:
                    delay = max(delay, e.retry_after)

                logger.warning(
                    f"LLM call failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )

                await asyncio.sleep(delay)

        # 所有重试失败
        error_msg = f"LLM call failed after {self.max_retries} attempts: {last_error}"
        logger.error(error_msg)
        raise last_error if last_error else LLMError(error_msg)

    async def _call_api(
        self, prompt: str, temperature: float, max_tokens: int, **kwargs
    ) -> LLMResponse:
        """实际调用 API"""
        start_time = time.monotonic()

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        logger.debug(
            f"LLM API request: model={self.model}, prompt_length={len(prompt)}"
        )

        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions", json=payload
            )

            latency_ms = (time.monotonic() - start_time) * 1000

            # 处理错误响应
            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                error = LLMError(
                    "Rate limit exceeded",
                    status_code=429,
                    response_body=response.text,
                )
                error.retry_after = float(retry_after) if retry_after else None
                raise error

            response.raise_for_status()

            data = response.json()

            # 提取响应内容
            content = data["choices"][0]["message"]["content"]
            usage = data.get(
                "usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            )

            logger.debug(
                f"LLM API response: latency={latency_ms:.1f}ms, "
                f"tokens={usage.get('total_tokens', 0)}"
            )

            # 报告成功
            if self.rate_limiter:
                self.rate_limiter.report_success()

            return LLMResponse(
                content=content, usage=usage, model=self.model, latency_ms=latency_ms
            )

        except httpx.HTTPStatusError as e:
            raise LLMError(
                f"HTTP error: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text,
            )
        except httpx.TimeoutException as e:
            raise TaskTimeoutError("unknown", self.timeout, str(e))
        except Exception as e:
            raise LLMError(f"API call failed: {e}")

    async def close(self) -> None:
        """关闭客户端"""
        if not self._closed:
            await self.client.aclose()
            self._closed = True
            logger.info("AsyncLLMClient closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
