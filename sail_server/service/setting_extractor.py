# -*- coding: utf-8 -*-
# @file setting_extractor.py
# @brief Setting Extraction Service
# @author sailing-innocent
# @date 2025-03-01
# @version 1.0
# ---------------------------------

import json
import logging
from typing import Optional, List, Dict, Any
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
    SettingData,
    SettingAttributeData,
    SettingRelationData,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Service-specific Data Classes
# ============================================================================

@dataclass
class ExtractedSetting:
    """提取的设定（服务内部使用）"""
    canonical_name: str
    setting_type: str  # item, location, organization, concept, magic_system, creature, event_type
    category: str = ""
    importance: str = "minor"  # critical, major, minor, background
    first_appearance: Optional[Dict[str, str]] = None
    description: str = ""
    attributes: List[Dict[str, str]] = field(default_factory=list)
    relations: List[Dict[str, str]] = field(default_factory=list)
    key_scenes: List[str] = field(default_factory=list)
    mention_count: int = 0


@dataclass
class SettingExtractionConfig:
    """设定提取配置"""
    setting_types: List[str] = field(default_factory=lambda: [
        "item", "location", "organization", "concept", "magic_system", "creature", "event_type"
    ])
    min_importance: str = "background"  # critical, major, minor, background
    extract_relations: bool = True
    extract_attributes: bool = True
    max_settings: int = 100
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: float = 0.3
    prompt_template_id: str = "setting_extraction_v1"


@dataclass
class ExtractionProgress:
    """提取进度"""
    current_step: str
    progress_percent: int
    message: str
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None
    is_retrying: bool = False
    retry_attempt: int = 0
    retry_delay: float = 0.0


@dataclass
class SettingExtractionResult:
    """设定提取结果"""
    settings: List[ExtractedSetting]
    metadata: Dict[str, Any]
    raw_response: Optional[str] = None
    is_recovered: bool = False
    recovered_from_checkpoint: Optional[str] = None


# ============================================================================
# Setting Extractor Service
# ============================================================================

class SettingExtractor:
    """设定提取服务
    
    负责从文本中提取设定元素，支持：
    - 多类型设定识别（物品/地点/组织/概念/能力体系/生物/事件类型）
    - 重要性分级
    - 属性提取
    - 关系识别
    - 分块处理长文本
    - 结果合并和去重
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
            logger.info(f"[SettingExtractor] Using default LLM config: {DEFAULT_LLM_PROVIDER}/{DEFAULT_LLM_MODEL}")
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
    
    async def extract(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: SettingExtractionConfig,
        work_title: str = "",
        known_settings: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> SettingExtractionResult:
        """执行设定提取
        
        Args:
            edition_id: 版本ID
            range_selection: 文本范围选择
            config: 提取配置
            work_title: 作品标题
            known_settings: 已知设定列表
            progress_callback: 进度回调函数
            task_id: 任务ID（用于缓存和恢复）
            resume_from_checkpoint: 是否尝试从检查点恢复
            
        Returns:
            提取结果
        """
        self._current_task_id = task_id
        self._is_cancelled = False
        
        logger.info(f"[Extractor] Starting setting extraction for edition {edition_id}")
        
        # 1. 获取文本内容
        from sail_server.service.range_selector import TextRangeParser
        parser = TextRangeParser(self.db)
        content_result = parser.get_content(range_selection)
        logger.info(f"[Extractor] Content parsed: {len(content_result.full_text)} chars")
        
        # 2. 检查是否需要分块
        needs_chunking = content_result.estimated_tokens > 8000 or len(content_result.chapters) > 20
        
        if needs_chunking:
            logger.info(f"[Extractor] Using batch processing")
            return await self._extract_with_chunking(
                edition_id,
                content_result,
                config,
                work_title,
                known_settings,
                progress_callback,
                task_id,
                resume_from_checkpoint,
            )
        
        # 3. 单块提取
        logger.info(f"[Extractor] Using single-pass extraction")
        if progress_callback:
            await progress_callback({
                "current_step": "extracting",
                "progress_percent": 50,
                "message": "正在分析设定...",
            })
        
        result = await self._extract_single_with_retry(
            edition_id,
            content_result.full_text,
            config,
            work_title,
            content_result.chapters,
            known_settings,
            progress_callback,
        )
        
        if progress_callback:
            await progress_callback({
                "current_step": "completed",
                "progress_percent": 100,
                "message": "设定提取完成",
            })
        
        return result
    
    async def _extract_single_with_retry(
        self,
        edition_id: int,
        text_content: str,
        config: SettingExtractionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_settings: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
    ) -> SettingExtractionResult:
        """单块文本提取（带重试）"""
        
        async def operation():
            return await self._extract_single(
                edition_id, text_content, config, work_title, chapters, known_settings
            )
        
        async def on_retry(attempt: int, delay: float, rate_limit_info: Any):
            message = f"LLM 调用失败，正在进行第 {attempt} 次重试..."
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
                })
        
        retry_result: RetryResult = await self.retry_handler.execute(operation, on_retry)
        
        if not retry_result.success:
            logger.error(f"[Extractor] Extraction failed after {retry_result.attempts} attempts")
            raise Exception(f"设定提取失败: {retry_result.error}")
        
        return retry_result.data
    
    async def _extract_single(
        self,
        edition_id: int,
        text_content: str,
        config: SettingExtractionConfig,
        work_title: str,
        chapters: List[Dict[str, Any]],
        known_settings: Optional[List[str]] = None,
    ) -> SettingExtractionResult:
        """单块文本提取"""
        logger.info(f"[_extract_single] Starting extraction for edition {edition_id}")
        
        # 1. 加载并渲染提示词模板
        chapter_range = self._format_chapter_range(chapters)
        
        variables = {
            "work_title": work_title,
            "chapter_range": chapter_range,
            "known_settings": known_settings or [],
            "chapter_contents": text_content,
        }
        
        # 2. 渲染提示词
        template_id = config.prompt_template_id or "setting_extraction_v1"
        logger.info(f"[_extract_single] Rendering prompt template: {template_id}")
        try:
            rendered = self.prompt_manager.render(template_id, variables)
        except ValueError as e:
            logger.warning(f"[_extract_single] Template {template_id} not found: {e}")
            raise
        
        # 3. 调用 LLM
        logger.info(f"[_extract_single] Calling LLM...")
        if config.llm_provider or config.llm_model:
            provider = config.llm_provider or DEFAULT_LLM_PROVIDER
            llm_config = LLMConfig.from_env(LLMProvider(provider))
            if config.llm_model:
                llm_config.model = config.llm_model
            if provider.lower() != "moonshot" and config.temperature is not None:
                llm_config.temperature = config.temperature
            client = LLMClient(llm_config)
        else:
            client = self.llm_client
        
        response = await client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt,
        )
        logger.info(f"[_extract_single] LLM response received")
        
        # 4. 解析结果
        logger.info(f"[_extract_single] Parsing extraction result...")
        result = self._parse_extraction_result(response.content)
        logger.info(f"[_extract_single] Result parsed: {len(result.settings)} settings")
        return result
    
    async def _extract_with_chunking(
        self,
        edition_id: int,
        content_result: Any,
        config: SettingExtractionConfig,
        work_title: str,
        known_settings: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
        task_id: Optional[str] = None,
        resume_from_checkpoint: bool = True,
    ) -> SettingExtractionResult:
        """按章节批量提取长文本"""
        chapters = content_result.chapters
        total_chapters = len(chapters)
        
        CHAPTERS_PER_BATCH = 20
        total_batches = (total_chapters + CHAPTERS_PER_BATCH - 1) // CHAPTERS_PER_BATCH
        
        logger.info(f"[_extract_with_chunking] Total chapters: {total_chapters}, batches: {total_batches}")
        
        all_settings: List[ExtractedSetting] = []
        failed_batches = []
        
        for batch_idx in range(total_batches):
            if self._is_cancelled:
                logger.info(f"[_extract_with_chunking] Task cancelled at batch {batch_idx}")
                break
            
            start_idx = batch_idx * CHAPTERS_PER_BATCH
            end_idx = min(start_idx + CHAPTERS_PER_BATCH, total_chapters)
            
            logger.info(f"[_extract_with_chunking] Processing batch {batch_idx + 1}/{total_batches}")
            
            batch_chapters = chapters[start_idx:end_idx]
            batch_content = self._format_chapter_batch(batch_chapters, start_idx)
            
            if progress_callback:
                await progress_callback({
                    "current_step": f"extracting_batch_{batch_idx + 1}",
                    "progress_percent": int((batch_idx / total_batches) * 100),
                    "message": f"正在分析第 {start_idx + 1}-{end_idx} 章的设定",
                    "batch_index": batch_idx + 1,
                    "total_batches": total_batches,
                })
            
            try:
                result = await self._extract_single_with_retry(
                    edition_id,
                    batch_content,
                    config,
                    work_title,
                    batch_chapters,
                    known_settings,
                    progress_callback,
                )
                
                all_settings.extend(result.settings)
                logger.info(f"[_extract_with_chunking] Batch {batch_idx + 1} completed, settings: {len(result.settings)}")
                
            except Exception as e:
                logger.error(f"[_extract_with_chunking] Batch {batch_idx + 1} failed: {e}")
                failed_batches.append(batch_idx)
                
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
                "message": "正在合并设定提取结果...",
            })
        
        # 合并并去重
        merged_result = self._merge_setting_results(all_settings)
        
        if progress_callback:
            await progress_callback({
                "current_step": "completed",
                "progress_percent": 100,
                "message": "设定提取完成",
            })
        
        return merged_result
    
    def _parse_extraction_result(self, response_content: str) -> SettingExtractionResult:
        """解析 LLM 输出结果"""
        logger.info(f"[_parse_extraction_result] Starting to parse response")
        try:
            json_str = self._extract_json(response_content)
            data = json.loads(json_str)
            
            settings = []
            settings_data = data.get("settings", [])
            logger.info(f"[_parse_extraction_result] Found {len(settings_data)} settings in response")
            
            for setting_data in settings_data:
                setting = ExtractedSetting(
                    canonical_name=setting_data.get("canonical_name", ""),
                    setting_type=setting_data.get("setting_type", "item"),
                    category=setting_data.get("category", ""),
                    importance=setting_data.get("importance", "minor"),
                    first_appearance=setting_data.get("first_appearance"),
                    description=setting_data.get("description", ""),
                    attributes=setting_data.get("attributes", []),
                    relations=setting_data.get("relations", []),
                    key_scenes=setting_data.get("key_scenes", []),
                    mention_count=setting_data.get("mention_count", 0),
                )
                settings.append(setting)
            
            metadata = data.get("metadata", {})
            
            return SettingExtractionResult(
                settings=settings,
                metadata=metadata,
                raw_response=response_content,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"[_parse_extraction_result] Failed to parse result: {e}")
            return SettingExtractionResult(
                settings=[],
                metadata={"error": "parse_failed"},
                raw_response=response_content,
            )
        except Exception as e:
            logger.error(f"[_parse_extraction_result] Unexpected error: {str(e)}", exc_info=True)
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
    
    def _merge_setting_results(
        self,
        all_settings: List[ExtractedSetting],
    ) -> SettingExtractionResult:
        """合并多批次的设定提取结果，进行去重和属性合并"""
        # 按标准名称分组
        name_groups: Dict[str, List[ExtractedSetting]] = {}
        
        for setting in all_settings:
            key = setting.canonical_name
            if key not in name_groups:
                name_groups[key] = []
            name_groups[key].append(setting)
        
        # 合并同一设定的不同提取结果
        merged_settings = []
        for name, group in name_groups.items():
            if len(group) == 1:
                merged_settings.append(group[0])
            else:
                merged_setting = self._merge_setting_group(group)
                merged_settings.append(merged_setting)
        
        # 按重要性排序
        importance_order = {
            "critical": 0,
            "major": 1,
            "minor": 2,
            "background": 3,
        }
        merged_settings.sort(key=lambda s: importance_order.get(s.importance, 4))
        
        # 统计元数据
        by_type = {}
        by_importance = {}
        for setting in merged_settings:
            by_type[setting.setting_type] = by_type.get(setting.setting_type, 0) + 1
            by_importance[setting.importance] = by_importance.get(setting.importance, 0) + 1
        
        metadata = {
            "total_settings": len(merged_settings),
            "by_type": by_type,
            "by_importance": by_importance,
            "merged": True,
        }
        
        return SettingExtractionResult(
            settings=merged_settings,
            metadata=metadata,
        )
    
    def _merge_setting_group(self, group: List[ExtractedSetting]) -> ExtractedSetting:
        """合并同一设定的多批次提取结果"""
        # 选择重要性最高的作为主要结果
        importance_order = {"critical": 0, "major": 1, "minor": 2, "background": 3}
        primary = min(group, key=lambda s: importance_order.get(s.importance, 4))
        
        # 合并属性（去重）
        all_attrs = []
        seen_attrs = set()
        for setting in group:
            for attr in setting.attributes:
                attr_key = attr.get("key", "")
                if attr_key and attr_key not in seen_attrs:
                    seen_attrs.add(attr_key)
                    all_attrs.append(attr)
        
        # 合并关系
        all_relations = []
        seen_relations = set()
        for setting in group:
            for rel in setting.relations:
                rel_key = (rel.get("target_name", ""), rel.get("relation_type", ""))
                if rel_key not in seen_relations:
                    seen_relations.add(rel_key)
                    all_relations.append(rel)
        
        # 合并关键场景
        all_scenes = []
        seen_scenes = set()
        for setting in group:
            for scene in setting.key_scenes:
                if scene not in seen_scenes:
                    seen_scenes.add(scene)
                    all_scenes.append(scene)
        
        # 累加提及次数
        total_mentions = sum(s.mention_count for s in group)
        
        return ExtractedSetting(
            canonical_name=primary.canonical_name,
            setting_type=primary.setting_type,
            category=primary.category,
            importance=primary.importance,
            first_appearance=primary.first_appearance,
            description=primary.description,
            attributes=all_attrs,
            relations=all_relations,
            key_scenes=all_scenes,
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
        logger.info(f"[Extractor] Task {self._current_task_id} cancelled")


# ============================================================================
# Convenience Functions
# ============================================================================

async def extract_settings(
    db: Session,
    edition_id: int,
    range_selection: TextRangeSelection,
    config: Optional[SettingExtractionConfig] = None,
    work_title: str = "",
    known_settings: Optional[List[str]] = None,
    task_id: Optional[str] = None,
) -> SettingExtractionResult:
    """便捷函数：提取设定
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        range_selection: 文本范围选择
        config: 提取配置（可选，使用默认配置）
        work_title: 作品标题
        known_settings: 已知设定列表
        task_id: 任务ID（用于缓存）
        
    Returns:
        提取结果
    """
    if config is None:
        config = SettingExtractionConfig()
    
    extractor = SettingExtractor(db)
    result = await extractor.extract(
        edition_id=edition_id,
        range_selection=range_selection,
        config=config,
        work_title=work_title,
        known_settings=known_settings,
        task_id=task_id,
        resume_from_checkpoint=True,
    )
    return result
