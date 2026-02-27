# -*- coding: utf-8 -*-
# @file test_novel_analysis.py
# @brief Unit tests for Novel Analysis Agent
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from sail_server.agent.novel_analysis import (
    NovelAnalysisAgent,
    ChapterChunk,
    AnalysisResult,
)
from sail_server.agent.base import (
    AgentContext,
    AgentExecutionResult,
    ValidationResult,
    ProgressUpdate,
)
from sail_server.data.unified_agent import (
    UnifiedAgentTask,
    TaskType,
    TaskSubType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def agent():
    """创建 Agent 实例"""
    return NovelAnalysisAgent()


@pytest.fixture
def mock_context():
    """创建 Mock 上下文"""
    mock_db = MagicMock()
    mock_llm = AsyncMock()
    
    return AgentContext(
        db_session=mock_db,
        llm_gateway=mock_llm,
    )


@pytest.fixture
def mock_task():
    """创建 Mock 任务"""
    task = MagicMock(spec=UnifiedAgentTask)
    task.id = 1
    task.task_type = TaskType.NOVEL_ANALYSIS
    task.sub_type = TaskSubType.OUTLINE_EXTRACTION
    task.edition_id = 1
    task.target_node_ids = [1, 2, 3]
    task.config = {}
    task.llm_provider = "openai"
    task.llm_model = "gpt-4o-mini"
    task.prompt_template_id = None
    return task


# ============================================================================
# Test NovelAnalysisAgent Basic
# ============================================================================

class TestNovelAnalysisAgentBasic:
    """测试 NovelAnalysisAgent 基本功能"""
    
    def test_agent_type(self, agent):
        """测试 Agent 类型"""
        assert agent.agent_type == "novel_analysis"
    
    def test_agent_info(self, agent):
        """测试 Agent 信息"""
        info = agent.agent_info
        assert info.agent_type == "novel_analysis"
        assert "小说分析" in info.name
        assert TaskType.NOVEL_ANALYSIS in info.supported_task_types
    
    def test_validate_task_valid(self, agent, mock_task):
        """测试验证有效任务"""
        result = agent.validate_task(mock_task)
        assert result.valid is True
    
    def test_validate_task_missing_edition(self, agent, mock_task):
        """测试验证缺少 edition_id 的任务"""
        mock_task.edition_id = None
        mock_task.target_node_ids = None
        
        result = agent.validate_task(mock_task)
        assert result.valid is False
        assert any("edition_id" in e for e in result.errors)
    
    def test_validate_task_invalid_subtype(self, agent, mock_task):
        """测试验证无效 sub_type 的任务"""
        mock_task.sub_type = "invalid_type"
        
        result = agent.validate_task(mock_task)
        assert result.valid is False
        assert any("sub_type" in e for e in result.errors)
    
    def test_estimate_cost(self, agent, mock_task):
        """测试成本预估"""
        mock_task.config = {
            "estimated_chunks": 3,
            "tokens_per_chunk": 5000,
        }
        
        with patch('sail_server.utils.llm.pricing.get_pricing') as mock_pricing:
            mock_price = Mock()
            mock_price.calculate_cost.return_value = 0.015
            mock_pricing.return_value = mock_price
            
            estimate = agent.estimate_cost(mock_task)
            
            assert estimate.estimated_tokens > 0
            assert estimate.estimated_cost > 0
            assert "chunks" in estimate.breakdown


# ============================================================================
# Test Chapter Chunking
# ============================================================================

class TestChapterChunking:
    """测试章节分块"""
    
    @pytest.fixture
    def mock_nodes(self):
        """创建 Mock 章节节点"""
        nodes = []
        for i in range(5):
            node = Mock()
            node.id = i + 1
            node.title = f"Chapter {i+1}"
            # 生成适当长度的内容
            node.raw_text = f"Content of chapter {i+1}. " * 100
            nodes.append(node)
        return nodes
    
    @pytest.mark.asyncio
    async def test_prepare_chunks(self, agent, mock_task, mock_context, mock_nodes):
        """测试准备分块"""
        # Mock 数据库查询
        mock_context.db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_nodes
        
        chunks = await agent._prepare_chunks(mock_task, mock_context)
        
        assert len(chunks) > 0
        assert all(isinstance(c, ChapterChunk) for c in chunks)
        assert all(c.token_estimate > 0 for c in chunks)
    
    @pytest.mark.asyncio
    async def test_prepare_chunks_empty(self, agent, mock_task, mock_context):
        """测试空章节列表"""
        mock_context.db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        
        chunks = await agent._prepare_chunks(mock_task, mock_context)
        
        assert chunks == []
    
    def test_create_chunk(self, agent):
        """测试创建分块"""
        nodes = [Mock(id=1, title="Chapter 1")]
        chunk = agent._create_chunk(0, nodes, "Content", 100)
        
        assert chunk.index == 0
        assert chunk.node_ids == [1]
        assert chunk.chapter_range == "Chapter 1"
        assert chunk.content == "Content"
        assert chunk.token_estimate == 100


# ============================================================================
# Test Result Parsing
# ============================================================================

class TestResultParsing:
    """测试结果解析"""
    
    @pytest.fixture
    def mock_chunk(self):
        """创建 Mock 分块"""
        return ChapterChunk(
            index=0,
            node_ids=[1, 2],
            chapter_range="Chapter 1-2",
            content="Test content",
            token_estimate=1000,
        )
    
    def test_parse_outline(self, agent, mock_chunk):
        """测试解析大纲结果"""
        parsed = {
            "plot_points": [
                {
                    "title": "Event 1",
                    "type": "scene",
                    "summary": "Summary 1",
                    "importance": "high",
                    "characters": ["A", "B"],
                    "evidence": "Evidence 1",
                }
            ],
            "overall_summary": "Overall summary",
        }
        
        results = agent._parse_outline(parsed, mock_chunk)
        
        assert len(results) == 2  # 1 plot point + 1 summary
        assert results[0].result_type == "outline_node"
        assert results[1].result_type == "chunk_summary"
    
    def test_parse_characters(self, agent, mock_chunk):
        """测试解析人物结果"""
        parsed = {
            "characters": [
                {
                    "canonical_name": "Character A",
                    "aliases": ["Alias 1"],
                    "role_type": "protagonist",
                    "description": "Description",
                    "first_mention": "Chapter 1",
                    "actions": ["Action 1"],
                    "mention_count": 5,
                }
            ]
        }
        
        results = agent._parse_characters(parsed, mock_chunk)
        
        assert len(results) == 1
        assert results[0].result_type == "character"
        assert results[0].data["canonical_name"] == "Character A"
    
    def test_parse_settings(self, agent, mock_chunk):
        """测试解析设定结果"""
        parsed = {
            "settings": [
                {
                    "name": "Setting A",
                    "type": "location",
                    "category": "World",
                    "description": "Description",
                    "attributes": {"key": "value"},
                    "related_characters": ["A"],
                    "importance": "high",
                    "evidence": "Evidence",
                }
            ]
        }
        
        results = agent._parse_settings(parsed, mock_chunk)
        
        assert len(results) == 1
        assert results[0].result_type == "setting"
        assert results[0].data["canonical_name"] == "Setting A"
    
    def test_parse_llm_response_with_markdown(self, agent, mock_chunk):
        """测试解析带 Markdown 代码块的结果"""
        content = '''```json
        {"plot_points": [{"title": "Test"}]}
        ```'''
        
        results = agent._parse_llm_response(content, TaskSubType.OUTLINE_EXTRACTION, mock_chunk)
        
        assert len(results) > 0
    
    def test_parse_invalid_json(self, agent, mock_chunk):
        """测试解析无效 JSON"""
        content = "Invalid JSON"
        
        results = agent._parse_llm_response(content, TaskSubType.OUTLINE_EXTRACTION, mock_chunk)
        
        assert len(results) == 1
        assert results[0].result_type == "parse_error"
    
    def test_fix_json(self, agent):
        """测试修复 JSON"""
        # 测试补全括号
        fixed = agent._fix_json('{"key": "value"')
        assert fixed is not None
        assert fixed["key"] == "value"
        
        # 测试无法修复
        fixed = agent._fix_json("Not JSON at all")
        assert fixed is None


# ============================================================================
# Test Execute
# ============================================================================

@pytest.mark.asyncio
class TestExecute:
    """测试执行功能"""
    
    async def test_execute_success(self, agent, mock_task, mock_context):
        """测试成功执行"""
        # Mock 所有依赖
        with patch.object(agent, '_prepare_chunks', return_value=[]):
            result = await agent.execute(mock_task, mock_context)
            
            # 由于没有分块，应该返回错误
            assert result.success is False
            assert result.error_code == "NO_CONTENT"
    
    async def test_execute_validation_failure(self, agent, mock_task, mock_context):
        """测试验证失败"""
        mock_task.edition_id = None
        mock_task.target_node_ids = None
        
        result = await agent.execute(mock_task, mock_context)
        
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
    
    async def test_execute_with_progress_callback(self, agent, mock_task, mock_context):
        """测试带进度回调的执行"""
        progress_updates = []
        
        def callback(update: ProgressUpdate):
            progress_updates.append(update)
        
        # Mock 依赖
        mock_chunk = ChapterChunk(
            index=0,
            node_ids=[1],
            chapter_range="Chapter 1",
            content="Content",
            token_estimate=100,
        )
        
        with patch.object(agent, '_prepare_chunks', return_value=[mock_chunk]), \
             patch.object(agent, '_process_chunk', return_value=[]):
            
            result = await agent.execute(mock_task, mock_context, callback)
            
            # 应该有进度更新
            assert len(progress_updates) > 0
            # 第一个更新应该是 preparing
            assert progress_updates[0].phase == "preparing"


# ============================================================================
# Test Compile Results
# ============================================================================

class TestCompileResults:
    """测试结果编译"""
    
    def test_compile_results(self, agent):
        """测试编译结果"""
        results = [
            AnalysisResult(
                result_type="outline_node",
                data={"title": "Event 1"},
                confidence=0.8,
                chunk_index=0,
                node_ids=[1],
            ),
            AnalysisResult(
                result_type="outline_node",
                data={"title": "Event 2"},
                confidence=0.9,
                chunk_index=0,
                node_ids=[1],
            ),
            AnalysisResult(
                result_type="character",
                data={"name": "Character A"},
                confidence=0.85,
                chunk_index=0,
                node_ids=[1],
            ),
        ]
        
        compiled = agent._compile_results(results, TaskSubType.OUTLINE_EXTRACTION)
        
        assert compiled["sub_type"] == TaskSubType.OUTLINE_EXTRACTION
        assert compiled["total_results"] == 3
        assert "outline_node" in compiled["results_by_type"]
        assert "character" in compiled["results_by_type"]
        assert len(compiled["raw_results"]) == 3
