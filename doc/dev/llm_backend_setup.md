# LLM 后端搭建与验证指南

## 概述

本文档介绍如何搭建和验证基于 Kimi K2.5 (Moonshot) 的 LLM 后端闭环功能。

## 功能特性

- ✅ 多 LLM 提供商支持 (OpenAI, Anthropic, Google, Moonshot/Kimi)
- ✅ Prompt 模板管理系统 (YAML/JSON)
- ✅ 异步 LLM 调用
- ✅ JSON 模式输出
- ✅ Token 和成本估算
- ✅ Prompt 导出功能 (支持多种格式)
- ✅ 输出 Schema 验证

## 快速开始

### 1. 环境配置

在项目根目录创建 `.env` 文件（或修改 `.env.dev`）:

```bash
# Moonshot (Kimi) 配置
MOONSHOT_API_KEY=your-moonshot-api-key
MOONSHOT_MODEL=kimi-k2-5
MOONSHOT_API_BASE=https://api.moonshot.cn/v1
```

获取 API Key: https://platform.moonshot.cn/

### 2. 安装依赖

```bash
# 使用 uv (推荐)
uv sync

# 或使用 pip
pip install -e .
```

### 3. 验证 LLM 后端

```bash
# 设置环境变量 (PowerShell)
$env:MOONSHOT_API_KEY = "your-api-key"

# 运行验证脚本
python scripts/verify_llm_backend.py
```

## 使用方法

### 基础 LLM 调用

```python
import asyncio
from sail_server.utils.llm import (
    LLMClient, LLMConfig, LLMProvider
)

async def main():
    # 创建配置
    config = LLMConfig(
        provider=LLMProvider.MOONSHOT,
        model="kimi-k2-5",
        api_key="your-api-key",
        temperature=0.3,
    )
    
    # 创建客户端
    client = LLMClient(config)
    
    # 调用 LLM
    response = await client.complete(
        prompt="请分析这段文本...",
        system="你是一个文学分析助手。"
    )
    
    print(response.content)
    print(f"Tokens: {response.total_tokens}")

asyncio.run(main())
```

### 使用 Prompt 模板

```python
from sail_server.utils.llm import get_template_manager

# 获取模板管理器
manager = get_template_manager()

# 列出可用模板
templates = manager.list_templates(task_type="outline_extraction")

# 渲染模板
variables = {
    "work_title": "作品名称",
    "chapter_range": "第1-3章",
    "chapter_contents": "章节内容...",
    "known_characters": "角色A, 角色B",
}

rendered = manager.render("outline_extraction_v1", variables)
print(rendered.system_prompt)
print(rendered.user_prompt)
print(f"Estimated tokens: {rendered.estimated_tokens}")
```

### JSON 模式输出

```python
schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["title", "summary"]
}

result = await client.complete_json(
    prompt="分析这段文本...",
    schema=schema
)

# result 是解析后的 Python 字典
print(result["title"])
print(result["characters"])
```

### Prompt 导出

```python
# 生成可导出的 Prompt
exported = client.generate_prompt_only(
    prompt="请分析这段文本...",
    system="你是一个助手。",
    task_id=123,
    chunk_index=0,
    total_chunks=5
)

# 导出为不同格式
openai_format = exported.to_openai_format()
anthropic_format = exported.to_anthropic_format()
markdown = exported.to_markdown()
plain_text = exported.to_plain_text()

# 完整字典
full_dict = exported.to_dict()
```

## 内置 Prompt 模板

### 1. 大纲提取 (outline_extraction_v1)

提取小说的情节大纲，识别情节点、类型、重要程度等。

```python
template = manager.get_template("outline_extraction_v1")
```

输出 Schema:
```json
{
  "plot_points": [
    {
      "title": "情节标题",
      "type": "conflict|revelation|climax|resolution|setup",
      "importance": "critical|major|normal|minor",
      "summary": "简要描述",
      "chapter_number": 1,
      "evidence": "原文引用",
      "characters": ["人物1"]
    }
  ],
  "overall_summary": "整体概述"
}
```

### 2. 人物识别 (character_detection_v1)

从章节内容中识别人物信息。

```python
template = manager.get_template("character_detection_v1")
```

输出 Schema:
```json
{
  "characters": [
    {
      "canonical_name": "标准名称",
      "aliases": ["别名"],
      "role_type": "protagonist|deuteragonist|supporting|minor|mentioned",
      "first_mention": "首次出现",
      "description": "描述",
      "mention_count": 10
    }
  ]
}
```

### 3. 设定提取 (setting_extraction_v1)

提取世界观设定元素（物品、地点、组织等）。

```python
template = manager.get_template("setting_extraction_v1")
```

## 成本估算

```python
# 估算 Token
input_text = "这是一段输入文本..."
tokens = client.estimate_tokens(input_text)

# 估算成本
input_tokens = 10000
output_tokens = 3000
cost = client.estimate_cost(input_tokens, output_tokens)
print(f"Estimated cost: ${cost:.6f} USD")
```

各模型定价参考:

| 模型 | 输入 ($/1K tokens) | 输出 ($/1K tokens) |
|------|-------------------|-------------------|
| gpt-4 | $0.03 | $0.06 |
| claude-3 | $0.015 | $0.075 |
| gemini-2.0 | $0.0001 | $0.0004 |
| kimi-k2.5 | ~$0.00083 | ~$0.00083 |

## 测试

### 运行单元测试

```bash
# 运行所有测试
pytest tests/test_llm_backend_closed_loop.py -v

# 运行特定测试类
pytest tests/test_llm_backend_closed_loop.py::TestLLMConnection -v

# 运行特定测试方法
pytest tests/test_llm_backend_closed_loop.py::TestLLMConnection::test_moonshot_connection -v -s
```

### 手动验证

```bash
python scripts/verify_llm_backend.py
```

## 故障排除

### API 连接失败

1. 检查 API Key 是否正确设置
2. 检查网络连接
3. 查看 Moonshot 平台状态: https://status.moonshot.cn/

### JSON 解析失败

- LLM 可能未按预期格式输出
- 检查 system prompt 中是否明确要求 JSON 格式
- 尝试降低 temperature 参数

### Token 估算不准确

- 当前使用简单字符估算，可能与实际有偏差
- 生产环境建议使用实际的 token 计数

## 文件结构

```
sail_server/
├── utils/llm/
│   ├── __init__.py          # 包导出
│   ├── client.py            # LLM 客户端
│   └── prompts.py           # 提示词模板管理
├── prompts/                 # 提示词模板目录 (可选)
│   └── *.yaml
└── model/analysis/
    └── task_scheduler.py    # 任务调度器

tests/
└── test_llm_backend_closed_loop.py  # 测试文件

scripts/
└── verify_llm_backend.py    # 验证脚本
```

## 下一步

- [ ] 实现任务调度器 (task_scheduler.py)
- [ ] 添加 WebSocket 实时状态推送
- [ ] 实现 Prompt 批量导出
- [ ] 添加更多提示词模板

## 参考

- [Moonshot API 文档](https://platform.moonshot.cn/docs)
- [Kimi K2.5 模型介绍](https://platform.moonshot.cn/)
- [OpenAI API 兼容说明](https://platform.moonshot.cn/docs/api-reference)
