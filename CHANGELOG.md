# Changelog

## Unreleased
### Added (Android)
- **阅读器离线优先重构**（`android/`）：Room 为事实源、网络只做后台刷新，开书首帧
  本地快照直接渲染，不再串行等待章节列表/正文/批注三个网络请求。
  - 同步状态可见：阅读页顶栏与首页展示 离线/同步中/已同步(时间)/失败重试 chip，
    并附待同步批注数（`ReaderSyncState` 归约器 + `ConnectivityObserver`）。
  - 离线缓存：目录标出已缓存章节；首页按书展示「已缓存 x/y 章」与一键
    「缓存全书」（带进度条）；阅读中自动预取后 2 章并预排版下一章；
    版本（edition）入缓存，断网也能定位书籍结构。
  - 流畅滚动：滚动进度高频上报不再驱动 UiState 重组；批注预裁剪为
    按段映射（无批注段零 AnnotatedString 开销）；item key 稳定。
  - 排版加速：分页结果进 LRU 缓存（`PageLayoutCache`），字号微调/旋转/重进
    不重排；首帧无 300ms 防抖空白窗口。
  - 修复：章节目录 stub 刷新不再覆盖已缓存正文；离线时跳过网络调用避免
    弱网空等超时；快速切章的后台刷新返回不再覆盖当前章。
  - `SyncWorker` 周期任务追加批注冲刷与作品刷新；新增 `ReaderSyncStateTest`、
    `PageLayoutCacheTest`、`AnnotationClipperTest` 共 16 个 JVM 单测。
- **滚动模式整章原生视图重构（修长距离滑动卡顿）**：章节全文一次性排版进
  单个原生 TextView（NestedScrollView 承载，与翻页模式共用 ReaderTextView），
  滚动 = 纯位移，任何距离/方向零组合成本——「全部加载好，直接上下滑动」。
  - 原生选字/复制/批注菜单、高亮点击、点按分区全部复用，两种模式交互一致；
  - 进度可感知：滚动百分比浮层（停止 0.9s 淡出）+ 底栏进度滑块
    （滚动按行跳 / 翻页按页跳）；
  - 滚动位置按排版引擎行高换算行号上报，持久化/恢复体系不变；
  - 行序排版（layoutLines）进 LRU 缓存，行区间无缝覆盖全文。
  - 新增 `ReaderLayoutLinesTest` 6 个单测。
- **翻页手势防误触**：HorizontalPager 滑动手势仅在点按唤出 UI 后可用
  （`userScrollEnabled = uiVisible`），沉浸式阅读下斜向滑动不再被误判为
  翻页而与手指对抗（实际操作卡顿来源）；点按左右 1/3 翻页始终可用。

### Fixed (Android)
- `RhythmTime.hoursUntil` 返回整小时（原毫秒级 Double 使事务排序比较对
  同一截止时间的多次求值因微秒噪声翻转顺序，测试偶发失败）。

### Added
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
