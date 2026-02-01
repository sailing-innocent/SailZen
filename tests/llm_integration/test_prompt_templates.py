# -*- coding: utf-8 -*-
# @file test_prompt_templates.py
# @brief Prompt Template Tests
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# pytest 测试用例 - Prompt 模板验证
#

import os
import pytest
import asyncio
import json

from tests.llm_integration.validators.prompt import (
    PromptValidator,
    PromptPerformanceValidator,
)
from tests.llm_integration.validators.base import ValidationLevel


class TestPromptValidator:
    """Prompt 模板验证测试"""
    
    @pytest.mark.asyncio
    async def test_manager_initialization(self, template_manager):
        """测试模板管理器初始化"""
        assert template_manager is not None
        assert len(template_manager.templates) > 0
    
    @pytest.mark.asyncio
    async def test_builtin_templates_exist(self, template_manager):
        """测试内置模板存在"""
        expected_templates = [
            "outline_extraction_v1",
            "character_detection_v1",
            "setting_extraction_v1",
        ]
        
        for template_id in expected_templates:
            template = template_manager.get_template(template_id)
            assert template is not None, f"Template {template_id} not found"
            assert template.system_prompt, f"Template {template_id} missing system_prompt"
            assert template.user_prompt_template, f"Template {template_id} missing user_prompt_template"
    
    @pytest.mark.asyncio
    async def test_template_rendering(self, template_manager, sample_variables):
        """测试模板渲染"""
        rendered = template_manager.render("character_detection_v1", sample_variables)
        
        assert rendered is not None
        assert len(rendered.system_prompt) > 0
        assert len(rendered.user_prompt) > 0
        assert rendered.estimated_tokens > 0
        
        # 检查变量替换
        assert sample_variables["work_title"] in rendered.user_prompt
    
    @pytest.mark.asyncio
    async def test_variable_substitution(self, template_manager):
        """测试变量替换"""
        variables = {
            "work_title": "我的测试小说",
            "chapter_range": "第1章",
            "chapter_contents": "这是测试内容。",
            "known_characters": "张三, 李四",
        }
        
        rendered = template_manager.render("outline_extraction_v1", variables)
        
        # 所有变量都应该被替换
        assert "我的测试小说" in rendered.user_prompt
        assert "第1章" in rendered.user_prompt
        assert "这是测试内容" in rendered.user_prompt
    
    @pytest.mark.asyncio
    async def test_output_validation_valid(self, template_manager):
        """测试有效输出验证"""
        valid_output = {
            "characters": [
                {
                    "canonical_name": "张三",
                    "role_type": "protagonist",
                }
            ],
            "total_characters": 1
        }
        
        result = template_manager.validate_output("character_detection_v1", valid_output)
        assert result.get("valid") is True
        assert len(result.get("errors", [])) == 0
    
    @pytest.mark.asyncio
    async def test_output_validation_invalid(self, template_manager):
        """测试无效输出验证"""
        invalid_output = {
            # 缺少 characters 字段
            "total_characters": 1
        }
        
        result = template_manager.validate_output("character_detection_v1", invalid_output)
        # 应该报告 characters 字段缺失
        assert result.get("valid") is False or len(result.get("errors", [])) > 0
    
    @pytest.mark.asyncio
    async def test_export_formats(self, llm_config_external):
        """测试导出格式"""
        from sail_server.utils.llm import LLMClient
        
        client = LLMClient(llm_config_external)
        exported = client.generate_prompt_only(
            prompt="测试用户提示",
            system="测试系统提示",
            task_id=1,
            chunk_index=0,
            total_chunks=1,
        )
        
        # 测试各种格式
        openai_format = exported.to_openai_format()
        assert "model" in openai_format
        assert "messages" in openai_format
        
        anthropic_format = exported.to_anthropic_format()
        assert "model" in anthropic_format
        assert "messages" in anthropic_format
        
        google_format = exported.to_google_format()
        assert "model" in google_format
        
        plain_text = exported.to_plain_text()
        assert "测试系统提示" in plain_text
        assert "测试用户提示" in plain_text
        
        markdown = exported.to_markdown()
        assert "System Prompt" in markdown
        assert "User Prompt" in markdown
    
    @pytest.mark.asyncio
    async def test_full_prompt_validation(self):
        """测试完整的 Prompt 验证流程"""
        validator = PromptValidator(
            test_real_llm=False,
        )
        report = await validator.run()
        
        assert report.total_count > 0
        
        # 检查关键验证项
        assert any(r.name == "manager_init" for r in report.results)
        assert any(r.name.startswith("template_") for r in report.results)
        assert any(r.name.startswith("render_") for r in report.results)


class TestPromptPerformanceValidator:
    """Prompt 性能验证测试"""
    
    @pytest.mark.asyncio
    async def test_render_performance(self):
        """测试渲染性能"""
        validator = PromptPerformanceValidator(iterations=50)
        report = await validator.run()
        
        # 检查性能结果
        perf_results = [r for r in report.results if r.name.startswith("perf_")]
        assert len(perf_results) > 0
        
        # 平均渲染时间应该在合理范围内 (< 100ms)
        for result in perf_results:
            if result.level == ValidationLevel.SUCCESS:
                avg_ms = result.details.get("avg_ms", 0)
                assert avg_ms < 100, f"Render time too slow: {avg_ms}ms"


class TestPromptWithRealLLM:
    """使用真实 LLM 的 Prompt 测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Google API key not configured"
    )
    async def test_prompt_with_google(self, template_manager, sample_variables):
        """测试使用 Google LLM"""
        from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        
        config = LLMConfig.from_env(LLMProvider.GOOGLE)
        client = LLMClient(config)
        
        # 使用较短的内容
        short_vars = {
            **sample_variables,
            "chapter_contents": "张三是铁匠。李四是道士。",
        }
        
        rendered = template_manager.render("character_detection_v1", short_vars)
        
        # 调用 LLM
        response = await client.complete(
            rendered.user_prompt,
            system=rendered.system_prompt
        )
        
        assert response.content is not None
        assert len(response.content) > 0
        assert response.total_tokens > 0
        
        # 尝试解析 JSON
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        try:
            parsed = json.loads(content.strip())
            assert "characters" in parsed
        except json.JSONDecodeError:
            # LLM 可能没有返回有效 JSON，这是可以接受的
            pass
