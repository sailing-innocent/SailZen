# -*- coding: utf-8 -*-
# @file validate_kimi.py
# @brief Kimi (Moonshot) API 连接验证脚本
# @author sailing-innocent
# @date 2026-02-09
# @version 1.0
# ---------------------------------
#
# 环境变量配置 (参考 .env.template):
#   MOONSHOT_API_KEY     - Kimi API 密钥 (必需)
#   MOONSHOT_MODEL       - 模型名称 (默认: kimi-k2-5)
#   MOONSHOT_API_BASE    - API 基础 URL (默认: https://api.moonshot.cn/v1)
#
# 使用方法:
#   uv run scripts/validate_kimi.py
#   python scripts/validate_kimi.py
#

import os
import sys
import asyncio
import argparse
from pathlib import Path


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sail.utils import read_env
from sail.llm import LLMClient, LLMConfig, LLMProvider


async def validate_kimi_api(
    api_key: str | None = None,
    model: str | None = None,
    api_base: str | None = None,
    env_mode: str = "dev",
) -> bool:
    """
    验证 Kimi (Moonshot) API 连接

    Args:
        api_key: API 密钥，如未提供则从环境变量读取
        model: 模型名称，如未提供则从环境变量读取或使用默认值
        api_base: API 基础 URL，如未提供则从环境变量读取或使用默认值
        env_mode: 环境模式 (dev/prod/debug)，用于读取对应的环境文件

    Returns:
        bool: 验证是否成功
    """
    # 加载环境变量
    env_file = project_root / f".env.{env_mode}"
    if env_file.exists():
        read_env(env_mode)
    else:
        print(f"警告: 环境文件 {env_file} 不存在，使用系统环境变量")

    # 获取配置 (优先级: 参数 > 环境变量 > 默认值)
    api_key = api_key or os.getenv("MOONSHOT_API_KEY")
    model = model or os.getenv("MOONSHOT_MODEL", "kimi-k2-5")
    api_base = api_base or os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")

    # 检查 API Key
    if not api_key:
        print("❌ 错误: 未找到 MOONSHOT_API_KEY")
        print("   请设置环境变量或在命令行参数中提供")
        return False

    # 显示配置信息
    print(f"\n{'=' * 60}")
    print("Kimi (Moonshot) API 连接验证")
    print(f"{'=' * 60}")
    print(f"API Base: {api_base}")
    print(f"Model:    {model}")
    print(f"API Key:  {'*' * 8}{api_key[-4:] if len(api_key) > 4 else ''}")
    print(f"{'=' * 60}\n")

    # 创建 LLM 配置
    config = LLMConfig(
        provider=LLMProvider.MOONSHOT,
        model=model,
        api_key=api_key,
        api_base=api_base,
        temperature=1,
        max_tokens=1024,
    )

    # 创建客户端
    try:
        client = LLMClient(config)
        print("✓ 客户端初始化成功")
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        return False

    # 发送测试请求
    test_prompt = "你好，请用一句话介绍你自己。"
    test_system = "你是一个 helpful 的 AI 助手，回答简洁明了。"

    print(f"\n发送测试请求...")
    print(f"  Prompt: {test_prompt}")

    try:
        response = await client.complete(test_prompt, system=test_system)

        print(f"\n{'=' * 60}")
        print("✓ API 调用成功!")
        print(f"{'=' * 60}")
        print(f"模型:      {response.model}")
        print(f"提供商:    {response.provider}")
        print(f"延迟:      {response.latency_ms} ms")
        print(f"输入 Token:  {response.prompt_tokens}")
        print(f"输出 Token:  {response.completion_tokens}")
        print(f"总 Token:    {response.total_tokens}")
        print(f"结束原因:  {response.finish_reason}")
        print(f"{'=' * 60}")
        print(f"\n响应内容:\n{response.content}")
        print(f"{'=' * 60}\n")

        return True

    except Exception as e:
        print(f"\n{'=' * 60}")
        print("❌ API 调用失败")
        print(f"{'=' * 60}")
        print(f"错误信息: {e}")
        print(f"{'=' * 60}\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="验证 Kimi (Moonshot) API 连接",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用环境变量中的配置
  uv run scripts/validate_kimi.py
  
  # 指定环境模式
  uv run scripts/validate_kimi.py --env prod
  
  # 直接在命令行提供 API Key
  uv run scripts/validate_kimi.py --api-key "your-api-key"
  
  # 指定模型
  uv run scripts/validate_kimi.py --model "kimi-k2-5"
        """,
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Moonshot API 密钥 (默认: 从环境变量 MOONSHOT_API_KEY 读取)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="模型名称 (默认: 从环境变量 MOONSHOT_MODEL 读取，或 kimi-k2-5)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="API 基础 URL (默认: 从环境变量 MOONSHOT_API_BASE 读取，或 https://api.moonshot.cn/v1)",
    )
    parser.add_argument(
        "--env",
        type=str,
        choices=["dev", "prod", "debug"],
        default="dev",
        help="环境模式 (默认: dev)",
    )

    args = parser.parse_args()

    # 运行验证
    success = asyncio.run(
        validate_kimi_api(
            api_key=args.api_key,
            model=args.model,
            api_base=args.api_base,
            env_mode=args.env,
        )
    )

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
