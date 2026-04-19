# SailZen NoteDoc 实现路线图与验证文档

> **版本**: 1.0-impl  
> **目标**: 根据 `sailzen_note_doc.md` 设计方案，实现最小可行版本 (MVP)，每一步可独立验证。  
> **范围**: 实现 + 验证。

---

## 实现概览

采用**渐进式实现**策略，每一阶段完成后都有明确的验证手段。不追求一次性实现所有设计，而是先打通"笔记 → LaTeX"的完整链路。

```
笔记 (with doc frontmatter)
    │
    ▼
┌─────────────────────────┐
│ Step 2: ProfileResolver │  ← 验证：解析测试笔记的 doc 配置
│   (读取 frontmatter)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Step 3: DocAssembler    │  ← 验证：递归展开 note refs
│   (组装文档树)          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Step 4: Remark Plugins  │  ← 验证：AST 中包含自定义节点
│   (::cite, ::figure)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Step 5: LaTeX Backend   │  ← 验证：生成可编译的 .tex 文件
│   (代码生成)            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Step 6: VSCode Command  │  ← 验证：命令面板可触发，生成文件
│   (Export to LaTeX)     │
└─────────────────────────┘
```

---

## Step 1: 项目结构与类型定义

### 1.1 新增文件

```
packages/
├── common-all/src/types/docEngine.ts          # 核心类型定义
├── unified/src/remark/sailzenCite.ts          # ::cite 解析插件
├── unified/src/remark/sailzenFigure.ts        # ::figure 解析插件
├── unified/src/types.ts                       # 扩展 DendronASTTypes
├── vscode_plugin/src/docEngine/               # 文档引擎核心
│   ├── types.ts                               # 内部类型
│   ├── profileResolver.ts                     # Profile 解析
│   ├── documentAssembler.ts                   # 文档组装
│   ├── latexBackend.ts                        # LaTeX 后端
│   └── index.ts                               # 导出
└── vscode_plugin/src/commands/
    └── ExportNoteToLatexCommand.ts            # 导出命令
```

### 1.2 类型定义 (`docEngine.ts`)

```typescript
export type DocRole = "source" | "compose" | "standalone" | "asset" | "bib";

export type DocExportConfig = {
  format: "latex" | "typst" | "slidev" | "markdown";
  template?: string;
  outDir?: string;
  vars?: Record<string, any>;
  preProcess?: string;
  postProcess?: string;
};

export type DocMeta = {
  authors?: Array<{
    name: string;
    affiliation?: string;
    email?: string;
  }>;
  conference?: string;
  keywords?: string[];
  [key: string]: any;
};

export type DocFrontmatter = {
  role?: DocRole;
  project?: string;
  order?: number;
  anchors?: string[];
  exports?: DocExportConfig[];
  meta?: DocMeta;
  bibtex?: {
    type: string;
    key: string;
    fields: Record<string, string>;
  };
  asset?: {
    path?: string;
  };
};

export type DocProfile = {
  rootNoteId: string;
  rootNoteFname: string;
  exports: DocExportConfig[];
  meta: DocMeta;
  includes: string[];        // 显式包含的笔记 fname
  discovered: string[];      // 自动发现的 compose 笔记
  citations: string[];       // 被引用的 bib key
  assets: string[];          // 被引用的 asset
};
```

### ✅ 验证方式 1.1: 类型编译

```bash
cd packages/common-all
pnpm run build
# 期望: 无类型错误，build 成功
```

---

## Step 2: Profile Resolution（画像解析）

### 2.1 实现 `profileResolver.ts`

**输入**: 根笔记 `NoteProps` + Engine NotesDict  
**输出**: `DocProfile`

**核心逻辑**:
1. 从 `note.custom.doc` 或 `note.custom` 中提取 `DocFrontmatter`
2. 读取 `doc.exports` 确定目标格式
3. 自动发现：遍历 notesDict，找到同 `project` 下 `role=compose` 的笔记
4. 按 `doc.order` 排序

### ✅ 验证方式 2.1: 单元测试

```typescript
// test/profileResolver.test.ts
const mockNotes = {
  "project.test.paper": {
    fname: "project.test.paper",
    custom: {
      doc: {
        role: "standalone",
        project: "project.test",
        exports: [{ format: "latex", template: "acmart" }]
      }
    }
  },
  "project.test.content.intro": {
    fname: "project.test.content.intro",
    custom: {
      doc: { role: "compose", project: "project.test", order: 1 }
    }
  },
  "project.test.content.method": {
    fname: "project.test.content.method",
    custom: {
      doc: { role: "compose", project: "project.test", order: 2 }
    }
  }
};

const profile = resolveProfile(mockNotes["project.test.paper"], mockNotes);
expect(profile.discovered).toEqual([
  "project.test.content.intro",
  "project.test.content.method"
]);
expect(profile.exports[0].format).toBe("latex");
```

### ✅ 验证方式 2.2: 实际笔记测试

在 `vault/notes/` 中创建测试笔记：

```markdown
---
id: test-doc-root
title: Test Paper
doc:
  role: standalone
  project: project.testdoc
  exports:
    - format: latex
      template: acmart-sigconf
---

![[project.testdoc.content.intro]]
```

```markdown
---
id: test-doc-intro
title: Introduction
doc:
  role: compose
  project: project.testdoc
  order: 1
---

This is the introduction.
```

运行 ProfileResolver，验证能正确发现 `project.testdoc.content.intro`。

---

## Step 3: Document Assembly（文档组装）

### 3.1 实现 `documentAssembler.ts`

**输入**: `DocProfile` + Engine  
**输出**: 组装后的 Markdown 字符串

**核心逻辑**:
1. 从根笔记开始，解析 body 中的 `![[note.ref]]`
2. 对每个 note ref，从 Engine 中获取对应笔记
3. 递归处理（被引用笔记中也可能有 note refs）
4. 处理 heading 层级偏移（嵌入笔记的 `# H1` → `## H2`）
5. 拼接为完整 Markdown

### ✅ 验证方式 3.1: 递归组装测试

```typescript
const assembled = assembleDocument(profile, engine);
expect(assembled).toContain("This is the introduction.");
expect(assembled).not.toContain("![[project.testdoc.content.intro]]");
```

### ✅ 验证方式 3.2: Heading 层级测试

根笔记有 `# Title`，被嵌入笔记有 `# Introduction`，期望输出中 Introduction 变为 `## Introduction`。

---

## Step 4: Remark 插件（::cite, ::figure）

### 4.1 `sailzenCite.ts`

将文本 `::cite[ key1, key2 ]` 解析为自定义 AST 节点：

```typescript
export type CiteNode = {
  type: "sailzenCite";
  keys: string[];
};
```

### 4.2 `sailzenFigure.ts`

将文本 `::figure[caption](src){opts}` 解析为：

```typescript
export type FigureNode = {
  type: "sailzenFigure";
  caption: string;
  src: string;
  options: Record<string, any>;
};
```

### ✅ 验证方式 4.1: AST 节点测试

```typescript
const processor = unified()
  .use(remarkParse)
  .use(sailzenCite)
  .use(sailzenFigure);

const tree = processor.parse("Hello ::cite[foo, bar] world.");
// 遍历 tree，验证存在 type: "sailzenCite" 的节点
// 且 keys = ["foo", "bar"]
```

### ✅ 验证方式 4.2: 集成到现有管线

通过 `MDUtilsV5` 创建 Doc 模式的 processor，验证插件被正确加载。

---

## Step 5: LaTeX 后端代码生成

### 5.1 实现 `latexBackend.ts`

**输入**: 组装后的 Markdown AST  
**输出**: `.tex` 文件内容

**核心逻辑**:
1. 遍历 AST，对每个节点类型生成对应 LaTeX：
   - `paragraph` → `\n{text}\n`
   - `heading` → `\section{...}` / `\subsection{...}`
   - `sailzenCite` → `\cite{keys}`
   - `sailzenFigure` → `\begin{figure}...\end{figure}`
   - `code` → `\begin{verbatim}...\end{verbatim}`
   - `math` → 保留 `$...$` / `$$...$$`
2. 生成 `main.tex` 骨架（基于模板变量）
3. 生成 `ref.bib`（从被引用的 bib 笔记中提取）

### 5.2 最小模板

内置一个最小 LaTeX 模板（不依赖外部模板）：

```latex
\documentclass{article}
\usepackage[UTF8]{ctex}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amsthm}
\begin{document}
\title{<%= title %>}
\author{<%= authors[0].name %>}
\maketitle

<%= content %>

\bibliographystyle{plain}
\bibliography{ref}
\end{document}
```

### ✅ 验证方式 5.1: 输出文件验证

```typescript
const result = generateLatex(ast, profile);
expect(result.mainTex).toContain("\\documentclass");
expect(result.mainTex).toContain("\\cite{foo,bar}");
expect(result.bibTex).toContain("@article{foo}");
```

### ✅ 验证方式 5.2: 可编译性验证

将生成的 `.tex` 复制到临时目录，运行 `pdflatex`（或 `xelatex`），验证：
- 无编译错误
- 输出 PDF 文件

---

## Step 6: VSCode 命令集成

### 6.1 实现 `ExportNoteToLatexCommand.ts`

继承 `BaseCommand`，执行流程：
1. 获取当前活跃笔记
2. 调用 `profileResolver.resolve()`
3. 调用 `documentAssembler.assemble()`
4. 调用 `latexBackend.generate()`
5. 写入 `.sailzen/doc/<project>/latex/` 目录
6. 显示成功通知，提供"打开输出目录"按钮

### 6.2 注册命令

在 `constants.ts` 的 `DENDRON_COMMANDS` 中新增：

```typescript
EXPORT_NOTE_TO_LATEX: {
  key: "sailzen.exportNoteToLatex",
  title: "SailZen: Export Note to LaTeX",
},
```

### ✅ 验证方式 6.1: 命令触发

1. 在 VSCode 中打开测试笔记 (`project.testdoc.paper.md`)
2. 命令面板 (Ctrl+Shift+P) → "SailZen: Export Note to LaTeX"
3. 验证：
   - 状态栏显示 "Exporting..."
   - 右下角弹出 "Export complete" 通知
   - `.sailzen/doc/project.testdoc/latex/` 目录下有 `main.tex` 和 `ref.bib`

### ✅ 验证方式 6.2: 端到端验证

1. 运行导出命令
2. 进入输出目录
3. 运行 `pdflatex main.tex && bibtex main`
4. 验证生成 `main.pdf`
5. 打开 PDF 检查内容完整性

---

## Step 7: 端到端集成测试

### 7.1 测试场景

**场景 A：最小论文**

笔记结构：
```
project.testdoc.paper.md        (standalone)
project.testdoc.content.intro.md (compose, order: 1)
project.testdoc.content.method.md (compose, order: 2)
source.papers.foo.md            (bib)
```

期望输出：
- `main.tex` 包含 `\section{Introduction}` 和 `\section{Method}`
- `ref.bib` 包含 `@article{foo,...}`
- 正文中有 `\cite{foo}`

**场景 B：嵌套引用**

`method.md` 中引用 `source.papers.bar.md`，验证递归展开正确。

### ✅ 验证方式 7.1: 自动化集成测试

```bash
cd packages/vscode_plugin
pnpm test -- --testPathPattern="docEngine"
```

### ✅ 验证方式 7.2: 手工端到端测试

在真实 vault 中创建测试项目，通过命令导出，人工检查 PDF。

---

## 验证清单汇总

| Step | 验证项 | 方式 | 通过标准 |
|------|--------|------|----------|
| 1 | 类型编译 | `pnpm build` | 无类型错误 |
| 2 | Profile 解析 | 单元测试 | 正确发现 compose 笔记 |
| 2 | 实际笔记解析 | 手工测试 | 解析测试笔记无异常 |
| 3 | 文档组装 | 单元测试 | 递归展开正确 |
| 3 | Heading 层级 | 单元测试 | 层级偏移正确 |
| 4 | AST 插件 | 单元测试 | 自定义节点存在 |
| 4 | 集成管线 | 集成测试 | 管线加载无异常 |
| 5 | LaTeX 生成 | 单元测试 | 输出包含预期内容 |
| 5 | LaTeX 可编译 | 手工测试 | `pdflatex` 成功 |
| 6 | 命令触发 | 手工测试 | 命令面板可见且可执行 |
| 6 | 文件输出 | 手工测试 | 输出目录存在且文件完整 |
| 7 | 端到端 | 手工测试 | PDF 内容正确 |

---

## 风险与回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| unified/remark 插件冲突 | 现有预览/发布功能损坏 | 新插件仅在 `DOC_EXPORT` 模式下启用，隔离影响 |
| LaTeX 编译失败 | 输出不可用 | 先生成 `.tex` 文件，用户可手动修复后再编译 |
| 类型定义冲突 | 编译失败 | 使用 `custom?: any` 扩展，不修改现有类型 |
| 性能问题（大笔记库） | 导出缓慢 | ProfileResolver 增加缓存，DocumentAssembler 限制递归深度 |

---

## 后续迭代

MVP 完成后，后续可增加：
1. **更多后端**: Typst, Slidev
2. **更多指令**: `::theorem`, `::algorithm`, `::if-format`
3. **模板系统**: Handlebars 模板 + 模板市场
4. **实时预览**: Doc Preview 面板
5. **文献同步**: `Sync Bibliography` 命令
6. **诊断**: 未解析引用警告、缺失模板变量提示
