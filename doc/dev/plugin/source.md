# SailZen插件源码结构

## 目录概览

```
src/
├── extension.ts              # 入口包装
├── _extension.ts             # 核心激活逻辑 (~745行)
├── commands/                 # 命令实现 (96个文件)
├── components/               # UI组件 (32个文件)
├── features/                 # 语言特性 (12个文件)
├── services/                 # 核心服务 (14个文件)
├── views/                    # 视图实现 (12个文件)
├── workspace/                # 工作区管理 (10个文件)
├── traits/                   # 笔记特性 (5个文件)
├── telemetry/                # 遥测追踪 (5个文件)
├── utils/                    # 工具函数 (15个文件)
├── web/                      # Web扩展变体 (5个文件)
└── external/                 # 外部工具
```

## 入口文件

### extension.ts
插件入口，包装 `_extension.ts` 并处理异常：

```typescript
export function activate(context: vscode.ExtensionContext) {
  z_activate(context);  // Zotero 功能
  _activate(context);   // 主激活逻辑
  return context;
}
```

### _extension.ts
核心激活逻辑：

1. 初始化日志和状态服务
2. 设置依赖注入容器
3. 注册命令和快捷键
4. 设置语言特性提供者
5. 初始化视图和面板
6. 激活工作区

## 命令系统 (commands/)

### 基类

```typescript
// base.ts
abstract class BasicCommand<TOpts, TOut> {
  abstract key: string;
  abstract execute(opts: TOpts): Promise<TOut>;

  run(opts: TOpts): Promise<TOut> {
    // 包装执行逻辑，处理错误和遥测
  }
}
```

### 命令分类

#### 笔记操作
| 文件 | 命令 |
|------|------|
| `NoteLookupCommand.ts` | 笔记查找 |
| `CreateNoteCommand.ts` | 创建笔记 |
| `DeleteCommand.ts` | 删除笔记 |
| `RenameNoteCommand.ts` | 重命名笔记 |
| `MoveNoteCommand.ts` | 移动笔记 |
| `MergeNoteCommand.ts` | 合并笔记 |

#### 日记类型
| 文件 | 命令 |
|------|------|
| `CreateDailyJournal.ts` | 每日日记 |
| `CreateJournalNoteCommand.ts` | 日记笔记 |
| `CreateScratchNoteCommand.ts` | 草稿笔记 |
| `CreateMeetingNoteCommand.ts` | 会议笔记 |

#### 层级导航
| 文件 | 命令 |
|------|------|
| `GoUpCommand.ts` | 向上导航 |
| `GoDownCommand.ts` | 向下导航 |
| `GoToSiblingCommand.ts` | 兄弟导航 |
| `GotoNote.ts` | 跳转笔记 |

#### 工作区管理
| 文件 | 命令 |
|------|------|
| `SetupWorkspace.ts` | 初始化工作区 |
| `VaultAddCommand.ts` | 添加Vault |
| `RemoveVaultCommand.ts` | 移除Vault |
| `Sync.ts` | 同步 |
| `AddAndCommit.ts` | 提交更改 |

#### 链接操作
| 文件 | 命令 |
|------|------|
| `CopyNoteLink.ts` | 复制链接 |
| `CopyNoteRef.ts` | 复制引用 |
| `CopyNoteURL.ts` | 复制URL |
| `InsertNoteLink.ts` | 插入链接 |
| `ConvertLink.ts` | 转换链接 |

#### 视图命令
| 文件 | 命令 |
|------|------|
| `ShowNoteGraph.ts` | 笔记图谱 |
| `ShowSchemaGraph.ts` | Schema图谱 |
| `TogglePreview.ts` | 预览切换 |

#### 开发工具
| 文件 | 命令 |
|------|------|
| `Doctor.ts` | 诊断工具 |
| `OpenLogs.ts` | 打开日志 |
| `ValidateEngineCommand.ts` | 验证引擎 |
| `DiagnosticsReport.ts` | 诊断报告 |

## 语言特性 (features/)

### 提供者实现

| 文件 | 功能 |
|------|------|
| `completionProvider.ts` | 自动补全 (链接、引用) |
| `DefinitionProvider.ts` | 跳转定义 (Ctrl+点击) |
| `ReferenceProvider.ts` | 查找引用 |
| `RenameProvider.ts` | 重命名 (F2) |
| `ReferenceHoverProvider.ts` | 悬停预览 |
| `codeActionProvider.ts` | 代码操作 |
| `FrontmatterFoldingRangeProvider.ts` | 折叠 Frontmatter |

### 视图提供者

| 文件 | 功能 |
|------|------|
| `BacklinksTreeDataProvider.ts` | 反向链接树 |
| `RecentWorkspacesTreeview.ts` | 最近工作区 |
| `windowDecorations.ts` | 编辑器装饰 |

## 服务层 (services/)

### 核心服务

```typescript
// stateService.ts
class StateService {
  globalState: vscode.Memento;      // 全局状态
  workspaceState: vscode.Memento;   // 工作区状态

  getGlobalState<T>(key: string): T | undefined;
  updateGlobalState<T>(key: string, value: T): Thenable<void>;
}
```

```typescript
// CommandRegistrar.ts
class CommandRegistrar {
  registerCommand(cmd: BasicCommand): vscode.Disposable;
  registerAllCommands(): void;
}
```

### 文本服务

| 文件 | 功能 |
|------|------|
| `TextDocumentService.ts` | 文档处理 (node/web) |
| `EngineAPIService.ts` | 引擎API封装 |
| `SchemaSyncService.ts` | Schema同步 |
| `NoteTraitService.ts` | 笔记特性管理 |

## 视图组件 (views/)

### TreeView

```typescript
// treeView/EngineNoteProvider.ts
class EngineNoteProvider implements vscode.TreeDataProvider<NoteTreeItem> {
  getChildren(element?: NoteTreeItem): Promise<NoteTreeItem[]>;
  getTreeItem(element: NoteTreeItem): vscode.TreeItem;
}
```

### WebView

```typescript
// components/views/PreviewViewFactory.ts
class PreviewPanelFactory {
  static create(webview: vscode.Webview): PreviewPanel;
}
```

## 组件 (components/)

### Lookup 组件
```
components/lookup/
├── LookupControllerV3.ts    # 查找控制器
├── NoteLookupProvider.ts    # 笔记查找提供者
├── SchemaLookupProvider.ts  # Schema查找提供者
└── types.ts                 # 类型定义
```

### 视图工厂
```
components/views/
├── PreviewViewFactory.ts        # 预览面板
├── NoteGraphViewFactory.ts      # 笔记图谱
├── SchemaGraphViewFactory.ts    # Schema图谱
└── ConfigureUIPanelFactory.ts   # 配置UI
```

## 工作区管理 (workspace/)

### 工作区类型

| 文件 | 功能 |
|------|------|
| `baseWorkspace.ts` | 基础工作区抽象 |
| `nativeWorkspace.ts` | 原生桌面工作区 |
| `codeWorkspace.ts` | VSCode 工作区 |

### 初始化器

| 文件 | 功能 |
|------|------|
| `workspaceInitializer.ts` | 初始化接口 |
| `blankInitializer.ts` | 空白工作区 |
| `templateInitializer.ts` | 模板工作区 |
| `tutorialInitializer.ts` | 教程工作区 |

### 激活流程

```typescript
// workspaceActivator.ts
class WorkspaceActivator {
  async activateWorkspace(): Promise<void> {
    // 1. 检测工作区类型
    // 2. 初始化引擎
    // 3. 加载笔记索引
    // 4. 设置文件监听
  }
}
```

## 笔记特性 (traits/)

```typescript
// NoteTraitManager.ts
class NoteTraitManager {
  registerTrait(trait: NoteTrait): void;
  getTraitForNote(note: NoteProps): NoteTrait[];
  applyTrait(note: NoteProps, traitId: string): Promise<void>;
}
```

内置特性：
- `journalNote` - 日记笔记
- `scratchNote` - 草稿笔记
- `meetingNote` - 会议笔记
- `taskNote` - 任务笔记

## 工具函数 (utils/)

| 文件 | 功能 |
|------|------|
| `ExtensionUtils.ts` | 扩展工具 |
| `StartupUtils.ts` | 启动工具 |
| `StartupPrompts.ts` | 启动提示 |
| `md.ts` | Markdown工具 |
| `analytics.ts` | 分析工具 |

## Web 变体 (web/)

支持 VSCode Web 版本：

```
web/
├── extension.ts              # Web入口
├── DendronWebExtension.ts    # Web扩展类
└── TextDocumentService.ts    # Web文档服务
```

## 依赖包

### 内部包
| 包名 | 功能 |
|------|------|
| `@saili/common-all` | 通用类型和工具 |
| `@saili/common-server` | 服务端通用代码 |
| `@saili/engine-server` | 笔记引擎核心 |
| `@saili/api-server` | API服务层 |
| `@saili/unified` | Markdown处理 |

### 外部包
| 包名 | 用途 |
|------|------|
| `vscode-languageclient` | LSP客户端 |
| `tsyringe` | 依赖注入 |
| `markdown-it` | Markdown解析 |
| `luxon` | 日期时间处理 |
| `lodash` | 工具函数 |

## 相关文档

- [开发环境](./devenv.md)
- [设计概述](../../design/plugin/overview.md)
- [Vault结构](../../design/plugin/vault.md)
