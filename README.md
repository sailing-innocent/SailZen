# SailZen

> **面向个人的全栈知识管理、生活操作系统与 24/7 AI 影子助手**
>
> **Core Principle**: *Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.*

---

## 1. 产品形态与系统架构

SailZen 的目标部署形态是**运行在个人公网 Linux 云服务器上的长驻数据中枢**，配合多端触点覆盖生活记录、深度管理、知识沉淀与 AI 主动监督：

```text
  [公网 Web 浏览器] ──────────────┐
  (site/ 桌面管理台)               │
                                  ▼ HTTPS / REST / WebSocket
  [手机 Android App] ────► [公网 Linux 云服务器]
  (android/ 随身哨兵)       ├── sail_server (Litestar + 托管 site_dist)
                           ├── PostgreSQL  (结构化个人数据唯一事实源)
                           └── sailtick    (24/7 Tick 驱动 AI 监督教练, :9070)

  [本地开发机 / 电脑]
  ├── VSCode 插件 (packages/vscode_plugin/, 基于 Dendron 改造) ──► 本地 Markdown Vault ◄──► Git 同步
  ├── SailZen CLI (packages/py/sailzen-cli/) ───────────────────► 经 HTTP API 桥接云端数据
  └── 本地调试环境 (Win + 本地 PG/SQLite) ◄── 定期从云端快照重构，调试完自动部署上线
```

### 组件一览

| 组件 | 路径 | 定位 | 状态 |
|---|---|---|---|
| **后端服务** | `sail_server/`、`packages/py/sailzen-orm/` | 财务/健康/节奏/物资/文本/提醒/票据 API 与定时调度 | ✅ 活跃核心 |
| **Web 前端** | `site/` | 桌面管理台（React 19 + Vite + Tailwind CSS 4），构建后由后端静态托管 | ✅ 活跃核心 |
| **Android App** | `android/` | 个人手机终端（系统通知、3秒采集、健康与节奏打卡、离线队列） | ✅ 活跃核心 |
| **VSCode 插件** | `packages/vscode_plugin/` 等 | 基于开源 Dendron 改造的层级 Markdown 笔记工作台（Git 同步，逐步通过 CLI/Agent 桥接后端） | ✅ 维护中 |
| **SailTick Daemon** | `sailtick/` | SailZen 3.0 AI 减肥监督教练（每 6h Tick 唤醒，独立 SQLite + 票据收件箱） | 🔄 活跃迭代 |
| **SailZen CLI** | `packages/py/sailzen-cli/` | 供人工与 AI Agent 使用的命令行工具（`sailzen`） | ✅ 活跃 |
| **飞书机器人** | `sail_bot/`、`bot.py` | 早期交互入口，生态位已完全由 Android App 替代 | ⛔ 已停用 |
| **旧 Autonomous Agent** | `archive/autonomous_agent/` | 早期 Agent 实验，已被 `sailtick/` 取代 | 📦 已归档 |

---

## 2. 文档入口

| 文档 | 说明 |
|---|---|
| [AGENTS.md](./AGENTS.md) | **AI 协作规范**（环境区分、红线约束、目录布局、常用命令） |
| [doc/ROADMAP.md](./doc/ROADMAP.md) | **开发计划与长期路线图**（M0–M4 阶段规划与迭代 SOP） |
| [doc/maintain/DevOps.md](./doc/maintain/DevOps.md) | **双环境与 AI 自动运维手册**（Win 调试环境 vs 云端生产环境、备份/还原/自动部署） |
| [doc/README.md](./doc/README.md) | **完整文档中心导航**（架构设计、模块文档、API、运维与测试手册） |
| [doc/SailZen3.0.md](./doc/SailZen3.0.md) | SailZen 3.0 核心理念与长期愿景 |

---

## 3. 各端开发与维护速查

> 首次配置请复制 `.env.template` 为 `.env.dev`（本地调试）或 `.env.prod`（云端生产），详见 [doc/ENV.md](./doc/ENV.md)。

### 3.1 `sail_server` 与 `site`（后端 + Web 前端）

```powershell
# 1. 安装依赖
uv sync
pnpm install

# 2. 本地调试启动
uv run server.py --dev          # 加载 .env.dev（本地 PG 或 DB_BACKEND=sqlite）
pnpm run dev:site               # Vite 前端开发服务器

# 3. 生产构建（Web 静态资源输出至 site/dist，部署时同步至 SITE_DIST）
pnpm run build-site

# 4. 生产模式运行（云端 systemd 托管，默认加载 .env.prod）
uv run server.py

# 5. 运行后端测试
uv run pytest
```

### 3.2 Android App（`android/`）

详见 [android/README.md](./android/README.md) 与 [AndroidHealthPageHandbook.md](./doc/AndroidHealthPageHandbook.md)。

```powershell
# Debug 包（真机/模拟器调试）
cd android; .\gradlew.bat assembleDebug

# Release 签名包（签名凭据通过 ~/.gradle/gradle.properties 或环境变量注入，严禁提交 keystore）
cd android; .\gradlew.bat assembleRelease
```

### 3.3 VSCode 插件（`packages/vscode_plugin/`）

```powershell
pnpm run version:patch          # 同步 monorepo 版本号
pnpm run build-plugin           # 按依赖拓扑构建插件及基础包
pnpm run package-plugin         # 打包 .vsix 安装包
pnpm test                       # 运行基础包单元测试
```

### 3.4 SailTick Daemon（`sailtick/`）

详见 [doc/design/agent-system/sailtick.md](./doc/design/agent-system/sailtick.md) 与 [doc/maintain/SailTickAcceptance.md](./doc/maintain/SailTickAcceptance.md)。

```powershell
uv run python -m sailtick doctor                 # 依赖与配置体检
uv run python -m sailtick bootstrap              # 幂等初始化计划与首批票据
uv run python -m sailtick trigger midday_checkin # 手动触发单次 Tick
uv run python scripts/sailtick_smoke.py          # 端到端冒烟测试
```

### 3.5 SailZen CLI（`packages/py/sailzen-cli/`）

SailZen CLI 已拆分为独立工具包 `packages/py/sailzen-cli`，与主服务共享 ORM 声明（`packages/py/sailzen-orm`），基于 Click 构建，独立进程运行。

```powershell
# 安装为全局 CLI 工具（uv tool）
uv tool install --from ./packages/py/sailzen-cli sailzen-cli
sailzen --version

# 升级 / 卸载
uv tool upgrade sailzen-cli
uv tool uninstall sailzen-cli

# 仓库内开发运行
uv run --package sailzen-cli sailzen --help
```

> 服务器地址解析顺序：`SAIL_SERVER_URL` 环境变量 → 当前目录 `.env.prod`/`.env.dev`/`.env` 的 `SERVER_HOST`+`SERVER_PORT` → `http://localhost:8000`。

常用示例：

```bash
sailzen finance list-accounts --server http://localhost:1974
sailzen finance pull --account 1 --server http://localhost:1974
sailzen health pull-weight --start 2026-01-01
sailzen notes list --vault ./notes
sailzen rhythm capture "每周运动3次" --json
```
