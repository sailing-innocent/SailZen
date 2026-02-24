# -*- coding: utf-8 -*-
# @file demo_llm_outline_extraction.py
# @brief Demo: Novel Outline Extraction with Kimi K2.5
# ---------------------------------

"""
小说大纲提取演示
================

使用 Kimi K2.5 进行完整的小说章节大纲提取演示。

使用方法:
    $env:MOONSHOT_API_KEY = "your-api-key"
    python scripts/demo_llm_outline_extraction.py
"""

import os
import sys
import json
import asyncio
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sail_server.utils.llm import (
    LLMClient,
    LLMConfig,
    LLMProvider,
    get_template_manager,
)


# 示例小说章节
SAMPLE_CHAPTER = """
第七章：真相大白

雨夜，废弃的仓库里。

林峰终于见到了那个神秘的幕后黑手——竟然是他最信任的搭档，
刑警队副队长张明。

"为什么？"林峰的声音有些颤抖，"我们曾经是生死与共的兄弟！"

张明冷笑一声："兄弟？在你眼里，我永远是那个跟在你身后的小跟班。
你拿所有的荣誉，而我只能默默付出？"

他举起手中的枪："现在，这个城市将由我来守护。至于你...
很抱歉，你知道得太多了。"

就在张明扣动扳机的一瞬间，仓库的大门被撞开，特警冲了进来。
原来林峰早就怀疑内部有鬼，这一切都在他的计划之中。

"放下武器！"特警队长喝道。

张明面如死灰，缓缓放下了枪...

天亮了，雨停了。林峰站在窗前，看着这座城市慢慢苏醒。
正义虽然迟到，但从未缺席。
"""


async def main():
    print("=" * 70)
    print("小说大纲提取演示 - 使用 Kimi K2.5")
    print("=" * 70)

    # 检查 API Key
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        print("\n⚠️  请设置 MOONSHOT_API_KEY 环境变量")
        print("    PowerShell: $env:MOONSHOT_API_KEY = 'your-key'")
        return

    # 创建 LLM 客户端
    print("\n[1/5] 初始化 LLM 客户端...")
    config = LLMConfig(
        provider=LLMProvider.MOONSHOT,
        model="kimi-k2-5",
        api_key=api_key,
        temperature=0.3,
        max_tokens=4096,
    )
    client = LLMClient(config)
    print("    ✓ 客户端已初始化")

    # 获取模板管理器
    print("\n[2/5] 加载提示词模板...")
    manager = get_template_manager()
    template = manager.get_template("outline_extraction_v1")
    print(f"    ✓ 模板已加载: {template.name}")

    # 渲染模板
    print("\n[3/5] 渲染 Prompt...")
    variables = {
        "work_title": "暗夜追凶",
        "chapter_range": "第七章",
        "chapter_contents": SAMPLE_CHAPTER,
        "known_characters": "林峰(主角刑警), 张明(反派副队长)",
    }

    rendered = manager.render("outline_extraction_v1", variables)
    print(f"    ✓ System prompt: {len(rendered.system_prompt)} chars")
    print(f"    ✓ User prompt: {len(rendered.user_prompt)} chars")
    print(f"    ✓ Estimated tokens: {rendered.estimated_tokens}")

    # 估算成本
    estimated_output_tokens = int(rendered.estimated_tokens * 0.3)
    cost = client.estimate_cost(rendered.estimated_tokens, estimated_output_tokens)
    print(f"    ✓ Estimated cost: ${cost:.6f}")

    # 调用 LLM
    print("\n[4/5] 调用 Kimi K2.5 API...")
    print("    请稍候...")

    response = await client.complete(
        prompt=rendered.user_prompt, system=rendered.system_prompt
    )

    print(f"    ✓ 响应接收完成")
    print(f"    ✓ Model: {response.model}")
    print(
        f"    ✓ Tokens: {response.total_tokens} ({response.prompt_tokens} in, {response.completion_tokens} out)"
    )
    print(f"    ✓ Latency: {response.latency_ms}ms")

    # 解析结果
    print("\n[5/5] 解析 LLM 输出...")
    content = response.content.strip()

    # 清理 markdown
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        parsed = json.loads(content.strip())
        print("    ✓ JSON 解析成功")

        # 验证
        validation = manager.validate_output("outline_extraction_v1", parsed)
        print(f"    ✓ 验证结果: {'通过' if validation['valid'] else '失败'}")

    except json.JSONDecodeError as e:
        print(f"    ⚠ JSON 解析失败: {e}")
        parsed = {"raw_output": content}

    # 显示结果
    print("\n" + "=" * 70)
    print("提取结果")
    print("=" * 70)

    if "plot_points" in parsed:
        print(f"\n📌 识别到 {len(parsed['plot_points'])} 个情节点:\n")

        for i, point in enumerate(parsed["plot_points"], 1):
            importance_emoji = {
                "critical": "🔴",
                "major": "🟠",
                "normal": "🟡",
                "minor": "⚪",
            }.get(point.get("importance", "normal"), "🟡")

            type_emoji = {
                "conflict": "⚔️",
                "revelation": "💡",
                "climax": "🔥",
                "resolution": "✅",
                "setup": "📖",
            }.get(point.get("type", "scene"), "📖")

            print(f"  {importance_emoji} 情节点 {i}: {point.get('title', 'N/A')}")
            print(f"     类型: {type_emoji} {point.get('type', 'N/A')}")
            print(f"     重要度: {point.get('importance', 'N/A')}")
            print(f"     摘要: {point.get('summary', 'N/A')[:100]}...")

            if point.get("characters"):
                print(f"     涉及人物: {', '.join(point['characters'])}")
            print()

    if "overall_summary" in parsed:
        print("\n📝 整体概述:")
        print(f"   {parsed['overall_summary']}")

    # 原始输出
    print("\n" + "=" * 70)
    print("原始 LLM 输出")
    print("=" * 70)
    print(response.content)

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
