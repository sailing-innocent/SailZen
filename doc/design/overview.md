# SailZen 系统架构

## 概述

SailZen 包含三大核心组件：

| 组件 | 用途 | 技术 |
|------|------|------|
| sail_server | 后端 API + 数据持久化 | Python + Litestar + PostgreSQL |
| site | Web 前端 | React + TypeScript + Vite |
| vscode_plugin | 笔记管理 | TypeScript + VSCode API |

## 模块架构

### Backend (sail_server)

```
router/        # API 路由层
├── finance.py      # 财务：账户、交易、预算
├── project.py      # 项目：项目、任务
├── health.py       # 健康：体重记录
├── text.py         # 文本：作品、版本、章节
├── analysis.py     # 分析：LLM 任务管理
├── necessity.py    # 物资：住所、库存
└── history.py      # 历史：时间线事件

controller/    # 业务逻辑层
model/         # 数据模型
├── finance/        # 财务模型
├── analysis/       # 分析模型
└── necessity/      # 物资模型
data/          # 数据访问层 (DAO)
utils/         # 工具函数
```

### Frontend (packages/site)

```
app/           # 页面路由
├── page.tsx        # 首页仪表盘
├── money/          # 财务管理
├── project/        # 项目管理
├── health/         # 健康管理
├── text/           # 文本管理
├── analysis/       # 作品分析
└── necessity/      # 物资管理

lib/
├── api/            # API 客户端
├── store/          # Zustand 状态管理
└── data/           # 数据处理工具
```

## 数据流向

```
Frontend (React)
       ↓ HTTP/WebSocket
Backend (Litestar)
       ↓ SQLAlchemy
PostgreSQL
```

## 模块详细文档

- [财务管理](./manager/life_budget.md)
- [项目管理](./manager/project.md)
- [健康管理](./manager/health.md)
- [物资管理](./manager/necessity.md)
- [文本管理](./manager/text.md)
- [大纲提取 V2 (Checkpoint-Resume)](./outline-extraction-v2.md) - 新版任务状态持久化
- [大纲提取 V1](./outline-extraction.md) - 原版文档
