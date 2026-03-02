# -*- coding: utf-8 -*-
# @file outline_extractor_v2.py
# @brief Outline Extractor V2 - Integrated Service
# @author sailing-innocent
# @date 2025-03-02
# @version 1.0
# ---------------------------------

"""
大纲提取服务 V2

集成位置锚点机制的增强版大纲提取服务，
支持可靠的拆分-合并处理，保证节点顺序与原文本一致。
"""

import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from sail_server.utils.llm.client import LLMClient, LLMConfig, LLMProvider
from sail_server.utils.llm.prompts import PromptTemplateManager
from sail_server.utils.llm.retry_handler import LLMRetryHandler, RetryConfig, RetryStrategy
from sail_server.application.dto.analysis import TextRangeSelection, OutlineExtractionConfig

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
from sail_server.service.range_selector import TextRangeParser

logger = logging.getLogger(__name__)


# ============================================================================
# Enhanced Prompt Template for V2
# ============================================================================

OUTLINE_EXTRACTION_V2_PROMPT = """
## 任务：从小说文本中提取结构化大纲

### 批次上下文
{{batch_context}}

### 待分析文本
```
{{chapter_contents}}
```

### 分析参数
- 作品名称：{{work_title}}
- 分析粒度：{{granularity}}
- 大纲类型：{{outline_type}}

### 输出格式

请输出以下 JSON 结构：

```json
{
  "outline_nodes": [
    {
      "id": "batch{{batch_index}}_node_1",
      "node_type": "act|arc|scene|beat",
      "title": "节点标题（简洁概括，10-30字）",
      "summary": "详细描述（50-150字）",
      "significance": "critical|major|normal|minor",
      "parent_id": null,
      "depth": 0,
      "position_anchor": {
        "chapter_index": 5,
        "in_chapter_order": 0,
        "char_offset": 1500,
        "chapter_title": "第五章 初遇"
      },
      "characters": ["人物1"],
      "evidence_list": [
        {
          "text": "关键原文引用（50-200字）",
          "chapter_title": "章节标题",
          "start_fragment": "开始片段（20-30字）",
          "end_fragment": "结束片段（20-30字）"
        }
      ]
    }
  ],
  "turning_points": [
    {
      "node_id": "batch{{batch_index}}_node_1",
      "turning_point_type": "inciting_incident|rising_action|climax|falling_action|resolution",
      "description": "转折点描述"
    }
  ],
  "metadata": {
    "total_nodes": 5,
    "max_depth": 2,
    "chapter_coverage": "第1章-第3章"
  }
}
```

### 位置锚点填写规则（重要）

**position_anchor** 字段用于确定节点在原文本中的位置，是保证大纲顺序正确的关键：

1. **chapter_index** (必填):
   - 使用节点首次出现的章节的**全局索引**（从0开始）
   - 当前批次处理的章节全局索引范围是 {{start_chapter_idx}} 到 {{end_chapter_idx}}
   - 例如：如果节点首次出现在批次中的第2章，且批次起始索引是10，则填写11

2. **in_chapter_order** (必填):
   - 同一章节内多个节点的出现顺序（从0开始）
   - 按时间线顺序递增

3. **char_offset** (可选但推荐):
   - 节点首次出现的证据在章节中的字符偏移量
   - 用于更精确的定位

4. **chapter_title** (可选):
   - 章节标题，用于验证

### 节点类型说明
- **act**：幕（大的故事阶段）
- **arc**：情节弧（完整的情节线）
- **scene**：场景（具体的场景）
- **beat**：节拍（最小的情节单位）

### 注意事项
1. 确保节点之间有正确的 parent_id 关系
2. 根节点的 parent_id 为 null
3. 证据的文本必须准确对应原文内容
4. 位置锚点决定节点在最终大纲中的顺序
"""


# ============================================================================
# V2 Extractor Service
# ============================================================================

class OutlineExtractorV2:
    """
    大纲提取服务 V2
    
    特性：
    1. 基于位置锚点的可靠排序
    2. 支持长文本拆分并行处理
    3. 智能合并保证节点顺序
    """
    
    def __init__(
        self,
        db: Session,
        llm_client: Optional[LLMClient] = None,
        prompt_manager: Optional[PromptTemplateManager] = None,
        retry_handler: Optional[LLMRetryHandler] = None,
    ):
        self.db = db
        self.llm_client = llm_client or self._create_default_llm_client()
        self.prompt_manager = prompt_manager or PromptTemplateManager()
        self.retry_handler = retry_handler or self._create_default_retry_handler()
        self.batcher = OutlineExtractionBatcher()
        self.merger = OutlineMerger()
        self.validator = OutlineOrderValidator()
    
    def _create_default_llm_client(self) -> LLMClient:
        """创建默认 LLM 客户端"""
        from sail_server.utils.llm.available_providers import DEFAULT_LLM_PROVIDER
        config = LLMConfig.from_env(LLMProvider(DEFAULT_LLM_PROVIDER))
        return LLMClient(config)
    
    def _create_default_retry_handler(self) -> LLMRetryHandler:
        """创建默认重试处理器"""
        return LLMRetryHandler(
            RetryConfig(
                max_retries=3,
                base_delay=2.0,
                max_delay=120.0,
                strategy=RetryStrategy.EXPONENTIAL,
                jitter=True,
            )
        )
    
    async def extract(
        self,
        edition_id: int,
        range_selection: TextRangeSelection,
        config: OutlineExtractionConfig,
        work_title: str = "",
        known_characters: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
    ) -> MergedOutlineResult:
        """
        执行大纲提取（V2）
        
        流程：
        1. 获取文本内容
        2. 划分批次
        3. 并行/串行处理各批次
        4. 合并结果
        5. 验证顺序
        """
        logger.info(f"[V2 Extractor] Starting extraction for edition {edition_id}")
        
        # 1. 获取文本内容
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
        
        logger.info(f"[V2 Extractor] Loaded {len(chapters)} chapters")
        
        # 2. 划分批次
        batches = self.batcher.create_batches(chapters)
        
        if len(batches) == 1:
            # 单批次，直接处理
            logger.info("[V2 Extractor] Single batch, processing directly")
            result = await self._process_batch(
                batch=batches[0],
                chapters=chapters,
                config=config,
                work_title=work_title,
                known_characters=known_characters,
            )
            # 转换为 MergedOutlineResult
            return MergedOutlineResult(
                nodes=result.nodes,
                turning_points=result.turning_points,
                metadata=result.metadata,
            )
        else:
            # 多批次，逐个处理（可改为并行）
            logger.info(f"[V2 Extractor] Processing {len(batches)} batches")
            batch_results = []
            
            for i, batch in enumerate(batches):
                if progress_callback:
                    await progress_callback({
                        "current_step": f"batch_{i+1}",
                        "progress_percent": int((i / len(batches)) * 100),
                        "message": f"正在处理第 {i+1}/{len(batches)} 批次",
                    })
                
                result = await self._process_batch(
                    batch=batch,
                    chapters=chapters,
                    config=config,
                    work_title=work_title,
                    known_characters=known_characters,
                )
                batch_results.append(result)
            
            # 4. 合并结果
            if progress_callback:
                await progress_callback({
                    "current_step": "merging",
                    "progress_percent": 95,
                    "message": "正在合并分析结果...",
                })
            
            merged = self.merger.merge(batch_results)
            
            # 5. 验证
            validation = self.validator.validate(merged)
            if not validation["valid"]:
                logger.warning(f"[V2 Extractor] Validation issues: {validation['issues']}")
            
            return merged
    
    async def _process_batch(
        self,
        batch: ExtractionBatch,
        chapters: List[ChapterInfo],
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
    ) -> BatchExtractionResult:
        """处理单个批次"""
        
        # 获取批次对应的章节内容
        batch_chapters = [
            ch for ch in chapters
            if batch.start_chapter_idx <= ch.sort_index <= batch.end_chapter_idx
        ]
        
        # 构建批次内容
        chapter_contents = self._format_chapter_contents(batch_chapters)
        
        # 构建提示词
        prompt = self._build_prompt(
            batch=batch,
            chapter_contents=chapter_contents,
            config=config,
            work_title=work_title,
            known_characters=known_characters,
        )
        
        # 调用 LLM
        logger.info(f"[V2 Extractor] Calling LLM for batch {batch.batch_index}")
        
        async def operation():
            response = await self.llm_client.complete(
                prompt=prompt,
                system="你是一个专业的小说结构分析师，擅长从文本中提取情节大纲。",
            )
            return self._parse_response(response.content, batch)
        
        retry_result = await self.retry_handler.execute(operation)
        
        if not retry_result.success:
            logger.error(f"[V2 Extractor] Batch {batch.batch_index} failed: {retry_result.error}")
            # 返回空结果
            return BatchExtractionResult(
                batch_index=batch.batch_index,
                start_chapter_idx=batch.start_chapter_idx,
                end_chapter_idx=batch.end_chapter_idx,
                nodes=[],
                turning_points=[],
                metadata={"error": str(retry_result.error)},
            )
        
        return retry_result.data
    
    def _build_prompt(
        self,
        batch: ExtractionBatch,
        chapter_contents: str,
        config: OutlineExtractionConfig,
        work_title: str,
        known_characters: Optional[List[str]],
    ) -> str:
        """构建提示词"""
        batch_context = batch.to_prompt_context()
        
        prompt = OUTLINE_EXTRACTION_V2_PROMPT
        prompt = prompt.replace("{{batch_context}}", batch_context)
        prompt = prompt.replace("{{chapter_contents}}", chapter_contents)
        prompt = prompt.replace("{{batch_index}}", str(batch.batch_index))
        prompt = prompt.replace("{{start_chapter_idx}}", str(batch.start_chapter_idx))
        prompt = prompt.replace("{{end_chapter_idx}}", str(batch.end_chapter_idx))
        prompt = prompt.replace("{{work_title}}", work_title or "未命名作品")
        prompt = prompt.replace("{{granularity}}", config.granularity)
        prompt = prompt.replace("{{outline_type}}", config.outline_type)
        
        return prompt
    
    def _format_chapter_contents(self, chapters: List[ChapterInfo]) -> str:
        """格式化章节内容"""
        parts = []
        for ch in chapters:
            header = f"## 第{ch.sort_index + 1}章"
            if ch.title:
                header += f" {ch.title}"
            parts.append(f"{header}\n\n{ch.content}")
        return "\n\n".join(parts)
    
    def _parse_response(
        self,
        content: str,
        batch: ExtractionBatch
    ) -> BatchExtractionResult:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            json_str = self._extract_json(content)
            data = json.loads(json_str)
            
            # 解析节点
            nodes = []
            for node_data in data.get("outline_nodes", []):
                # 解析位置锚点
                anchor_data = node_data.get("position_anchor", {})
                
                # 如果没有位置锚点，使用批次信息推断
                if not anchor_data:
                    anchor_data = {
                        "chapter_index": batch.start_chapter_idx,
                        "in_chapter_order": 0,
                        "chapter_title": None,
                    }
                
                # 验证 chapter_index 范围
                chapter_index = anchor_data.get("chapter_index", batch.start_chapter_idx)
                if chapter_index < batch.start_chapter_idx or chapter_index > batch.end_chapter_idx:
                    logger.warning(
                        f"Node chapter_index {chapter_index} out of batch range "
                        f"[{batch.start_chapter_idx}, {batch.end_chapter_idx}], using batch start"
                    )
                    chapter_index = batch.start_chapter_idx
                
                anchor = NodePositionAnchor(
                    chapter_index=chapter_index,
                    in_chapter_order=anchor_data.get("in_chapter_order", 0),
                    char_offset=anchor_data.get("char_offset"),
                    chapter_title=anchor_data.get("chapter_title"),
                )
                
                node = ExtractedOutlineNodeV2(
                    id=node_data.get("id", f"batch{batch.batch_index}_node_{len(nodes)}"),
                    node_type=node_data.get("node_type", "scene"),
                    title=node_data.get("title", ""),
                    summary=node_data.get("summary", ""),
                    significance=node_data.get("significance", "normal"),
                    parent_id=node_data.get("parent_id"),
                    depth=node_data.get("depth", 0),
                    characters=node_data.get("characters", []),
                    evidence_list=node_data.get("evidence_list", []),
                    position_anchor=anchor,
                    batch_index=batch.batch_index,
                )
                nodes.append(node)
            
            # 解析转折点
            turning_points = data.get("turning_points", [])
            
            return BatchExtractionResult(
                batch_index=batch.batch_index,
                start_chapter_idx=batch.start_chapter_idx,
                end_chapter_idx=batch.end_chapter_idx,
                nodes=nodes,
                turning_points=turning_points,
                metadata=data.get("metadata", {}),
            )
            
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
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


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "OutlineExtractorV2",
    "OUTLINE_EXTRACTION_V2_PROMPT",
]
