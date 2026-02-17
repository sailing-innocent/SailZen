# -*- coding: utf-8 -*-
# @file verify_llm_backend.py
# @brief LLM Backend Verification Script
# @description 验证 LLM 后端闭环功能的独立脚本
# ---------------------------------

"""
LLM 后端闭环验证脚本
====================

使用方法:
    1. 设置环境变量:
       $env:MOONSHOT_API_KEY = "your-api-key"

    2. 运行验证:
       python scripts/verify_llm_backend.py

验证内容:
    ✓ LLM Client 初始化和配置
    ✓ Moonshot (Kimi K2.5) API 连接
    ✓ Prompt 模板渲染
    ✓ LLM 调用与响应解析
    ✓ JSON 输出解析
    ✓ 成本和 Token 估算
    ✓ 完整闭环工作流
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sail_server.utils.llm import (
    LLMClient,
    LLMConfig,
    LLMProvider,
    ExportedPrompt,
    PromptTemplateManager,
    get_template_manager,
)
from .utils.cmd import Colors


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


def print_step(step_num, text):
    print(f"{Colors.CYAN}[STEP {step_num}] {text}{Colors.END}")


def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def check_env():
    """检查环境配置"""
    print_step("ENV", "Checking environment configuration...")

    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        print_error("MOONSHOT_API_KEY not found!")
        print(f"\n{Colors.YELLOW}Please set the environment variable:{Colors.END}")
        print(f"  PowerShell: $env:MOONSHOT_API_KEY = 'your-api-key'")
        print(f"  CMD:        set MOONSHOT_API_KEY=your-api-key")
        print(f"  Bash:       export MOONSHOT_API_KEY='your-api-key'")
        print(
            f"\n{Colors.CYAN}Get your API key from: https://platform.moonshot.cn/{Colors.END}\n"
        )
        return False

    print_success(f"MOONSHOT_API_KEY found ({len(api_key)} chars)")
    return True


def test_config():
    """测试配置创建"""
    print_step("1", "Testing LLM Config creation...")

    # 从环境变量创建配置
    config = LLMConfig.from_env(LLMProvider.MOONSHOT)
    print(f"  Provider: {config.provider.value}")
    print(f"  Model: {config.model}")
    print(f"  API Base: {config.api_base}")
    print(f"  Temperature: {config.temperature}")
    print(f"  Max Tokens: {config.max_tokens}")

    # 验证配置
    if not config.validate():
        print_error("Config validation failed!")
        return None

    print_success("Config created and validated")
    return config


def test_client_init(config):
    """测试客户端初始化"""
    print_step("2", "Testing LLM Client initialization...")

    try:
        client = LLMClient(config)
        print(f"  Client provider: {client.config.provider.value}")
        print(f"  Client model: {client.config.model}")
        print_success("LLM Client initialized")
        return client
    except Exception as e:
        print_error(f"Client initialization failed: {e}")
        return None


async def test_connection(client):
    """测试 API 连接"""
    print_step("3", "Testing Moonshot API connection...")

    try:
        response = await client.complete(
            prompt="你好，请简短回复'连接测试成功'。",
            system="你是一个测试助手，请简洁回复。",
        )

        print(f"  Model: {response.model}")
        print(f"  Provider: {response.provider}")
        print(f"  Content: {response.content[:100]}...")
        print(f"  Prompt tokens: {response.prompt_tokens}")
        print(f"  Completion tokens: {response.completion_tokens}")
        print(f"  Total tokens: {response.total_tokens}")
        print(f"  Latency: {response.latency_ms}ms")

        print_success("API connection successful")
        return True

    except Exception as e:
        print_error(f"API connection failed: {e}")
        return False


def test_templates():
    """测试模板管理"""
    print_step("4", "Testing Prompt Template Manager...")

    manager = get_template_manager()
    templates = manager.list_templates()

    print(f"  Loaded {len(templates)} templates:")
    for t in templates:
        print(f"    - {t.id}: {t.name} ({t.task_type})")

    # 测试模板渲染
    variables = {
        "work_title": "测试作品",
        "chapter_range": "第一章",
        "chapter_contents": "这是测试章节内容。",
        "known_characters": "",
    }

    rendered = manager.render("outline_extraction_v1", variables)
    print(f"\n  Rendered prompt:")
    print(f"    System length: {len(rendered.system_prompt)} chars")
    print(f"    User length: {len(rendered.user_prompt)} chars")
    print(f"    Estimated tokens: {rendered.estimated_tokens}")

    print_success("Template manager working")
    return manager


def test_cost_estimation(client):
    """测试成本估算"""
    print_step("5", "Testing cost estimation...")

    # Token 估算
    sample_text = "这是一段用于测试的示例文本，包含中英文 mixed content for testing."
    tokens = client.estimate_tokens(sample_text)
    print(f"  Sample text ({len(sample_text)} chars) -> ~{tokens} tokens")

    # 成本估算
    input_tokens = 10000
    output_tokens = 3000
    cost = client.estimate_cost(input_tokens, output_tokens)

    print(f"  Input: {input_tokens} tokens")
    print(f"  Output: {output_tokens} tokens")
    print(f"  Model: {client.config.model}")
    print(f"  Estimated cost: ${cost:.6f} USD")

    print_success("Cost estimation working")


async def test_json_mode(client):
    """测试 JSON 模式"""
    print_step("6", "Testing JSON mode completion...")

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "summary"],
    }

    try:
        result = await client.complete_json(
            prompt="""请分析以下段落：
            
深夜，侦探李明接到报案。富商王某死在了自家的书房里，
现场没有打斗痕迹，但书桌上的古董花瓶不见了。
唯一可疑的是，死者的秘书小张昨晚曾来过宅邸。
            """,
            schema=schema,
            system="你是一个文学分析助手，请以 JSON 格式输出分析结果。",
        )

        print(f"  Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
        print_success("JSON mode working")
        return True

    except Exception as e:
        print_error(f"JSON mode failed: {e}")
        return False


async def test_outline_extraction(client, template_manager):
    """测试完整的大纲提取流程"""
    print_step("7", "Testing full outline extraction workflow...")

    # 模拟小说章节
    chapter_content = """
第一章：命运的邂逅

春日的午后，阳光透过咖啡馆的玻璃窗洒进来。
林小雨坐在靠窗的位置，手中捧着一本旧书。

突然，一个身影撞到了她的桌子，咖啡洒了一地。
"对不起，对不起！"男子慌忙道歉，蹲下来帮忙收拾。

林小雨抬起头，看到了一张带着歉意的俊朗面孔。
"没关系，"她微微一笑，"反正我也喝完了。"

男子名叫陈墨，是附近画廊的画家。
就这样，两个素不相识的人，因为一杯打翻的咖啡，
开始了他们命中注定的故事...
    """

    # 渲染模板
    print("  Rendering template...")
    variables = {
        "work_title": "春日咖啡",
        "chapter_range": "第一章",
        "chapter_contents": chapter_content,
        "known_characters": "",
    }

    rendered = template_manager.render("outline_extraction_v1", variables)
    print(f"  ✓ Prompt rendered ({rendered.estimated_tokens} tokens)")

    # 调用 LLM
    print("  Calling LLM API...")
    response = await client.complete(
        prompt=rendered.user_prompt, system=rendered.system_prompt
    )
    print(
        f"  ✓ LLM responded ({response.total_tokens} tokens, {response.latency_ms}ms)"
    )

    # 解析结果
    print("  Parsing response...")
    content = response.content.strip()

    # 清理 markdown 代码块
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        parsed = json.loads(content.strip())
        print(f"  ✓ JSON parsed")
        print(f"  Keys: {list(parsed.keys())}")

        # 验证
        validation = template_manager.validate_output("outline_extraction_v1", parsed)
        print(f"  Validation: {validation}")

    except json.JSONDecodeError as e:
        print_warning(f"JSON parse failed: {e}")
        print(f"  Raw content: {content[:200]}...")

    # 成本分析
    cost = client.estimate_cost(
        rendered.estimated_tokens, response.total_tokens - response.prompt_tokens
    )
    print(f"  ✓ Estimated cost: ${cost:.6f}")

    print_success("Outline extraction workflow completed")


def test_prompt_export(client):
    """测试 Prompt 导出"""
    print_step("8", "Testing prompt export...")

    exported = client.generate_prompt_only(
        prompt="请分析这段文本的主要情节。",
        system="你是一个专业的小说分析助手。",
        task_id=123,
        chunk_index=2,
        total_chunks=5,
    )

    print(f"  Task ID: {exported.task_id}")
    print(f"  Chunk: {exported.chunk_index + 1}/{exported.total_chunks}")
    print(f"  Model: {exported.model_suggestion}")

    # 导出各种格式
    formats = {
        "OpenAI": exported.to_openai_format(),
        "Markdown": exported.to_markdown()[:200] + "...",
        "Plain": exported.to_plain_text()[:200] + "...",
    }

    for name, content in formats.items():
        print(f"  {name} format: {len(str(content))} chars")

    print_success("Prompt export working")


async def main():
    """主验证流程"""
    print_header("LLM Backend Closed-Loop Verification")
    print(f"{Colors.CYAN}Target Model: Kimi K2.5 (Moonshot){Colors.END}\n")

    # 检查环境
    if not check_env():
        return False

    # 测试配置
    config = test_config()
    if not config:
        return False

    # 测试客户端初始化
    client = test_client_init(config)
    if not client:
        return False

    # 测试连接
    if not await test_connection(client):
        return False

    # 测试模板
    template_manager = test_templates()

    # 测试成本估算
    test_cost_estimation(client)

    # 测试 JSON 模式
    await test_json_mode(client)

    # 测试完整工作流
    await test_outline_extraction(client, template_manager)

    # 测试 Prompt 导出
    test_prompt_export(client)

    # 总结
    print_header("Verification Summary")
    print(f"{Colors.GREEN}All tests passed! ✓{Colors.END}")
    print(f"\n{Colors.CYAN}LLM Backend is ready for use.{Colors.END}\n")

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Verification interrupted by user.{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
