# 总体判断

当前 VSCode 插件的主链路大致是：

```text
extension.ts
  -> _extension.ts
    -> DendronExtension singleton
    -> WorkspaceActivator.init()
       -> WorkspaceService / migrations / engine server
    -> WorkspaceActivator.activate()
       -> reloadWorkspace()
       -> watchers / tree view / webviews / providers
```

优点：

- 已经把笔记解析、索引、持久化等重活放在 `@saili/api-server` / `@saili/engine-server` 子进程中，而不是全部塞进 VSCode Extension Host。
- `WorkspaceActivator.init()` / `activate()` 两阶段设计是合理的，便于区分“工作区准备”和“引擎已可用后的 UI/Watcher 初始化”。
- 命令层基本遵循 `BaseCommand` 模式，维护成本可控。
- 已经建立本地启动性能日志 `StartupProfiler`，这是后续性能治理的基础。
- 从文档看，`NoteParserV2` 已经把原来的串行解析改成并发解析，这是很关键的一步。

主要风险：

- `_extension.ts` 和 `workspace.ts` 仍然是 God Object / God Module 倾向，启动逻辑、命令注册、欢迎页、状态、视图、语言服务等职责混在一起。
- `DendronExtension` singleton + `ExtensionProvider` + 旧的全局函数并存，长期会让测试、热重载、工作区切换、依赖注入变复杂。
- 启动时默认全量初始化倾向仍然比较明显，`reloadWorkspace()` 仍是最重路径。
- 性能监控目前只覆盖 `reloadWorkspace` 粗粒度耗时，无法定位“Engine 启动 / cache parse / tree view / watchers / providers / webview”各自消耗。
- Dendron 遗留命名、telemetry stub、web extension 残留、废弃服务等会增加认知负担。

---

# 1. 架构设计建议

## 1.1 拆分 `_extension.ts` 的激活编排职责

当前 `_extension.ts` 约 700+ 行，包含：

- 插件入口初始化
- Zotero 激活
- workspace trust 处理
- command 注册
- language feature 注册
- workspace 判断
- welcome / what's new
- recent workspace
- activator init / activate
- 特殊命令注册

建议把它改造成一个更薄的 orchestration 层：

```text
src/bootstrap/
  activateExtension.ts
  registerCoreCommands.ts
  registerWorkspaceCommands.ts
  registerLanguageFeatures.ts
  registerWelcomeFlows.ts
  registerExternalFeatures.ts
```

目标不是一次性大重构，而是逐步把明显独立的部分抽出去：

| 当前位置 | 建议迁移到 |
|---|---|
| `_setupCommands()` | `services/CommandRegistryService.ts` |
| `_setupLanguageFeatures()` | `features/registerLanguageFeatures.ts` |
| welcome / what's new | `startup/WelcomeFlow.ts` |
| Zotero 激活 | `integrations/zotero/registerZotero.ts` |
| recent workspace view | `views/recentWorkspaces/registerRecentWorkspaces.ts` |

这样做的收益：

- 降低启动主流程复杂度。
- 单元测试更容易。
- 未来区分 “无工作区激活” 和 “笔记工作区激活” 更清楚。
- 更容易做懒加载。

---

## 1.2 明确三类生命周期：Global / Workspace / Note

现在很多逻辑都集中在 activation 阶段，但实际上可以分为三类：

### Global lifecycle

不依赖 Dendron/SailZen workspace：

- recent workspace view
- welcome page
- setup workspace command
- open logs
- basic help
- Zotero 命令如果不依赖 workspace，也属于此类

### Workspace lifecycle

依赖 `dendron.yml` / vault / engine：

- engine process
- workspace migration
- tree view
- backlinks
- file watchers
- note lookup
- schema sync

### Note lifecycle

只在用户打开或编辑笔记时才需要：

- decorations
- hover / definition / reference
- frontmatter folding
- preview auto show
- duplicate note 检查

建议建立显式生命周期接口：

```ts
interface GlobalContribution {
  activate(context: vscode.ExtensionContext): Promise<void> | void;
}

interface WorkspaceContribution {
  activateWorkspace(ctx: WorkspaceActivationContext): Promise<void> | void;
  deactivateWorkspace?(): Promise<void> | void;
}

interface NoteContribution {
  onOpenNote?(ctx: NoteContext): Promise<void> | void;
  onSaveNote?(ctx: NoteContext): Promise<void> | void;
}
```

不一定马上实现接口，但建议文档和代码组织先按这个思路迁移。

---

## 1.3 收敛 `DendronExtension` singleton 和全局访问模式

`workspace.ts` 中同时存在：

- `DendronExtension.instanceV2()`
- `ExtensionProvider.getExtension()`
- `getExtension()`
- `getEngine()`
- `getDWorkspace()`
- 构造器里直接设置 `_DendronWorkspace = this`

这些全局入口会让依赖关系变隐式。比如 `FileWatcher` 里通过 `ExtensionProvider.getDWorkspace()` 取 workspace，`WindowWatcher` 里也有类似用法。

建议路线：

### 短期

保留 singleton，但禁止新增直接全局访问。

新增代码尽量通过构造函数传入：

```ts
new SomeService({
  extension,
  engine,
  workspaceService,
})
```

并在 `AGENTS.md` 或插件架构文档中明确：

> 新代码不要使用 `getExtension()` / `getEngine()` / `getDWorkspace()`，除非是兼容旧代码。

### 中期

引入 `WorkspaceActivationContext`：

```ts
type WorkspaceActivationContext = {
  extension: IDendronExtension;
  engine: IEngineAPIService;
  workspace: DWorkspaceV2;
  workspaceService: WorkspaceService;
  context: vscode.ExtensionContext;
};
```

大部分服务只接收这个 context，不直接访问 singleton。

### 长期

将 `DendronExtension` 降级为 VSCode adapter，而不是业务服务容器。

---

## 1.4 把命令注册从“实例化所有命令”改成“声明式 + 懒实例化”

当前 `ALL_COMMANDS` 是静态数组，`_setupCommands()` 启动时会遍历并实例化匹配的 command：

```ts
const cmd = new Cmd(ext);
vscode.commands.registerCommand(cmd.key, async (args) => {
  await cmd.run(args);
});
```

这比直接执行重逻辑要好，但仍有几个问题：

- 命令元信息散落在 command class / `package.json` / 特殊注册逻辑中。
- `requireActiveWorkspace` 依赖 class 静态字段，缺少集中可视化。
- 特殊命令在 `_setupCommands()` 里手写注册，长期会越来越乱。
- 部分命令启动时就构造，无法完全懒加载。

建议改为命令 manifest：

```ts
type CommandContribution = {
  id: string;
  requireActiveWorkspace: boolean;
  factory: (ctx: CommandContext) => IBaseCommand<any, any, any, any>;
};
```

注册时只注册 handler，真正执行时才动态 import 或创建命令：

```ts
vscode.commands.registerCommand(id, async (args) => {
  const command = await contribution.factory(ctx);
  return command.run(args);
});
```

收益：

- command palette 贡献、命令实现、注册逻辑可以统一生成或校验。
- 可减少启动时加载和实例化成本。
- 更容易拆出 SailZen 专属命令和 Dendron 遗留命令。

---

## 1.5 Engine API 边界需要更“产品化”

`EngineAPIService` 现在基本是 `DendronEngineClient` 的薄代理。这个设计简单，但插件层仍然知道很多 engine 细节。

建议逐步区分三类 API：

```text
EngineRawClient
  低级 HTTP API，尽量薄。

NoteRepository
  findNote / writeNote / renameNote / getBacklinks 等笔记语义 API。

WorkspaceIndexService
  reload / refresh / getStats / watchIndexEvents 等索引生命周期 API。
```

特别是以下逻辑建议不要留在插件层：

- `onWillSaveNote()` 中自己 `findNotes()` 再判断 frontmatter。
- `FileWatcher.onDidCreate()` 中读取文件、刷新 links/anchors、`writeNote(metaOnly)`。
- rename 流程里插件层拼 rename opts。

插件层最好表达用户意图：

```ts
noteService.updateNoteOnSave(uri)
noteService.handleFileCreated(uri)
noteService.handleFileRenamed(oldUri, newUri)
```

具体如何更新索引、如何处理 frontmatter、是否 metaOnly，应由 engine 或 domain service 决定。

---

## 1.6 将 Dendron 遗留模块标记为 Legacy Boundary

项目已经从 Dendron fork 演化而来，保留 `dendron.*` 命名是现实选择。但建议架构上显式划边界：

```text
src/legacy-dendron/
  commands/
  workspace/
  lookup/
  preview/

src/sailzen/
  commands/
  views/
  integrations/
```

不要求马上移动所有文件，但建议：

1. 新增 SailZen 功能不要继续放进 Dendron 命名空间。
2. 文档中标注哪些是 legacy，不再主动扩展。
3. 新功能命令 ID 使用 `sailzen.*`，旧命令继续兼容 `dendron.*`。
4. `package.json` 中用户可见标题逐步从 Dendron 改成 SailZen。

---

## 1.7 Webview 与插件通信建议统一消息协议

文档中提到 webviews 位于 `packages/dendron_plugin_views/`，通过 `postMessage` 通信。建议建立统一协议：

```ts
type WebviewRequest<T = unknown> = {
  id: string;
  type: string;
  payload: T;
};

type WebviewResponse<T = unknown> = {
  id: string;
  ok: boolean;
  payload?: T;
  error?: {
    message: string;
    code?: string;
  };
};
```

并提供：

```ts
WebviewRpcHost
WebviewRpcClient
```

收益：

- Finance / Project / Text / Necessity 等面板可以复用。
- 错误处理统一。
- 方便加 tracing。
- 后续可以把部分面板从 VSCode webview 迁移到 site 复用同一协议。

---

# 2. 性能优化建议

## 2.1 扩展 `StartupProfiler`，从单指标改成阶段化 profiling

当前 `StartupProfiler` 只记录：

```ts
durationMs: {
  reloadWorkspace: number;
}
```

这不足以定位瓶颈。建议扩展为：

```ts
durationMs: {
  totalActivate: number;
  extensionBootstrap: number;
  commandRegistration: number;
  languageFeatureRegistration: number;
  workspaceDetection: number;
  workspaceInit: number;
  migrations: number;
  wsServiceInitialize: number;
  engineProcessStart: number;
  engineClientCreate: number;
  reloadWorkspace: number;
  treeViewInit: number;
  watcherInit: number;
  postReloadWorkspace: number;
}
```

以及：

```ts
engineStats: {
  noteCount: number;
  vaultCount: number;
  cacheHit: boolean;
  cacheSizeBytes?: number;
  cacheParseMs?: number;
  parsedFiles?: number;
  skippedFiles?: number;
}
```

最重要的是把 `WorkspaceActivator.init()` 和 `activate()` 内部分段打点，而不是只知道 `reloadWorkspace` 慢。

---

## 2.2 `StartupProfiler.write()` 避免同步读写阻塞 Extension Host

当前实现使用：

```ts
fs.appendFileSync()
fs.readFileSync()
fs.writeFileSync()
```

虽然日志文件很小，但这段运行在 Extension Host，建议改成异步非阻塞，并且 trim 可以降低频率：

- append 用 `fs.promises.appendFile`
- trim 不必每次写都执行
- 或者每 10 次 / 文件超过阈值再 trim
- profiling 写失败仍然吞掉即可

这是小优化，但符合 VSCode 插件最佳实践：Extension Host 尽量避免 sync IO。

---

## 2.3 `reloadWorkspace()` 从全量重载走向增量索引

文档已经指出 `reloadWorkspace()` 是最慢步骤。当前启动时仍然依赖全量 engine init / note parsing。

建议分三阶段优化：

### 阶段一：更可靠的 cache

针对 `.dendron.cache.json`：

- 记录每个 note 的 `mtimeMs` / `size` / hash。
- 启动时只解析变化文件。
- 未变化文件直接复用缓存 metadata。
- 缓存 parse 本身可以考虑拆分为多文件或 SQLite，而不是一个大 JSON。

文档提到 “Cache cold start 7.8MB JSON parse 未优化”，这是很值得优先做的点。

### 阶段二：metadata first，body lazy

启动阶段只需要：

- id
- fname
- vault
- title
- parent / children
- links metadata
- frontmatter basic fields

正文、blocks、anchors、render 信息可以打开笔记或 preview 时再补充。

### 阶段三：background hydration

启动后先让插件进入可用状态，再后台补齐：

```text
1. load cached metadata
2. plugin active
3. tree/backlinks basic available
4. background parse changed notes
5. emit index updated event
```

用户体验会明显好于“等全量 reload 完成后才 active”。

---

## 2.4 Engine server 启动可以做复用和健康检查

`verifyOrStartServerProcess()` 目前逻辑是如果 `ext.port` 存在就复用，否则启动 server。建议增强为：

- 读取 `.dendron.port`
- 对端口做 health check
- 如果进程存在且 workspace hash 匹配，则复用
- 如果不匹配或无响应，再重启
- 记录：
  - server spawn time
  - health check time
  - first API latency
  - reload index time

这样可以减少窗口 reload 或插件重激活时的成本。

---

## 2.5 Watcher 事件应做队列化、合并和背压

`FileWatcher.onDidCreate()` / `onDidDelete()` 现在直接调用 engine API。对于批量文件操作，例如 git checkout、复制大量 md 文件、批量 rename，可能造成大量并发请求。

建议增加事件队列：

```ts
FileEventQueue
  enqueue(create/delete/rename/change)
  debounce 200-500ms
  merge same file events
  bulk sync to engine
```

例如：

```text
create A
delete A
=> noop

delete A
create A
=> change / rename candidate

create 100 files
=> engine.bulkWriteNotes(metaOnly)
```

这对大 vault 和 git 操作很有价值。

---

## 2.6 `WorkspaceWatcher.onWillSaveNote()` 避免保存路径上的远程/HTTP 查询

当前保存时：

```ts
await engine.findNotes({ fname, vault })
```

然后判断是否更新 `updated` frontmatter。

问题：

- `onWillSaveTextDocument` 是保存关键路径。
- 即使 `event.waitUntil()` 支持异步，也会影响保存体验。
- 每次保存都通过 engine 查 note，成本不低。

建议：

1. 在插件侧维护 `path -> noteMeta` 的轻量缓存。
2. 或让 engine 提供 `getNoteMetaByPath()` 快速 API。
3. 或把 frontmatter updated 的更新逻辑改成本地纯文本判断，不依赖 engine hydration。
4. 如果需要判断内容是否变化，可以使用 document dirty/version 或缓存上次保存 hash。

---

## 2.7 `WindowWatcher` 的 decorations 和 visible range 事件需要更细粒度降噪

`WindowWatcher.onDidChangeTextEditorVisibleRanges` 会在滚动时触发，并调用：

```ts
getNoteFromDocument()
triggerUpdateDecorations()
```

虽然 decorations 已经 debounced，但仍建议：

- 对非 markdown 文件更早 return。
- 对超大文件禁用或降级 decorations。
- 对同一 editor 的 visible range 变化做 throttle，而不只是 decoration 层 debounce。
- 为 `enablePerfMode` 增加更细配置：
  - disableDecorations
  - disableBacklinksAutoRefresh
  - disablePreviewAutoSync
  - disableDuplicateNoteCheck

---

## 2.8 减少启动时无条件注册/加载的功能

当前 activation event 是 `onStartupFinished`，已经比 `*` 好。但进入 `_activate()` 后仍会做不少事。

建议：

### 可懒加载的功能

| 功能 | 建议 |
|---|---|
| Zotero | 用户第一次执行 Zotero 命令时再初始化 |
| graph view factories | 打开 graph 时再创建 |
| preview proxy/panel | 打开 preview 时再初始化 |
| welcome/what's new | 放到低优先级 background |
| duplicate note doctor | 打开/保存 note 时再执行，且可配置关闭 |
| language providers | 可以先注册轻 handler，重逻辑动态 import |

### 命令懒加载

配合前面的 command manifest，可以做到：

```ts
registerCommand("dendron.someCommand", async () => {
  const { SomeCommand } = await import("./commands/SomeCommand");
  return new SomeCommand(ctx).run();
});
```

---

## 2.9 打包体积和 source map 策略

`package.json` 中 `compile` 使用：

```bash
esbuild ... --bundle ... --sourcemap=inline --sources-content=true
```

开发时没问题，但发布 VSIX 时建议：

- 生产包不要使用 inline sourcemap。
- 可以生成 external sourcemap，或者发布时关闭 sourcemap。
- 检查 `dist/extension.js` 体积。
- 检查 `media/`、`dist/`、复制过来的 webview bundle 是否有重复。
- `.vscodeignore` 应明确排除测试、源码 map、大型临时文件、旧 `.vsix`。

尤其当前目录里已有多个：

```text
sail-zen-vscode-0.3.6.vsix
sail-zen-vscode-0.3.7.vsix
sail-zen-vscode-0.3.8.vsix
sail-zen-vscode-0.3.9.vsix
```

建议确保 `.vscodeignore` 排除 `*.vsix`，避免误打入包中。

---

# 3. 开发体验建议

## 3.1 建立“插件开发模式”的一键脚本

现在 build 相关脚本有：

```json
"precompile": "pnpm --filter=@saili/engine-server run buildCI && pnpm --filter=@saili/dendron-plugin-views run build && pnpm --filter=@saili/dendron-plugin-views run copy-to-plugin",
"compile": "esbuild ...",
"watch": "esbuild ..."
```

建议新增根目录或插件目录脚本：

```bash
pnpm run dev:plugin
pnpm run dev:plugin:views
pnpm run dev:plugin:engine
pnpm run package-plugin:clean
pnpm run test:plugin
pnpm run perf:plugin-startup
```

理想效果：

- 修改插件 TS 自动 rebuild。
- 修改 webview 自动 build + copy。
- engine-server 支持 watch build。
- VSCode launch config 直接启动 Extension Development Host。
- 日志路径固定输出提示。

---

## 3.2 增加命令和 package.json 贡献项一致性检查

当前命令有三处来源：

1. `package.json contributes.commands`
2. `ALL_COMMANDS`
3. `_setupCommands()` 手写特殊命令
4. Zotero 自己注册命令

建议写一个校验脚本：

```bash
pnpm run check:plugin-commands
```

检查：

- `ALL_COMMANDS` 中每个 command key 是否在 `package.json` 中声明。
- `package.json` 中声明的 command 是否有注册实现。
- 是否存在重复 command id。
- `dendron.*` / `sailzen.*` 命名是否符合规则。
- command title 是否仍然错误显示为 Dendron。

这会极大降低长期维护成本。

---

## 3.3 为启动性能建立自动回归测试

既然已经有 `startup-perf.jsonl`，建议继续做一个本地 benchmark：

```bash
pnpm run perf:startup -- --vault fixtures/large-vault
```

准备几个 fixture：

```text
fixtures/vault-small      100 notes
fixtures/vault-medium     1000 notes
fixtures/vault-large      10000 notes
fixtures/vault-large-note includes >200KB notes
```

每次优化后记录：

- total activation
- engine start
- cache load
- reloadWorkspace
- tree init
- memory RSS
- dist bundle size

可以设置简单预算：

```json
{
  "largeVault": {
    "reloadWorkspaceMs": 5000,
    "activationTotalMs": 8000
  }
}
```

不一定 CI 强制失败，但至少输出趋势。

---

## 3.4 增强日志：分离用户日志和开发调试日志

当前 `Logger` 已经存在，`StartupProfiler` 也存在。建议分几类：

```text
logs/plugin.log
logs/plugin-debug.log
logs/startup-perf.jsonl
logs/engine-api.jsonl
logs/watcher-events.jsonl
```

尤其建议加一个 Engine API tracing，可配置开启：

```json
"sailzen.debug.traceEngineApi": true
```

记录：

- method
- duration
- payload size
- error
- request id

这对排查 “lookup 慢 / preview 慢 / save 卡顿” 很有帮助。

---

## 3.5 清理或归档废弃模块

文档已指出 telemetry 基本是 no-op。源码中还有：

- `telemetry/*`
- `stateService.ts` 多处 deprecated
- `ProxyMetricUtils.ts`
- `web/` extension 残留
- 一些 Dendron showcase / sign in / sign up / sync / publish dev 命令

建议建立 `LEGACY.md` 或 `deprecated-modules.md`：

```text
Deprecated but retained:
- telemetry/common/*
- telemetry/node/*
- telemetry/web/*
- services/stateService.ts
- utils/ProxyMetricUtils.ts

Removal candidates:
- SignInCommand
- SignUpCommand
- PublishDevCommand
- SyncCommand
...
```

然后分三类：

1. 立即删除：完全不可达且无 package contribution。
2. 标记 legacy：仍被引用但不再扩展。
3. 重写替代：例如 telemetry -> local perf/logging。

---

## 3.6 改善测试分层

当前有 Jest 配置和部分测试，但插件这种项目更需要三层测试：

### Unit tests

针对纯函数和服务：

- command input enrich
- path/vault utils
- frontmatter utils
- startup profiler
- command manifest validation

### Integration tests

mock VSCode / mock engine：

- WorkspaceActivator init flow
- command registration
- watcher event queue
- EngineAPIService wrapper

### Smoke tests

真实 Extension Development Host：

- 打开小 vault
- 执行 goto note
- 执行 lookup
- 打开 preview
- 保存 note
- rename note

建议先补最关键的：

```text
WorkspaceActivator
Command registration consistency
StartupProfiler
FileWatcher event merge
```

---

## 3.7 文档建议：从“架构索引”升级为“开发手册”

现有架构文档已经很好，但可以再补 4 个章节：

### 新增 Command 指南

说明：

- command class 怎么写
- 如何注册
- 是否需要 active workspace
- package.json 如何声明
- 测试怎么写

### 新增 View/Webview 指南

说明：

- React view 在哪里
- build/copy 流程
- postMessage 协议
- CSP / asset URI / state restore

### 新增 Performance Playbook

说明：

- 如何读取 `startup-perf.jsonl`
- 如何开启 debug trace
- 常见瓶颈
- 大 vault 优化策略

### 新增 Legacy Boundary

说明：

- Dendron 命名为什么还存在
- 新功能用 `sailzen.*`
- 哪些模块不要继续扩展

---

# 建议优先级路线图

## P0：低风险、立刻值得做

1. 扩展 `StartupProfiler`，增加阶段化耗时。
2. 将 `StartupProfiler.write()` 改成异步或降低同步 IO。
3. 检查 `.vscodeignore`，排除 `*.vsix`、测试、无用 sourcemap。
4. 新增 command/package.json 一致性检查脚本。
5. 在架构文档中明确 legacy boundary 和新代码约束。
6. 把 `_setupLanguageFeatures()`、`_setupCommands()` 从 `_extension.ts` 抽出。

## P1：中等收益，需要小规模重构

1. 引入 `WorkspaceActivationContext`，减少 `getExtension()` / `ExtensionProvider` 直接调用。
2. 命令注册改成 manifest + 懒实例化。
3. Watcher 事件队列化、合并、批量提交 engine。
4. `onWillSaveNote()` 避免保存路径上的 engine 查询。
5. Engine API 增加 tracing。
6. Webview postMessage 统一 RPC 协议。

## P2：高收益，但涉及 engine/server 配合

1. `reloadWorkspace()` 改为 cache-first、metadata-first。
2. `.dendron.cache.json` 改进为增量缓存，或迁移到 SQLite / 分片 JSON。
3. Engine server 支持健康检查和复用。
4. Tree/backlinks/lookup 支持 background hydration 后增量刷新。
5. 大 vault benchmark 纳入常规开发流程。

---

# 我最推荐的下一步

如果你希望这个插件继续向 SailZen 3.0 的“常驻影子助手”方向发展，我建议下一步先做：

> **插件启动链路 profiling + `_extension.ts` 瘦身 + command 注册一致性检查。**

这三项成本不高，但会给后续所有重构提供基础：

1. 先知道到底慢在哪里。
2. 先把启动入口拆清楚。
3. 先防止命令系统继续膨胀失控。

完成后，再进入更重的 `reloadWorkspace()` / cache / engine server 复用优化。

在你选择的方向下，我建议长期把 `vscode_plugin` 定位为：

> **本地知识工作台 + AI 心智驾驶舱 + 人类确认界面**  
> 核心智能、后台调度、跨域推理、长期记忆运行在 `sail_server` / 云端；VSCode 插件不再承担“永不休眠的大脑”，而是承担“连接笔记网络、人类编辑行为和 AI 后台心智”的前端操作层。

换句话说：

```text
VSCode Plugin 不是 AI Agent 本体
VSCode Plugin 是 Human-in-the-loop Console + Local Knowledge Adapter
sail_server / cloud daemon 才是 24h Shadow Assistant Runtime
```

这也契合项目原则：

> **Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.**

---

# 1. 长远系统角色划分

未来可以把 SailZen 拆成四层：

```text
┌──────────────────────────────────────────────┐
│ Human Interface Layer                         │
│ - VSCode Plugin                               │
│ - Web Site / Mobile / CLI                     │
│ - Review / Approve / Edit / Inspect           │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ Local Knowledge Workspace                     │
│ - Markdown Notes                              │
│ - Backlinks / wikilinks / hierarchy           │
│ - Local engine index                          │
│ - Local edit events                           │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ Sail Server / Agent Runtime                   │
│ - 24h scheduler                               │
│ - task queue                                  │
│ - semantic graph                              │
│ - AI extraction / completion / linking        │
│ - domain databases                            │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│ Long-term Mind                                │
│ - personal ontology                           │
│ - project memory                              │
│ - finance / health / necessity / text / etc. │
│ - historical traces                           │
└──────────────────────────────────────────────┘
```

在这个结构中，`vscode_plugin` 最重要的不是“做更多后台活”，而是：

1. **捕捉人类正在做什么**
2. **把笔记网络暴露给 AI**
3. **让 AI 结果以低干扰方式回到人类编辑界面**
4. **提供可审计、可回滚、可批准的修改流程**
5. **在本地和云端心智之间做同步、差异展示和安全边界控制**

---

# 2. `vscode_plugin` 的长期定位

## 2.1 从“笔记插件”升级为“AI 心智驾驶舱”

现在插件主要是：

```text
打开笔记
跳转笔记
查找笔记
预览
反链
树视图
笔记增删改
```

未来插件应该成为：

```text
AI 正在看什么
AI 为什么这样建议
AI 准备修改哪些笔记
AI 发现了哪些缺失链接
AI 想补全哪些知识空洞
AI 认为哪些项目/健康/财务/文本状态需要关注
人类是否批准
人类如何反馈
```

也就是从：

> **Editor Extension**

演化为：

> **Mind Console inside VSCode**

---

## 2.2 VSCode 插件不应成为 24 小时后台心智本体

VSCode 插件有天然限制：

- VSCode 不一定一直开着。
- Extension Host 不适合长期 heavy background tasks。
- VSCode 插件被用户编辑行为、窗口生命周期、工作区状态强约束。
- 长时间 LLM 调用、调度、爬取、分析不适合放在 extension host。
- 云端心智需要跨设备、跨工作区、跨时间运行。

所以长期应该避免：

```text
VSCode Plugin 内部跑复杂 Agent loop
VSCode Plugin 内部维护长期任务队列
VSCode Plugin 内部直接做大量 LLM 推理
VSCode Plugin 内部持有最终心智状态
```

更适合：

```text
VSCode Plugin 提供上下文、交互、审查、局部索引、编辑落地
sail_server 提供智能、调度、长期记忆、异步任务、跨域推理
```

---

# 3. 未来架构建议

## 3.1 新增 `Agent Bridge` 层

建议在插件中增加一个明确模块：

```text
packages/vscode_plugin/src/agent/
  AgentBridgeService.ts
  AgentClient.ts
  AgentSessionManager.ts
  AgentTaskProvider.ts
  AgentSuggestionProvider.ts
  AgentReviewPanel.ts
  AgentStatusBar.ts
  AgentContextCollector.ts
```

它的职责是：

```text
插件侧事件 → Agent 事件
Agent 任务 → VSCode 展示
Agent 建议 → 人类审批
Agent 修改 → 本地 workspace patch
人类反馈 → Agent memory
```

不要让普通 command、watcher、webview 直接调用 `sail_server`。统一经过 `AgentBridgeService`。

推荐逻辑：

```text
WorkspaceWatcher
FileWatcher
Command System
Backlink Provider
Editor Context
        │
        ▼
AgentBridgeService
        │
        ▼
sail_server / cloud agent API
```

---

## 3.2 建立稳定的 Agent API 协议

未来 `vscode_plugin` 和 `sail_server` 之间不应该只是普通 REST 调用，而应该有更明确的协议。

建议至少有四类 API：

### 1. Context API

插件向后端提交当前上下文：

```ts
type EditorContext = {
  workspaceId: string;
  activeNote?: {
    id: string;
    fname: string;
    title: string;
    vault: string;
    contentHash: string;
    selectedText?: string;
    cursor?: {
      line: number;
      character: number;
    };
  };
  visibleNotes: string[];
  recentNotes: string[];
  backlinks?: string[];
  outgoingLinks?: string[];
};
```

用途：

- AI 知道你当前在关注什么。
- AI 可以把后台心智和当前编辑任务关联起来。
- AI 可以在合适时机提出建议，而不是随机打扰。

---

### 2. Graph API

插件提供本地笔记网络结构，或者从 engine/server 拉取：

```ts
type NoteGraphSnapshot = {
  workspaceId: string;
  nodes: Array<{
    id: string;
    fname: string;
    title: string;
    vault: string;
    tags?: string[];
    updated: number;
    created: number;
  }>;
  edges: Array<{
    from: string;
    to: string;
    type: "wikilink" | "backlink" | "hierarchy" | "tag" | "embed" | "manual";
    confidence?: number;
  }>;
};
```

用途：

- AI 可以沿反向链接网络扩展上下文。
- AI 可以发现 orphan notes。
- AI 可以发现缺失链接。
- AI 可以进行主题聚类。
- AI 可以对项目、人物、概念形成局部地图。

---

### 3. Task API

后端 Agent 把长期任务暴露给插件：

```ts
type AgentTask = {
  id: string;
  type:
    | "link_completion"
    | "note_summarization"
    | "project_review"
    | "daily_digest"
    | "knowledge_gap_detection"
    | "entity_extraction"
    | "timeline_update"
    | "reading_analysis";
  status: "queued" | "running" | "blocked" | "needs_review" | "done" | "failed";
  title: string;
  description: string;
  relatedNotes: string[];
  createdAt: string;
  updatedAt: string;
};
```

插件侧展示：

- Agent Tasks Tree View
- status bar
- review panel
- command palette

---

### 4. Patch / Suggestion API

AI 不应直接改用户笔记，除非是明确允许的自动化范围。

建议所有 AI 修改先以 patch 形式出现：

```ts
type AgentSuggestion = {
  id: string;
  taskId: string;
  noteId: string;
  kind:
    | "insert_link"
    | "add_backlink"
    | "append_summary"
    | "update_frontmatter"
    | "create_note"
    | "merge_notes"
    | "extract_entity"
    | "add_project_status";
  confidence: number;
  rationale: string;
  diff: string;
  affectedFiles: string[];
  requiresApproval: boolean;
};
```

插件负责：

```text
展示 diff
显示 rationale
接受 / 拒绝 / 修改后接受
批量接受
回滚
把反馈回传给 sail_server
```

这点非常关键。未来 AI 会补全很多人类难以补全的内容，但人类必须能看见：

- 它为什么这样补？
- 它引用了哪些笔记？
- 它会改哪些文件？
- 它的置信度是多少？
- 接受后能否撤销？

---

# 4. 反向链接网络如何适配 AI 调度

你提到的核心愿景是：

> AI 可以更快速地借用反向链接形成的网络，在后台快速补全很多人类难以补全的内容。

这需要把现有 backlink 从“UI 功能”升级为“知识图谱基础设施”。

---

## 4.1 Backlink 不应只是 Tree View

现在 Backlinks 主要面向用户浏览：

```text
当前 note ← 哪些 note 链接了它
```

未来应该扩展成：

```text
当前 note 的局部语义邻域
当前 note 的知识依赖
当前 note 的未闭合问题
当前 note 的潜在上位概念
当前 note 的相关项目/人物/事件/资产/健康记录
```

也就是：

```text
Backlink Panel
  -> Knowledge Neighborhood Panel
```

可以显示：

```text
直接反链
二跳反链
共同引用
同标签
同项目
同人物
同时间段
语义相似但未链接
AI 建议新增链接
```

---

## 4.2 插件需要支持“AI 图遍历上下文包”

AI 不能每次都读全库。它需要快速获得一个 context packet：

```ts
type GraphContextPacket = {
  centerNote: NoteMeta;
  depth: 2 | 3;
  nodes: NoteMeta[];
  edges: GraphEdge[];
  excerpts: Array<{
    noteId: string;
    heading?: string;
    text: string;
    reason: "backlink" | "outgoing" | "semantic" | "recent" | "project";
  }>;
  unresolvedLinks: string[];
  suggestedLinks: SuggestedLink[];
};
```

插件可以请求：

```text
为当前笔记构造 AI 上下文包
为当前选中文本构造 AI 上下文包
为当前项目构造 AI 上下文包
为今日工作构造 AI 上下文包
```

这个包可以由 engine/server 生成，但插件需要提供入口和展示能力。

---

## 4.3 AI 应该能发现“隐形反链”

人类手动写 `[[link]]` 有成本，因此很多真实关联不会被写出来。AI 长期价值之一就是发现这些缺失链接。

建议后端 Agent 生成：

```ts
type SuggestedLink = {
  fromNote: string;
  toNote: string;
  anchorText?: string;
  reason: string;
  evidence: string[];
  confidence: number;
};
```

插件展示为：

```text
AI Suggested Links
- 在 A.md 中建议链接到 B.md
- 原因：两者都讨论 xxx，且 B.md 是 A.md 中 yyy 概念的展开
- 证据片段：...
- 操作：接受 / 忽略 / 永久忽略此模式
```

这会把 backlink 从“已有链接的结果”变成“未来链接的生长机制”。

---

# 5. VSCode 插件应该新增哪些长期功能

## 5.1 Agent Status Center

一个侧边栏视图：

```text
SailZen Mind
├── Cloud Mind: Online
├── Local Workspace: Synced
├── Running Tasks: 7
├── Suggestions: 23
├── Blocked: 2 need review
├── Last Digest: 09:00
└── Current Focus: sailzen-vscode-plugin
```

它让用户知道：

- 云端心智是否在线
- 最近做了什么
- 当前在哪些任务上运行
- 有哪些需要人类确认
- 当前 workspace 是否同步

---

## 5.2 Agent Task Tree

类似：

```text
AI Tasks
├── Needs Review
│   ├── 补全《xxx》人物关系链接
│   ├── 为 project.sailzen.3 添加状态摘要
│   └── 合并重复笔记 health.weight.*
├── Running
│   ├── 扫描最近 7 天新笔记
│   └── 提取文本分析实体
├── Scheduled
│   ├── 每日晨间摘要
│   ├── 每周项目回顾
│   └── 每月财务回顾
└── Done
```

这个视图比传统日志更适合长期 AI 调度。

---

## 5.3 Suggestion Review Panel

AI 的输出不能只放在聊天框里，应该变成结构化 review。

建议 panel 支持：

- diff preview
- evidence snippets
- confidence
- rationale
- impacted notes
- dependency notes
- accept one
- accept all similar
- reject
- reject and teach
- edit before apply

这个功能是未来“AI 帮你补全知识网络”的核心人机界面。

---

## 5.4 Current Note AI Sidebar

打开某个笔记时，插件侧边显示：

```text
AI Context
├── Summary
├── Missing Links
├── Related Notes
├── Possible Duplicates
├── Open Questions
├── Related Projects
├── Related People
├── Related Events
└── Suggested Actions
```

它不是聊天，而是“当前笔记的智能状态面板”。

示例：

```text
当前笔记：project.sailzen.vscode-plugin.future

AI 发现：
- 这篇笔记与 doc/sailzen-3.0-roadmap.md 高度相关，但没有链接。
- 你提到了“反向链接网络”，可能应该连接到 design/agent-system。
- 这篇笔记中包含 3 个可拆分任务。
- 上次相关讨论发生在 2026-04-20。
```

---

## 5.5 AI-generated Backlink Overlay

在编辑器中提供轻量装饰：

```text
[[已有链接]]
⟦AI建议链接：Agent Bridge⟧
```

或者 CodeLens：

```text
+ Add link to agent.bridge.design
+ Create note for "Graph Context Packet"
+ Extract task to project.sailzen.3
```

但要注意默认不打扰，可以配置：

```json
"sailzen.ai.inlineSuggestions": "off" | "subtle" | "active"
```

---

## 5.6 Daily / Weekly Mind Digest

VSCode 插件可以显示由云端生成的 digest：

```text
今日心智摘要
- 昨晚 AI 整理了 17 篇新笔记
- 发现 12 个缺失反链
- 3 个项目状态可能过期
- finance 中有 2 条交易缺少分类
- health.weight 已 5 天未更新
- text analysis 中 xxx 人物关系图有新发现
```

插件不是生成 digest 的地方，但它是最适合呈现 digest 的地方之一。

---

## 5.7 Human Feedback Capture

AI 心智长期变聪明，需要高质量反馈。

插件应支持：

```text
接受
拒绝
稍后
不要再建议这类
这条很重要
这个关联是错的
这个概念应该合并到另一个
这个人物不是同一个人
```

这些反馈应回传 `sail_server`，成为 Agent preference / correction memory。

---

# 6. 数据同步与一致性策略

未来云端 24h 运行，VSCode 本地也会编辑笔记，因此要特别注意一致性。

## 6.1 建议采用 Event Log，而不是直接状态覆盖

插件向后端发送事件：

```ts
type WorkspaceEvent =
  | NoteOpened
  | NoteSaved
  | NoteCreated
  | NoteDeleted
  | NoteRenamed
  | NoteSelectionChanged
  | SuggestionAccepted
  | SuggestionRejected
  | CommandExecuted;
```

后端根据事件更新心智，而不是依赖插件直接推完整状态。

优点：

- 可审计。
- 可重放。
- 可调试。
- 可以形成用户行为长期记忆。
- 便于云端和本地最终一致。

---

## 6.2 AI 修改必须带 provenance

任何 AI 生成内容都应该带来源：

```yaml
ai:
  generatedBy: sailzen-agent
  taskId: xxx
  createdAt: 2026-04-28T...
  sources:
    - note: project.sailzen.3
    - note: doc/design/agent-system
  confidence: 0.82
```

不一定直接写入 frontmatter，也可以写入 sidecar DB。但必须可追溯。

未来用户看到一段摘要时，可以问：

```text
这是谁生成的？
什么时候生成的？
根据哪些笔记生成的？
我是否批准过？
```

---

## 6.3 本地笔记和数据库不要混为一体

未来很多 AI 结果会进入数据库，而不是全部写进 Markdown。

建议区分：

```text
Markdown Notes:
- 人类可读、长期保留、重要表达
- 经过确认的知识
- 可编辑的思想内容

Database:
- task state
- embedding
- graph edge confidence
- suggestion queue
- AI provenance
- event log
- background analysis result
```

VSCode 插件需要展示二者的组合视图，但不要强迫所有 AI 中间产物写入笔记。

---

# 7. 安全与权限模型

这个远景下，安全会变得非常重要。

## 7.1 AI 权限分级

建议建立四级权限：

```text
Level 0: Read only
- AI 只能读笔记和生成建议

Level 1: Suggest
- AI 可以生成 patch，但需要人类批准

Level 2: Auto-apply safe changes
- AI 可以自动补标签、添加低风险反链、更新摘要缓存

Level 3: Autonomous editing
- AI 可以直接创建/修改笔记，但必须有审计和回滚
```

默认推荐：

```text
Level 1
```

对于个人项目中非常确定的任务，可以局部开启 Level 2。

---

## 7.2 按 workspace / vault / note pattern 授权

例如：

```yaml
aiPermissions:
  vaults:
    notes:
      read: true
      suggest: true
      autoApply: false
    private:
      read: false
    finance:
      read: true
      suggest: true
      autoApply: false
  patterns:
    - glob: "daily.private.*"
      read: false
    - glob: "project.*"
      autoApplyLinks: true
```

插件需要提供 UI 管理这些权限。

---

## 7.3 所有 AI 修改可回滚

可以考虑：

- patch log
- git commit
- local snapshot
- `sailzen.undoAgentPatch`
- 每次批量接受建议前创建 checkpoint

插件可以提供：

```text
Agent Changes History
├── 2026-04-28 02:30 自动补全 12 条反链
│   ├── 查看 diff
│   └── 回滚
```

---

# 8. 对当前 `vscode_plugin` 的演化路线

## 阶段一：插件变成 Agent-aware

目标：让当前插件知道云端 Agent 的存在。

新增：

```text
src/agent/AgentClient.ts
src/agent/AgentBridgeService.ts
src/agent/AgentStatusBar.ts
src/agent/AgentTaskTreeProvider.ts
```

实现：

- 配置 `sailzen.agent.endpoint`
- 显示云端连接状态
- 拉取任务列表
- 拉取 suggestions
- 当前 note context 上报
- command：
  - `sailzen.agent.showStatus`
  - `sailzen.agent.syncContext`
  - `sailzen.agent.reviewSuggestions`

此阶段不需要复杂自动修改。

---

## 阶段二：插件支持 AI suggestion review

目标：AI 可以给出结构化建议，人类在 VSCode 中审查。

新增：

```text
AgentReviewPanel
AgentSuggestionTreeProvider
PatchPreviewService
AgentPatchApplyService
```

能力：

- 展示 AI 建议链接
- 展示 AI 生成摘要
- 展示 create note / update note diff
- accept / reject
- feedback 回传

这是核心人机闭环。

---

## 阶段三：插件支持 Graph Context Packet

目标：让 AI 能高效借用反链网络。

新增：

```text
GraphContextService
NoteNeighborhoodProvider
RelatedNotesProvider
```

能力：

- 获取当前 note 的一跳/二跳上下文
- 获取 backlinks/outgoing links/hierarchy/tag/semantic candidates
- 构造上下文包发送给 sail_server
- 展示 AI 图遍历依据

---

## 阶段四：插件支持局部自动化

目标：对低风险内容允许自动应用。

例如：

- 添加反链
- 更新 generated summary block
- 修复 frontmatter 字段
- 为新 note 创建 index entry
- 补全项目状态缓存

但必须：

- 有权限配置
- 有 patch log
- 有回滚
- 有每日 digest

---

## 阶段五：插件成为完整 Mind Console

最终体验：

```text
打开 VSCode
SailZen Mind 显示：
- 云端心智已运行 18 小时
- 昨晚处理 246 个笔记节点
- 生成 31 个建议
- 4 个建议需要你确认
- 2 个项目存在阻塞
- 当前笔记可连接到 7 个相关概念
```

用户不再需要问 AI：

```text
你能帮我整理一下吗？
```

而是 AI 已经在后台整理好了，等待人类审查、确认、修正。

---

# 9. 对现有模块的具体发展方向

## `WorkspaceWatcher`

从“监听保存/重命名”升级为：

```text
WorkspaceEventEmitter
```

负责产生事件：

```text
note.opened
note.saved
note.renamed
note.deleted
selection.changed
activeNote.changed
```

这些事件进入本地队列，再同步给 `sail_server`。

---

## `FileWatcher`

从直接调用 engine 更新，演化为：

```text
FileChangeEventQueue
```

同时通知：

```text
Engine index
Agent event log
Cloud sync
```

---

## `BacklinksTreeDataProvider`

保留传统 backlinks，但新增：

```text
KnowledgeNeighborhoodProvider
AISuggestedLinksProvider
```

让 backlinks 不只是“已有链接”，还包括“AI 推断链接”。

---

## `EngineAPIService`

从纯 engine proxy 演化为：

```text
LocalKnowledgeIndexClient
```

并和 `AgentClient` 分离：

```text
EngineAPIService   -> 本地笔记索引
AgentClient        -> sail_server / cloud mind
```

不要混在一个 client 里。

---

## `StartupProfiler`

扩展成：

```text
PluginRuntimeProfiler
```

记录：

- activation
- engine startup
- graph context generation
- agent API latency
- suggestion apply latency
- watcher queue lag

---

## `commands`

新增 SailZen AI 命令命名空间：

```text
sailzen.agent.openConsole
sailzen.agent.reviewSuggestions
sailzen.agent.explainCurrentNote
sailzen.agent.findMissingLinks
sailzen.agent.generateGraphContext
sailzen.agent.acceptSuggestion
sailzen.agent.rejectSuggestion
sailzen.agent.pause
sailzen.agent.resume
```

旧的 `dendron.*` 命令继续保留，但新 AI 功能使用 `sailzen.agent.*`。

---

# 10. 最重要的设计原则

## 原则一：AI 先建议，再修改

默认不要让 AI 直接写笔记。

```text
Read → Think → Suggest → Review → Apply → Log
```

---

## 原则二：所有 AI 结论必须可追溯

每个建议都要有：

```text
原因
证据
来源笔记
置信度
影响范围
生成时间
任务 ID
```

---

## 原则三：插件不做长期思考，只做局部上下文和人机交互

```text
sail_server/cloud = long-running mind
vscode_plugin = active human workspace adapter
```

---

## 原则四：反链网络是 AI 的路径，不只是 UI 的列表

Backlink 未来是：

```text
context retrieval graph
reasoning graph
suggestion graph
knowledge maintenance graph
```

---

## 原则五：笔记仍然是人类主权空间

AI 可以补全、建议、整理，但最终 Markdown 知识库仍应保持：

- 可读
- 可编辑
- 可 git 管理
- 可迁移
- 不依赖特定模型
- 不被 AI 中间状态污染

---

# 结论

在这个远景下，`vscode_plugin` 不应该继续只作为 Dendron 风格的笔记工具演进，也不应该膨胀成完整 Agent runtime。它最理想的发展方向是：

> **成为 SailZen 24 小时云端心智的本地驾驶舱、上下文采集器、知识图谱浏览器、AI 建议审查器和安全落地层。**

一句话总结：

```text
sail_server 负责“想”和“持续运行”；
engine-server 负责“索引和理解本地笔记结构”；
vscode_plugin 负责“让人类看见、确认、修正和落地 AI 心智的工作”。
```

如果按这个方向推进，我建议下一步最值得设计的是：

```text
AgentBridgeService + AgentTaskTree + SuggestionReviewPanel + GraphContextPacket
```

这四个模块会成为未来 AI 心智系统和 VSCode 笔记插件之间的核心接口。
