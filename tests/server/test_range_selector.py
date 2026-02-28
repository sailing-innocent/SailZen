# -*- coding: utf-8 -*-
# @file test_range_selector.py
# @brief Text Range Selector Tests
# @author sailing-innocent
# @date 2025-02-28
# @version 1.0
# ---------------------------------

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from sail_server.service.range_selector import (
    TokenEstimator,
    TextRangeParser,
    create_range_selection,
    suggest_optimal_range,
)
from sail_server.data.analysis import (
    TextRangeSelection,
    TextRangePreview,
    TextRangeContent,
    RangeSelectionMode,
)
from sail_server.data.text import DocumentNode, Edition


# ============================================================================
# Token Estimator Tests
# ============================================================================

class TestTokenEstimator:
    """Token 估算器测试"""
    
    def test_estimate_chinese(self):
        """测试中文文本 token 估算"""
        text = "这是一段中文文本，用于测试 token 估算功能。"
        tokens = TokenEstimator.estimate(text, "zh")
        # 中文字符数 / 1.5
        expected = int(len(text) / 1.5)
        assert tokens == expected
    
    def test_estimate_english(self):
        """测试英文文本 token 估算"""
        text = "This is an English text for testing token estimation."
        tokens = TokenEstimator.estimate(text, "en")
        # 英文字符数 / 4
        expected = int(len(text) / 4)
        assert tokens == expected
    
    def test_estimate_empty(self):
        """测试空文本"""
        assert TokenEstimator.estimate("", "zh") == 0
        assert TokenEstimator.estimate(None, "zh") == 0
    
    def test_estimate_batch(self):
        """测试批量估算"""
        texts = ["中文文本", "English text", "更多中文"]
        total = TokenEstimator.estimate_batch(texts, "zh")
        expected = sum(TokenEstimator.estimate(t, "zh") for t in texts)
        assert total == expected
    
    def test_estimate_default_language(self):
        """测试默认语言"""
        text = "测试文本"
        tokens = TokenEstimator.estimate(text)  # 使用默认语言
        assert tokens > 0


# ============================================================================
# Text Range Parser Tests
# ============================================================================

def create_mock_query_result(return_value):
    """创建模拟查询结果"""
    mock_query = Mock()
    mock_filter = Mock()
    mock_filter2 = Mock()
    mock_filter3 = Mock()
    mock_order_by = Mock()
    
    mock_query.return_value = mock_filter
    mock_filter.return_value = mock_filter
    mock_filter.filter.return_value = mock_filter2
    mock_filter2.filter.return_value = mock_filter2
    mock_filter2.order_by.return_value = mock_order_by
    mock_order_by.all.return_value = return_value if isinstance(return_value, list) else []
    mock_order_by.first.return_value = return_value if not isinstance(return_value, list) else None
    
    return mock_query


class TestTextRangeParser:
    """文本范围解析器测试"""
    
    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库会话"""
        return Mock()
    
    @pytest.fixture
    def mock_edition(self):
        """创建模拟版本"""
        edition = Mock(spec=Edition)
        edition.id = 1
        edition.language = "zh"
        return edition
    
    @pytest.fixture
    def mock_chapters(self):
        """创建模拟章节列表"""
        chapters = []
        for i in range(10):
            chapter = Mock(spec=DocumentNode)
            chapter.id = i + 1
            chapter.sort_index = i
            chapter.label = f"第{i+1}章"
            chapter.title = f"章节标题{i+1}"
            chapter.raw_text = f"这是第{i+1}章的内容，用于测试。" * 10
            chapter.char_count = len(chapter.raw_text)
            chapter.word_count = chapter.char_count // 2
            chapters.append(chapter)
        return chapters
    
    def _setup_mock_db(self, mock_db, edition, chapters):
        """设置模拟数据库返回值"""
        # 创建 mock query 链
        def mock_query(*args, **kwargs):
            return mock_filter
        
        mock_filter = Mock()
        mock_filter2 = Mock()
        mock_filter3 = Mock()
        mock_order_by = Mock()
        
        mock_db.query = mock_query
        mock_query.return_value = mock_filter
        mock_filter.filter.return_value = mock_filter
        mock_filter.first.return_value = edition
        
        # 设置章节查询
        def setup_chapter_query(return_value):
            mock_filter.filter.return_value = mock_filter2
            mock_filter2.filter.return_value = mock_filter2
            mock_filter2.order_by.return_value = mock_order_by
            if isinstance(return_value, list):
                mock_order_by.all.return_value = return_value
            else:
                mock_order_by.first.return_value = return_value
        
        # 保存设置函数供测试使用
        mock_db._setup_chapter_query = setup_chapter_query
        mock_db._chapters = chapters
        mock_db._edition = edition
        
        return mock_filter, mock_filter2, mock_order_by
    
    def test_single_chapter_selection(self, mock_db, mock_edition, mock_chapters):
        """测试单章选择"""
        parser = TextRangeParser(mock_db)
        
        # 使用 patch 来模拟数据库查询
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapter_by_index', return_value=mock_chapters[0]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.SINGLE_CHAPTER,
                        chapter_index=0
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.edition_id == 1
                    assert result.mode == RangeSelectionMode.SINGLE_CHAPTER
                    assert result.chapter_count == 1
                    assert len(result.selected_chapters) == 1
                    assert result.selected_chapters[0]['sort_index'] == 0
    
    def test_chapter_range_selection(self, mock_db, mock_edition, mock_chapters):
        """测试连续章节范围选择"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapters_by_range', return_value=mock_chapters[2:5]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.CHAPTER_RANGE,
                        start_index=2,
                        end_index=4
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.chapter_count == 3
                    assert result.mode == RangeSelectionMode.CHAPTER_RANGE
    
    def test_multi_chapter_selection(self, mock_db, mock_edition, mock_chapters):
        """测试多章选择（不连续）"""
        parser = TextRangeParser(mock_db)
        
        selected_chapters = [mock_chapters[0], mock_chapters[2], mock_chapters[4]]
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapters_by_indices', return_value=selected_chapters):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.MULTI_CHAPTER,
                        chapter_indices=[0, 2, 4]
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.chapter_count == 3
                    assert result.mode == RangeSelectionMode.MULTI_CHAPTER
    
    def test_full_edition_selection(self, mock_db, mock_edition, mock_chapters):
        """测试整部作品选择"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                selection = TextRangeSelection(
                    edition_id=1,
                    mode=RangeSelectionMode.FULL_EDITION
                )
                
                result = parser.preview(selection)
                
                assert result.chapter_count == len(mock_chapters)
                assert result.mode == RangeSelectionMode.FULL_EDITION
    
    def test_current_to_end_selection(self, mock_db, mock_edition, mock_chapters):
        """测试从当前到结尾选择"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapters_from_start', return_value=mock_chapters[5:]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.CURRENT_TO_END,
                        start_index=5
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.chapter_count == 5  # 第6章到第10章
                    assert result.mode == RangeSelectionMode.CURRENT_TO_END
    
    def test_invalid_chapter_index(self, mock_db, mock_edition, mock_chapters):
        """测试无效章节索引验证"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapter_by_index', return_value=None):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.SINGLE_CHAPTER,
                        chapter_index=100  # 超出范围
                    )
                    
                    result = parser.preview(selection)
                    
                    assert len(result.warnings) > 0
                    assert any("超出范围" in w for w in result.warnings)
    
    def test_invalid_range(self, mock_db, mock_edition, mock_chapters):
        """测试无效范围（起始大于结束）"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapters_by_range', return_value=[]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.CHAPTER_RANGE,
                        start_index=5,
                        end_index=2
                    )
                    
                    result = parser.preview(selection)
                    
                    assert len(result.warnings) > 0
                    assert any("大于结束索引" in w for w in result.warnings)
    
    def test_content_retrieval(self, mock_db, mock_edition, mock_chapters):
        """测试内容获取"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapter_by_index', return_value=mock_chapters[0]):
                selection = TextRangeSelection(
                    edition_id=1,
                    mode=RangeSelectionMode.SINGLE_CHAPTER,
                    chapter_index=0
                )
                
                result = parser.get_content(selection)
                
                assert result.edition_id == 1
                assert result.mode == RangeSelectionMode.SINGLE_CHAPTER
                assert result.full_text is not None
                assert len(result.chapters) == 1
                assert result.chapters[0]['content'] == mock_chapters[0].raw_text
    
    def test_preview_text_generation(self, mock_db, mock_edition, mock_chapters):
        """测试预览文本生成"""
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=mock_chapters):
                with patch.object(parser, '_get_chapter_by_index', return_value=mock_chapters[0]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.SINGLE_CHAPTER,
                        chapter_index=0
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.preview_text is not None
                    assert len(result.preview_text) <= 503  # 500 + "..."


# ============================================================================
# Utility Function Tests
# ============================================================================

class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_create_range_selection_single_chapter(self):
        """测试创建单章选择"""
        selection = create_range_selection(
            1,
            RangeSelectionMode.SINGLE_CHAPTER,
            chapter_index=5
        )
        
        assert selection.edition_id == 1
        assert selection.mode == RangeSelectionMode.SINGLE_CHAPTER
        assert selection.chapter_index == 5
    
    def test_create_range_selection_chapter_range(self):
        """测试创建章节范围选择"""
        selection = create_range_selection(
            1,
            RangeSelectionMode.CHAPTER_RANGE,
            start_index=2,
            end_index=5
        )
        
        assert selection.start_index == 2
        assert selection.end_index == 5
    
    def test_create_range_selection_multi_chapter(self):
        """测试创建多章选择"""
        selection = create_range_selection(
            1,
            RangeSelectionMode.MULTI_CHAPTER,
            chapter_indices=[0, 2, 4, 6]
        )
        
        assert selection.chapter_indices == [0, 2, 4, 6]
    
    def test_suggest_optimal_range(self):
        """测试建议最优范围"""
        mock_db = Mock()
        
        # 创建模拟章节
        chapters = []
        for i in range(20):
            chapter = Mock(spec=DocumentNode)
            chapter.sort_index = i
            chapter.raw_text = "测试内容" * 100  # 约600字符
            chapters.append(chapter)
        
        with patch('sail_server.service.range_selector.TextRangeParser') as MockParser:
            mock_parser = Mock()
            mock_parser._get_chapters_from_start.return_value = chapters
            MockParser.return_value = mock_parser
            
            result = suggest_optimal_range(mock_db, 1, target_tokens=2000, start_index=0)
            
            assert result.edition_id == 1
            assert result.mode in [RangeSelectionMode.SINGLE_CHAPTER, RangeSelectionMode.CHAPTER_RANGE]


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_chapter_list(self):
        """测试空章节列表"""
        mock_db = Mock()
        parser = TextRangeParser(mock_db)
        
        mock_edition = Mock(spec=Edition)
        mock_edition.language = "zh"
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=[]):
                selection = TextRangeSelection(
                    edition_id=1,
                    mode=RangeSelectionMode.FULL_EDITION
                )
                
                result = parser.preview(selection)
                
                assert result.chapter_count == 0
                assert len(result.warnings) > 0
                assert any("没有章节" in w for w in result.warnings)
    
    def test_nonexistent_edition(self):
        """测试不存在的版本"""
        mock_db = Mock()
        parser = TextRangeParser(mock_db)
        
        with patch.object(parser, '_get_edition', return_value=None):
            with patch.object(parser, '_get_selected_chapters', return_value=[]):
                selection = TextRangeSelection(
                    edition_id=999,
                    mode=RangeSelectionMode.SINGLE_CHAPTER,
                    chapter_index=0
                )
                
                result = parser.preview(selection)
                
                assert len(result.warnings) > 0
                assert any("不存在" in w for w in result.warnings)
    
    def test_negative_index(self):
        """测试负索引"""
        mock_db = Mock()
        parser = TextRangeParser(mock_db)
        
        mock_edition = Mock(spec=Edition)
        mock_edition.language = "zh"
        
        # 创建一些模拟章节用于验证
        chapters = []
        for i in range(5):
            chapter = Mock(spec=DocumentNode)
            chapter.sort_index = i
            chapters.append(chapter)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=chapters):
                with patch.object(parser, '_get_chapter_by_index', return_value=None):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.SINGLE_CHAPTER,
                        chapter_index=-1
                    )
                    
                    result = parser.preview(selection)
                    
                    assert len(result.warnings) > 0
    
    def test_empty_multi_selection(self):
        """测试空的多章选择"""
        mock_db = Mock()
        parser = TextRangeParser(mock_db)
        
        mock_edition = Mock(spec=Edition)
        mock_edition.language = "zh"
        
        # 创建一些模拟章节用于验证
        chapters = []
        for i in range(5):
            chapter = Mock(spec=DocumentNode)
            chapter.sort_index = i
            chapters.append(chapter)
        
        with patch.object(parser, '_get_edition', return_value=mock_edition):
            with patch.object(parser, '_get_chapters', return_value=chapters):
                with patch.object(parser, '_get_chapters_by_indices', return_value=[]):
                    selection = TextRangeSelection(
                        edition_id=1,
                        mode=RangeSelectionMode.MULTI_CHAPTER,
                        chapter_indices=[]
                    )
                    
                    result = parser.preview(selection)
                    
                    assert result.chapter_count == 0
                    assert len(result.warnings) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
