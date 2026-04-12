# SailZen Project Guide for AI Agents

> 📚 **重要文档**: 
> - [SailZen 3.0 路线图](./doc/sailzen-3.0-roadmap.md) - **当前开发重点**
> - [产品需求文档 (PRD)](./doc/PRD.md) - 完整的产品功能需求
> - [文档中心](./doc/README.md) - 所有文档的导航入口
> - [重构计划](./doc/refact_todo.md) - 代码架构重构计划

## Current Development Focus: SailZen 3.0

SailZen 3.0 是当前主要开发目标，核心愿景是：**"开发一个真正的影子助手，运行在服务器和开发机上，永不休眠。"**

### 核心原则

**Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.**

### 3.0 架构概览 (Phase 0-1)

```
Human
  |
Feishu Bot / Cards
  |
Feishu Gateway
  |
Control Plane <-> Unified Agent Tasks
  |
Edge Runtime / Local Execution Session
  |
Workspace / OpenCode / Repo Operations
```

### 开发路线图

| 阶段 | 时间 | 目标 |
|------|------|------|
| **Phase 0** | Q2 2026 (4周) | Feishu Dev Loop MVP - 飞书开发控制台 |
| **Phase 1** | Q2 2026 (4周) | Development Task Layer - 结构化开发任务 |
| **Phase 2** | Q3 2026 (6周) | Unified Agent Tools - 统一工具层 |
| **Phase 3** | Q3-Q4 2026 (6周) | Note/Data Bridge - 笔记与数据桥接 |
| **Phase 4** | Q4 2026+ | Proactive Shadow - 主动式助手 |

### Phase 0 当前优先级 (最高)

1. **Consolidate Feishu path** - 统一飞书网关实现
2. **Harden control plane** - 强化会话控制平面
3. **Validate edge runtime** - 验证边缘运行时
4. **Build Feishu cockpit cards** - 构建飞书控制卡片

### 3.0 新增关键组件

| 组件 | 路径 | 状态 | 说明 |
|------|------|------|------|
| Feishu Gateway | `sail_server/feishu_gateway/` | 🚧 Phase 0 | 飞书消息网关 |
| Control Plane | `sail_server/control_plane/` | 🚧 Phase 0 | 工作区/会话控制 |
| Edge Runtime | `sail_server/edge_runtime/` | 🚧 Phase 0 | 本地执行运行时 |
| Unified Agent | `sail_server/router/unified_agent.py` | ✅ 基础可用 | 统一Agent路由 |

## Project Overview

SailZen 是一个基于 VSCode 扩展的个人知识管理与生产力工具。它由 TypeScript/JavaScript monorepo（前端/扩展）和 Python 后端（数据管理与 API 服务）组成。

该项目基于 Dendron（分层笔记工具）扩展，增加了个人财务追踪、健康监测、项目管理、文本分析和必需品/库存管理等功能。

### 核心功能模块

| 模块 | 状态 | 文档 |
|------|------|------|
| 财务管理 | ✅ 已实现 | [设计文档](./doc/design/manager/life_budget.md) |
| 项目管理 | ✅ 已实现 | [设计文档](./doc/design/manager/project.md) |
| 健康管理 | 🔶 部分实现 | [设计文档](./doc/design/manager/health.md) |
| 物资管理 | ✅ 已实现 | [设计文档](./doc/design/manager/necessity.md) |
| 文本管理 | ✅ 已实现 | [设计文档](./doc/design/manager/text.md) |
| AI文本分析 | ✅ 已实现 | [系统设计](./doc/design/text-analysis-system.md) |
| 历史/人物档案 | ✅ 已实现 | HistoryEvent + Person 表 |

## Technology Stack

### Frontend / Extension (TypeScript/JavaScript)

| 组件       | 技术                                               |
| ---------- | -------------------------------------------------- |
| 包管理器   | pnpm with workspace configuration                  |
| 构建工具   | TypeScript compiler + esbuild for VSCode extension |
| UI 框架    | React 19 + Tailwind CSS 4 + Radix UI components    |
| 状态管理   | Zustand (site), Redux Toolkit (plugin views)       |
| 图表库     | Recharts                                           |
| 测试框架   | Jest with ts-jest (ESM mode)                       |
| VSCode API | Targeting VSCode ^1.107.0                          |

### Backend (Python)

| 组件       | 技术                                     |
| ---------- | ---------------------------------------- |
| 运行时     | Python >= 3.13                           |
| 包管理器   | uv (with workspace support)              |
| Web 框架   | Litestar (ASGI) with uvicorn             |
| 数据库     | PostgreSQL with SQLAlchemy 2.0 + psycopg |
| 数据序列化 | msgspec, pydantic                        |
| LLM 集成   | google-genai, openai, moonshot           |
| 科学计算   | numpy, scipy, scikit-learn, matplotlib   |
| 测试框架   | pytest                                   |

## Project Structure

```
SailZen/
├── packages/                    # TypeScript monorepo 包
│   ├── common-all/             # 共享类型、工具函数、常量
│   ├── common-server/          # 服务端工具函数
│   ├── unified/                # Markdown/unified 解析工具
│   ├── engine-server/          # Dendron 引擎 (含 Prisma)
│   ├── api_server/             # Express API 服务器
│   ├── vscode_plugin/          # VSCode 扩展 (主插件)
│   ├── dendron_plugin_views/   # React webviews for plugin
│   └── site/                   # React Web 前端 (Vite)
├── sail_server/                # Python 后端
│   ├── router/                 # Litestar API 路由
│   │   ├── analysis.py         # 文本分析路由
│   │   ├── finance.py          # 财务路由
│   │   ├── health.py           # 健康路由
│   │   ├── history.py          # 历史路由
│   │   ├── necessity.py        # 必需品路由
│   │   ├── project.py          # 项目路由
│   │   ├── text.py             # 文本路由
│   │   ├── feishu.py           # 飞书路由 (Phase 0)
│   │   └── unified_agent.py    # 统一Agent路由
│   ├── feishu_gateway/         # 飞书消息网关 🚧 Phase 0
│   ├── control_plane/          # 工作区/会话控制平面 🚧 Phase 0
│   ├── edge_runtime/           # 边缘运行时/本地执行 🚧 Phase 0
│   ├── agent/                  # Agent 相关基础设施
│   ├── controller/             # 业务逻辑控制器
│   ├── model/                  # SQLAlchemy 模型
│   │   ├── analysis/           # 分析相关模型
│   │   ├── finance/            # 财务相关模型
│   │   └── necessity/          # 必需品相关模型
│   ├── data/                   # 数据访问层 (DAO)
│   ├── utils/                  # 工具函数 (LLM, 时间等)
│   └── cli/                    # CLI 命令
├── tests/                      # Python 测试
│   ├── llm_integration/        # LLM 集成测试
│   └── server/                 # 服务器 API 测试
├── scripts/                    # 构建和工具脚本
│   ├── build-with-deps.js      # 依赖拓扑排序构建脚本
│   └── bump-version.js         # 版本号同步脚本
├── doc/                        # 文档
│   ├── sailzen-3.0-roadmap.md  # 3.0 开发路线图
│   ├── design/agent-system/    # Agent系统设计文档
│   └── ...
└── .opencode/skills/           # AI Agent 技能定义
    ├── sailzen-dev-guide/      # 开发环境指南
    └── sailzen-ai-text-import/ # AI 文本导入工具
```

## Package Dependencies (Build Order)

包必须按以下依赖顺序构建：

笔记项目
1. `@saili/common-all` - 基础类型和工具 (无内部依赖)
2. `@saili/common-server` - 依赖 `common-all`
3. `@saili/unified` - 依赖 `common-all`
4. `@saili/engine-server` - 依赖 `common-all`, `common-server`, `unified`
5. `@saili/api-server` - 依赖 `common-all`, `common-server`, `engine-server`, `unified`
6. `@saili/dendron-plugin-views` - 依赖 `common-all`
7. `sail-zen-vscode` - 依赖以上所有

此外前后端项目比较独立
- `sail-site` - Web 前端

## Build Commands

当前项目使用 **pwsh** (Powershell7)为默认Shell，如果Shell和powershell均无法使用的时候，可以尝试使用`pwsh`

### TypeScript Packages

```bash
# 构建指定包及其所有依赖
pnpm run build-with-deps @saili/engine-server

# 构建所有基础包
pnpm run build:common-all
pnpm run build:common-server
pnpm run build:unified
pnpm run build:api-server

# 构建 VSCode 插件
pnpm run build-plugin

# 构建并打包扩展
pnpm run package-plugin

# 构建网站
pnpm run build-site

# 安装插件依赖
pnpm run install-plugin

# 安装网站依赖
pnpm run install-site
```

### Plugin Views Development

```bash
# 开发模式 (watch)
pnpm run views:dev

# 生产构建
pnpm run views:build

# 复制 views 到插件目录
pnpm run views:copy
```

### Python Backend

```bash
# 安装依赖
uv sync

# 运行主服务器
uv run server.py

# 运行开发模式
uv run server.py --dev

# 运行任务调度器
uv run main.py --task <task_name> --args <args>

# 导入文本文件
uv run main.py --import-text <file.txt> --title "Title" --author "Author" --prod

# AI 文本导入 (推荐)
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py \
  <file.txt> --title "Title" --author "Author" --preview

# 数据库同步工具
# 从云端拉取数据到本地（会清空本地数据库！）
uv run scripts/db_sync.py pull

# 将本地特定表推送到云端
uv run scripts/db_sync.py push-table --table works
uv run scripts/db_sync.py push-table --table accounts

# 列出所有可同步的表
uv run scripts/db_sync.py list-tables
```

**数据库同步配置说明：**
1. 确保 `.env.dev` 配置本地数据库，`POSTGRE_URI` 指向本地 PostgreSQL
2. 修改 `.env.prod`，将 `POSTGRE_URI` 改为云端数据库地址
3. 同步时会自动处理表之间的外键依赖关系

## Testing Commands

### TypeScript Tests

```bash
# 运行所有测试
pnpm test

# 运行特定包测试
pnpm run test:common-all
pnpm run test:common-server
pnpm run test:unified

# 运行覆盖率测试
pnpm run test:coverage
```

### Python Tests

```bash
# 运行所有测试
uv run pytest

# 跳过异步测试
uv run pytest -m "not asyncio"

# 运行 LLM 集成测试
uv run tests/llm_integration/run_validation.py connection --real-connection --providers google

# 运行特定标记的测试
uv run pytest -m "server"
uv run pytest -m "current"
```

## Development Environment Setup

### Prerequisites

- Node.js >= 18.0.0
- Python >= 3.13
- pnpm (for TypeScript packages)
- uv (for Python packages)
- PostgreSQL database

### Environment Configuration

基于 `.env.template` 创建环境文件：
- `.env.dev` - 开发环境
- `.env.prod` - 生产环境
- `.env.debug` - 调试环境

### Windows PowerShell 注意事项

```powershell
# ✅ 使用分号 (;) 而不是 &&
cd dir; uv run script.py

# ✅ 设置环境变量
$env:POSTGRE_URI="postgresql://postgres:password@localhost:5432/main"  

# ✅ 修复编码问题
chcp 65001

# ✅ Windows 路径使用原始字符串
$path = "D:\\path\\to\\file.txt"
```

## Code Style Guidelines

### TypeScript

- 使用严格模式 (`strict: true` in tsconfig)
- 目标 ES2024
- 使用 ES 模块 (`"type": "module`)
- 路径映射通过 `@saili/*` 导入
- Jest 测试使用 ESM 支持

### Python

- **文件头格式** (必须包含)：
```python
# -*- coding: utf-8 -*-
# @file filename.py
# @brief 简要描述
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```

- **Windows 编码处理**：
```python
# 设置 PostgreSQL 客户端编码环境变量
os.environ["PGCLIENTENCODING"] = "UTF8"
```

- Ruff linting 启用规则：F, W, T, S102, S307
- 鼓励使用类型提示

## Key Architecture Patterns

### Backend (Python)

- **Router-Controller-Model** 模式
- **依赖注入**：使用 Litestar 的 DI 系统与 `Provide`
- **数据库**：SQLAlchemy 2.0，会话管理通过 `g_db_func` 生成器
- **API 结构**：`/api/v1/<domain>` 端点

数据库访问模式：
```python
from sail_server.db import g_db_func
from sail_server.data.text import Work

db = next(g_db_func())
works = db.query(Work).all()
```

### Frontend Site (React)

- **状态管理**：Zustand stores in `lib/store/`
- **API 层**：TypeScript API clients in `lib/api/`
- **数据层**：数据转换工具 in `lib/data/`
- **组件**：基于特性的组织方式，共享 `ui/` 组件

### VSCode Extension

- **命令模式**：所有命令在 `commands/` 目录
- **工作区管理**：支持多种工作区类型
- **引擎集成**：与 Dendron 引擎通信
- **Webviews**：React-based views 在单独包中

## Domain Modules

应用围绕以下领域模块组织：

| 领域      | 路由         | 功能                     |
| --------- | ------------ | ------------------------ |
| Finance   | `/money`     | 账户管理、交易、预算     |
| Health    | `/health`    | 体重追踪、健康指标       |
| Project   | `/project`   | 任务板、任务管理         |
| Text      | `/text`      | 文本导入、章节管理、阅读 |
| Analysis  | `/analysis`  | 角色档案、大纲、设定提取 |
| Necessity | `/necessity` | 库存、住所、行程追踪     |
| History   | `/history`   | 时间线事件追踪           |

## Version Management

所有包使用同步版本号 (当前 0.2.4)：

```bash
# 升级版本 (patch, minor, major)
pnpm run version:patch
pnpm run version:minor
pnpm run version:major
```

这会更新所有 package.json 文件到相同版本。

## Security Considerations

- 环境文件 (`.env.*`) 已加入 gitignore
- LLM 提供商的 API keys 必须保密
- 数据库凭证存储在环境变量中
- CORS 在开发环境配置为允许所有来源 (`allow_origins=["*"]`)
- 日志文件可能包含敏感数据 - 分享前请检查

## AI Agent Skills

项目包含以下 AI Agent 技能（位于 `.agents/skills/`）：

### sailzen-dev-guide
开发环境指南，包含：
- 项目结构和常用命令
- Windows PowerShell 开发注意事项
- 编码问题处理
- 故障排除

### sailzen-ai-text-import
AI 驱动的智能文本导入工具：
- 解析 txt 小说文件的章节结构
- 支持采样分析学习章节模式
- 智能识别特殊章节（楔子、番外等）
- 过滤广告噪音
- 异常章节检测
- 人机确认界面

## Logging System

### 日志体系概述

项目使用统一的日志配置体系，支持多种模式和详细程度的日志记录。

**日志配置文件**: `sail_server/utils/logging_config.py`

### 日志模式

通过 `LOG_MODE` 环境变量控制：

| 模式 | 说明 | 日志级别 | 输出目标 |
|------|------|----------|----------|
| `prod` | 生产模式 | INFO | 控制台(WARN+) + 文件(JSON) |
| `dev` | 开发模式 | INFO | 控制台(彩色) + 文件 + 错误日志 |
| `debug` | 调试模式 | DEBUG | 所有目标 + 详细调试文件 |

### 环境变量

```bash
# 日志模式 (prod, dev, debug)
LOG_MODE=debug

# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=DEBUG

# 日志目录 (默认: logs)
LOG_DIR=logs

# 启用 LLM 详细调试
LLM_DEBUG=true

# 启用 API 请求/响应日志
API_DEBUG=true

# 启用数据库查询日志
DB_DEBUG=true
```

### 日志文件结构

在 `debug` 模式下，会生成以下日志文件：

```
logs/
├── sailzen.log              # 主日志（人类可读）
├── sailzen.json.log         # 主日志（JSON格式，便于分析）
├── error.log                # 错误日志（ERROR级别以上）
├── llm_debug.log            # LLM API 调用详情
├── api_requests.log         # HTTP 请求/响应详情
└── db_queries.log           # 数据库查询详情
```

### 使用日志工具

```python
from sail_server.utils.logging_config import get_logger, log_api_request, log_api_response

# 获取日志记录器
logger = get_logger("my_module")
logger.info("Something happened")
logger.debug("Debug info: %s", data)

# 记录 API 请求/响应（仅在 API_DEBUG=true 时记录）
log_api_request("POST", "/api/v1/analysis", body={"key": "value"})
log_api_response("/api/v1/analysis", 200, 0.5, body={"result": "ok"})
```

### 调试 LLM 调用

在 `debug` 模式下，LLM 调用会记录：
- 请求参数（模型、温度、max_tokens 等）
- 请求体预览（前500字符）
- HTTP 请求详情
- 响应内容（截断）
- 调用耗时
- 错误详情

查看 LLM 调试日志：
```bash
tail -f logs/llm_debug.log
```

## LLM Configuration Guide

### 调试日志

在开发和调试 LLM 相关功能时，可以启用详细的 API 调用日志：

**环境变量配置**:
```bash
# 启用详细调试日志
LLM_DEBUG=true

# 设置日志级别 (DEBUG, INFO, WARNING, ERROR)
LLM_LOG_LEVEL=DEBUG

# 设置日志文件路径
LLM_LOG_PATH=logs/llm_debug.log
```

**日志内容示例**:
```
2026-02-28 20:38:37 - llm_debug - INFO
[API CALL] _complete_moonshot
Params: {
  "model": "kimi-k2.5",
  "temperature": 1.0,
  "max_tokens": 4000,
  "messages_count": 2,
  "prompt_preview": "请分析以下文本的大纲结构..."
}
================================================================================

2026-02-28 20:38:45 - llm_debug - INFO
[API RESPONSE] {
  "function": "_complete_moonshot",
  "duration_seconds": 8.5,
  "timestamp": "2026-02-28T20:38:45.123456",
  "response": "{\"outline_nodes\": [...], ...}"
}
================================================================================
```

**日志文件位置**: 默认在项目根目录的 `logs/llm_debug.log`

### 默认 LLM 配置

项目使用集中式 LLM 配置管理，默认配置位于：

**文件**: `sail_server/utils/llm/available_providers.py`

```python
# 默认 Provider 和模型
DEFAULT_LLM_PROVIDER = "moonshot"
DEFAULT_LLM_MODEL = "kimi-k2.5"

# 默认 LLM 配置参数
DEFAULT_LLM_CONFIG = {
    "provider": DEFAULT_LLM_PROVIDER,
    "model": DEFAULT_LLM_MODEL,
    "temperature": 0.7,
    "max_tokens": 4000,
}
```

### 使用默认配置

在开发新的 LLM 功能时，**必须**使用上述默认配置，而不是硬编码：

```python
# ✅ 正确做法
from sail.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)

config = LLMConfig(
    provider=LLMProvider(DEFAULT_LLM_PROVIDER),
    model=DEFAULT_LLM_MODEL,
    max_tokens=DEFAULT_LLM_CONFIG["max_tokens"],
)

# ❌ 错误做法 - 硬编码
config = LLMConfig(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    max_tokens=4000,
)
```

### 可用的 Provider

| Provider | 默认模型 | 特点 |
|----------|----------|------|
| moonshot | kimi-k2.5 | 支持长文本，推荐用于小说分析 |
| openai | gpt-4o-mini | 通用能力强 |
| anthropic | claude-3-haiku | 上下文理解好 |
| google | gemini-2.0-flash | 速度快 |

### 修改默认配置

如需修改项目全局默认 LLM，只需修改 `available_providers.py` 中的常量：

```python
DEFAULT_LLM_PROVIDER = "openai"  # 改为其他 provider
DEFAULT_LLM_MODEL = "gpt-4o"     # 改为其他模型
```

## Notes for AI Agents

- 这是个人项目，注释中英文混杂
- 许多注释和 docstrings 是中文
- vscode-plugin 项目从 Dendron 演化而来 - 部分代码保留 "dendron" 命名
- 数据库迁移手动处理 (检查 `sail_server/migration/`)
- **Windows 开发注意**：
  - 使用 `uv run` 运行所有 Python 代码
  - PowerShell 使用分号 `;` 分隔命令，不是 `&&`
  - 处理中文编码问题使用 `chcp 65001`
