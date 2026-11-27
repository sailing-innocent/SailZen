# SailZen 文档中心

> **版本**: v3.0 | **更新**: 2026-11-22 | **状态**: ✅ 权威导航入口

本目录收录 SailZen 全栈项目的战略规划、系统设计、运维部署、接口参考与历史归档文档。状态约定：
- ✅ 活跃有效 · 🔄 迭代中 · 📦 历史/归档参考 · ⛔ 已停用（请勿继续开发）

---

## 1. 核心入口与战略规划

| 文档 | 说明 | 状态 |
|---|---|---|
| [AGENTS.md](../AGENTS.md) | **AI 协作总规范**（产品全貌、双环境边界、红线约束、常用命令） | ✅ 活跃 |
| [README.md](../README.md) | 项目根目录总览与各端维护速查 | ✅ 活跃 |
| [ROADMAP.md](./ROADMAP.md) | **短期技术债、AI 迭代循环与长期路线图（M0–M4）** | 🔄 迭代中 |
| [SailZen3.0.md](./SailZen3.0.md) | SailZen 3.0 愿景：个人影子助手与“笔记/数据库分离”理念 | ✅ 活跃 |
| [PRD.md](./PRD.md) | 产品需求文档（早期 v2.0 完整功能基线，部分规划已演进） | 📦 参考 |

---

## 2. 环境、运维与测试（DevOps）

| 文档 | 说明 | 状态 |
|---|---|---|
| [maintain/DevOps.md](./maintain/DevOps.md) | **双环境架构与 AI 自动化运维手册**（Win 调试机 vs 云端 Linux、备份/还原/自动部署闭环） | 🔄 迭代中 |
| [ENV.md](./ENV.md) | 环境变量完整参考（`.env.dev` / `.env.debug` / `.env.prod`） | ✅ 活跃 |
| [maintain/DeployPostgres.md](./maintain/DeployPostgres.md) | 云端 Ubuntu PostgreSQL 17 安装、systemd 配置与排障手册 | ✅ 参考 |
| [DATABASE.md](./DATABASE.md) | 核心业务表与 Rhythm/Reminder 字段速记 | ✅ 参考 |
| [TESTING.md](./TESTING.md) | TypeScript / Python / LLM 测试命令指南 | ✅ 活跃 |
| [maintain/RhythmUpgradeHandbook.md](./maintain/RhythmUpgradeHandbook.md) | Rhythm-PEMS 合并升级手册 | ✅ 已完成 |
| [maintain/SailTickAcceptance.md](./maintain/SailTickAcceptance.md) | SailTick 云端部署与 Day-1 验收手册 | ✅ 活跃 |

---

## 3. 系统架构与各端设计

### 总体与客户端

| 文档 | 说明 | 状态 |
|---|---|---|
| [design/overview.md](./design/overview.md) | 系统总体架构与云端/本地部署拓扑 | ✅ 活跃 |
| [design/android_app/README.md](./design/android_app/README.md) | Android App 架构（提醒反馈闭环、随手采集、WebSocket） | ✅ 活跃 |
| [design/android_app/ACCEPTANCE_M1.md](./design/android_app/ACCEPTANCE_M1.md) | Android App M1 构建与验收指南 | ✅ 活跃 |
| [AndroidHealthPageHandbook.md](./AndroidHealthPageHandbook.md) | Android 健康管理页面与后端联动实施手册 | ✅ 活跃 |
| [design/sail_site/Page.md](./design/sail_site/Page.md) | Web 管理台（`site/`）页面设计 | ✅ 参考 |
| [design/sail_server/API.md](./design/sail_server/API.md) | 后端 API 总体设计规范 | ✅ 参考 |
| [design/vscode_plugin/notedoc.md](./design/vscode_plugin/notedoc.md) | VSCode 笔记插件（Dendron 衍生）文档模型 | ✅ 参考 |
| [design/vscode_plugin/note-page-elements.md](./design/vscode_plugin/note-page-elements.md) | VSCode 插件笔记页面元素说明 | ✅ 参考 |
| [design/vscode_plugin/schema.md](./design/vscode_plugin/schema.md) | VSCode 插件笔记 Schema 说明 | ✅ 参考 |

### Agent 系统（SailTick）

| 文档 | 说明 | 状态 |
|---|---|---|
| [design/agent-system/sailtick.md](./design/agent-system/sailtick.md) | SailTick 减肥监督教练设计（Tick 状态机、票据协议、4 层记忆） | 🔄 活跃 |
| [design/agent-system/sailtick-testing.md](./design/agent-system/sailtick-testing.md) | SailTick 四层测试与灰度监控体系（单测/轨迹回放/实时沙盒/熔断） | 🔄 活跃 |
| [design/agent-system/sailtick-migration-notes.md](./design/agent-system/sailtick-migration-notes.md) | 从旧 `autonomous_agent` 迁移至 SailTick 的缺陷复盘 | 📦 参考 |

---

## 4. 业务模块设计与 API 文档

### 业务领域设计（`doc/design/sail_server/manager/`）

| 模块 | 设计文档 | API 参考 | 状态 |
|---|---|---|---|
| 模块总览 | [manager/README.md](./design/sail_server/manager/README.md) | [api/README.md](./api/README.md) | ✅ |
| 财务管理 | [manager/life_budget.md](./design/sail_server/manager/life_budget.md) | [api/finance.md](./api/finance.md) | ✅ 已实现 |
| 健康管理 | [manager/health.md](./design/sail_server/manager/health.md) | [api/health.md](./api/health.md) | ✅ 已实现 |
| 节奏管理 (Rhythm) | [manager/rhythm.md](./design/sail_server/manager/rhythm.md) | — | ✅ M1/M2 已实现 |
| 物资管理 | [manager/necessity.md](./design/sail_server/manager/necessity.md) | [api/necessity.md](./api/necessity.md) | ✅ 已实现 |
| 文本与内容 (Content 2.0) | [manager/content.md](./design/sail_server/manager/content.md) · [manager/text.md](./design/sail_server/manager/text.md) | [api/text.md](./api/text.md) | ✅ Phase 1 已实现 |
| 天气服务 | [manager/weather.md](./design/sail_server/manager/weather.md) | — | ✅ 已实现 |

---

## 5. 历史归档与已停用支线（⛔ 请勿作为现行规范）

| 文档 | 说明 | 状态 |
|---|---|---|
| [design/lark_bot/bot-self-update.md](./design/lark_bot/bot-self-update.md) | 飞书机器人自更新设计（已被 Android App 替代） | ⛔ 已停用 |
| [design/lark_bot/opencode_sse_client.md](./design/lark_bot/opencode_sse_client.md) | 飞书机器人 OpenCode SSE 客户端设计 | ⛔ 已停用 |
| [design/agent-system/autonomous-agent.md](./design/agent-system/autonomous-agent.md) | 旧版 Autonomous Agent 设计（代码已归档至 `archive/`，由 SailTick 取代） | 📦 已归档 |
| [design/agent-system/shadow-agent-v1-deprecated.md](./design/agent-system/shadow-agent-v1-deprecated.md) | 影子助手 v1 早期草案 | 📦 已废弃 |

---

## 6. 文档目录树

```text
doc/
├── README.md                            # 本文档（文档中心入口）
├── ROADMAP.md                           # 短期技术债、AI 迭代循环与长期路线图
├── SailZen3.0.md                        # SailZen 3.0 愿景
├── PRD.md                               # 产品需求文档（v2.0 基线）
├── ENV.md                               # 环境变量配置参考
├── DATABASE.md                          # 核心数据表速记
├── TESTING.md                           # 测试指南
├── AndroidHealthPageHandbook.md         # Android 健康模块实施手册
├── api/                                 # 模块 API 参考
│   ├── README.md
│   ├── finance.md / health.md / necessity.md / text.md
├── design/                              # 架构与模块设计
│   ├── overview.md                      # 系统架构总览
│   ├── agent-system/                    # SailTick（活跃）与旧 Agent（归档）
│   ├── android_app/                     # Android App 设计与验收
│   ├── sail_server/                     # 后端 API 与业务模块设计 (manager/)
│   ├── sail_site/                       # Web 前端页面设计
│   ├── vscode_plugin/                   # VSCode 笔记插件设计
│   └── lark_bot/                        # [⛔ 已停用] 旧飞书机器人设计
└── maintain/                            # 部署与运维手册
    ├── DevOps.md                        # 双环境架构与 AI 自动化运维手册
    ├── DeployPostgres.md                # PostgreSQL & systemd 部署指南
    ├── RhythmUpgradeHandbook.md         # Rhythm 合并升级手册
    └── SailTickAcceptance.md            # SailTick 部署验收手册
```

---

## 7. 文档维护约定

- **代码改，文档跟着改**：新增/下线路由、环境变量、部署步骤或模块状态变化时，同步更新 `AGENTS.md`、`doc/ENV.md`、`doc/maintain/DevOps.md` 及对应模块文档。
- **不留死链**：删除或归档文档时，必须同步更新本目录索引。
- **废弃须明标**：停用功能应在文档顶部标注 `⛔ 已停用` 并说明替代方案，避免误导后续 AI 与开发者。
