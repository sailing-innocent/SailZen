# -*- coding: utf-8 -*-
# @file ai_chapter_parser.py
# @brief AI 驱动的章节解析器
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------
"""
AI 驱动的智能章节解析器
支持采样分析、模式学习、特殊章节识别
"""

import re
import json
import logging
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from sail.llm.client import LLMClient, LLMConfig, LLMProvider
from sail_server.utils.text_import.chapter_types import (
    ChapterType,
    get_chapter_type_by_title,
    get_standard_chapter_patterns,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedChapter:
    """解析后的章节"""

    index: int  # 章节索引
    title: str  # 完整标题
    label: str  # 章节标签（如"第一章"）
    content_title: str  # 内容标题（如"风云初起"）
    chapter_type: ChapterType  # 章节类型
    content: str  # 章节内容
    char_count: int  # 字符数
    start_pos: int  # 起始位置
    end_pos: int  # 结束位置
    warnings: List[str] = field(default_factory=list)  # 警告信息


@dataclass
class ParseResult:
    """解析结果"""

    chapters: List[ParsedChapter]
    total_chars: int
    avg_chapter_length: float
    min_chapter_length: int
    max_chapter_length: int
    patterns_used: List[str]
    special_chapters: Dict[str, int]  # 各类型特殊章节数量
    warnings: List[str]


class AIChapterParser:
    """AI 章节解析器"""

    # 采样大小
    SAMPLE_SIZE = 3000

    def __init__(self, llm_config: Optional[LLMConfig] = None, use_ai: bool = True):
        """
        Args:
            llm_config: LLM 配置，None 则使用默认配置
            use_ai: 是否使用 AI 辅助解析
        """
        self.use_ai = use_ai
        self.llm_config = llm_config or LLMConfig.from_env(LLMProvider.MOONSHOT)
        self.llm_client = LLMClient(self.llm_config) if use_ai else None

        # 默认章节模式
        self.default_patterns = get_standard_chapter_patterns()

    async def parse(self, text: str, enable_ai: bool = True) -> ParseResult:
        """解析文本章节

        Args:
            text: 要解析的文本
            enable_ai: 是否启用 AI 分析

        Returns:
            解析结果
        """
        if not text:
            return ParseResult(
                chapters=[],
                total_chars=0,
                avg_chapter_length=0,
                min_chapter_length=0,
                max_chapter_length=0,
                patterns_used=[],
                special_chapters={},
                warnings=["Empty text provided"],
            )

        # 1. 采样分析（如果启用 AI）
        learned_patterns = []
        if enable_ai and self.use_ai and len(text) > 10000:
            learned_patterns = await self._analyze_samples(text)

        # 2. 合并模式
        all_patterns = learned_patterns if learned_patterns else self.default_patterns

        # 3. 解析章节
        chapters = self._parse_with_patterns(text, all_patterns)

        # 4. 如果没有解析到章节，将整个文本作为一章
        if not chapters:
            chapters = [
                ParsedChapter(
                    index=0,
                    title="正文",
                    label="",
                    content_title="正文",
                    chapter_type=ChapterType.STANDARD,
                    content=text.strip(),
                    char_count=len(text),
                    start_pos=0,
                    end_pos=len(text),
                )
            ]

        # 5. 后处理
        chapters = self._post_process_chapters(chapters)

        # 6. 生成结果统计
        return self._generate_result(chapters, all_patterns)

    async def _analyze_samples(self, text: str) -> List[str]:
        """采样分析文本，学习章节模式

        Args:
            text: 完整文本

        Returns:
            学习到的正则模式列表
        """
        # 提取样本
        samples = self._extract_samples(text)

        # 构建提示词
        prompt = self._build_analysis_prompt(samples)

        try:
            # 调用 LLM
            response = await self.llm_client.complete(prompt)

            # 解析响应
            patterns = self._parse_analysis_response(response.content)

            logger.info(f"AI learned {len(patterns)} patterns from samples")
            return patterns

        except Exception as e:
            logger.warning(f"AI analysis failed: {e}, falling back to default patterns")
            return []

    def _extract_samples(self, text: str) -> List[str]:
        """提取文本样本（开头、中间、结尾）

        Args:
            text: 完整文本

        Returns:
            样本列表
        """
        samples = []

        # 开头样本
        samples.append(text[: self.SAMPLE_SIZE])

        # 中间样本
        mid_start = len(text) // 2 - self.SAMPLE_SIZE // 2
        samples.append(text[mid_start : mid_start + self.SAMPLE_SIZE])

        # 结尾样本
        samples.append(text[-self.SAMPLE_SIZE :])

        return samples

    def _build_analysis_prompt(self, samples: List[str]) -> str:
        """构建分析提示词

        Args:
            samples: 文本样本

        Returns:
            提示词
        """
        prompt = """分析以下小说文本样本，识别章节标题的模式。

请仔细查看文本中的章节标记，例如：
- 标准章节：第一章、第1章、Chapter 1
- 前置章节：楔子、序章、引言
- 后置章节：尾声、后记
- 番外章节：番外、外传

文本样本：

"""

        for i, sample in enumerate(samples, 1):
            prompt += f"\n--- 样本 {i} ---\n"
            prompt += sample[:2000]  # 限制样本长度
            prompt += "\n"

        prompt += """
请返回 JSON 格式的分析结果：
{
    "chapter_patterns": [
        "第[一二三四五六七八九十百千万零〇\\\\d]+章",
        "Chapter\\\\s+\\\\d+"
    ],
    "special_types": ["楔子", "序章", "尾声", "番外"],
    "has_prologue": true/false,
    "has_epilogue": true/false,
    "notes": "其他观察"
}

只返回 JSON，不要其他说明。"""

        return prompt

    def _parse_analysis_response(self, content: str) -> List[str]:
        """解析 AI 分析响应

        Args:
            content: LLM 响应内容

        Returns:
            正则模式列表
        """
        try:
            # 提取 JSON
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                patterns = result.get("chapter_patterns", [])

                # 验证模式有效性
                valid_patterns = []
                for p in patterns:
                    try:
                        re.compile(p)
                        valid_patterns.append(p)
                    except re.error:
                        logger.warning(f"Invalid pattern from AI: {p}")

                return valid_patterns
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response: {e}")

        return []

    def _parse_with_patterns(
        self, text: str, patterns: List[str]
    ) -> List[ParsedChapter]:
        """使用正则模式解析章节

        Args:
            text: 完整文本
            patterns: 正则模式列表

        Returns:
            章节列表
        """
        chapters = []

        # 合并所有模式
        combined_pattern = "|".join(f"({p})" for p in patterns)

        try:
            regex = re.compile(combined_pattern, re.MULTILINE | re.IGNORECASE)
            matches = list(regex.finditer(text))

            if not matches:
                return chapters

            for i, match in enumerate(matches):
                title = match.group().strip()
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

                content = text[match.end() : end].strip()

                # 解析标题
                label, content_title = self._split_title(title)

                # 识别章节类型
                chapter_type = get_chapter_type_by_title(title)

                chapters.append(
                    ParsedChapter(
                        index=i,
                        title=title,
                        label=label,
                        content_title=content_title,
                        chapter_type=chapter_type,
                        content=content,
                        char_count=len(content),
                        start_pos=start,
                        end_pos=end,
                    )
                )

        except re.error as e:
            logger.error(f"Regex error: {e}")

        return chapters

    def _split_title(self, title: str) -> Tuple[str, str]:
        """拆分章节标题为标签和内容标题

        Args:
            title: 完整标题，如"第一章 风云初起"

        Returns:
            (标签, 内容标题)
        """
        # 尝试匹配"第X章 标题"格式
        match = re.match(r"(第[一二三四五六七八九十百千万零〇\d]+章)\s*(.*)", title)
        if match:
            return match.group(1), match.group(2)

        # 尝试匹配"Chapter X: Title"格式
        match = re.match(r"(Chapter\s+\d+)[:\s]*(.*)", title, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)

        # 无法拆分，返回原标题
        return title, ""

    def _post_process_chapters(
        self, chapters: List[ParsedChapter]
    ) -> List[ParsedChapter]:
        """后处理章节列表

        - 检测超长/超短章节
        - 分配排序索引

        Args:
            chapters: 原始章节列表

        Returns:
            处理后的章节列表
        """
        if not chapters:
            return chapters

        # 计算统计信息
        lengths = [c.char_count for c in chapters]
        avg_length = sum(lengths) / len(lengths)
        std_length = (sum((x - avg_length) ** 2 for x in lengths) / len(lengths)) ** 0.5

        # 标记异常章节
        for chapter in chapters:
            warnings = []

            # 超长章节
            if chapter.char_count > avg_length + 3 * std_length:
                warnings.append(f"Chapter unusually long ({chapter.char_count} chars)")

            # 超短章节
            if (
                chapter.char_count < avg_length - 3 * std_length
                or chapter.char_count < 100
            ):
                warnings.append(f"Chapter unusually short ({chapter.char_count} chars)")

            chapter.warnings = warnings

        # 重新分配索引（考虑章节类型排序）
        sorted_chapters = sorted(
            chapters,
            key=lambda c: (
                c.chapter_type.value != ChapterType.PROLOGUE.value,
                c.chapter_type.value != ChapterType.STANDARD.value,
                c.chapter_type.value != ChapterType.INTERLUDE.value,
                c.chapter_type.value != ChapterType.EPILOGUE.value,
                c.chapter_type.value != ChapterType.EXTRA.value,
                c.start_pos,
            ),
        )

        for i, chapter in enumerate(sorted_chapters):
            chapter.index = i

        return sorted_chapters

    def _generate_result(
        self, chapters: List[ParsedChapter], patterns: List[str]
    ) -> ParseResult:
        """生成解析结果统计

        Args:
            chapters: 章节列表
            patterns: 使用的模式

        Returns:
            解析结果
        """
        if not chapters:
            return ParseResult(
                chapters=[],
                total_chars=0,
                avg_chapter_length=0,
                min_chapter_length=0,
                max_chapter_length=0,
                patterns_used=patterns,
                special_chapters={},
                warnings=["No chapters found"],
            )

        lengths = [c.char_count for c in chapters]

        # 统计特殊章节
        special_counts = {}
        for c in chapters:
            if c.chapter_type != ChapterType.STANDARD:
                type_name = c.chapter_type.value
                special_counts[type_name] = special_counts.get(type_name, 0) + 1

        # 收集所有警告
        all_warnings = []
        for c in chapters:
            all_warnings.extend(c.warnings)

        return ParseResult(
            chapters=chapters,
            total_chars=sum(lengths),
            avg_chapter_length=sum(lengths) / len(lengths),
            min_chapter_length=min(lengths),
            max_chapter_length=max(lengths),
            patterns_used=patterns,
            special_chapters=special_counts,
            warnings=list(set(all_warnings)),  # 去重
        )


async def parse_chapters(
    text: str, llm_config: Optional[LLMConfig] = None, use_ai: bool = True
) -> ParseResult:
    """便捷函数：解析章节

    Args:
        text: 要解析的文本
        llm_config: LLM 配置
        use_ai: 是否使用 AI

    Returns:
        解析结果
    """
    parser = AIChapterParser(llm_config, use_ai)
    return await parser.parse(text, enable_ai=use_ai)
