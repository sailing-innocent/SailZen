# -*- coding: utf-8 -*-
# @file character_detector.py
# @brief Character Detection Service with Caching and Retry Support
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass, field
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
from sail_server.utils.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)
from sail_server.data.analysis import (
    TextRangeSelection,
    CharacterData,
    CharacterAliasData,
    CharacterAttributeData,
    CharacterRelationData,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Service-specific Data Classes
# ============================================================================

@dataclass
class DetectedCharacter:
    """检测到的人物（服务内部使用）"""
    canonical_name: str
    aliases: List[Dict[str, str]] = field(default_factory=list)
    role_type: str = "supporting"  # protagonist, deuteragonist, supporting, minor, mentioned
    role_confidence: float = 0.5
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    key_actions: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class CharacterDetectionConfig:
    """人物检测配置"""
    detect_aliases: bool = True
    detect_attributes: bool = True
    detect_relations: bool = True
    min_confidence: float = 0.5
    max_characters: int = 100
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "character_detection_v2"


@dataclass
class DetectionProgress:
    """检测进度"""
    current_step: str
    progress_percent: int
    message: str
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    is_retrying: bool = False
    retry_attempt: int = 0
    retry_delay: float = 0.0


@dataclass
class DetectionErrorInfo:
    """检测错误信息"""
    error_type: str
    error_message: str
    is_retryable: bool = False
    retry_count: int = 0
    suggestion: str = ""


@dataclass
class CharacterDetectionResult:
    """人物检测结果"""
    characters: List[DetectedCharacter]
    metadata: Dict[str, Any]
    raw_response: Optional[str] = None
    is_recovered: bool = False
    recovered_from_checkpoint: Optional[str] = None


# ============================================================================
# Character Detector Service
# ============================================================================

class CharacterDetector:
    """人物检测服务
    
    负责从文本中检测人物并构建档案，支持：
    - 人物识别和别名合并
    - 角色分类（主角/配角/龙套等）
    - 属性提取（外貌/性格/能力/背景）
    - 关系识别
    - 分块处理长文本
    - 结果合并和去重
    - 分阶段缓存和恢复
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
        # 创建默认 LLM 配置
        if llm_client is None:
            logger.info(f"[CharacterDetector] Using default LLM config: {DEFAULT_LLM_PROVIDER}/{DEFAULT_LLM_MODEL}")
            config = LLMConfig.from_env(LLMProvider(DEFAULT_LLM_PROVIDER))
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
    
    async def detect(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: CharacterDetectionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> CharacterDetectionResult:
        """执行人物检测
        
        Args:
            edition_id: 版本ID
            range_selection: 文本范围选择
            config: 检测配置
            work_title: 作品标题
            known_characters: 已知人物列表
            progress_callback: 进度回调函数
            task_id: 任务ID（用于缓存和恢复）
            resume_from_checkpoint: 是否尝试从检查点恢复
            
        Returns:
            检测结果
        """
        self._current_task_id = task_id
        self._is_cancelled = False
        
        logger.info(f"[Detector] Starting character detection for edition {edition_id}, work_title='{work_title}'")
        
        # 1. 获取文本内容
        from sail_server.service.range_selector import TextRangeParser
        parser = TextRangeParser(self.db)
        content_result = parser.get_content(range_selection)
        logger.info(f"[Detector] Content parsed: {len(content_result.full_text)} chars, "
                   f"{content_result.estimated_tokens} tokens, {len(content_result.chapters)} chapters")
        
        # 2. 检查是否需要分块
        needs_chunking = content_result.estimated_tokens > 8000 or len(content_result.chapters) > 20
        
        if needs_chunking:
            logger.info(f"[Detector] Using batch processing: {len(content_result.chapters)} chapters")
            return await self._detect_with_chunking(
                edition_id,
                content_result,
                config,
                work_title,
                known_characters,
                progress_callback,
                task_id,
                resume_from_checkpoint,
            )
        
        # 3. 单块提取
        logger.info(f"[Detector] Using single-pass detection")
        if progress_callback:
            await progress_callback({
                "current_step": "detecting",
                "progress_percent": 50,
                "message": "正在分析人物...",
            })
        
        result = await self._detect_single_with_retry(
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
                "message": "人物检测完成",
            })
        
        return result
    
    async def _detect_single_with_retry(
        self,
        edition_id: int,
        text_content: str,
        config: CharacterDetectionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
    ) -> CharacterDetectionResult:
        """单块文本检测（带重试）"""
        
        async def operation():
            return await self._detect_single(
                edition_id, text_content, config, work_title, chapters, known_characters
            )
        
        async def on_retry(attempt: int, delay: float, rate_limit_info: Any):
            message = f"LLM 调用失败，正在进行第 {attempt} 次重试，等待 {delay:.1f} 秒..."
            if rate_limit_info:
                message = f"遇到速率限制，等待 {delay:.1f} 秒后重试..."
            
            logger.warning(f"[Detector] {message}")
            
            if progress_callback:
                await progress_callback({
                    "current_step": "retrying",
                    "progress_percent": 40,
                    "message": message,
                    "is_retrying": True,
                    "retry_attempt": attempt,
                    "retry_delay": delay,
                })
        
        retry_result: RetryResult = await self.retry_handler.execute(operation, on_retry)
        
        if not retry_result.success:
            error_info = DetectionErrorInfo(
                error_type=retry_result.last_error_type or "Unknown",
                error_message=str(retry_result.error),
                is_retryable=True,
                retry_count=retry_result.attempts,
                suggestion=self._get_error_suggestion(retry_result),
            )
            
            logger.error(f"[Detector] Detection failed after {retry_result.attempts} attempts: {error_info}")
            
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
            
            raise Exception(f"人物检测失败: {error_info.error_message}")
        
        return retry_result.data
    
    def _get_error_suggestion(self, retry_result: RetryResult) -> str:
        """根据错误类型获取建议"""
        if retry_result.rate_limit_info:
            info = retry_result.rate_limit_info
            if info.limit_type == "TPD":
                return (
                    f"已达到每日 Token 上限 ({info.current_usage}/{info.limit})。"
                    "建议：1) 等待配额重置；2) 切换到其他 LLM 提供商；3) 减少处理章节数量。"
                )
            elif info.limit_type == "RPM":
                return "请求频率过高，请稍后再试。"
            else:
                return "遇到速率限制，请稍后再试。"
        
        if retry_result.last_error_type in ["TimeoutError", "asyncio.TimeoutError"]:
            return "请求超时，可能是网络问题或服务器繁忙。请检查网络连接后重试。"
        
        return "发生未知错误，请检查日志或联系管理员。"
    
    async def _detect_single(
        self,
        edition_id: int,
        text_content: str,
        config: CharacterDetectionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_characters: Optional[List[str]] = None,
    ) -> CharacterDetectionResult:
        """单块文本检测"""
        logger.info(f"[_detect_single] Starting single-pass detection for edition {edition_id}")
        
        # 1. 加载并渲染提示词模板
        chapter_range = self._format_chapter_range(chapters)
        
        variables = {
            "work_title": work_title,
            "chapter_range": chapter_range,
            "known_characters": known_characters or [],
            "chapter_contents": text_content,
        }
        
        # 2. 渲染提示词
        template_id = config.prompt_template_id or "character_detection_v2"
        logger.info(f"[_detect_single] Rendering prompt template: {template_id}")
        try:
            rendered = self.prompt_manager.render(template_id, variables)
            logger.info(f"[_detect_single] Prompt rendered successfully")
        except ValueError as e:
            logger.warning(f"[_detect_single] Template {template_id} not found, falling back to v1: {e}")
            rendered = self.prompt_manager.render("character_detection_v1", variables)
        
        # 3. 调用 LLM
        logger.info(f"[_detect_single] Calling LLM...")
        if config.llm_provider or config.llm_model:
            provider = config.llm_provider or DEFAULT_LLM_PROVIDER
            llm_config = LLMConfig.from_env(LLMProvider(provider))
            if config.llm_model:
                llm_config.model = config.llm_model
            if provider.lower() != "moonshot" and config.temperature is not None:
                llm_config.temperature = config.temperature
            client = LLMClient(llm_config)
            logger.info(f"[_detect_single] Using custom LLM config")
        else:
            client = self.llm_client
            logger.info(f"[_detect_single] Using default LLM client")
        
        response = await client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt,
        )
        logger.info(f"[_detect_single] LLM response received, content length: {len(response.content)}")
        
        # 4. 解析结果
        logger.info(f"[_detect_single] Parsing detection result...")
        result = self._parse_detection_result(response.content)
        logger.info(f"[_detect_single] Result parsed: {len(result.characters)} characters")
        return result
    
    async def _detect_with_chunking(
        self,
        edition_id: int,
        content_result: Any,
        config: CharacterDetectionConfig,
        work_title: str,
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> CharacterDetectionResult:
        """按章节批量检测长文本"""
        chapters = content_result.chapters
        total_chapters = len(chapters)
        
        CHAPTERS_PER_BATCH = 20
        total_batches = (total_chapters + CHAPTERS_PER_BATCH - 1) // CHAPTERS_PER_BATCH
        
        logger.info(f"[_detect_with_chunking] Total chapters: {total_chapters}, batches: {total_batches}")
        
        # 检查点恢复逻辑
        checkpoint: Optional[ExtractionCheckpoint] = None
        if task_id and resume_from_checkpoint:
            checkpoint = self.cache_manager.get_checkpoint(task_id)
            if checkpoint:
                logger.info(f"[_detect_with_chunking] Found checkpoint for task {task_id}")
                if checkpoint.phase == ExtractionPhase.COMPLETED.value:
                    return self._recover_from_checkpoint(checkpoint)
            else:
                checkpoint = self.cache_manager.create_checkpoint(
                    task_id=task_id,
                    edition_id=edition_id,
                    config={
                        "detect_aliases": config.detect_aliases,
                        "detect_attributes": config.detect_attributes,
                        "detect_relations": config.detect_relations,
                    },
                    range_selection={
                        "mode": content_result.mode if hasattr(content_result, 'mode') else "unknown",
                        "edition_id": edition_id,
                    },
                    work_title=work_title,
                    known_characters=known_characters,
                    total_batches=total_batches,
                )
        
        all_characters: List[DetectedCharacter] = []
        failed_batches = []
        
        start_batch = 0
        if checkpoint:
            completed = checkpoint.completed_batches
            if completed:
                start_batch = max(completed) + 1
                for batch_idx in completed:
                    batch_cp = checkpoint.get_batch_result(batch_idx)
                    if batch_cp:
                        for char_dict in batch_cp.characters:
                            char = self._dict_to_character(char_dict)
                            all_characters.append(char)
                logger.info(f"[_detect_with_chunking] Recovered {len(all_characters)} characters from {len(completed)} batches")
        
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.BATCH_STARTED)
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        for batch_idx in range(start_batch, total_batches):
            if self._is_cancelled:
                logger.info(f"[_detect_with_chunking] Task cancelled at batch {batch_idx}")
                break
            
            start_idx = batch_idx * CHAPTERS_PER_BATCH
            end_idx = min(start_idx + CHAPTERS_PER_BATCH, total_chapters)
            
            logger.info(f"[_detect_with_chunking] Processing batch {batch_idx + 1}/{total_batches}")
            
            if checkpoint and checkpoint.is_batch_completed(batch_idx):
                logger.info(f"[_detect_with_chunking] Batch {batch_idx} already completed, skipping")
                continue
            
            batch_chapters = chapters[start_idx:end_idx]
            batch_content = self._format_chapter_batch(batch_chapters, start_idx)
            
            if progress_callback:
                await progress_callback({
                    "current_step": f"detecting_batch_{batch_idx + 1}",
                    "progress_percent": int((batch_idx / total_batches) * 100),
                    "message": f"正在分析第 {start_idx + 1}-{end_idx} 章的人物",
                    "batch_index": batch_idx + 1,
                    "total_batches": total_batches,
                })
            
            if checkpoint:
                checkpoint.update_progress(
                    percent=int((batch_idx / total_batches) * 100),
                    step=f"batch_{batch_idx}",
                    message=f"Processing batch {batch_idx + 1}/{total_batches}",
                )
                self.cache_manager.save_checkpoint(checkpoint.task_id)
            
            try:
                result = await self._detect_single_with_retry(
                    edition_id,
                    batch_content,
                    config,
                    work_title,
                    batch_chapters,
                    known_characters,
                    progress_callback,
                )
                
                all_characters.extend(result.characters)
                logger.info(f"[_detect_with_chunking] Batch {batch_idx + 1} completed, characters: {len(result.characters)}")
                
                if checkpoint:
                    self.cache_manager.add_batch_result(
                        task_id=checkpoint.task_id,
                        batch_index=batch_idx,
                        characters=result.characters,
                        start_chapter=start_idx + 1,
                        end_chapter=end_idx,
                    )
                
            except Exception as e:
                logger.error(f"[_detect_with_chunking] Batch {batch_idx + 1} failed: {e}")
                failed_batches.append(batch_idx)
                
                if checkpoint:
                    checkpoint.mark_batch_failed(batch_idx, str(e))
                    self.cache_manager.save_checkpoint(checkpoint.task_id)
                
                if progress_callback:
                    await progress_callback({
                        "current_step": f"batch_{batch_idx + 1}_failed",
                        "progress_percent": int((batch_idx / total_batches) * 100),
                        "message": f"第 {batch_idx + 1} 批处理失败，继续处理下一批...",
                    })
        
        if progress_callback:
            await progress_callback({
                "current_step": "merging_results",
                "progress_percent": 95,
                "message": "正在合并人物检测结果...",
            })
        
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.MERGING)
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        # 合并并去重
        merged_result = self._merge_character_results(all_characters)
        
        if checkpoint:
            checkpoint.set_phase(ExtractionPhase.COMPLETED)
            checkpoint.update_progress(100, "completed", "人物检测完成")
            self.cache_manager.save_checkpoint(checkpoint.task_id)
        
        if progress_callback:
            await progress_callback({
                "current_step": "completed",
                "progress_percent": 100,
                "message": "人物检测完成",
            })
        
        return merged_result
    
    def _recover_from_checkpoint(self, checkpoint: ExtractionCheckpoint) -> CharacterDetectionResult:
        """从检查点恢复结果"""
        characters = []
        
        for char_dict in checkpoint.accumulated_data.get("characters", []):
            characters.append(self._dict_to_character(char_dict))
        
        logger.info(f"[_recover_from_checkpoint] Recovered {len(characters)} characters")
        
        return CharacterDetectionResult(
            characters=characters,
            metadata={
                "recovered": True,
                "recovered_from": checkpoint.task_id,
                "completed_batches": len(checkpoint.completed_batches),
            },
            is_recovered=True,
            recovered_from_checkpoint=checkpoint.task_id,
        )
    
    def _dict_to_character(self, char_dict: Dict[str, Any]) -> DetectedCharacter:
        """字典转换为人物对象"""
        return DetectedCharacter(
            canonical_name=char_dict.get("canonical_name", ""),
            aliases=char_dict.get("aliases", []),
            role_type=char_dict.get("role_type", "supporting"),
            role_confidence=char_dict.get("role_confidence", 0.5),
            first_appearance=char_dict.get("first_appearance"),
            description=char_dict.get("description", ""),
            attributes=char_dict.get("attributes", []),
            relations=char_dict.get("relations", []),
            key_actions=char_dict.get("key_actions", []),
            mention_count=char_dict.get("mention_count", 0),
        )
    
    def _parse_detection_result(self, response_content: str) -> CharacterDetectionResult:
        """解析 LLM 输出结果"""
        logger.info(f"[_parse_detection_result] Starting to parse response")
        try:
            json_str = self._extract_json(response_content)
            data = json.loads(json_str)
            
            characters = []
            characters_data = data.get("characters", [])
            logger.info(f"[_parse_detection_result] Found {len(characters_data)} characters in response")
            
            for char_data in characters_data:
                char = DetectedCharacter(
                    canonical_name=char_data.get("canonical_name", ""),
                    aliases=char_data.get("aliases", []),
                    role_type=char_data.get("role_type", "supporting"),
                    role_confidence=char_data.get("role_confidence", 0.5),
                    first_appearance=char_data.get("first_appearance"),
                    description=char_data.get("description", ""),
                    attributes=char_data.get("attributes", []),
                    relations=char_data.get("relations", []),
                    key_actions=char_data.get("key_actions", []),
                    mention_count=char_data.get("mention_count", 0),
                )
                characters.append(char)
            
            metadata = data.get("metadata", {})
            
            return CharacterDetectionResult(
                characters=characters,
                metadata=metadata,
                raw_response=response_content,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"[_parse_detection_result] Failed to parse result: {e}")
            return CharacterDetectionResult(
                characters=[],
                metadata={"error": "parse_failed"},
                raw_response=response_content,
            )
        except Exception as e:
            logger.error(f"[_parse_detection_result] Unexpected error: {str(e)}", exc_info=True)
            raise
    
    def _extract_json(self, content: str) -> str:
        """从响应中提取 JSON"""
        content = content.strip()
        
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            return content[start:end].strip()
        
        if "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            return content[start:end].strip()
        
        return content
    
    def _merge_character_results(
        self,
        all_characters: List[DetectedCharacter],
    ) -> CharacterDetectionResult:
        """合并多批次的人物检测结果，进行去重和属性合并"""
        # 按标准名称分组
        name_groups: Dict[str, List[DetectedCharacter]] = {}
        
        for char in all_characters:
            # 使用标准名称作为键
            key = char.canonical_name
            if key not in name_groups:
                name_groups[key] = []
            name_groups[key].append(char)
        
        # 合并同一人物的不同检测结果
        merged_characters = []
        for name, group in name_groups.items():
            if len(group) == 1:
                merged_characters.append(group[0])
            else:
                merged_char = self._merge_character_group(group)
                merged_characters.append(merged_char)
        
        # 按角色重要性排序
        role_order = {
            "protagonist": 0,
            "deuteragonist": 1,
            "supporting": 2,
            "minor": 3,
            "mentioned": 4,
        }
        merged_characters.sort(key=lambda c: role_order.get(c.role_type, 5))
        
        # 统计元数据
        metadata = {
            "total_characters": len(merged_characters),
            "protagonist_count": sum(1 for c in merged_characters if c.role_type == "protagonist"),
            "deuteragonist_count": sum(1 for c in merged_characters if c.role_type == "deuteragonist"),
            "supporting_count": sum(1 for c in merged_characters if c.role_type == "supporting"),
            "minor_count": sum(1 for c in merged_characters if c.role_type == "minor"),
            "mentioned_count": sum(1 for c in merged_characters if c.role_type == "mentioned"),
            "merged": True,
        }
        
        return CharacterDetectionResult(
            characters=merged_characters,
            metadata=metadata,
        )
    
    def _merge_character_group(self, group: List[DetectedCharacter]) -> DetectedCharacter:
        """合并同一人物的多批次检测结果"""
        # 选择置信度最高的作为主要结果
        primary = max(group, key=lambda c: c.role_confidence)
        
        # 合并别名（去重）
        all_aliases = []
        seen_aliases = set()
        for char in group:
            for alias in char.aliases:
                alias_key = alias.get("alias", "")
                if alias_key and alias_key not in seen_aliases:
                    seen_aliases.add(alias_key)
                    all_aliases.append(alias)
        
        # 合并属性（去重，保留置信度高的）
        all_attrs = []
        seen_attrs = set()
        for char in group:
            for attr in char.attributes:
                attr_key = (attr.get("category", ""), attr.get("key", ""))
                if attr_key not in seen_attrs:
                    seen_attrs.add(attr_key)
                    all_attrs.append(attr)
        
        # 合并关系
        all_relations = []
        seen_relations = set()
        for char in group:
            for rel in char.relations:
                rel_key = (rel.get("target_name", ""), rel.get("relation_type", ""))
                if rel_key not in seen_relations:
                    seen_relations.add(rel_key)
                    all_relations.append(rel)
        
        # 合并关键行为
        all_actions = []
        seen_actions = set()
        for char in group:
            for action in char.key_actions:
                if action not in seen_actions:
                    seen_actions.add(action)
                    all_actions.append(action)
        
        # 累加提及次数
        total_mentions = sum(c.mention_count for c in group)
        
        return DetectedCharacter(
            canonical_name=primary.canonical_name,
            aliases=all_aliases,
            role_type=primary.role_type,
            role_confidence=primary.role_confidence,
            first_appearance=primary.first_appearance,
            description=primary.description,
            attributes=all_attrs,
            relations=all_relations,
            key_actions=all_actions,
            mention_count=total_mentions,
        )
    
    def _format_chapter_batch(self, chapters: List[Dict[str, Any]], start_index: int) -> str:
        """格式化章节批次内容"""
        parts = []
        for i, ch in enumerate(chapters):
            chapter_num = start_index + i + 1
            parts.append(f"## 第{chapter_num}章 {ch.get('title', '')}\n\n{ch.get('content', '')}")
        return "\n\n".join(parts)
    
    def _format_chapter_range(self, chapters: List[Dict[str, Any]]) -> str:
        """格式化章节范围显示"""
        if not chapters:
            return "未知范围"
        
        if len(chapters) == 1:
            return chapters[0].get("label", "第1章")
        
        first = chapters[0].get("label", "第1章")
        last = chapters[-1].get("label", f"第{len(chapters)}章")
        return f"{first} - {last}"
    
    def cancel(self):
        """取消当前任务"""
        self._is_cancelled = True
        logger.info(f"[Detector] Task {self._current_task_id} cancelled")


# ============================================================================
# Convenience Functions
# ============================================================================

async def detect_characters(
    db: Session,
    edition_id: int,
    range_selection: TextRangeSelection,
    config: Optional[CharacterDetectionConfig] = None,
    work_title: str = "",
    known_characters: Optional[List[str]] = None,
    task_id: Optional[str] = None,
) -> CharacterDetectionResult:
    """便捷函数：检测人物
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        range_selection: 文本范围选择
        config: 检测配置（可选，使用默认配置）
        work_title: 作品标题
        known_characters: 已知人物列表
        task_id: 任务ID（用于缓存）
        
    Returns:
        检测结果
    """
    if config is None:
        config = CharacterDetectionConfig()
    
    detector = CharacterDetector(db)
    result = await detector.detect(
        edition_id=edition_id,
        range_selection=range_selection,
        config=config,
        work_title=work_title,
        known_characters=known_characters,
        task_id=task_id,
        resume_from_checkpoint=True,
    )
    return result
