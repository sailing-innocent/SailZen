# -*- coding: utf-8 -*-
# @file async_extractor.py
# @brief Main async outline extractor
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""异步大纲提取器主控制器

整合所有组件，提供高层次的异步大纲提取接口
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import uuid

from .types import (
    Task,
    TaskStatus,
    TaskLevel,
    ExtractionConfig,
    ExtractionProgress,
    OutlineNode,
)
from .exceptions import (
    AsyncOutlineExtractionError,
    CircularDependencyError,
    ExtractionCancelledError,
)
from .task_graph import TaskGraph
from .rate_limiter import RateLimiter, RateLimitConfig, get_priority_by_level
from .text_splitter import TextSplitter
from .async_llm_client import AsyncLLMClient, LLMResponse
from .result_merger import ChunkResultMerger, SegmentResultMerger
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """提取结果"""

    task_id: str
    outline: Dict[str, Any]
    progress: ExtractionProgress
    performance: Dict[str, Any]


class AsyncOutlineExtractor:
    """异步大纲提取器"""

    def __init__(
        self,
        llm_client: AsyncLLMClient,
        config: Optional[ExtractionConfig] = None,
    ):
        self.config = config or ExtractionConfig()
        self.llm_client = llm_client

        # 初始化组件
        self.text_splitter = TextSplitter(self.config)
        self.chunk_merger = ChunkResultMerger()
        self.segment_merger = SegmentResultMerger()

        # 初始化速率限制器（如果 llm_client 没有）
        if not self.llm_client.rate_limiter:
            rate_limit_config = RateLimitConfig(
                max_concurrent=self.config.max_concurrent,
                rpm_limit=self.config.rpm_limit,
                tpm_limit=self.config.tpm_limit,
            )
            self.llm_client.rate_limiter = RateLimiter(rate_limit_config)

        # 活跃的任务图
        self._active_extractions: Dict[str, TaskGraph] = {}
        self._progress_trackers: Dict[str, ProgressTracker] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

        logger.info("AsyncOutlineExtractor initialized")

    async def extract(
        self,
        text: str,
        work_id: str,
        chapter_id: Optional[str] = None,
        progress_callback: Optional[Callable[[ExtractionProgress], None]] = None,
    ) -> ExtractionResult:
        """执行异步大纲提取

        Args:
            text: 要提取大纲的文本
            work_id: 作品ID
            chapter_id: 章节ID（可选）
            progress_callback: 进度回调函数

        Returns:
            提取结果
        """
        extraction_id = str(uuid.uuid4())

        try:
            # 1. 构建任务图
            task_graph = await self._build_task_graph(text, work_id, chapter_id)

            # 2. 检测循环依赖
            cycle = task_graph.detect_cycles()
            if cycle:
                raise CircularDependencyError(cycle)

            # 3. 创建进度追踪器
            progress_tracker = ProgressTracker(task_graph, extraction_id)
            if progress_callback:
                progress_tracker.add_callback(progress_callback)

            # 4. 存储活跃任务
            async with self._lock:
                self._active_extractions[extraction_id] = task_graph
                self._progress_trackers[extraction_id] = progress_tracker
                self._cancel_events[extraction_id] = asyncio.Event()

            # 5. 执行提取
            logger.info(
                f"Starting extraction {extraction_id} with {len(task_graph.get_all_tasks())} tasks"
            )
            await self._execute_extraction(extraction_id, task_graph)

            # 6. 获取结果
            result = self._build_result(extraction_id, task_graph)

            logger.info(f"Extraction {extraction_id} completed successfully")

            return result

        except asyncio.CancelledError:
            logger.warning(f"Extraction {extraction_id} was cancelled")
            raise ExtractionCancelledError(extraction_id)
        except Exception as e:
            logger.error(f"Extraction {extraction_id} failed: {e}")
            raise
        finally:
            # 清理资源
            await self._cleanup_extraction(extraction_id)

    async def _build_task_graph(
        self, text: str, work_id: str, chapter_id: Optional[str]
    ) -> TaskGraph:
        """构建任务图"""
        task_graph = TaskGraph()

        # 切分文本并创建任务
        chunk_tasks, segment_tasks, chapter_tasks = self.text_splitter.build_task_graph(
            text, work_id, chapter_id
        )

        # 添加所有任务到图中
        for task in chunk_tasks + segment_tasks + chapter_tasks:
            task_graph.add_task(task)

        return task_graph

    async def _execute_extraction(
        self, extraction_id: str, task_graph: TaskGraph
    ) -> None:
        """执行提取任务"""
        cancel_event = self._cancel_events.get(extraction_id)

        # 获取所有叶节点（chunks）
        chunk_tasks = task_graph.get_tasks_by_level(TaskLevel.CHUNK)

        # 创建执行队列
        pending_tasks: asyncio.Queue = asyncio.Queue()
        for task in chunk_tasks:
            await pending_tasks.put(task)

        # 执行 worker 池
        workers = [
            asyncio.create_task(
                self._worker(extraction_id, task_graph, pending_tasks, cancel_event)
            )
            for _ in range(min(10, len(chunk_tasks)))  # 最多 10 个 worker
        ]

        # 等待所有任务完成或被取消
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except asyncio.CancelledError:
            # 取消所有 worker
            for worker in workers:
                worker.cancel()
            raise

    async def _worker(
        self,
        extraction_id: str,
        task_graph: TaskGraph,
        pending_queue: asyncio.Queue,
        cancel_event: Optional[asyncio.Event],
    ) -> None:
        """工作线程"""
        while True:
            # 检查取消
            if cancel_event and cancel_event.is_set():
                break

            try:
                # 获取下一个可执行任务
                task = await asyncio.wait_for(pending_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # 检查是否所有任务都完成了
                if self._is_extraction_complete(task_graph):
                    break
                continue

            try:
                # 执行任务
                await self._execute_task(task, task_graph)

                # 检查下游任务
                await self._schedule_downstream_tasks(task, task_graph, pending_queue)

            except Exception as e:
                logger.error(f"Task {task.id} failed: {e}")
                await task_graph.update_task_status(
                    task.id, TaskStatus.FAILED, error=str(e)
                )

                # 增加重试计数
                task.retry_count += 1
                if task.retry_count < self.config.max_retries:
                    # 重新放入队列
                    await asyncio.sleep(
                        self.config.retry_delay_base * (2**task.retry_count)
                    )
                    await pending_queue.put(task)

    async def _execute_task(self, task: Task, task_graph: TaskGraph) -> None:
        """执行单个任务"""
        # 更新状态为运行中
        await task_graph.update_task_status(task.id, TaskStatus.RUNNING)

        # 根据层级执行不同的提取逻辑
        if task.level == TaskLevel.CHUNK:
            result = await self._extract_chunk(task)
        elif task.level == TaskLevel.SEGMENT:
            result = await self._extract_segment(task, task_graph)
        elif task.level == TaskLevel.CHAPTER:
            result = await self._extract_chapter(task, task_graph)
        else:
            raise ValueError(f"Unknown task level: {task.level}")

        # 更新状态为完成
        await task_graph.update_task_status(
            task.id, TaskStatus.COMPLETED, result=result
        )

    async def _extract_chunk(self, task: Task) -> List[OutlineNode]:
        """提取 chunk 大纲"""
        # TODO: 实现实际的 LLM 调用
        # 这里先用占位实现
        prompt = self._build_chunk_prompt(task.text)

        try:
            response = await self.llm_client.complete(
                prompt=prompt,
                task=task,
                temperature=0.7,
                max_tokens=1000,
            )

            # 解析响应为 OutlineNode 列表
            nodes = self._parse_outline_response(response.content, task)
            return nodes

        except Exception as e:
            logger.error(f"Chunk extraction failed: {e}")
            raise

    async def _extract_segment(
        self, task: Task, task_graph: TaskGraph
    ) -> List[OutlineNode]:
        """提取 segment 大纲"""
        # 获取所有依赖的 chunks 结果
        chunk_results = []
        for dep_id in task.dependencies:
            dep_task = task_graph.get_task(dep_id)
            if dep_task and dep_task.result:
                chunk_results.extend(dep_task.result)

        # 合并 chunks 结果
        chunk_tasks = [
            task_graph.get_task(dep_id)
            for dep_id in task.dependencies
            if task_graph.get_task(dep_id) is not None
        ]
        merged_chunks = self.chunk_merger.merge(chunk_tasks)

        # TODO: 实现实际的 LLM 调用
        # 基于合并的 chunks 进行 segment 级别提取
        prompt = self._build_segment_prompt(
            task.text, merged_chunks, task.context.get("context_summary", "")
        )

        try:
            response = await self.llm_client.complete(
                prompt=prompt,
                task=task,
                temperature=0.7,
                max_tokens=1500,
            )

            nodes = self._parse_outline_response(response.content, task)
            return nodes

        except Exception as e:
            logger.error(f"Segment extraction failed: {e}")
            raise

    async def _extract_chapter(
        self, task: Task, task_graph: TaskGraph
    ) -> List[OutlineNode]:
        """提取 chapter 大纲"""
        # 获取所有依赖的 segments 结果
        segment_results = []
        for dep_id in task.dependencies:
            dep_task = task_graph.get_task(dep_id)
            if dep_task and dep_task.result:
                segment_results.extend(dep_task.result)

        # 合并 segments 结果
        segment_tasks = [
            task_graph.get_task(dep_id)
            for dep_id in task.dependencies
            if task_graph.get_task(dep_id) is not None
        ]
        final_outline = self.segment_merger.merge(segment_tasks)

        return final_outline

    async def _schedule_downstream_tasks(
        self,
        completed_task: Task,
        task_graph: TaskGraph,
        pending_queue: asyncio.Queue,
    ) -> None:
        """调度下游任务"""
        # 找到所有依赖于此任务的任务
        ready_tasks = task_graph.get_ready_tasks()

        for task in ready_tasks:
            if task.status == TaskStatus.READY:
                await pending_queue.put(task)

    def _is_extraction_complete(self, task_graph: TaskGraph) -> bool:
        """检查提取是否完成"""
        tasks = task_graph.get_all_tasks()
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for t in tasks
        )

    def _build_result(
        self, extraction_id: str, task_graph: TaskGraph
    ) -> ExtractionResult:
        """构建提取结果"""
        # 获取 chapter 任务的结果
        chapter_tasks = task_graph.get_tasks_by_level(TaskLevel.CHAPTER)

        if not chapter_tasks:
            raise AsyncOutlineExtractionError("No chapter task found")

        chapter_task = chapter_tasks[0]
        outline_nodes = chapter_task.result or []

        # 格式化为标准结构
        outline = self.segment_merger.format_as_outline(outline_nodes)

        # 获取进度
        progress_tracker = self._progress_trackers.get(extraction_id)
        progress = None
        if progress_tracker:
            progress = progress_tracker.calculate_progress()

        # 性能指标
        performance = progress.performance_metrics if progress else {}

        return ExtractionResult(
            task_id=extraction_id,
            outline=outline,
            progress=progress,
            performance=performance,
        )

    def _build_chunk_prompt(self, text: str) -> str:
        """构建 chunk 提取提示词"""
        return f"""请分析以下文本片段，提取关键事件、角色出现和场景转换，以大纲形式输出。

文本片段：
{text}

请输出结构化的大纲节点列表，每个节点包含标题和内容。"""

    def _build_segment_prompt(
        self, text: str, chunk_nodes: List[OutlineNode], context: str
    ) -> str:
        """构建 segment 提取提示词"""
        context_section = f"前文摘要：{context}\n\n" if context else ""

        return f"""{context_section}请基于以下文本片段和已提取的子片段大纲，生成完整的段落大纲。

文本片段：
{text}

子片段大纲：
{self._format_nodes_for_prompt(chunk_nodes)}

请整合以上信息，生成连贯的段落大纲，去除重复内容，补全缺失信息。"""

    def _format_nodes_for_prompt(self, nodes: List[OutlineNode]) -> str:
        """将节点格式化为提示词"""
        lines = []
        for node in nodes:
            lines.append(f"- {node.title}: {node.content}")
        return "\n".join(lines)

    def _parse_outline_response(self, content: str, task: Task) -> List[OutlineNode]:
        """解析 LLM 响应为 OutlineNode 列表"""
        # TODO: 实现更健壮的解析逻辑
        # 这里使用简单的占位实现
        nodes = []

        # 假设响应是 JSON 格式
        import json

        try:
            data = json.loads(content)
            for item in data.get("nodes", []):
                node = OutlineNode(
                    title=item.get("title", "Untitled"),
                    content=item.get("content", ""),
                    level=item.get("level", 1),
                    start_pos=task.context.get("start_pos", 0),
                    end_pos=task.context.get("end_pos", 0),
                    metadata={"source": task.id},
                )
                nodes.append(node)
        except json.JSONDecodeError:
            # 如果不是 JSON，创建单个节点
            nodes.append(
                OutlineNode(
                    title="Extracted Content",
                    content=content,
                    level=1,
                    start_pos=task.context.get("start_pos", 0),
                    end_pos=task.context.get("end_pos", 0),
                    metadata={"source": task.id},
                )
            )

        return nodes

    async def cancel_extraction(self, extraction_id: str) -> bool:
        """取消提取任务"""
        cancel_event = self._cancel_events.get(extraction_id)
        if cancel_event:
            cancel_event.set()
            return True
        return False

    def get_progress(self, extraction_id: str) -> Optional[ExtractionProgress]:
        """获取当前进度"""
        tracker = self._progress_trackers.get(extraction_id)
        if tracker:
            return tracker.calculate_progress()
        return None

    async def _cleanup_extraction(self, extraction_id: str) -> None:
        """清理提取任务资源"""
        async with self._lock:
            if extraction_id in self._active_extractions:
                del self._active_extractions[extraction_id]

            if extraction_id in self._progress_trackers:
                self._progress_trackers[extraction_id].cleanup()
                del self._progress_trackers[extraction_id]

            if extraction_id in self._cancel_events:
                del self._cancel_events[extraction_id]
