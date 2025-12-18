# Unified 模块测试框架文档

## 概述

本文档描述了 `@saili/unified` 模块的测试框架结构、使用方法和维护指南。该模块是一个自定义的 markdown 词法解析器，基于 unified/remark/rehype 生态系统构建。

## 目录结构

```
packages/unified/
├── src/
│   ├── __tests__/              # 测试相关文件
│   │   ├── fixtures/           # 测试数据和 mock 对象
│   │   │   └── testNotes.ts    # NoteProps 测试 fixtures
│   │   ├── utils/              # 测试工具函数
│   │   │   └── testHelpers.ts  # 测试辅助函数
│   │   ├── utils.test.ts       # utils.ts 的测试
│   │   └── utilsWeb.test.ts   # utilsWeb.ts 的测试
│   ├── remark/                 # Remark 插件
│   │   ├── __tests__/          # Remark 插件测试
│   │   │   ├── wikiLinks.test.ts
│   │   │   ├── hashtag.test.ts
│   │   │   ├── zdocTags.test.ts
│   │   │   └── blockAnchors.test.ts
│   │   └── ...
│   ├── rehype/                 # Rehype 插件
│   │   ├── __tests__/         # Rehype 插件测试
│   │   │   └── wrap.test.ts
│   │   └── ...
│   └── ...
├── jest.config.mjs            # Jest 配置文件
└── package.json               # 包含测试脚本
```

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
