# -*- coding: utf-8 -*-
# @file range_selector.py
# @brief Text Range Selector Service
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from sail_server.infrastructure.orm.text import DocumentNode, Edition
from sail_server.application.dto.analysis import (
    TextRangeSelection,
    TextRangePreview,
    TextRangeContent,
    RangeSelectionMode,
)


# ============================================================================
# Token Estimation
# ============================================================================

class TokenEstimator:
    """Token 估算器
    
    基于字符数估算 token 数量，不同语言有不同的比例：
    - 中文：约 1 token / 1.5 字符
    - 英文：约 1 token / 4 字符
    """
    
    # 语言特定的 token 比例（字符数 / token数）
    LANGUAGE_RATIOS = {
        "zh": 1.5,      # 中文
        "zh_cn": 1.5,
        "zh_tw": 1.5,
        "en": 4.0,      # 英文
        "ja": 1.8,      # 日文
        "ko": 1.8,      # 韩文
        "default": 2.0,  # 默认
    }
    
    @classmethod
    def estimate(cls, text: str, language: str = "zh") -> int:
        """估算文本的 token 数量
        
        Args:
            text: 输入文本
            language: 语言代码
            
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0
        
        ratio = cls.LANGUAGE_RATIOS.get(language, cls.LANGUAGE_RATIOS["default"])
        char_count = len(text)
        return int(char_count / ratio)
    
    @classmethod
    def estimate_batch(cls, texts: List[str], language: str = "zh") -> int:
        """批量估算多个文本的 token 数量
        
        Args:
            texts: 文本列表
            language: 语言代码
            
        Returns:
            总 token 数量
        """
        return sum(cls.estimate(text, language) for text in texts if text)


# ============================================================================
# Text Range Parser
# ============================================================================

class TextRangeParser:
    """文本范围解析器
    
    处理各种范围选择逻辑，支持6种选择模式：
    1. single_chapter: 单章选择
    2. chapter_range: 连续章节范围
    3. multi_chapter: 多章选择（不连续）
    4. full_edition: 整部作品
    5. current_to_end: 从当前到结尾
    6. custom_range: 自定义范围
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_edition(self, edition_id: int) -> Optional[Edition]:
        """获取版本信息"""
        return self.db.query(Edition).filter(Edition.id == edition_id).first()
    
    def _get_chapters(self, edition_id: int) -> List[DocumentNode]:
        """获取版本的所有章节（按 sort_index 排序）"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter"
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )
    
    def _get_chapter_by_index(self, edition_id: int, index: int) -> Optional[DocumentNode]:
        """通过索引获取章节"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index == index
            )
            .first()
        )
    
    def _get_chapters_by_indices(
        self, edition_id: int, indices: List[int]
    ) -> List[DocumentNode]:
        """通过索引列表获取多个章节"""
        if not indices:
            return []
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index.in_(indices)
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )
    
    def _get_chapters_by_range(
        self, edition_id: int, start_index: int, end_index: int
    ) -> List[DocumentNode]:
        """获取连续章节范围"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index >= start_index,
                DocumentNode.sort_index <= end_index
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )
    
    def _get_chapters_from_start(
        self, edition_id: int, start_index: int
    ) -> List[DocumentNode]:
        """从指定索引获取到结尾的所有章节"""
        return (
            self.db.query(DocumentNode)
            .filter(
                DocumentNode.edition_id == edition_id,
                DocumentNode.node_type == "chapter",
                DocumentNode.sort_index >= start_index
            )
            .order_by(DocumentNode.sort_index)
            .all()
        )
    
    def _get_nodes_by_ids(self, node_ids: List[int]) -> List[DocumentNode]:
        """通过节点ID列表获取节点"""
        if not node_ids:
            return []
        return (
            self.db.query(DocumentNode)
            .filter(DocumentNode.id.in_(node_ids))
            .order_by(DocumentNode.sort_index)
            .all()
        )
    
    def _validate_selection(self, selection: TextRangeSelection) -> List[str]:
        """验证选择参数，返回警告信息列表"""
        warnings = []
        
        # 验证版本存在
        edition = self._get_edition(selection.edition_id)
        if not edition:
            warnings.append(f"版本 ID {selection.edition_id} 不存在")
            return warnings
        
        # 获取所有章节
        all_chapters = self._get_chapters(selection.edition_id)
        if not all_chapters:
            warnings.append("该版本没有章节")
            return warnings
        
        max_index = max(ch.sort_index for ch in all_chapters)
        
        # 根据模式验证
        if selection.mode == RangeSelectionMode.SINGLE_CHAPTER:
            if selection.chapter_index is None:
                warnings.append("单章选择需要指定 chapter_index")
            elif selection.chapter_index < 0 or selection.chapter_index > max_index:
                warnings.append(
                    f"章节索引 {selection.chapter_index} 超出范围 (0-{max_index})"
                )
        
        elif selection.mode == RangeSelectionMode.CHAPTER_RANGE:
            if selection.start_index is None or selection.end_index is None:
                warnings.append("章节范围选择需要指定 start_index 和 end_index")
            else:
                if selection.start_index < 0 or selection.start_index > max_index:
                    warnings.append(
                        f"起始索引 {selection.start_index} 超出范围 (0-{max_index})"
                    )
                if selection.end_index < 0 or selection.end_index > max_index:
                    warnings.append(
                        f"结束索引 {selection.end_index} 超出范围 (0-{max_index})"
                    )
                if selection.start_index > selection.end_index:
                    warnings.append(
                        f"起始索引 {selection.start_index} 大于结束索引 {selection.end_index}"
                    )
        
        elif selection.mode == RangeSelectionMode.MULTI_CHAPTER:
            if not selection.chapter_indices:
                warnings.append("多章选择需要指定 chapter_indices")
            else:
                invalid_indices = [
                    idx for idx in selection.chapter_indices
                    if idx < 0 or idx > max_index
                ]
                if invalid_indices:
                    warnings.append(
                        f"以下章节索引超出范围: {invalid_indices} (有效范围: 0-{max_index})"
                    )
        
        elif selection.mode == RangeSelectionMode.CURRENT_TO_END:
            if selection.start_index is None:
                warnings.append("从当前到结尾选择需要指定 start_index")
            elif selection.start_index < 0 or selection.start_index > max_index:
                warnings.append(
                    f"起始索引 {selection.start_index} 超出范围 (0-{max_index})"
                )
        
        elif selection.mode == RangeSelectionMode.CUSTOM_RANGE:
            if not selection.node_ids:
                warnings.append("自定义范围需要指定 node_ids")
        
        return warnings
    
    def _get_selected_chapters(
        self, selection: TextRangeSelection
    ) -> List[DocumentNode]:
        """根据选择模式获取选中的章节列表"""
        
        if selection.mode == RangeSelectionMode.SINGLE_CHAPTER:
            if selection.chapter_index is not None:
                chapter = self._get_chapter_by_index(
                    selection.edition_id, selection.chapter_index
                )
                return [chapter] if chapter else []
            return []
        
        elif selection.mode == RangeSelectionMode.CHAPTER_RANGE:
            if selection.start_index is not None and selection.end_index is not None:
                return self._get_chapters_by_range(
                    selection.edition_id, selection.start_index, selection.end_index
                )
            return []
        
        elif selection.mode == RangeSelectionMode.MULTI_CHAPTER:
            if selection.chapter_indices:
                return self._get_chapters_by_indices(
                    selection.edition_id, selection.chapter_indices
                )
            return []
        
        elif selection.mode == RangeSelectionMode.FULL_EDITION:
            return self._get_chapters(selection.edition_id)
        
        elif selection.mode == RangeSelectionMode.CURRENT_TO_END:
            if selection.start_index is not None:
                return self._get_chapters_from_start(
                    selection.edition_id, selection.start_index
                )
            return []
        
        elif selection.mode == RangeSelectionMode.CUSTOM_RANGE:
            if selection.node_ids:
                return self._get_nodes_by_ids(selection.node_ids)
            return []
        
        return []
    
    def _calculate_stats(
        self, chapters: List[DocumentNode], language: str = "zh"
    ) -> Tuple[int, int, int]:
        """计算统计信息
        
        Returns:
            (总字符数, 总词数, 预估token数)
        """
        total_chars = sum(ch.char_count or 0 for ch in chapters)
        total_words = sum(ch.word_count or 0 for ch in chapters)
        
        # 估算 token
        all_text = " ".join(ch.raw_text or "" for ch in chapters)
        estimated_tokens = TokenEstimator.estimate(all_text, language)
        
        return total_chars, total_words, estimated_tokens
    
    def preview(self, selection: TextRangeSelection) -> TextRangePreview:
        """预览选中的文本范围
        
        Args:
            selection: 范围选择参数
            
        Returns:
            预览结果
        """
        # 验证选择
        warnings = self._validate_selection(selection)
        
        # 获取选中的章节
        chapters = self._get_selected_chapters(selection)
        
        # 获取版本语言
        edition = self._get_edition(selection.edition_id)
        language = edition.language if edition else "zh"
        
        # 计算统计信息
        total_chars, total_words, estimated_tokens = self._calculate_stats(
            chapters, language
        )
        
        # 构建章节信息列表
        selected_chapters = [
            {
                "id": ch.id,
                "sort_index": ch.sort_index,
                "label": ch.label,
                "title": ch.title,
                "char_count": ch.char_count,
                "word_count": ch.word_count,
            }
            for ch in chapters
        ]
        
        # 生成预览文本（前500个字符）
        preview_text = None
        if chapters:
            first_chapter = chapters[0]
            if first_chapter.raw_text:
                preview_text = first_chapter.raw_text[:500]
                if len(first_chapter.raw_text) > 500:
                    preview_text += "..."
        
        return TextRangePreview(
            edition_id=selection.edition_id,
            mode=selection.mode,
            chapter_count=len(chapters),
            total_chars=total_chars,
            total_words=total_words,
            estimated_tokens=estimated_tokens,
            selected_chapters=selected_chapters,
            preview_text=preview_text,
            warnings=warnings,
            meta_data={
                "language": language,
                "selection_params": {
                    "chapter_index": selection.chapter_index,
                    "start_index": selection.start_index,
                    "end_index": selection.end_index,
                    "chapter_indices": selection.chapter_indices,
                    "node_ids": selection.node_ids,
                }
            }
        )
    
    def get_content(self, selection: TextRangeSelection) -> TextRangeContent:
        """获取选中的文本内容
        
        Args:
            selection: 范围选择参数
            
        Returns:
            内容结果
        """
        # 获取选中的章节
        chapters = self._get_selected_chapters(selection)
        
        # 获取版本语言
        edition = self._get_edition(selection.edition_id)
        language = edition.language if edition else "zh"
        
        # 计算统计信息
        total_chars, total_words, estimated_tokens = self._calculate_stats(
            chapters, language
        )
        
        # 构建完整文本
        chapter_contents = []
        full_text_parts = []
        
        for ch in chapters:
            chapter_text = ch.raw_text or ""
            chapter_info = {
                "id": ch.id,
                "sort_index": ch.sort_index,
                "label": ch.label,
                "title": ch.title,
                "char_count": ch.char_count,
                "word_count": ch.word_count,
                "content": chapter_text,
            }
            chapter_contents.append(chapter_info)
            
            # 添加章节标题到完整文本
            header = ""
            if ch.label:
                header += ch.label
            if ch.title:
                header += " " + ch.title if header else ch.title
            if header:
                header += "\n\n"
            
            full_text_parts.append(header + chapter_text)
        
        full_text = "\n\n".join(full_text_parts)
        
        return TextRangeContent(
            edition_id=selection.edition_id,
            mode=selection.mode,
            full_text=full_text,
            chapters=chapter_contents,
            chapter_count=len(chapters),
            total_chars=total_chars,
            total_words=total_words,
            estimated_tokens=estimated_tokens,
            meta_data={
                "language": language,
                "chapter_ids": [ch.id for ch in chapters],
            }
        )


# ============================================================================
# Utility Functions
# ============================================================================

def create_range_selection(
    edition_id: int,
    mode: RangeSelectionMode,
    **kwargs
) -> TextRangeSelection:
    """创建范围选择的便捷函数
    
    Args:
        edition_id: 版本ID
        mode: 选择模式
        **kwargs: 模式特定的参数
        
    Returns:
        TextRangeSelection 对象
    """
    return TextRangeSelection(
        edition_id=edition_id,
        mode=mode,
        chapter_index=kwargs.get("chapter_index"),
        start_index=kwargs.get("start_index"),
        end_index=kwargs.get("end_index"),
        chapter_indices=kwargs.get("chapter_indices", []),
        node_ids=kwargs.get("node_ids", []),
        meta_data=kwargs.get("meta_data", {}),
    )


def suggest_optimal_range(
    db: Session,
    edition_id: int,
    target_tokens: int = 4000,
    start_index: int = 0
) -> TextRangeSelection:
    """建议最优的文本范围
    
    根据目标 token 数量，建议一个合适的章节范围。
    
    Args:
        db: 数据库会话
        edition_id: 版本ID
        target_tokens: 目标 token 数量
        start_index: 起始章节索引
        
    Returns:
        建议的范围选择
    """
    parser = TextRangeParser(db)
    
    # 获取从起始索引开始的所有章节
    chapters = parser._get_chapters_from_start(edition_id, start_index)
    
    if not chapters:
        return create_range_selection(
            edition_id, RangeSelectionMode.SINGLE_CHAPTER, chapter_index=start_index
        )
    
    # 逐个添加章节，直到达到目标 token 数
    current_tokens = 0
    end_index = start_index
    
    for ch in chapters:
        ch_tokens = TokenEstimator.estimate(ch.raw_text or "", "zh")
        
        if current_tokens + ch_tokens > target_tokens and current_tokens > 0:
            break
        
        current_tokens += ch_tokens
        end_index = ch.sort_index
    
    # 如果只有一个章节，使用单章模式
    if end_index == start_index:
        return create_range_selection(
            edition_id, RangeSelectionMode.SINGLE_CHAPTER, chapter_index=start_index
        )
    
    return create_range_selection(
        edition_id,
        RangeSelectionMode.CHAPTER_RANGE,
        start_index=start_index,
        end_index=end_index
    )
