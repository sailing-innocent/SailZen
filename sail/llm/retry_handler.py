# -*- coding: utf-8 -*-
# @file retry_handler.py
# @brief LLM Retry Handler with Rate Limit Support
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import asyncio
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any, TypeVar, Generic
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryStrategy(Enum):
    """重试策略"""

    FIXED = "fixed"  # 固定间隔
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"  # 线性增长


class RateLimitInfo:
    """速率限制信息"""

    def __init__(
        self,
        limit_type: str = "unknown",
        current_usage: int = 0,
        limit: int = 0,
        reset_time: Optional[datetime] = None,
        retry_after: Optional[int] = None,
    ):
        self.limit_type = limit_type  # TPD, RPM, TPM, etc.
        self.current_usage = current_usage
        self.limit = limit
        self.reset_time = reset_time
        self.retry_after = retry_after  # 秒
        self.detected_at = datetime.now()

    @property
    def is_rate_limited(self) -> bool:
        return self.current_usage >= self.limit

    @property
    def usage_percent(self) -> float:
        if self.limit == 0:
            return 0.0
        return (self.current_usage / self.limit) * 100

    def to_dict(self) -> dict:
        return {
            "limit_type": self.limit_type,
            "current_usage": self.current_usage,
            "limit": self.limit,
            "usage_percent": round(self.usage_percent, 2),
            "reset_time": self.reset_time.isoformat() if self.reset_time else None,
            "retry_after": self.retry_after,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True  # 添加随机抖动避免惊群
    jitter_range: tuple = (0.8, 1.2)
    retry_on_rate_limit: bool = True
    retry_on_timeout: bool = True
    retry_on_server_error: bool = True


@dataclass
class RetryResult(Generic[T]):
    """重试结果"""

    success: bool
    data: Optional[T] = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_delay: float = 0.0
    rate_limit_info: Optional[RateLimitInfo] = None
    last_error_type: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_delay": round(self.total_delay, 2),
            "rate_limit_info": self.rate_limit_info.to_dict()
            if self.rate_limit_info
            else None,
            "last_error_type": self.last_error_type,
            "error": str(self.error) if self.error else None,
        }


class LLMRetryHandler:
    """LLM 调用重试处理器

    支持：
    - 多种重试策略（固定间隔、指数退避、线性增长）
    - 速率限制检测和智能等待
    - 抖动避免惊群
    - 详细的重试状态反馈
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._rate_limit_history: list[RateLimitInfo] = []

    def _parse_rate_limit_error(self, error: Exception) -> Optional[RateLimitInfo]:
        """从错误信息中解析速率限制信息"""
        import re

        error_str = str(error)

        # Moonshot / OpenAI 格式
        if "rate_limit_reached_error" in error_str or "429" in error_str:
            info = RateLimitInfo(limit_type="rate_limit")

            # 尝试解析 TPD 信息
            if "TPD" in error_str or "organization" in error_str.lower():
                info.limit_type = "TPD"  # Tokens Per Day
                # 解析 current: X, limit: Y
                match = re.search(r"current:\s*(\d+)", error_str)
                if match:
                    info.current_usage = int(match.group(1))
                match = re.search(r"limit:\s*(\d+)", error_str)
                if match:
                    info.limit = int(match.group(1))

            # 尝试解析 retry_after
            match = re.search(r"retry after (\d+) seconds", error_str, re.IGNORECASE)
            if match:
                info.retry_after = int(match.group(1))

            # 如果没有明确的 retry_after，根据策略计算
            if info.retry_after is None:
                info.retry_after = int(self._calculate_wait_time(0, is_rate_limit=True))

            return info

        return None

    def _calculate_wait_time(self, attempt: int, is_rate_limit: bool = False) -> float:
        """计算等待时间"""
        if is_rate_limit and self.config.retry_on_rate_limit:
            # 速率限制使用更长的基础延迟
            base = max(self.config.base_delay * 2, 5.0)
        else:
            base = self.config.base_delay

        if self.config.strategy == RetryStrategy.FIXED:
            delay = base
        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = base * (2**attempt)
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = base * (attempt + 1)
        else:
            delay = base

        # 应用最大值限制
        delay = min(delay, self.config.max_delay)

        # 添加抖动
        if self.config.jitter:
            jitter_min, jitter_max = self.config.jitter_range
            delay *= random.uniform(jitter_min, jitter_max)

        return delay

    def _should_retry(
        self, error: Exception, attempt: int
    ) -> tuple[bool, Optional[RateLimitInfo]]:
        """判断是否应该重试"""
        if attempt >= self.config.max_retries:
            return False, None

        error_str = str(error).lower()
        error_type = type(error).__name__

        # 检查速率限制
        rate_limit_info = self._parse_rate_limit_error(error)
        if rate_limit_info:
            if self.config.retry_on_rate_limit:
                logger.warning(f"Rate limit detected: {rate_limit_info.to_dict()}")
                self._rate_limit_history.append(rate_limit_info)
                return True, rate_limit_info
            return False, rate_limit_info

        # 检查超时
        if self.config.retry_on_timeout:
            if any(kw in error_str for kw in ["timeout", "timed out", "connection"]):
                return True, None
            if error_type in ["TimeoutError", "asyncio.TimeoutError"]:
                return True, None

        # 检查服务器错误
        if self.config.retry_on_server_error:
            if any(
                kw in error_str for kw in ["500", "502", "503", "504", "server error"]
            ):
                return True, None

        return False, None

    async def execute(
        self,
        operation: Callable[[], Any],
        on_retry: Optional[
            Callable[[int, float, Optional[RateLimitInfo]], None]
        ] = None,
    ) -> RetryResult[T]:
        """执行带重试的操作

        Args:
            operation: 要执行的操作
            on_retry: 重试回调函数 (attempt, delay, rate_limit_info)

        Returns:
            RetryResult 包含执行结果和状态信息
        """
        attempt = 0
        total_delay = 0.0
        last_error = None
        last_error_type = None
        last_rate_limit_info = None

        while attempt <= self.config.max_retries:
            try:
                logger.debug(
                    f"[RetryHandler] Attempt {attempt + 1}/{self.config.max_retries + 1}"
                )
                result = await operation()
                return RetryResult(
                    success=True,
                    data=result,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                    rate_limit_info=last_rate_limit_info,
                )

            except Exception as e:
                last_error = e
                last_error_type = type(e).__name__

                should_retry, rate_limit_info = self._should_retry(e, attempt)

                if rate_limit_info:
                    last_rate_limit_info = rate_limit_info

                if not should_retry or attempt >= self.config.max_retries:
                    logger.error(
                        f"[RetryHandler] Giving up after {attempt + 1} attempts: {e}"
                    )
                    break

                # 计算等待时间
                delay = self._calculate_wait_time(
                    attempt, is_rate_limit=rate_limit_info is not None
                )

                # 如果有明确的 retry_after，使用它
                if rate_limit_info and rate_limit_info.retry_after:
                    delay = max(delay, rate_limit_info.retry_after)

                total_delay += delay
                attempt += 1

                logger.warning(
                    f"[RetryHandler] Attempt {attempt} failed ({last_error_type}), "
                    f"retrying in {delay:.2f}s..."
                )

                # 调用回调（支持同步和异步回调）
                if on_retry:
                    try:
                        result = on_retry(attempt, delay, rate_limit_info)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as callback_error:
                        logger.warning(f"Retry callback failed: {callback_error}")

                await asyncio.sleep(delay)

        return RetryResult(
            success=False,
            error=last_error,
            attempts=attempt + 1,
            total_delay=total_delay,
            rate_limit_info=last_rate_limit_info,
            last_error_type=last_error_type,
        )

    def get_rate_limit_stats(self) -> dict:
        """获取速率限制统计信息"""
        if not self._rate_limit_history:
            return {"count": 0}

        recent_limits = [
            r
            for r in self._rate_limit_history
            if (datetime.now() - r.detected_at).total_seconds() < 3600  # 1小时内
        ]

        return {
            "total_count": len(self._rate_limit_history),
            "recent_count": len(recent_limits),
            "last_limit": self._rate_limit_history[-1].to_dict()
            if self._rate_limit_history
            else None,
            "by_type": self._aggregate_by_type(),
        }

    def _aggregate_by_type(self) -> dict:
        """按类型聚合速率限制"""
        counts = {}
        for info in self._rate_limit_history:
            counts[info.limit_type] = counts.get(info.limit_type, 0) + 1
        return counts


# 全局默认重试处理器
_default_retry_handler: Optional[LLMRetryHandler] = None


def get_default_retry_handler() -> LLMRetryHandler:
    """获取默认重试处理器"""
    global _default_retry_handler
    if _default_retry_handler is None:
        _default_retry_handler = LLMRetryHandler(
            RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=120.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
            )
        )
    return _default_retry_handler


def set_default_retry_handler(handler: LLMRetryHandler):
    """设置默认重试处理器"""
    global _default_retry_handler
    _default_retry_handler = handler
