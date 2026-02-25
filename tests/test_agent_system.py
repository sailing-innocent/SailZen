# -*- coding: utf-8 -*-
# @file test_agent_system.py
# @brief Agent System Basic Tests
# @author sailing-innocent
# @date 2025-02-25
# @version 1.0
# ---------------------------------

"""
Agent 系统基础测试

运行方式:
    uv run pytest tests/test_agent_system.py -v
"""

import pytest
from datetime import datetime
from typing import Generator

# Test data models import
from sail_server.data.agent import (
    UserPrompt, UserPromptData, UserPromptCreateRequest,
    AgentTask, AgentTaskData,
    AgentStep, AgentStepData,
    AgentOutput, AgentOutputData,
    AgentSchedulerState, SchedulerStateData,
)


class TestDataModels:
    """测试数据模型"""
    
    def test_user_prompt_data_creation(self):
        """测试 UserPromptData 创建"""
        data = UserPromptData(
            content="Test prompt",
            prompt_type="general",
            priority=3,
        )
        assert data.content == "Test prompt"
        assert data.prompt_type == "general"
        assert data.priority == 3
        assert data.status == "pending"
    
    def test_user_prompt_create_request(self):
        """测试 UserPromptCreateRequest 创建"""
        req = UserPromptCreateRequest(
            content="Test content",
            prompt_type="code",
            priority=1,
        )
        assert req.content == "Test content"
        assert req.prompt_type == "code"
        assert req.priority == 1
    
    def test_agent_task_data_creation(self):
        """测试 AgentTaskData 创建"""
        data = AgentTaskData(
            prompt_id=1,
            agent_type="coder",
            status="created",
            progress=0,
        )
        assert data.prompt_id == 1
        assert data.agent_type == "coder"
        assert data.status == "created"
        assert data.progress == 0
    
    def test_agent_step_data_creation(self):
        """测试 AgentStepData 创建"""
        data = AgentStepData(
            task_id=1,
            step_number=1,
            step_type="thought",
            title="Test step",
        )
        assert data.task_id == 1
        assert data.step_number == 1
        assert data.step_type == "thought"
        assert data.title == "Test step"
    
    def test_agent_output_data_creation(self):
        """测试 AgentOutputData 创建"""
        data = AgentOutputData(
            task_id=1,
            output_type="text",
            content="Test output",
        )
        assert data.task_id == 1
        assert data.output_type == "text"
        assert data.content == "Test output"
    
    def test_scheduler_state_data_creation(self):
        """测试 SchedulerStateData 创建"""
        data = SchedulerStateData(
            is_running=True,
            active_agent_count=2,
            max_concurrent_agents=5,
        )
        assert data.is_running is True
        assert data.active_agent_count == 2
        assert data.max_concurrent_agents == 5


class TestAgentRunnerMock:
    """测试 Agent Runner 的 Mock 功能"""
    
    @pytest.mark.asyncio
    async def test_mock_delay_range(self):
        """测试 Mock 延时范围"""
        from sail_server.model.agent.runner import AgentRunner
        
        # 验证配置值
        assert AgentRunner.MOCK_MIN_DELAY >= 0
        assert AgentRunner.MOCK_MAX_DELAY > AgentRunner.MOCK_MIN_DELAY
        assert 0 <= AgentRunner.MOCK_FAILURE_RATE <= 1
    
    @pytest.mark.asyncio
    async def test_mock_step_range(self):
        """测试 Mock 步骤范围"""
        from sail_server.model.agent.runner import AgentRunner
        
        # 验证配置值
        assert AgentRunner.MOCK_MIN_STEPS >= 1
        assert AgentRunner.MOCK_MAX_STEPS >= AgentRunner.MOCK_MIN_STEPS


class TestAgentScheduler:
    """测试 Agent 调度器"""
    
    @pytest.mark.asyncio
    async def test_scheduler_singleton(self):
        """测试调度器单例模式"""
        from sail_server.model.agent.scheduler import get_agent_scheduler, set_agent_scheduler, AgentScheduler
        
        # 获取默认实例
        scheduler1 = get_agent_scheduler()
        assert scheduler1 is not None
        
        # 再次获取应该是同一个实例
        scheduler2 = get_agent_scheduler()
        assert scheduler1 is scheduler2
        
        # 设置新实例
        new_scheduler = AgentScheduler(poll_interval=10.0)
        set_agent_scheduler(new_scheduler)
        
        # 获取应该是新实例
        scheduler3 = get_agent_scheduler()
        assert scheduler3 is new_scheduler
        
        # 恢复原始实例
        set_agent_scheduler(scheduler1)


class TestAPIEndpoints:
    """测试 API 端点定义"""
    
    def test_router_creation(self):
        """测试 Router 创建"""
        from sail_server.router.agent import router
        assert router is not None
        assert router.path == "/agent"
    
    def test_controllers_exist(self):
        """测试控制器存在"""
        from sail_server.router.agent import (
            UserPromptController,
            AgentTaskController,
            SchedulerController,
            AgentEventWebSocket,
        )
        assert UserPromptController is not None
        assert AgentTaskController is not None
        assert SchedulerController is not None
        assert AgentEventWebSocket is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
