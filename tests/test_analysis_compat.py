# -*- coding: utf-8 -*-
# @file test_analysis_compat.py
# @brief Unit tests for Analysis API Compatibility Layer
# @author sailing-innocent
# @date 2026-02-28
# @version 1.0
# ---------------------------------

import pytest
from datetime import datetime
from unittest.mock import Mock

from sail_server.router.analysis_compat import (
    convert_old_task_type_to_new,
    convert_new_status_to_old,
    convert_unified_task_to_analysis_response,
    CreateAnalysisTaskRequest,
    AnalysisTaskResponse,
    TASK_TYPE_MAPPING,
    STATUS_MAPPING,
)
from sail_server.data.unified_agent import (
    TaskType,
    TaskSubType,
    TaskStatus,
)


# ============================================================================
# Test Type Conversions
# ============================================================================

class TestTypeConversions:
    """测试类型转换"""
    
    def test_convert_old_task_type_to_new(self):
        """测试旧任务类型转换为新类型"""
        assert convert_old_task_type_to_new("outline_extraction") == TaskSubType.OUTLINE_EXTRACTION
        assert convert_old_task_type_to_new("character_detection") == TaskSubType.CHARACTER_DETECTION
        assert convert_old_task_type_to_new("setting_extraction") == TaskSubType.SETTING_EXTRACTION
        assert convert_old_task_type_to_new("unknown_type") == "unknown_type"
    
    def test_convert_new_status_to_old(self):
        """测试新状态转换为旧状态"""
        assert convert_new_status_to_old(TaskStatus.PENDING) == "pending"
        assert convert_new_status_to_old(TaskStatus.SCHEDULED) == "pending"
        assert convert_new_status_to_old(TaskStatus.RUNNING) == "running"
        assert convert_new_status_to_old(TaskStatus.COMPLETED) == "completed"
        assert convert_new_status_to_old(TaskStatus.FAILED) == "failed"
        assert convert_new_status_to_old(TaskStatus.CANCELLED) == "cancelled"
        assert convert_new_status_to_old("unknown") == "unknown"


# ============================================================================
# Test Response Conversion
# ============================================================================

class TestResponseConversion:
    """测试响应转换"""
    
    @pytest.fixture
    def mock_unified_task(self):
        """创建 Mock 统一任务"""
        task = Mock()
        task.id = 1
        task.task_type = TaskType.NOVEL_ANALYSIS
        task.sub_type = TaskSubType.OUTLINE_EXTRACTION
        task.edition_id = 1
        task.target_node_ids = [1, 2, 3]
        task.target_scope = "full"
        task.status = TaskStatus.RUNNING
        task.config = {"key": "value"}
        task.llm_provider = "openai"
        task.llm_model = "gpt-4"
        task.prompt_template_id = "template_v1"
        task.result_data = {"results": []}
        task.created_at = datetime.utcnow()
        task.started_at = datetime.utcnow()
        task.completed_at = None
        task.error_message = None
        return task
    
    def test_convert_unified_task_to_analysis_response(self, mock_unified_task):
        """测试统一任务转换为分析响应"""
        response = convert_unified_task_to_analysis_response(mock_unified_task)
        
        assert isinstance(response, AnalysisTaskResponse)
        assert response.id == 1
        assert response.edition_id == 1
        assert response.task_type == "outline_extraction"  # 反向映射
        assert response.status == "running"
        assert response.target_scope == "full"
        assert response.llm_provider == "openai"
        assert response.llm_model == "gpt-4"
        assert response.llm_prompt_template == "template_v1"


# ============================================================================
# Test Request Models
# ============================================================================

class TestRequestModels:
    """测试请求模型"""
    
    def test_create_analysis_task_request(self):
        """测试创建分析任务请求"""
        request = CreateAnalysisTaskRequest(
            edition_id=1,
            task_type="outline_extraction",
            target_node_ids=[1, 2, 3],
            target_scope="range",
            llm_provider="openai",
            llm_model="gpt-4",
            llm_prompt_template="template_v1",
            parameters={"key": "value"},
            priority=3,
        )
        
        assert request.edition_id == 1
        assert request.task_type == "outline_extraction"
        assert request.target_node_ids == [1, 2, 3]
        assert request.target_scope == "range"
        assert request.llm_provider == "openai"
        assert request.priority == 3


# ============================================================================
# Test Status Mapping
# ============================================================================

class TestStatusMapping:
    """测试状态映射"""
    
    def test_all_old_statuses_mapped(self):
        """测试所有旧状态都有映射"""
        old_statuses = ["pending", "running", "completed", "failed", "cancelled"]
        for status in old_statuses:
            assert status in STATUS_MAPPING
    
    def test_all_new_statuses_mapped(self):
        """测试所有新状态都有反向映射"""
        new_statuses = [
            TaskStatus.PENDING,
            TaskStatus.SCHEDULED,
            TaskStatus.RUNNING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]
        for status in new_statuses:
            assert status in STATUS_MAPPING


# ============================================================================
# Test Task Type Mapping
# ============================================================================

class TestTaskTypeMapping:
    """测试任务类型映射"""
    
    def test_all_task_types_mapped(self):
        """测试所有任务类型都有映射"""
        old_types = [
            "outline_extraction",
            "character_detection",
            "setting_extraction",
            "relation_analysis",
            "plot_analysis",
        ]
        for task_type in old_types:
            assert task_type in TASK_TYPE_MAPPING
    
    def test_task_type_mapping_values(self):
        """测试任务类型映射值"""
        assert TASK_TYPE_MAPPING["outline_extraction"] == TaskSubType.OUTLINE_EXTRACTION
        assert TASK_TYPE_MAPPING["character_detection"] == TaskSubType.CHARACTER_DETECTION
        assert TASK_TYPE_MAPPING["setting_extraction"] == TaskSubType.SETTING_EXTRACTION
