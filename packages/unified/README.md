# Unified Framework

## Function
# Unified Package Functional Status

> Package: `@saili/unified` v0.3.7
> Last updated: 2026-02

## Overview

The `unified` package provides remark/rehype plugins that extend standard Markdown with Dendron-specific and SailZen-specific syntax. It sits between raw markdown text and rendered HTML, handling parsing, AST transformation, and compilation for multiple output destinations.

## Architecture

```
Raw Markdown
    |
    v
[remark-parse] + custom tokenizers  -->  MDAST (custom nodes)
    |
    v
[remark plugins] transform AST
    |
    v
[remark-rehype] + [rehype plugins]  -->  HAST (HTML AST)
    |
    v
[rehype-stringify]                  -->  HTML / Markdown / Other
```

**Key processor factories:**
- `MDUtilsV5.procRehypeFull()` — Server-side full pipeline (HTML output)
- `MDUtilsV5Web.procRehypeWeb()` — Browser-compatible pipeline
- `MDUtilsV5.procRemarkFull()` — Internal remark-only pipeline (used by noteRefsV2)

## Custom AST Node Types

Defined in `src/types.ts` as `DendronASTTypes`:

| Type String | TypeScript Interface | Purpose |
|-------------|---------------------|---------|
| `wikiLink` | `WikiLinkNoteV4` | `[[target]]`, `[[alias\|target]]` cross-references |
| `refLinkV2` | `NoteRefNoteV4` | `![[note-ref]]` transclusion |
| `blockAnchor` | `BlockAnchor` | `^anchor` block references |
| `hashtag` | `HashTag` | `#tag` topic tags |
| `zdoctag` | `ZDocTag` | `\cite{key}` zdoc citations |
| `extendedImage` | `ExtendedImage` | `![alt](url){props}` images with YAML props |
| `sailzenCite` | `SailZenCite` | `::cite[key1, key2]` inline citations |
| `sailzenFigure` | `SailZenFigure` | `::figure[caption](src){opts}` figures |
| `sailzenTable` | — | Table directive (registered type, implementation TBD) |
| `sailzenMathEnv` | — | Math environment (registered type, implementation TBD) |
| `sailzenAlgorithm` | — | Algorithm block (registered type, implementation TBD) |
| `sailzenIfFormat` | — | Conditional format (registered type, implementation TBD) |

## Plugin Inventory

### Remark Plugins (`src/remark/`)

| Plugin | Syntax | Status | Tests | Notes |
|--------|--------|--------|-------|-------|
| `wikiLinks` | `[[target]]` | ✅ Active | ✅ | Dual implementation: legacy tokenizer + micromark extension |
| `hashtag` | `#tag` | ✅ Active | ✅ | Config-gated (`enableHashTags`) |
| `zdocTags` | `\cite{key}` | ✅ Active | ✅ | Config-gated (`enableZDocTags`) |
| `blockAnchors` | `^anchor` | ✅ Active | ✅ | **Bug in `matchBlockAnchor`**: checks `match.length == 1` but regex always produces `length >= 2`, so function always returns `undefined` |
| `noteRefsV2` | `![[ref]]` | ✅ Active | ❌ | Most complex plugin: transclusion, anchor ranges, wildcards, pretty refs, `MAX_REF_LVL = 3` nesting limit |
| `extendedImage` | `![alt](url){props}` | ✅ Active | ❌ | Parses YAML props via `js-yaml`; falls back to regular image on parse failure |
| `sailzenCite` | `::cite[keys]` | ✅ Active | ❌ | Splits keys on comma; renders `<sup>[keys]</sup>` for HTML |
| `sailzenFigure` | `::figure[cap](src){opts}` | ✅ Active | ❌ | Parses `key="value"` / `key=value` options |
| `backlinks` | — | ✅ Active | ❌ | Injects backlink sections into notes |
| `hierarchies` | — | ✅ Active | ❌ | Handles note hierarchy metadata |
| `dendronPub` | — | ✅ Active | ❌ | Publication-ready transformations |
| `dendronPreview` | — | ✅ Active | ❌ | Preview-specific transformations |
| `transformLinks` | — | ✅ Active | ❌ | Link transformation utilities |
| `abbr` | — | ✅ Active | ❌ | Abbreviation support |
| `publishSite` | — | ✅ Active | ❌ | Site publication logic |

### Rehype Plugins (`src/rehype/`)

| Plugin | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `wrap` | Wrap HAST elements matching selector | ✅ Active | ✅ |
| *(others)* | Various HTML transformations | ✅ Active | ❌ |

### Decoration Modules (`src/decorations/`)

All 10 modules are **untested**. They provide editor decorations (VSCode) rather than rendering:

| Module | Decorates |
|--------|-----------|
| `decorations.ts` | Dispatcher/router |
| `wikilinks.ts` | Wiki link underlines/highlights |
| `hashTags.ts` | Hashtag highlights |
| `blockAnchors.ts` | Block anchor indicators |
| `zdocTags.ts` | ZDoc tag highlights |
| `references.ts` | Reference indicators |
| `taskNotes.ts` | Task note markers |
| `frontmatter.ts` | Frontmatter folding |
| `diagnostics.ts` | Error/warning squiggles |
| `utils.ts` | Shared decoration utilities |

## Compiler Destinations

All custom plugins switch on `DendronASTDest`:

| Destination | Purpose |
|-------------|---------|
| `MD_DENDRON` | Round-trip markdown (preserve custom syntax) |
| `MD_REGULAR` | Standard markdown (strip custom syntax) |
| `MD_ENHANCED_PREVIEW` | Enhanced markdown preview |
| `HTML` | Full HTML rendering |
| `DOC_EXPORT` | Document export backend placeholder |
| `DOC_PREVIEW` | Document preview mode |

## External Plugins Integrated

| Plugin | Purpose |
|--------|---------|
| `remark-gfm` | GitHub Flavored Markdown (tables, strikethrough, etc.) |
| `remark-math` | `$...$` and `$$...$$` math syntax |
| `rehype-katex` | KaTeX math rendering |
| `rehype-prism` | Syntax highlighting via Prism |
| `remark-frontmatter` | YAML frontmatter parsing |
| `rehype-slug` | Auto-generate heading IDs |
| `rehype-autolink-headings` | Auto-link headings |
| `rehype-raw` | Parse raw HTML in markdown |

## Test Coverage Summary

### Tested Plugins
- `hashtag` — regex, utils, full processor
- `wikiLinks` — regex, utils, full processor
- `zdocTags` — regex, utils, full processor
- `blockAnchors` — regex, utils, full processor *(new)*
- `wrap` (rehype) — selector wrapping

### Untested Plugins (Priority Order)
1. **High**: `noteRefsV2` — complex transclusion logic, anchor slicing, wildcard resolution
2. **Medium**: `extendedImage`, `sailzenCite`, `sailzenFigure` — standard tokenizer/compiler pattern
3. **Medium**: `backlinks`, `hierarchies` — metadata injection
4. **Low**: `dendronPub`, `dendronPreview`, `transformLinks`, `abbr`, `publishSite`
5. **Low**: All `decorations/` modules (VSCode-specific, harder to test headlessly)


## Testing 


## 测试框架配置

### Jest 配置

测试框架使用 Jest 和 ts-jest，配置在 `jest.config.mjs` 中：

- **环境**: Node.js (ESM 模块)
- **预设**: `ts-jest/presets/default-esm`
- **测试匹配**: `**/src/**/*.test.ts` 和 `**/src/**/__tests__/**/*.ts`
- **覆盖率**: 收集所有 `.ts` 文件的覆盖率，排除测试文件和类型定义文件

### 测试脚本

在 `package.json` 中定义了以下测试脚本：

```json
{
  "scripts": {
    "test": "运行所有测试",
    "test:watch": "监视模式运行测试",
    "test:coverage": "运行测试并生成覆盖率报告",
    "coverage": "test:coverage 的别名"
  }
}
```

## 测试工具和 Fixtures

### Fixtures (`__tests__/fixtures/testNotes.ts`)

提供创建测试用的 `NoteProps` 对象的工具函数：

- `createTestVault()` - 创建测试用的 vault
- `createTestConfig()` - 创建测试用的配置
- `createTestNote()` - 创建基本的测试 note
- `createTestNoteWithBody()` - 创建带内容的测试 note
- `createTestNoteWithWikiLinks()` - 创建带 wiki links 的测试 note
- `createTestNoteWithHashtags()` - 创建带 hashtags 的测试 note
- `createTestNoteWithFrontmatter()` - 创建带 frontmatter 的测试 note

### 测试辅助函数 (`__tests__/utils/testHelpers.ts`)

提供测试中常用的工具函数：

- `createTestProcessor()` - 创建基础的 remark processor
- `processMarkdownToAST()` - 处理 markdown 并返回 AST
- `processMarkdownToString()` - 处理 markdown 并返回字符串
- `createFullTestProcessor()` - 创建完整的 Dendron processor
- `processNoteFull()` - 使用完整 processor 处理 note
- `expectContains()` / `expectNotContains()` - 字符串包含断言
- `expectMatches()` / `expectNotMatches()` - 正则匹配断言

## 编写测试

### 基本测试结构

```typescript
import { remark } from "remark";
import remarkParse from "remark-parse";
import { yourPlugin } from "../yourPlugin";
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("yourPlugin", () => {
  describe("基本功能", () => {
    test("should do something", async () => {
      // 测试代码
    });
  });
});
```

### 测试 Remark 插件

1. **测试正则表达式**（如果有）：
```typescript
describe("REGEX", () => {
  test("should match pattern", () => {
    const match = YOUR_REGEX.exec("input");
    expect(match).not.toBeNull();
  });
});
```

2. **测试插件解析**：
```typescript
test("should parse markdown", async () => {
  const processor = remark()
    .use(remarkParse)
    .use(yourPlugin);

  const result = await processor.process("input");
  const ast = result.result as any;
  
  // 验证 AST
});
```

3. **测试完整处理流程**：
```typescript
test("should render in HTML", async () => {
  const note = createTestNoteWithBody("input");
  const html = await processNoteFull(note);
  expect(html).toContain("expected");
});
```

### 测试 Rehype 插件

```typescript
import { remark } from "remark";
import remarkParse from "remark-parse";
import remarkRehype from "remark-rehype";
import rehypeStringify from "rehype-stringify";
import { yourRehypePlugin } from "../yourRehypePlugin";

test("should transform HTML", async () => {
  const processor = remark()
    .use(remarkParse)
    .use(remarkRehype)
    .use(yourRehypePlugin)
    .use(rehypeStringify);

  const result = await processor.process("input");
  const html = result.toString();
  
  expect(html).toContain("expected");
});
```

### 测试工具函数

```typescript
import { YourUtils } from "../yourUtils";

describe("YourUtils", () => {
  describe("methodName", () => {
    test("should handle normal case", () => {
      const result = YourUtils.methodName("input");
      expect(result).toBe("expected");
    });

    test("should handle edge case", () => {
      const result = YourUtils.methodName("");
      expect(result).toBeDefined();
    });
  });
});
```

## 测试最佳实践

### 1. 测试组织

- 使用 `describe` 块组织相关测试
- 每个测试文件对应一个源文件
- 测试文件放在 `__tests__` 目录或与源文件同级

### 2. 测试命名

- 测试描述应该清晰说明测试的内容
- 使用 "should ..." 格式描述预期行为
- 分组测试使用嵌套的 `describe` 块

### 3. 测试覆盖

优先测试：
- 核心功能和主要用例
- 边界情况和错误处理
- 正则表达式匹配（如果有）
- 插件集成和端到端流程

### 4. 使用 Fixtures

- 使用 `createTestNote*` 函数创建测试数据
- 避免硬编码测试数据
- 复用 fixtures 以提高一致性

### 5. 异步测试

- 使用 `async/await` 处理异步操作
- 确保所有异步操作完成后再断言

### 6. AST 遍历辅助函数

对于需要遍历 AST 的测试，可以使用以下辅助函数：

```typescript
function findNodeByType(node: any, type: string): any {
  if (node.type === type) {
    return node;
  }
  if (node.children) {
    for (const child of node.children) {
      const found = findNodeByType(child, type);
      if (found) return found;
    }
  }
  return undefined;
}

function findAllNodesByType(node: any, type: string): any[] {
  const results: any[] = [];
  if (node.type === type) {
    results.push(node);
  }
  if (node.children) {
    for (const child of node.children) {
      results.push(...findAllNodesByType(child, type));
    }
  }
  return results;
}
```

## 运行测试

### 运行所有测试

```bash
pnpm test
```

### 监视模式

```bash
pnpm test:watch
```

### 生成覆盖率报告

```bash
pnpm test:coverage
```

覆盖率报告会生成在 `coverage/` 目录中，包括：
- `coverage/lcov-report/index.html` - HTML 报告
- `coverage/lcov.info` - LCOV 格式报告

## 覆盖率目标

当前覆盖率阈值设置为 10%（在 `jest.config.mjs` 中），这是初始值。随着测试的增加，建议逐步提高阈值：

- 短期目标：30%
- 中期目标：60%
- 长期目标：80%+

## 维护指南

### 添加新功能时

1. **编写测试**：为新功能编写测试，遵循现有测试模式
2. **运行测试**：确保所有测试通过
3. **检查覆盖率**：确保新代码被测试覆盖

### 修复 Bug 时

1. **编写回归测试**：先编写一个失败的测试来重现 bug
2. **修复代码**：修复 bug 使测试通过
3. **验证**：确保没有破坏其他测试

### 重构时

1. **确保测试通过**：重构前确保所有测试通过
2. **更新测试**：如果 API 改变，更新相应测试
3. **保持覆盖率**：确保重构后覆盖率不下降

### 更新依赖时

1. **运行测试**：确保新版本兼容
2. **更新测试**：如果 API 改变，更新测试代码
3. **检查破坏性变更**：查看依赖的 changelog

## 常见问题

### Q: 测试在 ESM 模式下失败？

A: 确保使用正确的 Jest 配置和 Node.js 选项。检查 `jest.config.mjs` 和 `package.json` 中的脚本。

### Q: 如何测试私有函数？

A: 优先测试公共 API。如果必须测试私有函数，可以考虑：
1. 将它们导出（仅用于测试）
2. 通过公共 API 间接测试

### Q: 如何处理异步错误？

A: 使用 `expect().rejects` 或 `try/catch` 配合 `await`：

```typescript
test("should throw error", async () => {
  await expect(asyncFunction()).rejects.toThrow();
});
```

### Q: 如何模拟外部依赖？

A: 使用 Jest 的 mock 功能：

```typescript
jest.mock("../dependency", () => ({
  dependencyFunction: jest.fn(),
}));
```

## 参考资源

- [Jest 文档](https://jestjs.io/docs/getting-started)
- [ts-jest 文档](https://kulshekhar.github.io/ts-jest/)
- [Unified 文档](https://unifiedjs.com/)
- [Remark 文档](https://remark.js.org/)
- [Rehype 文档](https://github.com/rehypejs/rehype)

## 贡献指南

在添加新测试时，请：

1. 遵循现有的测试模式和结构
2. 使用提供的 fixtures 和工具函数
3. 确保测试描述清晰
4. 运行 `pnpm test` 确保所有测试通过
5. 检查覆盖率报告，确保新代码被覆盖

## 更新日志

- **2025-01-XX**: 初始测试框架搭建
  - 创建测试目录结构
  - 添加 fixtures 和测试工具
  - 编写核心插件测试
  - 撰写测试文档


## 1. Package Architecture Overview

```
packages/unified/src/
├── remark/          # Custom Markdown syntax parsers (MDAST extensions)
├── rehype/          # HTML transformation plugins (HAST transforms)
├── decorations/     # Editor decoration providers (VS Code style)
├── types.ts         # AST node types & DendronASTTypes enum
├── utilsv5.ts       # Server-side processor factory (MDUtilsV5)
├── utilsWeb.ts      # Browser-side processor factory (MDUtilsV5Web)
├── __tests__/       # Test suites & fixtures
└── remark/__tests__/# Plugin-level unit tests
```

### Processing Pipeline

```
Markdown Input
    ↓
remark-parse (CommonMark)
    ↓
remark plugins (custom tokenizers) → MDAST with DendronASTTypes nodes
    ↓
remark-rehype
    ↓
rehype plugins (HTML transforms) → HAST
    ↓
rehype-stringify → HTML Output
```

**Processor Factories:**
- `MDUtilsV5.procRehypeFull()` — Server-side, full pipeline (used in tests via `processNoteFull()`)
- `MDUtilsV5Web.procRehypeWeb()` — Browser-side, for preview builds

---

## 2. Functional Status: Remark Plugins

| Plugin | File | Status | Tests | Description |
|--------|------|--------|-------|-------------|
| `wikiLinks` | `remark/wikiLinks.ts` | ✅ Active | ✅ `wikiLinks.test.ts` | `[[target]]`, `[[alias\|target]]`, `[[target#anchor]]` wiki-style links. Uses micromark tokenization. |
| `hashtags` | `remark/hashtag.ts` | ✅ Active | ✅ `hashtag.test.ts` | `#tag` tags, shorthand for `[[tags.tag]]`. Regex-based tokenizer. |
| `zdocTags` | `remark/zdocTags.ts` | ✅ Active | ✅ `zdocTags.test.ts` + `tag.test.ts` | `\cite{key}` ZDoc citations. Requires `enableZDocTags` config. |
| `blockAnchors` | `remark/blockAnchors.ts` | ✅ Active | ❌ None | `^anchor-id` block references. Used by noteRefs for range selection. |
| `noteRefsV2` | `remark/noteRefsV2.ts` | ✅ Active | ❌ None | `![[note-ref]]` transclusion. Complex: wildcard refs, anchor ranges, pretty refs, nesting limit. |
| `extendedImage` | `remark/extendedImage.ts` | ✅ Active | ❌ None | `![alt](url){props}` images with YAML props. Falls back to regular image on bad props. |
| `sailzenCite` | `remark/sailzenCite.ts` | ✅ Active | ❌ None | `::cite[foo, bar]` inline citations. Multi-dest rendering (MD/HTML/DOC). |
| `sailzenFigure` | `remark/sailzenFigure.ts` | ✅ Active | ❌ None | `::figure[caption](src){opts}` figure directives. Option parser for key=value pairs. |
| `abbr` | `remark/abbr.ts` | ✅ Active | ❌ None | Abbreviation expansion plugin. |
| `dendronPub` | `remark/dendronPub.ts` | ✅ Active | ❌ None | Publishing-time link resolution & note ref HAST conversion. |
| `dendronPreview` | `remark/dendronPreview.ts` | ✅ Active | ❌ None | Preview-mode link resolution. |
| `transformLinks` | `remark/transformLinks.ts` | ✅ Active | ❌ None | Link transformation utilities. |
| `backlinks` | `remark/backlinks.ts` | ✅ Active | ❌ None | Backlink injection during processing. |
| `backlinksHover` | `remark/backlinksHover.ts` | ✅ Active | ❌ None | Hover preview for backlinks. |
| `hierarchies` | `remark/hierarchies.ts` | ✅ Active | ❌ None | Hierarchy-aware processing. |
| `publishSite` | `remark/publishSite.ts` | ✅ Active | ❌ None | Site publishing helpers. |

### Remark Plugin Pattern

All remark plugins follow the same structure:

```ts
const plugin: Plugin<[PluginOpts?]> = function (this: Processor, _opts?) {
  attachParser(this);      // Register tokenizer + locator
  if (this.Compiler != null) {
    attachCompiler(this);  // Register AST-to-target visitor
  }
};
```

**Parser attachment:**
1. `locator(value, fromIndex)` — Returns index of syntax start
2. `inlineTokenizer(eat, value)` — Regex match + `eat(match[0])(node)`
3. Register in `Parser.prototype.inlineTokenizers` and `inlineMethods`

**Compiler attachment:**
1. Register visitor in `Compiler.prototype.visitors[DendronASTTypes.X]`
2. Switch on `DendronASTDest` (MD_DENDRON / MD_REGULAR / HTML / DOC_EXPORT / DOC_PREVIEW)

---

## 3. Functional Status: Rehype Plugins

| Plugin | File | Status | Tests | Description |
|--------|------|--------|-------|-------------|
| `wrap` | `rehype/wrap.ts` | ✅ Active | ✅ `wrap.test.ts` | Wraps HAST nodes matching a CSS selector in a wrapper element. |
| `mermaid-noop` | `rehype/mermaid-noop.ts` | ✅ Active | ❌ None | No-op placeholder for mermaid diagrams (avoids playwright dep). |

---

## 4. Functional Status: Decorations

Decorations analyze parsed AST to produce IDE highlighting (ranges + types). They do **not** generate HTML.

| Decoration | File | Status | Tests | Description |
|------------|------|--------|-------|-------------|
| `wikiLinks` | `decorations/wikilinks.ts` | ✅ Active | ❌ None | Highlight wiki link ranges. |
| `hashTags` | `decorations/hashTags.ts` | ✅ Active | ❌ None | Highlight hashtag ranges. |
| `zdocTags` | `decorations/zdocTags.ts` | ✅ Active | ❌ None | Highlight ZDoc tag ranges. |
| `blockAnchors` | `decorations/blockAnchors.ts` | ✅ Active | ❌ None | Highlight block anchor ranges. |
| `references` | `decorations/references.ts` | ✅ Active | ❌ None | Highlight note reference ranges. |
| `frontmatter` | `decorations/frontmatter.ts` | ✅ Active | ❌ None | Frontmatter region decoration. |
| `taskNotes` | `decorations/taskNotes.ts` | ✅ Active | ❌ None | Task note decorations. |
| `diagnostics` | `decorations/diagnostics.ts` | ✅ Active | ❌ None | Diagnostic warnings (bad frontmatter, etc.). |
| `decorations.ts` | `decorations/decorations.ts` | ✅ Active | ❌ None | Dispatcher: `runDecorator()` + `runAllDecorators()`. |

---

## 5. Test Coverage Matrix

### Existing Tests

| Test File | What It Tests | Approach |
|-----------|---------------|----------|
| `mdutilsv5.test.ts` | Full `procRehypeFull` pipeline | Integration: note → processor → HTML string assertions |
| `utilsWeb.test.ts` | Full `procRehypeWeb` pipeline | Integration: note → processor → HTML string assertions |
| `utils.test.ts` | Utility functions | Unit tests |
| `hello.test.ts` | Sanity check | Smoke test |
| `remark/__tests__/wikiLinks.test.ts` | Wiki link regex + utils + full processor | Regex unit + integration via `processNoteFull()` |
| `remark/__tests__/hashtag.test.ts` | Hashtag regex + utils + full processor | Regex unit + integration |
| `remark/__tests__/zdocTags.test.ts` | ZDoc tag regex + utils + full processor | Regex unit + integration |
| `remark/__tests__/tag.test.ts` | ZDoc regex edge cases | Regex unit |
| `rehype/__tests__/wrap.test.ts` | `wrap` plugin | HAST transform test |

### Coverage Gaps (Priority Order)

| Module | Priority | Why | Suggested Test Approach |
|--------|----------|-----|------------------------|
| `sailzenCite` | **High** | Custom syntax, multi-dest rendering | Regex + AST node creation + HTML output per dest |
| `sailzenFigure` | **High** | Custom syntax, option parser | Regex + option parsing + HTML/MD round-trip |
| `blockAnchors` | **High** | Core feature, noteRefs dependency | Regex + block anchor node + MD_DENDRON round-trip |
| `extendedImage` | **Medium** | Custom syntax, YAML props | Regex + props parsing + HTML rendering |
| `noteRefsV2` | **Medium** | Complex but critical | Mock `noteCacheForRenderDict`, test basic transclusion |
| `decorations/*` | **Medium** | All 8 decorators untested | AST → decoration range assertions |
| `dendronPub` | **Low** | Publishing logic | Integration with mock engine |
| `backlinks` | **Low** | Backlink injection | Mock engine + assert backlinks in output |
| `hierarchies` | **Low** | Hierarchy processing | TBD based on usage |

---

## 6. How to Test Custom Markdown Annotation Syntax

This section formalizes the testing pattern used by `wikiLinks`, `hashtag`, and `zdocTags`.

### Pattern A: Regex & Utils (Fast, Isolated)

Test the regex patterns and utility functions directly without a processor.

```ts
// src/remark/__tests__/sailzenCite.test.ts
import { CITE_REGEX, sailzenCite } from "../sailzenCite";

describe("sailzenCite regex", () => {
  test("should match basic cite", () => {
    const match = CITE_REGEX.exec("::cite[foo, bar]");
    expect(match).not.toBeNull();
    expect(match?.[1]).toBe("foo, bar");
  });

  test("should not match without keys", () => {
    expect(CITE_REGEX.exec("::cite[]")).toBeNull();
  });
});
```

### Pattern B: AST Node Creation (Plugin Isolation)

Build a minimal pipeline to verify the plugin creates the correct AST node.

```ts
import { remark } from "remark";
import remarkParse from "remark-parse";
import { sailzenCite } from "../sailzenCite";
import { DendronASTTypes } from "../../types";

describe("sailzenCite AST", () => {
  test("should create sailzenCite node", async () => {
    const processor = remark()
      .use(remarkParse)
      .use(sailzenCite);

    const ast = processor.parse("::cite[foo, bar]");
    // Traverse AST to find our custom node
    const citeNode = findNodeByType(ast, DendronASTTypes.SAILZEN_CITE);
    expect(citeNode).toBeDefined();
    expect(citeNode.keys).toEqual(["foo", "bar"]);
  });
});
```

**Note:** Some tokenizers (hashtag, zdocTags) check `ConfigUtils.getWorkspace(config)` via `MDUtilsV5.getProcData(proc)`. For these, use Pattern C.

### Pattern C: Full Processor Integration (Recommended)

Use the existing test helpers to process through the full pipeline.

```ts
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("sailzenCite with full processor", () => {
  test("should render cite in HTML", async () => {
    const note = createTestNoteWithBody("See ::cite[foo, bar] for details.");
    const html = await processNoteFull(note);
    expect(html).toContain("<sup>");
    expect(html).toContain("[foo, bar]");
  });
});
```

**Key helpers from `testHelpers.ts`:**

| Helper | Purpose |
|--------|---------|
| `createTestNoteWithBody(body)` | Creates a `NoteProps` with given markdown body |
| `createTestNoteWithWikiLinks(links)` | Creates note with `[[link]]` bodies |
| `createTestNoteWithHashtags(tags)` | Creates note with `#tag` bodies |
| `processNoteFull(note, flavor?)` | Runs note through `MDUtilsV5.procRehypeFull` → HTML string |
| `createFullTestProcessor(note, flavor?)` | Returns processor instance for custom assertions |

### Pattern D: Multi-Destination Compiler Tests

For plugins with `attachCompiler` that switch on `DendronASTDest`:

```ts
import { DendronASTDest } from "../../types";
import { MDUtilsV5 } from "../../utilsv5";

describe("sailzenCite compiler", () => {
  test("should round-trip in MD_DENDRON mode", async () => {
    const note = createTestNoteWithBody("::cite[foo, bar]");
    const proc = MDUtilsV5.procRehypeFull(
      { noteToRender: note, fname: note.fname, vault: note.vault, config: createTestConfig(), dest: DendronASTDest.MD_DENDRON },
      { flavor: ProcFlavor.REGULAR }
    );
    const result = await proc.process(note.body);
    expect(result.toString()).toContain("::cite[foo, bar]");
  });
});
```

---

## 7. Custom Syntax Catalog

| Syntax | AST Type | Plugin | Example | Destinations |
|--------|----------|--------|---------|-------------|
| `[[target]]` | `wikiLink` | `wikiLinks` | `[[hello]]` | MD_DENDRON, HTML |
| `[[alias\|target]]` | `wikiLink` | `wikiLinks` | `[[hi\|hello]]` | MD_DENDRON, HTML |
| `#tag` | `hashtag` | `hashtags` | `#important` | MD_DENDRON, MD_REGULAR |
| `\cite{key}` | `zdoctag` | `zdocTags` | `\cite{foo}` | MD_DENDRON |
| `^anchor` | `blockAnchor` | `blockAnchors` | `^my-anchor` | MD_DENDRON, MD_REGULAR, MD_ENHANCED_PREVIEW |
| `![[note]]` | `refLinkV2` | `noteRefsV2` | `![[daily.journal]]` | MD_DENDRON, HTML |
| `![alt](url){props}` | `extendedImage` | `extendedImage` | `![](img.png){width: 100}` | MD_DENDRON, MD_REGULAR, MD_ENHANCED_PREVIEW |
| `::cite[keys]` | `sailzenCite` | `sailzenCite` | `::cite[foo, bar]` | MD_DENDRON, HTML, DOC_EXPORT, DOC_PREVIEW |
| `::figure[cap](src){opts}` | `sailzenFigure` | `sailzenFigure` | `::figure[Teaser](fig1){width="80%"}` | MD_DENDRON, HTML, DOC_EXPORT, DOC_PREVIEW |

### Reserved / Planned Types (in `DendronASTTypes` but not fully implemented)

| Type | Status | Description |
|------|--------|-------------|
| `SAILZEN_TABLE` | 🔶 Planned | Advanced table directive |
| `SAILZEN_MATH_ENV` | 🔶 Planned | `::theorem`, `::proof`, `::definition` |
| `SAILZEN_ALGORITHM` | 🔶 Planned | `::algorithm` environment |
| `SAILZEN_IF_FORMAT` | 🔶 Planned | `::if-format[latex]` conditional |

---

## 8. Running Tests

```bash
# All unified tests
pnpm run test:unified

# Single test file
pnpm jest packages/unified/src/remark/__tests__/hashtag.test.ts

# With coverage
pnpm jest packages/unified --coverage
```

**ESM Note:** Jest runs with `--experimental-vm-modules` due to ESM usage in `unified` v11.

---

## 9. Adding a New Custom Syntax: Checklist

1. **Define AST type** in `src/types.ts` (add to `DendronASTTypes` enum + node interface)
2. **Implement remark plugin** in `src/remark/mySyntax.ts`:
   - `attachParser()` with locator + tokenizer
   - `attachCompiler()` with multi-dest visitor
3. **Register plugin** in `src/utilsv5.ts` (`procRehypeFull`) and/or `src/utilsWeb.ts`
4. **Add decoration** in `src/decorations/` (if IDE highlighting needed)
   - Register in `src/decorations/decorations.ts` `runDecorator()` dispatcher
5. **Write tests** in `src/remark/__tests__/mySyntax.test.ts`:
   - Regex unit tests
   - Full processor integration tests via `processNoteFull()`
   - If compiler has multiple destinations, test each
6. **Update this document** with the new syntax entry

# Custom Markdown Syntax Testing Guide

> For `@saili/unified` contributors adding new remark plugins.

## Testing Philosophy

Custom syntax plugins in this package follow a **4-tier testing pattern**. Because tokenizers depend on `MDUtilsV5.getProcData(proc).config`, isolated `remark().use(plugin)` tests are unreliable. The reliable path is:

1. **Test regexes in isolation** — fast, deterministic, no processor context needed
2. **Test utility functions** — pure functions that extract data from matches
3. **Skip isolated plugin tests** — remark-parse tokenizers need full `MDUtilsV5` context
4. **Test via `processNoteFull`** — full pipeline integration test with real HTML output

## 4-Tier Test Structure

### Tier 1: Regex Unit Tests

Every custom syntax exports a `*_REGEX` (start-anchored) and `*_REGEX_LOOSE` (anywhere). Test both.

```ts
describe("MY_FEATURE_REGEX", () => {
  test("should match at start", () => {
    const match = MY_FEATURE_REGEX.exec("::myFeature[value]");
    expect(match).not.toBeNull();
    expect(match?.[1]).toBe("value");
  });

  test("should not match in middle of text", () => {
    const match = MY_FEATURE_REGEX.exec("text ::myFeature[value]");
    expect(match).toBeNull();
  });
});

describe("MY_FEATURE_REGEX_LOOSE", () => {
  test("should match anywhere", () => {
    const match = MY_FEATURE_REGEX_LOOSE.exec("text ::myFeature[value]");
    expect(match).not.toBeNull();
  });
});
```

### Tier 2: Utility Function Tests

Test pure helper functions like `matchMyFeature()`, `extractXFromMatch()`.

```ts
describe("MyFeatureUtils", () => {
  test("matchMyFeature should extract value", () => {
    const result = MyFeatureUtils.matchMyFeature("::myFeature[test]");
    expect(result).toBe("test");
  });

  test("matchMyFeature should return undefined for invalid input", () => {
    const result = MyFeatureUtils.matchMyFeature("invalid");
    expect(result).toBeUndefined();
  });
});
```

### Tier 3: Skipped Isolated Plugin Tests

Keep the describe block as a placeholder. The tokenizers require `MDUtilsV5` processor data that `remark().use()` alone cannot provide.

```ts
describe.skip("myFeature plugin integration", () => {
  test("should parse in markdown", () => {
    // Skipped: requires full processor context
  });
});
```

### Tier 4: Full Processor Integration Tests

Use `processNoteFull(note)` from `__tests__/utils/testHelpers.ts`. It runs the entire remark→rehype→HTML pipeline.

```ts
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("myFeature with full processor", () => {
  test("should render in HTML", async () => {
    const note = createTestNoteWithBody("Some ::myFeature[value] text");
    const html = await processNoteFull(note);
    expect(html).toContain("value");
  });
});
```

## Test Fixtures

Use helpers from `src/__tests__/fixtures/testNotes.ts`:

| Function | Purpose |
|----------|---------|
| `createTestNoteWithBody(body)` | Note with arbitrary markdown body |
| `createTestNoteWithWikiLinks(links[])` | Body with `[[link]]` entries |
| `createTestNoteWithHashtags(tags[])` | Body with `#tag` entries |
| `createTestConfig()` | Minimal workspace config |
| `createTestVault()` | Minimal vault descriptor |

## File Naming Convention

Place tests alongside the plugin in `src/remark/__tests__/`:

```
src/remark/
  myFeature.ts
  __tests__/
    myFeature.test.ts
```

## Complete Template

```ts
/**
 * Tests for myFeature remark plugin
 */

import {
  myFeature,
  MY_FEATURE_REGEX,
  MY_FEATURE_REGEX_LOOSE,
  MyFeatureUtils,
} from "../myFeature";
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";
import { DendronASTTypes } from "../../types";

describe("myFeature plugin", () => {
  // === Tier 1: Regex ===
  describe("MY_FEATURE_REGEX", () => {
    test("should match at start", () => {
      const match = MY_FEATURE_REGEX.exec("::myFeature[test]");
      expect(match).not.toBeNull();
      expect(match?.[1]).toBe("test");
    });

    test("should not match in middle", () => {
      expect(MY_FEATURE_REGEX.exec("text ::myFeature[test]")).toBeNull();
    });
  });

  describe("MY_FEATURE_REGEX_LOOSE", () => {
    test("should match anywhere", () => {
      const match = MY_FEATURE_REGEX_LOOSE.exec("text ::myFeature[test]");
      expect(match).not.toBeNull();
    });
  });

  // === Tier 2: Utilities ===
  describe("MyFeatureUtils", () => {
    test("matchMyFeature extracts value", () => {
      expect(MyFeatureUtils.matchMyFeature("::myFeature[test]")).toBe("test");
    });
  });

  // === Tier 3: Skipped (needs MDUtilsV5 context) ===
  describe.skip("myFeature plugin integration", () => {
    test("should parse in markdown", () => {
      // Skipped: requires full processor context
    });
  });

  // === Tier 4: Full processor ===
  describe("myFeature with full processor", () => {
    test("should render in HTML", async () => {
      const note = createTestNoteWithBody("Hello ::myFeature[world]");
      const html = await processNoteFull(note);
      expect(html).toContain("world");
    });
  });
});
```

## Running Tests

From repo root:

```bash
# Run all unified tests
pnpm test:unified

# Run a specific test file
pnpm --filter="./packages/unified" exec cross-env NODE_OPTIONS=--experimental-vm-modules jest src/remark/__tests__/myFeature.test.ts

# Watch mode
pnpm --filter="./packages/unified" exec cross-env NODE_OPTIONS=--experimental-vm-modules jest --watch
```

## Config-Gated Syntax

If your plugin reads `config.enableMyFeature`, the `processNoteFull` helper uses a default test config. If your feature is disabled by default, enable it in the test note or mock the config.

## Common Pitfalls

1. **Regex anchor mismatch**: `MY_FEATURE_REGEX` must be start-anchored (`^...`) because remark inline tokenizers receive text from the current position onward.
2. **Locator function**: Always provide a `locator` on the inlineTokenizer so remark can find your syntax efficiently.
3. **Insertion order**: Use `inlineMethods.splice(inlineMethods.indexOf("link"), 0, "myFeature")` to insert before `link` (or `"text"` for text-priority syntax).
4. **Compiler destination**: Always handle all `DendronASTDest` values or throw a descriptive `DendronError`.
5. **HTML assertions**: `processNoteFull` returns a full HTML document string; use `.toContain()` for assertions rather than exact matching.
