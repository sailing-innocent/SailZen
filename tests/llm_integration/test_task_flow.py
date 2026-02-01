# -*- coding: utf-8 -*-
# @file test_task_flow.py
# @brief Task Flow Tests
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# pytest 测试用例 - 任务流程验证
#

import os
import pytest
import asyncio

from tests.llm_integration.validators.task import (
    TaskFlowValidator,
    MinimalTaskValidator,
)
from tests.llm_integration.validators.base import ValidationLevel


class TestMinimalTaskValidator:
    """最小任务验证测试 (不需要数据库)"""
    
    @pytest.mark.asyncio
    async def test_data_classes(self):
        """测试数据类"""
        from sail_server.model.analysis.task_scheduler import (
            ChapterChunk,
            TaskExecutionPlan,
            TaskProgress,
            TaskRunResult,
            TaskExecutionMode,
        )
        
        # 测试 ChapterChunk
        chunk = ChapterChunk(
            index=0,
            node_ids=[1, 2, 3],
            chapter_range="第1章 - 第3章",
            content="测试内容",
            token_estimate=100,
        )
        assert chunk.index == 0
        assert len(chunk.node_ids) == 3
        
        # 测试 TaskProgress
        progress = TaskProgress(
            task_id=1,
            status="running",
            current_step="processing",
            total_chunks=5,
            completed_chunks=2,
        )
        progress_dict = progress.to_dict()
        assert "task_id" in progress_dict
        assert "status" in progress_dict
        
        # 测试 TaskRunResult
        result = TaskRunResult(
            task_id=1,
            success=True,
            results_count=10,
            execution_time_seconds=5.5,
        )
        assert result.success
        result_dict = result.to_dict()
        assert "success" in result_dict
        
        # 测试枚举
        assert TaskExecutionMode.LLM_DIRECT.value == "llm_direct"
        assert TaskExecutionMode.PROMPT_ONLY.value == "prompt_only"
    
    @pytest.mark.asyncio
    async def test_template_to_prompt_flow(self, template_manager, sample_variables):
        """测试模板到 Prompt 的流程"""
        from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        
        # 渲染模板
        rendered = template_manager.render("character_detection_v1", sample_variables)
        assert rendered.system_prompt
        assert rendered.user_prompt
        
        # 生成导出格式
        config = LLMConfig(provider=LLMProvider.EXTERNAL)
        client = LLMClient(config)
        
        exported = client.generate_prompt_only(
            rendered.user_prompt,
            system=rendered.system_prompt,
            task_id=1,
            chunk_index=0,
            total_chunks=1,
        )
        
        # 验证导出内容
        assert exported.task_id == 1
        assert exported.system_prompt == rendered.system_prompt
        assert exported.user_prompt == rendered.user_prompt
        
        # 测试各种格式
        openai_fmt = exported.to_openai_format()
        assert openai_fmt["messages"][0]["role"] == "system"
        assert openai_fmt["messages"][1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_minimal_validator(self):
        """测试最小验证器"""
        validator = MinimalTaskValidator(
            use_real_llm=False,
        )
        report = await validator.run()
        
        assert report.total_count > 0
        
        # 检查数据类验证
        data_class_results = [r for r in report.results if r.name.startswith("data_class_")]
        assert len(data_class_results) > 0
        
        # 检查模板到 Prompt 验证
        template_result = next(
            (r for r in report.results if r.name == "template_render"),
            None
        )
        assert template_result is not None


class TestTaskFlowValidator:
    """任务流程验证测试 (需要数据库)"""
    
    @pytest.mark.asyncio
    async def test_imports_validation(self):
        """测试模块导入验证"""
        validator = TaskFlowValidator(
            use_real_llm=False,
            cleanup_after_test=True,
        )
        
        # 只验证导入，不运行完整流程
        modules = await validator._validate_imports()
        
        assert modules is not None
        assert "AnalysisTask" in modules
        assert "AnalysisResult" in modules
        assert "TaskExecutionMode" in modules
        assert "AnalysisTaskRunner" in modules
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.getenv("SKIP_DB_TESTS", "false").lower() == "true",
        reason="Database tests skipped"
    )
    async def test_full_task_flow_prompt_only(self, db_session):
        """测试完整任务流程 (Prompt Only 模式)"""
        validator = TaskFlowValidator(
            db_session_factory=lambda: db_session,
            use_real_llm=False,
            cleanup_after_test=True,
        )
        report = await validator.run()
        
        # 应该有任务创建结果
        task_create_result = next(
            (r for r in report.results if r.name == "task_create"),
            None
        )
        if task_create_result:
            assert task_create_result.level in [
                ValidationLevel.SUCCESS,
                ValidationLevel.SKIPPED,
            ]
        
        # 如果有执行结果，检查是否成功
        task_execute_result = next(
            (r for r in report.results if r.name == "task_execute"),
            None
        )
        if task_execute_result:
            # 可能成功或因为没有数据而跳过
            assert task_execute_result.level in [
                ValidationLevel.SUCCESS,
                ValidationLevel.WARNING,
                ValidationLevel.SKIPPED,
            ]


class TestTaskFlowWithRealLLM:
    """使用真实 LLM 的任务流程测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Google API key not configured"
    )
    async def test_minimal_with_google(self):
        """测试最小验证器使用 Google LLM"""
        validator = MinimalTaskValidator(
            use_real_llm=True,
            llm_provider="google",
        )
        report = await validator.run()
        
        # 检查 LLM 调用结果
        llm_results = [r for r in report.results if r.name.startswith("llm_")]
        
        # 至少有一个 LLM 相关的结果
        assert len(llm_results) > 0
        
        # 检查是否成功调用
        llm_call_result = next(
            (r for r in report.results if r.name == "llm_call"),
            None
        )
        if llm_call_result:
            assert llm_call_result.level == ValidationLevel.SUCCESS


class TestTaskExecutionPlan:
    """任务执行计划测试"""
    
    @pytest.mark.asyncio
    async def test_execution_plan_creation(self):
        """测试执行计划创建"""
        from sail_server.model.analysis.task_scheduler import (
            TaskExecutionPlan,
            TaskExecutionMode,
            ChapterChunk,
        )
        
        # 创建测试分块
        chunks = [
            ChapterChunk(
                index=0,
                node_ids=[1, 2],
                chapter_range="第1章 - 第2章",
                content="内容1",
                token_estimate=500,
            ),
            ChapterChunk(
                index=1,
                node_ids=[3, 4],
                chapter_range="第3章 - 第4章",
                content="内容2",
                token_estimate=600,
            ),
        ]
        
        plan = TaskExecutionPlan(
            task_id=1,
            mode=TaskExecutionMode.PROMPT_ONLY,
            chunks=chunks,
            total_estimated_tokens=1100,
            estimated_cost_usd=0.05,
            prompt_template_id="character_detection_v1",
        )
        
        plan_dict = plan.to_dict()
        
        assert plan_dict["task_id"] == 1
        assert plan_dict["mode"] == "prompt_only"
        assert len(plan_dict["chunks"]) == 2
        assert plan_dict["total_estimated_tokens"] == 1100
    
    @pytest.mark.asyncio
    async def test_result_import_parsing(self):
        """测试结果导入解析"""
        import json
        
        # 模拟外部 LLM 返回的结果
        mock_result = json.dumps({
            "characters": [
                {
                    "canonical_name": "张三",
                    "aliases": [],
                    "role_type": "protagonist",
                    "description": "年轻的铁匠",
                },
                {
                    "canonical_name": "李四",
                    "aliases": ["老者", "道士"],
                    "role_type": "supporting",
                    "description": "神秘的道士",
                },
            ],
            "total_characters": 2
        }, ensure_ascii=False)
        
        # 解析
        parsed = json.loads(mock_result)
        
        assert len(parsed["characters"]) == 2
        assert parsed["characters"][0]["canonical_name"] == "张三"
        assert "老者" in parsed["characters"][1]["aliases"]
