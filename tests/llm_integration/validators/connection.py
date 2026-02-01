# -*- coding: utf-8 -*-
# @file connection.py
# @brief LLM Connection Validator
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# LLM 服务连接稳定性验证器
# 测试各种 LLM 提供商的连接、响应时间、错误处理等
#

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .base import BaseValidator, ValidationReport, ValidationLevel

logger = logging.getLogger(__name__)


class LLMConnectionValidator(BaseValidator):
    """LLM 连接验证器"""
    
    # 测试用简单 prompt
    TEST_PROMPTS = {
        "echo": "Reply with exactly: 'Connection successful'",
        "json": "Reply with JSON: {\"status\": \"ok\"}",
        "chinese": "用中文回复：连接成功",
    }
    
    # 支持的提供商
    PROVIDERS = ["openai", "anthropic", "google", "local"]
    
    def __init__(
        self, 
        providers: Optional[List[str]] = None,
        test_real_connection: bool = True,
        timeout_seconds: int = 30,
    ):
        super().__init__("LLM Connection Validator")
        self.providers = providers or self.PROVIDERS
        self.test_real_connection = test_real_connection
        self.timeout_seconds = timeout_seconds
    
    async def validate(self) -> ValidationReport:
        """执行连接验证"""
        started_at = datetime.utcnow()
        
        # 1. 验证环境变量配置
        await self._validate_env_config()
        
        # 2. 验证 LLM 客户端初始化
        await self._validate_client_init()
        
        # 3. 验证实际连接 (如果启用)
        if self.test_real_connection:
            await self._validate_real_connections()
        else:
            self._skip("real_connection", "Real connection test disabled")
        
        # 4. 验证错误处理
        await self._validate_error_handling()
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
    
    async def _validate_env_config(self):
        """验证环境变量配置"""
        print("\n  >> Checking environment configuration...")
        
        env_checks = [
            ("OPENAI_API_KEY", "openai"),
            ("ANTHROPIC_API_KEY", "anthropic"),
            ("GOOGLE_API_KEY", "google"),
        ]
        
        configured_providers = []
        
        for env_var, provider in env_checks:
            if provider not in self.providers:
                continue
            
            value = os.getenv(env_var)
            if value and len(value) > 0:
                # 不暴露完整的 API key
                masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
                self._success(
                    f"env_{provider}",
                    f"{env_var} configured",
                    {"masked_value": masked}
                )
                configured_providers.append(provider)
            else:
                self._warning(
                    f"env_{provider}",
                    f"{env_var} not configured",
                    {"hint": f"Set {env_var} to enable {provider} provider"}
                )
        
        # 检查是否至少有一个提供商配置
        if not configured_providers:
            self._warning(
                "env_any_provider",
                "No LLM provider API keys configured",
                {"hint": "Configure at least one provider for real LLM testing"}
            )
        else:
            self._success(
                "env_any_provider",
                f"Providers configured: {', '.join(configured_providers)}",
            )
        
        return configured_providers
    
    async def _validate_client_init(self):
        """验证客户端初始化"""
        print("\n  >> Validating client initialization...")
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
            
            self._success("import_llm_module", "LLM module imported successfully")
        except ImportError as e:
            self._error("import_llm_module", f"Failed to import LLM module: {e}")
            return
        
        # 测试各提供商的客户端初始化
        for provider_name in self.providers:
            try:
                provider = LLMProvider(provider_name)
                config = LLMConfig.from_env(provider)
                
                # 尝试创建客户端
                result, duration, error = self._measure_sync(
                    lambda: LLMClient(config)
                )
                
                if error:
                    self._error(
                        f"client_init_{provider_name}",
                        f"Failed to initialize {provider_name} client: {error}",
                        duration_ms=duration
                    )
                else:
                    self._success(
                        f"client_init_{provider_name}",
                        f"{provider_name} client initialized",
                        {"provider": provider_name},
                        duration_ms=duration
                    )
            except Exception as e:
                self._error(
                    f"client_init_{provider_name}",
                    f"Client init error: {e}"
                )
    
    async def _validate_real_connections(self):
        """验证实际连接"""
        print("\n  >> Testing real LLM connections...")
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        except ImportError:
            self._skip("real_connection", "LLM module not available")
            return
        
        for provider_name in self.providers:
            if provider_name == "local":
                # 本地模式需要特殊处理
                await self._test_local_connection()
                continue
            
            if provider_name == "external":
                # external 模式不需要真实连接
                self._skip(
                    f"connection_{provider_name}",
                    "External mode does not require connection"
                )
                continue
            
            try:
                provider = LLMProvider(provider_name)
                config = LLMConfig.from_env(provider)
                
                if not config.validate():
                    self._skip(
                        f"connection_{provider_name}",
                        f"No API key configured for {provider_name}"
                    )
                    continue
                
                client = LLMClient(config)
                
                # 测试简单请求
                try:
                    result, duration, error = await self._measure_async(
                        asyncio.wait_for(
                            client.complete(self.TEST_PROMPTS["echo"]),
                            timeout=self.timeout_seconds
                        )
                    )
                    
                    if error:
                        if isinstance(error, asyncio.TimeoutError):
                            self._error(
                                f"connection_{provider_name}",
                                f"Connection timeout ({self.timeout_seconds}s)",
                                duration_ms=duration
                            )
                        else:
                            self._error(
                                f"connection_{provider_name}",
                                f"Connection failed: {error}",
                                duration_ms=duration
                            )
                    else:
                        # 验证响应
                        response_preview = result.content[:100] if result.content else ""
                        self._success(
                            f"connection_{provider_name}",
                            f"Connection successful (latency: {result.latency_ms}ms)",
                            {
                                "model": result.model,
                                "response_preview": response_preview,
                                "tokens_used": result.total_tokens,
                            },
                            duration_ms=duration
                        )
                        
                        # 额外检查响应质量
                        if result.latency_ms > 10000:
                            self._warning(
                                f"latency_{provider_name}",
                                f"High latency detected: {result.latency_ms}ms",
                                {"threshold": 10000}
                            )
                
                except Exception as e:
                    self._error(
                        f"connection_{provider_name}",
                        f"Unexpected error: {e}"
                    )
            
            except Exception as e:
                self._error(
                    f"connection_{provider_name}",
                    f"Setup error: {e}"
                )
    
    async def _test_local_connection(self):
        """测试本地 LLM 连接 (Ollama)"""
        import aiohttp
        
        base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        
        try:
            async with aiohttp.ClientSession() as session:
                # 检查 Ollama 服务是否运行
                try:
                    async with session.get(
                        f"{base_url}/api/version",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self._success(
                                "connection_local",
                                f"Ollama service running (version: {data.get('version', 'unknown')})",
                                {"url": base_url}
                            )
                        else:
                            self._warning(
                                "connection_local",
                                f"Ollama service responded with status {resp.status}",
                                {"url": base_url}
                            )
                except aiohttp.ClientConnectorError:
                    self._warning(
                        "connection_local",
                        f"Ollama service not running at {base_url}",
                        {"hint": "Start Ollama with: ollama serve"}
                    )
                except Exception as e:
                    self._warning(
                        "connection_local",
                        f"Could not connect to Ollama: {e}",
                        {"url": base_url}
                    )
        except ImportError:
            self._skip("connection_local", "aiohttp not installed")
    
    async def _validate_error_handling(self):
        """验证错误处理"""
        print("\n  >> Testing error handling...")
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        except ImportError:
            self._skip("error_handling", "LLM module not available")
            return
        
        # 测试无效 API key 的错误处理
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            api_key="invalid-key-for-testing",
        )
        
        client = LLMClient(config)
        
        try:
            # 这个应该失败，但应该优雅地处理
            result, duration, error = await self._measure_async(
                asyncio.wait_for(
                    client.complete("test"),
                    timeout=10
                )
            )
            
            if error:
                # 期望的行为：优雅地返回错误
                self._success(
                    "error_invalid_key",
                    "Invalid API key handled gracefully",
                    {"error_type": type(error).__name__}
                )
            else:
                self._warning(
                    "error_invalid_key",
                    "Expected error for invalid API key but got response"
                )
        except Exception as e:
            # 也是可接受的，只要不是崩溃
            self._success(
                "error_invalid_key",
                f"Invalid API key raised exception (expected): {type(e).__name__}"
            )
        
        # 测试 External 模式不应该执行实际调用
        config_external = LLMConfig(provider=LLMProvider.EXTERNAL)
        client_external = LLMClient(config_external)
        
        try:
            await client_external.complete("test")
            self._error(
                "error_external_mode",
                "External mode should not allow complete() calls"
            )
        except ValueError as e:
            self._success(
                "error_external_mode",
                "External mode correctly rejects complete() calls",
                {"error_message": str(e)[:100]}
            )
        except Exception as e:
            self._warning(
                "error_external_mode",
                f"Unexpected error type: {type(e).__name__}",
                {"error_message": str(e)[:100]}
            )


class LLMStabilityValidator(BaseValidator):
    """LLM 稳定性验证器 - 执行多次调用测试稳定性"""
    
    def __init__(
        self,
        provider: str = "openai",
        num_iterations: int = 5,
        delay_between_calls: float = 1.0,
    ):
        super().__init__(f"LLM Stability Validator ({provider})")
        self.provider = provider
        self.num_iterations = num_iterations
        self.delay_between_calls = delay_between_calls
    
    async def validate(self) -> ValidationReport:
        """执行稳定性验证"""
        started_at = datetime.utcnow()
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
        except ImportError:
            self._error("import", "LLM module not available")
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        try:
            provider = LLMProvider(self.provider)
            config = LLMConfig.from_env(provider)
            
            if not config.validate():
                self._skip("stability_test", f"No API key configured for {self.provider}")
                return ValidationReport(
                    validator_name=self.name,
                    started_at=started_at,
                    results=self.results,
                )
            
            client = LLMClient(config)
        except Exception as e:
            self._error("client_init", f"Failed to initialize client: {e}")
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        print(f"\n  >> Running {self.num_iterations} stability iterations...")
        
        latencies = []
        successes = 0
        failures = 0
        
        for i in range(self.num_iterations):
            self._report_progress(
                f"Iteration {i + 1}/{self.num_iterations}",
                i + 1,
                self.num_iterations
            )
            
            try:
                result, duration, error = await self._measure_async(
                    asyncio.wait_for(
                        client.complete(f"Say 'iteration {i + 1} complete'"),
                        timeout=30
                    )
                )
                
                if error:
                    failures += 1
                    self._warning(
                        f"iteration_{i + 1}",
                        f"Failed: {error}",
                        duration_ms=duration
                    )
                else:
                    successes += 1
                    latencies.append(result.latency_ms)
                    self._success(
                        f"iteration_{i + 1}",
                        f"Success (latency: {result.latency_ms}ms)",
                        duration_ms=duration
                    )
                
                # 延迟以避免 rate limiting
                if i < self.num_iterations - 1:
                    await asyncio.sleep(self.delay_between_calls)
                    
            except Exception as e:
                failures += 1
                self._error(f"iteration_{i + 1}", f"Exception: {e}")
        
        # 汇总结果
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            self._success(
                "stability_summary",
                f"Stability test complete: {successes}/{self.num_iterations} successful",
                {
                    "success_rate": f"{successes/self.num_iterations*100:.1f}%",
                    "avg_latency_ms": round(avg_latency, 2),
                    "min_latency_ms": min_latency,
                    "max_latency_ms": max_latency,
                    "latency_variance": round(max_latency - min_latency, 2),
                }
            )
        else:
            self._error(
                "stability_summary",
                "No successful iterations",
                {"total_failures": failures}
            )
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
