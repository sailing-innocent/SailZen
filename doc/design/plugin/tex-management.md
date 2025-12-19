# LaTeX 项目管理插件设计

## 1. 背景与目标

### 1.1 现状分析

**SailDoc 当前实现：**
- 使用 xmake 构建系统管理 LaTeX 项目
- 通过 `content.rule.lua` 和 `latex.rule.lua` 收集依赖
- 将所有依赖（tex文件、图片、样式文件等）打包到 `autogendir`
- 调用 `latexmk` 生成 PDF
- 复制到指定输出目录

**存在的问题：**
1. **依赖管理复杂**：大量二进制图片依赖难以追踪和管理
2. **脚本驱动**：依赖 xmake 脚本，缺乏可视化界面
3. **心智负担高**：直接编写 LaTeX，语法复杂
4. **依赖追踪困难**：无法直观看到项目依赖关系图

### 1.2 设计目标

1. **可视化管理**：提供图形界面管理项目依赖，特别是图片资源
2. **Markdown 优先**：主要使用 Markdown 编写，编译时转换为 LaTeX
3. **依赖追踪**：自动分析和可视化展示依赖关系
4. **无缝集成**：与现有 SailZen 插件架构整合
5. **增量构建**：智能检测变更，只重新构建必要部分

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    VSCode Extension Layer                    │
├─────────────────────────────────────────────────────────────┤
│  UI Components                                               │
│  ├─ Asset Browser View (资源浏览器)                         │
│  ├─ Dependency Graph View (依赖关系图)                      │
│  ├─ LaTeX Project Manager (项目管理器)                      │
│  └─ Build Status Panel (构建状态面板)                       │
├─────────────────────────────────────────────────────────────┤
│  Core Services                                               │
│  ├─ AssetManagementService (资源管理服务)                   │
│  ├─ DependencyAnalyzer (依赖分析器)                         │
│  ├─ MarkdownToLatexConverter (Markdown转换器)               │
│  ├─ BuildOrchestrator (构建编排器)                          │
│  └─ ProjectWatcher (项目监控器)                             │
├─────────────────────────────────────────────────────────────┤
│  Data Layer                                                  │
│  ├─ Project Metadata Store (项目元数据存储)                 │
│  ├─ Asset Database (资源数据库)                             │
│  └─ Build Cache (构建缓存)                                  │
└─────────────────────────────────────────────────────────────┘
         ↓                                    ↓
    ┌────────────┐                    ┌──────────────┐
    │  xmake     │                    │  latexmk     │
    │  (可选)    │                    │  (编译器)    │
    └────────────┘                    └──────────────┘
```

### 2.2 核心模块

#### 2.2.1 Asset Browser View（资源浏览器）

**功能：**
- 展示项目中所有资源文件（图片、样式、数据文件等）
- 支持拖拽添加/移除依赖
- 预览图片资源
- 显示资源使用情况（被哪些文档引用）
- 资源搜索与过滤

**界面设计：**
```
┌──────────────────────────────────────┐
│ 📦 LaTeX Assets                    ⚙ │
├──────────────────────────────────────┤
│ 🔍 Search assets...                  │
├──────────────────────────────────────┤
│ 📁 Images (23)                       │
│   ├─ 🖼 fig_bigs_clip_vis/          │
│   │   ├─ 📷 image1.png   [Used: 2]  │
│   │   └─ 📷 image2.jpg   [Used: 1]  │
│   └─ 🖼 fig_gs_gpu_pass/            │
├──────────────────────────────────────┤
│ 📁 Styles (5)                        │
│   ├─ 📄 custom.sty       [Used: 5]  │
│   └─ 📄 theorem.sty      [Used: 3]  │
├──────────────────────────────────────┤
│ 📁 Data (8)                          │
│   └─ 📊 results.csv      [Used: 1]  │
└──────────────────────────────────────┘
```

#### 2.2.2 Dependency Graph View（依赖关系图）

**功能：**
- 可视化展示文档依赖关系
- 支持交互式节点选择和高亮
- 检测循环依赖
- 显示依赖路径

**技术方案：**
- 使用 D3.js 或 vis.js 渲染依赖图
- 实时更新依赖关系
- 支持导出为 SVG/PNG

#### 2.2.3 LaTeX Project Manager（项目管理器）

**功能：**
- 项目配置管理（编译器选择、输出目录等）
- 文档模板管理
- 构建配置（是否启用 bibliography、索引等）
- 多项目支持

**配置文件格式（`.sail-latex.json`）：**
```json
{
  "version": "1.0",
  "projects": [
    {
      "name": "docfig_bigs_clip_vis",
      "type": "figure",
      "main": "main.md",
      "compiler": "xelatex",
      "outputDir": "build",
      "dependencies": [
        {
          "type": "image",
          "path": "assets/fig_bigs_clip_vis",
          "files": ["*.png", "*.jpg"]
        },
        {
          "type": "style",
          "path": "styles/custom.sty"
        }
      ],
      "buildOptions": {
        "enableBib": true,
        "bibFile": "ref.bib",
        "enableIndex": false
      }
    }
  ],
  "globalSettings": {
    "defaultCompiler": "xelatex",
    "outputRoot": "build",
    "cacheEnabled": true
  }
}
```

#### 2.2.4 Markdown to LaTeX Converter（转换器）

**核心特性：**
1. **扩展 Markdown 语法**：支持 LaTeX 专用语法
2. **智能转换**：保留 LaTeX 命令块
3. **模板系统**：支持文档模板（article, beamer, figure等）

**扩展语法示例：**

```markdown
---
title: "3D Gaussian Splatting GPU Pipeline"
type: figure
compiler: xelatex
template: tikz-figure
dependencies:
  - images/fig_gs_gpu_pass/*.png
  - styles/custom.sty
---

# Figure: GPU Pipeline

## Description

This figure illustrates the GPU rendering pipeline for 3D Gaussian Splatting.

<!-- LaTeX Block -->
```latex
\begin{tikzpicture}
  \node[draw] (gpu) at (0,0) {GPU};
  \node[draw] (shader) at (3,0) {Shader};
  \draw[->] (gpu) -- (shader);
\end{tikzpicture}
```

## Assets

![Pipeline Overview](./pipeline.png){width=0.8\textwidth}

<!-- 这会自动转换为：\includegraphics[width=0.8\textwidth]{pipeline.png} -->
```

**转换流程：**
```
Markdown (.md)
    ↓
  [Parser] 解析 frontmatter 和内容
    ↓
  [Transformer] 转换 Markdown → LaTeX
    ↓
  [Template Engine] 应用文档模板
    ↓
  [Asset Resolver] 解析资源引用
    ↓
LaTeX (.tex)
```

#### 2.2.5 Build Orchestrator（构建编排器）

**功能：**
- 管理构建流程
- 增量构建支持
- 并行构建多个文档
- 错误处理和报告

**构建流程：**
```
1. 检测变更文件
   ↓
2. 分析依赖关系
   ↓
3. 确定需要重新构建的文档
   ↓
4. Markdown → LaTeX 转换
   ↓
5. 收集依赖资源到临时目录
   ↓
6. 调用 latexmk 编译
   ↓
7. 复制输出文件
   ↓
8. 更新缓存
```

#### 2.2.6 Project Watcher（项目监控器）

**功能：**
- 监控文件变更（基于 `WorkspaceWatcher` 扩展）
- 自动触发增量构建
- 资源变更检测
- 配置文件热加载

**实现方案：**
```typescript
export class LaTeXProjectWatcher {
  private fileWatcher: FileSystemWatcher;
  private buildQueue: BuildQueue;
  
  async onFileChange(uri: vscode.Uri) {
    if (this.isMarkdownFile(uri)) {
      await this.analyzeDependencies(uri);
      await this.scheduleRebuild(uri);
    } else if (this.isAssetFile(uri)) {
      await this.findAffectedDocuments(uri);
      await this.scheduleRebuild(affectedDocs);
    }
  }
}
```

### 2.3 数据存储

#### 2.3.1 Project Metadata（项目元数据）

存储在 `.sail-latex/metadata.db`（SQLite）：

```sql
-- 项目表
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  main_file TEXT NOT NULL,
  type TEXT,
  compiler TEXT,
  last_build TIMESTAMP
);

-- 资源表
CREATE TABLE assets (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  type TEXT,
  hash TEXT,
  size INTEGER,
  created_at TIMESTAMP
);

-- 依赖关系表
CREATE TABLE dependencies (
  document_id TEXT,
  asset_id TEXT,
  dependency_type TEXT,
  PRIMARY KEY (document_id, asset_id)
);

-- 构建缓存表
CREATE TABLE build_cache (
  file_path TEXT PRIMARY KEY,
  content_hash TEXT,
  dependencies_hash TEXT,
  last_built TIMESTAMP
);
```

## 3. 命令与快捷键设计

### 3.1 新增命令

```json
{
  "commands": [
    {
      "command": "sailzen.latex.newProject",
      "title": "SailZen: Create LaTeX Project"
    },
    {
      "command": "sailzen.latex.buildProject",
      "title": "SailZen: Build LaTeX Project",
      "icon": "$(run)"
    },
    {
      "command": "sailzen.latex.buildAll",
      "title": "SailZen: Build All LaTeX Projects"
    },
    {
      "command": "sailzen.latex.cleanBuild",
      "title": "SailZen: Clean Build Cache"
    },
    {
      "command": "sailzen.latex.addAsset",
      "title": "SailZen: Add Asset to Project"
    },
    {
      "command": "sailzen.latex.showDependencyGraph",
      "title": "SailZen: Show Dependency Graph"
    },
    {
      "command": "sailzen.latex.convertMdToTex",
      "title": "SailZen: Convert Markdown to LaTeX"
    },
    {
      "command": "sailzen.latex.previewPDF",
      "title": "SailZen: Preview PDF Output"
    },
    {
      "command": "sailzen.latex.analyzeAssetUsage",
      "title": "SailZen: Analyze Asset Usage"
    }
  ]
}
```

### 3.2 快捷键绑定

```json
{
  "keybindings": [
    {
      "command": "sailzen.latex.buildProject",
      "key": "ctrl+shift+b",
      "mac": "cmd+shift+b",
      "when": "sailzen:latexProjectActive"
    },
    {
      "command": "sailzen.latex.previewPDF",
      "key": "ctrl+k p",
      "mac": "cmd+k p",
      "when": "sailzen:latexProjectActive"
    }
  ]
}
```

## 4. 实现路径

### 4.1 Phase 1: 基础架构（2-3周）

**目标：** 建立核心服务和数据层

- [ ] 创建 `LaTeXProjectService` 核心服务
- [ ] 实现项目配置解析（`.sail-latex.json`）
- [ ] 建立 SQLite 数据库和 ORM 层
- [ ] 实现基础的 `ProjectWatcher`
- [ ] 添加基本命令（创建项目、构建项目）

**文件结构：**
```
packages/vscode_plugin/src/
  latex/
    ├── services/
    │   ├── LaTeXProjectService.ts
    │   ├── AssetManagementService.ts
    │   └── BuildOrchestrator.ts
    ├── data/
    │   ├── ProjectDatabase.ts
    │   └── schemas.sql
    ├── watchers/
    │   └── LaTeXProjectWatcher.ts
    └── types/
        └── project.types.ts
```

### 4.2 Phase 2: Markdown 转换器（2-3周）

**目标：** 实现 Markdown 到 LaTeX 的转换

- [ ] 扩展 `@saili/unified` 包，添加 LaTeX 转换插件
- [ ] 实现模板系统
- [ ] 支持常用 LaTeX 环境的 Markdown 语法
- [ ] 添加资源路径解析
- [ ] 编写单元测试

**关键模块：**
```typescript
// packages/unified/src/remark/latex/
export class MarkdownToLatexConverter {
  async convert(markdown: string, options: ConvertOptions): Promise<string> {
    const ast = await this.parse(markdown);
    const transformed = await this.transform(ast);
    return this.stringify(transformed);
  }
}
```

### 4.3 Phase 3: 资源管理界面（2周）

**目标：** 实现资源浏览器视图

- [ ] 创建 Asset Browser Webview
- [ ] 实现资源扫描和索引
- [ ] 添加拖拽添加依赖功能
- [ ] 实现图片预览
- [ ] 显示资源使用统计

**技术栈：**
- React for Webview UI
- VSCode Webview API
- File System Watcher

### 4.4 Phase 4: 依赖图可视化（1-2周）

**目标：** 实现依赖关系图视图

- [ ] 集成 D3.js 或 vis.js
- [ ] 实现依赖分析算法
- [ ] 创建交互式依赖图
- [ ] 添加循环依赖检测
- [ ] 支持导出图表

### 4.5 Phase 5: 构建系统集成（2周）

**目标：** 完善构建流程

- [ ] 实现增量构建逻辑
- [ ] 添加构建缓存机制
- [ ] 集成 latexmk
- [ ] 错误处理和日志
- [ ] 构建状态显示面板

### 4.6 Phase 6: 优化和测试（1-2周）

**目标：** 性能优化和完善测试

- [ ] 性能优化（资源索引、构建速度）
- [ ] 添加集成测试
- [ ] 文档编写
- [ ] Bug 修复
- [ ] 用户体验优化

## 5. 技术决策

### 5.1 为什么选择 Markdown 作为主要格式？

1. **易读易写**：降低心智负担，专注内容而非格式
2. **通用性**：可以轻松转换为其他格式（HTML、PDF等）
3. **版本控制友好**：纯文本格式，Git diff 清晰
4. **编辑器支持好**：VSCode 原生支持 Markdown

### 5.2 为什么保留 xmake 兼容性？

1. **向后兼容**：不破坏现有 SailDoc 项目
2. **灵活性**：用户可选择使用 xmake 或插件构建
3. **复杂项目支持**：某些复杂构建逻辑可能仍需要 xmake

### 5.3 为什么使用 SQLite 存储元数据？

1. **无需额外服务**：嵌入式数据库，零配置
2. **性能好**：适合本地查询和索引
3. **事务支持**：保证数据一致性
4. **跨平台**：支持所有 VSCode 平台

### 5.4 构建工具选择

**方案对比：**

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| 完全替代 xmake | 简化架构，统一工具链 | 破坏现有项目，迁移成本高 | ❌ |
| 调用 xmake | 复用现有逻辑，零迁移成本 | 依赖 xmake 安装 | ⚠️ |
| 直接调用 latexmk | 独立性强，轻量级 | 需要自己管理依赖收集 | ✅ |
| 混合方案 | 兼顾灵活性和兼容性 | 实现复杂度高 | ✅ |

**最终方案：** 混合方案
- 默认使用插件直接调用 latexmk
- 提供 xmake 集成选项（通过配置启用）
- 自动检测项目类型并选择构建方式

## 6. 用户工作流示例

### 6.1 创建新的 LaTeX 图表项目

1. 用户执行命令 `SailZen: Create LaTeX Project`
2. 选择项目类型：`Figure`
3. 输入项目名称：`fig_attention_mechanism`
4. 选择模板：`TikZ Figure`
5. 插件自动生成：
   ```
   fig_attention_mechanism/
     ├── main.md (Markdown 源文件)
     ├── .sail-latex.json (项目配置)
     └── assets/ (资源目录)
   ```
6. 用户在 `main.md` 中使用 Markdown + LaTeX 编写内容
7. 插件自动监控变更并提示构建

### 6.2 添加图片依赖

1. 用户将图片拖入 `assets/` 目录
2. `ProjectWatcher` 检测到新文件
3. Asset Browser 自动刷新显示新图片
4. 用户在 Markdown 中引用：`![attention](assets/attention.png)`
5. 插件自动记录依赖关系

### 6.3 构建和预览

1. 用户按 `Ctrl+Shift+B` 或点击构建按钮
2. 插件执行：
   - 转换 `main.md` → `main.tex`
   - 收集依赖到临时目录
   - 调用 `latexmk -pdfxe main.tex`
   - 复制 PDF 到输出目录
3. 构建状态实时显示在状态栏
4. 构建完成后自动打开 PDF 预览

### 6.4 查看依赖关系

1. 用户执行命令 `SailZen: Show Dependency Graph`
2. 打开 Webview 显示依赖图
3. 点击节点高亮相关文件
4. 检测到 `fig_attention_mechanism` 依赖 `custom.sty` 和 `attention.png`
5. 可以导出为 SVG 用于文档

## 7. 与现有架构的集成

### 7.1 复用现有服务

**`WorkspaceWatcher`：**
```typescript
// 扩展现有 WorkspaceWatcher
export class WorkspaceWatcher {
  private latexWatcher: LaTeXProjectWatcher;

  async onDidSaveTextDocument(document: TextDocument) {
    // 现有逻辑...
    
    // 新增 LaTeX 项目检测
    if (this.isLatexProject(document)) {
      await this.latexWatcher.onDocumentSave(document);
    }
  }
}
```

**`TextDocumentService`：**
- 扩展支持 `.tex` 文件
- 提供 LaTeX 语法高亮和自动补全

### 7.2 新增视图容器

```json
{
  "viewsContainers": {
    "activitybar": [
      {
        "id": "sailzen-latex",
        "title": "LaTeX Projects",
        "icon": "media/icons/latex.svg"
      }
    ]
  },
  "views": {
    "sailzen-latex": [
      {
        "id": "sailzen.latex.assets",
        "name": "Assets Browser"
      },
      {
        "id": "sailzen.latex.projects",
        "name": "Projects"
      },
      {
        "id": "sailzen.latex.build-status",
        "name": "Build Status"
      }
    ]
  }
}
```

## 8. 性能考虑

### 8.1 资源索引优化

- 使用增量索引，只扫描变更的目录
- 大文件（>10MB）延迟索引
- 缓存文件哈希值，避免重复计算

### 8.2 构建优化

- 增量构建：只重新编译变更的文档
- 并行构建：多个独立项目可并行编译
- 智能缓存：基于内容哈希判断是否需要重新构建

### 8.3 UI 渲染优化

- 虚拟滚动：Asset Browser 处理大量文件
- 懒加载：依赖图按需加载节点
- Webview 缓存：避免重复渲染

## 9. 未来扩展

### 9.1 协作功能

- 资源共享库：团队共享常用样式和图片
- 模板市场：社区贡献的文档模板
- 云端构建：支持在云端编译 LaTeX

### 9.2 AI 辅助

- AI 辅助编写 LaTeX 代码
- 自动生成 TikZ 图表
- 智能资源推荐

### 9.3 多格式支持

- 支持 Typst 格式（新兴的类 LaTeX 系统）
- 支持 Jupyter Notebook 转 LaTeX
- 支持导出为 Word/EPUB

## 10. 总结

本设计提供了一个完整的 LaTeX 项目管理解决方案，核心特点：

1. **可视化管理**：通过 Asset Browser 和 Dependency Graph 直观管理资源
2. **Markdown 优先**：降低使用门槛，专注内容创作
3. **智能构建**：增量构建和缓存机制提高效率
4. **无缝集成**：与现有 SailZen 插件架构完美整合
5. **向后兼容**：支持现有 SailDoc 项目的迁移

通过这个设计，用户可以更轻松地管理复杂的 LaTeX 项目，特别是处理大量图片依赖时，大大降低了心智负担。
