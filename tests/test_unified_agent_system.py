# -*- coding: utf-8 -*-
# @file test_unified_agent_system.py
# @brief Unified Agent System Tests
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------

"""
Unified Agent 系统测试

运行方式:
    uv run pytest tests/test_unified_agent_system.py -v

此测试文件替代已弃用的 test_agent_system.py，
基于新的 Unified Agent 架构。
"""

import pytest
from datetime import datetime
from typing import Generator

from sail_server.data.unified_agent import (
    UnifiedAgentTask,
    UnifiedAgentStep,
    UnifiedAgentEvent,
    UnifiedTaskData,
    UnifiedStepData,
    UnifiedTaskCreateRequest,
    TaskType,
    TaskStatus,
    ReviewStatus,
    StepType,
)
from sail_server.model.unified_agent import (
    UnifiedTaskDAO,
    UnifiedStepDAO,
    UnifiedEventDAO,
)


class TestUnifiedTaskDataModels:
    """测试 Unified Agent 数据模型"""
    
    def test_task_data_creation(self):
        """测试 UnifiedTaskData 创建"""
        data = UnifiedTaskData(
            task_type=TaskType.GENERAL,
            status=TaskStatus.PENDING,
            priority=3,
        )
        assert data.task_type == TaskType.GENERAL
        assert data.status == TaskStatus.PENDING
        assert data.priority == 3
        assert data.progress == 0
    
    def test_task_create_request(self):
        """测试 UnifiedTaskCreateRequest 创建"""
        req = UnifiedTaskCreateRequest(
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type="outline_extraction",
            edition_id=1,
            priority=1,
        )
        assert req.task_type == TaskType.NOVEL_ANALYSIS
        assert req.sub_type == "outline_extraction"
        assert req.edition_id == 1
        assert req.priority == 1
    
    def test_step_data_creation(self):
        """测试 UnifiedStepData 创建"""
        data = UnifiedStepData(
            step_type=StepType.THOUGHT,
            title="Test step",
            content="Test content",
        )
        assert data.step_type == StepType.THOUGHT
        assert data.title == "Test step"
        assert data.content == "Test content"
    
    def test_novel_analysis_task(self):
        """测试小说分析任务创建"""
        data = UnifiedTaskData(
            task_type=TaskType.NOVEL_ANALYSIS,
            sub_type="character_detection",
            edition_id=1,
            target_node_ids=[1, 2, 3],
            target_scope="range",
            llm_provider="google",
            llm_model="gemini-2.0-flash",
            prompt_template_id="character_detection_v1",
            priority=2,
        )
        assert data.task_type == TaskType.NOVEL_ANALYSIS
        assert data.sub_type == "character_detection"
        assert data.edition_id == 1
        assert data.target_node_ids == [1, 2, 3]
        assert data.llm_provider == "google"


class TestTaskStatusTransitions:
    """测试任务状态转换"""
    
    def test_pending_to_running(self):
        """测试 PENDING -> RUNNING 转换"""
        data = UnifiedTaskData(
            task_type=TaskType.GENERAL,
            status=TaskStatus.PENDING,
        )
        assert data.status == TaskStatus.PENDING
        
        # 模拟状态转换
        data.status = TaskStatus.RUNNING
        data.started_at = datetime.utcnow()
        assert data.status == TaskStatus.RUNNING
        assert data.started_at is not None
    
    def test_running_to_completed(self):
        """测试 RUNNING -> COMPLETED 转换"""
        data = UnifiedTaskData(
            task_type=TaskType.GENERAL,
            status=TaskStatus.RUNNING,
            progress=50,
        )
        
        # 模拟完成
        data.status = TaskStatus.COMPLETED
        data.progress = 100
        data.completed_at = datetime.utcnow()
        data.review_status = ReviewStatus.PENDING
        
        assert data.status == TaskStatus.COMPLETED
        assert data.progress == 100
        assert data.completed_at is not None
    
    def test_running_to_failed(self):
        """测试 RUNNING -> FAILED 转换"""
        data = UnifiedTaskData(
            task_type=TaskType.GENERAL,
            status=TaskStatus.RUNNING,
        )
        
        # 模拟失败
        data.status = TaskStatus.FAILED
        data.error_message = "Test error"
        data.error_code = "ERR_001"
        data.completed_at = datetime.utcnow()
        
        assert data.status == TaskStatus.FAILED
        assert data.error_message == "Test error"
        assert data.error_code == "ERR_001"


class TestTaskCostTracking:
    """测试任务成本追踪"""
    
    def test_cost_estimation(self):
        """测试成本估算"""
        data = UnifiedTaskData(
            task_type=TaskType.NOVEL_ANALYSIS,
            estimated_tokens=5000,
            estimated_cost=0.005,
        )
        assert data.estimated_tokens == 5000
        assert float(data.estimated_cost) == 0.005
    
    def test_actual_cost_tracking(self):
        """测试实际成本追踪"""
        data = UnifiedTaskData(
            task_type=TaskType.NOVEL_ANALYSIS,
            estimated_tokens=5000,
            actual_tokens=5200,
            actual_cost=0.0052,
        )
        assert data.actual_tokens == 5200
        assert float(data.actual_cost) == 0.0052


class TestStepTypes:
    """测试步骤类型"""
    
    def test_thought_step(self):
        """测试思考步骤"""
        step = UnifiedStepData(
            step_type=StepType.THOUGHT,
            title="分析需求",
            content="需要分析小说角色",
        )
        assert step.step_type == StepType.THOUGHT
    
    def test_llm_call_step(self):
        """测试 LLM 调用步骤"""
        step = UnifiedStepData(
            step_type=StepType.LLM_CALL,
            title="调用 LLM",
            llm_provider="openai",
            llm_model="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500,
            cost=0.01,
        )
        assert step.step_type == StepType.LLM_CALL
        assert step.llm_provider == "openai"
        assert step.prompt_tokens == 1000
        assert step.completion_tokens == 500
    
    def test_action_step(self):
        """测试动作步骤"""
        step = UnifiedStepData(
            step_type=StepType.ACTION,
            title="保存结果",
            content="将分析结果保存到数据库",
        )
        assert step.step_type == StepType.ACTION


class TestTaskTypes:
    """测试任务类型枚举"""
    
    def test_task_type_values(self):
        """测试任务类型值"""
        assert TaskType.NOVEL_ANALYSIS == "novel_analysis"
        assert TaskType.CODE == "code"
        assert TaskType.WRITING == "writing"
        assert TaskType.GENERAL == "general"
        assert TaskType.DATA == "data"
    
    def test_task_status_values(self):
        """测试任务状态值"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.SCHEDULED == "scheduled"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PAUSED == "paused"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
    
    def test_review_status_values(self):
        """测试审核状态值"""
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"
        assert ReviewStatus.MODIFIED == "modified"


class TestDAOClasses:
    """测试 DAO 类定义"""
    
    def test_task_dao_exists(self):
        """测试 UnifiedTaskDAO 存在"""
        assert UnifiedTaskDAO is not None
    
    def test_step_dao_exists(self):
        """测试 UnifiedStepDAO 存在"""
        assert UnifiedStepDAO is not None
    
    def test_event_dao_exists(self):
        """测试 UnifiedEventDAO 存在"""
        assert UnifiedEventDAO is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
