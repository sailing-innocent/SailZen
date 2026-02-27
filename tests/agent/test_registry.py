# -*- coding: utf-8 -*-
# @file test_registry.py
# @brief Unit tests for Agent Registry
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
from unittest.mock import Mock

from sail_server.agent.registry import AgentRegistry, get_agent_registry, register_agent
from sail_server.agent.base import BaseAgent, AgentExecutionResult, CostEstimate, ValidationResult


# ============================================================================
# Mock Agents for testing
# ============================================================================

class TestAgent1(BaseAgent):
    """测试 Agent 1"""
    
    @property
    def agent_type(self) -> str:
        return "test_agent_1"
    
    async def execute(self, task, context, callback=None):
        return AgentExecutionResult(success=True)
    
    def estimate_cost(self, task):
        return CostEstimate(estimated_tokens=100, estimated_cost=0.01)
    
    def validate_task(self, task):
        return ValidationResult(valid=True)


class TestAgent2(BaseAgent):
    """测试 Agent 2"""
    
    @property
    def agent_type(self) -> str:
        return "test_agent_2"
    
    async def execute(self, task, context, callback=None):
        return AgentExecutionResult(success=True)
    
    def estimate_cost(self, task):
        return CostEstimate(estimated_tokens=200, estimated_cost=0.02)
    
    def validate_task(self, task):
        return ValidationResult(valid=True)


# ============================================================================
# Test AgentRegistry
# ============================================================================

class TestAgentRegistry:
    """测试 Agent 注册表"""
    
    @pytest.fixture
    def registry(self):
        """创建新的注册表实例"""
        # 重置单例
        AgentRegistry._instance = None
        return AgentRegistry()
    
    def test_singleton(self, registry):
        """测试单例模式"""
        registry2 = AgentRegistry()
        assert registry is registry2
    
    def test_register_agent(self, registry):
        """测试注册 Agent"""
        result = registry.register(TestAgent1)
        assert result is True
        assert registry.is_registered("test_agent_1") is True
    
    def test_register_duplicate(self, registry):
        """测试重复注册"""
        registry.register(TestAgent1)
        
        # 不允许重复注册
        with pytest.raises(ValueError):
            registry.register(TestAgent1)
        
        # 允许覆盖
        result = registry.register(TestAgent1, override=True)
        assert result is True
    
    def test_register_invalid_class(self, registry):
        """测试注册无效类"""
        class NotAnAgent:
            pass
        
        with pytest.raises(TypeError):
            registry.register(NotAnAgent)
    
    def test_unregister_agent(self, registry):
        """测试注销 Agent"""
        registry.register(TestAgent1)
        
        result = registry.unregister("test_agent_1")
        assert result is True
        assert registry.is_registered("test_agent_1") is False
    
    def test_unregister_nonexistent(self, registry):
        """测试注销不存在的 Agent"""
        result = registry.unregister("nonexistent")
        assert result is False
    
    def test_get_agent(self, registry):
        """测试获取 Agent"""
        registry.register(TestAgent1)
        
        agent = registry.get_agent("test_agent_1")
        assert agent is not None
        assert isinstance(agent, TestAgent1)
        assert agent.agent_type == "test_agent_1"
    
    def test_get_nonexistent_agent(self, registry):
        """测试获取不存在的 Agent"""
        agent = registry.get_agent("nonexistent")
        assert agent is None
    
    def test_list_agents(self, registry):
        """测试列出所有 Agent"""
        registry.register(TestAgent1)
        registry.register(TestAgent2)
        
        agents = registry.list_agents()
        assert len(agents) == 2
        
        agent_types = [a.agent_type for a in agents]
        assert "test_agent_1" in agent_types
        assert "test_agent_2" in agent_types
    
    def test_list_agent_types(self, registry):
        """测试列出 Agent 类型"""
        registry.register(TestAgent1)
        registry.register(TestAgent2)
        
        types = registry.list_agent_types()
        assert len(types) == 2
        assert "test_agent_1" in types
        assert "test_agent_2" in types
    
    def test_clear(self, registry):
        """测试清空注册表"""
        registry.register(TestAgent1)
        registry.register(TestAgent2)
        
        registry.clear()
        
        assert len(registry.list_agent_types()) == 0
        assert registry.is_registered("test_agent_1") is False
    
    def test_get_stats(self, registry):
        """测试获取统计信息"""
        registry.register(TestAgent1)
        
        stats = registry.get_stats()
        assert stats["total_agents"] == 1


# ============================================================================
# Test convenience functions
# ============================================================================

class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """重置注册表"""
        AgentRegistry._instance = None
        yield
        AgentRegistry._instance = None
    
    def test_get_agent_registry(self):
        """测试获取全局注册表"""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()
        
        assert registry1 is registry2
    
    def test_register_agent(self):
        """测试便捷注册函数"""
        result = register_agent(TestAgent1)
        assert result is True
        
        registry = get_agent_registry()
        assert registry.is_registered("test_agent_1") is True
    
    def test_get_agent(self):
        """测试便捷获取函数"""
        from sail_server.agent.registry import get_agent
        
        # 使用 override=True 避免重复注册错误
        register_agent(TestAgent1, override=True)
        
        agent = get_agent("test_agent_1")
        assert agent is not None
        assert isinstance(agent, TestAgent1)
