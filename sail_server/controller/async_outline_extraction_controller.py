# -*- coding: utf-8 -*-
# @file async_outline_extraction_controller.py
# @brief Async Outline Extraction Controller
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步大纲提取控制器

提供异步并行大纲提取的 API 接口
"""

from __future__ import annotations
from litestar import Controller, post, get, delete
from litestar.exceptions import NotFoundException, ClientException
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import asyncio
import logging
import os

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 导入异步大纲提取模块
from sail_server.service.async_outline_extraction import (
    AsyncOutlineExtractor,
    ExtractionConfig,
    ExtractionResult,
    ExtractionProgress,
)
from sail_server.service.async_outline_extraction.async_llm_client import AsyncLLMClient
from sail_server.utils.llm.available_providers import DEFAULT_LLM_CONFIG
import os


def get_llm_config():
    """获取 LLM 配置"""
    provider = os.environ.get("DEFAULT_LLM_PROVIDER", DEFAULT_LLM_CONFIG["provider"])

    # 根据 provider 获取 API key 和 base URL
    api_key = os.environ.get(f"{provider.upper()}_API_KEY", "")
    api_base = os.environ.get(f"{provider.upper()}_API_BASE", "")

    if not api_base:
        # 默认 base URL
        api_bases = {
            "moonshot": "https://api.moonshot.cn/v1",
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com",
        }
        api_base = api_bases.get(provider, "")

    return {
        "provider": provider,
        "api_key": api_key,
        "api_base": api_base,
        "model": os.environ.get(
            f"{provider.upper()}_MODEL", DEFAULT_LLM_CONFIG.get("model", "gpt-4o-mini")
        ),
    }


# ============================================================================
# Pydantic Models
# ============================================================================


class AsyncOutlineExtractionRequest(BaseModel):
    """异步大纲提取请求"""

    text: str = Field(description="要提取大纲的文本")
    work_id: str = Field(description="作品ID")
    chapter_id: Optional[str] = Field(default=None, description="章节ID")
    mode: str = Field(default="parallel", description="模式：parallel 或 sequential")
    chunk_size: int = Field(default=1500, description="每个 chunk 的 token 数")
    chunk_overlap: int = Field(default=200, description="chunk 之间的重叠 token 数")
    chunks_per_segment: int = Field(
        default=5, description="每个 segment 包含的 chunk 数"
    )
    max_concurrent: int = Field(default=100, description="最大并发数")
    timeout_seconds: int = Field(default=30, description="单个任务超时时间")


class AsyncOutlineExtractionResponse(BaseModel):
    """异步大纲提取响应"""

    success: bool = Field(description="是否成功")
    task_id: str = Field(description="任务ID")
    outline: Optional[Dict[str, Any]] = Field(default=None, description="提取的大纲")
    performance: Optional[Dict[str, Any]] = Field(default=None, description="性能指标")
    message: str = Field(default="", description="消息")
    error: Optional[str] = Field(default=None, description="错误信息")


class AsyncOutlineExtractionProgressResponse(BaseModel):
    """异步大纲提取进度响应"""

    task_id: str = Field(description="任务ID")
    overall_progress: float = Field(description="总体进度百分比")
    level_progress: Dict[str, Dict[str, Any]] = Field(description="各级别进度")
    estimated_time_remaining: Optional[int] = Field(
        default=None, description="预估剩余时间（秒）"
    )
    current_status: str = Field(description="当前状态")
    performance_metrics: Optional[Dict[str, Any]] = Field(
        default=None, description="性能指标"
    )


class AsyncOutlineExtractionStatusResponse(BaseModel):
    """异步大纲提取状态响应"""

    task_id: str = Field(description="任务ID")
    status: str = Field(description="状态")
    is_active: bool = Field(description="是否活跃")


# ============================================================================
# Controller
# ============================================================================


class AsyncOutlineExtractionController(Controller):
    """异步大纲提取控制器"""

    path = "/async-outline"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_extractions: Dict[str, AsyncOutlineExtractor] = {}
        self._lock = asyncio.Lock()

    @post("/extract")
    async def extract_outline(
        self,
        data: AsyncOutlineExtractionRequest,
    ) -> AsyncOutlineExtractionResponse:
        """执行异步大纲提取"""
        try:
            # 创建配置
            config = ExtractionConfig(
                chunk_size=data.chunk_size,
                chunk_overlap=data.chunk_overlap,
                chunks_per_segment=data.chunks_per_segment,
                max_concurrent=data.max_concurrent,
                timeout_seconds=data.timeout_seconds,
                mode=data.mode,
            )

            # 创建 LLM 客户端
            llm_config = get_llm_config()
            llm_client = AsyncLLMClient(
                base_url=llm_config.get("api_base", ""),
                api_key=llm_config.get("api_key", ""),
                model=llm_config.get("model", "gpt-4o-mini"),
                timeout=data.timeout_seconds,
            )

            # 创建提取器
            extractor = AsyncOutlineExtractor(
                llm_client=llm_client,
                config=config,
            )

            # 生成任务ID
            task_id = str(uuid.uuid4())

            async with self._lock:
                self._active_extractions[task_id] = extractor

            # 执行提取
            result = await extractor.extract(
                text=data.text,
                work_id=data.work_id,
                chapter_id=data.chapter_id,
            )

            return AsyncOutlineExtractionResponse(
                success=True,
                task_id=task_id,
                outline=result.outline,
                performance=result.performance,
                message="Extraction completed successfully",
            )

        except Exception as e:
            logger.error(f"Async outline extraction failed: {e}")
            return AsyncOutlineExtractionResponse(
                success=False,
                task_id="",
                error=str(e),
                message="Extraction failed",
            )

    @get("/status/{task_id:str}")
    async def get_status(
        self,
        task_id: str,
    ) -> AsyncOutlineExtractionProgressResponse:
        """获取提取进度"""
        extractor = self._active_extractions.get(task_id)

        if not extractor:
            raise NotFoundException(f"Task {task_id} not found")

        progress = extractor.get_progress(task_id)

        if not progress:
            raise NotFoundException(f"Progress for task {task_id} not found")

        return AsyncOutlineExtractionProgressResponse(
            task_id=task_id,
            overall_progress=progress.overall_progress,
            level_progress=progress.level_progress,
            estimated_time_remaining=progress.estimated_time_remaining,
            current_status=progress.current_status,
            performance_metrics=progress.performance_metrics,
        )

    @delete("/{task_id:str}")
    async def cancel_extraction(
        self,
        task_id: str,
    ) -> AsyncOutlineExtractionStatusResponse:
        """取消提取任务"""
        extractor = self._active_extractions.get(task_id)

        if not extractor:
            raise NotFoundException(f"Task {task_id} not found")

        success = await extractor.cancel_extraction(task_id)

        if success:
            async with self._lock:
                del self._active_extractions[task_id]

        return AsyncOutlineExtractionStatusResponse(
            task_id=task_id,
            status="cancelled" if success else "unknown",
            is_active=task_id in self._active_extractions,
        )

    @get("/active")
    async def list_active_extractions(
        self,
    ) -> List[AsyncOutlineExtractionStatusResponse]:
        """列出活跃的提取任务"""
        return [
            AsyncOutlineExtractionStatusResponse(
                task_id=task_id,
                status="running",
                is_active=True,
            )
            for task_id in self._active_extractions.keys()
        ]
