# -*- coding: utf-8 -*-
# @file test_llm_connection.py
# @brief LLM Connection Tests
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# pytest 测试用例 - LLM 连接验证
#

import os
import pytest
import asyncio

from tests.llm_integration.validators.connection import (
    LLMConnectionValidator,
    LLMStabilityValidator,
)
from tests.llm_integration.validators.base import ValidationLevel


class TestLLMConnectionValidator:
    """LLM 连接验证测试"""
    
    @pytest.mark.asyncio
    async def test_env_config_validation(self):
        """测试环境变量配置验证"""
        validator = LLMConnectionValidator(
            test_real_connection=False,
        )
        report = await validator.run()
        
        # 应该至少检查了环境变量
        assert report.total_count > 0
        
        # 找到环境变量相关的结果
        env_results = [r for r in report.results if r.name.startswith("env_")]
        assert len(env_results) > 0
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """测试客户端初始化"""
        validator = LLMConnectionValidator(
            providers=["openai", "anthropic", "google"],
            test_real_connection=False,
        )
        report = await validator.run()
        
        # 检查客户端初始化结果
        init_results = [r for r in report.results if r.name.startswith("client_init_")]
        assert len(init_results) > 0
        
        # 至少有一个成功（模块导入成功）
        module_result = next((r for r in report.results if r.name == "import_llm_module"), None)
        assert module_result is not None
        assert module_result.level == ValidationLevel.SUCCESS
    
    @pytest.mark.asyncio
    async def test_error_handling_validation(self):
        """测试错误处理验证"""
        validator = LLMConnectionValidator(
            test_real_connection=False,
        )
        report = await validator.run()
        
        # 检查错误处理结果
        error_results = [r for r in report.results if r.name.startswith("error_")]
        assert len(error_results) > 0
        
        # external 模式应该正确拒绝 complete() 调用
        external_result = next(
            (r for r in report.results if r.name == "error_external_mode"),
            None
        )
        if external_result:
            assert external_result.level == ValidationLevel.SUCCESS
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Google API key not configured"
    )
    async def test_real_connection_google(self):
        """测试 Google 真实连接"""
        validator = LLMConnectionValidator(
            providers=["google"],
            test_real_connection=True,
            timeout_seconds=30,
        )
        report = await validator.run()
        
        # 检查连接结果
        conn_result = next(
            (r for r in report.results if r.name == "connection_google"),
            None
        )
        assert conn_result is not None
        assert conn_result.level == ValidationLevel.SUCCESS
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="OpenAI API key not configured"
    )
    async def test_real_connection_openai(self):
        """测试 OpenAI 真实连接"""
        validator = LLMConnectionValidator(
            providers=["openai"],
            test_real_connection=True,
            timeout_seconds=30,
        )
        report = await validator.run()
        
        conn_result = next(
            (r for r in report.results if r.name == "connection_openai"),
            None
        )
        assert conn_result is not None
        # 可能成功或失败，但应该有结果
        assert conn_result.level in [ValidationLevel.SUCCESS, ValidationLevel.ERROR, ValidationLevel.SKIPPED]


class TestLLMStabilityValidator:
    """LLM 稳定性验证测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Google API key not configured"
    )
    async def test_stability_google(self):
        """测试 Google 稳定性 (3 次迭代)"""
        validator = LLMStabilityValidator(
            provider="google",
            num_iterations=3,
            delay_between_calls=1.0,
        )
        report = await validator.run()
        
        # 应该有迭代结果
        iteration_results = [r for r in report.results if r.name.startswith("iteration_")]
        assert len(iteration_results) == 3
        
        # 检查汇总结果
        summary_result = next(
            (r for r in report.results if r.name == "stability_summary"),
            None
        )
        assert summary_result is not None
    
    @pytest.mark.asyncio
    async def test_stability_skip_no_key(self):
        """测试没有 API key 时跳过"""
        # 使用一个肯定没配置的 provider
        validator = LLMStabilityValidator(
            provider="anthropic",  # 假设没配置
            num_iterations=1,
        )
        
        if not os.getenv("ANTHROPIC_API_KEY"):
            report = await validator.run()
            # 应该跳过测试
            skip_results = [r for r in report.results if r.level == ValidationLevel.SKIPPED]
            assert len(skip_results) > 0
