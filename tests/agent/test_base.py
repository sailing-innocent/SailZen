# -*- coding: utf-8 -*-
# @file test_base.py
# @brief Unit tests for Base Agent
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from sail_server.agent.base import (
    BaseAgent,
    AgentContext,
    AgentExecutionResult,
    CostEstimate,
    ValidationResult,
    ProgressUpdate,
    AgentInfo,
)
from sail_server.data.unified_agent import UnifiedAgentTask


# ============================================================================
# Mock Agent for testing
# ============================================================================

class MockAgent(BaseAgent):
    """测试用的 Mock Agent"""
    
    @property
    def agent_type(self) -> str:
        return "mock"
    
    async def execute(self, task, context, callback=None):
        return AgentExecutionResult(success=True)
    
    def estimate_cost(self, task):
        return CostEstimate(estimated_tokens=100, estimated_cost=0.01)
    
    def validate_task(self, task):
        return ValidationResult(valid=True)


# ============================================================================
# Test ValidationResult
# ============================================================================

class TestValidationResult:
    """测试验证结果"""
    
    def test_valid_result(self):
        """测试有效结果"""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
    
    def test_add_error(self):
        """测试添加错误"""
        result = ValidationResult(valid=True)
        result.add_error("Error 1")
        
        assert result.valid is False
        assert "Error 1" in result.errors
    
    def test_add_warning(self):
        """测试添加警告"""
        result = ValidationResult(valid=True)
        result.add_warning("Warning 1")
        
        assert result.valid is True  # 警告不影响有效性
        assert "Warning 1" in result.warnings
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = ValidationResult(valid=False)
        result.add_error("Error 1")
        result.add_warning("Warning 1")
        
        data = result.to_dict()
        assert data["valid"] is False
        assert "Error 1" in data["errors"]
        assert "Warning 1" in data["warnings"]


# ============================================================================
# Test CostEstimate
# ============================================================================

class TestCostEstimate:
    """测试成本预估"""
    
    def test_basic_estimate(self):
        """测试基本预估"""
        estimate = CostEstimate(
            estimated_tokens=1000,
            estimated_cost=0.05,
            confidence=0.8,
        )
        
        assert estimate.estimated_tokens == 1000
        assert estimate.estimated_cost == 0.05
        assert estimate.confidence == 0.8
    
    def test_to_dict(self):
        """测试转换为字典"""
        estimate = CostEstimate(
            estimated_tokens=1000,
            estimated_cost=0.05,
            breakdown={"input": 0.02, "output": 0.03},
        )
        
        data = estimate.to_dict()
        assert data["estimated_tokens"] == 1000
        assert data["estimated_cost"] == 0.05
        assert data["breakdown"]["input"] == 0.02


# ============================================================================
# Test AgentExecutionResult
# ============================================================================

class TestAgentExecutionResult:
    """测试执行结果"""
    
    def test_success_result(self):
        """测试成功结果"""
        result = AgentExecutionResult(
            success=True,
            result_data={"key": "value"},
            total_tokens=100,
            total_cost=0.01,
        )
        
        assert result.success is True
        assert result.result_data["key"] == "value"
        assert result.total_tokens == 100
    
    def test_failure_result(self):
        """测试失败结果"""
        result = AgentExecutionResult(
            success=False,
            error_message="Something went wrong",
            error_code="ERROR_CODE",
        )
        
        assert result.success is False
        assert result.error_message == "Something went wrong"
        assert result.error_code == "ERROR_CODE"
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = AgentExecutionResult(
            success=True,
            result_data={"key": "value"},
            execution_time_seconds=1.5,
        )
        
        data = result.to_dict()
        assert data["success"] is True
        assert data["result_data"]["key"] == "value"
        assert data["execution_time_seconds"] == 1.5


# ============================================================================
# Test AgentContext
# ============================================================================

class TestAgentContext:
    """测试执行上下文"""
    
    def test_basic_context(self):
        """测试基本上下文"""
        mock_db = Mock()
        mock_llm = Mock()
        
        context = AgentContext(
            db_session=mock_db,
            llm_gateway=mock_llm,
        )
        
        assert context.db_session is mock_db
        assert context.llm_gateway is mock_llm
        assert context.config == {}
    
    def test_context_with_config(self):
        """测试带配置的上下文"""
        context = AgentContext(
            db_session=Mock(),
            llm_gateway=Mock(),
            config={"key": "value"},
        )
        
        assert context.get_config("key") == "value"
        assert context.get_config("missing", "default") == "default"


# ============================================================================
# Test BaseAgent
# ============================================================================

class TestBaseAgent:
    """测试 Agent 基类"""
    
    def test_agent_type(self):
        """测试 Agent 类型"""
        agent = MockAgent()
        assert agent.agent_type == "mock"
    
    def test_agent_info(self):
        """测试 Agent 信息"""
        agent = MockAgent()
        info = agent.agent_info
        
        assert isinstance(info, AgentInfo)
        assert info.agent_type == "mock"
    
    def test_notify_progress(self):
        """测试进度通知"""
        agent = MockAgent()
        
        updates = []
        def callback(update):
            updates.append(update)
        
        agent._notify_progress(callback, 50, "phase", "message")
        
        assert len(updates) == 1
        assert updates[0].progress == 50
        assert updates[0].phase == "phase"
        assert updates[0].message == "message"
    
    def test_notify_progress_no_callback(self):
        """测试无回调时的进度通知"""
        agent = MockAgent()
        
        # 不应该抛出异常
        agent._notify_progress(None, 50, "phase", "message")
    
    def test_repr(self):
        """测试字符串表示"""
        agent = MockAgent()
        assert "mock" in repr(agent)


# ============================================================================
# Test ProgressUpdate
# ============================================================================

class TestProgressUpdate:
    """测试进度更新"""
    
    def test_basic_update(self):
        """测试基本更新"""
        update = ProgressUpdate(progress=50)
        
        assert update.progress == 50
        assert update.phase is None
        assert update.message is None
    
    def test_full_update(self):
        """测试完整更新"""
        update = ProgressUpdate(
            progress=75,
            phase="processing",
            message="Processing data...",
            step_number=3,
            total_steps=5,
            metadata={"extra": "info"},
        )
        
        assert update.progress == 75
        assert update.phase == "processing"
        assert update.message == "Processing data..."
        assert update.step_number == 3
        assert update.total_steps == 5
        assert update.metadata["extra"] == "info"


# ============================================================================
# Test AgentInfo
# ============================================================================

class TestAgentInfo:
    """测试 Agent 信息"""
    
    def test_basic_info(self):
        """测试基本信息"""
        info = AgentInfo(
            agent_type="test",
            name="Test Agent",
            description="A test agent",
        )
        
        assert info.agent_type == "test"
        assert info.name == "Test Agent"
        assert info.description == "A test agent"
        assert info.version == "1.0"
    
    def test_full_info(self):
        """测试完整信息"""
        info = AgentInfo(
            agent_type="test",
            name="Test Agent",
            description="A test agent",
            version="2.0",
            supported_task_types=["type1", "type2"],
            capabilities=["cap1", "cap2"],
        )
        
        data = info.to_dict()
        assert data["version"] == "2.0"
        assert len(data["supported_task_types"]) == 2
        assert len(data["capabilities"]) == 2
