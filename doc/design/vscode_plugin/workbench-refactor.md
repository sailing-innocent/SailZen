# SailZen VS Code 插件重构蓝图：从 Dendron 衍生插件到「工作与创作工作台」

> **版本**: v1.0 | **日期**: 2026-11-27 | **目标包**: `packages/sailzen-workbench/`  
> **关联基线**: [AGENTS.md](../../../AGENTS.md) · [Rhythm v2](../sail_server/manager/rhythm.md) · [Content 2.0](../sail_server/manager/content.md) · [SailZen 3.0](../../SailZen3.0.md)

---

## 1. 现状诊断与重构共识

### 1.1 推倒重写的动因
旧 VS Code 插件继承自停更的 Dendron，横跨 7 个活跃包（外加已废弃 `dendron_plugin_views`），合计 **557 个 TS/TSX 文件、约 88,010 行代码**，拖带本地 Express (`api_server`)、Prisma (`engine-server`)、1.1 万行 `unified/remark` 渲染与发布管线及 80+ 条旧生态命令。
而真实 `D:/vault/notes`（8,539 篇笔记）结构极简：扁平点层级文件名 + 极简 YAML frontmatter（`id/title/desc/updated/created`）+ `[[wikilink]]` + 每日日记模板（`journal.daily.YYYY.MM.DD.md`）。

### 1.2 三端分工
- **Web (`site/`)**：综合推进、深度可视化、批量管理、复盘与配置
- **Android (`android/`)**：随身哨兵（系统通知、3 秒采集、健康打卡、碎片阅读）
- **VS Code (`sailzen-workbench`)**：纯粹的工作与创作工作台（长篇小说、独立游戏、科研推进、系统工程）

### 1.3 已锁定的架构决策
1. **单扩展洁净重写**：位于 `packages/sailzen-workbench/`，零依赖旧 Dendron 7 包，100% 兼容 `D:/vault` 现有 `.md` 格式；并行验证替代日常后，将旧包归档至 `archive/dendron_legacy/`。
2. **保留的笔记内核**：点层级 TreeView、快速 Lookup/Create、`gotoToday` + 模板、`[[wikilink]]`（补全 / Ctrl+Click 跳转与不存在自动建壳 / 重命名或重构层级自动全库更新引用）、Calendar View。
3. **移除的历史包袱**：Note Preview、Backlinks Tree、Graph View、Publishing/SEO、Hooks、Traits、复杂 Schema 引擎、Task Notes、`docEngine`、Zotero、Note Reference (`![[...]]`)、`<sail-elem>`、Telemetry、Express (`api_server`)、Prisma (`engine-server`)。
4. **双库隐私防火墙 (`PrivacyGuard`)**：私人库与工作库独立配置，按库控制云端同步开关；工作库强制离线隔离，代码层硬拦截任何向个人云端 `sail_server` 的上行请求。
5. **多机器语义与路径分离**：云端只存跨机器唯一语义标识（`slug / archetype / vault_namespace / repo_hints / topic_id / original_work_id`），本机路径仅存 `~/.sailzen/machine.json`；打开 Vault 或任意代码/创作仓库全局双栖激活。
6. **混合双轨云端内容协同**：外部书架/论文/划线通过 `sailzen://` 只读 Virtual FS 打开不污染本地库；原创写作与 `read.*/topic.*/study.*` 采用本地 Markdown + 围栏双向同步。

---

## 2. 目标架构

- **核心层 (`src/core/`)**：
  - `vault/`：纯内存点层级 Trie + HashMap 索引 + `.sailzen-index.json` 增量缓存 + `FileSystemWatcher` + `[[wikilink]]` 与 `WorkspaceEdit` 原子重命名/重构层级引擎 + 模板引擎。
  - `machine/`：`~/.sailzen/machine.json` 本机配置、`ProjectResolver`（双栖工作区解析）、`PrivacyGuard`（双库隐私防火墙）。
  - `server/`：强类型 REST 客户端 + 离线降级、`sailzen://` Virtual FS、围栏同步器。
- **工作台 UI (`src/features/views/`)**：
  - 4 个 Activity Bar 视图：`Today & Rhythm`（含 SailTick 快聊 Webview）、`Projects & Content`、`Vault Tree`、`Calendar`（极简 Webview），加底部 StatusBar。
- **四大深度场景 (`src/features/workflows/`)**：
  - 统一复用 `Venture + Archetype + Vault Namespace + Local Repo` 语义底座，叠加小说（卷章/字数/设定悬浮/章节回写/AI Diff）、游戏（引擎仓↔GDD）、科研（论文库只读浏览/实验日志）、系统工程（跨机器 `repo://<slug>/path#L10` 语义源码互链 + AI Context Pack）。

---

## 3. 后端洁净演进 (`/api/v1/workbench` + `chapter-sync`)

- `GET /api/v1/workbench/bootstrap?date=`：一次往返聚合今日时间线、活跃 Venture（含 `workbench` 语义配置）、活跃 Topic 与待处理 SailTick 票据。
- `PUT /api/v1/workbench/project/{venture_id}`：标准化读写 `RhythmAffair.kind_meta.workbench`。
- `GET /api/v1/workbench/context-pack/{venture_id}`：聚合项目倒排、里程碑、近期时间块、关联 Topic 作品与 `NoteItem` 摘要，生成供本地 IDE Agent 使用的精简 Markdown 上下文包。
- `PUT /api/v1/text/edition/{edition_id}/chapter-sync`：原创作品单章幂等创建/更新 `DocumentNode` 并重算字数统计。
- `GET /api/v1/workbench/release/latest` · `/latest.vsix` · `/download/{filename}`：VS Code 插件 VSIX OTA 分发接口（存储于 `<SERVER_DATA_DIR>/vscode_releases/`，支持 SHA-256 校验与多台无 JS 开发环境的轻量笔记本一键自更新）。

---

## 4. 分阶段路线（全部落地）

- [x] **Phase 0**：脚手架 + 后端 Workbench API + `machine.json` / `PrivacyGuard`。
- [x] **Phase 1 (MVP)**：极速 8,500+ 篇笔记引擎 + Tree/Lookup/Wikilink/原子重命名与批量重命名/删除/Calendar/双库隐私 + Today & Rhythm + SailTick 快聊 + 日记半自动同步。
- [x] **Phase 2**：多机器代码仓自动绑定 + `Projects & Content` 面板 + `sailzen://` Virtual FS + 围栏双向同步。
- [x] **Phase 3**：四大创作与工程场景工作流 + `repo://` 语义源码互链 + AI Context Pack + 章节回写与 Diff 审阅 + Pin 常用/可搜索图书馆 + Dendron 原生快捷键恢复。
- [x] **Phase 4**：云端 VSIX OTA 发布（`scripts/ops/publish_vscode_vsix.py` + 扩展内置 `sailzen.checkForUpdate` 一键自更新）；旧 Dendron 8 包已完整归档至 `archive/dendron_legacy/`，完成 `pnpm-workspace.yaml` 与文档收口。
