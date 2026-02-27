# SailZen 测试用例维护文档

## 概述

本文档记录了 SailZen 项目的测试用例结构、分类和维护指南。测试用例分为 Python 后端测试和 TypeScript 前端测试两部分。

## 测试结构

```
tests/
├── conftest.py                      # 全局 pytest 配置
├── __init__.py
├── test_db_read.py                  # 数据库读取基础测试
├── test_unified_agent_system.py     # Unified Agent 系统测试 ✅ 新增
├── model/
│   └── test_unified_agent.py        # Unified Agent 模型测试
├── server/
│   ├── conftest.py                  # Server 测试配置
│   └── test_basic_connect.py        # 基础连接测试
├── utils/
│   └── llm/
│       └── test_gateway.py          # LLM Gateway 单元测试
└── llm_integration/                 # LLM 集成测试框架
    ├── conftest.py                  # LLM 集成测试配置
    ├── run_validation.py            # 验证运行器 CLI
    ├── test_llm_connection.py       # LLM 连接测试
    ├── test_prompt_templates.py     # Prompt 模板测试
    ├── test_task_flow.py            # 任务流程测试
    └── validators/                  # 验证器模块
        ├── __init__.py
        ├── base.py                  # 验证器基类
        ├── connection.py            # 连接验证器
        ├── prompt.py                # Prompt 验证器
        └── task.py                  # 任务验证器
```

## 测试分类

### 1. 单元测试（Unit Tests）

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/utils/llm/test_gateway.py` | LLM Gateway 核心功能测试 | ✅ 活跃 |
| `tests/model/test_unified_agent.py` | Unified Agent 数据模型测试 | ✅ 活跃 |
| `tests/test_unified_agent_system.py` | Unified Agent 系统测试 | ✅ 新增 |
| `tests/test_db_read.py` | 数据库基础读取测试 | ✅ 活跃 |

### 2. 集成测试（Integration Tests）

| 测试文件 | 描述 | 状态 |
|---------|------|------|
| `tests/llm_integration/test_llm_connection.py` | LLM 提供商连接测试 | ✅ 活跃 |
| `tests/llm_integration/test_prompt_templates.py` | Prompt 模板渲染测试 | ✅ 活跃 |
| `tests/llm_integration/test_task_flow.py` | 任务执行流程测试 | ✅ 活跃 |
| `tests/server/test_basic_connect.py` | 服务器基础连接测试 | ⚠️ 需配置 |

## LLM 网关重构后的变更

### 新架构（推荐）

重构后的 LLM 模块采用 Gateway + Provider 架构：

```python
# 新版 API（推荐）
from sail_server.utils.llm import (
    LLMGateway,
    LLMExecutionConfig,
    TokenBudget,
    create_default_gateway,
)

gateway = create_default_gateway()
config = LLMExecutionConfig(
    provider="openai",
    model="gpt-4o",
    enable_caching=True,
)
result = await gateway.execute("prompt", config)
```

## 运行测试

### 基础命令

```powershell
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/utils/llm/test_gateway.py -v

# 运行特定测试类
uv run pytest tests/utils/llm/test_gateway.py::TestLLMGateway -v

# 跳过异步测试（不调用真实 LLM）
uv run pytest -m "not asyncio"

# 运行服务器测试
uv run pytest -m "server"

# 运行当前标记的测试
uv run pytest -m "current"
```

### LLM 集成测试

```powershell
# 快速检查（不调用真实 LLM）
uv run python tests/llm_integration/run_validation.py quick

# 验证 LLM 连接（需要 API Key）
uv run python tests/llm_integration/run_validation.py connection --real-connection

# 验证 Prompt 模板
uv run python tests/llm_integration/run_validation.py prompt

# 验证任务流程
uv run python tests/llm_integration/run_validation.py task --minimal

# 运行所有验证
uv run python tests/llm_integration/run_validation.py all
```

### 环境变量配置

```powershell
# 设置 API Keys（如需测试真实 LLM 连接）
$env:OPENAI_API_KEY="your-key"
$env:GOOGLE_API_KEY="your-key"
$env:ANTHROPIC_API_KEY="your-key"
$env:MOONSHOT_API_KEY="your-key"

# 设置数据库连接
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"
```

## 测试标记（Markers）

| 标记 | 描述 | 使用场景 |
|------|------|---------|
| `@pytest.mark.asyncio` | 异步测试 | 所有 async 测试函数 |
| `@pytest.mark.server` | 服务器测试 | 需要运行服务器的测试 |
| `@pytest.mark.skipif` | 条件跳过 | API Key 未配置时跳过 |
| `@pytest.mark.current` | 当前开发标记 | 标记正在开发的测试 |

## 维护指南

### 添加新测试

1. 在适当的目录创建测试文件
2. 使用标准文件头格式：

```python
# -*- coding: utf-8 -*-
# @file test_xxx.py
# @brief 测试描述
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```

3. 使用 pytest 最佳实践：
   - 使用 fixtures 管理依赖
   - 使用参数化测试减少重复代码
   - 使用适当的标记分类测试

## 常见问题

### 1. 数据库连接失败

```powershell
# 检查环境变量
$env:POSTGRE_URI

# 设置正确的连接字符串
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"
```

### 2. LLM API 调用失败

```powershell
# 检查 API Key
$env:OPENAI_API_KEY

# 运行不调用真实 LLM 的测试
uv run pytest -m "not asyncio"
```

### 3. 编码问题（Windows）

```powershell
# 修复终端编码
chcp 65001
```

## 测试覆盖率目标

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| `sail_server.utils.llm.gateway` | 90% | 🟡 待评估 |
| `sail_server.utils.llm.providers` | 80% | 🟡 待评估 |
| `sail_server.model.unified_agent` | 85% | 🟡 待评估 |
| `sail_server.data.*` | 75% | 🟡 待评估 |

## 更新记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-02-27 | 1.0 | 初始版本，整理 LLM 网关重构后的测试结构 |
| 2026-02-27 | 1.1 | 标记过时测试文件，创建新的 Unified Agent 系统测试 |
