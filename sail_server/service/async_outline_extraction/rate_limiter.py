# -*- coding: utf-8 -*-
# @file rate_limiter.py
# @brief Rate limiting and concurrency control
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""速率限制和并发控制

实现令牌桶算法，支持 RPM、TPM 和并发数限制
"""

import asyncio
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import IntEnum

from .types import TaskLevel
from .exceptions import ConcurrencyLimitError, RateLimitError

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """任务优先级"""

    HIGH = 0  # Chapter 级别
    MEDIUM = 1  # Segment 级别
    LOW = 2  # Chunk 级别


def get_priority_by_level(level: TaskLevel) -> Priority:
    """根据任务层级获取优先级"""
    priority_map = {
        TaskLevel.CHAPTER: Priority.HIGH,
        TaskLevel.SEGMENT: Priority.MEDIUM,
        TaskLevel.CHUNK: Priority.LOW,
    }
    return priority_map.get(level, Priority.LOW)


@dataclass
class RateLimitConfig:
    """速率限制配置"""

    max_concurrent: int = 100
    rpm_limit: int = 400  # 预留 20% 缓冲
    tpm_limit: int = 2_400_000  # 预留 20% 缓冲
    token_refill_rate: float = 8.33  # 500/60，每秒补充的令牌数


class TokenBucket:
    """令牌桶实现

    用于平滑流量，支持突发和持续限制
    """

    def __init__(
        self, capacity: int, refill_rate: float, initial_tokens: Optional[int] = None
    ):
        self.capacity = capacity
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.refill_rate = refill_rate  # 每秒补充的令牌数
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """获取令牌

        Args:
            tokens: 需要的令牌数
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            是否成功获取令牌
        """
        async with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

        # 需要等待
        if timeout == 0:
            return False

        start_time = time.monotonic()
        while True:
            async with self._lock:
                self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

            # 计算需要等待的时间
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.refill_rate

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    return False
                wait_time = min(wait_time, remaining_timeout)

            await asyncio.sleep(min(wait_time, 0.1))  # 最多等待 100ms

    def _refill(self) -> None:
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    async def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌（非阻塞）"""
        return await self.acquire(tokens, timeout=0)

    @property
    def available_tokens(self) -> float:
        """当前可用令牌数"""
        self._refill()
        return self.tokens


class RateLimiter:
    """速率限制器

    管理并发数、RPM 和 TPM 限制
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config

        # 并发控制
        self._concurrent_semaphore = asyncio.Semaphore(config.max_concurrent)
        self._current_concurrent = 0
        self._concurrent_lock = asyncio.Lock()

        # RPM 限制（令牌桶）
        self._rpm_bucket = TokenBucket(
            capacity=config.rpm_limit, refill_rate=config.token_refill_rate
        )

        # TPM 限制（滑动窗口）
        self._tpm_window: list = []  # (timestamp, tokens)
        self._tpm_lock = asyncio.Lock()

        # 优先级队列
        self._priority_queues: dict = {
            Priority.HIGH: asyncio.Queue(),
            Priority.MEDIUM: asyncio.Queue(),
            Priority.LOW: asyncio.Queue(),
        }

        # 动态调整
        self._adaptive_factor = 1.0
        self._error_count = 0
        self._success_count = 0

        logger.info(
            f"RateLimiter initialized: max_concurrent={config.max_concurrent}, "
            f"rpm_limit={config.rpm_limit}, tpm_limit={config.tpm_limit}"
        )

    async def acquire_slot(
        self,
        priority: Priority = Priority.LOW,
        estimated_tokens: int = 500,
        timeout: Optional[float] = None,
    ) -> bool:
        """获取执行槽位

        Args:
            priority: 任务优先级
            estimated_tokens: 预估 Token 数
            timeout: 超时时间

        Returns:
            是否成功获取槽位
        """
        start_time = time.monotonic()

        # 1. 等待并发槽位
        try:
            await asyncio.wait_for(
                self._concurrent_semaphore.acquire(), timeout=timeout
            )
        except asyncio.TimeoutError:
            return False

        try:
            # 2. 等待 RPM 令牌
            rpm_timeout = None
            if timeout is not None:
                rpm_timeout = timeout - (time.monotonic() - start_time)
                if rpm_timeout <= 0:
                    return False

            rpm_acquired = await self._rpm_bucket.acquire(1, timeout=rpm_timeout)
            if not rpm_acquired:
                return False

            # 3. 检查 TPM 限制
            tpm_timeout = None
            if timeout is not None:
                tpm_timeout = timeout - (time.monotonic() - start_time)
                if tpm_timeout <= 0:
                    return False

            tpm_acquired = await self._check_tpm_limit(
                estimated_tokens, timeout=tpm_timeout
            )
            if not tpm_acquired:
                return False

            # 4. 记录 TPM 使用
            await self._record_token_usage(estimated_tokens)

            async with self._concurrent_lock:
                self._current_concurrent += 1

            return True

        except Exception:
            # 如果失败，释放并发槽位
            self._concurrent_semaphore.release()
            raise

    def release_slot(self) -> None:
        """释放执行槽位"""
        self._concurrent_semaphore.release()

        async def decr():
            async with self._concurrent_lock:
                self._current_concurrent -= 1

        # 创建临时任务来减少计数
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(decr())
            else:
                loop.run_until_complete(decr())
        except Exception:
            pass

    async def _check_tpm_limit(
        self, tokens: int, timeout: Optional[float] = None
    ) -> bool:
        """检查 TPM 限制"""
        start_time = time.monotonic()

        while True:
            async with self._tpm_lock:
                now = time.monotonic()
                # 清理 60 秒前的记录
                self._tpm_window = [
                    (ts, t) for ts, t in self._tpm_window if now - ts < 60
                ]

                # 计算当前分钟的 token 使用
                current_usage = sum(t for _, t in self._tpm_window)

                # 应用动态调整因子
                adjusted_limit = int(self.config.tpm_limit * self._adaptive_factor)

                if current_usage + tokens <= adjusted_limit:
                    return True

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= timeout:
                    return False

            # 等待一段时间后重试
            await asyncio.sleep(0.5)

    async def _record_token_usage(self, tokens: int) -> None:
        """记录 Token 使用"""
        async with self._tpm_lock:
            self._tpm_window.append((time.monotonic(), tokens))

    def report_success(self) -> None:
        """报告成功"""
        self._success_count += 1
        self._maybe_adjust_rate()

    def report_error(self, is_rate_limit: bool = False) -> None:
        """报告错误

        Args:
            is_rate_limit: 是否是速率限制错误（429）
        """
        self._error_count += 1

        if is_rate_limit:
            # 收到 429，立即降低限制
            self._adaptive_factor = max(0.5, self._adaptive_factor * 0.8)
            logger.warning(
                f"Rate limit hit, reducing adaptive factor to {self._adaptive_factor}"
            )

    def _maybe_adjust_rate(self) -> None:
        """根据成功率动态调整速率"""
        total = self._success_count + self._error_count
        if total >= 50:  # 每 50 次请求调整一次
            success_rate = self._success_count / total

            if success_rate > 0.98 and self._adaptive_factor < 1.0:
                # 成功率高，可以恢复
                self._adaptive_factor = min(1.0, self._adaptive_factor * 1.1)
                logger.info(
                    f"High success rate, increasing adaptive factor to {self._adaptive_factor}"
                )

            # 重置计数
            self._success_count = 0
            self._error_count = 0

    @property
    def current_concurrent(self) -> int:
        """当前并发数"""
        return self._current_concurrent

    @property
    def adaptive_factor(self) -> float:
        """当前自适应因子"""
        return self._adaptive_factor

    async def get_stats(self) -> dict:
        """获取统计信息"""
        async with self._tpm_lock:
            now = time.monotonic()
            self._tpm_window = [(ts, t) for ts, t in self._tpm_window if now - ts < 60]
            current_tpm = sum(t for _, t in self._tpm_window)

        return {
            "current_concurrent": self._current_concurrent,
            "max_concurrent": self.config.max_concurrent,
            "current_tpm": current_tpm,
            "tpm_limit": int(self.config.tpm_limit * self._adaptive_factor),
            "rpm_available": self._rpm_bucket.available_tokens,
            "adaptive_factor": self._adaptive_factor,
        }
