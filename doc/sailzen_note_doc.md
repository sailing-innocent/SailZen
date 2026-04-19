# SailZen NoteDoc: 笔记即源码的排版系统设计方案

> **版本**: 1.0-draft  
> **目标**: 打通 SailZen 笔记库 (`vault/notes`) 与排版输出库 (`vault/doc`)，实现"笔记即源码"(Note-as-Source)的单源发布体系。  
> **范围**: 设计文档，不包含具体实现。

---

## 1. 现状分析

### 1.1 笔记库 (`vault/notes`)

当前笔记库基于 **Dendron** 风格的分层命名体系，约 **8,400+** 个 Markdown 文件：

| 命名空间 | 示例 | 用途 |
|---------|------|------|
| `dev-env.*` | `dev-env.toolchain.xmake.md` | 开发环境配置 |
| `dev-note.*` | `dev-note.cpp.cuda.md` | 技术笔记 |
| `notes.theories.*` | `notes.theories.computer-graphics.*` | 理论/知识库 |
| `source.papers.*` | `source.papers.3d-gaussian-splatting.md` | 文献阅读笔记 |
| `source.articles.*` | `source.articles.*` | 文章/博客笔记 |
| `project.*` | `project.archived.bigs.paper.method.md` | 项目/论文工作笔记 |
| `daily.*` / `journal.*` | `daily.2025.01.01` | 日志 |

**Frontmatter 结构**（现有）：
```yaml
---
id: xxx
title: Texlive
desc: ''
updated: 1715480117387
created: 1715480116341
tags: [tool, latex]
---
```

**已有特性**：
- Wikilink: `[[note.name]]` / `[[note.name#heading]]`
- Note Reference: `![[note.name]]`（嵌入其他笔记内容）
- Block Anchor: `^block-id`
- Schema 系统：`dendron.*.schema.yml`
- Hierarchical tags / hashtags

### 1.2 输出库 (`vault/doc`)

当前 `doc/` 目录是一个**独立的 LaTeX 排版工程**，使用 **xmake** 作为构建系统：

```
doc/
├── doc/
│   ├── content/master/          # 学位论文内容
│   ├── content/algorithms/      # 算法库
│   ├── content/equations/       # 公式库
│   ├── paper/                   # 会议论文
│   │   └── bigs/
│   │       └── acmmm_main.tex
│   ├── thesis/                  # 学位论文主文件
│   │   └── doc/main.tex
│   ├── template/                # 各类模板
│   │   ├── acmart/
│   │   ├── cvpr/
│   │   ├── iccv/
│   │   ├── icml/
│   │   ├── njuthesis/
│   │   └── ...
│   └── bib/                     # BibTeX 数据库
├── figures/                     # 图片资源
├── typst/                       # Typst 实验文件
└── xmake.lua                    # 构建配置
```

**现有痛点**：
1. **双轨维护**：同一内容（如 BIGS 论文的 method 章节）需要在 `notes/project.archived.bigs.paper.method.md` 中写笔记，又在 `doc/doc/paper/bigs/bigs_method.tex` 中写 LaTeX。
2. **内容孤岛**：笔记中的文献引用 (`source.papers.*`) 与 `doc/bib/` 中的 `.bib` 条目无关联。
3. **格式冗余**：为不同会议/期刊（ACMMM, CVPR, ICCV）需要维护多套 `.tex` 文件，内容重复。
4. **图片管理混乱**：`figures/` 目录与笔记中引用的图片路径不统一。
5. **无法渐进输出**：不能从笔记快速生成 draft/slide/poster 等不同格式。

### 1.3 插件架构（SailZen VSCode Extension）

当前插件基于 **Dendron Engine V3** + **Unified/Remark** 渲染管线：

```
Markdown File → NoteParserV2 → DendronEngineV3
                                      ↓
                              Unified Processor
                              (remark plugins)
                              - wikiLinks
                              - noteRefsV2
                              - dendronPub / dendronPreview
                              - publishSite
                              - blockAnchors
                              - hashtags / zdocTags
                                      ↓
                              HTML / Markdown String
```

**关键扩展点**：
- `ProcFlavor` / `ProcMode` 可区分 preview / publish / export 场景
- `DendronASTDest` 支持 HTML / MD_DENDRON / MD_REGULAR 等目标
- `remark` / `rehype` 插件体系可插入自定义转换
- `NoteProps.custom` 可承载任意 frontmatter 扩展字段

---

## 2. 设计目标

### 2.1 核心愿景

> **"笔记即源码" (Note-as-Source)**：SailZen 笔记是唯一的真相来源。任何排版输出（LaTeX 论文、Typst 文档、Slidev 幻灯片）都是笔记的**编译产物**，而非独立维护的文档。

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| **Single Source of Truth** | 消除 notes/ 与 doc/ 的内容重复。doc/ 只保留模板、样式、构建脚本，不保留内容。 |
| **Declarative Composition** | 通过 frontmatter 声明"这份笔记属于哪个输出项目、扮演什么角色"，而非手动组织文件。 |
| **Progressive Enhancement** | 普通笔记无需任何修改即可被引用；需要排版控制的场景才使用扩展语法。 |
| **Engine Agnostic** | 统一中间表示（AST），后端可扩展支持 LaTeX / Typst / Slidev / Markdown 等任意格式。 |
| **Editor Native** | 所有功能内嵌于 VSCode 插件，支持实时预览、一键编译、错误定位。 |

---

## 3. 整体架构

### 3.1 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│                    VSCode Extension Layer                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Commands │  │ Preview  │  │ Status   │  │ Diagnostics│  │
│  │ (Export) │  │ (Doc Mode│  │ Bar      │  │ (Compile)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
└───────┼─────────────┼─────────────┼──────────────┼─────────┘
        │             │             │              │
        ▼             ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                  SailZen Doc Engine (TS)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Profile      │  │ AST Pipeline │  │ Backend Codegen  │  │
│  │ Resolver     │  │ (Unified)    │  │ (LaTeX/Typst/MD) │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                      Vault Storage                           │
│  notes/*.md  →  doc-profile.yml  →  .templates/  →  assets/ │
└─────────────────────────────────────────────────────────────┘
          │                 │                   │
          ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Build Toolchain                  │
│         xmake (LaTeX)  /  typst-cli  /  slidev              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 关键概念

#### 3.2.1 Doc Profile（文档画像）

一个 **Profile** 定义了一个输出项目的完整元数据：模板、格式、包含的笔记、编译参数等。

存储位置：
- **Inline Profile**：笔记自身的 `doc` frontmatter 字段
- **Project Profile**：`notes/project.<name>.doc.<format>.md` 作为根节点
- **Shared Profile**：`.config/doc-profile.yml` 或 `dendron.yml` 的 `docProfiles` 字段

#### 3.2.2 Note Role（笔记角色）

| Role | 说明 | 示例 |
|------|------|------|
| `source` | 普通知识笔记，可被引用但自身不直接输出 | `source.papers.nerf.md` |
| `compose` | 组成文档的章节/片段，可被根文档引用 | `project.bigs.method.md` |
| `standalone` | 自身就是一个完整输出文档 | `project.bigs.paper.acmmm.md` |
| `asset` | 图片、表格、算法等可复用资源 | `project.bigs.fig.teaser.md` |
| `bib` | 文献条目，可导出为 `.bib` | `source.papers.nerf.bib.md` |

#### 3.2.3 Doc Template（文档模板）

模板是目标格式的**骨架文件**（LaTeX 的 `.cls`/`.sty`，Typst 的 `#show` 规则集），负责定义排版样式，内容由笔记填充。

模板路径查找顺序：
1. `vault/.templates/<format>/<template-name>/`
2. `vault/doc/template/`（复用现有模板）
3. SailZen 插件内置模板库

---

## 4. 语法设计：SailZen Doc Markdown

### 4.1 Frontmatter 扩展

在现有 Dendron frontmatter 基础上新增 `doc` 顶级字段：

```yaml
---
id: xxx
title: "BIGS: Bayesian Inference Gaussian Splatting"
desc: 'ACMMM 2025 Submission'
updated: 1765940490469
created: 1715430099515
tags: [paper, gs, feature-uplifting]
# ── SailZen Doc 扩展 ──
doc:
  # 角色：这份笔记在文档系统中的定位
  role: standalone        # source | compose | standalone | asset | bib
  
  # 隶属的文档项目（可选，用于聚合）
  project: project.bigs
  
  # 输出格式配置（standalone 或 compose 时生效）
  exports:
    - format: latex
      template: acmart-sigconf
      outDir: doc/paper/bigs/
      # 模板变量注入
      vars:
        documentclass: "[sigconf,authordraft,anonymous]{acmart}"
        bibliography: "ref"
      # 预处理钩子
      preProcess: "stripAnnotations"
      # 后处理钩子
      postProcess: "anonimizeAuthors"
    - format: typst
      template: research-article
      outDir: doc/typst/bigs/
    - format: slidev
      template: nju-thesis-defense
      outDir: doc/slide/bigs/
  
  # 排版元数据（模板可引用）
  meta:
    authors:
      - name: "Zhu Zihang"
        affiliation: "Nanjing University"
        email: "522022150087@smail.nju.edu.cn"
    conference: "ACM Multimedia 2025"
    keywords: 
      - "Gaussian Splatting"
      - "2D-3D Feature Uplifting"
---
```

**Compose 角色的章节笔记**：

```yaml
---
id: xxx
title: Method
doc:
  role: compose
  project: project.bigs
  # 在父文档中的顺序/权重
  order: 3
  # 可被引用的锚点标记
  anchors: [problem-formulation, bayesian-framework, inference-pipeline]
---
```

### 4.2 行内扩展语法

SailZen Doc 扩展语法兼容 CommonMark，以 `::` 为指令前缀（类似自定义 directive），在现有渲染管线中作为特殊节点处理。

#### 4.2.1 文献引用 `::cite`

```markdown
Existing methods typically rely on explicit depth estimation ::cite[ instant-ngp, 
mip-nerf-360, gaussian-splatting-original ] or multi-view stereo ::cite[ colmap ].
```

**编译行为**：
- 解析 `::cite[ keys ]` 中的 key，匹配 `source.papers.<key>.md` 或 `project.<name>.bib.*.md`
- 自动收集所有引用，生成对应格式的参考文献列表
- LaTeX: `\cite{instant-ngp, mip-nerf-360, ...}` + `.bib` 文件
- Typst: `@instant-ngp` + `#bibliography(...)`

**文献笔记的 BibTeX 提取**：

```yaml
---
id: xxx
title: Instant NGP
doc:
  role: bib
  bibtex:
    type: article
    key: instant-ngp
    fields:
      author: "Thomas M\"{u}ller et al."
      title: "Instant Neural Graphics Primitives"
      journal: "ACM TOG"
      year: 2022
---

## 笔记正文
...
```

#### 4.2.2 增强图片 `::figure`

```markdown
::figure[Overview of our Bayesian Inference Gaussian Splatting framework.]
  (fig_bigs_teaser)
  {
    width: "\linewidth",
    label: "fig:teaser",
    subfigures: [
      { src: "fig_bigs_teaser_a", caption: "Input" },
      { src: "fig_bigs_teaser_b", caption: "Output" }
    ]
  }
```

**路径解析规则**：
1. 若 `fig_bigs_teaser` 对应笔记 `project.bigs.fig.teaser.md`，提取其 frontmatter 中的 `doc.asset.path`
2. 若对应 `doc/figures/fig_bigs_teaser/` 目录，自动查找 `.pdf`/`.png`/`.svg`
3. 支持 `width`, `height`, `placement` 等跨格式通用参数

#### 4.2.3 表格 `::table`

```markdown
::table[Comparison with state-of-the-art methods on Replica dataset.]
  (tab:replica_comparison)
  {
    columns: [l c c c c],
    source: "project.bigs.exp.replica-table"   # 引用另一个笔记中的表格数据
  }

| Method | PSNR↑ | SSIM↑ | LPIPS↓ | Time |
|:-------|------:|------:|-------:|-----:|
| 3DGS   | 32.1  | 0.95  | 0.12   | 10m  |
| BIGS   | 34.5  | 0.97  | 0.08   | 12m  |
```

#### 4.2.4 数学环境 `::theorem`, `::proof`, `::definition`

```markdown
::definition[Bayesian Gaussian Splatting]{label: "def:bigs"}
Given a set of 3D Gaussians $\mathcal{G} = \{g_i\}_{i=1}^N$ with parameters 
$\theta_i = (\mu_i, \Sigma_i, c_i, \alpha_i)$, we define the posterior distribution 
over feature fields as:
$$
p(f | \mathcal{I}, \mathcal{G}) \propto p(\mathcal{I} | f, \mathcal{G}) \, p(f | \mathcal{G})
$$
::end

::theorem[Feature Consistency]{label: "thm:consistency"}
Under the Markov blanket assumption, the posterior factorizes across views as...
::end

::proof
The likelihood term decomposes as...
::end
```

**后端映射**：
- LaTeX: `\begin{definition}...\end{definition}`（依赖 `amsthm`）
- Typst: `#definition[...]`（依赖 `ctheorems`）
- Slidev: 自动转换为带样式的 block

#### 4.2.5 算法 `::algorithm`

```markdown
::algorithm[Parallel Prefix Sum]{label: "alg:prefix-sum"}
::input[Array $A$ of length $n$]
::output[Array $B$ where $B[i] = \sum_{j=0}^i A[j]$]
1. Up-sweep: for $d = 0$ to $\log_2 n - 1$:
   - parallel for $i = 0$ to $n-1$ by $2^{d+1}$:
     - $A[i + 2^{d+1} - 1] \mathrel{+}= A[i + 2^d - 1]$
2. Down-sweep: ...
::end
```

#### 4.2.6 跨格式条件内容 `::if-format`

```markdown
::if-format[latex]
> 注意：在 LaTeX 中需要额外加载 `algorithmicx` 包。
::end

::if-format[slidev]
---
layout: center
---
# 本节核心观点
::end
```

### 4.3 现有语法的保留与增强

| 现有语法 | 在 Doc 模式下的行为 |
|---------|-------------------|
| `[[note.name]]` | 保留为内部链接；在 standalone 输出时根据策略转为 `\ref{}`、`<a>` 或忽略 |
| `![[note.name]]` | **核心机制**：嵌入其他笔记内容。若被嵌入笔记的 `doc.role=compose`，则提取其正文并递归解析；若为 `source`，则根据上下文决定是否内联或转为引用 |
| `![[note.name#heading]]` | 仅嵌入指定 heading 下的内容 |
| `^block-id` | 可作为 `::ref` 的目标，或转为 `\label`/`<a name="">` |
| `#tag` / `tags: []` | 保留；可用于自动组织文档结构（如收集所有带 `#experiment` 的笔记作为 experiments 章节） |
| Code blocks | 保留；支持 ` ```latex ` / ` ```typst ` 等语言标记用于原样输出 |

---

## 5. 编译管线设计

### 5.1 四阶段编译流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Phase 1    │     │  Phase 2    │     │  Phase 3    │     │  Phase 4    │
│  Profile    │ ──► │  Document   │ ──► │  AST        │ ──► │  Backend    │
│  Resolution │     │  Assembly   │     │  Transform  │     │  Codegen    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

#### Phase 1: Profile Resolution（画像解析）

输入：用户选定的根笔记（如 `project.bigs.paper.acmmm.md`）
输出：完整的 `DocProfile` 对象

流程：
1. 读取根笔记的 `doc.exports[]`，确定目标格式和模板
2. 若根笔记显式声明了 `doc.includes[]`，按列表收集笔记
3. 若未声明，通过**自动发现**收集：
   - 同 `project` 命名空间下所有 `doc.role=compose` 的笔记
   - 按 `doc.order` 排序
   - 通过 wikilink 关系图（backlinks / forward links）发现关联笔记
4. 收集所有被 `::cite` 引用的 `doc.role=bib` 笔记
5. 收集所有被 `::figure` 引用的 `doc.role=asset` 笔记

#### Phase 2: Document Assembly（文档组装）

输入：`DocProfile` + 笔记集合
输出：一颗完整的 Markdown AST（含 SailZen Doc 自定义节点）

流程：
1. 对每个 compose 笔记，解析其 Markdown 为 MDAST
2. 递归解析 `![[note]]` note ref，将引用替换为被引用笔记的 AST 子树
3. 处理 heading 层级：自动调整嵌入笔记的 heading depth，防止层级冲突
4. 合并所有片段为单一文档树
5. 注入根笔记的 `doc.meta` 作为全局变量上下文

#### Phase 3: AST Transform（AST 转换）

输入：组装后的 MDAST
输出：目标格式特定的 AST（或直接用 Stringifier）

流程（以 LaTeX 为例）：
1. 运行 Unified/Remark 插件管线：
   - `remark-sailzen-cite`：将 `::cite[]` 转为 `CiteNode`
   - `remark-sailzen-figure`：将 `::figure` 转为 `FigureNode`
   - `remark-sailzen-math-env`：将 `::theorem` 等转为 `MathEnvNode`
   - `remark-sailzen-note-refs`：复用现有 `noteRefsV2`，增强 doc 模式行为
2. 运行 `rehype` 或自定义 transformer，将特殊节点转为目标格式节点
3. 收集所有 `CiteNode`，生成参考文献数据库（`.bib`）

#### Phase 4: Backend Codegen（后端代码生成）

输入：转换后的 AST + Template
输出：目标格式的源文件 + 构建脚本

**LaTeX 后端**：
```
output/
├── main.tex              # 由模板 + 内容生成
├── sections/
│   ├── 01_introduction.tex
│   ├── 02_related_work.tex
│   ├── 03_method.tex
│   └── ...
├── figures/
│   └── (复制/链接的图片)
├── ref.bib               # 自动生成的 BibTeX
└── xmake.lua             # 自动生成的构建脚本（复用现有体系）
```

**Typst 后端**：
```
output/
├── main.typ
├── sections/
├── figures/
└── ref.bib
```

**Slidev 后端**：
```
output/
├── slides.md             # 所有幻灯片合并为一个 markdown
├── components/           # 自动提取的自定义组件
├── public/figures/
└── package.json          # 依赖声明
```

### 5.2 与现有 xmake 构建系统的整合

为了不破坏现有的 `doc/` 目录结构，编译输出采用**影子生成**模式：

```
vault/
├── notes/                    # 笔记源码（唯一真相）
│   └── project.bigs.paper.acmmm.md
├── doc/                      # 现有排版工程（保留兼容）
│   ├── doc/
│   ├── figures/
│   └── xmake.lua
└── .sailzen/                 # 编译输出缓存（gitignored）
    └── doc/
        └── project.bigs/
            ├── latex-acmmm/   # LaTeX 产物
            ├── typst/         # Typst 产物
            └── slidev/        # Slidev 产物
```

**增量编译策略**：
- 以笔记的 `updated` 时间戳和 `contentHash` 作为缓存键
- 仅当依赖的笔记或模板发生变更时才重新生成
- 生成的 `.tex`/`.typ` 文件保留可读性，便于调试

---

## 6. 模板系统设计

### 6.1 模板结构

每个模板是一个目录，包含格式特定的骨架文件：

```
.templates/latex/acmart-sigconf/
├── template.yml            # 模板元数据
├── main.tex.hbs            # Handlebars / 自定义模板引擎
├── preamble.tex.hbs
├── sections/               # 章节模板片段
│   ├── abstract.tex.hbs
│   └── section.tex.hbs
└── assets/
    └── acmart.cls          # 必要依赖
```

`template.yml` 示例：
```yaml
name: acmart-sigconf
format: latex
description: ACM Conference Paper (sigconf)
engine: pdflatex           # pdflatex | xelatex | lualatex
requires:
  - acmart.cls
variables:
  - name: title
    required: true
  - name: authors
    type: array
  - name: abstract
    type: string
  - name: bibliography
    default: "ref"
  - name: documentclass_options
    default: "[sigconf,authordraft]"
sectioning:
  style: numbered          # numbered | unnumbered | chapter
  maxDepth: 3
```

### 6.2 模板变量注入

模板引擎从以下来源收集变量：
1. 根笔记 `doc.meta.*`
2. 根笔记 frontmatter 标准字段（`title`, `desc` 映射为 `abstract`）
3. 编译时动态计算（如 `\today`, 参考文献计数等）

### 6.3 内置模板库

| 模板 ID | 格式 | 说明 |
|--------|------|------|
| `acmart-sigconf` | LaTeX | ACM 会议论文 |
| `acmart-sigplan` | LaTeX | ACM SIGPLAN |
| `cvpr` | LaTeX | CVPR 论文 |
| `iccv` | LaTeX | ICCV 论文 |
| `icml` | LaTeX | ICML 论文 |
| `njuthesis` | LaTeX | 南京大学学位论文 |
| `njupre` | LaTeX | 南大预印本 |
| `arxiv` | LaTeX | arXiv 通用模板 |
| `research-article` | Typst | 通用研究文章 |
| `ctez-book` | Typst | 中文书籍（复用现有 ctez 尝试）|
| `slidev-default` | Slidev | 默认幻灯片 |
| `slidev-nju-defense` | Slidev | 南大答辩幻灯片 |

---

## 7. VSCode 插件集成

### 7.1 新增命令

| 命令 | 快捷键 | 行为 |
|------|--------|------|
| `SailZen: Export Note to LaTeX` | - | 为当前笔记生成 LaTeX，选择模板 |
| `SailZen: Export Note to Typst` | - | 生成 Typst |
| `SailZen: Export Note to Slidev` | - | 生成 Slidev 幻灯片 |
| `SailZen: Open Doc Preview` | `Ctrl+Shift+D` | 打开 Doc 模式预览面板 |
| `SailZen: Compile Project` | - | 编译当前项目的所有导出配置 |
| `SailZen: Sync Bibliography` | - | 同步笔记文献到 `.bib` 文件 |
| `SailZen: New Document Project` | - | 向导式创建新的文档项目 |

### 7.2 状态栏与装饰

- **状态栏**：当打开具有 `doc` frontmatter 的笔记时，显示当前 `doc.role` 和目标格式图标（如 `📄 LaTeX`）
- **面包屑**：在编辑器顶部显示该笔记在文档项目中的位置（如 `project.bigs > paper > method`）
- **边栏装饰**：在文件树中，属于某个文档项目的笔记显示特殊图标/颜色

### 7.3 Doc 模式预览

新增 `DendronASTDest.DOC_PREVIEW` 目标：

```typescript
// 在现有 preview pipeline 中新增一个分支
if (dest === DendronASTDest.DOC_PREVIEW) {
  // 1. 执行 Profile Resolution（缓存结果）
  // 2. 执行 Document Assembly（仅当前笔记及其直接引用）
  // 3. 使用轻量级 renderer 显示近似排版效果
  //    - ::cite 显示为 [1,2,3] 上标
  //    - ::figure 显示为占位图 + 题注
  //    - ::theorem 显示为带框的 block
  // 4. 不执行完整后端编译，保持实时响应
}
```

预览面板支持切换目标格式（LaTeX / Typst / Slidev），以便用户预览不同后端的渲染差异。

### 7.4 诊断与错误定位

- 若 `::cite[key]` 中的 `key` 找不到对应笔记 → 红色波浪线 + Quick Fix "Create Bib Note"
- 若 `::figure[src]` 找不到图片 → 黄色警告
- 若模板变量缺失（如 `doc.meta.authors` 未定义）→ 信息提示
- 后端编译错误（如 LaTeX 编译失败）→ 解析错误日志，映射回笔记行号

---

## 8. 项目组织最佳实践

### 8.1 推荐目录约定

```
notes/
├── project.<name>.doc.<format>.md       # 文档根节点（standalone）
│   # 例: project.bigs.paper.acmmm.md
├── project.<name>.content.<section>.md  # 章节笔记（compose）
│   # 例: project.bigs.content.introduction.md
│   # 例: project.bigs.content.method.md
├── project.<name>.fig.<name>.md         # 图片资源（asset）
│   # 例: project.bigs.fig.teaser.md
├── project.<name>.tab.<name>.md         # 表格资源（asset）
│   # 例: project.bigs.tab.comparison.md
├── project.<name>.bib.<key>.md          # 文献条目（bib）
│   # 例: project.bigs.bigs.instant-ngp.md
│   # （也可直接引用 source.papers.* 下的笔记）
└── project.<name>.slide.<section>.md    # 幻灯片页面（compose）
    # 例: project.bigs.slide.background.md
```

### 8.2 从现有 doc/ 迁移的路径

**阶段 1：并行运行（不破坏现有流程）**
- 在 `notes/` 中创建对应的 `project.*.content.*.md`
- 使用 `![[project.*.content.*]]` 在 doc 根笔记中引用
- 继续使用现有 `doc/` 目录编译，但内容逐步迁移到笔记

**阶段 2：单源验证**
- 从笔记生成 `.tex` 到 `.sailzen/doc/`
- 对比生成结果与手写的 `doc/doc/content/` 文件
- 调整模板和语法直至输出一致

**阶段 3：完全切换**
- 删除 `doc/doc/content/` 中的重复 `.tex` 文件
- `doc/` 仅保留模板、样式、xmake 构建脚本
- 构建流程改为：笔记 → `.sailzen/doc/` → xmake → PDF

### 8.3 文献管理整合

现有 `source.papers.*` 笔记可以**渐进式**增加 `doc.role: bib` 和 `doc.bibtex` 字段：

```yaml
---
# 这是现有的文献阅读笔记，只需新增 doc 字段
title: "3D Gaussian Splatting for Real-Time Radiance Field Rendering"
doc:
  role: bib
  bibtex:
    type: article
    key: gaussian-splatting-original
    fields:
      author: "Bernhard Kerbl et al."
      title: "3D Gaussian Splatting for Real-Time Radiance Field Rendering"
      journal: "ACM TOG"
      year: 2023
      volume: 42
      number: 4
---

## 笔记正文（阅读批注、摘要、评论）
...
```

优势：
- 文献笔记的**阅读批注**和**引用信息**统一在一处
- 编译时自动从所有被引用的文献笔记中提取 `.bib`
- 支持从外部 `.bib` 文件**反向导入**为文献笔记（一次性迁移工具）

---

## 9. 与 SailZen 3.0 的协同

### 9.1 利用现有基础设施

| 现有组件 | 在 NoteDoc 中的复用 |
|---------|-------------------|
| `DendronEngineV3` | Note 查询、链接解析、graph 构建 |
| `unified` + `remark` | AST 处理管线，插入 SailZen Doc 插件 |
| `NoteProps.custom` | 承载 `doc` frontmatter 扩展 |
| `ProcFlavor` / `ProcMode` | 新增 `DOC_EXPORT` / `DOC_PREVIEW` 模式 |
| `xmake` 构建系统 | 后端编译 orchestration |
| `PreviewPanel` | 扩展为支持 Doc 模式预览 |

### 9.2 后端（Python）可扩展点

未来 SailZen 3.0 的 Python 后端可作为**集中式编译服务**：

```
VSCode Plugin ──► sail_server API
                    ├── POST /api/v1/doc/compile
                    │     Input: { rootNoteId, format, template }
                    │     Output: { jobId, status, artifacts[] }
                    ├── GET  /api/v1/doc/template/list
                    └── GET  /api/v1/doc/bib/generate
```

这将支持：
- 在服务器端执行重型编译（如完整 LaTeX 编译链）
- CI/CD 集成：提交笔记后自动生成论文 PDF
- 多用户协作：共享模板和文献库

---

## 10. 非目标与边界

以下功能**明确不在本设计范围内**，留待后续迭代：

1. **WYSIWYG 编辑器**：保持 Markdown 纯文本编辑，不做可视化排版编辑。
2. **非学术文档**：如简历、信件等简单格式，优先通过 Typst/Markdown 原生处理。
3. **协作排版**：多人同时编辑同一文档的实时冲突解决（沿用 Git 工作流）。
4. **图片自动生成**：如从数据脚本生成图表，属于外部工具链职责，NoteDoc 只负责引用已有图片资源。
5. **多语言混排引擎**：如中文竖排、从右至左等复杂排版，依赖底层 LaTeX/Typst 模板支持。

---

## 11. 演进路线图

| 阶段 | 周期 | 目标 |
|------|------|------|
| **M1: 语法冻结** | 1 周 | 确定 frontmatter 扩展、`::` 指令语法、模板元数据格式 |
| **M2: 核心管线** | 2 周 | 实现 Profile Resolution → Document Assembly → AST Transform（不绑定后端）|
| **M3: LaTeX 后端** | 2 周 | 实现 LaTeX Codegen，支持 `acmart-sigconf` 和 `njuthesis`，验证可生成现有论文 |
| **M4: VSCode 集成** | 1 周 | 命令面板、Doc Preview、状态栏、诊断 |
| **M5: Typst + Slidev** | 2 周 | 新增 Typst 和 Slidev 后端，复用 M2 管线 |
| **M6: 迁移与模板库** | 2 周 | 将现有 `doc/` 内容迁移为笔记，完善内置模板库 |
| **M7: 后端服务化** | 后续 | 接入 SailZen 3.0 Python 后端，支持远程编译 |

---

## 12. 附录

### A. 完整示例：从笔记生成 ACMMM 论文

**Step 1: 文献笔记**（新增 `doc` 字段）

```markdown
---
title: "Instant Neural Graphics Primitives"
doc:
  role: bib
  bibtex:
    type: article
    key: instant-ngp
    fields:
      author: "Thomas M{\"u}ller et al."
      title: "Instant Neural Graphics Primitives with a Multiresolution Hash Encoding"
      journal: "ACM TOG"
      year: 2022
---

# Instant NGP

## 核心思想
使用多分辨率哈希编码 + 小型 MLP...
```

**Step 2: 章节笔记**

```markdown
---
title: Introduction
doc:
  role: compose
  project: project.bigs
  order: 1
---

Novel view synthesis has achieved remarkable progress since the advent of NeRF ::cite[ nerf-original ].
However, training speed remains a bottleneck. Instant-NGP ::cite[ instant-ngp ] proposes...
```

**Step 3: 根文档笔记**

```markdown
---
title: "BIGS: Bayesian Inference Gaussian Splatting"
doc:
  role: standalone
  project: project.bigs
  exports:
    - format: latex
      template: acmart-sigconf
      vars:
        documentclass: "[sigconf,authordraft]{acmart}"
        bibliography: ref
---

![[project.bigs.content.abstract]]

![[project.bigs.content.introduction]]

![[project.bigs.content.related-work]]

![[project.bigs.content.method]]

![[project.bigs.content.experiments]]

![[project.bigs.content.conclusion]]
```

**Step 4: 一键导出**

在 VSCode 中打开 `project.bigs.paper.acmmm.md`，执行 `SailZen: Export Note to LaTeX`：

```
.sailzen/doc/project.bigs/latex-acmmm/
├── main.tex
├── sections/
│   ├── 00_abstract.tex
│   ├── 01_introduction.tex
│   ├── 02_related_work.tex
│   ├── 03_method.tex
│   ├── 04_experiments.tex
│   └── 05_conclusion.tex
├── figures/
│   └── fig_bigs_teaser.pdf
└── ref.bib
```

运行 `xmake` 即可编译出与手写版本一致的 `main.pdf`。

---

### B. 术语表

| 术语 | 定义 |
|------|------|
| **Doc Profile** | 描述一个输出项目的完整元数据配置，包括模板、格式、变量等。 |
| **Note Role** | 笔记在文档系统中的角色定位：`source`/`compose`/`standalone`/`asset`/`bib`。 |
| **SailZen Doc Syntax** | 基于 `::` 前缀的 Markdown 扩展指令集，用于表达排版语义。 |
| **Document Assembly** | 将多个 compose 笔记通过 note ref 组装为单一文档树的过程。 |
| **Shadow Generation** | 编译输出到 `.sailzen/` 目录，不污染原始笔记和 doc/ 目录的策略。 |
| **Template Variable Injection** | 将笔记 frontmatter 中的元数据注入模板占位符的过程。 |
