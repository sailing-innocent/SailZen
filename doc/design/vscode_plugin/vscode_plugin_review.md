# SailZen VSCode Plugin — 代码地图与技术债务审查报告

> **生成日期**: 2025年（最后更新：本轮清理后）
> **审查范围**: `packages/vscode_plugin/src/`
> **代码总量**: ~220 个 TypeScript 文件（含测试，已清理约 40 个文件）
> **项目背景**: 从开源项目 Sail 分叉演变而来的个人维护 VSCode 插件，目前只服务于单一用户，但仍保留了大量 Sail 的历史代码。

---

## 目录

1. [代码地图](#1-代码地图)
2. [债务清单](#2-债务清单)
3. [后续重构计划](#3-后续重构计划)
4. [顺手修复记录](#4-顺手修复记录)
5. [版本兼容 API 清理记录](#5-版本兼容-api-清理记录)

---

## 1. 代码地图

### 1.1 顶层架构概览

```
src/
├── extension.ts / _extension.ts          # 扩展入口（Node 版）
├── workspace.ts                          # 工作区核心（SailExtension）
├── sailExtensionInterface.ts           # 扩展接口定义
├── ExtensionProvider.ts                   # 静态访问替代方案
├── constants.ts                           # 命令/视图/配置常量（大量 sail. 前缀）
├── types.ts / logger.ts / settings.ts     # 基础类型、日志、设置
├── server.ts / clientUtils.ts             # 本地引擎服务器通信
├── fileWatcher.ts / windowWatcher.ts      # 文件系统与窗口监听
│
├── commands/                              # ~65 个命令实现（已清理 ~15 个）
├── components/                            # UI 组件（Lookup、Views、Doctor）
├── docEngine/                             # SailZen 新增：文档编译引擎
├── features/                              # VSCode 语言功能 Provider
├── services/                              # 核心服务（引擎、Trait、Schema）
├── views/                                 # 树视图与面板视图（Node 版）
├── workspace/                             # 工作区初始化器集合
├── utils/                                 # 通用工具函数
├── traits/                                # Note Trait 系统
└── external/                              # 外部库封装（memo、fileutils）
```

### 1.2 核心目录详解

#### `commands/` — 命令层（~65 文件，已清理冗余命令）

所有 VSCode 命令的实现，遵循 `BasicCommand` / `BasicCommand<T>` 基类模式。文件按功能松散分组：

| 子集 | 关键文件 | 说明 |
|------|---------|------|
| 笔记 CRUD | `CreateNoteCommand.ts`, `DeleteCommand.ts`, `RenameNoteCommand.ts`, `MoveNoteCommand.ts` | 基础笔记生命周期管理 |
| 层级导航 | `GoUpCommand.ts`, `GoDownCommand.ts`, `GoToSiblingCommand.ts` | 在 Sail 层级中上下导航 |
| Lookup | `NoteLookupCommand.ts`, `SchemaLookupCommand.ts`, `NoteLookupAutoCompleteCommand.ts` | 笔记/Schema 查找命令 |
| 模板与 Trait | `ApplyTemplateCommand.ts`, `CreateNoteWithTraitCommand.ts`, `CreateNoteWithUserDefinedTrait.ts` | 模板应用与 Trait 创建 |
| 发布/导出 | `CompileDocumentCommand.ts`, `ExportNoteCommand.ts` | **SailZen 新增**：文档编译与导出 |
| 开发工具 | `DevTriggerCommand.ts`, `Doctor.ts`, `DiagnosticsReport.ts` | 诊断与调试命令 |
| Zotero | `Zotero.ts` | 文献管理集成 |

**命令注册方式**: `_extension.ts` 中通过 `ALL_COMMANDS` 数组批量注册构造函数无参的命令；有参命令（如 `TogglePreviewCommand`）在 `_setupCommands()` 中手动注册。

#### `components/lookup/` — 查找系统（~18 文件，已去版本号）

Sail 的核心 UX 组件，负责 QuickPick 的完整交互逻辑。

| 文件 | 职责 |
|------|------|
| `LookupController.ts` / `LookupControllerFactory.ts` / `LookupControllerInterface.ts` | Lookup 控制器（已去 V3 后缀） |
| `LookupProviderFactory.ts` / `LookupProviderInterface.ts` | 数据提供者工厂（已去 V3 后缀） |
| `NoteLookupProvider.ts` / `SchemaLookupProvider.ts` | 笔记/Schema 查找具体实现 |
| `NotePickerUtils.ts` / `SchemaPickerUtils.ts` | 候选列表生成工具 |
| `HierarchySelector.ts` | 层级选择器 |
| `QuickPickTemplateSelector.ts` | 模板选择器 |
| `TabUtils.ts` | Tab 键自动补全逻辑 |
| `buttons.ts` / `ButtonTypes.ts` | QuickPick 按钮定义 |

**清理状态**: `V3` 后缀已全部移除。`PickerUtilsV2` → `PickerUtils`。`SailClientUtilsV2` → `SailClientUtils`。

#### `components/views/` — 视图组件（~10 文件）

| 文件 | 职责 |
|------|------|
| `PreviewPanel.ts` / `PreviewViewFactory.ts` / `PreviewProxy.ts` | 笔记预览面板（Node 版） |
| `NoteGraphViewFactory.ts` / `SchemaGraphViewFactory.ts` | 图谱视图工厂 |
| `ConfigureUIPanelFactory.ts` | 配置 UI 面板 |
| `LookupQuickPickView.ts` | Lookup 的 QuickPick 视图包装（已去 V3 后缀） |

#### `docEngine/` — SailZen 文档编译引擎（~14 文件 + 7 测试）

**SailZen 新增的核心功能**，负责将 Markdown 笔记编译为 LaTeX / Typst / Markdown 等格式的文档。

| 文件 | 职责 |
|------|------|
| `compileService.ts` | 编译服务入口 |
| `documentAssembler.ts` / `astDocumentAssembler.ts` | 文档组装器（基于文本 / 基于 AST） |
| `latexBackend.ts` / `typstBackend.ts` / `markdownBackend.ts` | 各格式后端生成器 |
| `astLatexTransformer.ts` | AST → LaTeX 转换器 |
| `profileResolver.ts` / `astProfileResolver.ts` | 文档配置文件解析 |
| `templateEngine.ts` / `templateLoader.ts` | 模板引擎与加载器 |

**集成问题**: `docEngine` 与 Sail 遗留代码混在一起，没有清晰的物理或逻辑边界。编译命令 `CompileDocumentCommand` 和 `ExportNoteCommand` 放在 `commands/` 根目录，而非 `commands/docEngine/` 子目录。

#### `features/` — VSCode 语言功能（~12 文件）

实现 VSCode 的各种 `*Provider` 接口：

| 文件 | 注册类型 |
|------|---------|
| `completionProvider.ts` | `CompletionItemProvider` |
| `DefinitionProvider.ts` | `DefinitionProvider` |
| `ReferenceProvider.ts` / `ReferenceHoverProvider.ts` | `ReferenceProvider` / `HoverProvider` |
| `RenameProvider.ts` | `RenameProvider`（内部调用 `RenameNoteInternalCommand`，已去 V2a 后缀） |
| `codeActionProvider.ts` | `CodeActionProvider` |
| `FrontmatterFoldingRangeProvider.ts` | `FoldingRangeProvider` |
| `BacklinksTreeDataProvider.ts` / `Backlink.ts` | 反向链接树视图数据提供 |
| `RecentWorkspacesTreeview.ts` | 最近工作区树视图 |
| `DocStatusBar.ts` | 状态栏显示 |
| `windowDecorations.ts` / `NoteRefComment.ts` | 窗口装饰与行内注释 |

#### `services/` — 核心服务层（~10 文件，已清理 StateService）

| 文件 | 职责 | 债务状态 |
|------|------|---------|
| `EngineAPIService.ts` / `Interface.ts` | 与 engine-server 通信的服务 | 活跃 |
| `TextDocumentServiceFactory.ts` | 文本服务工厂 | 活跃 |
| `NoteTraitManager.ts` / `NoteTraitService.ts` | Trait 系统管理 | **可移除** |
| `SchemaSyncService.ts` / `Interface.ts` | Schema 同步服务 | 活跃 |
| `ZoteroService.ts` | Zotero 文献服务 | 活跃 |
| `CommandRegistrar.ts` | 命令注册辅助 | 活跃 |

#### `workspace/` — 工作区初始化器（~7 文件，已清理 seedBrowserInitializer）

| 文件 | 职责 |
|------|------|
| `workspaceActivator.ts` | 工作区激活主逻辑 |
| `baseWorkspace.ts` | 基础工作区抽象 |
| `codeWorkspace.ts` / `nativeWorkspace.ts` | Code 工作区 / Native 工作区 |
| `blankInitializer.ts` / `templateInitializer.ts` / `tutorialInitializer.ts` | 各类初始化器 |
| `WorkspaceInitFactory.ts` | 初始化器工厂 |

#### `views/` — 树视图实现（~10 文件）

| 文件 | 职责 |
|------|------|
| `CalendarView.ts` | 日历视图 |
| `LookupPanelView.ts` | Lookup 面板视图 |
| `SampleView.ts` / `ShowMeHowView.ts` / `UpgradeView.ts` | 示例/引导/升级视图 |
| `common/treeview/` | 通用树视图组件（`EngineNoteProvider`, `NativeTreeView`, `TreeNote`） |
| `node/treeview/MetadataSvcTreeViewConfig.ts` | Node 版树视图配置 |
| `utils.ts` | 视图工具函数（含 `@deprecated` 方法 `genHTMLForView`，待清理） |

#### `traits/` — Note Trait 系统（~5 文件）

- `journal.ts`, `MeetingNote.ts` — 内置 Trait 实现
- `TraitUtils.ts` — Trait 工具
- `UserDefinedTraitV1.ts` — 用户自定义 Trait
- `webpack-require-hack.ts` — Webpack 兼容 hack

**债务要点**: Sail 的 Trait 系统允许用户定义笔记模板行为，对个人使用可能过度设计。

#### `utils/` — 通用工具（~13 文件，已清理遥测辅助）

| 文件 | 职责 | 债务 |
|------|------|------|
| `ExtensionUtils.ts` | 扩展激活/服务器启动工具 | 第 145 行 dev 模式扩展名已修复 |
| `StartupUtils.ts` | 启动逻辑 | 含 Sail 引导逻辑 |
| `EditorUtils.ts` / `md.ts` / `frontmatter.ts` / `files.ts` | 编辑器/Markdown/Frontmatter/文件工具 | 活跃 |
| `quickPick.ts` / `strings.ts` / `autoCompleter.ts` | UI 与字符串工具 | 活跃 |
| `TwoWayBinding.ts` | 双向绑定工具 | 活跃 |
| `registers/AutoCompletableRegistrar.ts` | 自动完成注册器 | 活跃 |

---

## 2. 债务清单

### 2.1 债务总览表

| 编号 | 债务描述 | 位置 / 文件 | 影响范围 | 建议优先级 | 状态 |
|------|---------|------------|---------|-----------|------|
| D01 | **Package 命令前缀全部为 `sail.`**，仅 `sailzen.compileDocument` 和 `sailzen.exportNote` 例外 | `package.json` > `contributes.commands` (~80 条命令) | 用户-facing 命令 ID、keybindings、菜单绑定 | **P0** | 待处理 |
| D02 | **View IDs 全部使用 `sail.` 前缀**：`sail.backlinks`, `sail.treeView`, `sail.calendar-view`, `sail.lookup-view` 等 | `package.json` > `contributes.views`, `constants.ts` > `DENDRON_VIEWS` | 视图容器、Activity Bar、菜单 when 条件 | **P0** | 待处理 |
| D03 | **Context keys 全部使用 `sail:` 前缀**：`sail:pluginActive`, `sail:devMode`, `sail:noteLookupActive` 等 | `constants.ts` > `SailContext` enum | 所有命令的 `when` / `enablement` 条件 | **P0** | 待处理 |
| D04 | **`extensionQualifiedId = "sail.sail"`** | `constants.ts` 第 11 行 | VSCode 扩展标识、API 调用、版本检测 | **P0** | 待处理 |
| D05 | **文件名 `sailExtensionInterface.ts`、类名 `SailExtension`** | `sailExtensionInterface.ts`, `workspace.ts` | 扩展核心接口与实现，被大量文件 import | **P0** | 待处理 |
| D06 | **上游包 `common-all` 中大量 sail 命名**：`DENDRON_CONFIG_FILE = "sail.yml"`, `DENDRON_WS_NAME = "sail.code-workspace"`, `DENDRON_DELIMETER = "sail://"` | `packages/common-all/src/`（外部依赖） | 配置系统、工作区文件、WikiLink 协议 | **P0** | 待处理 |
| D07 | ~~**日志文件名 `sail.log`, `sail.server.log`**~~ | ~~`ExtensionUtils.ts`, `logger.ts`~~ | ~~日志文件路径~~ | ~~**P1**~~ | ✅ **已清理** |
| D08 | ~~**`workspace.ts` (SailExtension + DWorkspaceV2) 与 `workspacev2.ts` (旧版 DWorkspace) 并存**~~ | ~~`workspace.ts`, `workspacev2.ts`~~ | ~~工作区核心，所有命令依赖~~ | ~~**P0**~~ | ✅ **已清理** |
| D09 | ~~**`WSUtilsV2.ts` / `WSUtilsV2Interface.ts` — "V2" 后缀表明第二次重写**~~ | ~~`WSUtilsV2.ts`, `WSUtilsV2Interface.ts`~~ | ~~工作区工具，广泛依赖~~ | ~~**P1**~~ | ✅ **已清理** |
| D10 | ~~**`LookupControllerV3.ts`, `V3Factory`, `V3Interface` — "V3" 后缀**~~ | ~~`components/lookup/LookupControllerV3*.ts`~~ | ~~Lookup 系统核心~~ | ~~**P1**~~ | ✅ **已清理** |
| D11 | ~~**`LookupProviderV3Factory.ts`, `V3Interface` — "V3" 后缀**~~ | ~~`components/lookup/LookupProviderV3*.ts`~~ | ~~Lookup 数据提供~~ | ~~**P1**~~ | ✅ **已清理** |
| D12 | ~~**`RenameNoteV2a.ts` — 内部 V2a 重命名命令**~~ | ~~`commands/RenameNoteV2a.ts`~~ | ~~重命名功能内部实现~~ | ~~**P1**~~ | ✅ **已清理**（重命名为 `RenameNoteInternal.ts`） |
| D13 | ~~**`Refactor.ts` — LegacyRefactorCommand**~~ | ~~`commands/Refactor.ts`~~ | ~~遗留重构命令~~ | ~~**P1**~~ | ✅ **已清理** |
| D14 | ~~**`web/engine/SailEngineV3Web.ts` / `NoteParserV2.ts` — Web 引擎带版本号**~~ | ~~`web/engine/`~~ | ~~Web 版引擎~~ | ~~**P2**~~ | ✅ **已清理**（`web/` 目录整体不存在） |
| D15 | ~~**`common-all/src/VaultUtilsV2.ts` — 上游 V2 后缀**~~ | ~~`packages/common-all/`~~ | ~~Vault 工具~~ | ~~**P2**~~ | ✅ **已清理**（重命名为 `VaultUtilsURI.ts`） |
| D16 | ~~**`src/web/` 目录下有 32 个 .ts 文件，构成完整 Web VSCode 扩展实现**~~ | ~~`src/web/` 全部~~ | ~~完整的 Web 版平行代码栈~~ | ~~**P1**~~ | ✅ **已清理**（目录不存在） |
| D17 | ~~**Node/Web 平台服务分裂**：`services/node/TextDocumentService.ts` vs `services/web/TextDocumentService.ts`**~~ | ~~`services/node/`, `services/web/`~~ | ~~文本服务~~ | ~~**P1**~~ | ✅ **已清理**（`web/` 已移除） |
| D18 | ~~**预览面板双实现**：`components/views/PreviewPanel.ts` vs `web/views/preview/PreviewPanel.ts`**~~ | ~~`components/views/`, `web/views/preview/`~~ | ~~预览功能~~ | ~~**P1**~~ | ✅ **已清理** |
| D19 | ~~**Web 扩展使用 `tsyringe` DI 容器，Node 扩展使用手动构造函数**~~ | ~~`web/injection-providers/setupWebExtContainer.ts`~~ | ~~架构一致性~~ | ~~**P1**~~ | ✅ **已清理** |
| D20 | **`workspace.ts` 中大量 `@deprecated` 静态方法**：`getDWorkspace()`, `getExtension()`, `getEngine()` | `workspace.ts` 第 84–104 行 | 全局静态访问模式 | **P1** | 待处理（仍被广泛引用，需专项重构） |
| D21 | **`ExtensionProvider` 被设计为替代方案，但过渡未完成** | `ExtensionProvider.ts`, 各处调用 | 架构迁移半途 | **P1** | 待处理 |
| D22 | ~~**`StateService` 整个类被标记为 `@deprecated`**~~ | ~~`services/stateService.ts`~~ | ~~状态管理~~ | ~~**P2**~~ | ✅ **已清理** |
| D23 | ~~**`versionProvider.ts` 被标记为 `@deprecated`**~~ | ~~`versionProvider.ts`~~ | ~~版本获取~~ | ~~**P2**~~ | ✅ **已清理** |
| D24 | **`views/utils.ts` 中有 `@deprecated` 方法** | `views/utils.ts` | 视图工具 | **P2** | 待处理（`genHTMLForView` 仍被 `SampleView.ts` 引用） |
| D25 | ~~**`telemetry/` 目录：完整的遥测系统**~~ | ~~`telemetry/` (~5 文件)~~ | ~~遥测数据收集~~ | ~~**P2**~~ | ✅ **已清理** |
| D26 | ~~**`showcase/` 目录：功能展示提示系统**~~ | ~~`showcase/` (~8 文件)~~ | ~~用户引导~~ | ~~**P2**~~ | ✅ **已清理** |
| D27 | ~~**`commands/SignIn.ts`, `commands/SignUp.ts` — Sail 云端账户认证**~~ | ~~`commands/SignIn.ts`, `commands/SignUp.ts`~~ | ~~账户系统~~ | ~~**P2**~~ | ✅ **已清理** |
| D28 | ~~**`commands/PublishDevCommand.ts` — Sail 发布系统**~~ | ~~`commands/PublishDevCommand.ts`~~ | ~~发布功能~~ | ~~**P2**~~ | ✅ **已清理** |
| D29 | ~~**`commands/SeedAddCommand.ts`, `SeedBrowseCommand.ts`, `SeedRemoveCommand.ts` — Sail Seed 注册表**~~ | ~~`commands/SeedAddCommand.ts` 等~~ | ~~Seed 生态~~ | ~~**P2**~~ | ✅ **已清理** |
| D30 | ~~**`commands/ShowWelcomePageCommand.ts`, `LaunchTutorialWorkspaceCommand.ts` — 教程引导**~~ | ~~`commands/ShowWelcomePageCommand.ts` 等~~ | ~~新用户引导~~ | ~~**P2**~~ | ✅ **已清理** |
| D31 | ~~**`commands/CopyCodespaceURL.ts` — GitHub Codespaces 专用**~~ | ~~`commands/CopyCodespaceURL.ts`~~ | ~~Codespaces 支持~~ | ~~**P2**~~ | ✅ **已清理** |
| D32 | ~~**`commands/MigrateSelfContainedVault.ts`, `RunMigrationCommand.ts` — 迁移命令**~~ | ~~`commands/MigrateSelfContainedVault.ts` 等~~ | ~~数据迁移~~ | ~~**P2**~~ | ✅ **已清理** |
| D33 | ~~**`commands/ShowLegacyPreview.ts` / `ShowPreviewInterface.ts` — Legacy preview**~~ | ~~`commands/ShowLegacyPreview.ts` 等~~ | ~~旧预览系统~~ | ~~**P2**~~ | ✅ **已清理** |
| D34 | ~~**`commands/InstrumentedWrapperCommand.ts` — 遥测包装命令**~~ | ~~`commands/InstrumentedWrapperCommand.ts`~~ | ~~遥测~~ | ~~**P2**~~ | ✅ **已清理** |
| D35 | **Traits 系统过度设计**：`services/NoteTraitManager.ts`, `NoteTraitService.ts`, `traits/` 目录 | `services/NoteTrait*.ts`, `traits/` (~5 文件) | 笔记模板系统 | **P3** | 待处理 |
| D36 | **docEngine 与 Sail 遗留代码混合，无清晰边界** | `docEngine/` (~14 文件), `commands/CompileDocumentCommand.ts`, `commands/ExportNoteCommand.ts` | 文档编译功能 | **P1** | 待处理 |
| D37 | **配置系统混乱**：`sailExtensionInterface.ts` 中 `SailWorkspaceSettings` 含大量 `sail.` 前缀配置键；存在 `sail.yml`, `sailrc.yml`, `sail.code-workspace` 多个配置文件 | `sailExtensionInterface.ts`, `constants.ts` > `CONFIG`, 外部 `common-all` | 配置管理 | **P1** | 待处理 |
| D38 | ~~**`ExtensionUtils.ts` 第 145 行：dev 模式下扩展名是 `sail.sail-sail`（明显错误）**~~ | ~~`utils/ExtensionUtils.ts`~~ | ~~开发模式扩展检测~~ | ~~**P0**~~ | ✅ **已清理** |
| D39 | ~~**`getEnablePrettlyLinks.ts`：文件名和函数名拼写错误（Prettly → Pretty）**~~ | ~~`web/injection-providers/getEnablePrettlyLinks.ts`~~ | ~~Web 版配置注入~~ | ~~**P2**~~ | ✅ **已清理**（`web/` 目录已移除） |
| D40 | ~~**`Refactor.ts` 中 `process.exit(0)` 在 VSCode 扩展环境中极其危险**~~ | ~~`commands/Refactor.ts`~~ | ~~扩展稳定性~~ | ~~**P0**~~ | ✅ **已清理**（文件已删除） |
| D41 | **`_extension.ts` 第 499 行：升级提示指向 `https://sail.so/...`（外部死链风险）** | `_extension.ts` 第 499 行 | 升级提示 | **P1** | 待处理 |
| D42 | **`DENDRON_COMMANDS` 常量对象中 CMD 前缀为 `"Sail:"`** | `constants.ts` 第 151 行 | 命令标题显示 | **P1** | 待处理 |
| D43 | **`DENDRON_CHANNEL_NAME = "Sail"`** | `constants.ts` 第 976 行 | 输出频道名称 | **P1** | 待处理 |
| D44 | **`DENDRON_WORKSPACE_FILE = "sail.code-workspace"`** | `workspace.ts` 第 120 行 | 工作区文件名 | **P0** | 待处理 |
| D45 | **Views Container title 仍为 "Sail"** | `package.json` / `constants.ts` > `DENDRON_VIEWS_CONTAINERS` | Activity Bar 标题 | **P0** | 待处理 |

### 2.2 债务分类统计

| 债务级别 | 数量 | 主要类别 |
|---------|------|---------|
| **P0 — 阻塞/高影响** | 5 | 命名遗留（命令/视图/上下文/扩展ID/工作区文件） |
| **P1 — 高优先** | 9 | docEngine 边界、配置混乱、deprecated 方法过渡、死链 |
| **P2 — 中等优先** | 2 | 视图工具 deprecated 方法、Trait 系统 |
| **P3 — 低优先/可选** | 2 | Trait 系统简化、其他装饰性清理 |
| **已清理** | 29 | 版本兼容 API、冗余命令、遥测/展示/Web 版 |

---

## 3. 后续重构计划

### 3.1 第一轮：命名统一与身份重塑（P0）

**目标**: 消除所有用户可见的 `sail` 命名，建立 SailZen 品牌一致性。

**任务清单**:

1. **package.json 命令前缀迁移**
   - 将所有 `sail.` 前缀命令重命名为 `sailzen.` 前缀
   - 保留 `sailzen.compileDocument` 和 `sailzen.exportNote`
   - 同步更新 `constants.ts` 中 `DENDRON_COMMANDS` 对象的所有 key
   - 同步更新所有 `when` / `enablement` 条件中的命令引用

2. **View IDs 与 Context Keys 迁移**
   - `sail.backlinks` → `sailzen.backlinks`
   - `sail.treeView` → `sailzen.treeView`
   - `sail.calendar-view` → `sailzen.calendarView`
   - `sail.lookup-view` → `sailzen.lookupView`
   - `sail:pluginActive` → `sailzen:pluginActive`
   - `sail:devMode` → `sailzen:devMode`
   - 同步更新 `constants.ts` 中 `SailContext` enum

3. **扩展标识符修正**
   - `extensionQualifiedId = "sail.sail"` → `"sailinginnocent.sail-zen-vscode"`
   - `DENDRON_CHANNEL_NAME = "Sail"` → `"SailZen"`
   - `CMD_PREFIX = "Sail:"` → `"SailZen:"`
   - Views Container title `"Sail"` → `"SailZen"`

4. **核心类重命名**
   - `SailExtension` → `SailZenExtension`
   - `ISailExtension` → `ISailZenExtension`
   - `sailExtensionInterface.ts` → `extensionInterface.ts`
   - `SailWorkspaceSettings` → `SailZenWorkspaceSettings`
   - `SailContext` → `SailZenContext`
   - `DENDRON_COMMANDS` → `SAILZEN_COMMANDS`
   - `DENDRON_VIEWS` → `SAILZEN_VIEWS`

5. **工作区文件名**
   - `DENDRON_WORKSPACE_FILE = "sail.code-workspace"` → `"sailzen.code-workspace"`
   - 需要同步处理 `common-all` 中的 `DENDRON_WS_NAME`

**预计影响**: 全局性改动，需要全量回归测试。

---

### 3.2 第二轮：架构清理与版本合并（P1）—— 大部分已完成

**本轮清理成果**:

- ✅ **Workspace 统一**: `workspacev2.ts` 已删除，`extension.ts` 已迁移到 `DWorkspaceV2`
- ✅ **Lookup 系统去版本号**: `LookupControllerV3` → `LookupController`，`LookupProviderV3Factory` → `LookupProviderFactory`
- ✅ **WSUtils 去版本号**: `WSUtilsV2` → `WSUtils`，`IWSUtilsV2` → `IWSUtils`
- ✅ **PickerUtils 去版本号**: `PickerUtilsV2` → `PickerUtils`
- ✅ **SailClientUtils 去版本号**: `SailClientUtilsV2` → `SailClientUtils`
- ✅ **Rename/Refactor 去版本号**: `RenameNoteV2a` → `RenameNoteInternal`，`RefactorHierarchyV2` → `RefactorHierarchy`
- ✅ **common-all 类型去版本号**: `DNodePropsQuickInputV2` → `DNodePropsQuickInput`，`VaultUtilsV2` → `VaultUtilsURI`
- ✅ **vscode_plugin 类型去版本号**: `SailQuickPickItemV2` → `SailQuickPickItem`，`SailQuickPickerV2` → `SailQuickPicker`

**剩余任务**:

1. **docEngine 边界清晰化**
   - 将 `commands/CompileDocumentCommand.ts` 和 `commands/ExportNoteCommand.ts` 移动到 `commands/docEngine/` 子目录
   - 考虑将 `docEngine/` 提升为 monorepo 的独立包（如 `@saili/doc-engine`）

2. **配置系统简化**
   - 统一配置文件：优先使用 VSCode 的 `settings.json`，逐步废弃 `sail.yml`/`sailrc.yml`
   - 将 `sailExtensionInterface.ts` 中的配置键前缀从 `sail.` 改为 `sailzen.`
   - 与 `common-all` 同步更新 `DENDRON_CONFIG_FILE` 等常量

3. **外部链接修复**
   - 将 `_extension.ts` 中的 `https://sail.so/...` 替换为 SailZen 自己的文档链接或移除升级提示

---

### 3.3 第三轮：Web/Node 平台决策与冗余模块移除（P1/P2）—— 已完成

**本轮清理成果**:

- ✅ **Web 平台移除**: `src/web/` 目录已不存在，Web 版平行实现已清理
- ✅ **遥测系统移除**: `telemetry/` 目录已删除，`ProxyMetricUtils.ts`、`MeetingTelemHelper.ts` 已删除
- ✅ **Showcase 系统移除**: `showcase/` 目录已删除，`_extension.ts` 中的 `FeatureShowcaseToaster` 引用已清理
- ✅ **Sail 专属功能移除**: 以下命令已删除并从 `ALL_COMMANDS`、`constants.ts`、`package.json` 中清理：
  - `SignIn.ts`, `SignUp.ts`
  - `PublishDevCommand.ts`
  - `SeedAddCommand.ts`, `SeedBrowseCommand.ts`, `SeedRemoveCommand.ts`
  - `ShowWelcomePageCommand.ts`, `LaunchTutorialWorkspaceCommand.ts`
  - `CopyCodespaceURL.ts`
  - `MigrateSelfContainedVault.ts`, `RunMigrationCommand.ts`
  - `ShowLegacyPreview.ts`
  - `Refactor.ts`（LegacyRefactorCommand）
  - `InstrumentedWrapperCommand.ts`
- ✅ **StateService 移除**: `services/stateService.ts` 已删除，引用已内联到 `context.workspaceState`
- ✅ **VersionProvider 移除**: `versionProvider.ts` 已删除，引用已改用 `SailExtension.version()`

**剩余任务**:

1. **Trait 系统评估**
   - 评估个人使用是否真正需要 Trait 系统
   - 如不需要，删除 `services/NoteTraitManager.ts`, `NoteTraitService.ts` 和 `traits/` 目录

---

### 3.4 第四轮：Deprecated 代码清理与细节修复（P2/P3）—— 部分完成

**本轮清理成果**:

- ✅ **日志文件名更新**: `sail.log` → `sailzen.log`, `sail.server.log` → `sailzen.server.log`
- ✅ **ExtensionUtils.ts 扩展名修复**: 第 145 行已改为正确的 `SailingInnocent.sail-zen-vscode`
- ✅ **Refactor.ts 危险代码移除**: `process.exit(0)` 随文件一起删除

**剩余任务**:

1. **`workspace.ts` 中 `@deprecated` 静态方法**
   - `getDWorkspace()`, `getExtension()`, `getEngine()` 仍被大量文件引用
   - 需要专项重构，将所有调用迁移到 `ExtensionProvider` 或构造函数注入

2. **`views/utils.ts` 中 `@deprecated` 方法**
   - `genHTMLForView` 仍被 `SampleView.ts` 引用
   - 需将 `SampleView.ts` 迁移到 `getWebviewContent` 后再移除

---

### 3.5 第五轮：上游 common-all 清理（P0/P1，需跨包协调）

**目标**: 清理上游包中的 sail 命名。

**任务清单**:

1. **`common-all` 包常量重命名**
   - `DENDRON_CONFIG_FILE = "sail.yml"` → `SAILZEN_CONFIG_FILE = "sailzen.yml"`
   - `DENDRON_WS_NAME = "sail.code-workspace"` → `SAILZEN_WS_NAME = "sailzen.code-workspace"`
   - `DENDRON_DELIMETER = "sail://"` → `SAILZEN_DELIMETER = "sailzen://"`
   - `DENDRON_VSCODE_CONFIG_KEYS` → `SAILZEN_VSCODE_CONFIG_KEYS`

2. **统一 WikiLink 协议**
   - 将 `sail://` 协议改为 `sailzen://`
   - 更新所有文档和内部链接解析逻辑

---

## 4. 顺手修复记录

本轮审查过程中已识别并建议立即修复的小问题：

| # | 问题 | 位置 | 修复建议 | 状态 |
|---|------|------|---------|------|
| F01 | ~~Dev 模式扩展名错误：`sail.sail-sail`~~ | ~~`utils/ExtensionUtils.ts` ~L145~~ | ~~改为正确的扩展标识符~~ | ✅ **已修复** |
| F02 | ~~`process.exit(0)` 在 VSCode 扩展中危险~~ | ~~`commands/Refactor.ts`~~ | ~~替换为安全的错误处理方式~~ | ✅ **已修复**（文件已删除） |
| F03 | 升级提示指向外部死链 `sail.so` | `_extension.ts` ~L499 | 替换为 SailZen 文档链接或移除 | 🔧 待修复 |
| F04 | ~~文件名/函数名拼写：`Prettly` → `Pretty`~~ | ~~`web/injection-providers/getEnablePrettlyLinks.ts`~~ | ~~重命名文件和函数~~ | ✅ **已修复**（`web/` 已移除） |
| F05 | `DENDRON_COMMANDS.EXPORT_NOTE` / `COMPILE_DOCUMENT` 的 title 仍使用 `Sail:` 前缀 | `constants.ts` ~L848–857 | 改为 `SailZen:` 前缀 | 🔧 待修复 |

---

## 5. 版本兼容 API 清理记录

### 5.1 已删除的文件清单

#### Workspace 旧版
- `src/workspacev2.ts` — 旧版 `DWorkspace` 类

#### 废弃服务
- `src/services/stateService.ts` — `@deprecated` 状态服务
- `src/versionProvider.ts` — `@deprecated` 版本提供者

#### 冗余命令（Sail 专属 / 个人版不需要）
- `src/commands/Refactor.ts` — `LegacyRefactorCommand`
- `src/commands/ShowLegacyPreview.ts` — 旧版预览
- `src/commands/SignIn.ts` — Sail 云端登录
- `src/commands/SignUp.ts` — Sail 云端注册
- `src/commands/PublishDevCommand.ts` — Sail 发布
- `src/commands/SeedAddCommand.ts` — Seed 注册表添加
- `src/commands/SeedBrowseCommand.ts` — Seed 注册表浏览
- `src/commands/SeedRemoveCommand.ts` — Seed 注册表移除
- `src/commands/ShowWelcomePageCommand.ts` — 教程欢迎页
- `src/commands/LaunchTutorialWorkspaceCommand.ts` — 教程工作区启动
- `src/commands/CopyCodespaceURL.ts` — GitHub Codespaces 专用
- `src/commands/MigrateSelfContainedVault.ts` — 数据迁移
- `src/commands/RunMigrationCommand.ts` — 运行迁移
- `src/commands/InstrumentedWrapperCommand.ts` — 遥测包装命令
- `src/commands/SeedCommandBase.ts` — Seed 命令基类

#### Web 版平行实现
- `src/web/` — 整个目录（~32 文件，已提前不存在或本轮确认清理）

#### 遥测系统
- `src/telemetry/` — 整个目录（~5 文件）
- `src/utils/ProxyMetricUtils.ts` — 遥测辅助
- `src/utils/MeetingTelemHelper.ts` — 会议笔记遥测

#### 功能展示提示系统
- `src/showcase/` — 整个目录（~8 文件）

#### 其他辅助文件
- `src/WelcomeUtils.ts` — 教程欢迎工具
- `src/utils/StartupPrompts.ts` — 启动提示（依赖 StateService）
- `src/workspace/seedBrowserInitializer.ts` — Seed 浏览器初始化器

### 5.2 已重命名的类/接口/文件清单

| 旧名称 | 新名称 | 所在文件 |
|--------|--------|---------|
| `WSUtilsV2` | `WSUtils` | `src/WSUtils.ts`（原 `WSUtilsV2.ts`） |
| `IWSUtilsV2` | `IWSUtils` | `src/WSUtilsInterface.ts`（原 `WSUtilsV2Interface.ts`） |
| `LookupControllerV3` | `LookupController` | `src/components/lookup/LookupController.ts` |
| `ILookupControllerV3` | `ILookupController` | `src/components/lookup/LookupControllerInterface.ts` |
| `ILookupControllerV3Factory` | `ILookupControllerFactory` | `src/components/lookup/LookupControllerFactory.ts` |
| `LookupControllerV3CreateOpts` | `LookupControllerCreateOpts` | `src/components/lookup/LookupControllerInterface.ts` |
| `ILookupProviderV3` | `ILookupProvider` | `src/components/lookup/LookupProviderInterface.ts` |
| `ILookupProviderOptsV3` | `ILookupProviderOpts` | `src/components/lookup/LookupProviderInterface.ts` |
| `LookupProviderV3Factory` | `LookupProviderFactory` | `src/components/lookup/LookupProviderFactory.ts` |
| `LookupV3QuickPickView` | `LookupQuickPickView` | `src/components/views/LookupQuickPickView.ts` |
| `RenameNoteV2aCommand` | `RenameNoteInternalCommand` | `src/commands/RenameNoteInternal.ts`（原 `RenameNoteV2a.ts`） |
| `RenameNoteOutputV2a` | `RenameNoteOutput` | `src/commands/RenameNoteInternal.ts` |
| `RefactorHierarchyCommandV2` | `RefactorHierarchyCommand` | `src/commands/RefactorHierarchy.ts`（原 `RefactorHierarchyV2.ts`） |
| `RefactorHierarchyV2CommandOutput` | `RefactorHierarchyCommandOutput` | `src/commands/RefactorHierarchy.ts` |
| `PickerUtilsV2` | `PickerUtils` | `src/components/lookup/utils.ts` |
| `SailClientUtilsV2` | `SailClientUtils` | `src/clientUtils.ts` |
| `DNodePropsQuickInputV2` | `DNodePropsQuickInput` | `packages/common-all/src/types/typesv2.ts` |
| `NoteQuickInputV2` | `ReducedNoteQuickInput` | `packages/common-all/src/types/typesv2.ts` |
| `VaultUtilsV2` | `VaultUtilsURI` | `packages/common-all/src/VaultUtilsURI.ts`（原 `VaultUtilsV2.ts`） |
| `SailQuickPickItemV2` | `SailQuickPickItem` | `src/components/lookup/types.ts` |
| `SailQuickPickerV2` | `SailQuickPicker` | `src/components/lookup/types.ts` |

### 5.3 common-all 中的改动

| 文件 | 改动内容 |
|------|---------|
| `packages/common-all/src/types/typesv2.ts` | `DNodePropsQuickInputV2<T>` → `DNodePropsQuickInput<T>`；`NoteQuickInputV2` → `ReducedNoteQuickInput` |
| `packages/common-all/src/dnode.ts` | 更新 import：`DNodePropsQuickInputV2` → `DNodePropsQuickInput`；`NoteQuickInputV2` → `ReducedNoteQuickInput` |
| `packages/common-all/src/VaultUtilsV2.ts` | 重命名为 `VaultUtilsURI.ts`，类名 `VaultUtilsV2` → `VaultUtilsURI` |
| `packages/common-all/src/index.ts` | `export * from "./VaultUtilsV2"` → `export * from "./VaultUtilsURI"` |
| `packages/engine-server/src/history.ts` | 注释中的 `LookupProviderV3` → `LookupProvider` |

### 5.4 package.json 清理

- 从 `contributes.commands` 中移除 13 个已删除命令的声明
- 从 `contributes.menus.commandPalette` 中移除 13 个已删除命令的菜单项
- 从 `contributes.keybindings` 中移除 1 个已删除命令的快捷键绑定
- 更新 `viewsWelcome` 中 `sail.recent-workspaces` 的内容，移除 `launchTutorialWorkspace` 命令引用

---

## 附录：关键文件速查表

| 类别 | 文件 | 说明 |
|------|------|------|
| 扩展入口 | `src/extension.ts`, `src/_extension.ts` | Node 版激活入口（Web 版已移除） |
| 扩展核心 | `src/workspace.ts`, `src/sailExtensionInterface.ts` | SailExtension 类与接口 |
| 命令注册 | `src/commands/index.ts`, `src/commands/base.ts` | ALL_COMMANDS 数组与基类 |
| 常量定义 | `src/constants.ts` | 命令、视图、上下文键、菜单常量 |
| 配置接口 | `src/sailExtensionInterface.ts` | SailWorkspaceSettings |
| 静态访问 | `src/ExtensionProvider.ts` | 替代全局静态方法的方案 |
| 编译引擎 | `src/docEngine/index.ts` | SailZen 文档编译导出 |
| 日志 | `src/logger.ts`, `src/utils/ExtensionUtils.ts` | 日志与服务器启动 |

---

*报告结束。建议将此报告与 `doc/refact_todo.md` 和 `doc/sailzen-3.0-roadmap.md` 交叉参考，制定具体的重构排期。*
*本轮清理（版本兼容 API 与冗余模块移除）已大幅减少技术债务，剩余主要任务为命名统一（`sail.` → `sailzen.`）和 `workspace.ts` 中 deprecated 静态方法的全面迁移。*
