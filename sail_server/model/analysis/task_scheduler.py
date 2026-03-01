# -*- coding: utf-8 -*-
# @file task_scheduler.py
# @brief Analysis Task Scheduler and Runner
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# 分析任务调度器和执行器
# 支持 LLM 直接调用和 Prompt 导出两种模式
#

import json
import asyncio
import logging
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.analysis import AnalysisTask, AnalysisResult
from sail_server.application.dto.analysis import AnalysisTaskData, AnalysisResultData
from sail_server.infrastructure.orm.text import DocumentNode
from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider, PromptTemplateManager, get_template_manager

logger = logging.getLogger(__name__)


class TaskExecutionMode(Enum):
    """任务执行模式"""
    LLM_DIRECT = "llm_direct"       # 直接调用 LLM API
    PROMPT_ONLY = "prompt_only"     # 仅生成 Prompt
    MANUAL = "manual"               # 人工处理


@dataclass
class ChapterChunk:
    """章节分块"""
    index: int
    node_ids: List[int]
    chapter_range: str
    content: str
    token_estimate: int


@dataclass
class TaskExecutionPlan:
    """任务执行计划"""
    task_id: int
    mode: TaskExecutionMode
    chunks: List[ChapterChunk]
    total_estimated_tokens: int
    estimated_cost_usd: float
    prompt_template_id: str
    llm_config: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mode": self.mode.value,
            "chunks": [
                {
                    "index": c.index,
                    "node_ids": c.node_ids,
                    "chapter_range": c.chapter_range,
                    "token_estimate": c.token_estimate,
                }
                for c in self.chunks
            ],
            "total_estimated_tokens": self.total_estimated_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "prompt_template_id": self.prompt_template_id,
        }


@dataclass
class TaskProgress:
    """任务进度"""
    task_id: int
    status: str
    current_step: str
    total_chunks: int
    completed_chunks: int
    current_chunk_info: Optional[str] = None
    started_at: Optional[datetime] = None
    estimated_remaining_seconds: Optional[int] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "current_step": self.current_step,
            "total_chunks": self.total_chunks,
            "completed_chunks": self.completed_chunks,
            "current_chunk_info": self.current_chunk_info,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "error": self.error,
        }


@dataclass
class TaskRunResult:
    """任务执行结果"""
    task_id: int
    success: bool
    results_count: int
    error_message: Optional[str] = None
    execution_time_seconds: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "results_count": self.results_count,
            "error_message": self.error_message,
            "execution_time_seconds": self.execution_time_seconds,
        }


class AnalysisTaskRunner:
    """分析任务执行器"""
    
    # 任务类型到模板的映射
    TASK_TYPE_TEMPLATE_MAP = {
        "outline_extraction": "outline_extraction_v1",
        "character_detection": "character_detection_v1",
        "setting_extraction": "setting_extraction_v1",
    }
    
    # 每个分块的最大 token 数
    MAX_CHUNK_TOKENS = 8000
    
    def __init__(
        self, 
        db_session_factory: Callable[[], Session],
        llm_config: Optional[LLMConfig] = None
    ):
        self.db_factory = db_session_factory
        self.llm_config = llm_config or LLMConfig(provider=LLMProvider.EXTERNAL)
        self.template_manager = get_template_manager()
        self.llm_client: Optional[LLMClient] = None
        
        # 进度追踪
        self._progress: Dict[int, TaskProgress] = {}
        self._progress_callbacks: Dict[int, List[Callable]] = {}
    
    def _get_llm_client(self) -> LLMClient:
        """获取或创建 LLM 客户端"""
        if self.llm_client is None:
            self.llm_client = LLMClient(self.llm_config)
        return self.llm_client
    
    def set_llm_config(self, config: LLMConfig):
        """设置 LLM 配置"""
        self.llm_config = config
        self.llm_client = None  # 重置客户端
    
    def create_execution_plan(
        self,
        db: Session,
        task_id: int,
        mode: TaskExecutionMode
    ) -> TaskExecutionPlan:
        """创建任务执行计划"""
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # 获取模板
        template_id = self.TASK_TYPE_TEMPLATE_MAP.get(task.task_type)
        if not template_id:
            template_id = task.llm_prompt_template or f"{task.task_type}_v1"
        
        # 准备章节内容并分块
        chunks = self._prepare_chapter_chunks(db, task)
        
        # 计算总 token 和成本
        total_tokens = sum(c.token_estimate for c in chunks)
        
        # 估算输出 token（假设输出是输入的 30%）
        estimated_output_tokens = int(total_tokens * 0.3)
        
        # 计算成本
        client = self._get_llm_client()
        estimated_cost = client.estimate_cost(total_tokens, estimated_output_tokens)
        
        return TaskExecutionPlan(
            task_id=task_id,
            mode=mode,
            chunks=chunks,
            total_estimated_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            prompt_template_id=template_id,
            llm_config={
                "model": self.llm_config.model,
                "temperature": self.llm_config.temperature,
            } if mode == TaskExecutionMode.LLM_DIRECT else None,
        )
    
    def _prepare_chapter_chunks(
        self, 
        db: Session, 
        task: AnalysisTask
    ) -> List[ChapterChunk]:
        """准备章节内容并分块"""
        chunks = []
        
        # 获取目标章节
        if task.target_node_ids and len(task.target_node_ids) > 0:
            nodes = db.query(DocumentNode).filter(
                DocumentNode.id.in_(task.target_node_ids)
            ).order_by(DocumentNode.sort_index).all()
        else:
            # 获取整个版本的所有章节
            nodes = db.query(DocumentNode).filter(
                DocumentNode.edition_id == task.edition_id,
                DocumentNode.node_type == 'chapter'
            ).order_by(DocumentNode.sort_index).all()
        
        if not nodes:
            return chunks
        
        # 分块处理
        current_chunk_nodes = []
        current_chunk_content = ""
        current_chunk_tokens = 0
        chunk_index = 0
        
        client = self._get_llm_client()
        
        for node in nodes:
            node_content = node.raw_text or ""
            node_tokens = client.estimate_tokens(node_content)
            
            # 如果单个章节就超过限制，单独作为一块
            if node_tokens > self.MAX_CHUNK_TOKENS:
                # 先保存当前块
                if current_chunk_nodes:
                    chunks.append(ChapterChunk(
                        index=chunk_index,
                        node_ids=[n.id for n in current_chunk_nodes],
                        chapter_range=self._get_chapter_range(current_chunk_nodes),
                        content=current_chunk_content,
                        token_estimate=current_chunk_tokens,
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
            if current_chunk_tokens + node_tokens > self.MAX_CHUNK_TOKENS:
                if current_chunk_nodes:
                    chunks.append(ChapterChunk(
                        index=chunk_index,
                        node_ids=[n.id for n in current_chunk_nodes],
                        chapter_range=self._get_chapter_range(current_chunk_nodes),
                        content=current_chunk_content,
                        token_estimate=current_chunk_tokens,
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
            chunks.append(ChapterChunk(
                index=chunk_index,
                node_ids=[n.id for n in current_chunk_nodes],
                chapter_range=self._get_chapter_range(current_chunk_nodes),
                content=current_chunk_content,
                token_estimate=current_chunk_tokens,
            ))
        
        return chunks
    
    def _get_chapter_range(self, nodes: List[DocumentNode]) -> str:
        """获取章节范围描述"""
        if not nodes:
            return ""
        if len(nodes) == 1:
            return nodes[0].title or f"Chapter {nodes[0].id}"
        return f"{nodes[0].title or 'Chapter'} - {nodes[-1].title or 'Chapter'}"
    
    async def run_task(
        self,
        db: Session,
        task_id: int,
        mode: TaskExecutionMode
    ) -> TaskRunResult:
        """执行分析任务"""
        start_time = datetime.utcnow()
        logger.info(f"[DEBUG] Starting task {task_id}, mode={mode.value}")
        
        try:
            # 获取任务
            task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            
            logger.info(f"[DEBUG] Task info: type={task.task_type}, edition_id={task.edition_id}")
            
            # 更新任务状态为运行中
            task.status = 'running'
            task.started_at = start_time
            db.commit()
            
            # 创建执行计划
            logger.info(f"[DEBUG] Creating execution plan...")
            plan = self.create_execution_plan(db, task_id, mode)
            logger.info(f"[DEBUG] Execution plan created: {len(plan.chunks)} chunks, template={plan.prompt_template_id}")
            
            # 初始化进度
            self._progress[task_id] = TaskProgress(
                task_id=task_id,
                status="running",
                current_step="initializing",
                total_chunks=len(plan.chunks),
                completed_chunks=0,
                started_at=start_time,
            )
            
            # 执行分析
            results = []
            chunk_start_time = datetime.utcnow()
            
            for i, chunk in enumerate(plan.chunks):
                chunk_elapsed = (datetime.utcnow() - chunk_start_time).total_seconds()
                logger.info(f"[DEBUG] Processing chunk {i+1}/{len(plan.chunks)}: {chunk.chapter_range} "
                           f"(elapsed: {chunk_elapsed:.2f}s)")
                
                self._update_progress(task_id, 
                    current_step="processing_chunk",
                    current_chunk_info=chunk.chapter_range
                )
                
                chunk_process_start = datetime.utcnow()
                
                if mode == TaskExecutionMode.LLM_DIRECT:
                    chunk_results = await self._process_chunk_with_llm(
                        db, task, chunk, plan.prompt_template_id
                    )
                else:
                    chunk_results = await self._generate_chunk_prompt(
                        db, task, chunk, plan.prompt_template_id
                    )
                
                chunk_process_time = (datetime.utcnow() - chunk_process_start).total_seconds()
                logger.info(f"[DEBUG] Chunk {i+1} processed in {chunk_process_time:.2f}s, "
                           f"got {len(chunk_results)} results")
                
                results.extend(chunk_results)
                
                self._update_progress(task_id,
                    completed_chunks=self._progress[task_id].completed_chunks + 1
                )
            
            # 保存结果
            for result_data in results:
                result = AnalysisResult(
                    task_id=task_id,
                    result_type=result_data.get('result_type', task.task_type),
                    result_data=result_data.get('data', {}),
                    confidence=result_data.get('confidence'),
                )
                db.add(result)
            
            # 更新任务状态为完成
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            task.result_summary = {
                "total_results": len(results),
                "chunks_processed": len(plan.chunks),
            }
            db.commit()
            
            self._update_progress(task_id, status="completed", current_step="done")
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return TaskRunResult(
                task_id=task_id,
                success=True,
                results_count=len(results),
                execution_time_seconds=execution_time,
            )
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            
            # 更新任务状态为失败
            task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
            if task:
                task.status = 'failed'
                task.completed_at = datetime.utcnow()
                task.error_message = str(e)
                db.commit()
            
            self._update_progress(task_id, status="failed", error=str(e))
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return TaskRunResult(
                task_id=task_id,
                success=False,
                results_count=0,
                error_message=str(e),
                execution_time_seconds=execution_time,
            )
    
    async def _process_chunk_with_llm(
        self,
        db: Session,
        task: AnalysisTask,
        chunk: ChapterChunk,
        template_id: str
    ) -> List[Dict[str, Any]]:
        """使用 LLM 处理分块"""
        logger.info(f"[DEBUG] Starting LLM processing for chunk {chunk.index}: {chunk.chapter_range}")
        
        # 获取作品信息
        from sail_server.infrastructure.orm.text import Edition, Work
        edition = db.query(Edition).filter(Edition.id == task.edition_id).first()
        work_title = "Unknown"
        if edition:
            work = db.query(Work).filter(Work.id == edition.work_id).first()
            if work:
                work_title = work.title
        
        # 渲染模板
        variables = {
            "work_title": work_title,
            "chapter_range": chunk.chapter_range,
            "chapter_contents": chunk.content,
            "known_characters": task.parameters.get("known_characters", ""),
            "setting_types": task.parameters.get("setting_types", "item, location, organization"),
        }
        
        rendered = self.template_manager.render(template_id, variables)
        logger.info(f"[DEBUG] Template rendered: {template_id}, estimated_tokens: {rendered.estimated_tokens}")
        
        # 调用 LLM
        client = self._get_llm_client()
        logger.info(f"[DEBUG] LLM client created, starting API call for chunk {chunk.index}...")
        
        try:
            import time
            api_start = time.time()
            
            response = await client.complete(
                rendered.user_prompt,
                system=rendered.system_prompt
            )
            
            api_duration = time.time() - api_start
            logger.info(f"[DEBUG] LLM API call completed for chunk {chunk.index}: "
                       f"duration={api_duration:.2f}s, "
                       f"model={response.model}, "
                       f"finish_reason={response.finish_reason}, "
                       f"tokens={response.total_tokens}, "
                       f"content_length={len(response.content)}")
            
            # 检查是否因为 max_tokens 导致截断
            if response.finish_reason == "length":
                logger.warning(f"LLM response truncated due to max_tokens limit for chunk {chunk.index}")
            
            # 解析响应
            content = response.content.strip()
            
            # 移除 markdown 代码块
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            # 尝试解析 JSON，如果失败则尝试修复
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error for chunk {chunk.index}: {e}, attempting to fix...")
                # 尝试修复不完整的 JSON
                fixed_content = self._fix_incomplete_json(content)
                try:
                    parsed = json.loads(fixed_content)
                    logger.info(f"Successfully fixed JSON for chunk {chunk.index}")
                except json.JSONDecodeError:
                    # 如果修复失败，尝试提取有效部分
                    parsed = self._extract_valid_json(content)
                    if parsed is None:
                        raise e
            
            # 转换为结果列表
            results = self._parse_llm_output(task.task_type, parsed, chunk)
            
            return results
            
        except Exception as e:
            logger.error(f"LLM processing failed for chunk {chunk.index}: {e}")
            return [{
                "result_type": task.task_type,
                "data": {
                    "error": str(e),
                    "chunk_index": chunk.index,
                    "chunk_range": chunk.chapter_range,
                },
                "confidence": 0,
            }]
    
    def _fix_incomplete_json(self, content: str) -> str:
        """尝试修复不完整的 JSON 字符串"""
        # 移除尾部的不完整内容
        # 找到最后一个完整的 JSON 对象/数组
        content = content.strip()
        
        # 尝试找到最后一个完整的结构
        braces = 0
        brackets = 0
        in_string = False
        escape_next = False
        last_valid_pos = 0
        
        for i, char in enumerate(content):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not in_string:
                in_string = True
            elif char == '"' and in_string:
                in_string = False
            elif not in_string:
                if char == '{':
                    braces += 1
                elif char == '}':
                    braces -= 1
                    if braces == 0 and brackets == 0:
                        last_valid_pos = i + 1
                elif char == '[':
                    brackets += 1
                elif char == ']':
                    brackets -= 1
                    if braces == 0 and brackets == 0:
                        last_valid_pos = i + 1
        
        # 如果找到了完整的结构，截取到那里
        if last_valid_pos > 0:
            return content[:last_valid_pos]
        
        # 否则尝试补全
        if braces > 0:
            content += '}' * braces
        if brackets > 0:
            content += ']' * brackets
        
        return content
    
    def _extract_valid_json(self, content: str) -> Optional[Dict[str, Any]]:
        """从文本中提取有效的 JSON 对象"""
        # 尝试找到第一个 JSON 对象
        obj_match = re.search(r'\{[\s\S]*\}', content)
        if obj_match:
            try:
                return json.loads(obj_match.group())
            except json.JSONDecodeError:
                pass
        
        # 尝试找到第一个 JSON 数组
        arr_match = re.search(r'\[[\s\S]*\]', content)
        if arr_match:
            try:
                return json.loads(arr_match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    async def _generate_chunk_prompt(
        self,
        db: Session,
        task: AnalysisTask,
        chunk: ChapterChunk,
        template_id: str
    ) -> List[Dict[str, Any]]:
        """生成分块的 Prompt（不调用 LLM）"""
        # 获取作品信息
        from sail_server.infrastructure.orm.text import Edition, Work
        edition = db.query(Edition).filter(Edition.id == task.edition_id).first()
        work_title = "Unknown"
        if edition:
            work = db.query(Work).filter(Work.id == edition.work_id).first()
            if work:
                work_title = work.title
        
        # 渲染模板
        variables = {
            "work_title": work_title,
            "chapter_range": chunk.chapter_range,
            "chapter_contents": chunk.content,
            "known_characters": task.parameters.get("known_characters", ""),
            "setting_types": task.parameters.get("setting_types", "item, location, organization"),
        }
        
        rendered = self.template_manager.render(template_id, variables)
        
        # 生成导出格式的 Prompt
        client = self._get_llm_client()
        exported = client.generate_prompt_only(
            rendered.user_prompt,
            system=rendered.system_prompt,
            task_id=task.id,
            chunk_index=chunk.index,
            total_chunks=self._progress.get(task.id, TaskProgress(
                task_id=task.id, status="", current_step="", 
                total_chunks=1, completed_chunks=0
            )).total_chunks,
        )
        
        return [{
            "result_type": "exported_prompt",
            "data": {
                "chunk_index": chunk.index,
                "chunk_range": chunk.chapter_range,
                "node_ids": chunk.node_ids,
                "prompt": exported.to_dict(),
                "awaiting_external_result": True,
            },
            "confidence": None,
        }]
    
    def _parse_llm_output(
        self,
        task_type: str,
        parsed: Dict[str, Any],
        chunk: ChapterChunk
    ) -> List[Dict[str, Any]]:
        """解析 LLM 输出为结果列表"""
        results = []
        
        if task_type == "outline_extraction":
            plot_points = parsed.get("plot_points", [])
            for point in plot_points:
                results.append({
                    "result_type": "outline_node",
                    "data": {
                        "title": point.get("title", ""),
                        "node_type": point.get("type", "scene"),
                        "summary": point.get("summary", ""),
                        "significance": point.get("importance", "normal"),
                        "characters": point.get("characters", []),
                        "evidence": point.get("evidence", ""),
                        "chunk_index": chunk.index,
                        "node_ids": chunk.node_ids,
                    },
                    "confidence": 0.8,
                })
            
            # 添加总结
            if parsed.get("overall_summary"):
                results.append({
                    "result_type": "chunk_summary",
                    "data": {
                        "summary": parsed["overall_summary"],
                        "chunk_index": chunk.index,
                        "chunk_range": chunk.chapter_range,
                    },
                    "confidence": 0.9,
                })
        
        elif task_type == "character_detection":
            characters = parsed.get("characters", [])
            for char in characters:
                results.append({
                    "result_type": "character",
                    "data": {
                        "canonical_name": char.get("canonical_name", ""),
                        "aliases": char.get("aliases", []),
                        "role_type": char.get("role_type", "supporting"),
                        "description": char.get("description", ""),
                        "first_mention": char.get("first_mention", ""),
                        "actions": char.get("actions", []),
                        "mention_count": char.get("mention_count", 1),
                        "chunk_index": chunk.index,
                        "node_ids": chunk.node_ids,
                    },
                    "confidence": 0.8,
                })
        
        elif task_type == "setting_extraction":
            settings = parsed.get("settings", [])
            for setting in settings:
                results.append({
                    "result_type": "setting",
                    "data": {
                        "canonical_name": setting.get("name", ""),
                        "setting_type": setting.get("type", "item"),
                        "category": setting.get("category", ""),
                        "description": setting.get("description", ""),
                        "attributes": setting.get("attributes", {}),
                        "related_characters": setting.get("related_characters", []),
                        "importance": setting.get("importance", "normal"),
                        "evidence": setting.get("evidence", ""),
                        "chunk_index": chunk.index,
                        "node_ids": chunk.node_ids,
                    },
                    "confidence": 0.8,
                })
        
        return results
    
    def _update_progress(self, task_id: int, **kwargs):
        """更新任务进度"""
        if task_id in self._progress:
            for key, value in kwargs.items():
                if hasattr(self._progress[task_id], key):
                    setattr(self._progress[task_id], key, value)
            
            # 触发回调
            for callback in self._progress_callbacks.get(task_id, []):
                try:
                    callback(self._progress[task_id])
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")
    
    def get_progress(self, task_id: int) -> Optional[TaskProgress]:
        """获取任务进度"""
        return self._progress.get(task_id)
    
    def subscribe_progress(self, task_id: int, callback: Callable[[TaskProgress], None]):
        """订阅任务进度更新"""
        if task_id not in self._progress_callbacks:
            self._progress_callbacks[task_id] = []
        self._progress_callbacks[task_id].append(callback)
    
    def unsubscribe_progress(self, task_id: int, callback: Callable[[TaskProgress], None]):
        """取消订阅任务进度更新"""
        if task_id in self._progress_callbacks:
            try:
                self._progress_callbacks[task_id].remove(callback)
            except ValueError:
                pass


# 全局任务执行器实例
_task_runner: Optional[AnalysisTaskRunner] = None


def get_task_runner(db_session_factory: Callable[[], Session]) -> AnalysisTaskRunner:
    """获取全局任务执行器"""
    global _task_runner
    if _task_runner is None:
        _task_runner = AnalysisTaskRunner(db_session_factory)
    return _task_runner


def import_external_result(
    db: Session,
    task_id: int,
    chunk_index: int,
    result_text: str
) -> Optional[AnalysisResultData]:
    """导入外部 LLM 的结果"""
    # 查找对应的 exported_prompt 结果
    existing = db.query(AnalysisResult).filter(
        AnalysisResult.task_id == task_id,
        AnalysisResult.result_type == "exported_prompt",
    ).all()
    
    target_result = None
    for r in existing:
        if r.result_data.get("chunk_index") == chunk_index:
            target_result = r
            break
    
    if not target_result:
        return None
    
    # 解析导入的结果
    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        # 如果不是 JSON，作为原始文本保存
        parsed = {"raw_text": result_text}
    
    # 获取任务类型
    task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
    if not task:
        return None
    
    # 创建新的结果记录
    new_result = AnalysisResult(
        task_id=task_id,
        result_type=f"{task.task_type}_imported",
        result_data={
            "chunk_index": chunk_index,
            "imported_data": parsed,
            "original_prompt_result_id": target_result.id,
        },
        confidence=0.7,  # 外部导入的结果置信度略低
        review_status="pending",
    )
    db.add(new_result)
    
    # 更新原始 prompt 结果
    target_result.result_data["awaiting_external_result"] = False
    target_result.result_data["external_result_imported"] = True
    
    db.commit()
    db.refresh(new_result)
    
    return AnalysisResultData.read_from_orm(new_result)
