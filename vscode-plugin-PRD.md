# SailZen VSCode 插件 PRD

> 版本：v1.0  
> 更新时间：2026-02-01  
> 所属模块：packages/vscode_plugin  
> 上级文档：[总体 PRD](./PRD.md)

---

## 1. 模块概述

### 1.1 定位与职责

SailZen VSCode 插件是基于 Dendron 的知识管理工具，提供强大的笔记链接、层级导航和工作区管理功能，专注于：
- **层级化笔记管理**：使用点号分隔的文件名表示层级关系
- **知识图谱构建**：通过 Wiki 风格链接构建笔记网络
- **多工作区支持**：管理多个独立的笔记仓库（Vault）
- **快速捕获**：日记、草稿等快速创建功能
- **文献集成**：Zotero 文献引用管理

### 1.2 核心价值

- **结构化知识管理**：层级化组织大量笔记，清晰的知识架构
- **快速导航**：通过层级关系和链接快速定位笔记
- **灵活扩展**：Schema 定义笔记结构规范，支持自定义模板
- **学术研究友好**：集成 Zotero，方便文献管理
- **本地优先**：所有数据存储在本地，完全控制

### 1.3 技术架构

```
vscode_plugin
├─ TypeScript
├─ VSCode Extension API
├─ Dendron 核心引擎
│  ├─ common-all (通用工具)
│  ├─ common-server (服务端通用)
│  ├─ engine-server (笔记引擎)
│  ├─ api-server (API 服务)
│  └─ unified (Markdown 处理)
├─ tsyringe (依赖注入)
└─ vscode-languageclient (LSP)
```

---

## 2. 核心功能详解

### 2.1 笔记管理 ✅

#### 2.1.1 层级化笔记系统

**设计理念**：
- 使用点号（`.`）分隔的文件名表示层级关系
- 例如：`project.frontend.components` 表示项目下的前端组件笔记
- 支持无限层级嵌套

**核心功能** ✅：
- [x] 笔记创建/编辑/删除
- [x] 笔记查找（Lookup）
  - 命令：`Dendron: Lookup Note` (`Ctrl+L`)
  - 支持模糊搜索
  - 支持层级过滤
  - 创建不存在的笔记
- [x] 层级导航
  - 向上导航 (`Ctrl+Shift+↑`)
  - 向下导航 (`Ctrl+Shift+↓`)
  - 下一个兄弟 (`Ctrl+Shift+]`)
  - 上一个兄弟 (`Ctrl+Shift+[`)
- [x] 笔记重命名
  - 自动更新所有引用
  - 保持层级关系

#### 2.1.2 快速捕获

**日记笔记** ✅：
- [x] 创建日记笔记 (`Ctrl+Shift+I`)
- [x] 支持自定义日记层级
- [x] 日期格式可配置
- [x] 自动生成日记模板

**草稿笔记** ✅：
- [x] 创建临时草稿 (`Ctrl+K S`)
- [x] 草稿独立层级
- [x] 快速记录想法

**其他快捷创建** ✅：
- [x] 从选择创建笔记
- [x] 从剪贴板创建笔记
- [x] 从模板创建笔记

#### 2.1.3 笔记操作

**已实现功能** ✅：
- [x] 复制笔记链接 (`Ctrl+Shift+C`)
- [x] 复制笔记 URL
- [x] 复制笔记引用
- [x] 删除笔记 (`Ctrl+Shift+D`)
- [x] 移动笔记
- [x] 归档笔记
- [x] 查找笔记
- [x] 笔记预览
- [x] 导出笔记（HTML、PDF）

---

### 2.2 链接与引用 ✅

#### 2.2.1 Wiki 风格链接

**语法** ✅：
- `[[note-name]]` - 链接到笔记
- `[[note-name#header]]` - 链接到笔记的特定标题
- `[[note-name|Alias]]` - 使用别名
- `![[note-name]]` - 嵌入笔记内容

**功能** ✅：
- [x] 链接自动补全
- [x] 链接跳转（`F12` 或 `Ctrl+Click`）
- [x] 链接悬停预览
- [x] 失效链接检测
- [x] 链接重命名时自动更新

#### 2.2.2 反向链接

**功能** ✅：
- [x] 自动追踪反向链接
- [x] 反向链接面板
- [x] 链接图谱可视化
- [x] 笔记关系网络

#### 2.2.3 笔记引用

**块引用** ✅：
- [x] 标题引用
- [x] 段落引用
- [x] 代码块引用
- [x] 引用自动更新

---

### 2.3 工作区与 Vault 管理 ✅

#### 2.3.1 工作区系统

**核心概念**：
- **Workspace**：工作区，包含一个或多个 Vault
- **Vault**：笔记仓库，独立的笔记集合
- **Self-Contained Vault**：自包含 Vault，所有配置在 Vault 内部

**功能** ✅：
- [x] 初始化工作区 (`initWS`)
- [x] 工作区配置（`dendron.yml`）
- [x] 工作区同步
- [x] 工作区切换

#### 2.3.2 Vault 管理

**功能** ✅：
- [x] 添加 Vault (`vaultAdd`)
- [x] 移除 Vault (`removeVault`)
- [x] Vault 配置
- [x] 多 Vault 支持
- [x] Vault 选择器
- [x] 跨 Vault 链接

**Vault 类型** ✅：
- [x] 本地 Vault
- [x] Git 仓库 Vault
- [x] 远程 Vault（通过 Git）

---

### 2.4 视图与面板 ✅

#### 2.4.1 树视图

**功能** ✅：
- [x] 层级树视图
- [x] 按字母排序/按修改时间排序
- [x] 展开/折叠层级
- [x] 快速跳转
- [x] 右键菜单操作

#### 2.4.2 日历视图

**功能** ✅：
- [x] 日历视图显示日记
- [x] 点击日期创建/打开日记
- [x] 日期标记（有笔记的日期高亮）
- [x] 月度视图

#### 2.4.3 反向链接面板

**功能** ✅：
- [x] 当前笔记的反向链接列表
- [x] 链接上下文预览
- [x] 点击跳转

#### 2.4.4 笔记图谱

**功能** ✅：
- [x] 笔记关系图谱可视化
- [x] 节点交互（点击跳转）
- [x] 图谱筛选
- [x] 局部图谱/全局图谱

#### 2.4.5 Schema 图谱

**功能** ✅：
- [x] Schema 结构可视化
- [x] Schema 关系展示

---

### 2.5 Schema 与模板 ✅

#### 2.5.1 Schema 系统

**核心概念**：
- Schema 定义笔记的结构规范
- 类似于"文件夹"，但更强大
- 支持继承和模板

**功能** ✅：
- [x] Schema 定义（YAML）
- [x] Schema 验证
- [x] Schema 自动补全
- [x] Schema 层级关系
- [x] Schema 模板绑定

**示例**：
```yaml
schemas:
  - id: project
    title: Project
    desc: Project notes
    parent: root
    children:
      - pattern: frontend
      - pattern: backend
      - pattern: design
```

#### 2.5.2 模板系统

**功能** ✅：
- [x] 笔记模板定义
- [x] 变量替换（日期、时间等）
- [x] 模板继承
- [x] 从模板创建笔记
- [x] Schema 绑定模板

**内置变量**：
- `{{CURRENT_YEAR}}`
- `{{CURRENT_MONTH}}`
- `{{CURRENT_DAY}}`
- `{{CURRENT_TIME}}`
- `{{TITLE}}`

---

### 2.6 文献管理集成 ✅

#### 2.6.1 Zotero 集成

**功能** ✅：
- [x] 引用选择器 (`Alt+Shift+Z`)
- [x] 在 Zotero 中打开 (`Ctrl+Shift+Z`)
- [x] 打开 PDF (`Ctrl+Alt+Shift+Z`)
- [x] 引用格式化
- [x] 文献笔记创建

**引用格式**：
```markdown
[@citekey]
[@citekey, p. 123]
```

---

### 2.7 编辑增强 ✅

#### 2.7.1 语言特性

**已实现** ✅：
- [x] 自动补全
  - 笔记名称补全
  - 链接补全
  - Schema 补全
  - 标签补全
- [x] 跳转定义 (`F12`)
- [x] 查找引用 (`Shift+F12`)
- [x] 重命名 (`F2`)
- [x] 悬停预览
- [x] 代码折叠

#### 2.7.2 快捷操作

**已实现** ✅：
- [x] 插入时间戳
- [x] 插入链接
- [x] 插入图片
- [x] 格式化表格
- [x] 任务列表切换
- [x] 代码块高亮

---

## 3. 配置与设置

### 3.1 VSCode 设置

**核心配置**：
```json
{
  "dendron.rootDir": "",                          // 工作区根目录
  "dendron.logLevel": "info",                     // 日志级别
  "dendron.serverPort": null,                     // 服务端口
  "dendron.enableSelfContainedVaultWorkspace": true,  // 自包含 Vault
  "dendron.defaultJournalName": "journal",        // 日记名称
  "dendron.defaultJournalDateFormat": "y.MM.dd",  // 日记日期格式
  "dendron.defaultScratchName": "scratch",        // 草稿名称
  "dendron.defaultScratchDateFormat": "y.MM.dd.HHmmss"  // 草稿日期格式
}
```

### 3.2 工作区配置

**配置文件**：`dendron.yml`

**核心配置项**：
```yaml
version: 5
vaults:
  - fsPath: vault1
    name: Main Vault
  - fsPath: vault2
    name: Work Vault

workspace:
  journal:
    dailyDomain: daily
    name: journal
    dateFormat: y.MM.dd
  scratch:
    name: scratch
    dateFormat: y.MM.dd.HHmmss

preview:
  enableFMTitle: true
  enableNoteTitleForLink: true

publishing:
  siteUrl: https://example.com
  siteHierarchies:
    - root
```

---

## 4. 命令总览

### 4.1 核心命令（96+ 命令）

#### 笔记操作

| 命令 | 快捷键 | 说明 |
|------|--------|------|
| `lookupNote` | `Ctrl+L` | 查找/创建笔记 |
| `createDailyJournalNote` | `Ctrl+Shift+I` | 创建日记 |
| `createScratchNote` | `Ctrl+K S` | 创建草稿 |
| `copyNoteLink` | `Ctrl+Shift+C` | 复制笔记链接 |
| `delete` | `Ctrl+Shift+D` | 删除笔记 |
| `rename` | - | 重命名笔记 |
| `archive` | - | 归档笔记 |

#### 层级导航

| 命令 | 快捷键 | 说明 |
|------|--------|------|
| `goUpHierarchy` | `Ctrl+Shift+↑` | 向上导航 |
| `goDownHierarchy` | `Ctrl+Shift+↓` | 向下导航 |
| `goNextHierarchy` | `Ctrl+Shift+]` | 下一个兄弟 |
| `goPrevHierarchy` | `Ctrl+Shift+[` | 上一个兄弟 |

#### 工作区管理

| 命令 | 快捷键 | 说明 |
|------|--------|------|
| `initWS` | - | 初始化工作区 |
| `vaultAdd` | - | 添加 Vault |
| `removeVault` | - | 移除 Vault |
| `sync` | - | 同步工作区 |

#### Zotero 集成

| 命令 | 快捷键 | 说明 |
|------|--------|------|
| `insertCitation` | `Alt+Shift+Z` | 引用选择器 |
| `openInZotero` | `Ctrl+Shift+Z` | 在 Zotero 中打开 |
| `openPDF` | `Ctrl+Alt+Shift+Z` | 打开 PDF |

---

## 5. 当前实现状态

### 5.1 已实现功能 ✅

**核心功能**（100% 完成）：
- ✅ 层级化笔记管理
- ✅ Wiki 风格链接与引用
- ✅ 多 Vault 工作区
- ✅ 树视图与日历视图
- ✅ Schema 与模板系统
- ✅ Zotero 文献集成
- ✅ 语言特性（补全、跳转、重命名）
- ✅ 96+ 命令集成

**视图与面板**（100% 完成）：
- ✅ 层级树视图
- ✅ 日历视图
- ✅ 反向链接面板
- ✅ 笔记图谱
- ✅ Schema 图谱

**编辑增强**（100% 完成）：
- ✅ 自动补全
- ✅ 跳转定义
- ✅ 查找引用
- ✅ 重命名
- ✅ 悬停预览
- ✅ 代码折叠

### 5.2 待优化功能 📋

**P1 优先级**：
- [ ] 与 sail_server 数据联动
  - [ ] 同步日记到云端
  - [ ] 笔记元数据云端存储
  - [ ] 跨设备笔记同步
- [ ] 笔记模板系统增强
  - [ ] 更多内置模板
  - [ ] 模板变量扩展
  - [ ] 模板分类管理
- [ ] 搜索性能优化
  - [ ] 全文搜索加速
  - [ ] 增量索引
  - [ ] 搜索结果缓存

**P2 优先级**：
- [ ] AI 辅助写作
  - [ ] AI 自动补全
  - [ ] AI 摘要生成
  - [ ] AI 标签建议
- [ ] 多人协作笔记
  - [ ] 实时协作编辑
  - [ ] 冲突解决
  - [ ] 评论与讨论
- [ ] 移动端支持
  - [ ] VSCode Mobile 适配
  - [ ] 或独立移动应用

**P3 优先级**：
- [ ] 更多视图类型
  - [ ] 看板视图
  - [ ] 时间线视图
  - [ ] 思维导图视图
- [ ] 插件生态
  - [ ] 插件 API
  - [ ] 社区插件市场
- [ ] 性能优化
  - [ ] 大规模笔记性能（10000+ 笔记）
  - [ ] 启动速度优化
  - [ ] 内存占用优化

---

## 6. 与 sail_server 联动设计

### 6.1 联动场景

**日记同步**：
- VSCode 创建日记 → 同步到 sail_server
- 日记中的任务 → 同步到项目管理
- 日记中的支出记录 → 同步到财务管理

**笔记元数据**：
- 笔记创建/修改时间 → 存储到云端
- 笔记标签 → 云端管理
- 笔记关系图谱 → 云端计算与存储

**知识抽取**：
- 笔记内容 → 发送到 sail_server 进行 LLM 分析
- 实体识别 → 存储到文本管理模块
- 关系抽取 → 构建知识图谱

### 6.2 技术方案

**方案 1：VSCode 插件直接调用 API**
```typescript
// 在 VSCode 插件中调用 sail_server API
import axios from 'axios';

async function syncNoteToServer(note: Note) {
  const response = await axios.post('http://server/api/notes', {
    title: note.title,
    content: note.content,
    tags: note.tags,
    created_at: note.created_at
  });
  return response.data;
}
```

**方案 2：通过配置文件关联**
```yaml
# dendron.yml
workspace:
  sailzen:
    enabled: true
    server_url: http://server:8000
    api_key: xxx
    sync_journal: true
    sync_tags: true
```

**方案 3：独立同步服务**
- VSCode 插件生成 JSON 导出
- 独立同步服务监听文件变化
- 自动同步到 sail_server

### 6.3 实现优先级

**P1 优先级**（当前迭代）：
- [ ] 设计联动协议
- [ ] 实现日记同步
- [ ] 实现标签同步

**P2 优先级**（下一迭代）：
- [ ] 实现完整笔记同步
- [ ] 实现知识抽取集成
- [ ] 实现双向同步

---

## 7. 技术架构详解

### 7.1 依赖包结构

```
packages/
├── vscode_plugin/          # VSCode 插件主体
│   ├── src/
│   │   ├── commands/       # 96+ 命令实现
│   │   ├── features/       # 语言特性
│   │   ├── views/          # 视图实现
│   │   ├── services/       # 核心服务
│   │   └── workspace/      # 工作区管理
├── common-all/             # 通用工具和类型定义
├── common-server/          # 服务端通用代码
├── engine-server/          # 笔记引擎核心
├── api-server/             # API 服务层
└── unified/                # Markdown 处理
```

### 7.2 核心服务

**StateService** ✅：
- 管理插件全局状态
- 工作区状态
- Vault 状态
- 配置状态

**CommandRegistrar** ✅：
- 命令注册与管理
- 命令执行
- 命令快捷键绑定

**NoteTraitService** ✅：
- 笔记特性管理
- 日记特性
- 会议笔记特性
- 自定义特性

**EngineNoteProvider** ✅：
- 笔记数据提供
- 笔记索引
- 笔记缓存

### 7.3 依赖注入

使用 `tsyringe` 进行依赖注入管理：

```typescript
import { container } from "tsyringe";

// 注册服务
container.register("IWorkspace", { useClass: NativeWorkspace });
container.register("IStateService", { useClass: StateService });

// 获取服务
const workspace = container.resolve<IWorkspace>("IWorkspace");
```

---

## 8. 性能与优化

### 8.1 性能指标

| 指标 | 目标值 | 当前值 | 说明 |
|------|-------|--------|------|
| 插件启动时间 | < 2s | ~1.5s | ✅ |
| 笔记搜索响应 | < 200ms | ~150ms | ✅ |
| 笔记打开时间 | < 100ms | ~80ms | ✅ |
| 内存占用 | < 200MB | ~150MB | ✅ |
| 大规模笔记支持 | 10000+ | 已测试 5000+ | 🔶 |

### 8.2 性能优化策略

**已实施** ✅：
- [x] 笔记索引缓存
- [x] 增量更新
- [x] 懒加载
- [x] 虚拟滚动（树视图）

**待优化** 📋：
- [ ] 更智能的缓存策略
- [ ] 索引优化（大规模笔记）
- [ ] 搜索算法优化
- [ ] 内存管理优化

---

## 9. 测试与质量

### 9.1 测试覆盖

**当前测试覆盖**：
- `common-all`: ✅ 有测试
- `common-server`: ✅ 有测试
- `unified`: ✅ 有测试
- `engine-server`: 🔶 部分测试
- `vscode_plugin`: 🔶 部分测试

**测试类型**：
- 单元测试（Jest）
- 集成测试
- E2E 测试（部分）

### 9.2 质量保障

**代码质量**：
- TypeScript 严格模式
- ESLint 规则
- Prettier 格式化
- 代码审查

**兼容性**：
- VSCode 版本：1.60+
- Node.js 版本：16+
- 操作系统：Windows、macOS、Linux

---

## 10. 开发路线图

### 10.1 Phase 1: 稳定维护 (2026 Q1-Q2)

**目标**：保持稳定，修复已知问题

**关键任务**：
- [ ] 修复已知 Bug
- [ ] 性能优化（大规模笔记）
- [ ] VSCode 版本兼容性
- [ ] 文档完善

### 10.2 Phase 2: 云端联动 (2026 Q3-Q4)

**目标**：实现与 sail_server 的数据联动

**关键任务**：
- [ ] 设计联动协议
- [ ] 实现日记同步
- [ ] 实现标签同步
- [ ] 实现完整笔记同步
- [ ] 双向同步支持

### 10.3 Phase 3: AI 增强 (2027 Q1-Q2)

**目标**：集成 AI 辅助功能

**关键任务**：
- [ ] AI 自动补全
- [ ] AI 摘要生成
- [ ] AI 标签建议
- [ ] 知识抽取集成
- [ ] 智能笔记推荐

### 10.4 Phase 4: 生态扩展 (2027 Q3+)

**目标**：构建插件生态，支持移动端

**关键任务**：
- [ ] 插件 API
- [ ] 社区插件市场
- [ ] 移动端支持
- [ ] 多人协作
- [ ] 更多视图类型

---

## 11. 相关文档

### 11.1 设计文档
- [插件设计概述](./doc/design/plugin/overview.md)
- [Vault 结构](./doc/design/plugin/vault.md)

### 11.2 开发文档
- [开发环境搭建](./doc/dev/plugin/devenv.md)
- [源码结构](./doc/dev/plugin/source.md)

### 11.3 上级文档
- [总体 PRD](./PRD.md)

---

## 12. 变更记录

| 版本 | 日期 | 作者 | 变更内容 |
|------|------|------|---------|
| v1.0 | 2026-02-01 | AI Assistant | 初始版本，基于现有实现整理 |

---

## 附录

### A. 命令分类总览

**笔记操作**（20+ 命令）：
- 查找、创建、删除、重命名、移动、归档等

**层级导航**（4 命令）：
- 上、下、前、后兄弟导航

**工作区管理**（10+ 命令）：
- 初始化、添加 Vault、同步等

**视图操作**（15+ 命令）：
- 打开树视图、日历视图、图谱等

**编辑增强**（20+ 命令）：
- 插入链接、时间戳、格式化等

**Zotero 集成**（5+ 命令）：
- 引用选择、打开 PDF 等

**其他**（30+ 命令）：
- 配置、诊断、帮助等

### B. 快捷键总览

| 类别 | 快捷键 | 命令 |
|------|--------|------|
| **笔记操作** |||
| 查找笔记 | `Ctrl+L` | `lookupNote` |
| 创建日记 | `Ctrl+Shift+I` | `createDailyJournalNote` |
| 创建草稿 | `Ctrl+K S` | `createScratchNote` |
| 复制链接 | `Ctrl+Shift+C` | `copyNoteLink` |
| 删除笔记 | `Ctrl+Shift+D` | `delete` |
| **层级导航** |||
| 向上 | `Ctrl+Shift+↑` | `goUpHierarchy` |
| 向下 | `Ctrl+Shift+↓` | `goDownHierarchy` |
| 下一个 | `Ctrl+Shift+]` | `goNextHierarchy` |
| 上一个 | `Ctrl+Shift+[` | `goPrevHierarchy` |
| **Zotero** |||
| 引用选择器 | `Alt+Shift+Z` | `insertCitation` |
| 在 Zotero 中打开 | `Ctrl+Shift+Z` | `openInZotero` |
| 打开 PDF | `Ctrl+Alt+Shift+Z` | `openPDF` |
| **编辑** |||
| 跳转定义 | `F12` | 跳转定义 |
| 查找引用 | `Shift+F12` | 查找引用 |
| 重命名 | `F2` | 重命名 |

### C. 配置示例

**基础工作区配置**：
```yaml
version: 5
vaults:
  - fsPath: vault
    name: Main Vault

workspace:
  journal:
    dailyDomain: daily
    name: journal
    dateFormat: y.MM.dd
    addBehavior: asOwnDomain
  scratch:
    name: scratch
    dateFormat: y.MM.dd.HHmmss
    addBehavior: asOwnDomain

preview:
  enableFMTitle: true
  enableNoteTitleForLink: true
  enablePrettyRefs: true

publishing:
  enableFMTitle: true
  enablePrettyRefs: true
```

**自定义 Schema 示例**：
```yaml
version: 1
imports: []
schemas:
  - id: project
    title: Project
    desc: Project notes
    parent: root
    children:
      - pattern: frontend
        template: templates.project.frontend
      - pattern: backend
        template: templates.project.backend
      - pattern: design
        template: templates.project.design
```

**自定义模板示例**：
```markdown
---
id: {{TITLE}}
title: {{TITLE}}
desc: ''
updated: {{CURRENT_TIME}}
created: {{CURRENT_TIME}}
tags:
  - project
  - frontend
---

## Overview

## Tasks

- [ ] TODO

## Notes
```
