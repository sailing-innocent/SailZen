# -*- coding: utf-8 -*-
# @file exceptions.py
# @brief Exception classes for async outline extraction
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步大纲提取的异常类定义"""

from typing import Optional, Dict, Any


class AsyncOutlineExtractionError(Exception):
    """异步大纲提取基础异常"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TaskTimeoutError(AsyncOutlineExtractionError):
    """任务执行超时异常"""

    def __init__(
        self, task_id: str, timeout_seconds: float, message: Optional[str] = None
    ):
        super().__init__(
            message or f"Task {task_id} timed out after {timeout_seconds}s",
            {"task_id": task_id, "timeout_seconds": timeout_seconds},
        )
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds


class RateLimitError(AsyncOutlineExtractionError):
    """速率限制异常"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.retry_after = retry_after


class ConcurrencyLimitError(AsyncOutlineExtractionError):
    """并发限制异常"""

    def __init__(self, current: int, max_concurrent: int):
        super().__init__(
            f"Concurrency limit reached: {current}/{max_concurrent}",
            {"current": current, "max_concurrent": max_concurrent},
        )
        self.current = current
        self.max_concurrent = max_concurrent


class TaskGraphError(AsyncOutlineExtractionError):
    """任务图相关异常"""

    pass


class CircularDependencyError(TaskGraphError):
    """循环依赖异常"""

    def __init__(self, cycle_path: list):
        path_str = " -> ".join(cycle_path + [cycle_path[0]])
        super().__init__(
            f"Circular dependency detected: {path_str}", {"cycle_path": cycle_path}
        )
        self.cycle_path = cycle_path


class TaskNotFoundError(TaskGraphError):
    """任务不存在异常"""

    def __init__(self, task_id: str):
        super().__init__(f"Task not found: {task_id}", {"task_id": task_id})
        self.task_id = task_id


class LLMError(AsyncOutlineExtractionError):
    """LLM API 调用异常"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body
        self.retry_after = retry_after


class ExtractionCancelledError(AsyncOutlineExtractionError):
    """提取任务被取消异常"""

    def __init__(self, task_id: str):
        super().__init__(
            f"Extraction task {task_id} was cancelled", {"task_id": task_id}
        )
        self.task_id = task_id
