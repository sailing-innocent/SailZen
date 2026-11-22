# SailZen 系统架构总览

> **版本**: v3.0 | **更新**: 2026-11-22 | **状态**: ✅ 活跃
> **关联文档**: [AGENTS.md](../../AGENTS.md) · [ROADMAP.md](../ROADMAP.md) · [maintain/DevOps.md](../maintain/DevOps.md)

---

## 1. 产品形态与部署拓扑

SailZen 采用 **“公网云端数据中枢 + 多端按需触达 + 本地 Git 笔记库”** 的混合架构：

```text
                       ┌──────────────────────┐     ┌─────────────────────────┐
                       │   Web 浏览器 (site)   │     │   手机 Android App       │
                       │   桌面管理 / 深度复盘  │     │   随身哨兵 / 提醒 / 采集 │
                       └──────────┬───────────┘     └────────────┬────────────┘
                                  │  HTTP /api/v1                │ HTTP /api/v1 + WebSocket
                                  └──────────────┬───────────────┘
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            公网 Linux 云服务器（生产环境）                               │
│                                                                                        │
│  ┌────────────────────────────────────┐    HTTP /api/v1    ┌────────────────────────┐  │
│  │  sail_server (Litestar + uvicorn)  │ ◄────────────────► │ sailtick daemon (:9070)│  │
│  │  · 托管 site_dist 静态前端          │    (tick/health)   │ · 6h Tick 状态机        │  │
│  │  · REST API + Reminder WebSocket   │                    │ · 4 层记忆 + Handoff    │  │
│  │  · 天气 / 提醒 后台定时循环         │                    │ · 隔离 SQLite (st_*)   │  │
│  └─────────────────┬──────────────────┘                    └────────────────────────┘  │
│                    │ SQLAlchemy 2.0 (packages/py/sailzen-orm)                          │
│                    ▼                                                                   │
│            ┌───────────────┐                                                           │
│            │ PostgreSQL 17 │  ◄── 唯一权威结构化事实源（定期 pg_dump 备份）              │
│            └───────────────┘                                                           │
└────────────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────────────┐
│                            个人电脑 / Windows 开发机                                    │
│  · VSCode 插件 (packages/vscode_plugin/, 基于 Dendron 改造) ──► 本地 Markdown Vault ──► Git
│  · SailZen CLI (packages/py/sailzen-cli/) ──► 通过 HTTP API 桥接云端数据与本地笔记         │
│  · 本地调试环境 (.env.dev + 本地 PG/SQLite) ◄── 从云端快照重构，验证通过后 SSH 自动发布    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心组件职责边界

| 组件 | 路径 | 职责边界 | 技术栈 |
|---|---|---|---|
| **后端服务 (`sail_server`)** | `sail_server/`、`server.py` | 全部结构化数据的读写 API、权限校验、WebSocket 实时推送、后台调度、Web 静态托管 | Python >=3.13, Litestar, uvicorn, SQLAlchemy 2.0, psycopg3 |
| **共享 ORM (`sailzen-orm`)** | `packages/py/sailzen-orm/` | PostgreSQL / SQLite 主库表结构唯一权威声明（被 `sail_server` 与 `sailzen-cli` 共享） | SQLAlchemy 2.0 |
| **Web 管理台 (`site`)** | `site/` | 桌面端深度操作、批量编辑、数据可视化、SailTick 票据收件箱 | React 19, TypeScript, Vite, Tailwind CSS 4, Zustand, Recharts |
| **Android App (`android`)** | `android/` | 随身哨兵：系统级通知触达、反馈闭环（处理/延后/忽略）、3 秒现场采集、离线缓存与补偿同步 | Kotlin, Jetpack Compose, Room, Retrofit, OkHttp WS, WorkManager |
| **VSCode 插件 (`vscode_plugin`)** | `packages/vscode_plugin/` 等 | 个人知识库：基于 Dendron 的层级 Markdown 笔记，本地优先 + Git 同步；与后端结构化数据通过 CLI / Agent 非侵入式渐进打通 | TypeScript, pnpm workspace, VSCode API, Prisma |
| **SailTick Daemon (`sailtick`)** | `sailtick/` | SailZen 3.0 24/7 AI 代理：每 6h Tick 唤醒，读取云端数据、维护独立记忆、通过票据与人异步协作 | Python, APScheduler, DeepSeek/Moonshot, SQLite |
| **CLI (`sailzen-cli`)** | `packages/py/sailzen-cli/` | 独立进程命令行工具，为人工脚本与 AI Agent 提供无状态 HTTP 操作入口 | Python, Click (`uv tool`) |

> **已停用组件**：原飞书机器人（`sail_bot/`、`bot.py`）已停止使用，由 Android App 替代；原 `autonomous_agent` 已归档至 `archive/autonomous_agent/`，由 `sailtick/` 替代。

---

## 3. 后端分层架构（`sail_server`）

```text
HTTP / WebSocket Request
    ↓
Router        (sail_server/router/)           路径定义 + Litestar DI (Provide)
    ↓
Controller    (sail_server/controller/)       参数校验、状态码、DTO 编解码
    ↓
DTO           (sail_server/application/dto/)  Pydantic BaseModel（含 body_metrics 自动生成块）
    ↓
Model         (sail_server/model/)            领域业务逻辑 + 后台调度循环
    ↓
DAO           (sail_server/data/)             数据库查询封装
    ↓
ORM           (packages/py/sailzen-orm/)      SQLAlchemy 2.0 表结构声明
    ↓
PostgreSQL (生产) / SQLite (轻量本地开发)
```

### 当前活跃路由模块（`/api/v1/...`）

| 路由文件 | 前缀 | 职责 |
|---|---|---|
| `finance.py` | `/finance` | 账户、交易、预算、标签 |
| `health.py` | `/health` | 体重、体重计划、身体指标、运动、睡眠/作息、用药、饮食、情绪、仪表盘 |
| `rhythm.py` | `/rhythm` | 统一事务、日时间线、戒律打卡、事业、能量配置、周复盘 |
| `reminder.py` | `/reminder` | 提醒生命周期状态机、设备注册、WebSocket 实时推送 |
| `tick.py` | `/tick` | SailTick 交互票据收件箱（`sail_tick_tickets`）与推送桥接 |
| `life.py` | `/life` | Day / TimeSpan 时间主轴与天气服务 |
| `necessity.py` | `/necessity` | 住所、容器、物品、库存、消耗与行程 |
| `text.py` | `/text` | 作品、版本、章节与文本管理 |
| `history.py` | `/history` | 历史事件时间线 |
| `file_storage.py` | `/file_storage` | 文件上传与存储 |
| `blog.py` | `/blog` | Markdown 博客发布与审阅 |

---

## 4. 前端与跨端数据契约

### Web 前端（`site/src/`）

- 路由唯一配置源：`site/src/config/basic.ts`（`/main`、`/money`、`/health`、`/tick`、`/rhythm`、`/info`、`/text`、`/necessity`、`/file-storage`、`/blog`）。
- 生产构建由 `pnpm run build-site` 输出至 `site/dist`，并由 `sail_server` 挂载在 `SITE_DIST` 目录统一提供单页应用路由回退。

### 跨端单一权威配置（Codegen）

- `config/body_metrics.toml` 是内置身体指标（`BUILTIN_METRICS`）的唯一权威配置。
- 通过 `uv run python scripts/generate_body_metrics.py` 自动同步生成到后端 DTO、Web 前端与 Android DTO，避免多端手工维护产生漂移。

---

## 5. 关联设计文档

- **核心业务设计**：[财务](./sail_server/manager/life_budget.md) · [健康](./sail_server/manager/health.md) · [节奏 (Rhythm)](./sail_server/manager/rhythm.md) · [物资](./sail_server/manager/necessity.md) · [文本](./sail_server/manager/text.md) · [天气](./sail_server/manager/weather.md)
- **客户端设计**：[Android App](./android_app/README.md) · [Android 健康手册](../AndroidHealthPageHandbook.md) · [Web 页面](./sail_site/Page.md) · [VSCode 笔记插件](./vscode_plugin/notedoc.md)
- **Agent 系统**：[SailTick 设计](./agent-system/sailtick.md) · [SailTick 四层测试](./agent-system/sailtick-testing.md)
- **双环境与自动运维**：[DevOps 手册](../maintain/DevOps.md)
