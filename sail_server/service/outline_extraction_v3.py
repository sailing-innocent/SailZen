# -*- coding: utf-8 -*-
# @file outline_extraction_v3.py
# @brief Outline Extraction V3 Engine - Strategy Selector + Iterative Refinement
# @author sailing-innocent
# @date 2026-04-17
# @version 1.0
# ---------------------------------

"""
大纲提取 V3 引擎

核心特性：
1. 动态策略选择（短篇直通 / 中篇标准 / 长篇分层 / 超长篇递进）
2. 迭代式精炼（Round 1 粗纲 → Round 2 全局精炼）
3. 简化上下文管理（Token 预算分配）
4. 复用 V2 的位置锚点、批次合并、冲突检测
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sail.llm.client import LLMClient, LLMConfig, LLMProvider
from sail.llm.retry_handler import LLMRetryHandler, RetryConfig, RetryStrategy
from sail.llm.available_providers import DEFAULT_LLM_PROVIDER, DEFAULT_LLM_MODEL

from sail_server.application.dto.analysis import (
    TextRangeSelection,
    OutlineExtractionConfig,
)
from sail_server.service.outline_extraction_v2 import (
    NodePositionAnchor,
    ExtractedOutlineNodeV2,
    ExtractionBatch,
    BatchExtractionResult,
    MergedOutlineResult,
    ChapterInfo,
    OutlineExtractionBatcher,
    OutlineMerger,
    OutlineOrderValidator,
)
from sail_server.service.range_selector import TextRangeParser, TokenEstimator

logger = logging.getLogger(__name__)


# ============================================================================
# Strategy Definitions
# ============================================================================

class ExtractionStrategy(str, Enum):
    """提取策略"""
    DIRECT = "direct"           # ≤30 章：单次 LLM 调用
    STANDARD = "standard"       # 31-150 章：V2 标准批次并行
    HIERARCHICAL = "hierarchical"  # 151-500 章：标准 + 全局精炼
    PROGRESSIVE = "progressive"    # >500 章：递进模式（分阶段）


@dataclass
class StrategyConfig:
    """策略配置"""
    strategy: ExtractionStrategy
    max_chapters_per_batch: int = 20
    max_tokens_per_batch: int = 8000
    overlap_chapters: int = 1
    enable_refinement: bool = False
    refinement_model: Optional[str] = None
    progressive_stage_size: Optional[int] = None
    concurrency: int = 5


class StrategySelector:
    """策略选择器
    
    根据作品规模自动选择最优提取策略。
    """
    
    # 策略边界
    DIRECT_THRESHOLD = 30
    STANDARD_THRESHOLD = 150
    HIERARCHICAL_THRESHOLD = 500
    
    # 各策略的默认配置
    DEFAULT_CONFIGS = {
        ExtractionStrategy.DIRECT: StrategyConfig(
            strategy=ExtractionStrategy.DIRECT,
            max_chapters_per_batch=30,
            max_tokens_per_batch=24000,
            overlap_chapters=0,
            enable_refinement=False,
            concurrency=1,
        ),
        ExtractionStrategy.STANDARD: StrategyConfig(
            strategy=ExtractionStrategy.STANDARD,
            max_chapters_per_batch=20,
            max_tokens_per_batch=8000,
            overlap_chapters=1,
            enable_refinement=False,
            concurrency=5,
        ),
        ExtractionStrategy.HIERARCHICAL: StrategyConfig(
            strategy=ExtractionStrategy.HIERARCHICAL,
            max_chapters_per_batch=15,
            max_tokens_per_batch=6000,
            overlap_chapters=1,
            enable_refinement=True,
            refinement_model=DEFAULT_LLM_MODEL,
            concurrency=5,
        ),
        ExtractionStrategy.PROGRESSIVE: StrategyConfig(
            strategy=ExtractionStrategy.PROGRESSIVE,
            max_chapters_per_batch=15,
            max_tokens_per_batch=6000,
            overlap_chapters=1,
            enable_refinement=True,
            refinement_model=DEFAULT_LLM_MODEL,
            progressive_stage_size=200,
            concurrency=5,
        ),
    }
    
    @classmethod
    def select(cls, chapter_count: int, user_override: Optional[str] = None) -> StrategyConfig:
        """选择提取策略
        
        Args:
            chapter_count: 章节总数
            user_override: 用户手动指定的策略（可选）
            
        Returns:
            策略配置
        """
        if user_override:
            try:
                strategy = ExtractionStrategy(user_override)
                return cls.DEFAULT_CONFIGS[strategy]
            except ValueError:
                logger.warning(f"Unknown strategy override: {user_override}, using auto-selection")
        
        if chapter_count <= cls.DIRECT_THRESHOLD:
            strategy = ExtractionStrategy.DIRECT
        elif chapter_count <= cls.STANDARD_THRESHOLD:
            strategy = ExtractionStrategy.STANDARD
        elif chapter_count <= cls.HIERARCHICAL_THRESHOLD:
            strategy = ExtractionStrategy.HIERARCHICAL
        else:
            strategy = ExtractionStrategy.PROGRESSIVE
        
        logger.info(f"[StrategySelector] Selected {strategy.value} for {chapter_count} chapters")
        return cls.DEFAULT_CONFIGS[strategy]


# ============================================================================
# Simplified Context Builder
# ============================================================================

@dataclass
class ContextBudget:
    """上下文 Token 预算"""
    total_budget: int = 32000
    text_ratio: float = 0.65
    character_ratio: float = 0.20
    context_ratio: float = 0.10
    format_ratio: float = 0.05
    
    @property
    def text_budget(self) -> int:
        return int(self.total_budget * self.text_ratio)
    
    @property
    def character_budget(self) -> int:
        return int(self.total_budget * self.character_ratio)
    
    @property
    def context_budget(self) -> int:
        return int(self.total_budget * self.context_ratio)
    
    @property
    def format_budget(self) -> int:
        return int(self.total_budget * self.format_ratio)


class SimpleContextBuilder:
    """简化版上下文构建器
    
    替代复杂的 5C Context Builder，采用简单的 Token 预算分配。
    """
    
    def __init__(self, budget: Optional[ContextBudget] = None):
        self.budget = budget or ContextBudget()
        self.token_estimator = TokenEstimator()
    
    def build(
        self,
        chapters_text: str,
        known_characters: Optional[List[Dict[str, Any]]] = None,
        prev_batch_summary: Optional[str] = None,
        work_title: str = "",
        batch_info: Optional[str] = None,
    ) -> str:
        """构建提示词上下文
        
        Args:
            chapters_text: 章节原文
            known_characters: 已知角色列表（含名称、描述等）
            prev_batch_summary: 上一批结尾摘要
            work_title: 作品标题
            batch_info: 批次信息描述
            
        Returns:
            构建好的提示词
        """
        # 1. 截断原文（如果超长）
        truncated_text = self._truncate_text(chapters_text, self.budget.text_budget)
        
        # 2. 格式化角色列表
        character_section = self._format_characters(
            known_characters or [], 
            self.budget.character_budget
        )
        
        # 3. 前文摘要
        context_section = ""
        if prev_batch_summary:
            max_chars = int(self.budget.context_budget * 1.5)  # 中文字符估算
            context_section = prev_batch_summary[:max_chars]
        
        # 4. 组装提示词
        parts = []
        
        if work_title:
            parts.append(f"【作品】{work_title}")
        
        if batch_info:
            parts.append(f"【批次】{batch_info}")
        
        if context_section:
            parts.append(f"【前文衔接】\n{context_section}")
        
        if character_section:
            parts.append(f"【已知角色】\n{character_section}")
        
        parts.append(f"【待分析文本】\n{truncated_text}")
        
        return "\n\n".join(parts)
    
    def _truncate_text(self, text: str, token_budget: int) -> str:
        """截断文本至 Token 预算内
        
        策略：如果超长，截断尾部（通常尾部是过渡性内容，不如头部重要）
        """
        estimated_tokens = self.token_estimator.estimate(text)
        if estimated_tokens <= token_budget:
            return text
        
        # 计算需要保留的字符数
        target_chars = int(token_budget * 1.5)  # 中文约 1.5 字符/token
        
        # 截断尾部
        truncated = text[:target_chars]
        
        # 尝试在段落边界截断
        last_para = truncated.rfind("\n\n")
        if last_para > target_chars * 0.8:
            truncated = truncated[:last_para]
        
        logger.debug(f"[ContextBuilder] Truncated text from {len(text)} to {len(truncated)} chars")
        return truncated + "\n\n[文本已截断...]"
    
    def _format_characters(
        self, 
        characters: List[Dict[str, Any]], 
        token_budget: int
    ) -> str:
        """格式化角色列表"""
        if not characters:
            return ""
        
        lines = []
        max_chars = int(token_budget * 1.5)
        current_chars = 0
        
        for i, char in enumerate(characters[:20]):  # 最多 20 个
            name = char.get("canonical_name", char.get("name", "未知"))
            desc = char.get("description", "")
            aliases = char.get("aliases", [])
            
            line = f"- {name}"
            if aliases:
                line += f"（别名：{', '.join(aliases[:3])}）"
            if desc:
                # 限制描述长度
                short_desc = desc[:50] + "..." if len(desc) > 50 else desc
                line += f"：{short_desc}"
            
            line_chars = len(line)
            if current_chars + line_chars > max_chars:
                lines.append(f"- ... 等共 {len(characters)} 个角色")
                break
            
            lines.append(line)
            current_chars += line_chars
        
        return "\n".join(lines)


# ============================================================================
# Global Refinement
# ============================================================================

class GlobalRefinementPrompt:
    """全局精炼 Prompt 模板（内联，后续可迁移到 YAML）"""
    
    SYSTEM_PROMPT = """你是一位资深小说编辑，擅长从全局视角审视故事结构。

你的任务是基于已提取的粗纲，以"全书读者视角"进行全局精炼：
1. 识别跨章节伏笔和呼应关系
2. 合并重复或过度细分的节点
3. 修正层级关系（确保父节点确实涵盖子节点内容）
4. 补充全局视角才能发现的情节线索
5. 标注节点之间的因果/递进关系

输出要求：
- 必须输出合法的 JSON 格式
- 保持所有节点的 position_anchor 不变（确保顺序稳定）
- 可以修改、合并、删除节点，也可以新增全局视角节点
- 不要输出任何解释性文字"""

    USER_PROMPT_TEMPLATE = """【任务】全局大纲精炼

【作品】{work_title}
【总章节数】{total_chapters}
【原始节点数】{total_nodes}

【粗纲结构】
{outline_summary}

【候选实体列表】
{candidate_entities}

【精炼要求】
1. 合并相似节点（标题或摘要高度相似的相邻节点）
2. 识别并标注跨批次的情节线索（如伏笔、呼应、反转）
3. 确保层级合理（父节点应涵盖所有子节点的内容）
4. 为重要节点添加 "global_insight" 字段（全局视角补充）
5. 删除过于细碎的次要节点（保留 significance ≥ normal 的节点）

【输出格式】
输出与粗纲相同的 JSON 结构，在 metadata 中增加：
- refinement_changes: 变更列表（合并了哪些节点、新增了哪些节点、删除了哪些节点）
- cross_chapter_threads: 跨章节线索列表

```json
{{"outline_nodes": [...], "turning_points": [...], "metadata": {{...}}}}
```"""

    @classmethod
    def build(
        cls,
        merged_result: MergedOutlineResult,
        work_title: str = "",
        total_chapters: int = 0,
        candidate_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, str]:
        """构建全局精炼的 system prompt 和 user prompt
        
        Returns:
            (system_prompt, user_prompt)
        """
        # 生成大纲摘要（精简版，避免超出上下文）
        outline_summary = cls._summarize_outline(merged_result)
        
        # 格式化候选实体
        entity_text = cls._format_entities(candidate_entities or [])
        
        user_prompt = cls.USER_PROMPT_TEMPLATE.format(
            work_title=work_title or "未命名作品",
            total_chapters=total_chapters,
            total_nodes=len(merged_result.nodes),
            outline_summary=outline_summary,
            candidate_entities=entity_text,
        )
        
        return cls.SYSTEM_PROMPT, user_prompt
    
    @classmethod
    def _summarize_outline(cls, result: MergedOutlineResult, max_nodes: int = 100) -> str:
        """生成大纲精简摘要（用于精炼输入）"""
        nodes = result.nodes[:max_nodes]  # 限制节点数，避免过长
        
        lines = []
        for node in nodes:
            anchor = node.get_effective_anchor()
            indent = "  " * node.depth
            line = f"{indent}- [{node.node_type}] {node.title} (第{anchor.chapter_index + 1}章)"
            if node.significance in ("critical", "major"):
                line += " [重要]"
            lines.append(line)
            
            # 只显示重要节点的摘要
            if node.significance in ("critical", "major") and node.summary:
                summary = node.summary[:60] + "..." if len(node.summary) > 60 else node.summary
                lines.append(f"{indent}  摘要：{summary}")
        
        return "\n".join(lines)
    
    @classmethod
    def _format_entities(cls, entities: List[Dict[str, Any]]) -> str:
        """格式化实体列表"""
        if not entities:
            return "无"
        
        lines = []
        for entity in entities[:30]:
            name = entity.get("name", "未知")
            types = entity.get("types", [])
            mentions = entity.get("mention_count", 0)
            line = f"- {name}"
            if types:
                line += f" ({', '.join(types)})"
            line += f" - 出现 {mentions} 次"
            lines.append(line)
        
        return "\n".join(lines)


# ============================================================================
# Iterative Refinement Engine
# ============================================================================

@dataclass
class RefinementResult:
    """精炼结果"""
    refined_outline: MergedOutlineResult
    changes: List[Dict[str, Any]]
    cross_chapter_threads: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


class IterativeRefinementEngine:
    """迭代精炼引擎
    
    Round 1: 粗纲提取（复用 V2 的批次并行处理）
    Round 2: 全局精炼（单次 LLM 调用，基于全书视角）
    """
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        retry_handler: Optional[LLMRetryHandler] = None,
    ):
        self.llm_client = llm_client or self._create_default_llm_client()
        self.retry_handler = retry_handler or self._create_default_retry_handler()
    
    def _create_default_llm_client(self) -> LLMClient:
        config = LLMConfig.from_env(LLMProvider(DEFAULT_LLM_PROVIDER))
        return LLMClient(config)
    
    def _create_default_retry_handler(self) -> LLMRetryHandler:
        return LLMRetryHandler(
            RetryConfig(
                max_retries=2,
                base_delay=2.0,
                max_delay=60.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
            )
        )
    
    async def refine(
        self,
        coarse_result: MergedOutlineResult,
        work_title: str = "",
        total_chapters: int = 0,
        candidate_entities: Optional[List[Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> RefinementResult:
        """执行全局精炼
        
        Args:
            coarse_result: Round 1 粗纲结果
            work_title: 作品标题
            total_chapters: 总章节数
            candidate_entities: 候选实体列表
            progress_callback: 进度回调
            
        Returns:
            精炼结果
        """
        logger.info(f"[Refinement] Starting global refinement for {len(coarse_result.nodes)} nodes")
        
        if progress_callback:
            await progress_callback({
                "current_step": "global_refinement",
                "progress_percent": 70,
                "message": "正在进行全局视角精炼...",
            })
        
        # 构建 Prompt
        system_prompt, user_prompt = GlobalRefinementPrompt.build(
            merged_result=coarse_result,
            work_title=work_title,
            total_chapters=total_chapters,
            candidate_entities=candidate_entities,
        )
        
        # 调用 LLM
        async def operation():
            response = await self.llm_client.complete(
                prompt=user_prompt,
                system=system_prompt,
            )
            return self._parse_refinement_response(response.content, coarse_result)
        
        retry_result = await self.retry_handler.execute(operation)
        
        if not retry_result.success:
            logger.error(f"[Refinement] Global refinement failed: {retry_result.error}")
            # 降级：返回原始结果
            return RefinementResult(
                refined_outline=coarse_result,
                changes=[],
                cross_chapter_threads=[],
                metadata={"refinement_status": "failed", "error": str(retry_result.error)},
            )
        
        refinement = retry_result.data
        
        if progress_callback:
            await progress_callback({
                "current_step": "refinement_complete",
                "progress_percent": 90,
                "message": f"全局精炼完成，应用了 {len(refinement.changes)} 处变更",
            })
        
        logger.info(f"[Refinement] Completed with {len(refinement.changes)} changes")
        return refinement
    
    def _parse_refinement_response(
        self,
        content: str,
        original_result: MergedOutlineResult,
    ) -> RefinementResult:
        """解析精炼响应"""
        try:
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            
            # 解析节点（保持位置锚点）
            nodes = []
            for node_data in data.get("outline_nodes", []):
                anchor_data = node_data.get("position_anchor", {})
                anchor = NodePositionAnchor(
                    chapter_index=anchor_data.get("chapter_index", 0),
                    in_chapter_order=anchor_data.get("in_chapter_order", 0),
                    char_offset=anchor_data.get("char_offset"),
                    chapter_title=anchor_data.get("chapter_title"),
                ) if anchor_data else None
                
                node = ExtractedOutlineNodeV2(
                    id=node_data.get("id", f"refined_{len(nodes)}"),
                    node_type=node_data.get("node_type", "scene"),
                    title=node_data.get("title", ""),
                    summary=node_data.get("summary", ""),
                    significance=node_data.get("significance", "normal"),
                    parent_id=node_data.get("parent_id"),
                    depth=node_data.get("depth", 0),
                    characters=node_data.get("characters", []),
                    evidence_list=node_data.get("evidence_list", []),
                    position_anchor=anchor,
                    batch_index=-1,  # 精炼节点标记为 -1
                )
                nodes.append(node)
            
            # 如果没有解析到节点，降级使用原始结果
            if not nodes:
                logger.warning("[Refinement] No nodes parsed from refinement response, using original")
                return RefinementResult(
                    refined_outline=original_result,
                    changes=[],
                    cross_chapter_threads=[],
                    metadata={"refinement_status": "empty_response"},
                )
            
            # 构建精炼结果
            refined_outline = MergedOutlineResult(
                nodes=nodes,
                turning_points=data.get("turning_points", original_result.turning_points),
                conflicts=original_result.conflicts,  # 保留原始冲突
                metadata={
                    **original_result.metadata,
                    "refined": True,
                    **data.get("metadata", {}),
                },
            )
            
            metadata = data.get("metadata", {})
            
            return RefinementResult(
                refined_outline=refined_outline,
                changes=metadata.get("refinement_changes", []),
                cross_chapter_threads=metadata.get("cross_chapter_threads", []),
                metadata={"refinement_status": "success"},
            )
        
        except Exception as e:
            logger.error(f"[Refinement] Failed to parse refinement response: {e}")
            return RefinementResult(
                refined_outline=original_result,
                changes=[],
                cross_chapter_threads=[],
                metadata={"refinement_status": "parse_error", "error": str(e)},
            )
    
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


# ============================================================================
# Entity Extraction from Batches
# ============================================================================

@dataclass
class CandidateEntity:
    """候选实体"""
    name: str
    aliases: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)
    description: str = ""
    mention_count: int = 0
    first_chapter: int = 0
    last_chapter: int = 0


class BatchEntityExtractor:
    """从批次结果中提取候选实体"""
    
    def extract(self, batch_results: List[BatchExtractionResult]) -> List[CandidateEntity]:
        """从批次结果中提取候选实体"""
        entity_map: Dict[str, CandidateEntity] = {}
        
        for batch in batch_results:
            for node in batch.nodes:
                for char_name in node.characters:
                    name = char_name.strip()
                    if not name:
                        continue
                    
                    if name not in entity_map:
                        entity_map[name] = CandidateEntity(
                            name=name,
                            first_chapter=batch.start_chapter_idx,
                        )
                    
                    entity = entity_map[name]
                    entity.mention_count += 1
                    entity.last_chapter = max(entity.last_chapter, batch.end_chapter_idx)
                    entity.types.append("character")
        
        # 去重类型
        for entity in entity_map.values():
            entity.types = list(set(entity.types))
        
        # 按提及次数排序
        sorted_entities = sorted(
            entity_map.values(),
            key=lambda e: e.mention_count,
            reverse=True,
        )
        
        return sorted_entities
    
    def to_dict_list(self, entities: List[CandidateEntity]) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [
            {
                "name": e.name,
                "aliases": e.aliases,
                "types": e.types,
                "description": e.description,
                "mention_count": e.mention_count,
                "first_chapter": e.first_chapter,
                "last_chapter": e.last_chapter,
            }
            for e in entities
        ]


# ============================================================================
# Main V3 Engine
# ============================================================================

class OutlineExtractionEngineV3:
    """大纲提取引擎 V3
    
    主入口，协调策略选择、批次处理、迭代精炼。
    """
    
    def __init__(
        self,
        db: Session,
        llm_client: Optional[LLMClient] = None,
    ):
        self.db = db
        self.llm_client = llm_client or self._create_default_llm_client()
        self.context_builder = SimpleContextBuilder()
        self.refinement_engine = IterativeRefinementEngine(llm_client=self.llm_client)
        self.entity_extractor = BatchEntityExtractor()
        self.merger = OutlineMerger()
        self.validator = OutlineOrderValidator()
    
    def _create_default_llm_client(self) -> LLMClient:
        config = LLMConfig.from_env(LLMProvider(DEFAULT_LLM_PROVIDER))
        return LLMClient(config)
    
    async def extract(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        strategy_override: Optional[str] = None,
    ) -> MergedOutlineResult:
        """执行 V3 大纲提取
        
        流程：
        1. 加载章节内容
        2. 选择策略
        3. Round 1: 粗纲提取（复用 V2 批次处理）
        4. Round 2: 全局精炼（如策略启用）
        5. 验证并返回
        """
        logger.info(f"[V3 Engine] Starting extraction for edition {edition_id}")
        
        # 1. 加载章节
        parser = TextRangeParser(self.db)
        content_result = parser.get_content(range_selection)
        
        chapters = [
            ChapterInfo(
                id=ch["id"],
                sort_index=ch["sort_index"],
                title=ch.get("title"),
                label=ch.get("label"),
                char_count=ch.get("char_count", 0),
                content=ch.get("content", ""),
            )
            for ch in content_result.chapters
        ]
        
        total_chapters = len(chapters)
        logger.info(f"[V3 Engine] Loaded {total_chapters} chapters")
        
        # 2. 选择策略
        strategy_config = StrategySelector.select(total_chapters, strategy_override)
        logger.info(f"[V3 Engine] Strategy: {strategy_config.strategy.value}")
        
        # 3. Round 1: 粗纲提取
        coarse_result = await self._round1_coarse_extraction(
            chapters=chapters,
            strategy_config=strategy_config,
            config=config,
            work_title=work_title,
            known_characters=known_characters,
            progress_callback=progress_callback,
        )
        
        if not coarse_result.nodes:
            logger.warning("[V3 Engine] Round 1 produced no nodes, returning empty result")
            return coarse_result
        
        # 4. 提取候选实体
        # Note: 这里需要从 batch_results 提取，但 _round1 返回的是 merged result
        # 为了简化，我们从 coarse_result 的节点中提取
        candidate_entities = self._extract_entities_from_result(coarse_result)
        
        # 5. Round 2: 全局精炼（如果策略启用）
        if strategy_config.enable_refinement:
            refinement_result = await self.refinement_engine.refine(
                coarse_result=coarse_result,
                work_title=work_title,
                total_chapters=total_chapters,
                candidate_entities=candidate_entities,
                progress_callback=progress_callback,
            )
            final_result = refinement_result.refined_outline
            
            # 记录精炼元数据
            final_result.metadata["refinement"] = {
                "changes_count": len(refinement_result.changes),
                "threads_count": len(refinement_result.cross_chapter_threads),
                "status": refinement_result.metadata.get("refinement_status", "unknown"),
            }
        else:
            final_result = coarse_result
            final_result.metadata["refinement"] = {"status": "skipped"}
        
        # 6. 最终验证
        validation = self.validator.validate(final_result)
        final_result.metadata["validation"] = validation
        
        if not validation["valid"]:
            logger.warning(f"[V3 Engine] Validation issues: {validation['issues']}")
        
        logger.info(
            f"[V3 Engine] Extraction complete: {len(final_result.nodes)} nodes, "
            f"{len(final_result.turning_points)} turning points"
        )
        
        return final_result
    
    async def _round1_coarse_extraction(
        self,
        chapters: List[ChapterInfo],
        strategy_config: StrategyConfig,
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> MergedOutlineResult:
        """Round 1: 粗纲提取"""
        
        # 直通模式：单次调用
        if strategy_config.strategy == ExtractionStrategy.DIRECT:
            return await self._direct_extract(
                chapters=chapters,
                config=config,
                work_title=work_title,
                known_characters=known_characters,
                progress_callback=progress_callback,
            )
        
        # 其他模式：批次并行
        batcher = OutlineExtractionBatcher(
            max_chapters_per_batch=strategy_config.max_chapters_per_batch,
            max_tokens_per_batch=strategy_config.max_tokens_per_batch,
            overlap_chapters=strategy_config.overlap_chapters,
        )
        batches = batcher.create_batches(chapters)
        
        logger.info(f"[V3 Engine] Round 1: {len(batches)} batches")
        
        # 并发处理批次
        batch_results = await self._process_batches_concurrent(
            batches=batches,
            chapters=chapters,
            config=config,
            work_title=work_title,
            known_characters=known_characters,
            progress_callback=progress_callback,
            concurrency=strategy_config.concurrency,
        )
        
        # 合并
        if progress_callback:
            await progress_callback({
                "current_step": "merging",
                "progress_percent": 55,
                "message": "正在合并批次结果...",
            })
        
        merged = self.merger.merge(batch_results)
        
        # 验证
        validation = self.validator.validate(merged)
        merged.metadata["round1_validation"] = validation
        
        return merged
    
    async def _direct_extract(
        self,
        chapters: List[ChapterInfo],
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
    ) -> MergedOutlineResult:
        """直通模式：单次 LLM 调用提取"""
        logger.info("[V3 Engine] Direct extraction mode")
        
        if progress_callback:
            await progress_callback({
                "current_step": "direct_extraction",
                "progress_percent": 30,
                "message": "正在直通提取...",
            })
        
        # 构建完整文本
        chapter_contents = self._format_chapter_contents(chapters)
        
        # 构建 Prompt（复用 V2 的 Prompt 模板风格）
        from sail_server.service.outline_extractor_v2 import OUTLINE_EXTRACTION_V2_PROMPT
        
        batch = ExtractionBatch(
            batch_index=0,
            start_chapter_idx=0,
            end_chapter_idx=len(chapters) - 1,
            chapter_ids=[ch.id for ch in chapters],
        )
        
        prompt = OUTLINE_EXTRACTION_V2_PROMPT
        prompt = prompt.replace("{{batch_context}}", batch.to_prompt_context())
        prompt = prompt.replace("{{chapter_contents}}", chapter_contents)
        prompt = prompt.replace("{{batch_index}}", "0")
        prompt = prompt.replace("{{start_chapter_idx}}", "0")
        prompt = prompt.replace("{{end_chapter_idx}}", str(len(chapters) - 1))
        prompt = prompt.replace("{{work_title}}", work_title or "未命名作品")
        prompt = prompt.replace("{{granularity}}", config.granularity)
        prompt = prompt.replace("{{outline_type}}", config.outline_type)
        
        # 调用 LLM
        retry_handler = LLMRetryHandler(
            RetryConfig(max_retries=3, base_delay=2.0, max_delay=120.0, strategy=RetryStrategy.EXPONENTIAL)
        )
        
        async def operation():
            response = await self.llm_client.complete(
                prompt=prompt,
                system="你是一个专业的小说结构分析师，擅长从文本中提取情节大纲。",
            )
            return self._parse_direct_response(response.content, batch)
        
        retry_result = await retry_handler.execute(operation)
        
        if not retry_result.success:
            logger.error(f"[V3 Engine] Direct extraction failed: {retry_result.error}")
            return MergedOutlineResult()
        
        batch_result = retry_result.data
        
        # 合并单批次（复用 merger）
        merged = self.merger.merge([batch_result])
        
        if progress_callback:
            await progress_callback({
                "current_step": "direct_complete",
                "progress_percent": 80,
                "message": "直通提取完成",
            })
        
        return merged
    
    async def _process_batches_concurrent(
        self,
        batches: List[ExtractionBatch],
        chapters: List[ChapterInfo],
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
        concurrency: int = 5,
    ) -> List[BatchExtractionResult]:
        """并发处理批次"""
        semaphore = asyncio.Semaphore(concurrency)
        results: List[Optional[BatchExtractionResult]] = [None] * len(batches)
        completed_count = 0
        
        async def process_one(idx: int, batch: ExtractionBatch):
            nonlocal completed_count
            async with semaphore:
                try:
                    result = await self._process_single_batch(
                        batch=batch,
                        chapters=chapters,
                        config=config,
                        work_title=work_title,
                        known_characters=known_characters,
                    )
                    results[idx] = result
                    completed_count += 1
                    
                    if progress_callback:
                        await progress_callback({
                            "current_step": f"batch_{idx + 1}",
                            "progress_percent": int((completed_count / len(batches)) * 50),
                            "message": f"已完成 {completed_count}/{len(batches)} 批次",
                            "batch_index": idx,
                            "total_batches": len(batches),
                        })
                    
                except Exception as e:
                    logger.error(f"[V3 Engine] Batch {idx} failed: {e}")
                    results[idx] = BatchExtractionResult(
                        batch_index=batch.batch_index,
                        start_chapter_idx=batch.start_chapter_idx,
                        end_chapter_idx=batch.end_chapter_idx,
                        nodes=[],
                        turning_points=[],
                        metadata={"error": str(e)},
                    )
        
        await asyncio.gather(*[
            process_one(i, batch) for i, batch in enumerate(batches)
        ])
        
        return [r for r in results if r is not None]
    
    async def _process_single_batch(
        self,
        batch: ExtractionBatch,
        chapters: List[ChapterInfo],
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
    ) -> BatchExtractionResult:
        """处理单个批次"""
        from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
        
        # 复用 V2 的单批次处理逻辑
        v2_extractor = OutlineExtractorV2(self.db, llm_client=self.llm_client)
        
        # 获取批次章节
        batch_chapters = [
            ch for ch in chapters
            if batch.start_chapter_idx <= ch.sort_index <= batch.end_chapter_idx
        ]
        
        # 构建上下文
        chapter_contents = self._format_chapter_contents(batch_chapters)
        
        # 简化上下文
        context = self.context_builder.build(
            chapters_text=chapter_contents,
            known_characters=None,  # TODO: 从数据库加载已知角色
            prev_batch_summary=None,
            work_title=work_title,
            batch_info=batch.to_prompt_context(),
        )
        
        # 使用 V2 的 Prompt 模板 + 简化上下文
        from sail_server.service.outline_extractor_v2 import OUTLINE_EXTRACTION_V2_PROMPT
        
        prompt = OUTLINE_EXTRACTION_V2_PROMPT
        prompt = prompt.replace("{{batch_context}}", batch.to_prompt_context())
        prompt = prompt.replace("{{chapter_contents}}", chapter_contents)
        prompt = prompt.replace("{{batch_index}}", str(batch.batch_index))
        prompt = prompt.replace("{{start_chapter_idx}}", str(batch.start_chapter_idx))
        prompt = prompt.replace("{{end_chapter_idx}}", str(batch.end_chapter_idx))
        prompt = prompt.replace("{{work_title}}", work_title or "未命名作品")
        prompt = prompt.replace("{{granularity}}", config.granularity)
        prompt = prompt.replace("{{outline_type}}", config.outline_type)
        
        # 调用 LLM（通过 V2 的 retry handler）
        retry_handler = LLMRetryHandler(
            RetryConfig(max_retries=3, base_delay=2.0, max_delay=120.0, strategy=RetryStrategy.EXPONENTIAL)
        )
        
        async def operation():
            response = await self.llm_client.complete(
                prompt=prompt,
                system="你是一个专业的小说结构分析师，擅长从文本中提取情节大纲。",
            )
            return v2_extractor._parse_response(response.content, batch)
        
        retry_result = await retry_handler.execute(operation)
        
        if not retry_result.success:
            logger.error(f"[V3 Engine] Batch {batch.batch_index} failed: {retry_result.error}")
            return BatchExtractionResult(
                batch_index=batch.batch_index,
                start_chapter_idx=batch.start_chapter_idx,
                end_chapter_idx=batch.end_chapter_idx,
                nodes=[],
                turning_points=[],
                metadata={"error": str(retry_result.error)},
            )
        
        return retry_result.data
    
    def _format_chapter_contents(self, chapters: List[ChapterInfo]) -> str:
        """格式化章节内容"""
        parts = []
        for ch in chapters:
            header = f"## 第{ch.sort_index + 1}章"
            if ch.title:
                header += f" {ch.title}"
            parts.append(f"{header}\n\n{ch.content}")
        return "\n\n".join(parts)
    
    def _extract_entities_from_result(
        self, 
        result: MergedOutlineResult,
    ) -> List[Dict[str, Any]]:
        """从合并结果中提取候选实体"""
        entity_map: Dict[str, Dict[str, Any]] = {}
        
        for node in result.nodes:
            for char_name in node.characters:
                name = char_name.strip()
                if not name:
                    continue
                
                if name not in entity_map:
                    entity_map[name] = {
                        "name": name,
                        "aliases": [],
                        "types": ["character"],
                        "mention_count": 0,
                    }
                
                entity_map[name]["mention_count"] += 1
        
        sorted_entities = sorted(
            entity_map.values(),
            key=lambda e: e["mention_count"],
            reverse=True,
        )
        
        return sorted_entities
    
    def _parse_direct_response(self, content: str, batch: ExtractionBatch) -> BatchExtractionResult:
        """解析直通模式响应"""
        from sail_server.service.outline_extractor_v2 import OutlineExtractorV2
        v2 = OutlineExtractorV2(self.db, llm_client=self.llm_client)
        return v2._parse_response(content, batch)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "ExtractionStrategy",
    "StrategyConfig",
    "StrategySelector",
    "ContextBudget",
    "SimpleContextBuilder",
    "GlobalRefinementPrompt",
    "RefinementResult",
    "IterativeRefinementEngine",
    "CandidateEntity",
    "BatchEntityExtractor",
    "OutlineExtractionEngineV3",
]
