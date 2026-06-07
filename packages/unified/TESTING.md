# @saili/unified 测试指南

> 本文档描述 `@saili/unified` 包的基本功能、现有 unittest 建设情况，并提供测试框架的使用与迭代指南。

---

## 1. 包功能概述

`@saili/unified` 是 SailZen 的 **Markdown / Unified 解析工具包**，基于 [unified](https://unifiedjs.com/) 生态系统构建，核心职责包括：

| 模块 | 功能 | 关键文件 |
|------|------|----------|
| **核心处理器** | 构建 remark/rehype 处理器链，支持多种渲染模式（Preview / Publishing / Hover 等） | `utilsv5.ts`, `utilsWeb.ts` |
| **AST 类型系统** | 定义 Dendron 扩展 AST 节点类型（WikiLink、HashTag、NoteRef、BlockAnchor、SailZen 扩展节点等） | `types.ts` |
| **MDast 工具** | 辅助遍历、查找标题、生成消息 AST、异步访问器等 | `utils.ts` |
| **Remark 插件** | Wiki 链接、标签、块锚点、笔记引用、扩展图片、反向链接、层级、SailZen 引用/图注等 | `remark/*.ts` |
| **Rehype 插件** | HTML 元素包装、Mermaid 占位等 | `rehype/*.ts` |
| **Decoration 工具** | VSCode 编辑器装饰相关的解析辅助（wikilinks、hashtags、frontmatter、references 等） | `decorations/*.ts` |
| **站点工具** | 发布站点 URL 生成、发布权限判断、重复笔记处理等 | `SiteUtils.ts` |
| **层级工具** | 笔记父子层级关系遍历 | `HierarchyUtils.ts` |
| **YAML 工具** | Frontmatter 解析、tags 提取 | `yaml.ts` |

---

## 2. 测试技术栈

| 项目 | 版本 / 配置 |
|------|------------|
| 测试框架 | **Jest** (ESM 模式) |
| TS 转换器 | **ts-jest** (`useESM: true`) |
| 基础配置 | `../../jest.config.base.mjs` |
| 包配置 | `jest.config.mjs` (覆盖 `displayName` 和 `moduleNameMapper`) |
| 环境 | `node` |
| 匹配模式 | `**/src/**/__tests__/**/*.test.ts` |

### 运行测试

```bash
# 在 packages/unified 目录下
pnpm test

# Watch 模式
pnpm test:watch

# 覆盖率报告
pnpm test:coverage

# 从 monorepo 根目录运行指定包
pnpm run test:unified
```

---

## 3. 测试目录结构

```
src/
├── __tests__/
│   ├── fixtures/
│   │   └── testNotes.ts          # 测试夹具：NoteProps / Config / Vault 工厂函数
│   ├── utils/
│   │   └── testHelpers.ts        # 测试辅助：处理器创建、AST 断言工具
│   ├── hello.test.ts             # 基础冒烟测试
│   ├── utils.test.ts             # MdastUtils / renderFromNote 测试
│   ├── mdutilsv5.test.ts         # MDUtilsV5 处理器测试
│   └── utilsWeb.test.ts          # MDUtilsV5Web 处理器测试
├── remark/
│   └── __tests__/
│       ├── wikiLinks.test.ts     # Wiki 链接正则 + 全处理器集成
│       ├── hashtag.test.ts       # HashTag 正则 + 工具函数 + 集成
│       ├── zdocTags.test.ts      # ZDoc 标签正则 + 工具函数 + 集成
│       ├── blockAnchors.test.ts  # 块锚点正则 + 工具函数 + 集成
│       ├── sailzenCite.test.ts   # SailZen 引用节点解析与编译
│       ├── sailzenFigure.test.ts # SailZen 图注节点解析与编译
│       └── tag.test.ts           # ZDoc 标签独立正则测试
├── rehype/
│   └── __tests__/
│       └── wrap.test.ts          # wrap 插件 HTML 包装测试
└── __mocks__/
    └── rehype-mermaid.ts         # rehype-mermaid 的 no-op Mock
```

---

## 4. 测试策略与分层

本包采用 **三层测试策略**：

### 4.1 单元测试（正则 / 纯函数）

对不依赖外部上下文的纯函数和正则表达式进行直接测试：

- `LINK_REGEX`, `LINK_REGEX_LOOSE`, `matchWikiLink`
- `HASHTAG_REGEX`, `HASHTAG_REGEX_LOOSE`, `HashTagUtils`
- `ZDOCTAG_REGEX`, `ZDOCTAG_REGEX_LOOSE`, `ZDocTagUtils`
- `BLOCK_LINK_REGEX`, `BLOCK_LINK_REGEX_LOOSE`, `matchBlockAnchor`
- `MdastUtils.genMDMsg`, `MdastUtils.findIndex`, `MdastUtils.findHeader`

**特点**：零依赖、执行快、定位精准。

### 4.2 插件隔离测试（独立 Processor）

对单个 remark/rehype 插件使用最小化处理器进行测试：

```ts
const processor = remark().use(remarkParse).use(sailzenCite);
const tree = processor.parse("::cite[foo]");
expect(tree.children[0].children[0].type).toBe("sailzenCite");
```

**适用插件**：`sailzenCite`, `sailzenFigure`, `wrap`

**特点**：验证插件的 parse / compile 行为，不依赖 Dendron 配置上下文。

### 4.3 全处理器集成测试（MDUtilsV5）

通过 `MDUtilsV5.procRehypeFull()` 或 `MDUtilsV5.procRemarkFull()` 构建完整处理器，验证端到端渲染：

```ts
const note = createTestNoteWithBody("#important");
const html = await processNoteFull(note);
expect(html).toContain("important");
```

**特点**：覆盖插件链的协作效果，但构建成本较高，适合关键路径。

---

## 5. 测试基础设施

### 5.1 夹具工厂（`fixtures/testNotes.ts`）

| 函数 | 用途 |
|------|------|
| `createTestVault(overrides?)` | 创建最小 DVault |
| `createTestConfig(overrides?)` | 创建默认 DendronConfig |
| `createTestNote(overrides?)` | 创建最小 NoteProps |
| `createTestNoteWithBody(body, overrides?)` | 创建带正文笔记 |
| `createTestNoteWithWikiLinks(links, overrides?)` | 创建带 wiki 链接笔记 |
| `createTestNoteWithHashtags(tags, overrides?)` | 创建带标签笔记 |
| `createTestNoteWithFrontmatter(fm, body, overrides?)` | 创建带 frontmatter 笔记 |

**使用示例**：

```ts
import { createTestNoteWithBody, createTestConfig, createTestVault } from "./fixtures/testNotes";

const note = createTestNoteWithBody("[[target]]");
const config = createTestConfig();
const vault = createTestVault();
```

### 5.2 测试辅助（`utils/testHelpers.ts`）

| 函数 | 用途 |
|------|------|
| `createTestProcessor()` | 创建基础 remark 处理器 |
| `processMarkdownToAST(md)` | Markdown → AST |
| `processMarkdownToString(md)` | Markdown → String |
| `createFullTestProcessor(note, flavor)` | 创建完整 Dendron 处理器 |
| `processNoteFull(note, flavor)` | 笔记 → HTML 字符串 |
| `expectContains(actual, expected)` | 包含断言 |
| `expectNotContains(actual, unexpected)` | 不包含断言 |
| `expectMatches(actual, pattern)` | 正则匹配断言 |
| `expectNotMatches(actual, pattern)` | 正则不匹配断言 |

### 5.3 Mock

- `__mocks__/rehype-mermaid.ts`：将 `rehype-mermaid` 替换为 no-op，避免浏览器依赖（Playwright）。

---

## 6. 如何编写新测试（迭代指南）

### 6.1 步骤 1：确定测试分层

根据被测代码选择适当的分层：

| 被测代码类型 | 推荐分层 | 示例 |
|-------------|----------|------|
| 正则表达式、纯工具函数 | 单元测试 | `HashTagUtils.matchHashtag` |
| 单个 remark/rehype 插件 | 插件隔离测试 | `sailzenCite` 解析 |
| 跨插件协作、HTML 输出 | 全处理器集成 | Wiki 链接 → HTML |
| 处理器配置/模式差异 | 全处理器集成 | `ProcFlavor.PREVIEW` vs `PUBLISHING` |

### 6.2 步骤 2：选择测试文件位置

遵循 **与被测代码同目录** 原则：

- `src/utils.ts` → `src/__tests__/utils.test.ts`
- `src/remark/hierarchies.ts` → `src/remark/__tests__/hierarchies.test.ts`
- `src/SiteUtils.ts` → `src/__tests__/SiteUtils.test.ts`

### 6.3 步骤 3：编写测试模板

#### 模板 A：纯函数 / 正则单元测试

```ts
/**
 * Tests for <module-name>
 */
import { someFunction, SOME_REGEX } from "../<module>";

describe("<module-name>", () => {
  describe("SOME_REGEX", () => {
    test("should match valid pattern", () => {
      const match = SOME_REGEX.exec("input");
      expect(match).not.toBeNull();
      expect(match?.groups?.groupName).toBe("expected");
    });

    test("should not match invalid pattern", () => {
      expect(SOME_REGEX.exec("invalid")).toBeNull();
    });
  });

  describe("someFunction", () => {
    test("should return expected for valid input", () => {
      expect(someFunction("input")).toBe("expected");
    });

    test("should handle edge case", () => {
      expect(someFunction("")).toBeUndefined();
    });
  });
});
```

#### 模板 B：插件隔离测试

```ts
import { remark } from "remark";
import remarkParse from "remark-parse";
import { myPlugin } from "../myPlugin";

describe("myPlugin", () => {
  test("should parse custom syntax into AST node", () => {
    const processor = remark().use(remarkParse).use(myPlugin);
    const tree = processor.parse("::my-directive[arg]");

    const root = tree as any;
    expect(root.children).toHaveLength(1);

    const paragraph = root.children[0];
    expect(paragraph.type).toBe("paragraph");

    const node = paragraph.children[0];
    expect(node.type).toBe("myNodeType");
    expect(node.value).toBe("arg");
  });

  test("should compile node back to string", () => {
    const processor = remark().use(remarkParse).use(myPlugin);
    const result = processor.processSync("::my-directive[arg]").toString();
    expect(result).toContain("::my-directive[arg]");
  });
});
```

#### 模板 C：全处理器集成测试

```ts
import { createTestNoteWithBody } from "../../__tests__/fixtures/testNotes";
import { processNoteFull } from "../../__tests__/utils/testHelpers";

describe("myFeature integration", () => {
  test("should render feature in HTML", async () => {
    const note = createTestNoteWithBody("::my-directive[content]");
    const html = await processNoteFull(note);

    expect(html).toBeDefined();
    expect(html).toContain("content");
  });

  test("should handle multiple directives", async () => {
    const note = createTestNoteWithBody("::a[x]\n\n::b[y]");
    const html = await processNoteFull(note);

    expect(html).toContain("x");
    expect(html).toContain("y");
  });
});
```

### 6.4 步骤 4：遵循命名与结构规范

- 使用 `describe` 分组：按模块 → 按函数/特性 → 按场景
- 使用 `test` 或 `it` 描述具体行为（`should ... when ...`）
- 一个断言一个职责；相关断言可放在同一 `test` 中
- 优先使用夹具工厂，避免硬编码大对象
- 对需要 `DendronConfig` 的测试，使用 `createTestConfig()`

### 6.5 步骤 5：运行并验证

```bash
# 运行全部测试
pnpm test

# 运行单个测试文件
pnpm exec cross-env NODE_OPTIONS=--experimental-vm-modules jest src/remark/__tests__/myFeature.test.ts

# 运行特定 describe/test
pnpm test -- -t "should render feature"

# 覆盖率
pnpm test:coverage
```

---

## 7. 当前测试覆盖情况

### ✅ 已覆盖模块

| 模块 | 覆盖类型 | 说明 |
|------|----------|------|
| `utils.ts` — MdastUtils | 单元 + 集成 | `genMDMsg`, `genMDErrorMsg`, `findIndex`, `findHeader`, `renderFromNote` |
| `utilsv5.ts` — MDUtilsV5 | 集成 | `procRemarkFull`, `procRehypeFull`（task list、headers、wiki link + math） |
| `utilsWeb.ts` — MDUtilsV5Web | 集成 | `procRehypeWeb`（创建、HTML 输出、wiki links、hashtags、flavor） |
| `remark/wikiLinks` | 单元 + 集成 | 正则、`matchWikiLink`、全处理器渲染 |
| `remark/hashtag` | 单元 + 集成 | 正则、`HashTagUtils`、全处理器渲染 |
| `remark/zdocTags` | 单元 + 集成 | 正则、`ZDocTagUtils`、全处理器渲染 |
| `remark/blockAnchors` | 单元 + 集成 | 正则、`matchBlockAnchor`、全处理器渲染 |
| `remark/sailzenCite` | 插件隔离 | 解析、round-trip、DOC_EXPORT 编译 |
| `remark/sailzenFigure` | 插件隔离 | 解析（含 options）、round-trip、DOC_EXPORT 编译 |
| `rehype/wrap` | 插件隔离 | 选择器匹配、多元素包装、class 包装、非匹配排除 |

### ⚠️ 覆盖缺口（待补充）

以下模块 **目前缺少测试**，是按优先级推荐的扩展方向：

#### 高优先级（核心逻辑 / 频繁使用）

| 模块 | 建议测试内容 |
|------|-------------|
| `remark/dendronPub.ts` | 标题插入、`transformNoPublish`、图片 URL 转换、wiki link opts 前缀 |
| `remark/noteRefsV2.ts` | 笔记引用解析、嵌套引用、锚点范围、`convertNoteRefToHAST` |
| `remark/backlinks.ts` | 反向链接生成、链接去重 |
| `remark/backlinksHover.ts` | Hover 预览内容生成 |
| `remark/hierarchies.ts` | 层级列表生成、children 链接渲染 |
| `SiteUtils.ts` | `canPublish`, `isPublished`, `getSiteUrlPathForNote`, `handleDup`, `isIndexNote` |
| `HierarchyUtils.ts` | `getChildren`（含 `skipLevels`） |

#### 中优先级（辅助逻辑）

| 模块 | 建议测试内容 |
|------|-------------|
| `decorations/*.ts` | 各类 Decoration 的范围计算、位置映射（需要模拟 VSCode API 或仅测试纯逻辑） |
| `yaml.ts` | `parseFrontmatter`, `getFrontmatterTags`, `visitYamlUnist` |
| `remark/extendedImage.ts` | 扩展图片语法解析、属性提取 |
| `remark/transformLinks.ts` | 链接转换规则 |

#### 低优先级（边界 / 较稳定）

| 模块 | 建议测试内容 |
|------|-------------|
| `remark/dendronPreview.ts` | Hover 预览图片 URL 重写 |
| `remark/publishSite.ts` | 站点发布专用转换 |
| `remark/abbr.ts` | 缩写解析 |
| `utilities/getParsingDependencyDicts.ts` | 解析依赖字典生成 |
| `rehype/mermaid-noop.ts` | no-op 行为确认 |

---

## 8. 迭代示例：为 `HierarchyUtils` 添加测试

### 8.1 创建测试文件

`src/__tests__/HierarchyUtils.test.ts`：

```ts
/**
 * Tests for HierarchyUtils
 */
import { HierarchyUtils } from "../HierarchyUtils";
import { NotePropsByIdDict } from "@saili/common-all";

describe("HierarchyUtils", () => {
  describe("getChildren", () => {
    test("should return direct children", () => {
      const notes: NotePropsByIdDict = {
        root: { id: "root", children: ["child1", "child2"] } as any,
        child1: { id: "child1", children: [] } as any,
        child2: { id: "child2", children: [] } as any,
      };

      const children = HierarchyUtils.getChildren({
        skipLevels: 0,
        note: notes.root as any,
        notes,
      });

      expect(children).toHaveLength(2);
      expect(children.map((c) => c.id)).toEqual(["child1", "child2"]);
    });

    test("should skip levels when skipLevels > 0", () => {
      const notes: NotePropsByIdDict = {
        root: { id: "root", children: ["mid"] } as any,
        mid: { id: "mid", children: ["leaf"] } as any,
        leaf: { id: "leaf", children: [] } as any,
      };

      const children = HierarchyUtils.getChildren({
        skipLevels: 1,
        note: notes.root as any,
        notes,
      });

      expect(children).toHaveLength(1);
      expect(children[0].id).toBe("leaf");
    });

    test("should filter out undefined children", () => {
      const notes: NotePropsByIdDict = {
        root: { id: "root", children: ["missing", "exists"] } as any,
        exists: { id: "exists", children: [] } as any,
      };

      const children = HierarchyUtils.getChildren({
        skipLevels: 0,
        note: notes.root as any,
        notes,
      });

      expect(children).toHaveLength(1);
      expect(children[0].id).toBe("exists");
    });
  });
});
```

### 8.2 运行验证

```bash
pnpm exec cross-env NODE_OPTIONS=--experimental-vm-modules jest src/__tests__/HierarchyUtils.test.ts
```

---

## 9. 最佳实践

1. **优先测试纯函数和正则**：它们无依赖、快、稳定。
2. **使用夹具工厂**：保持测试数据一致性，减少样板代码。
3. **分层清晰**：单元测试失败时定位快；集成测试保障端到端正确性。
4. **避免过度测试内部实现**：关注输入输出行为，而非 AST 中间结构的每个字段。
5. **Mock 外部依赖**：对 `rehype-mermaid` 等重型依赖使用 Mock；对 VSCode API 相关代码在 Decoration 测试中隔离纯逻辑。
6. **保持测试独立**：每个 `test` 块应自包含，不依赖其他测试的执行顺序或副作用。
7. **清理全局状态**：若测试修改了全局缓存（如 `MDUtilsV5.clearRefCache()`），在 `afterEach` 中恢复。

---

## 10. 常见问题

### Q: `jest-haste-map: duplicate manual mock found`

**原因**：`lib/__mocks__/`（编译产物）与 `src/__mocks__/`（源码）同时存在。

**解决**：`pnpm run clean` 清理 `lib/` 目录后再运行测试。

### Q: 插件集成测试需要完整 `MDUtilsV5` 上下文怎么办？

**方案**：使用 `processNoteFull()` 辅助函数，它已经封装了完整处理器构建。若需要更细粒度控制，使用 `createFullTestProcessor()`。

### Q: 如何测试依赖 `DEngineClient` 的函数（如 `LinkUtils.findLinks`）？

**方案**：目前部分函数需要 Engine 实例，建议在更高层（如 `engine-server`）进行集成测试。在 `unified` 包内，优先测试不依赖 Engine 的纯函数分支。

---

*最后更新：基于 `@saili/unified` v0.3.12 的代码状态编写。*
