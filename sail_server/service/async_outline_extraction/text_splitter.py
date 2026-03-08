# -*- coding: utf-8 -*-
# @file text_splitter.py
# @brief Text splitting with hierarchical levels
# @author sailing-innocent
# @date 2026-03-08
# @version 1.0
# ---------------------------------

"""文本切分器

支持多级切分：Text → Chunks → Segments → Chapter(s)
"""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .types import Task, TaskLevel, ExtractionConfig


@dataclass
class TextChunk:
    """文本片段"""

    text: str
    index: int
    start_pos: int
    end_pos: int
    overlap_prev: str = ""  # 与前一片段的重叠部分
    overlap_next: str = ""  # 与后一片段的重叠部分


class TextSplitter:
    """文本切分器

    将长文本切分为多级结构：
    - Level 0: Chunks (基本处理单元)
    - Level 1: Segments (包含多个 chunks)
    - Level 2: Chapters (包含多个 segments)
    """

    # 中文 token 估算比例（约 1 token = 1.5 中文字符或 4 英文字符）
    CHARS_PER_TOKEN_CN = 1.5
    CHARS_PER_TOKEN_EN = 4

    def __init__(self, config: ExtractionConfig):
        self.config = config

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数

        使用简单启发式：
        - 中文字符按 1/1.5 计算
        - 非中文字符按 1/4 计算
        """
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - cn_chars

        tokens = int(
            cn_chars / self.CHARS_PER_TOKEN_CN + other_chars / self.CHARS_PER_TOKEN_EN
        )
        return max(1, tokens)

    def split_into_chunks(self, text: str) -> List[TextChunk]:
        """将文本切分为 chunks

        使用滑动窗口，确保每个 chunk 的 token 数不超过限制
        保持句子边界完整
        """
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        chunks = []
        start = 0
        index = 0

        while start < len(text):
            # 计算当前 chunk 的结束位置
            end = self._find_chunk_end(text, start, chunk_size)

            # 创建 chunk
            chunk_text = text[start:end]

            # 计算重叠部分
            overlap_prev = ""
            overlap_next = ""

            if index > 0:
                # 前一片段的重叠部分（当前 chunk 的开头）
                overlap_start = max(0, start - overlap)
                overlap_prev = text[overlap_start:start]

            if end < len(text):
                # 后一片段的重叠部分（当前 chunk 的结尾）
                overlap_end = min(len(text), end + overlap)
                overlap_next = text[end:overlap_end]

            chunks.append(
                TextChunk(
                    text=chunk_text,
                    index=index,
                    start_pos=start,
                    end_pos=end,
                    overlap_prev=overlap_prev,
                    overlap_next=overlap_next,
                )
            )

            # 移动窗口（考虑重叠）
            if end >= len(text):
                break

            # 下一个 chunk 的起始位置（减去 overlap）
            next_start = end - overlap
            if next_start <= start:
                next_start = end  # 避免死循环

            start = next_start
            index += 1

        return chunks

    def _find_chunk_end(self, text: str, start: int, max_tokens: int) -> int:
        """找到 chunk 的合适结束位置

        优先在句子边界结束，如果找不到则在词边界
        """
        # 估算最大字符数
        max_chars = int(max_tokens * self.CHARS_PER_TOKEN_CN)

        # 初始结束位置
        end = min(start + max_chars, len(text))

        if end >= len(text):
            return len(text)

        # 尝试找到句子边界（句号、问号、感叹号）
        sentence_end = self._find_sentence_boundary(text, start, end)
        if sentence_end > start:
            return sentence_end

        # 尝试找到段落边界（换行符）
        para_end = text.find("\n\n", start, end)
        if para_end != -1:
            return para_end + 2

        # 尝试找到空格或标点
        for i in range(end - 1, start, -1):
            if text[i] in ' 。，！？；：""（）【】':
                return i + 1

        # fallback：直接截断
        return end

    def _find_sentence_boundary(self, text: str, start: int, max_end: int) -> int:
        """找到句子边界"""
        sentence_endings = "。！？.!?"

        # 在范围内找最后一个句子结束符
        for i in range(max_end - 1, start, -1):
            if text[i] in sentence_endings:
                # 确保不是省略号
                if text[i] == "." and i > start and text[i - 1] == ".":
                    continue
                return i + 1

        return -1

    def group_into_segments(self, chunks: List[TextChunk]) -> List[List[TextChunk]]:
        """将 chunks 分组为 segments"""
        chunks_per_segment = self.config.chunks_per_segment

        segments = []
        for i in range(0, len(chunks), chunks_per_segment):
            segment = chunks[i : i + chunks_per_segment]
            segments.append(segment)

        return segments

    def build_task_graph(
        self, text: str, work_id: str, chapter_id: Optional[str] = None
    ) -> Tuple[List[Task], List[Task], List[Task]]:
        """构建任务图

        返回：(chunk_tasks, segment_tasks, chapter_tasks)
        """
        # 1. 切分 chunks
        chunks = self.split_into_chunks(text)

        # 2. 分组为 segments
        segments = self.group_into_segments(chunks)

        chunk_tasks = []
        segment_tasks = []

        # 3. 创建 chunk 任务
        for chunk in chunks:
            task = Task(
                level=TaskLevel.CHUNK,
                index=chunk.index,
                text=chunk.text,
                dependencies=[],
                context={
                    "work_id": work_id,
                    "chapter_id": chapter_id,
                    "start_pos": chunk.start_pos,
                    "end_pos": chunk.end_pos,
                    "overlap_prev": chunk.overlap_prev,
                    "overlap_next": chunk.overlap_next,
                },
            )
            chunk_tasks.append(task)

        # 4. 创建 segment 任务
        for seg_idx, segment_chunks in enumerate(segments):
            # segment 依赖于其包含的所有 chunks
            chunk_ids = [chunk_tasks[c.index].id for c in segment_chunks]

            # 构建 segment 文本（去重）
            segment_text = self._build_segment_text(segment_chunks)

            # 获取上下文（前一个 segment 的摘要）
            context_summary = ""
            if seg_idx > 0:
                prev_seg_chunks = segments[seg_idx - 1]
                # 取前一个 segment 的最后一段作为上下文
                context_summary = (
                    prev_seg_chunks[-1].text[-500:] if prev_seg_chunks else ""
                )

            task = Task(
                level=TaskLevel.SEGMENT,
                index=seg_idx,
                text=segment_text,
                dependencies=chunk_ids,
                context={
                    "work_id": work_id,
                    "chapter_id": chapter_id,
                    "chunk_indices": [c.index for c in segment_chunks],
                    "context_summary": context_summary,
                    "start_pos": segment_chunks[0].start_pos,
                    "end_pos": segment_chunks[-1].end_pos,
                },
            )
            segment_tasks.append(task)

        # 5. 创建 chapter 任务
        chapter_tasks = []
        if segment_tasks:
            chapter_task = Task(
                level=TaskLevel.CHAPTER,
                index=0,
                text=text[:2000] + "...",  # 摘要
                dependencies=[t.id for t in segment_tasks],
                context={
                    "work_id": work_id,
                    "chapter_id": chapter_id,
                    "segment_count": len(segment_tasks),
                    "chunk_count": len(chunk_tasks),
                },
            )
            chapter_tasks.append(chapter_task)

        return chunk_tasks, segment_tasks, chapter_tasks

    def _build_segment_text(self, chunks: List[TextChunk]) -> str:
        """构建 segment 文本，处理重叠部分"""
        if not chunks:
            return ""

        # 简单连接（后续在合并时处理去重）
        texts = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                texts.append(chunk.text)
            else:
                # 跳过与前一个 chunk 的重叠部分
                overlap = chunk.overlap_prev
                if overlap and chunk.text.startswith(overlap):
                    texts.append(chunk.text[len(overlap) :])
                else:
                    texts.append(chunk.text)

        return "\n".join(texts)
