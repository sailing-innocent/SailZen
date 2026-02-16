# SailZen 项目结构

## 技术栈

### 后端 (Python)
- **Python**: >= 3.13
- **包管理器**: uv (替代 pip)
- **Web 框架**: Litestar (ASGI) + uvicorn
- **数据库**: PostgreSQL + SQLAlchemy 2.0 + psycopg
- **ORM**: SQLAlchemy 2.0
- **数据序列化**: msgspec, pydantic

### 前端 (TypeScript/JavaScript)
- **包管理器**: pnpm
- **构建工具**: TypeScript + esbuild
- **UI 框架**: React 19 + Tailwind CSS 4
- **状态管理**: Zustand (site), Redux Toolkit (plugin)

## 目录结构

```
SailZen/
├── packages/                    # TypeScript monorepo
│   ├── common-all/             # 共享类型和工具
│   ├── common-server/          # 服务端工具
│   ├── unified/                # Markdown/unified 解析
│   ├── engine-server/          # Dendron 引擎
│   ├── api_server/             # Express API 服务器
│   ├── vscode_plugin/          # VSCode 扩展
│   ├── dendron_plugin_views/   # React webviews
│   └── site/                   # React 前端 (Vite)
├── sail_server/                # Python 后端
│   ├── router/                 # Litestar API 路由
│   ├── controller/             # 业务逻辑控制器
│   ├── model/                  # SQLAlchemy 模型
│   ├── data/                   # 数据访问层 (ORM + DTO)
│   ├── utils/                  # 工具函数
│   └── cli/                    # CLI 命令
├── tests/                      # Python 测试
├── .venv/                      # Python 虚拟环境 (uv)
├── node_modules/               # Node.js 依赖 (pnpm)
└── .agents/skills/             # AI Skills
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python 项目配置，uv 依赖 |
| `pnpm-workspace.yaml` | pnpm 工作区配置 |
| `package.json` | 根 package.json |
| `.env.dev` | 开发环境变量 |
| `.env.prod` | 生产环境变量 |
| `uv.lock` | uv 锁定文件 |
| `pnpm-lock.yaml` | pnpm 锁定文件 |

## 后端架构 (sail_server)

```
sail_server/
├── data/                       # 数据层
│   ├── orm.py                 # ORM Base
│   ├── text.py                # 文本模型 (Work, Edition, DocumentNode)
│   ├── finance.py             # 财务模型 (Account, Transaction, Budget)
│   ├── health.py              # 健康模型 (Weight, Exercise)
│   ├── project.py             # 项目模型 (Project, Mission)
│   └── ...
├── model/                      # 业务逻辑层
│   ├── text.py                # 文本业务逻辑
│   ├── finance/               # 财务业务逻辑
│   ├── health.py              # 健康业务逻辑
│   └── ...
├── router/                     # API 路由层
│   ├── text.py                # 文本 API
│   ├── finance.py             # 财务 API
│   └── ...
├── controller/                 # 控制器 (LLM 集成等)
│   ├── analysis_llm.py        # AI 分析
│   └── ...
└── utils/                      # 工具
    ├── db.py                  # 数据库连接
    ├── llm/                   # LLM 客户端
    └── env.py                 # 环境变量读取
```

## 数据库模型关系

### 文本系统
```
Work (作品)
  └── Edition (版本)
        └── DocumentNode (文档节点/章节)
```

### 财务系统
```
Account (账户) <-->> Transaction (交易) <<--> Account
Budget (预算) <-->> BudgetItem (预算项)
Transaction --> Budget (optional)
```

### 项目系统
```
Project (项目) <-->> Mission (任务/使命)
Mission (树形结构，parent_id 自关联)
```

## 环境变量

### 必需变量
```bash
POSTGRE_URI=postgresql://user:pass@localhost:5432/main
SERVER_PORT=4399
SERVER_HOST=localhost
```

### LLM 配置（至少一个）
```bash
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
MOONSHOT_API_KEY=...
```

## 编码规范

### Python
- 文件头模板：
```python
# -*- coding: utf-8 -*-
# @file filename.py
# @brief Brief description
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```
- 使用 UTF-8 编码
- 类型提示鼓励使用
- Ruff linting (F, W, T, S102, S307)

### TypeScript
- Strict mode
- ES2024 target
- ES modules
- Path mapping: `@saili/*`
