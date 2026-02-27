# -*- coding: utf-8 -*-
# @file test_gateway.py
# @brief LLM Gateway Unit Tests
# @author sailing-innocent
# @date 2026-02-27
# @version 1.0
# ---------------------------------

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from sail_server.utils.llm import (
    LLMGateway,
    LLMExecutionConfig,
    TokenBudget,
    LLMExecutionResult,
    ProviderConfig,
    ProviderResponse,
    ProviderError,
    PricingRegistry,
    calculate_cost,
    estimate_cost,
)


class TestTokenBudget:
    """Token 预算测试"""
    
    def test_check_budget_pass(self):
        """测试预算检查通过"""
        budget = TokenBudget(max_tokens=1000, max_cost=1.0)
        ok, msg = budget.check_budget(500, 200, 0.5)
        assert ok is True
        assert msg == "OK"
    
    def test_check_budget_exceed_tokens(self):
        """测试超出 Token 预算"""
        budget = TokenBudget(max_tokens=1000, max_cost=1.0)
        ok, msg = budget.check_budget(800, 500, 0.5)  # 1300 tokens
        assert ok is False
        assert "exceeds budget" in msg
    
    def test_check_budget_exceed_cost(self):
        """测试超出成本预算"""
        budget = TokenBudget(max_tokens=10000, max_cost=0.5)
        ok, msg = budget.check_budget(500, 200, 1.0)
        assert ok is False
        assert "exceeds budget" in msg
    
    def test_check_budget_warning(self):
        """测试警告阈值"""
        budget = TokenBudget(max_tokens=10000, max_cost=1.0, warning_threshold=0.8)
        ok, msg = budget.check_budget(500, 200, 0.85)
        assert ok is True
        assert "Warning" in msg


class TestPricingRegistry:
    """定价注册表测试"""
    
    def test_get_pricing_openai(self):
        """测试获取 OpenAI 定价"""
        pricing = PricingRegistry.get_pricing("gpt-4o")
        assert pricing is not None
        assert pricing.input_price > 0
        assert pricing.output_price > 0
    
    def test_get_pricing_google(self):
        """测试获取 Google 定价"""
        pricing = PricingRegistry.get_pricing("gemini-2.0-flash")
        assert pricing is not None
        assert pricing.input_price >= 0
    
    def test_get_pricing_unknown(self):
        """测试获取未知模型定价"""
        pricing = PricingRegistry.get_pricing("unknown-model-xyz")
        # 应该返回默认定价
        assert pricing is not None
        assert pricing.input_price == 0.01
    
    def test_calculate_cost(self):
        """测试成本计算"""
        cost = calculate_cost("gpt-4o", 1000, 500)
        assert cost > 0
        # gpt-4o: input $0.0025/1K, output $0.01/1K
        # expected: 1 * 0.0025 + 0.5 * 0.01 = 0.0025 + 0.005 = 0.0075
        assert abs(cost - 0.0075) < 0.0001
    
    def test_estimate_cost(self):
        """测试成本估算"""
        cost = estimate_cost("gpt-4o", "Hello world, this is a test prompt.", 100)
        assert cost > 0


class TestLLMCache:
    """LLM 缓存测试"""
    
    def test_cache_get_set(self):
        """测试缓存存取"""
        from sail_server.utils.llm.gateway import LLMCache
        
        cache = LLMCache(max_size=10, ttl_seconds=60)
        config = LLMExecutionConfig(provider="test", model="test-model")
        result = LLMExecutionResult(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            provider="test",
            model="test-model",
            latency_ms=100,
        )
        
        # 设置缓存
        cache.set("test prompt", config, result)
        
        # 获取缓存
        cached = cache.get("test prompt", config)
        assert cached is not None
        assert cached.cached is True
        assert cached.content == "test"
    
    def test_cache_disabled(self):
        """测试禁用缓存"""
        from sail_server.utils.llm.gateway import LLMCache
        
        cache = LLMCache(max_size=10, ttl_seconds=60)
        config = LLMExecutionConfig(
            provider="test",
            model="test-model",
            enable_caching=False,
        )
        result = LLMExecutionResult(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            provider="test",
            model="test-model",
            latency_ms=100,
        )
        
        cache.set("test prompt", config, result)
        cached = cache.get("test prompt", config)
        assert cached is None
    
    def test_cache_expiration(self):
        """测试缓存过期"""
        from sail_server.utils.llm.gateway import LLMCache
        import time
        
        cache = LLMCache(max_size=10, ttl_seconds=0)  # 立即过期
        config = LLMExecutionConfig(provider="test", model="test-model")
        result = LLMExecutionResult(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            provider="test",
            model="test-model",
            latency_ms=100,
        )
        
        cache.set("test prompt", config, result)
        time.sleep(0.1)  # 等待过期
        
        cached = cache.get("test prompt", config)
        assert cached is None


class TestLLMGateway:
    """LLM Gateway 测试"""
    
    @pytest.fixture
    def gateway(self):
        """创建测试 Gateway"""
        return LLMGateway(enable_cache=True)
    
    @pytest.fixture
    def mock_provider(self):
        """创建 Mock Provider"""
        provider = Mock()
        provider.provider_name = "mock"
        provider.complete = AsyncMock()
        provider.get_health_status = Mock(return_value={
            "provider": "mock",
            "healthy": True,
        })
        provider.config = Mock()
        provider.config.model = "mock-model"
        return provider
    
    @pytest.mark.asyncio
    async def test_execute_success(self, gateway, mock_provider):
        """测试执行成功"""
        gateway._providers["mock"] = mock_provider
        
        mock_response = ProviderResponse(
            content="Hello, world!",
            model="mock-model",
            provider="mock",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            finish_reason="stop",
        )
        mock_provider.complete.return_value = mock_response
        
        config = LLMExecutionConfig(
            provider="mock",
            model="mock-model",
            enable_caching=False,
        )
        
        result = await gateway.execute("Hello", config)
        
        assert result.content == "Hello, world!"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.provider == "mock"
        assert result.cached is False
    
    @pytest.mark.asyncio
    async def test_execute_with_cache(self, gateway, mock_provider):
        """测试缓存命中"""
        gateway._providers["mock"] = mock_provider
        
        mock_response = ProviderResponse(
            content="Hello, world!",
            model="mock-model",
            provider="mock",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
        mock_provider.complete.return_value = mock_response
        
        config = LLMExecutionConfig(
            provider="mock",
            model="mock-model",
            enable_caching=True,
        )
        
        # 第一次调用
        result1 = await gateway.execute("Hello", config)
        assert result1.cached is False
        
        # 第二次调用（应该命中缓存）
        result2 = await gateway.execute("Hello", config)
        assert result2.cached is True
        
        # 验证只调用了一次 Provider
        assert mock_provider.complete.call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_budget_exceeded(self, gateway):
        """测试预算超限"""
        budget = TokenBudget(max_tokens=10, max_cost=0.001)
        config = LLMExecutionConfig(
            provider="mock",
            model="gpt-4o",  # 昂贵的模型
            enable_caching=False,
        )
        
        gateway._providers["mock"] = Mock()
        
        with pytest.raises(ProviderError) as exc_info:
            await gateway.execute("This is a very long prompt that will exceed token budget", config, budget)
        
        assert "BUDGET_EXCEEDED" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_provider_not_found(self, gateway):
        """测试 Provider 未注册"""
        config = LLMExecutionConfig(
            provider="nonexistent",
            model="model",
        )
        
        with pytest.raises(ProviderError) as exc_info:
            await gateway.execute("Hello", config)
        
        assert "not registered" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_with_fallback(self, gateway):
        """测试降级调用"""
        # 设置两个 mock provider
        provider1 = Mock()
        provider1.complete = AsyncMock(side_effect=ProviderError("Provider 1 failed"))
        provider1.get_health_status = Mock(return_value={"healthy": False})
        
        provider2 = Mock()
        provider2.complete = AsyncMock(return_value=ProviderResponse(
            content="Success from provider 2",
            model="model-2",
            provider="provider2",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ))
        provider2.get_health_status = Mock(return_value={"healthy": True})
        
        gateway._providers["provider1"] = provider1
        gateway._providers["provider2"] = provider2
        
        configs = [
            LLMExecutionConfig(provider="provider1", model="model-1"),
            LLMExecutionConfig(provider="provider2", model="model-2"),
        ]
        
        result = await gateway.execute_with_fallback("Hello", configs)
        
        assert result.content == "Success from provider 2"
        assert result.provider == "provider2"
    
    @pytest.mark.asyncio
    async def test_execute_fallback_all_fail(self, gateway):
        """测试所有 Provider 都失败"""
        provider1 = Mock()
        provider1.complete = AsyncMock(side_effect=ProviderError("Provider 1 failed"))
        
        provider2 = Mock()
        provider2.complete = AsyncMock(side_effect=ProviderError("Provider 2 failed"))
        
        gateway._providers["provider1"] = provider1
        gateway._providers["provider2"] = provider2
        
        configs = [
            LLMExecutionConfig(provider="provider1", model="model-1"),
            LLMExecutionConfig(provider="provider2", model="model-2"),
        ]
        
        with pytest.raises(ProviderError) as exc_info:
            await gateway.execute_with_fallback("Hello", configs)
        
        assert "ALL_PROVIDERS_FAILED" in str(exc_info.value)
    
    def test_get_stats(self, gateway):
        """测试获取统计信息"""
        # 添加一些统计数据
        result = LLMExecutionResult(
            content="test",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01,
            provider="test",
            model="test",
            latency_ms=500,
        )
        
        gateway._stats.record_request(result, success=True)
        gateway._stats.record_request(result, success=False)
        
        stats = gateway.get_stats()
        
        assert stats.total_requests == 2
        assert stats.successful_requests == 1
        assert stats.failed_requests == 1
        assert stats.total_cost == 0.02
        assert stats.total_tokens == 300
    
    def test_get_cache_stats(self, gateway):
        """测试获取缓存统计"""
        stats = gateway.get_cache_stats()
        
        assert stats["enabled"] is True
        assert "size" in stats
        assert "max_size" in stats
    
    def test_clear_cache(self, gateway):
        """测试清空缓存"""
        # 添加一些缓存
        from sail_server.utils.llm.gateway import LLMCache
        
        if gateway._cache:
            gateway._cache.set(
                "test",
                LLMExecutionConfig(provider="test", model="test"),
                LLMExecutionResult(
                    content="test",
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    cost=0.001,
                    provider="test",
                    model="test",
                    latency_ms=100,
                )
            )
            
            gateway.clear_cache()
            
            stats = gateway.get_cache_stats()
            assert stats["size"] == 0


class TestCircuitBreaker:
    """熔断器测试"""
    
    def test_circuit_closed_initially(self):
        """测试熔断器初始状态"""
        from sail_server.utils.llm.providers.base import CircuitBreakerState
        
        cb = CircuitBreakerState()
        assert cb.state == "closed"
        assert cb.can_execute() is True
    
    def test_circuit_opens_after_failures(self):
        """测试熔断器在多次失败后打开"""
        from sail_server.utils.llm.providers.base import CircuitBreakerState
        
        cb = CircuitBreakerState(failure_threshold=3)
        
        # 记录失败
        assert cb.record_failure() is False  # 第1次
        assert cb.record_failure() is False  # 第2次
        assert cb.record_failure() is True   # 第3次，熔断器打开
        
        assert cb.state == "open"
        assert cb.can_execute() is False
    
    def test_circuit_resets_on_success(self):
        """测试成功时熔断器重置"""
        from sail_server.utils.llm.providers.base import CircuitBreakerState
        
        cb = CircuitBreakerState(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        
        assert cb.failures == 2
        
        cb.record_success()
        
        assert cb.failures == 0
        assert cb.state == "closed"
    
    def test_circuit_half_open_after_timeout(self):
        """测试超时后半开"""
        from sail_server.utils.llm.providers.base import CircuitBreakerState
        import time
        
        cb = CircuitBreakerState(
            failure_threshold=1,
            recovery_timeout=0.1  # 100ms 恢复
        )
        
        cb.record_failure()
        assert cb.state == "open"
        assert cb.can_execute() is False
        
        # 等待恢复
        time.sleep(0.15)
        
        assert cb.can_execute() is True
        assert cb.state == "half_open"


class TestLLMExecutionResult:
    """LLM 执行结果测试"""
    
    def test_to_dict(self):
        """测试转换为字典"""
        result = LLMExecutionResult(
            content="Hello",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            provider="test",
            model="test-model",
            latency_ms=100,
            finish_reason="stop",
        )
        
        data = result.to_dict()
        
        assert data["content"] == "Hello"
        assert data["prompt_tokens"] == 10
        assert data["completion_tokens"] == 5
        assert data["total_tokens"] == 15
        assert data["cost"] == 0.001
        assert data["provider"] == "test"
        assert data["model"] == "test-model"
        assert data["latency_ms"] == 100
        assert data["cached"] is False
        assert data["finish_reason"] == "stop"
