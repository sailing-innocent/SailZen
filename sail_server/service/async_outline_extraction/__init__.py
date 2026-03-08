# -*- coding: utf-8 -*-
# @file __init__.py
# @brief Async Outline Extraction Module
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步并行大纲提取模块

该模块提供了基于 asyncio 的并行大纲提取功能，支持：
- 多级任务层级（chunk/segment/chapter）
- 任务依赖图管理
- 并发控制和速率限制
- 实时进度追踪
"""

from .types import TaskStatus, TaskLevel, ExtractionConfig, ExtractionProgress
from .exceptions import (
    AsyncOutlineExtractionError,
    TaskTimeoutError,
    RateLimitError,
    TaskGraphError,
    ConcurrencyLimitError,
)
from .task_graph import Task, TaskGraph
from .rate_limiter import RateLimiter, TokenBucket
from .text_splitter import TextSplitter
from .async_llm_client import AsyncLLMClient
from .result_merger import ChunkResultMerger, SegmentResultMerger
from .progress_tracker import ProgressTracker
from .async_extractor import AsyncOutlineExtractor, ExtractionResult

__all__ = [
    # Types
    "TaskStatus",
    "TaskLevel",
    "ExtractionConfig",
    "ExtractionProgress",
    # Exceptions
    "AsyncOutlineExtractionError",
    "TaskTimeoutError",
    "RateLimitError",
    "TaskGraphError",
    "ConcurrencyLimitError",
    # Core Classes
    "Task",
    "TaskGraph",
    "RateLimiter",
    "TokenBucket",
    "TextSplitter",
    "AsyncLLMClient",
    "ChunkResultMerger",
    "SegmentResultMerger",
    "ProgressTracker",
    "AsyncOutlineExtractor",
    "ExtractionResult",
]
