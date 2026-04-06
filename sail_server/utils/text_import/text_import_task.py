# -*- coding: utf-8 -*-
# @file text_import_task.py
# @brief 文本导入任务处理器
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
文本导入任务处理器 - 集成到 UnifiedAgentScheduler

四阶段处理流程：
1. UPLOAD (0-20%) - 文件接收（已完成）
2. PREPROCESS (20-40%) - 文本清理、编码检测
3. PARSE (40-80%) - 章节解析、AI分析
4. STORE (80-100%) - 数据库存储
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from sail.llm.client import LLMConfig, LLMProvider
from sail_server.utils.text_import import (
    TextCleaner,
    EncodingDetector,
    AIChapterParser,
    ParseResult,
    ParsedChapter,
    get_temp_file_manager,
)
from sail_server.model.text import (
    create_work_impl,
    create_edition_impl,
    create_document_node_impl,
    WorkCreateRequest,
    EditionCreateRequest,
    DocumentNodeCreateRequest,
)
from sail_server.application.dto.unified_agent import TaskStatus
from sail_server.infrastructure.orm.text import Work, Edition, DocumentNode

logger = logging.getLogger(__name__)


class ImportStage(Enum):
    """导入阶段"""

    UPLOAD = "upload"  # 0-20%
    PREPROCESS = "preprocess"  # 20-40%
    PARSE = "parse"  # 40-80%
    STORE = "store"  # 80-100%


@dataclass
class ImportProgress:
    """导入进度信息"""

    stage: ImportStage
    stage_progress: int  # 当前阶段进度 (0-100)
    overall_progress: int  # 总体进度 (0-100)
    message: str
    chapters_found: int = 0
    chapters_processed: int = 0
    eta_seconds: Optional[int] = None


@dataclass
class ImportResult:
    """导入结果"""

    work_id: int
    edition_id: int
    chapter_count: int
    total_chars: int
    processing_time_seconds: float
    warnings: List[str] = field(default_factory=list)


class TextImportTaskHandler:
    """文本导入任务处理器"""

    # 阶段进度权重
    STAGE_WEIGHTS = {
        ImportStage.UPLOAD: 0.20,
        ImportStage.PREPROCESS: 0.20,
        ImportStage.PARSE: 0.40,
        ImportStage.STORE: 0.20,
    }

    def __init__(
        self,
        db: Session,
        task_id: int,
        payload: Dict[str, Any],
        progress_callback: Optional[callable] = None,
    ):
        """
        Args:
            db: 数据库会话
            task_id: 任务ID
            payload: 任务负载数据
            progress_callback: 进度回调函数
        """
        self.db = db
        self.task_id = task_id
        self.payload = payload
        self.progress_callback = progress_callback

        # 解析 payload
        self.file_id = payload.get("file_id")
        self.work_title = payload.get("work_title", "Untitled")
        self.work_author = payload.get("work_author")
        self.edition_name = payload.get("edition_name", "原始导入")
        self.enable_ai = payload.get("enable_ai_parsing", True)
        self.encoding_hint = payload.get("encoding")

        # 初始化工具
        self.text_cleaner = TextCleaner()
        self.encoding_detector = EncodingDetector()
        self.chapter_parser: Optional[AIChapterParser] = None

        # 处理状态
        self.current_stage = ImportStage.UPLOAD
        self.start_time = datetime.utcnow()
        self.cancelled = False

        # 中间结果
        self.raw_text: Optional[str] = None
        self.cleaned_text: Optional[str] = None
        self.parse_result: Optional[ParseResult] = None
        self.work_id: Optional[int] = None
        self.edition_id: Optional[int] = None

    async def execute(self) -> ImportResult:
        """执行导入任务

        Returns:
            导入结果
        """
        logger.info(f"Starting text import task {self.task_id}")

        try:
            # Stage 1: UPLOAD (已完成，只需确认文件存在)
            await self._stage_upload()

            # Stage 2: PREPROCESS
            if self.cancelled:
                raise asyncio.CancelledError("Task cancelled")
            await self._stage_preprocess()

            # Stage 3: PARSE
            if self.cancelled:
                raise asyncio.CancelledError("Task cancelled")
            await self._stage_parse()

            # Stage 4: STORE
            if self.cancelled:
                raise asyncio.CancelledError("Task cancelled")
            await self._stage_store()

            # 完成任务
            processing_time = (datetime.utcnow() - self.start_time).total_seconds()

            result = ImportResult(
                work_id=self.work_id,
                edition_id=self.edition_id,
                chapter_count=len(self.parse_result.chapters)
                if self.parse_result
                else 0,
                total_chars=self.parse_result.total_chars if self.parse_result else 0,
                processing_time_seconds=processing_time,
                warnings=self.parse_result.warnings if self.parse_result else [],
            )

            logger.info(f"Text import task {self.task_id} completed successfully")
            return result

        except asyncio.CancelledError:
            logger.info(f"Text import task {self.task_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Text import task {self.task_id} failed: {e}", exc_info=True)
            raise

    async def _stage_upload(self):
        """阶段1: UPLOAD - 确认文件并读取"""
        self.current_stage = ImportStage.UPLOAD
        self._report_progress(0, "正在读取上传的文件...")

        # 获取临时文件
        temp_manager = get_temp_file_manager()
        file_info = temp_manager.get_file(self.file_id)

        if not file_info:
            raise ValueError(f"File not found: {self.file_id}")

        # 读取文件内容
        self.raw_text = temp_manager.read_file(self.file_id, self.encoding_hint)

        if not self.raw_text:
            raise ValueError(f"Failed to read file content: {self.file_id}")

        self._report_progress(100, f"文件读取完成，共 {len(self.raw_text)} 字符")
        logger.info(f"Stage UPLOAD completed: {len(self.raw_text)} chars")

    async def _stage_preprocess(self):
        """阶段2: PREPROCESS - 文本清理"""
        self.current_stage = ImportStage.PREPROCESS
        self._report_progress(0, "正在预处理文本...")

        if not self.raw_text:
            raise ValueError("No raw text to preprocess")

        # 1. 移除BOM
        text = self.text_cleaner.remove_bom(self.raw_text)
        self._report_progress(20, "已移除BOM标记")

        # 2. 文本清理
        self._report_progress(30, "正在清理广告和噪音...")
        cleaned_text, stats = self.text_cleaner.clean(text, aggressive=False)

        logger.info(f"Text cleaning stats: {stats}")
        self._report_progress(
            60,
            f"清理完成: 移除 {stats.get('lines_removed', 0)} 行, "
            f"{stats.get('urls_removed', 0)} 个URL",
        )

        # 3. 标准化换行符
        cleaned_text = self.text_cleaner._normalize_newlines(cleaned_text)
        self._report_progress(80, "文本格式化完成")

        self.cleaned_text = cleaned_text
        self._report_progress(100, f"预处理完成，清理后共 {len(cleaned_text)} 字符")
        logger.info(f"Stage PREPROCESS completed: {len(cleaned_text)} chars")

    async def _stage_parse(self):
        """阶段3: PARSE - 章节解析"""
        self.current_stage = ImportStage.PARSE
        self._report_progress(0, "正在解析章节结构...")

        if not self.cleaned_text:
            raise ValueError("No cleaned text to parse")

        # 初始化章节解析器
        llm_config = LLMConfig.from_env(LLMProvider.MOONSHOT)
        self.chapter_parser = AIChapterParser(llm_config, use_ai=self.enable_ai)

        self._report_progress(10, "正在分析章节模式...")

        # 解析章节
        self.parse_result = await self.chapter_parser.parse(
            self.cleaned_text, enable_ai=self.enable_ai
        )

        # 报告进度（逐个章节）
        total_chapters = len(self.parse_result.chapters)
        for i, chapter in enumerate(self.parse_result.chapters):
            progress = int((i + 1) / total_chapters * 80) + 10  # 10-90%
            self._report_progress(
                progress,
                f"已解析 {i + 1}/{total_chapters} 章...",
                chapters_found=total_chapters,
                chapters_processed=i + 1,
            )
            # 小延迟避免阻塞
            if i % 10 == 0:
                await asyncio.sleep(0.01)

        # 报告统计信息
        special_chapters = self.parse_result.special_chapters
        special_info = (
            ", ".join(f"{k}: {v}" for k, v in special_chapters.items())
            if special_chapters
            else "无"
        )

        self._report_progress(
            100,
            f"章节解析完成: 共 {total_chapters} 章 ({special_info})",
            chapters_found=total_chapters,
            chapters_processed=total_chapters,
        )

        logger.info(
            f"Stage PARSE completed: {total_chapters} chapters, "
            f"special: {special_chapters}"
        )

    async def _stage_store(self):
        """阶段4: STORE - 数据库存储"""
        self.current_stage = ImportStage.STORE
        self._report_progress(0, "正在保存到数据库...")

        if not self.parse_result:
            raise ValueError("No parse result to store")

        # 1. 创建作品
        self._report_progress(10, "正在创建作品...")
        work_data = WorkCreateRequest(
            slug=self._generate_slug(self.work_title),
            title=self.work_title,
            author=self.work_author,
            language_primary="zh",
            work_type="web_novel",
            status="ongoing",
        )
        work_response = create_work_impl(self.db, work_data)
        self.work_id = work_response.id

        self._report_progress(25, f"作品创建成功 (ID: {self.work_id})")

        # 2. 创建版本
        self._report_progress(30, "正在创建版本...")
        edition_data = EditionCreateRequest(
            work_id=self.work_id,
            edition_name=self.edition_name,
            language="zh",
            source_format="txt",
            word_count=self.parse_result.total_chars,  # 简化为字符数
            char_count=self.parse_result.total_chars,
            status="active",
        )
        edition_response = create_edition_impl(self.db, edition_data)
        self.edition_id = edition_response.id

        self._report_progress(40, f"版本创建成功 (ID: {self.edition_id})")

        # 3. 批量创建章节节点
        chapters = self.parse_result.chapters
        total = len(chapters)

        self._report_progress(45, f"正在保存 {total} 个章节...")

        for i, chapter in enumerate(chapters):
            # 创建文档节点
            node_data = DocumentNodeCreateRequest(
                edition_id=self.edition_id,
                node_type="chapter",
                sort_index=chapter.index,
                depth=1,
                label=chapter.label or f"第{chapter.index + 1}章",
                title=chapter.content_title or "",
                raw_text=chapter.content,
                word_count=chapter.char_count,
                char_count=chapter.char_count,
                path=f"{chapter.index:04d}",
                meta_data={
                    "chapter_type": chapter.chapter_type.value,
                    "warnings": chapter.warnings,
                },
            )
            create_document_node_impl(self.db, node_data)

            # 更新进度（45-95%）
            progress = int((i + 1) / total * 50) + 45
            if progress % 5 == 0 or i == total - 1:
                self._report_progress(progress, f"已保存 {i + 1}/{total} 章...")

            # 每50章提交一次，避免事务过大
            if (i + 1) % 50 == 0:
                self.db.commit()
                await asyncio.sleep(0.01)

        # 最终提交
        self.db.commit()

        self._report_progress(100, f"导入完成！共 {total} 章")
        logger.info(
            f"Stage STORE completed: work_id={self.work_id}, "
            f"edition_id={self.edition_id}, chapters={total}"
        )

    def _report_progress(
        self,
        stage_progress: int,
        message: str,
        chapters_found: int = 0,
        chapters_processed: int = 0,
    ):
        """报告进度

        Args:
            stage_progress: 当前阶段进度 (0-100)
            message: 进度消息
            chapters_found: 发现的章节数
            chapters_processed: 已处理的章节数
        """
        # 计算总体进度
        stage_weight = self.STAGE_WEIGHTS[self.current_stage]
        stage_start = sum(
            self.STAGE_WEIGHTS[s]
            for s in ImportStage
            if list(ImportStage).index(s) < list(ImportStage).index(self.current_stage)
        )

        overall_progress = int(
            (stage_start + stage_progress / 100 * stage_weight) * 100
        )
        overall_progress = min(100, max(0, overall_progress))

        # 计算预计剩余时间
        eta = None
        if overall_progress > 0 and overall_progress < 100:
            elapsed = (datetime.utcnow() - self.start_time).total_seconds()
            estimated_total = elapsed / (overall_progress / 100)
            eta = int(estimated_total - elapsed)

        progress = ImportProgress(
            stage=self.current_stage,
            stage_progress=stage_progress,
            overall_progress=overall_progress,
            message=message,
            chapters_found=chapters_found,
            chapters_processed=chapters_processed,
            eta_seconds=eta,
        )

        # 调用回调
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

        logger.debug(f"Task {self.task_id} progress: {overall_progress}% - {message}")

    def _generate_slug(self, title: str) -> str:
        """生成作品 slug"""
        import re

        # 移除特殊字符，转换为小写
        slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
        # 替换空格为连字符
        slug = re.sub(r"[-\s]+", "-", slug)
        # 限制长度
        slug = slug[:50]
        # 添加时间戳确保唯一性
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{slug}-{timestamp}"

    def cancel(self):
        """取消任务"""
        self.cancelled = True
        logger.info(f"Task {self.task_id} cancellation requested")


async def execute_text_import_task(
    db: Session,
    task_id: int,
    payload: Dict[str, Any],
    progress_callback: Optional[callable] = None,
) -> ImportResult:
    """便捷函数：执行文本导入任务

    Args:
        db: 数据库会话
        task_id: 任务ID
        payload: 任务负载
        progress_callback: 进度回调

    Returns:
        导入结果
    """
    handler = TextImportTaskHandler(db, task_id, payload, progress_callback)
    return await handler.execute()
