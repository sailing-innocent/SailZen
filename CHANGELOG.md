# Changelog

## Unreleased

### Added

- **Fast-first startup（三阶段启动）**：扩展激活分 `cold → warm → ready` 三个阶段。
  - `warm` 阶段即可打开/创建今日日记；全量索引在后台完成后再解锁 tree view、
    watchers、backlinks 等完整功能。
  - 新配置（`settings.json`）：
    - `sail.startup.mode`：`"fast"`（默认）/ `"full"`（旧版阻塞式启动，用于回退排查）。
    - `sail.startup.autoOpenDailyJournal`：到达 `warm` 后自动打开今日日记（默认 `false`）。
    - `sail.startup.deferMigrations`：vault 迁移延后到 ready 阶段执行（默认 `true`）。
  - `warm` 期间：status bar 显示 "Sail indexing…"；tree view 显示索引占位；
    journal 族命令经 `(sail:pluginActive || sail:engineWarm)` 可见；其余命令
    内部 `waitForWarm()` 排队。
- **服务端 minimal init**：`SailEngine.initMinimal({priorityPaths})` 全量解析
  schemas + priority notes，其余笔记注册为 stub（不进客户端 payload）；
  `/initialize` 支持 `mode: "minimal"|"full"` 与 `priorityPaths`；
  新增 `GET /workspace/initStatus`（`{state, progress}`）。
- **写路径安全**：full init 改为 metadata 合并（保留 warm 期写入），stub 经
  `deleteMetadata` 清理；warm 期 `writeNote` 安全（stub 原地提升/按 schema 创建）。
- **可观测性**：`startup-perf.jsonl` 增加分段耗时（`spawnServer`/`wsInit`/
  `minimalInit`/`fullInit`/`treeViewInit`/`deferredWork`）与启动模式记录。
- **测试设施**：engine-server / api-server 接入 jest（ts-jest ESM）；
  新增 `engineInitMinimal`（9）、`workspaceController`（6）、
  `StartupStateService`（9）测试。插件新增 `tsconfig.typecheck.json` 类型检查入口。
- 兼容降级：minimal init 打到旧版服务端时自动按完整激活处理（等效 full 模式）。

### Changed

- api-server 对同一 workspace 的 initialize 请求按 wsKey 串行化（initQueue），
  minimal/full 不再并发解析；full init 复用 warm 引擎实例（不重建、不丢状态）。
- 非关键启动工作（welcome/whats-new 提示、keybinding 冲突提示、preview、
  uninstall 提示、analyze/tracking）延后到 ready 阶段或 idle 执行。
- 菜单 gating：`sail.gotoToday` / `sail.createDailyJournalNote` /
  `sail.createScratchNote` / `sail.createNote` 在 warm 期即可见。

### Fixed

- unified 的 phantom dependency `hast-util-parse-selector` 显式固定为 `^2.2.5`（CJS）。

### Notes

- 已知且与本改动无关的既有问题（在基线 `3f2a6f8` 上同样存在）：
  `vscode_plugin` 的 `rhythmCore` / `weatherCore` 测试套件在 ESM 下报
  `jest is not defined`；`better-sqlite3` 原生模块在本机无法构建。
- 文档：`packages/vscode_plugin/doc/startup-mode.md`（启动模式配置、时序、
  写路径安全、排查指引）。
