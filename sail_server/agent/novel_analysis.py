# -*- coding: utf-8 -*-
# @file novel_analysis.py
# @brief Novel Analysis Agent
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------
#
# 小说分析 Agent
# 整合大纲分析、人物分析、设定分析等功能

import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .base import (
    BaseAgent,
    AgentContext,
    AgentExecutionResult,
    CostEstimate,
    ValidationResult,
    ProgressCallback,
    AgentInfo,
    ProgressUpdate,
)
from sail_server.infrastructure.orm.unified_agent import UnifiedAgentTask
from sail_server.application.dto.unified_agent import (
    TaskType,
    TaskSubType,
    StepType,
)
from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)
from sail_server.infrastructure.orm.text import DocumentNode, Edition, Work
from sail_server.utils.llm.gateway import LLMExecutionConfig, TokenBudget

logger = logging.getLogger(__name__)


# ============================================================================
# 配置常量
# ============================================================================

MAX_CHUNK_TOKENS = 8000  # 每个分块的最大 token 数
DEFAULT_TEMPERATURE = 0.3  # 默认温度


# 任务类型到提示词模板的映射
TASK_TYPE_TEMPLATE_MAP = {
    TaskSubType.OUTLINE_EXTRACTION: "outline_extraction_v1",
    TaskSubType.CHARACTER_DETECTION: "character_detection_v1",
    TaskSubType.SETTING_EXTRACTION: "setting_extraction_v1",
}


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class ChapterChunk:
    """章节分块"""
    index: int
    node_ids: List[int]
    chapter_range: str
    content: str
    token_estimate: int


@dataclass
class AnalysisResult:
    """分析结果项"""
    result_type: str
    data: Dict[str, Any]
    confidence: float
    chunk_index: int
    node_ids: List[int]


# ============================================================================
# NovelAnalysisAgent
# ============================================================================

class NovelAnalysisAgent(BaseAgent):
    """
    小说分析 Agent
    
    支持以下分析类型：
    - outline_extraction: 大纲提取
    - character_detection: 人物检测
    - setting_extraction: 设定提取
    - relation_analysis: 关系分析
    - plot_analysis: 情节分析
    """
    
    @property
    def agent_type(self) -> str:
        return "novel_analysis"
    
    @property
    def agent_info(self) -> AgentInfo:
        return AgentInfo(
            agent_type=self.agent_type,
            name="小说分析 Agent",
            description="分析小说内容，提取大纲、人物、设定等信息",
            version="1.0",
            supported_task_types=[
                TaskType.NOVEL_ANALYSIS,
                TaskSubType.OUTLINE_EXTRACTION,
                TaskSubType.CHARACTER_DETECTION,
                TaskSubType.SETTING_EXTRACTION,
                TaskSubType.RELATION_ANALYSIS,
                TaskSubType.PLOT_ANALYSIS,
            ],
            capabilities=[
                "outline_extraction",
                "character_detection",
                "setting_extraction",
                "chapter_chunking",
                "result_parsing",
            ],
        )
    
    def validate_task(self, task: UnifiedAgentTask) -> ValidationResult:
        """验证任务配置"""
        result = ValidationResult(valid=True)
        
        # 检查必需的配置
        config = task.config or {}
        
        # 检查 edition_id
        if not task.edition_id:
            result.add_error("edition_id is required for novel analysis")
        
        # 检查 sub_type
        valid_sub_types = [
            TaskSubType.OUTLINE_EXTRACTION,
            TaskSubType.CHARACTER_DETECTION,
            TaskSubType.SETTING_EXTRACTION,
            TaskSubType.RELATION_ANALYSIS,
            TaskSubType.PLOT_ANALYSIS,
        ]
        
        sub_type = task.sub_type or config.get("sub_type")
        if sub_type and sub_type not in valid_sub_types:
            result.add_error(f"Invalid sub_type: {sub_type}. Must be one of {valid_sub_types}")
        
        # 检查 target_node_ids
        target_node_ids = task.target_node_ids or config.get("target_node_ids", [])
        if not target_node_ids and not task.edition_id:
            result.add_warning("No target_node_ids specified, will analyze entire edition")
        
        return result
    
    def estimate_cost(self, task: UnifiedAgentTask) -> CostEstimate:
        """预估任务成本"""
        config = task.config or {}
        
        # 获取目标章节
        # 这里简化处理，实际应该查询数据库获取准确的 token 数
        estimated_chunks = config.get("estimated_chunks", 5)
        tokens_per_chunk = config.get("tokens_per_chunk", 6000)
        
        total_input_tokens = estimated_chunks * tokens_per_chunk
        # 假设输出是输入的 30%
        estimated_output_tokens = int(total_input_tokens * 0.3)
        
        # 获取模型定价
        model = task.llm_model or config.get("llm_model", "gpt-4o-mini")
        
        from sail_server.utils.llm.pricing import get_pricing
        pricing = get_pricing(model)
        
        input_cost = pricing.calculate_cost(total_input_tokens, 0)
        output_cost = pricing.calculate_cost(0, estimated_output_tokens)
        total_cost = input_cost + output_cost
        
        return CostEstimate(
            estimated_tokens=total_input_tokens + estimated_output_tokens,
            estimated_cost=total_cost,
            confidence=0.7,
            breakdown={
                "input_tokens": total_input_tokens,
                "output_tokens": estimated_output_tokens,
                "chunks": estimated_chunks,
                "model": model,
                "input_cost": input_cost,
                "output_cost": output_cost,
            }
        )
    
    async def execute(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        callback: Optional[ProgressCallback] = None
    ) -> AgentExecutionResult:
        """执行小说分析任务"""
        start_time = datetime.utcnow()
        
        try:
            # 1. 验证任务
            validation = self.validate_task(task)
            if not validation.valid:
                return AgentExecutionResult(
                    success=False,
                    error_message=f"Task validation failed: {validation.errors}",
                    error_code="VALIDATION_ERROR",
                )
            
            # 2. 准备章节分块
            self._notify_progress(callback, 5, "preparing", "Preparing chapter chunks...")
            
            chunks = await self._prepare_chunks(task, context)
            if not chunks:
                return AgentExecutionResult(
                    success=False,
                    error_message="No chapters to analyze",
                    error_code="NO_CONTENT",
                )
            
            self._notify_progress(
                callback, 10, "prepared",
                f"Prepared {len(chunks)} chunks",
                chunks_count=len(chunks)
            )
            
            # 3. 获取提示词模板
            sub_type = task.sub_type or task.config.get("sub_type", TaskSubType.OUTLINE_EXTRACTION)
            template_id = task.prompt_template_id or TASK_TYPE_TEMPLATE_MAP.get(sub_type)
            
            if not template_id:
                return AgentExecutionResult(
                    success=False,
                    error_message=f"No template found for sub_type: {sub_type}",
                    error_code="TEMPLATE_NOT_FOUND",
                )
            
            # 4. 执行分析
            all_results = []
            total_tokens = 0
            total_cost = 0.0
            
            for i, chunk in enumerate(chunks):
                progress = 10 + int((i / len(chunks)) * 80)
                self._notify_progress(
                    callback, progress, "analyzing",
                    f"Analyzing chunk {i+1}/{len(chunks)}: {chunk.chapter_range}",
                    current_chunk=i+1,
                    total_chunks=len(chunks),
                    chapter_range=chunk.chapter_range,
                )
                
                # 创建步骤记录
                await self._create_step(
                    task, context,
                    step_type=StepType.ACTION,
                    title=f"Analyze Chunk {i+1}",
                    content=f"Analyzing {chunk.chapter_range}",
                )
                
                # 处理分块
                chunk_results = await self._process_chunk(
                    task, context, chunk, template_id
                )
                
                all_results.extend(chunk_results)
                
                # 累加成本
                for result in chunk_results:
                    total_tokens += result.data.get("tokens", 0)
                    total_cost += result.data.get("cost", 0.0)
            
            # 5. 保存结果
            self._notify_progress(callback, 95, "saving", "Saving results...")
            
            result_data = self._compile_results(all_results, sub_type)
            
            # 更新任务结果
            await self._update_task_result(task, context, result_data)
            
            # 6. 完成
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._notify_progress(callback, 100, "completed", "Analysis completed")
            
            return AgentExecutionResult(
                success=True,
                result_data=result_data,
                execution_time_seconds=execution_time,
                total_tokens=total_tokens,
                total_cost=total_cost,
                steps_completed=len(chunks),
            )
        
        except Exception as e:
            logger.error(f"Novel analysis failed: {e}", exc_info=True)
            
            return AgentExecutionResult(
                success=False,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
                execution_time_seconds=(datetime.utcnow() - start_time).total_seconds(),
            )
    
    async def _prepare_chunks(
        self,
        task: UnifiedAgentTask,
        context: AgentContext
    ) -> List[ChapterChunk]:
        """准备章节分块"""
        db = context.db_session
        
        # 获取目标章节
        if task.target_node_ids:
            nodes = db.query(DocumentNode).filter(
                DocumentNode.id.in_(task.target_node_ids)
            ).order_by(DocumentNode.sort_index).all()
        elif task.edition_id:
            nodes = db.query(DocumentNode).filter(
                DocumentNode.edition_id == task.edition_id,
                DocumentNode.node_type == 'chapter'
            ).order_by(DocumentNode.sort_index).all()
        else:
            return []
        
        if not nodes:
            return []
        
        # 分块处理
        chunks = []
        current_chunk_nodes = []
        current_chunk_content = ""
        current_chunk_tokens = 0
        chunk_index = 0
        
        # 估算 token 数（简化版）
        def estimate_tokens(text: str) -> int:
            # 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4)
        
        for node in nodes:
            node_content = node.raw_text or ""
            node_tokens = estimate_tokens(node_content)
            
            # 如果单个章节就超过限制，单独作为一块
            if node_tokens > MAX_CHUNK_TOKENS:
                # 先保存当前块
                if current_chunk_nodes:
                    chunks.append(self._create_chunk(
                        chunk_index, current_chunk_nodes, current_chunk_content, current_chunk_tokens
                    ))
                    chunk_index += 1
                    current_chunk_nodes = []
                    current_chunk_content = ""
                    current_chunk_tokens = 0
                
                # 大章节单独成块
                chunks.append(ChapterChunk(
                    index=chunk_index,
                    node_ids=[node.id],
                    chapter_range=node.title or f"Chapter {node.id}",
                    content=node_content,
                    token_estimate=node_tokens,
                ))
                chunk_index += 1
                continue
            
            # 检查是否需要开始新块
            if current_chunk_tokens + node_tokens > MAX_CHUNK_TOKENS:
                if current_chunk_nodes:
                    chunks.append(self._create_chunk(
                        chunk_index, current_chunk_nodes, current_chunk_content, current_chunk_tokens
                    ))
                    chunk_index += 1
                current_chunk_nodes = []
                current_chunk_content = ""
                current_chunk_tokens = 0
            
            # 添加到当前块
            current_chunk_nodes.append(node)
            current_chunk_content += f"\n\n### {node.title or 'Chapter'}\n\n{node_content}"
            current_chunk_tokens += node_tokens
        
        # 保存最后一块
        if current_chunk_nodes:
            chunks.append(self._create_chunk(
                chunk_index, current_chunk_nodes, current_chunk_content, current_chunk_tokens
            ))
        
        return chunks
    
    def _create_chunk(
        self,
        index: int,
        nodes: List[DocumentNode],
        content: str,
        tokens: int
    ) -> ChapterChunk:
        """创建分块"""
        if len(nodes) == 1:
            chapter_range = nodes[0].title or f"Chapter {nodes[0].id}"
        else:
            chapter_range = f"{nodes[0].title or 'Chapter'} - {nodes[-1].title or 'Chapter'}"
        
        return ChapterChunk(
            index=index,
            node_ids=[n.id for n in nodes],
            chapter_range=chapter_range,
            content=content,
            token_estimate=tokens,
        )
    
    async def _process_chunk(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        chunk: ChapterChunk,
        template_id: str
    ) -> List[AnalysisResult]:
        """处理单个分块"""
        db = context.db_session
        
        # 获取作品信息
        edition = db.query(Edition).filter(Edition.id == task.edition_id).first()
        work_title = "Unknown"
        if edition:
            work = db.query(Work).filter(Work.id == edition.work_id).first()
            if work:
                work_title = work.title
        
        # 渲染提示词模板
        from sail_server.utils.llm import get_template_manager
        template_manager = get_template_manager()
        
        config = task.config or {}
        variables = {
            "work_title": work_title,
            "chapter_range": chunk.chapter_range,
            "chapter_contents": chunk.content,
            "known_characters": config.get("known_characters", ""),
            "setting_types": config.get("setting_types", "item, location, organization"),
        }
        
        try:
            rendered = template_manager.render(template_id, variables)
        except Exception as e:
            logger.error(f"Failed to render template {template_id}: {e}")
            return [AnalysisResult(
                result_type="error",
                data={"error": str(e), "chunk_index": chunk.index},
                confidence=0,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            )]
        
        # 调用 LLM
        llm_config = LLMExecutionConfig(
            provider=task.llm_provider or config.get("llm_provider", "openai"),
            model=task.llm_model or config.get("llm_model", "gpt-4o-mini"),
            temperature=config.get("temperature", DEFAULT_TEMPERATURE),
            max_tokens=config.get("max_tokens", 4000),
            system_prompt=rendered.system_prompt,
        )
        
        try:
            response = await context.llm_gateway.execute(
                rendered.user_prompt,
                llm_config,
                budget=TokenBudget(
                    max_tokens=config.get("max_tokens_per_chunk", 10000),
                    max_cost=config.get("max_cost_per_chunk", 0.5),
                )
            )
            
            # 解析结果
            results = self._parse_llm_response(
                response.content,
                task.sub_type or config.get("sub_type", TaskSubType.OUTLINE_EXTRACTION),
                chunk
            )
            
            # 添加 token 和成本信息
            for result in results:
                result.data["tokens"] = response.total_tokens
                result.data["cost"] = response.cost
            
            return results
        
        except Exception as e:
            logger.error(f"LLM call failed for chunk {chunk.index}: {e}")
            return [AnalysisResult(
                result_type="error",
                data={
                    "error": str(e),
                    "chunk_index": chunk.index,
                    "chunk_range": chunk.chapter_range,
                },
                confidence=0,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            )]
    
    def _parse_llm_response(
        self,
        content: str,
        task_type: str,
        chunk: ChapterChunk
    ) -> List[AnalysisResult]:
        """解析 LLM 响应"""
        results = []
        
        # 清理内容
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # 尝试解析 JSON
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 尝试修复不完整的 JSON
            parsed = self._fix_json(content)
        
        if parsed is None:
            return [AnalysisResult(
                result_type="parse_error",
                data={"raw_content": content[:500]},
                confidence=0,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            )]
        
        # 根据任务类型解析
        if task_type == TaskSubType.OUTLINE_EXTRACTION:
            results = self._parse_outline(parsed, chunk)
        elif task_type == TaskSubType.CHARACTER_DETECTION:
            results = self._parse_characters(parsed, chunk)
        elif task_type == TaskSubType.SETTING_EXTRACTION:
            results = self._parse_settings(parsed, chunk)
        else:
            # 通用解析
            results = [AnalysisResult(
                result_type="raw",
                data=parsed,
                confidence=0.5,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            )]
        
        return results
    
    def _fix_json(self, content: str) -> Optional[Dict[str, Any]]:
        """尝试修复不完整的 JSON"""
        # 简单修复：补全括号
        braces = content.count('{') - content.count('}')
        brackets = content.count('[') - content.count(']')
        
        fixed = content
        if braces > 0:
            fixed += '}' * braces
        if brackets > 0:
            fixed += ']' * brackets
        
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None
    
    def _parse_outline(
        self,
        parsed: Dict[str, Any],
        chunk: ChapterChunk
    ) -> List[AnalysisResult]:
        """解析大纲结果"""
        results = []
        
        plot_points = parsed.get("plot_points", [])
        for point in plot_points:
            results.append(AnalysisResult(
                result_type="outline_node",
                data={
                    "title": point.get("title", ""),
                    "node_type": point.get("type", "scene"),
                    "summary": point.get("summary", ""),
                    "significance": point.get("importance", "normal"),
                    "characters": point.get("characters", []),
                    "evidence": point.get("evidence", ""),
                },
                confidence=0.8,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            ))
        
        # 添加总结
        if parsed.get("overall_summary"):
            results.append(AnalysisResult(
                result_type="chunk_summary",
                data={"summary": parsed["overall_summary"]},
                confidence=0.9,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            ))
        
        return results
    
    def _parse_characters(
        self,
        parsed: Dict[str, Any],
        chunk: ChapterChunk
    ) -> List[AnalysisResult]:
        """解析人物结果"""
        results = []
        
        characters = parsed.get("characters", [])
        for char in characters:
            results.append(AnalysisResult(
                result_type="character",
                data={
                    "canonical_name": char.get("canonical_name", ""),
                    "aliases": char.get("aliases", []),
                    "role_type": char.get("role_type", "supporting"),
                    "description": char.get("description", ""),
                    "first_mention": char.get("first_mention", ""),
                    "actions": char.get("actions", []),
                    "mention_count": char.get("mention_count", 1),
                },
                confidence=0.8,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            ))
        
        return results
    
    def _parse_settings(
        self,
        parsed: Dict[str, Any],
        chunk: ChapterChunk
    ) -> List[AnalysisResult]:
        """解析设定结果"""
        results = []
        
        settings = parsed.get("settings", [])
        for setting in settings:
            results.append(AnalysisResult(
                result_type="setting",
                data={
                    "canonical_name": setting.get("name", ""),
                    "setting_type": setting.get("type", "item"),
                    "category": setting.get("category", ""),
                    "description": setting.get("description", ""),
                    "attributes": setting.get("attributes", {}),
                    "related_characters": setting.get("related_characters", []),
                    "importance": setting.get("importance", "normal"),
                    "evidence": setting.get("evidence", ""),
                },
                confidence=0.8,
                chunk_index=chunk.index,
                node_ids=chunk.node_ids,
            ))
        
        return results
    
    def _compile_results(
        self,
        results: List[AnalysisResult],
        sub_type: str
    ) -> Dict[str, Any]:
        """编译所有结果"""
        # 按类型分组
        by_type = {}
        for result in results:
            if result.result_type not in by_type:
                by_type[result.result_type] = []
            by_type[result.result_type].append({
                "data": result.data,
                "confidence": result.confidence,
                "chunk_index": result.chunk_index,
                "node_ids": result.node_ids,
            })
        
        return {
            "sub_type": sub_type,
            "total_results": len(results),
            "results_by_type": by_type,
            "raw_results": [
                {
                    "result_type": r.result_type,
                    "data": r.data,
                    "confidence": r.confidence,
                    "chunk_index": r.chunk_index,
                }
                for r in results
            ],
        }
    
    async def _create_step(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        step_type: str,
        title: str,
        content: str,
        **kwargs
    ):
        """创建步骤记录"""
        try:
            step_dao = UnifiedStepDAO(context.db_session)
            step_number = step_dao.get_next_step_number(task.id)
            
            step_dao.create(
                task_id=task.id,
                step_number=step_number,
                step_type=step_type,
                title=title,
                content=content,
                meta_data=kwargs,
            )
        except Exception as e:
            logger.warning(f"Failed to create step record: {e}")
    
    async def _update_task_result(
        self,
        task: UnifiedAgentTask,
        context: AgentContext,
        result_data: Dict[str, Any]
    ):
        """更新任务结果"""
        try:
            task_dao = UnifiedTaskDAO(context.db_session)
            task_dao.update(
                task.id,
                result_data=result_data,
            )
        except Exception as e:
            logger.warning(f"Failed to update task result: {e}")
