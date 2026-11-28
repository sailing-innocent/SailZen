# Fast-first startup（三阶段启动）

SailZen 的启动优化：把"打开今天的日记"从"等整个仓库索引完成"中解放出来。
扩展激活分为三个阶段：

| 阶段 | 含义 | 用户可用功能 |
|------|------|-------------|
| `cold` | 引擎服务器进程启动中 | 无（status bar 显示启动进度） |
| `warm` | schemas + 今日日记/模板等 priority notes 已解析，其余笔记注册为 stub | 打开/创建今日日记（`sail.gotoToday`、`sail.createDailyJournalNote`）、新建 scratch/note 命令 |
| `ready` | 全量索引完成 | 全部功能：tree view、watchers、backlinks、preview 等 |

## 配置项（`settings.json`，`sail.startup.*`）

| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sail.startup.mode` | `"fast" \| "full"` | `"fast"` | `fast`：三阶段启动；`full`：旧版阻塞式全量启动（回退/排查用） |
| `sail.startup.autoOpenDailyJournal` | boolean | `false` | `fast` 模式下，到达 `warm` 后自动打开今日日记 |
| `sail.startup.deferMigrations` | boolean | `true` | 把 vault 迁移延后到 `ready` 阶段执行（`warm` 优先路径不被迁移阻塞） |

## fast 模式时序

1. `_activate` → 同步准备（含可能延后的 migrations 暂存）→ `activate()`。
2. `_activateWarm`：
   - 客户端 `StartupStateService` 进入 `cold`，设置 `sail:starting` context。
   - 向 api-server 发 `workspace/initialize`，`mode: "minimal"`，`priorityPaths` =
     今日日记 fname + `templates.<dailyDomain>`（由 journal 配置推导）。
   - 引擎侧 `SailEngine.initMinimal`：全量解析 schemas（fuse 索引就绪）、解析
     priority notes + `root.md`，其余笔记以 stub 形式注册进 metadata store。
   - 响应到达后：设置 `sail:engineWarm` context，`StartupStateService` → `warm`，
     resolve 进度通知（`showActivateProgress` 的 `onWarm` race），`_activate` 返回
     `true` —— 扩展激活完成，日记可开。
3. 后台 `finishActivation`（fire-and-forget，失败时降级为 `not_initialized` 提示）：
   - 执行暂存的 migrations（如有）。
   - 再次 `initialize`，`mode: "full"` —— **由客户端触发全量索引**（见下文设计决策）。
   - `SailEngineClient.init` 用全量结果替换客户端 notes/fuse 索引，并为新出现的
     note id 合成 `create` 变更事件（stub 提升、warm 期新增笔记由此进入 tree/lookup）。
   - `_completeActivation`：`StartupStateService` → `ready`，清除 `sail:starting`，
     打开 watchers、`sail:pluginActive` context、tree view、recent workspaces 等。

warm 期间：status bar 显示 "Sail indexing…"；tree view 显示索引占位条目；
需要 workspace 的命令（`requireActiveWorkspace`）内部 `waitForWarm()` 排队执行；
journal 族命令经 `(sail:pluginActive || sail:engineWarm)` 在命令面板可见。

## 写路径安全（WARM 期）

- `writeNote` 在 `warm` 期即安全：schema store 已就绪，stub 存在时原地提升，
  否则按 schema 正常创建；full init 用 **metadata 合并（bulkWriteMetadata upsert，
  非 dispose 重建）**，warm 期的写入不会因后台全量索引丢失。
- 客户端 file watchers 只在 `ready` 后启动（`activateWatchers` 位于
  `_completeActivation`），避免 watcher 事件与后台索引重复注册。
- 引擎侧无 file watcher；api-server 对同一 workspace 的 initialize 请求按 wsKey
  串行化（initQueue），warm/full 不会并发解析。
- 已知残留风险：warm 期外部（非本插件）删除 priority note 会产生 ghost stub，
  到达 ready 后由 watcher 同步自愈。

## 设计决策记录

- **全量索引由客户端触发**（而非服务端 warm init 后自动续跑）：避免二次全量
  解析，且第二次 init 的响应天然携带全量 note 集合，客户端同步"免费"完成。
- **old-server 降级**：minimal init 打到旧版服务端时响应无 `engineState` 字段，
  客户端按 `ready` 处理并内联走完整激活路径（等效 `startup.mode: "full"`），
  `fetchInitStatus` 失败时同样降级并 warn-once。
- **菜单 gating**：`sail.gotoToday` / `createDailyJournalNote` / `createScratchNote` /
  `createNote` 在 `(sail:pluginActive || sail:engineWarm)` 下可见；tree view 本身
  仍要求 `sail:pluginActive`（ready），避免半填充视图。

## 排查指引

- **启动行为异常** → 设置 `"sail.startup.mode": "full"` 回退到旧版阻塞式启动；
  该配置即时生效（下次激活），无需重启服务端。
- **一直停留在 "Sail indexing…"** → 查看 `Sail/Open Logs`，确认后台
  `finishActivation` 的 full init 是否报错；`workspace/initStatus` 返回
  `{state, progress}` 可用于诊断。
- **需要迁移排查** → 设 `"sail.startup.deferMigrations": false` 恢复启动期
  内联迁移。
- **性能对比** → `startup-perf.jsonl` 记录分段耗时（`spawnServer` / `wsInit` /
  `minimalInit` / `fullInit` / `treeViewInit` / `deferredWork`）及
  `mode: "fast"|"full"`，可用于对比两种模式的 TTFE / T-warm / T-ready。

## 测试

- `packages/engine-server/src/__tests__/engineInitMinimal.test.ts`（9 项）：
  warm 可达、priority 解析、stub 不进客户端 payload、`findNotesMeta`/`querySchema`
  warm 可用、warm 期写笔记与 stub 提升、warm→ready 写入保留且无 stub 重复、
  重复 init 幂等、第二 describe 的 schema 在 full init 后仍生效。
- `packages/api_server/src/__tests__/workspaceController.test.ts`（6 项）：
  mode 透传、engine 复用（`toBe` 同一实例）、legacy 无 mode 全量、并发 init
  串行化、`initStatus` 冷/温/热、失败 init 不毒化 initQueue。
- `packages/vscode_plugin/src/services/__tests__/StartupStateService.test.ts`（9 项）：
  状态机转换、事件广播、幂等 setState、`waitForWarm` 立即/延迟/超时拒绝、
  cancel、reset。
