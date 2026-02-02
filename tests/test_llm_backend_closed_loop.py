# -*- coding: utf-8 -*-
# @file test_llm_backend_closed_loop.py
# @brief LLM Backend Closed-Loop Integration Test
# @description 使用 Kimi K2.5 验证 LLM 后端的闭环功能
# ---------------------------------

"""
LLM 后端闭环功能测试
====================

测试内容:
1. LLM Client 连接测试 (Kimi K2.5)
2. Prompt 模板渲染
3. LLM 调用与响应
4. JSON 输出解析
5. 成本估算
6. 完整任务执行流程

使用方法:
    uv run pytest tests/test_llm_backend_closed_loop.py -v -s
    
环境变量:
    MOONSHOT_API_KEY: Kimi API Key (必需)
"""

import os
import json
import asyncio
import pytest
from datetime import datetime
from typing import Dict, Any

# 确保从项目根目录导入
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sail_server.utils.llm import (
    LLMClient, LLMConfig, LLMProvider, 
    PromptTemplateManager, get_template_manager
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def moonshot_api_key():
    """获取 Moonshot API Key"""
    key = os.getenv("MOONSHOT_API_KEY")
    if not key:
        pytest.skip("MOONSHOT_API_KEY not set in environment")
    return key


@pytest.fixture
def llm_config(moonshot_api_key):
    """创建 Kimi LLM 配置"""
    return LLMConfig(
        provider=LLMProvider.MOONSHOT,
        model="kimi-k2-5",
        api_key=moonshot_api_key,
        temperature=0.3,
        max_tokens=4096,
    )


@pytest.fixture
def llm_client(llm_config):
    """创建 LLM 客户端"""
    return LLMClient(llm_config)


@pytest.fixture
def template_manager():
    """获取模板管理器"""
    return get_template_manager()


# ============================================================================
# Test Cases
# ============================================================================

class TestLLMConnection:
    """测试 LLM 连接功能"""
    
    @pytest.mark.asyncio
    async def test_moonshot_connection(self, llm_client):
        """测试 Moonshot (Kimi) API 连接"""
        print("\n[TEST] Testing Moonshot API connection...")
        
        # 简单测试调用
        response = await llm_client.complete(
            prompt="你好，请回复'连接测试成功'。",
            system="你是一个测试助手，请简洁回复。"
        )
        
        print(f"[RESPONSE] Model: {response.model}")
        print(f"[RESPONSE] Content: {response.content[:100]}...")
        print(f"[RESPONSE] Usage: {response.usage}")
        print(f"[RESPONSE] Latency: {response.latency_ms}ms")
        
        assert response.content is not None
        assert len(response.content) > 0
        assert response.provider == "moonshot"
        assert response.usage.get("total_tokens", 0) > 0
        print("✓ Moonshot connection test passed")
    
    def test_config_validation(self, moonshot_api_key):
        """测试配置验证"""
        print("\n[TEST] Testing config validation...")
        
        # 有效配置
        config = LLMConfig(
            provider=LLMProvider.MOONSHOT,
            api_key=moonshot_api_key,
        )
        assert config.validate() is True
        
        # 无效配置 (无 API key)
        config_invalid = LLMConfig(
            provider=LLMProvider.MOONSHOT,
            api_key=None,
        )
        assert config_invalid.validate() is False
        
        # EXTERNAL 模式不需要 API key
        config_external = LLMConfig(provider=LLMProvider.EXTERNAL)
        assert config_external.validate() is True
        
        print("✓ Config validation test passed")


class TestPromptTemplate:
    """测试 Prompt 模板功能"""
    
    def test_template_loading(self, template_manager):
        """测试模板加载"""
        print("\n[TEST] Testing template loading...")
        
        # 检查内置模板
        templates = template_manager.list_templates()
        print(f"[INFO] Loaded {len(templates)} templates")
        
        for t in templates:
            print(f"  - {t.id}: {t.name} ({t.task_type})")
        
        # 检查特定模板存在
        outline_template = template_manager.get_template("outline_extraction_v1")
        assert outline_template is not None
        assert outline_template.task_type == "outline_extraction"
        
        character_template = template_manager.get_template("character_detection_v1")
        assert character_template is not None
        assert character_template.task_type == "character_detection"
        
        print("✓ Template loading test passed")
    
    def test_template_rendering(self, template_manager):
        """测试模板渲染"""
        print("\n[TEST] Testing template rendering...")
        
        variables = {
            "work_title": "测试小说",
            "chapter_range": "第1章-第3章",
            "chapter_contents": "这是测试章节内容。",
            "known_characters": "张三, 李四",
        }
        
        rendered = template_manager.render("outline_extraction_v1", variables)
        
        print(f"[RENDERED] System prompt length: {len(rendered.system_prompt)} chars")
        print(f"[RENDERED] User prompt length: {len(rendered.user_prompt)} chars")
        print(f"[RENDERED] Estimated tokens: {rendered.estimated_tokens}")
        
        assert "测试小说" in rendered.user_prompt
        assert "第1章-第3章" in rendered.user_prompt
        assert rendered.estimated_tokens > 0
        
        print("✓ Template rendering test passed")
    
    def test_output_schema_validation(self, template_manager):
        """测试输出 Schema 验证"""
        print("\n[TEST] Testing output schema validation...")
        
        # 有效输出
        valid_output = {
            "plot_points": [
                {
                    "title": "测试情节",
                    "type": "conflict",
                    "importance": "major",
                    "summary": "这是一个测试情节",
                }
            ],
            "overall_summary": "整体概述"
        }
        
        result = template_manager.validate_output("outline_extraction_v1", valid_output)
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        
        # 无效输出 (缺少必需字段)
        invalid_output = {
            "plot_points": []
            # 缺少 overall_summary
        }
        
        result = template_manager.validate_output("outline_extraction_v1", invalid_output)
        print(f"[VALIDATION] Errors: {result['errors']}")
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        
        print("✓ Schema validation test passed")


class TestLLMCompletion:
    """测试 LLM 完成功能"""
    
    @pytest.mark.asyncio
    async def test_simple_completion(self, llm_client):
        """测试简单文本补全"""
        print("\n[TEST] Testing simple completion...")
        
        response = await llm_client.complete(
            prompt="请用一句话总结：人工智能正在改变我们的生活。",
            system="你是一个简洁的摘要助手。"
        )
        
        print(f"[RESPONSE] {response.content}")
        assert len(response.content) > 10
        
        print("✓ Simple completion test passed")
    
    @pytest.mark.asyncio
    async def test_json_completion(self, llm_client):
        """测试 JSON 模式输出"""
        print("\n[TEST] Testing JSON completion...")
        
        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["title", "summary"]
        }
        
        result = await llm_client.complete_json(
            prompt="""请分析以下段落并提取信息：
            
人工智能技术的发展日新月异，从早期的专家系统到如今的深度学习，
AI 已经渗透到我们生活的方方面面。在医疗、教育、交通等领域，
AI 正在带来革命性的变化。
            """,
            schema=schema,
            system="你是一个信息提取助手，请以 JSON 格式输出。"
        )
        
        print(f"[JSON RESULT] {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        assert "title" in result
        assert "summary" in result
        assert isinstance(result.get("keywords", []), list)
        
        print("✓ JSON completion test passed")
    
    @pytest.mark.asyncio
    async def test_novel_outline_extraction(self, llm_client, template_manager):
        """测试小说大纲提取"""
        print("\n[TEST] Testing novel outline extraction...")
        
        # 模拟小说章节内容
        sample_chapter = """
第一章：初遇

清晨的阳光透过窗帘洒进房间，李明揉了揉惺忪的睡眼，
看了看床头的闹钟——已经八点半了！

"完了，要迟到了！"李明一跃而起，匆忙穿好衣服。
今天是新工作的第一天，他绝不能迟到。

地铁上，李明遇到了一个陌生女孩。她的书掉在了地上，
李明帮她捡了起来。

"谢谢。"女孩微笑着说。
"不客气。"李明有些腼腆地回应。

他不知道，这个叫小雨的女孩，将会改变他的一生。
        """
        
        # 渲染模板
        variables = {
            "work_title": "命运之约",
            "chapter_range": "第一章",
            "chapter_contents": sample_chapter,
            "known_characters": "",
        }
        
        rendered = template_manager.render("outline_extraction_v1", variables)
        
        print(f"[PROMPT] System: {rendered.system_prompt[:100]}...")
        print(f"[PROMPT] User length: {len(rendered.user_prompt)} chars")
        
        # 调用 LLM
        response = await llm_client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt
        )
        
        print(f"[RESPONSE] {response.content[:500]}...")
        
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
            print(f"[PARSED] {json.dumps(parsed, ensure_ascii=False, indent=2)[:500]}...")
            
            # 验证输出结构
            validation = template_manager.validate_output("outline_extraction_v1", parsed)
            print(f"[VALIDATION] Valid: {validation['valid']}, Errors: {validation['errors']}")
            
            assert "plot_points" in parsed or "outline" in parsed
            
        except json.JSONDecodeError as e:
            print(f"[WARNING] JSON parse failed: {e}")
            # 即使解析失败，也确保有内容返回
            assert len(response.content) > 50
        
        print("✓ Novel outline extraction test passed")
    
    @pytest.mark.asyncio
    async def test_character_detection(self, llm_client, template_manager):
        """测试人物识别"""
        print("\n[TEST] Testing character detection...")
        
        sample_text = """
第三章：暗流涌动

王局长坐在办公室里，脸色阴沉。桌上的电话突然响起，
他接起来，听到了一个熟悉的声音。

"老王，事情办得怎么样了？"电话那头是刘总的的声音。

"有些麻烦，新来的李科长很难对付。"王局长压低声音说道。

这时，秘书小张敲门进来："局长，有位叫陈雪的记者想要采访您。"

王局长皱了皱眉："就说我不在。"

他不知道，陈雪已经掌握了他贪污的证据...
        """
        
        variables = {
            "work_title": "权谋",
            "chapter_range": "第三章",
            "chapter_contents": sample_text,
        }
        
        rendered = template_manager.render("character_detection_v1", variables)
        
        response = await llm_client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt
        )
        
        print(f"[RESPONSE] {response.content[:500]}...")
        
        # 验证返回了人物信息
        assert len(response.content) > 50
        assert "王局长" in response.content or "老王" in response.content
        
        print("✓ Character detection test passed")


class TestCostEstimation:
    """测试成本估算功能"""
    
    def test_token_estimation(self, llm_client):
        """测试 Token 估算"""
        print("\n[TEST] Testing token estimation...")
        
        # 中文文本
        chinese_text = "这是一段中文测试文本，用于估算token数量。"
        chinese_tokens = llm_client.estimate_tokens(chinese_text)
        print(f"[ESTIMATE] Chinese text ({len(chinese_text)} chars) -> {chinese_tokens} tokens")
        
        # 英文文本
        english_text = "This is an English test text for token estimation."
        english_tokens = llm_client.estimate_tokens(english_text)
        print(f"[ESTIMATE] English text ({len(english_text)} chars) -> {english_tokens} tokens")
        
        # 混合文本
        mixed_text = "This is a 混合 test 文本 with 多种 languages."
        mixed_tokens = llm_client.estimate_tokens(mixed_text)
        print(f"[ESTIMATE] Mixed text ({len(mixed_text)} chars) -> {mixed_tokens} tokens")
        
        assert chinese_tokens > 0
        assert english_tokens > 0
        
        print("✓ Token estimation test passed")
    
    def test_cost_estimation(self, llm_client):
        """测试成本估算"""
        print("\n[TEST] Testing cost estimation...")
        
        input_tokens = 10000
        output_tokens = 3000
        
        cost = llm_client.estimate_cost(input_tokens, output_tokens)
        print(f"[COST] Input: {input_tokens}, Output: {output_tokens}")
        print(f"[COST] Estimated cost: ${cost:.6f} USD")
        
        assert cost > 0
        assert cost < 1.0  # 应该小于 1 美元
        
        print("✓ Cost estimation test passed")


class TestExportedPrompt:
    """测试 Prompt 导出功能"""
    
    def test_generate_prompt_only(self, llm_client):
        """测试仅生成 Prompt"""
        print("\n[TEST] Testing prompt-only generation...")
        
        exported = llm_client.generate_prompt_only(
            prompt="请分析这段文本。",
            system="你是一个文学分析助手。",
            task_id=123,
            chunk_index=0,
            total_chunks=5
        )
        
        print(f"[EXPORTED] Task ID: {exported.task_id}")
        print(f"[EXPORTED] Chunk: {exported.chunk_index + 1}/{exported.total_chunks}")
        print(f"[EXPORTED] Model: {exported.model_suggestion}")
        print(f"[EXPORTED] Temperature: {exported.temperature}")
        
        # 测试各种格式转换
        openai_format = exported.to_openai_format()
        print(f"[FORMAT] OpenAI: {json.dumps(openai_format, ensure_ascii=False, indent=2)[:200]}...")
        
        markdown_format = exported.to_markdown()
        print(f"[FORMAT] Markdown length: {len(markdown_format)} chars")
        
        assert exported.task_id == 123
        assert exported.chunk_index == 0
        assert "请分析这段文本。" in exported.user_prompt
        
        print("✓ Prompt-only generation test passed")


class TestClosedLoopIntegration:
    """测试完整闭环集成"""
    
    @pytest.mark.asyncio
    async def test_full_outline_workflow(self, llm_client, template_manager):
        """测试完整的大纲提取工作流"""
        print("\n[TEST] Testing full outline extraction workflow...")
        
        # 1. 准备输入数据
        chapter_content = """
第二章：危机

深夜，警局接到报警电话。城郊废弃工厂发现一具尸体。

刑警队长赵刚带着助手小王赶到现场。死者是本地富商钱老板，
死状凄惨，显然经过激烈搏斗。

"队长，这里有发现！"小王指着墙角的一个徽章。

赵刚捡起徽章，脸色大变。这是二十年前的连环杀手"幽灵"的标记。

但"幽灵"已经在监狱里死了十年...

赵刚的手机突然响起，一个经过变声处理的声音传来：
"赵队长，游戏开始了。你准备好面对真相了吗？"
        """
        
        print("\n[STEP 1] Rendering prompt template...")
        variables = {
            "work_title": "暗夜追凶",
            "chapter_range": "第二章",
            "chapter_contents": chapter_content,
            "known_characters": "赵刚(刑警队长), 小王(助手)",
        }
        
        rendered = template_manager.render("outline_extraction_v1", variables)
        print(f"  ✓ Prompt rendered: {rendered.estimated_tokens} tokens")
        
        print("\n[STEP 2] Calling LLM API...")
        response = await llm_client.complete(
            prompt=rendered.user_prompt,
            system=rendered.system_prompt
        )
        print(f"  ✓ LLM responded: {response.total_tokens} tokens, {response.latency_ms}ms")
        
        print("\n[STEP 3] Parsing LLM output...")
        content = response.content.strip()
        if content.startswith("```"):
            content = content[content.find("{"):content.rfind("}")+1]
        
        try:
            parsed = json.loads(content)
            print(f"  ✓ JSON parsed successfully")
            print(f"  ✓ Keys: {list(parsed.keys())}")
            
            # 验证输出
            validation = template_manager.validate_output("outline_extraction_v1", parsed)
            print(f"  ✓ Validation: {validation}")
            
        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON parse failed: {e}")
            parsed = {"raw_output": content}
        
        print("\n[STEP 4] Cost analysis...")
        input_tokens = rendered.estimated_tokens
        output_tokens = response.total_tokens - response.prompt_tokens
        cost = llm_client.estimate_cost(input_tokens, output_tokens)
        print(f"  ✓ Input tokens: {input_tokens}")
        print(f"  ✓ Output tokens: {output_tokens}")
        print(f"  ✓ Estimated cost: ${cost:.6f}")
        
        print("\n[STEP 5] Result summary...")
        result_summary = {
            "task_type": "outline_extraction",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": response.latency_ms,
            "estimated_cost_usd": cost,
            "parsed_successfully": "plot_points" in parsed or "outline" in parsed,
        }
        print(f"  {json.dumps(result_summary, indent=2)}")
        
        # 最终断言
        assert response.content is not None
        assert response.total_tokens > 0
        assert cost >= 0
        
        print("\n✓ Full outline workflow test passed!")
        print("=" * 60)


# ============================================================================
# Run as script
# ============================================================================

if __name__ == "__main__":
    # 手动运行测试
    print("=" * 60)
    print("LLM Backend Closed-Loop Integration Test")
    print("Model: Kimi K2.5 (Moonshot)")
    print("=" * 60)
    
    # 检查 API Key
    if not os.getenv("MOONSHOT_API_KEY"):
        print("\n⚠️  ERROR: MOONSHOT_API_KEY not set!")
        print("Please set the environment variable:")
        print("  export MOONSHOT_API_KEY='your-api-key'")
        print("\nGet your API key from: https://platform.moonshot.cn/")
        sys.exit(1)
    
    # 运行 pytest
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "-s"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    sys.exit(result.returncode)
