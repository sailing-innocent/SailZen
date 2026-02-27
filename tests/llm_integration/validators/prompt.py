# -*- coding: utf-8 -*-
# @file prompt.py
# @brief Prompt Template Validator
# @author sailing-innocent
# @date 2025-02-01
# ---------------------------------
#
# Prompt 模板功能验证器
# 测试模板加载、变量渲染、输出验证等功能
#

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from .base import BaseValidator, ValidationReport, ValidationLevel

logger = logging.getLogger(__name__)


class PromptValidator(BaseValidator):
    """Prompt 模板验证器"""
    
    # 测试用变量
    TEST_VARIABLES = {
        "work_title": "测试小说",
        "chapter_range": "第1章 - 第3章",
        "chapter_contents": """
### 第一章 开始

这是一个测试章节的内容。主角张三第一次出现在故事中。
他住在一个叫做"青云镇"的小镇上，是一位普通的铁匠。

### 第二章 相遇

张三在镇上遇到了神秘的道士李四。李四手持一把名为"青霜"的宝剑。
他告诉张三："你有习武的天赋，愿意随我修行吗？"

### 第三章 抉择

张三思考了一整夜，最终决定跟随李四离开家乡，开始修行之路。
""",
        "known_characters": "张三, 李四",
        "setting_types": "item, location, organization",
    }
    
    # 预期的模板 ID
    EXPECTED_TEMPLATES = [
        "outline_extraction_v1",
        "character_detection_v1",
        "setting_extraction_v1",
    ]
    
    def __init__(
        self,
        test_real_llm: bool = False,
        llm_provider: str = "moonshot",
    ):
        super().__init__("Prompt Template Validator")
        self.test_real_llm = test_real_llm
        self.llm_provider = llm_provider
    
    async def validate(self) -> ValidationReport:
        """执行 Prompt 验证"""
        started_at = datetime.utcnow()
        
        # 1. 验证模板管理器初始化
        manager = await self._validate_manager_init()
        if not manager:
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        # 2. 验证内置模板存在
        await self._validate_builtin_templates(manager)
        
        # 3. 验证模板渲染功能
        await self._validate_template_rendering(manager)
        
        # 4. 验证变量替换
        await self._validate_variable_substitution(manager)
        
        # 5. 验证输出 Schema 验证
        await self._validate_output_validation(manager)
        
        # 6. 验证导出格式
        await self._validate_export_formats()
        
        # 7. 可选：用真实 LLM 测试 Prompt
        if self.test_real_llm:
            await self._validate_with_real_llm(manager)
        else:
            self._skip("real_llm_test", "Real LLM test disabled")
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
    
    async def _validate_manager_init(self):
        """验证模板管理器初始化"""
        print("\n  >> Initializing template manager...")
        
        try:
            from sail_server.utils.llm import PromptTemplateManager, get_template_manager
            
            result, duration, error = self._measure_sync(get_template_manager)
            
            if error:
                self._error(
                    "manager_init",
                    f"Failed to initialize template manager: {error}",
                    duration_ms=duration
                )
                return None
            
            manager = result
            template_count = len(manager.templates)
            
            self._success(
                "manager_init",
                f"Template manager initialized with {template_count} templates",
                {"template_count": template_count},
                duration_ms=duration
            )
            
            return manager
            
        except ImportError as e:
            self._error("import", f"Failed to import prompt module: {e}")
            return None
    
    async def _validate_builtin_templates(self, manager):
        """验证内置模板存在"""
        print("\n  >> Checking builtin templates...")
        
        for template_id in self.EXPECTED_TEMPLATES:
            template = manager.get_template(template_id)
            
            if template:
                # 验证模板必要字段
                missing_fields = []
                for field in ['id', 'name', 'task_type', 'system_prompt', 'user_prompt_template']:
                    if not getattr(template, field, None):
                        missing_fields.append(field)
                
                if missing_fields:
                    self._warning(
                        f"template_{template_id}",
                        f"Template missing fields: {', '.join(missing_fields)}",
                        {"template_id": template_id}
                    )
                else:
                    self._success(
                        f"template_{template_id}",
                        f"Template '{template.name}' valid",
                        {
                            "task_type": template.task_type,
                            "version": template.version,
                            "has_schema": bool(template.output_schema),
                        }
                    )
            else:
                self._error(
                    f"template_{template_id}",
                    f"Template not found: {template_id}"
                )
        
        # 列出所有可用模板
        all_templates = manager.list_templates()
        self._success(
            "template_listing",
            f"Total {len(all_templates)} templates available",
            {"template_ids": [t.id for t in all_templates]}
        )
    
    async def _validate_template_rendering(self, manager):
        """验证模板渲染功能"""
        print("\n  >> Testing template rendering...")
        
        for template_id in self.EXPECTED_TEMPLATES:
            template = manager.get_template(template_id)
            if not template:
                continue
            
            try:
                result, duration, error = self._measure_sync(
                    manager.render,
                    template_id,
                    self.TEST_VARIABLES
                )
                
                if error:
                    self._error(
                        f"render_{template_id}",
                        f"Rendering failed: {error}",
                        duration_ms=duration
                    )
                    continue
                
                rendered = result
                
                # 检查渲染结果
                checks = {
                    "has_system_prompt": len(rendered.system_prompt) > 0,
                    "has_user_prompt": len(rendered.user_prompt) > 0,
                    "has_token_estimate": rendered.estimated_tokens > 0,
                    "work_title_replaced": self.TEST_VARIABLES["work_title"] in rendered.user_prompt,
                }
                
                all_passed = all(checks.values())
                
                if all_passed:
                    self._success(
                        f"render_{template_id}",
                        f"Rendered successfully ({rendered.estimated_tokens} tokens)",
                        {
                            "system_length": len(rendered.system_prompt),
                            "user_length": len(rendered.user_prompt),
                            "estimated_tokens": rendered.estimated_tokens,
                        },
                        duration_ms=duration
                    )
                else:
                    failed_checks = [k for k, v in checks.items() if not v]
                    self._warning(
                        f"render_{template_id}",
                        f"Rendering incomplete: {', '.join(failed_checks)}",
                        checks,
                        duration_ms=duration
                    )
                    
            except Exception as e:
                self._error(
                    f"render_{template_id}",
                    f"Exception during rendering: {e}"
                )
    
    async def _validate_variable_substitution(self, manager):
        """验证变量替换功能"""
        print("\n  >> Testing variable substitution...")
        
        # 测试简单变量替换
        template = manager.get_template("outline_extraction_v1")
        if not template:
            self._skip("variable_substitution", "No template available for testing")
            return
        
        test_cases = [
            {
                "name": "basic_variables",
                "vars": {"work_title": "我的测试", "chapter_range": "第1章"},
                "expect_in_result": ["我的测试", "第1章"],
            },
            {
                "name": "empty_optional",
                "vars": {"work_title": "测试", "chapter_range": "第1章", "known_characters": ""},
                "expect_not_in_result": ["已知人物："],
            },
            {
                "name": "with_optional",
                "vars": {"work_title": "测试", "chapter_range": "第1章", "known_characters": "张三"},
                "expect_in_result": ["张三"],
            },
            {
                "name": "chinese_content",
                "vars": {
                    "work_title": "仙侠修真传",
                    "chapter_range": "第一章至第十章",
                    "chapter_contents": "主角开始修炼",
                },
                "expect_in_result": ["仙侠修真传", "主角开始修炼"],
            },
        ]
        
        for test_case in test_cases:
            try:
                rendered = manager.render("outline_extraction_v1", test_case["vars"])
                full_text = rendered.system_prompt + rendered.user_prompt
                
                passed = True
                details = {}
                
                # 检查必须包含的内容
                if "expect_in_result" in test_case:
                    for expected in test_case["expect_in_result"]:
                        if expected not in full_text:
                            passed = False
                            details[f"missing_{expected[:20]}"] = True
                
                # 检查不应该包含的内容
                if "expect_not_in_result" in test_case:
                    for unexpected in test_case["expect_not_in_result"]:
                        if unexpected in full_text:
                            passed = False
                            details[f"unexpected_{unexpected[:20]}"] = True
                
                if passed:
                    self._success(
                        f"var_sub_{test_case['name']}",
                        f"Variable substitution correct"
                    )
                else:
                    self._warning(
                        f"var_sub_{test_case['name']}",
                        "Variable substitution incomplete",
                        details
                    )
                    
            except Exception as e:
                self._error(
                    f"var_sub_{test_case['name']}",
                    f"Exception: {e}"
                )
    
    async def _validate_output_validation(self, manager):
        """验证输出 Schema 验证功能"""
        print("\n  >> Testing output validation...")
        
        # 测试有效输出
        valid_outline_output = {
            "plot_points": [
                {
                    "title": "主角登场",
                    "type": "setup",
                    "importance": "major",
                    "summary": "张三首次出现",
                }
            ],
            "overall_summary": "故事开始了"
        }
        
        result = manager.validate_output("outline_extraction_v1", valid_outline_output)
        
        if result.get("valid"):
            self._success(
                "output_valid_check",
                "Valid output correctly validated"
            )
        else:
            self._error(
                "output_valid_check",
                f"Valid output rejected: {result.get('errors')}",
                result
            )
        
        # 测试无效输出（缺少必填字段）
        invalid_output = {
            "plot_points": []
            # 缺少 overall_summary
        }
        
        result = manager.validate_output("outline_extraction_v1", invalid_output)
        
        if not result.get("valid"):
            self._success(
                "output_invalid_check",
                "Invalid output correctly rejected",
                {"errors": result.get("errors", [])}
            )
        else:
            self._warning(
                "output_invalid_check",
                "Invalid output was not rejected (schema validation may be lenient)"
            )
        
        # 测试字符类型输出验证
        valid_character_output = {
            "characters": [
                {
                    "canonical_name": "张三",
                    "role_type": "protagonist",
                }
            ],
            "total_characters": 1
        }
        
        result = manager.validate_output("character_detection_v1", valid_character_output)
        
        if result.get("valid"):
            self._success(
                "output_character_check",
                "Character output validated"
            )
        else:
            self._warning(
                "output_character_check",
                f"Character output validation failed: {result.get('errors')}"
            )
    
    async def _validate_export_formats(self):
        """验证导出格式"""
        print("\n  >> Testing export formats...")
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
            
            config = LLMConfig(provider=LLMProvider.EXTERNAL, model="gpt-4")
            client = LLMClient(config)
            
            exported = client.generate_prompt_only(
                prompt="这是用户提示词",
                system="这是系统提示词",
                task_id=1,
                chunk_index=0,
                total_chunks=1,
            )
            
            # 检查各种格式
            formats = {
                "openai": exported.to_openai_format(),
                "anthropic": exported.to_anthropic_format(),
                "google": exported.to_google_format(),
                "plain": exported.to_plain_text(),
                "markdown": exported.to_markdown(),
                "dict": exported.to_dict(),
            }
            
            for format_name, content in formats.items():
                if format_name in ["plain", "markdown"]:
                    is_valid = isinstance(content, str) and len(content) > 0
                else:
                    is_valid = isinstance(content, dict) and len(content) > 0
                
                if is_valid:
                    self._success(
                        f"export_{format_name}",
                        f"Export format '{format_name}' valid",
                        {"content_type": type(content).__name__}
                    )
                else:
                    self._error(
                        f"export_{format_name}",
                        f"Export format '{format_name}' invalid"
                    )
            
            # 验证 OpenAI 格式结构
            openai_format = formats["openai"]
            required_keys = ["model", "messages", "temperature"]
            missing = [k for k in required_keys if k not in openai_format]
            
            if not missing:
                self._success(
                    "export_openai_structure",
                    "OpenAI format has correct structure"
                )
            else:
                self._error(
                    "export_openai_structure",
                    f"OpenAI format missing keys: {missing}"
                )
            
        except Exception as e:
            self._error("export_formats", f"Exception: {e}")
    
    async def _validate_with_real_llm(self, manager):
        """用真实 LLM 测试 Prompt"""
        print("\n  >> Testing with real LLM...")
        
        try:
            from sail_server.utils.llm import LLMClient, LLMConfig, LLMProvider
            import asyncio
            
            provider = LLMProvider(self.llm_provider)
            config = LLMConfig.from_env(provider)
            
            if not config.validate():
                self._skip(
                    "real_llm_test",
                    f"No API key configured for {self.llm_provider}"
                )
                return
            
            client = LLMClient(config)
            
            # 使用较短的测试内容
            short_vars = {
                "work_title": "测试小说",
                "chapter_range": "第1章",
                "chapter_contents": "张三是一个铁匠。李四是一个道士。他们在青云镇相遇了。",
                "known_characters": "",
            }
            
            rendered = manager.render("character_detection_v1", short_vars)
            
            # 执行 LLM 调用
            result, duration, error = await self._measure_async(
                asyncio.wait_for(
                    client.complete(rendered.user_prompt, system=rendered.system_prompt),
                    timeout=60
                )
            )
            
            if error:
                self._error(
                    "real_llm_call",
                    f"LLM call failed: {error}",
                    duration_ms=duration
                )
                return
            
            self._success(
                "real_llm_call",
                f"LLM responded (latency: {result.latency_ms}ms)",
                {
                    "model": result.model,
                    "tokens": result.total_tokens,
                },
                duration_ms=duration
            )
            
            # 尝试解析 JSON 响应
            content = result.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            try:
                parsed = json.loads(content.strip())
                
                # 验证输出
                validation = manager.validate_output("character_detection_v1", parsed)
                
                if validation.get("valid"):
                    characters = parsed.get("characters", [])
                    self._success(
                        "real_llm_parse",
                        f"LLM output parsed successfully ({len(characters)} characters found)",
                        {
                            "characters": [c.get("canonical_name") for c in characters[:5]],
                            "valid": True,
                        }
                    )
                else:
                    self._warning(
                        "real_llm_parse",
                        "LLM output parsed but validation failed",
                        {"errors": validation.get("errors", [])}
                    )
                    
            except json.JSONDecodeError as e:
                self._warning(
                    "real_llm_parse",
                    f"LLM output is not valid JSON: {e}",
                    {"response_preview": content[:200]}
                )
                
        except Exception as e:
            self._error("real_llm_test", f"Exception: {e}")


class PromptPerformanceValidator(BaseValidator):
    """Prompt 性能验证器 - 测试模板渲染性能"""
    
    def __init__(self, iterations: int = 100):
        super().__init__("Prompt Performance Validator")
        self.iterations = iterations
    
    async def validate(self) -> ValidationReport:
        """执行性能验证"""
        started_at = datetime.utcnow()
        
        try:
            from sail_server.utils.llm import get_template_manager
            manager = get_template_manager()
        except ImportError as e:
            self._error("import", f"Failed to import: {e}")
            return ValidationReport(
                validator_name=self.name,
                started_at=started_at,
                results=self.results,
            )
        
        print(f"\n  >> Running {self.iterations} render iterations...")
        
        test_vars = {
            "work_title": "测试" * 10,
            "chapter_range": "第1章",
            "chapter_contents": "内容" * 1000,  # 约 2000 字符
            "known_characters": "张三, 李四, 王五",
        }
        
        templates = ["outline_extraction_v1", "character_detection_v1", "setting_extraction_v1"]
        
        for template_id in templates:
            template = manager.get_template(template_id)
            if not template:
                self._skip(f"perf_{template_id}", "Template not found")
                continue
            
            times = []
            for i in range(self.iterations):
                _, duration, error = self._measure_sync(
                    manager.render,
                    template_id,
                    test_vars
                )
                if not error:
                    times.append(duration)
            
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                # 性能阈值：平均渲染时间应小于 10ms
                if avg_time < 10:
                    self._success(
                        f"perf_{template_id}",
                        f"Avg render time: {avg_time:.2f}ms",
                        {
                            "avg_ms": round(avg_time, 2),
                            "min_ms": min_time,
                            "max_ms": max_time,
                            "iterations": len(times),
                        }
                    )
                else:
                    self._warning(
                        f"perf_{template_id}",
                        f"Slow render time: {avg_time:.2f}ms (threshold: 10ms)",
                        {
                            "avg_ms": round(avg_time, 2),
                            "min_ms": min_time,
                            "max_ms": max_time,
                        }
                    )
            else:
                self._error(f"perf_{template_id}", "All iterations failed")
        
        return ValidationReport(
            validator_name=self.name,
            started_at=started_at,
            results=self.results,
        )
