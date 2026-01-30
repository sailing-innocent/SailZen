# SailZen Plugin 设计概述

SailZen VSCode插件是一个基于 Dendron 的知识管理工具，提供强大的笔记链接、层级导航和工作区管理功能。

## 核心设计理念

### 1. 层级化笔记系统
- 使用点号分隔的文件名表示层级关系（如 `project.frontend.components`）
- 支持 Schema 定义笔记结构规范
- 层级导航支持上下左右移动

### 2. 多Vault工作区
- 一个工作区可包含多个 Vault（笔记仓库）
- 支持自包含 Vault（Self-Contained Vault）模式
- Vault 可以是本地目录或 Git 仓库

### 3. Wiki风格链接
- 使用 `[[note-name]]` 语法创建笔记间链接
- 自动反向链接追踪
- 支持标题锚点链接

## 技术架构

### 依赖包结构

```
packages/
├── vscode_plugin/     # VSCode 插件主体
├── common-all/        # 通用工具和类型定义
├── common-server/     # 服务端通用代码
├── engine-server/     # 笔记引擎核心
├── api-server/        # API 服务层
└── unified/           # Markdown 处理 (基于 unified.js)
```

### 插件架构

```
src/
├── extension.ts          # 入口文件
├── _extension.ts         # 核心激活逻辑
├── commands/             # 命令实现 (96+ 命令)
├── components/           # UI组件
│   ├── lookup/           # 查找功能
│   ├── views/            # 面板工厂
│   └── doctor/           # 诊断工具
├── features/             # 语言特性
│   ├── completionProvider.ts    # 自动补全
│   ├── DefinitionProvider.ts    # 跳转定义
│   ├── ReferenceProvider.ts     # 查找引用
│   ├── RenameProvider.ts        # 重命名
│   └── ReferenceHoverProvider.ts # 悬停预览
├── services/             # 核心服务
│   ├── stateService.ts          # 状态管理
│   ├── CommandRegistrar.ts      # 命令注册
│   └── NoteTraitService.ts      # 笔记特性
├── views/                # 视图实现
│   ├── treeView/               # 层级树视图
│   └── calendar/               # 日历视图
├── workspace/            # 工作区管理
│   ├── workspaceActivator.ts   # 工作区激活
│   └── nativeWorkspace.ts      # 原生工作区
├── traits/               # 笔记特性系统
├── telemetry/            # 遥测追踪
└── utils/                # 工具函数
```

## 核心功能模块

### 1. 笔记操作
| 命令 | 功能 | 快捷键 |
|------|------|--------|
| `lookupNote` | 查找/创建笔记 | `Ctrl+L` |
| `createDailyJournalNote` | 创建日记 | `Ctrl+Shift+I` |
| `createScratchNote` | 创建草稿 | `Ctrl+K S` |
| `copyNoteLink` | 复制笔记链接 | `Ctrl+Shift+C` |
| `delete` | 删除笔记 | `Ctrl+Shift+D` |

### 2. 层级导航
| 命令 | 功能 | 快捷键 |
|------|------|--------|
| `goUpHierarchy` | 向上导航 | `Ctrl+Shift+↑` |
| `goDownHierarchy` | 向下导航 | `Ctrl+Shift+↓` |
| `goNextHierarchy` | 下一个兄弟 | `Ctrl+Shift+]` |
| `goPrevHierarchy` | 上一个兄弟 | `Ctrl+Shift+[` |

### 3. 工作区管理
- `initWS` - 初始化工作区
- `vaultAdd` - 添加 Vault
- `removeVault` - 移除 Vault
- `sync` - 同步工作区

### 4. 视图面板
- **Backlinks** - 反向链接面板
- **Tree View** - 层级树视图
- **Calendar View** - 日历视图
- **Note Graph** - 笔记图谱
- **Schema Graph** - Schema 图谱

### 5. 扩展集成
- **Zotero** - 文献引用管理
  - 引用选择器 (`Alt+Shift+Z`)
  - 在Zotero中打开 (`Ctrl+Shift+Z`)
  - 打开PDF (`Ctrl+Alt+Shift+Z`)

## 配置系统

### VSCode 设置
```json
{
  "dendron.rootDir": "",           // 工作区根目录
  "dendron.logLevel": "info",      // 日志级别
  "dendron.serverPort": null,      // 服务端口
  "dendron.enableSelfContainedVaultWorkspace": true
}
```

### 工作区配置
工作区配置存储在 `dendron.yml` 文件中，包含：
- Vault 定义
- Journal 设置
- Scratch 设置
- Preview 配置
- 发布设置

## 设计模式

### 命令模式
所有命令继承自 `BasicCommand` 基类：
```typescript
abstract class BasicCommand<TOpts, TOut> {
  abstract key: string;
  abstract execute(opts: TOpts): Promise<TOut>;
}
```

### 依赖注入
使用 `tsyringe` 进行依赖注入管理：
```typescript
import { container } from "tsyringe";
container.register("IWorkspace", { useClass: NativeWorkspace });
```

### 语言服务协议 (LSP)
通过 `vscode-languageclient` 实现与语言服务器通信，提供智能编辑功能。

## 相关文档

- [Vault 结构](./vault.md)
- [开发环境](../dev/plugin/devenv.md)
- [源码结构](../dev/plugin/source.md)
