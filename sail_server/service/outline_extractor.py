# -*- coding: utf-8 -*-
# @file outline_extractor.py
# @brief Outline Extraction Service with Caching and Retry Support
# @author sailing-innocent
# @date 2025-02-28
# @version 2.0
# ---------------------------------

import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from sail_server.utils.llm.client import LLMClient, LLMConfig, LLMProvider
from sail_server.utils.llm.prompts import PromptTemplateManager
from sail_server.utils.llm.retry_handler import (
    LLMRetryHandler, RetryConfig, RetryStrategy, RetryResult
)
from sail_server.service.extraction_cache import (
    ExtractionCacheManager, ExtractionCheckpoint, ExtractionPhase, get_cache_manager
)
from litestar.exceptions import ClientException
from sail_server.utils.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)
from sail_server.data.analysis import (
    TextRangeSelection,
    OutlineExtractionConfig,
    ExtractedOutlineNode,
    OutlineExtractionResult,
)
from sail_server.model.analysis.outline import (
    add_outline_node_impl,
    add_outline_event_impl,
)
from sail_server.model.analysis.evidence import add_text_evidence_impl

logger = logging.getLogger(__name__)


# ============================================================================
# Service-specific Data Classes
# ============================================================================

@dataclass
class ExtractedTurningPoint:
    """提取的转折点（服务内部使用）"""
    node_id: str
    turning_point_type: str
    description: str


@dataclass
class ExtractionProgress:
    """提取进度"""
    current_step: str
    progress_percent: int
    message: str
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    
    # 新增：重试相关信息
    is_retrying: bool = False
    retry_attempt: int = 0
    retry_delay: float = 0.0
    rate_limit_info: Optional[Dict[str, Any]] = None


@dataclass
class ExtractionErrorInfo:
    """提取错误信息"""
    error_type: str
    error_message: str
    is_retryable: bool = False
    retry_count: int = 0
    rate_limit_info: Optional[Dict[str, Any]] = None
    suggestion: str = ""


# ============================================================================
# Service Result Wrapper
# ============================================================================

@dataclass 
class ServiceExtractionResult:
    """服务层使用的提取结果（内部使用）"""
    nodes: List[ExtractedOutlineNode]
    turning_points: List[ExtractedTurningPoint]
    metadata: Dict[str, Any]
    raw_response: Optional[str] = None
    
    # 新增：恢复信息
    is_recovered: bool = False
    recovered_from_checkpoint: Optional[str] = None
    
    def to_data_result(self) -> OutlineExtractionResult:
        """转换为 data 层的结果类型"""
        return OutlineExtractionResult(
            nodes=self.nodes,
            metadata=self.metadata,
            turning_points=[
                {
                    "node_id": tp.node_id,
                    "turning_point_type": tp.turning_point_type,
                    "description": tp.description,
                }
                for tp in self.turning_points
            ],
        )


# ============================================================================
# Outline Extractor Service
# ============================================================================

class OutlineExtractor:
    """大纲提取服务
    
    负责从文本中提取结构化大纲，支持：
    - 多粒度分析（幕/弧/场景/节拍）
    - 分块处理长文本
    - 结果合并
    - 证据自动关联
    - 分阶段缓存和恢复
    - LLM 调用重试机制
    """
    
    def __init__(
        self,
        db: Session,
        llm_client: Optional[LLMClient] = None,
        prompt_manager: Optional[PromptTemplateManager] = None,
        retry_handler: Optional[LLMRetryHandler] = None,
        cache_manager: Optional[ExtractionCacheManager] = None,
    ):
        self.db = db
        # 创建默认 LLM 配置（使用项目全局默认）
        if llm_client is None:
            logger.info(f"[OutlineExtractor] Using default LLM config: {DEFAULT_LLM_PROVIDER}/{DEFAULT_LLM_MODEL}")
            # 使用 from_env 从环境变量读取 API key 和 provider 特定配置
            # 注意：from_env 已经设置了正确的 temperature（Kimi K2.5 要求为 1.0）
            config = LLMConfig.from_env(LLMProvider(DEFAULT_LLM_PROVIDER))
            # 只覆盖模型和 max_tokens（保持 from_env 设置的 temperature）
            config.model = DEFAULT_LLM_MODEL
            config.max_tokens = DEFAULT_LLM_CONFIG["max_tokens"]
            self.llm_client = LLMClient(config)
        else:
            self.llm_client = llm_client
        self.prompt_manager = prompt_manager or PromptTemplateManager()
        
        # 初始化重试处理器
        self.retry_handler = retry_handler or LLMRetryHandler(
            RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=120.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
                retry_on_rate_limit=True,
                retry_on_timeout=True,
                retry_on_server_error=True,
            )
        )
        
        # 初始化缓存管理器
        self.cache_manager = cache_manager or get_cache_manager()
        
        # 任务状态
        self._current_task_id: Optional[str] = None
        self._is_cancelled: bool = False
    
    async def extract(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> ServiceExtractionResult:
        """执行大纲提取
        
        Args:
            edition_id: 版本ID
            range_selection: 文本范围选择
            config: 提取配置
            work_title: 作品标题
            known_characters: 已知人物列表
            progress_callback: 进度回调函数，接收进度字典
            task_id: 任务ID（用于缓存和恢复）
            resume_from_checkpoint: 是否尝试从检查点恢复
            
        Returns:
            提取结果
        """
        self._current_task_id = task_id
        self._is_cancelled = False
        
        logger.info(f"[Extractor] Starting extraction for edition {edition_id}, work_title='{work_title}'")
        logger.info(f"[Extractor] Config: granularity={config.granularity}, outline_type={config.outline_type}, "
                   f"extract_turning_points={config.extract_turning_points}, extract_characters={config.extract_characters}")
        
        # 1. 获取文本内容
        logger.info(f"[Extractor] Parsing text range selection: mode={range_selection.mode}")
        from sail_server.service.range_selector import TextRangeParser
        parser = TextRangeParser(self.db)
        content_result = parser.get_content(range_selection)
        logger.info(f"[Extractor] Content parsed: {len(content_result.full_text)} chars, "
                   f"{content_result.estimated_tokens} tokens, {len(content_result.chapters)} chapters")
        
        # 2. 检查是否需要分块（超过8000 tokens或超过20章）
        needs_chunking = content_result.estimated_tokens > 8000 or len(content_result.chapters) > 20
        
        if needs_chunking:
            logger.info(f"[Extractor] Using batch processing: {len(content_result.chapters)} chapters")
            return await self._extract_with_chunking(
                edition_id,
                content_result,
                config,
                work_title,
                known_characters,
                progress_callback,
                task_id,
                resume_from_checkpoint,
            )
        
        # 3. 单块提取（小内容）
        logger.info(f"[Extractor] Using single-pass extraction")
        if progress_callback:
            await progress_callback({
                "current_step": "extracting",
                "progress_percent": 50,
                "message": "正在分析文本...",
            })
        
        result = await self._extract_single_with_retry(
            edition_id,
            content_result.full_text,
            config,
            work_title,
            content_result.chapters,
            known_characters,
            progress_callback,
        )
        
        if progress_callback:
            await progress_callback({
                "current_step": "completed",
                "progress_percent": 100,
                "message": "分析完成",
            })
        
        return result
    
    async def extract_with_progress(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
    ) -> ServiceExtractionResult:
        """执行大纲提取（带进度回调）
        
        Args:
            progress_callback: 进度回调函数，接收 ExtractionProgress 参数
            task_id: 任务ID（用于缓存）
            
        Returns:
            提取结果
        """
        return await self.extract(
            edition_id=edition_id,
            range_selection=range_selection,
            config=config,
            work_title=work_title,
            known_characters=known_characters,
            progress_callback=progress_callback,
            task_id=task_id,
            resume_from_checkpoint=True,
        )
    
    async def _extract_single_with_retry(
        self,
        edition_id: int,
        text_content: str,
        config: OutlineExtractionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
    ) -> ServiceExtractionResult:
        """单块文本提取（带重试）"""
        
        async def operation():
            return await self._extract_single(
                edition_id, text_content, config, work_title, chapters, known_characters
            )
        
        async def on_retry(attempt: int, delay: float, rate_limit_info: Any):
            """重试回调"""
            message = f"LLM 调用失败，正在进行第 {attempt} 次重试，等待 {delay:.1f} 秒..."
            if rate_limit_info:
                message = f"遇到速率限制，等待 {delay:.1f} 秒后重试..."
            
            logger.warning(f"[Extractor] {message}")
            
            if progress_callback:
                await progress_callback({
                    "current_step": "retrying",
                    "progress_percent": 40,
                    "message": message,
                    "is_retrying": True,
                    "retry_attempt": attempt,
                    "retry_delay": delay,
                    "rate_limit_info": rate_limit_info.to_dict() if rate_limit_info else None,
                })
        
        retry_result: RetryResult = await self.retry_handler.execute(operation, on_retry)
        
        if not retry_result.success:
            # 构建详细的错误信息
            error_info = ExtractionErrorInfo(
                error_type=retry_result.last_error_type or "Unknown",
                error_message=str(retry_result.error),
                is_retryable=True,
                retry_count=retry_result.attempts,
                rate_limit_info=retry_result.rate_limit_info.to_dict() if retry_result.rate_limit_info else None,
                suggestion=self._get_error_suggestion(retry_result),
            )
            
            logger.error(f"[Extractor] Extraction failed after {retry_result.attempts} attempts: {error_info}")
            
            # 更新检查点状态
            if self._current_task_id:
                self.cache_manager.update_checkpoint(
                    self._current_task_id,
                    lambda cp: (
                        setattr(cp, "phase", ExtractionPhase.FAILED.value),
                        setattr(cp, "last_error", error_info.error_message),
                        setattr(cp, "last_error_type", error_info.error_type),
                    ),
                    auto_save=True,
                )
            
            raise ClientException(
                detail={
                    "message": "大纲提取失败",
                    "error_info": {
                        "type": error_info.error_type,
                        "message": error_info.error_message,
                        "retry_count": error_info.retry_count,
                        "rate_limit_info": error_info.rate_limit_info,
                        "suggestion": error_info.suggestion,
                    },
                }
            )
        
        return retry_result.data
    
    def _get_error_suggestion(self, retry_result: RetryResult) -> str:
        """根据错误类型获取建议"""
        if retry_result.rate_limit_info:
            info = retry_result.rate_limit_info
            if info.limit_type == "TPD":
                return (
                    f"已达到每日 Token 上限 ({info.current_usage}/{info.limit})。"
                    "建议：1) 等待配额重置（通常次日重置）；"
                    "2) 切换到其他 LLM 提供商；"
                    "3) 减少处理章节数量。"
                )
            elif info.limit_type == "RPM":
                return "请求频率过高，请稍后再试。"
            else:
                return "遇到速率限制，请稍后再试。"
        
        if retry_result.last_error_type in ["TimeoutError", "asyncio.TimeoutError"]:
            return "请求超时，可能是网络问题或服务器繁忙。请检查网络连接后重试。"
        
        return "发生未知错误，请检查日志或联系管理员。"
    
    async def _extract_single(
        self,
        edition_id: int,
        text_content: str,
        config: OutlineExtractionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_characters: Optional[List[str]] = None,
    ) -> ServiceExtractionResult:
        """单块文本提取"""
        logger.info(f"[_extract_single] Starting single-pass extraction for edition {edition_id}")
        
        # 1. 加载并渲染提示词模板
        chapter_range = self._format_chapter_range(chapters)
        logger.info(f"[_extract_single] Chapter range: {chapter_range}")
        
        variables = {
            "work_title": work_title,
            "chapter_range": chapter_range,
            "granularity": config.granularity,
            "outline_type": config.outline_type,
            "extract_turning_points": config.extract_turning_points,
            "extract_characters": config.extract_characters,
            "known_characters": known_characters or [],
            "chapter_contents": text_content,
        }
        
        # 2. 渲染提示词
        template_id = config.prompt_template_id or "outline_extraction_v2"
        logger.info(f"[_extract_single] Rendering prompt template: {template_id}")
        try:
            rendered = self.prompt_manager.render(template_id, variables)
            logger.info(f"[_extract_single] Prompt rendered successfully, user_prompt length: {len(rendered.user_prompt)}")
        except ValueError as e:
            # 如果 v2 模板不存在，使用 v1
            logger.warning(f"[_extract_single] Template {template_id} not found, falling back to v1: {e}")
            rendered = self.prompt_manager.render("outline_extraction_v1", variables)
        
        # 4. 调用 LLM
        logger.info(f"[_extract_single] Calling LLM...")
        # 如果需要特定的 provider/model，创建新的 client
        if config.llm_provider or config.llm_model:
            provider = config.llm_provider or DEFAULT_LLM_PROVIDER
            # 使用 from_env 从环境变量读取 API key 和 provider 特定配置
            llm_config = LLMConfig.from_env(LLMProvider(provider))
            # 覆盖模型（如果指定）
            if config.llm_model:
                llm_config.model = config.llm_model
            # 注意：对于 Moonshot/Kimi K2.5，保持 from_env 设置的 temperature=1.0
            # 不要覆盖 temperature，因为 Kimi K2.5 要求必须为 1
            if provider.lower() != "moonshot" and config.temperature is not None:
                llm_config.temperature = config.temperature
            client = LLMClient(llm_config)
            logger.info(f"[_extract_single] Using custom LLM config: provider={provider}, model={llm_config.model}, temp={llm_config.temperature}")
        else:
            client = self.llm_client
            logger.info(f"[_extract_single] Using default LLM client ({DEFAULT_LLM_PROVIDER}/{DEFAULT_LLM_MODEL})")
        
        response = await client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt,
        )
        logger.info(f"[_extract_single] LLM response received, content length: {len(response.content)}")
        
        # 5. 解析结果
        logger.info(f"[_extract_single] Parsing extraction result...")
        result = self._parse_extraction_result(response.content)
        logger.info(f"[_extract_single] Result parsed: {len(result.nodes)} nodes, {len(result.turning_points)} turning_points")
        return result
    
    async def _extract_with_chunking(
        self,
        edition_id: int,
        content_result: Any,
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> ServiceExtractionResult:
        """按章节批量提取长文本（支持检查点恢复）
        
        策略：
        1. 每批处理固定章节数（如20章）
        2. 增量合并结果
        3. 通过回调反馈进度
        4. 支持检查点恢复
        """
        chapters = content_result.chapters
        total_chapters = len(chapters)
        
        # 每批处理的章节数
        CHAPTERS_PER_BATCH = 20
        total_batches = (total_chapters + CHAPTERS_PER_BATCH - 1) // CHAPTERS_PER_BATCH
        
        logger.info(f"[_extract_with_chunking] Total chapters: {total_chapters}, batch size: {CHAPTERS_PER_BATCH}, total_batches: {total_batches}")
        
        # 检查点恢复逻辑
        checkpoint: Optional[ExtractionCheckpoint] = None
        if task_id and resume_from_checkpoint:
            checkpoint = self.cache_manager.get_checkpoint(task_id)
            if checkpoint:
                logger.info(f"[_extract_with_chunking] Found checkpoint for task {task_id}, phase={checkpoint.phase}")
                if checkpoint.phase == ExtractionPhase.COMPLETED.value:
                    # 如果已经完成，直接返回缓存的结果
                    logger.info(f"[_extract_with_chunking] Checkpoint shows completed, recovering result")
                    return self._recover_from_checkpoint(checkpoint)
            else:
                # 创建新的检查点
                checkpoint = self.cache_manager.create_checkpoint(
                    task_id=task_id,
                    edition_id=edition_id,
                    config={
                        "granularity": config.granularity,
                        "outline_type": config.outline_type,
                        "extract_turning_points": config.extract_turning_points,
                        "extract_characters": config.extract_characters,
                    },
                    range_selection={
                        "mode": content_result.mode if hasattr(content_result, 'mode') else "unknown",
                        "edition_id": edition_id,
                    },
                    work_title=work_title,
                    known_characters=known_characters,
                    total_batches=total_batches,
                )
        
        all_nodes = []
        all_turning_points = []
        failed_batches = []
        
        # 确定起始批次
        start_batch = 0
        if checkpoint:
            completed = checkpoint.completed_batches
            if completed:
                start_batch = max(completed) + 1
                # 恢复已完成的批次结果
                for batch_idx in completed:
                    batch_cp = checkpoint.get_batch_result(batch_idx)
                    if batch_cp:
                        for node_dict in batch_cp.nodes:
                            node = self._dict_to_node(node_dict)
                            all_nodes.append(node)
                        for tp_dict in batch_cp.turning_points:
                            tp = ExtractedTurningPoint(**tp_dict)
                            all_turning_points.append(tp)
                logger.info(f"[_extract_with_chunking] Recovered {len(all_nodes)} nodes from {len(completed)} completed batches")
        
        # 更新检查点状态
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.BATCH_STARTED)
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        for batch_idx in range(start_batch, total_batches):
            if self._is_cancelled:
                logger.info(f"[_extract_with_chunking] Task cancelled at batch {batch_idx}")
                break
            
            start_idx = batch_idx * CHAPTERS_PER_BATCH
            end_idx = min(start_idx + CHAPTERS_PER_BATCH, total_chapters)
            
            logger.info(f"[_extract_with_chunking] Processing batch {batch_idx + 1}/{total_batches}, chapters {start_idx + 1}-{end_idx}")
            
            # 检查是否已完成
            if checkpoint and checkpoint.is_batch_completed(batch_idx):
                logger.info(f"[_extract_with_chunking] Batch {batch_idx} already completed, skipping")
                continue
            
            # 构建批次内容
            batch_chapters = chapters[start_idx:end_idx]
            batch_content = self._format_chapter_batch(batch_chapters, start_idx)
            
            # 更新进度
            if progress_callback:
                await progress_callback({
                    "current_step": f"extracting_batch_{batch_idx + 1}",
                    "progress_percent": int((batch_idx / total_batches) * 100),
                    "message": f"正在分析第 {start_idx + 1}-{end_idx} 章（共 {total_chapters} 章）",
                    "batch_index": batch_idx + 1,
                    "total_batches": total_batches,
                })
            
            # 更新检查点
            if checkpoint:
                checkpoint.update_progress(
                    percent=int((batch_idx / total_batches) * 100),
                    step=f"batch_{batch_idx}",
                    message=f"Processing batch {batch_idx + 1}/{total_batches}",
                )
                self.cache_manager.save_checkpoint(checkpoint.task_id)
            
            # 提取当前批次（带重试）
            try:
                result = await self._extract_single_with_retry(
                    edition_id,
                    batch_content,
                    config,
                    work_title,
                    batch_chapters,
                    known_characters,
                    progress_callback,
                )
                
                # 调整节点索引（避免批次间冲突）
                for node in result.nodes:
                    node.sort_index += len(all_nodes)
                
                all_nodes.extend(result.nodes)
                all_turning_points.extend(result.turning_points)
                
                logger.info(f"[_extract_with_chunking] Batch {batch_idx + 1} completed, nodes: {len(result.nodes)}")
                
                # 保存批次结果到检查点
                if checkpoint:
                    self.cache_manager.add_batch_result(
                        task_id=checkpoint.task_id,
                        batch_index=batch_idx,
                        nodes=result.nodes,
                        turning_points=result.turning_points,
                        start_chapter=start_idx + 1,
                        end_chapter=end_idx,
                    )
                
            except Exception as e:
                logger.error(f"[_extract_with_chunking] Batch {batch_idx + 1} failed: {e}")
                failed_batches.append(batch_idx)
                
                if checkpoint:
                    checkpoint.mark_batch_failed(batch_idx, str(e))
                    self.cache_manager.save_checkpoint(checkpoint.task_id)
                
                # 继续处理其他批次，不中断
                if progress_callback:
                    await progress_callback({
                        "current_step": f"batch_{batch_idx + 1}_failed",
                        "progress_percent": int((batch_idx / total_batches) * 100),
                        "message": f"第 {batch_idx + 1} 批处理失败，继续处理下一批...",
                        "batch_index": batch_idx + 1,
                        "total_batches": total_batches,
                    })
        
        # 最终进度更新
        if progress_callback:
            await progress_callback({
                "current_step": "merging_results",
                "progress_percent": 95,
                "message": "正在合并分析结果...",
            })
        
        # 更新检查点状态
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.MERGING)
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        # 合并并去重
        merged_result = self._merge_results(all_nodes, all_turning_points)
        
        # 标记完成
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.COMPLETED)
            checkpoint.update_progress(100, "completed", "分析完成")
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        if progress_callback:
            await progress_callback({
                "current_step": "completed",
                "progress_percent": 100,
                "message": "分析完成",
            })
        
        return merged_result
    
    def _recover_from_checkpoint(self, checkpoint: ExtractionCheckpoint) -> ServiceExtractionResult:
        """从检查点恢复结果"""
        nodes = []
        turning_points = []
        
        for node_dict in checkpoint.accumulated_nodes:
            nodes.append(self._dict_to_node(node_dict))
        
        for tp_dict in checkpoint.accumulated_turning_points:
            turning_points.append(ExtractedTurningPoint(**tp_dict))
        
        logger.info(f"[_recover_from_checkpoint] Recovered {len(nodes)} nodes, {len(turning_points)} turning points")
        
        return ServiceExtractionResult(
            nodes=nodes,
            turning_points=turning_points,
            metadata={
                "recovered": True,
                "recovered_from": checkpoint.task_id,
                "completed_batches": len(checkpoint.completed_batches),
            },
            is_recovered=True,
            recovered_from_checkpoint=checkpoint.task_id,
        )
    
    def _dict_to_node(self, node_dict: Dict[str, Any]) -> ExtractedOutlineNode:
        """字典转换为节点"""
        return ExtractedOutlineNode(
            id=node_dict.get("id", ""),
            node_type=node_dict.get("node_type", "scene"),
            title=node_dict.get("title", ""),
            summary=node_dict.get("summary", ""),
            significance=node_dict.get("significance", "normal"),
            sort_index=node_dict.get("sort_index", 0),
            parent_id=node_dict.get("parent_id"),
            characters=node_dict.get("characters", []),
            evidence=node_dict.get("evidence"),
        )
    
    def _format_chapter_batch(self, chapters: List[Dict[str, Any]], start_index: int) -> str:
        """格式化章节批次内容"""
        parts = []
        for i, ch in enumerate(chapters):
            chapter_num = start_index + i + 1
            parts.append(f"## 第{chapter_num}章 {ch.get('title', '')}\n\n{ch.get('content', '')}")
        return "\n\n".join(parts)
    
    def _parse_extraction_result(self, response_content: str) -> ServiceExtractionResult:
        """解析 LLM 输出结果"""
        logger.info(f"[_parse_extraction_result] Starting to parse response, content length: {len(response_content)}")
        try:
            # 提取 JSON 部分
            json_str = self._extract_json(response_content)
            logger.info(f"[_parse_extraction_result] JSON extracted, length: {len(json_str)}")
            data = json.loads(json_str)
            
            # 解析节点
            nodes = []
            outline_nodes_data = data.get("outline_nodes", [])
            logger.info(f"[_parse_extraction_result] Found {len(outline_nodes_data)} outline nodes in response")
            for i, node_data in enumerate(outline_nodes_data):
                node = ExtractedOutlineNode(
                    id=node_data.get("id", ""),
                    node_type=node_data.get("node_type", "scene"),
                    title=node_data.get("title", ""),
                    summary=node_data.get("summary", ""),
                    significance=node_data.get("significance", "normal"),
                    sort_index=node_data.get("sort_index", 0),
                    parent_id=node_data.get("parent_id"),
                    characters=node_data.get("characters", []),
                    evidence=node_data.get("evidence"),
                )
                nodes.append(node)
                if i < 3:  # 只记录前3个节点的详细信息
                    logger.info(f"[_parse_extraction_result] Node {i}: type={node.node_type}, title='{node.title[:50]}...'")
            
            # 解析转折点
            turning_points = []
            turning_points_data = data.get("turning_points", [])
            logger.info(f"[_parse_extraction_result] Found {len(turning_points_data)} turning points in response")
            for tp_data in turning_points_data:
                tp = ExtractedTurningPoint(
                    node_id=tp_data.get("node_id", ""),
                    turning_point_type=tp_data.get("turning_point_type", ""),
                    description=tp_data.get("description", ""),
                )
                turning_points.append(tp)
            
            metadata = data.get("metadata", {})
            logger.info(f"[_parse_extraction_result] Metadata: {metadata}")
            
            return ServiceExtractionResult(
                nodes=nodes,
                turning_points=turning_points,
                metadata=metadata,
                raw_response=response_content,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"[_parse_extraction_result] Failed to parse extraction result: {e}")
            logger.error(f"[_parse_extraction_result] Raw response preview: {response_content[:500]}...")
            return ServiceExtractionResult(
                nodes=[],
                turning_points=[],
                metadata={"error": "parse_failed"},
                raw_response=response_content,
            )
        except Exception as e:
            logger.error(f"[_parse_extraction_result] Unexpected error during parsing: {str(e)}", exc_info=True)
            raise
    
    def _extract_json(self, content: str) -> str:
        """从响应中提取 JSON"""
        # 尝试直接解析
        content = content.strip()
        
        # 如果包裹在代码块中，提取出来
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            return content[start:end].strip()
        
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            return content[start:end].strip()
        
        return content
    
    def _merge_results(
        self,
        all_nodes: List[ExtractedOutlineNode],
        all_turning_points: List[ExtractedTurningPoint],
    ) -> ServiceExtractionResult:
        """合并多个分块的结果"""
        # 去重：基于标题和内容相似度
        unique_nodes = []
        seen_titles = set()
        
        for node in all_nodes:
            key = f"{node.title}:{node.summary[:50]}"
            if key not in seen_titles:
                seen_titles.add(key)
                unique_nodes.append(node)
        
        # 重新排序
        unique_nodes.sort(key=lambda n: n.sort_index)
        
        # 重新分配 ID
        id_mapping = {}
        for i, node in enumerate(unique_nodes):
            old_id = node.id
            new_id = f"node_{i}"
            id_mapping[old_id] = new_id
            node.id = new_id
        
        # 更新 parent_id
        for node in unique_nodes:
            if node.parent_id and node.parent_id in id_mapping:
                node.parent_id = id_mapping[node.parent_id]
            else:
                node.parent_id = None
        
        # 更新转折点引用
        for tp in all_turning_points:
            if tp.node_id in id_mapping:
                tp.node_id = id_mapping[tp.node_id]
        
        return ServiceExtractionResult(
            nodes=unique_nodes,
            turning_points=all_turning_points,
            metadata={
                "total_nodes": len(unique_nodes),
                "merged": True,
            },
        )
    
    def _format_chapter_range(self, chapters: List[Dict[str, Any]]) -> str:
        """格式化章节范围显示"""
        if not chapters:
            return "未知范围"
        
        if len(chapters) == 1:
            return chapters[0].get("label", "第1章")
        
        first = chapters[0].get("label", "第1章")
        last = chapters[-1].get("label", f"第{len(chapters)}章")
        return f"{first} - {last}"
    
    def save_to_database(
        self,
        edition_id: int,
        result: ServiceExtractionResult,
        config: OutlineExtractionConfig,
    ) -> Dict[str, Any]:
        """将提取结果保存到数据库
        
        Returns:
            保存结果统计
        """
        from sail_server.model.analysis.outline import create_outline_impl
        from sail_server.data.analysis import OutlineData
        
        # 1. 创建大纲
        outline_data = OutlineData(
            edition_id=edition_id,
            name=f"自动提取 - {config.outline_type}",
            outline_type=config.outline_type,
            description=f"通过 LLM 自动提取的大纲，粒度：{config.granularity}",
        )
        outline = create_outline_impl(self.db, outline_data)
        
        # 2. 创建节点映射
        node_id_map = {}
        
        # 先创建所有节点（按层级排序，确保父节点先创建）
        sorted_nodes = sorted(result.nodes, key=lambda n: (n.parent_id is not None, n.sort_index))
        
        created_count = 0
        for node in sorted_nodes:
            parent_orm_id = None
            if node.parent_id and node.parent_id in node_id_map:
                parent_orm_id = node_id_map[node.parent_id]
            
            node_data = add_outline_node_impl(
                db=self.db,
                outline_id=outline.id,
                node_type=node.node_type,
                title=node.title,
                parent_id=parent_orm_id,
                summary=node.summary,
                significance=node.significance,
                meta_data={
                    "extracted": True,
                    "characters": node.characters,
                },
            )
            
            if node_data:
                node_id_map[node.id] = node_data.id
                created_count += 1
                
                # 3. 创建证据关联
                if node.evidence and node.evidence.get("text"):
                    self._create_evidence_for_node(
                        edition_id=edition_id,
                        outline_node_id=node_data.id,
                        evidence_data=node.evidence,
                    )
        
        # 4. 创建转折点事件
        event_count = 0
        for tp in result.turning_points:
            if tp.node_id in node_id_map:
                add_outline_event_impl(
                    db=self.db,
                    node_id=node_id_map[tp.node_id],
                    event_type=tp.turning_point_type,
                    title=tp.turning_point_type,
                    description=tp.description,
                    importance="critical",
                )
                event_count += 1
        
        return {
            "outline_id": outline.id,
            "nodes_created": created_count,
            "events_created": event_count,
        }
    
    def _create_evidence_for_node(
        self,
        edition_id: int,
        outline_node_id: int,
        evidence_data: Dict[str, Any],
    ):
        """为节点创建文本证据"""
        try:
            # 查找包含该文本的章节
            text = evidence_data.get("text", "")
            start_offset = evidence_data.get("start_offset", 0)
            end_offset = evidence_data.get("end_offset", len(text))
            
            # 简化实现：不关联具体章节，只保存证据内容
            # 实际实现中应该根据 offset 查找对应的 node_id
            add_text_evidence_impl(
                db=self.db,
                edition_id=edition_id,
                node_id=0,  # 简化处理
                target_type="outline_node",
                target_id=outline_node_id,
                start_char=start_offset,
                end_char=end_offset,
                text_snippet=text[:200],
                evidence_type="outline_extraction",
                source="llm_extraction",
            )
        except Exception as e:
            logger.error(f"Failed to create evidence: {e}")
    
    def cancel(self):
        """取消当前任务"""
        self._is_cancelled = True
        logger.info(f"[Extractor] Task {self._current_task_id} cancelled")


# ============================================================================
# Convenience Functions
# ============================================================================

async def extract_outline(
    db: Session,
    edition_id: int,
    range_selection: TextRangeSelection,
    config: Optional[OutlineExtractionConfig] = None,
    work_title: str = "",
    known_characters: Optional[List[str]] = None,
    task_id: Optional[str] = None,
) -> OutlineExtractionResult:
    """便捷函数：提取大纲
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        range_selection: 文本范围选择
        config: 提取配置（可选，使用默认配置）
        work_title: 作品标题
        known_characters: 已知人物列表
        task_id: 任务ID（用于缓存）
        
    Returns:
        提取结果
    """
    if config is None:
        config = OutlineExtractionConfig()
    
    extractor = OutlineExtractor(db)
    result = await extractor.extract(
        edition_id=edition_id,
        range_selection=range_selection,
        config=config,
        work_title=work_title,
        known_characters=known_characters,
        task_id=task_id,
        resume_from_checkpoint=True,
    )
    return result.to_data_result()
