# SailZen Project Guide for AI Agents

> **最后更新**: 2026-11-22 | **当前主线**: SailZen 3.0（云端核心服务 + Android 随身端 + SailTick 常驻代理 + AI 自动化运维闭环）
>
> **必读导航**:
> - [项目路线图与迭代循环](./doc/ROADMAP.md) — 近期短板修复与中长期演进规划
> - [双环境与 AI 自动运维手册](./doc/maintain/DevOps.md) — 本地调试环境 vs 云端生产环境边界、备份/恢复/部署闭环
> - [文档中心](./doc/README.md) — 全仓库文档索引（区分活跃 / 历史 / 废弃）
> - [SailTick 减肥监督教练设计](./doc/design/agent-system/sailtick.md) — 当前 Agent 重点模块
> - [SailZen 3.0 愿景](./doc/SailZen3.0.md) & [PRD](./doc/PRD.md)

---

## 1. 产品全貌与核心原则

### 核心原则

1. **Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.**
2. **人做规划与验收，AI 做本地迭代与自动运维**：本地调试环境由线上数据快照重构，功能验证通过后再自动化部署上线，绝不在生产库上直接试错。

### 实际产品形态（4+1 架构）

SailZen 是面向个人的知识管理与生产力系统，最终产品形态运行在**一台公网 Linux 云服务器**上（PostgreSQL + `sail_server` + `sailtick`），个人通过公网 Web 浏览器或手机端 Android App 与云端交互；个人笔记则通过 VSCode 插件本地维护并经 Git 同步：

| 组件 | 目录 | 角色与状态 | 技术栈 | 数据持久化 |
|---|---|---|---|---|
| **后端与数据服务** | `sail_server/` + `packages/py/sailzen-orm/` | ✅ 活跃核心：REST/WS API、定时任务、静态托管 `site_dist` | Python >=3.13, Litestar, SQLAlchemy 2.0, psycopg3 | 云端 PostgreSQL（本地开发可切换 SQLite） |
| **Web 管理台** | `site/` | ✅ 活跃核心：桌面端深度管理/复盘/配置面板，构建后由 `sail_server` 托管 | React 19, TypeScript, Vite, Tailwind CSS 4, Zustand | 调 `sail_server` API |
| **Android App** | `android/` | ✅ 活跃核心：手机随身哨兵（系统通知提醒、3秒采集、健康/节奏打卡） | Kotlin, Jetpack Compose, Room, Retrofit, OkHttp WS | 调云端 `sail_server` REST + WS |
| **VSCode 笔记插件** | `packages/vscode_plugin/` 及 `packages/*` | ✅ 维护中：基于开源 Dendron 改造，专注层级 Markdown 笔记，通过 Git 同步（与后端结构化数据尚未完全打通，仅有 CLI/部分桥接尝试） | TypeScript, Node.js, pnpm workspace, VSCode API ^1.107 | 本地 Markdown Vault + Git |
| **SailTick 守护进程** | `sailtick/` | 🔄 活跃开发：SailZen 3.0 首个 24/7 Tick 驱动常驻 AI 教练，同机部署于云端 `:9070` | Python, APScheduler, DeepSeek/Moonshot | 独立 SQLite（`data/sailtick/db/sailtick.db`）+ `sail_server` 票据表 |
| **命令行工具** | `packages/py/sailzen-cli/` | ✅ 活跃：供人工与 Agent 调用的独立 CLI（`sailzen`），通过 HTTP API 与服务端交互 | Python, Click (`uv tool`) | 无状态客户端 |

### ⛔ 已停用 / 已归档支线（AI 禁止再开发或误当主线）

以下目录/文件仅作历史参考，**禁止投入新功能开发，也不要将其写入新架构依赖**：

- **飞书（Lark）机器人支线**（`sail_bot/`、`bot.py`、`bot_watcher.py`、`bot.example.yaml`、`sail/feishu_card_kit/`、`doc/design/lark_bot/`）：**已停止使用**，其触达与交互生态位已由 **Android App + Reminder WebSocket 通道** 替代。
- **旧版 Autonomous Agent**（`archive/autonomous_agent/`、`scripts/agent-daemon.service`、`doc/design/agent-system/autonomous-agent.md`、`doc/design/agent-system/shadow-agent-v1-deprecated.md`）：**已归档**，已被 `sailtick/` 取代。
- **旧版 Dendron Webview**（`packages/dendron_plugin_views/`）：已被 `packages/sail_plugin_views/` 替代。

---

## 2. 双环境拓扑与隔离红线（开发必读）

> 详细运维与自动化方案见 [doc/maintain/DevOps.md](./doc/maintain/DevOps.md)。

AI 在执行任何命令、改配置、查数据库或重启服务前，**必须先明确自己处于哪个环境**：

| 维度 | 本地开发调试环境（当前机器） | 公网云端生产环境 |
|---|---|---|
| **主机与系统** | Windows 开发机（默认 Shell：`pwsh`） | 公网 Linux 云服务器（Ubuntu + systemd） |
| **已装工具链** | `uv`、Node.js/`pnpm`、本地 PostgreSQL、Android Studio/JDK 17/`adb`、OpenSSH（`ssh`/`scp`） | PostgreSQL 17、`uv`、Node.js/`pnpm`、systemd |
| **环境配置文件** | `.env.dev`（或 `.env.debug`） | `.env.prod` |
| **启动命令** | `uv run server.py --dev`（或 `--debug`） | `uv run server.py`（默认 `--prod`，由 systemd 托管） |
| **数据库来源** | **本地调试库**（从云端定期备份重构的本地 PG 或本地 SQLite `DB_BACKEND=sqlite`） | **云端生产 PostgreSQL（唯一权威事实源）** |
| **Web 前端调试** | `pnpm run dev:site`（Vite 热重载）或 `pnpm run build-site` | `pnpm run build-site` 产物同步至 `SITE_DIST` 由 `sail_server` 静态托管 |
| **Android 调试** | Android Studio / `gradlew assembleDebug` + `adb` 指向局域网/本地调试服务 | `gradlew assembleRelease` 签名安装包，指向公网云服务地址 |
| **SailTick 运行** | 单元测试 / 轨迹回放 / 短周期沙盒（Layer 1–3） | 常驻 systemd 服务（`sailtick.service`，监听 `127.0.0.1:9070`，支持 Layer 4 灰度开关） |

### 环境变量加载机制（`sail/utils.py`）

- `uv run server.py --dev` → 加载 `.env.dev`，设置 `ENV=dev`
- `uv run server.py --debug` → 加载 `.env.debug`，设置 `ENV=debug`
- `uv run server.py`（无参数） → 加载 `.env.prod`，设置 `ENV=prod`

### 🚨 AI 操作红线（严禁违反）

1. **严禁直接用开发代码连接或修改云端生产数据库**：任何功能开发、Schema 调试、数据写入测试都必须在本地调试库完成；需要真实数据时，必须通过“云端备份 → 本地还原”构建本地调试库。
2. **严禁在未确认前直接 `git push origin`**：除非环境变量 `$ALLOW_PUSH=1`，否则遵循 `.agents/skills/git-push/SKILL.md` / `commit-current-change` / `finalize-today-work` 规则，生成 patch 或由人确认后推送。
3. **严禁泄露或提交敏感信息**：禁止提交 `.env.dev`、`.env.prod`、`.env.debug`、Android `keystore/`、SSH 私钥、API Key 或生产库 dump 文件；日志与文档中引用连接串必须脱敏。
4. **严禁对 `sailtick` 独立数据库执行 `db_sync.py`**：`data/sailtick/db/sailtick.db`（`st_*` 表族）与主库隔离，不参与主库同步。
5. **严禁向 `sail_server/migration/` 新增 Python 迁移脚本**：启动期迁移仅允许**幂等 `.sql` 文件**（见 `sail_server/migration/__init__.py`）；一次性数据回填请写独立脚本放 `scripts/` 手动执行。
6. **生产上线必须满足门禁**：本地单测与冒烟通过 → 部署前对云端生产库执行备份 → 执行部署与静态资源同步 → `/api/v1/health` 与关键路由体检通过 → 失败则立即回滚并报告。

---

## 3. 项目目录结构（真实布局）

```text
SailZen/
├── AGENTS.md                   # 本文档（AI 协作规范与环境约定）
├── README.md                   # 项目总览与各端维护入口
├── server.py                   # sail_server 主入口（Litestar + uvicorn + 静态托管）
├── pyproject.toml              # uv Python workspace 根配置 (sailserver 0.3.0)
├── package.json                # pnpm monorepo 根脚本
├── pnpm-workspace.yaml         # workspaces: packages/* + site
├── .env.template               # 环境变量模板（复制到 .env.dev / .env.prod）
├── sailtick.yaml               # SailTick 配置文件模板
│
├── sail_server/                # Python 后端（Router → Controller → Model → DAO → ORM）
│   ├── router/                 # API 路由（finance/health/history/text/necessity/file_storage/blog/life/reminder/rhythm/tick）
│   ├── controller/             # Litestar Controllers
│   ├── application/dto/        # Pydantic DTOs（含 body_data 自动生成块）
│   ├── model/                  # 领域业务逻辑（含 weather/reminder_scheduler 后台任务）
│   ├── data/                   # DAO 数据访问层
│   ├── migration/              # PostgreSQL 幂等 SQL 迁移脚本
│   ├── config/paths.py         # 统一数据目录配置（基于 SERVER_DATA_DIR）
│   └── utils/                  # logging_config / time_utils / websocket_manager 等
│
├── packages/                   # Monorepo 子包
│   ├── py/
│   │   ├── sailzen-orm/        # 共享 SQLAlchemy 2.0 ORM 定义（主库唯一表结构权威）
│   │   └── sailzen-cli/        # 独立 CLI 工具包（`sailzen` 命令）
│   ├── common-all/             # VSCode 插件基础类型与工具
│   ├── common-server/          # VSCode 插件服务端工具
│   ├── unified/                # Markdown / unified 解析
│   ├── engine-server/          # Sail 笔记引擎（含 Prisma）
│   ├── api_server/             # 插件本地 Express API
│   ├── sail_plugin_views/      # 插件 React Webviews
│   ├── vscode_plugin/          # VSCode 扩展主包（Dendron 衍生，v1.0.4）
│   └── dendron_plugin_views/   # [历史遗留] 旧 Dendron views
│
├── site/                       # Web 前端管理台（React 19 + Vite + Tailwind 4，注意在根目录而非 packages/ 下）
│   └── src/
│       ├── pages/              # main/money/health/tick/rhythm/info/text/necessity/file_storage/blog
│       ├── config/basic.ts     # 前端路由唯一配置源
│       └── lib/                # api/ store/ data/
│
├── android/                    # Android 原生 App（Kotlin + Jetpack Compose）
│   └── app/src/main/java/com/sailzen/app/
│
├── sailtick/                   # SailZen 3.0 AI 减肥监督教练常驻 daemon（独立包）
│   ├── tick_engine.py          # SLEEP→WAKE→SCAN→PLAN→WORK→HANDOFF 状态机
│   ├── daemon.py               # 常驻调度 / 管理 API (:9070) / inbox 轮询
│   ├── canary.py               # Layer 4 灰度开关与自动熔断
│   ├── testing/                # Layer 2 轨迹回放 + Layer 3 实时沙盒
│   └── prompts/                # 人设 / 问卷 / 计划模板
│
├── sail/                       # 通用 Python 基础设施（utils.read_env、llm/、dag/、opencode/）
├── sailzen/dag_client/         # DAG 客户端（与 sailtick 共享）
├── config/body_metrics.toml    # 内置身体指标单一权威配置（代码生成驱动三端）
├── scripts/                    # 构建、同步、代码生成、冒烟测试、systemd unit 与运维脚本
├── tests/                      # pytest 测试（server / sailtick / unit / llm_integration）
├── doc/                        # 项目文档中心（详见 doc/README.md）
├── .agents/skills/             # AI Agent Skills（git/patch/finance/wellness/text-import 等）
├── sail_bot/                   # [⛔ 已停用] 旧飞书机器人，已被 Android App 替代
└── archive/                    # [📦 已归档] 旧 autonomous_agent 等历史代码
```

---

## 4. 核心业务模块与路由对照

| 业务领域 | 后端 Router (`/api/v1/...`) | Web 页面 (`site/src/pages/`) | Android 端 | 关联设计文档 |
|---|---|---|---|---|
| 财务管理 | `/finance` | `/money` | 部分接入 | [life_budget.md](./doc/design/sail_server/manager/life_budget.md) |
| 健康管理 | `/health` | `/health` | ✅ 独立 Tab（体重/饮食/运动/睡眠/用药） | [health.md](./doc/design/sail_server/manager/health.md) · [AndroidHealthPageHandbook.md](./doc/AndroidHealthPageHandbook.md) |
| 节奏管理 (Rhythm) | `/rhythm` | `/rhythm` | ✅ 规划页三合一（今日/事务/事业） | [rhythm.md](./doc/design/sail_server/manager/rhythm.md) · [RhythmUpgradeHandbook.md](./doc/maintain/RhythmUpgradeHandbook.md) |
| 提醒与推送 | `/reminder` (+ WS) | — | ✅ 收件箱 / 系统通知 / 离线反馈队列 | [android_app/README.md](./doc/design/android_app/README.md) |
| SailTick 教练 | `/tick` (+ daemon `:9070`) | `/tick` | ✅ 复用 Reminder WS 推送 | [sailtick.md](./doc/design/agent-system/sailtick.md) · [sailtick-testing.md](./doc/design/agent-system/sailtick-testing.md) |
| 时间与天气 | `/life` | `/main` | — | [weather.md](./doc/design/sail_server/manager/weather.md) |
| 物资管理 | `/necessity` | `/necessity` | — | [necessity.md](./doc/design/sail_server/manager/necessity.md) |
| 文本与阅读 | `/text` | `/text` | ✅ 阅读 Tab | [text.md](./doc/design/sail_server/manager/text.md) |
| 历史时间线 | `/history` | — | — | 已逐步向 NoteItem/Markdown 靠拢 |
| 文件与博客 | `/file_storage`, `/blog` | `/file-storage`, `/blog` | — | — |

---

## 5. 常用开发、构建与测试命令

> **Windows PowerShell (`pwsh`) 注意事项**：
> - 使用分号 `;` 分隔命令，不要使用 `&&`。
> - 中文输出编码异常时先执行 `chcp 65001`。
> - 所有 Python 命令统一通过 `uv run` 执行。

### Python 后端 & SailTick & 数据工具

```powershell
# 安装/同步依赖
uv sync

# 本地开发模式启动后端（加载 .env.dev）
uv run server.py --dev

# 调试模式启动后端（加载 .env.debug）
uv run server.py --debug

# 生产模式启动后端（加载 .env.prod，云端 systemd 使用）
uv run server.py

# 内置身体指标三端代码生成（修改 config/body_metrics.toml 后必跑）
uv run python scripts/generate_body_metrics.py
uv run python scripts/generate_body_metrics.py --check

# 运行测试
uv run pytest
uv run pytest tests/sailtick tests/server -m "not current"
uv run python scripts/sailtick_smoke.py

# SailTick 诊断与单次触发
uv run python -m sailtick doctor
uv run python -m sailtick trigger midday_checkin
uv run python -m sailtick bootstrap

# 数据库同步工具（注意：使用前检查 .env.dev 与 .env.prod 配置，切勿反向覆盖生产库）
uv run scripts/db_sync.py list-tables
uv run scripts/db_sync.py pull
uv run scripts/db_sync.py export-sqlite --env prod
```

### Web 前端 (`site/`) & VSCode 插件 (`packages/*`)

VSCode 插件依赖构建顺序：`common-all` → `common-server` / `unified` → `engine-server` → `api_server` → `sail_plugin_views` → `vscode_plugin`。

```powershell
# Web 前端本地开发与生产构建（输出到 site/dist）
pnpm run dev:site
pnpm run build-site

# VSCode 插件构建与打包
pnpm run build-plugin
pnpm run package-plugin

# Plugin Views
pnpm run views:dev
pnpm run views:build
pnpm run views:copy

# TypeScript 单元测试
pnpm test
pnpm run test:vscode-plugin

# 版本号同步（更新 packages/* 与 site/package.json）
pnpm run version:patch
```

### Android App (`android/`)

```powershell
# 在 android/ 目录下构建 Debug / Release APK
cd android; .\gradlew.bat assembleDebug
cd android; .\gradlew.bat assembleRelease
# 签名凭据通过 ~/.gradle/gradle.properties 或环境变量注入，严禁提交 keystore
```

### SailZen CLI (`packages/py/sailzen-cli`)

```powershell
# 安装为全局工具
uv tool install --from ./packages/py/sailzen-cli sailzen-cli

# 仓库内开发运行
uv run --package sailzen-cli sailzen --help
```

---

## 6. 编码与架构规范

### Python（`sail_server/`、`sail/`、`sailtick/`、`packages/py/`）

- **分层约束**：`Router`（路径与 DI） → `Controller`（HTTP 入参/出参） → `Model`（领域逻辑） → `DAO`（数据访问） → `ORM`（`packages/py/sailzen-orm/`）。
- **文件头规范**（新建 Python 文件包含）：
  ```python
  # -*- coding: utf-8 -*-
  # @file filename.py
  # @brief 简要描述
  # @author sailing-innocent
  # @date YYYY-MM-DD
  # @version 1.0
  # ---------------------------------
  ```
- **ORM 权威位置**：主库表结构统一定义在 `packages/py/sailzen-orm/sailzen_orm/`，不要在 `sail_server/` 下重复定义 ORM 模型。
- **PostgreSQL 编码**：`sail_server/db.py` 会自动设置 `PGCLIENTENCODING=UTF8` 并使用 `postgresql+psycopg://`（psycopg3）。
- **Linting**：遵循 `ruff.toml`（F, W, T, S102, S307），鼓励完整类型提示。

### LLM 默认配置（禁止硬编码模型与 Key）

集中配置位于 `sail/llm/available_providers.py`（当前默认 `moonshot` / `kimi-k2.5`，**注意 `kimi-k2.5` 强制要求 `temperature=1.0`**；第一候补 `deepseek` / `deepseek-chat`）：

```python
from sail.llm.available_providers import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_CONFIG,
)
```

### 日志体系

统一使用 `sail_server/utils/logging_config.py`：
- 通过 `LOG_MODE`（`prod`/`dev`/`debug`）、`LOG_LEVEL`、`API_DEBUG`、`LLM_DEBUG`、`DB_DEBUG` 控制输出。
- 业务模块通过 `get_logger("module_name")` 获取 logger；严禁在日志中打印数据库密码或 API Key（数据库 URI 须经 `_mask_db_uri` 脱敏）。

### TypeScript（`site/` & `packages/*`）

- 严格模式 `strict: true`，ES 模块（`"type": "module"`）。
- `site/` 使用 React 19 + Tailwind CSS 4 + Radix UI + Zustand；页面路由唯一配置源为 `site/src/config/basic.ts`。
- `packages/` 使用 `@saili/*` 路径映射与 Jest ESM 模式。

---

## 7. AI 开发迭代循环（标准工作流）

每次新版本或新功能迭代，AI 必须遵循 [.agents/skills/sailzen-ops/SKILL.md](./.agents/skills/sailzen-ops/SKILL.md)、[doc/maintain/DevOps.md](./doc/maintain/DevOps.md) 与 [doc/ROADMAP.md](./doc/ROADMAP.md) 定义的闭环：

1. **需求对齐（人主导）**：确认本轮目标、影响端（Backend / Site / Android / SailTick / Plugin）及验收标准。
2. **本地数据准备（AI 执行）**：运行 `uv run python scripts/ops/restore_local_db.py`（或 `--pull` 先拉取云端快照再覆盖）重构本机 PostgreSQL 调试库，绝不直连生产库调试。
3. **本地实现与验证（AI 执行）**：编写代码、执行代码生成校验（如 `body_metrics`）、跑通自动化测试与本地健康体检（`scripts/ops/health_check.py --env dev`）。
4. **提交与交付（遵循 Git 规范）**：按 `commit-current-change` / `finalize-today-work` 规范提交（受 `$ALLOW_PUSH` 约束）。
5. **自动化部署与健康检查（AI 执行）**：先 `deploy_cloud.py --dry-run`，再执行 `deploy_cloud.py`（自动完成生产库备份 → 代码同步与构建 `site_dist` → 重启云端 systemd 服务 → 线上健康检查；失败自动回滚）。
6. **最终验收（人主导）**：用户通过 Web/Android 核对核心场景并确认版本升级完成。
