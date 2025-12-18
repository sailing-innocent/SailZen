# 测试维护文档

## 目录

- [概述](#概述)
- [测试框架配置](#测试框架配置)
- [运行测试](#运行测试)
- [编写测试](#编写测试)
- [测试覆盖率](#测试覆盖率)
- [测试文件组织](#测试文件组织)
- [测试最佳实践](#测试最佳实践)
- [模块测试清单](#模块测试清单)
- [常见问题](#常见问题)

## 概述

`@saili/common-all` 包使用 **Jest** 作为测试框架，配合 **ts-jest** 进行 TypeScript 支持。测试的目标是确保代码质量、功能正确性和可维护性。

### 技术栈

- **测试框架**: Jest (支持 ESM)
- **TypeScript 支持**: ts-jest
- **测试环境**: Node.js (>=18.0.0)
- **模块系统**: ESM (ECMAScript Modules)
- **断言库**: Jest 内置断言

## 测试框架配置

### 配置文件

测试配置位于 `jest.config.mjs`（使用 `.mjs` 扩展名以支持 ESM）：

```javascript
export default {
  preset: "ts-jest/presets/default-esm",
  testEnvironment: "node",
  extensionsToTreatAsEsm: [".ts"],
  // 使用新的 ts-jest 配置格式（支持 ESM）
  transform: {
    "^.+\\.ts$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
  },
  moduleNameMapper: {
    // 处理文件扩展名映射（ESM 需要显式的 .js 扩展名）
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
  moduleFileExtensions: ["ts", "js", "json", "node"],
  // 排除 lib 目录（编译输出）和类型定义文件
  testMatch: [
    "**/src/**/*.test.ts",
    "**/src/**/__tests__/**/*.ts",
  ],
  // 排除不需要测试的文件和目录
  testPathIgnorePatterns: [
    "/node_modules/",
    "/lib/",
    "\\.d\\.ts$",
  ],
  // ... 其他配置
};
```

### 配置说明

- **preset**: 使用 `ts-jest/presets/default-esm` 预设，支持 ESM 模块
- **testEnvironment**: 设置为 `node`，适合 Node.js 环境测试
- **extensionsToTreatAsEsm**: 将 `.ts` 文件视为 ESM 模块
- **transform**: 使用新的 ts-jest 配置格式，启用 `useESM: true` 以支持 ESM
- **moduleNameMapper**: 处理 ESM 导入时的文件扩展名映射（TypeScript 导入不需要扩展名，但运行时需要）
- **testMatch**: 匹配以下模式的测试文件：
  - `**/src/**/*.test.ts` - src 目录下的 `.test.ts` 文件
  - `**/src/**/__tests__/**/*.ts` - src 目录下 `__tests__` 目录中的所有 `.ts` 文件
- **testPathIgnorePatterns**: 排除 `lib` 目录（编译输出）和类型定义文件

### TypeScript 配置

测试文件使用项目的 `tsconfig.json`，其中已包含 Jest 类型定义：

```json
{
  "compilerOptions": {
    "module": "ESNext",
    "moduleResolution": "bundler",
    "target": "ES2024",
    "types": ["node", "jest"],
    // ... 其他配置
  }
}
```

**注意**: 项目使用 ESM 模块系统，`module` 设置为 `ESNext`。

## 运行测试

### 基本命令

```bash
# 运行所有测试
pnpm test

# 运行特定测试文件
pnpm test getJournalTitle.test.ts

# 运行测试并查看覆盖率
pnpm test --coverage

# 监听模式（自动运行测试）
pnpm test --watch

# 运行匹配模式的测试
pnpm test --testNamePattern="getJournalTitle"
```

**注意**: 测试命令使用 `cross-env NODE_OPTIONS=--experimental-vm-modules` 来启用 Jest 的 ESM 支持。你可能会看到实验性警告，这是正常的。

### 覆盖率报告

```bash
# 生成覆盖率报告
pnpm test --coverage

# 覆盖率报告格式
# - 终端输出：简要覆盖率统计
# - HTML 报告：coverage/lcov-report/index.html
# - LCOV 格式：coverage/lcov.info（用于 CI/CD）
```

### 覆盖率阈值配置（推荐添加）

建议在 `jest.config.js` 中添加覆盖率阈值：

```javascript
module.exports = {
  // ... 现有配置
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
    "!src/**/__tests__/**",
    "!src/**/*.test.ts",
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70,
    },
  },
};
```

## 编写测试

### 测试文件命名

测试文件应遵循以下命名约定：

1. **方式一**：与源文件同目录，使用 `.test.ts` 后缀
   ```
   src/utils/stringUtil.ts
   src/utils/stringUtil.test.ts
   ```

2. **方式二**：使用 `__tests__` 目录
   ```
   src/utils/__tests__/stringUtil.test.ts
   ```

### 测试结构

使用 Jest 的 `describe` 和 `it`（或 `test`）组织测试：

```typescript
import { functionToTest } from "../index";

describe("functionToTest", () => {
  describe("正常情况", () => {
    it("应该返回正确的结果", () => {
      const result = functionToTest("input");
      expect(result).toBe("expected");
    });
  });

  describe("边界情况", () => {
    it("应该处理空字符串", () => {
      const result = functionToTest("");
      expect(result).toBeUndefined();
    });
  });

  describe("错误情况", () => {
    it("应该抛出错误当输入无效时", () => {
      expect(() => functionToTest(null)).toThrow();
    });
  });
});
```

### 现有测试示例

参考 `src/utils/__tests__/getJournalTitle.test.ts` 作为测试编写示例：

```typescript
import { getJournalTitle } from "../index";

describe("getJournalTitle", () => {
  describe("valid date formats", () => {
    it("should return formatted title for YYYY.MM.DD format", () => {
      const result = getJournalTitle("2023.12.25", "yyyy.MM.dd");
      expect(result).toBe("2023-12-25");
    });
    // ... 更多测试用例
  });

  describe("edge cases", () => {
    it("should return undefined for empty string", () => {
      const result = getJournalTitle("", "yyyy.MM.dd");
      expect(result).toBeUndefined();
    });
  });
});
```

### 常用断言方法

```typescript
// 相等性
expect(value).toBe(expected);           // 严格相等 (===)
expect(value).toEqual(expected);        // 深度相等
expect(value).toStrictEqual(expected);  // 严格深度相等

// 真值
expect(value).toBeTruthy();
expect(value).toBeFalsy();
expect(value).toBeDefined();
expect(value).toBeUndefined();
expect(value).toBeNull();

// 数字
expect(value).toBeGreaterThan(3);
expect(value).toBeGreaterThanOrEqual(3.5);
expect(value).toBeLessThan(5);
expect(value).toBeCloseTo(0.3, 5);

// 字符串
expect(str).toMatch(/pattern/);
expect(str).toContain("substring");

// 数组/对象
expect(array).toContainEqual(item);
expect(array).toHaveLength(3);
expect(object).toHaveProperty("key", "value");

// 异常
expect(() => fn()).toThrow();
expect(() => fn()).toThrow("error message");
expect(() => fn()).toThrowError(TypeError);

// 异步
await expect(promise).resolves.toBe(value);
await expect(promise).rejects.toThrow();
```

### Mock 和 Spy

```typescript
// Mock 函数
const mockFn = jest.fn();
mockFn.mockReturnValue(42);
mockFn.mockResolvedValue(Promise.resolve(42));

// Mock 模块
jest.mock("../module", () => ({
  exportedFunction: jest.fn(),
}));

// Spy 现有函数
const spy = jest.spyOn(object, "method");
spy.mockReturnValue("mocked");

// 清理
afterEach(() => {
  jest.clearAllMocks();
});
```

## 测试覆盖率

### 覆盖率指标

测试覆盖率包括四个维度：

1. **Statements (语句覆盖率)**: 已执行的语句百分比
2. **Branches (分支覆盖率)**: 已执行的分支（if/else, switch）百分比
3. **Functions (函数覆盖率)**: 已调用的函数百分比
4. **Lines (行覆盖率)**: 已执行的行百分比

### 覆盖率目标

建议的覆盖率目标：

- **最低要求**: 60%
- **推荐目标**: 70-80%
- **核心模块**: 80%+

### 查看覆盖率报告

```bash
# 运行测试并生成覆盖率
pnpm test --coverage

# 查看 HTML 报告
open coverage/lcov-report/index.html  # macOS/Linux
start coverage/lcov-report/index.html  # Windows
```

### 排除文件

在 `jest.config.js` 中使用 `collectCoverageFrom` 排除不需要测试的文件：

```javascript
collectCoverageFrom: [
  "src/**/*.{ts,tsx}",
  "!src/**/*.d.ts",           // 类型定义文件
  "!src/**/__tests__/**",     // 测试文件目录
  "!src/**/*.test.ts",         // 测试文件
  "!src/index.ts",             // 入口文件（如需要）
],
```

## 测试文件组织

### 目录结构建议

```
src/
├── utils/
│   ├── __tests__/
│   │   ├── stringUtil.test.ts
│   │   └── dateFormatUtil.test.ts
│   ├── stringUtil.ts
│   └── dateFormatUtil.ts
├── store/
│   ├── __tests__/
│   │   ├── NoteStore.test.ts
│   │   └── SchemaStore.test.ts
│   ├── NoteStore.ts
│   └── SchemaStore.ts
└── api.ts
    └── api.test.ts  # 或创建 __tests__/api.test.ts
```

### 测试文件命名规范

- 测试文件应与被测试文件同名，加上 `.test.ts` 后缀
- 使用描述性的测试名称
- 使用 `describe` 块组织相关测试

## 测试最佳实践

### 1. 测试结构（AAA 模式）

```typescript
it("should do something", () => {
  // Arrange: 准备测试数据和环境
  const input = "test";
  const expected = "result";

  // Act: 执行被测试的代码
  const result = functionToTest(input);

  // Assert: 验证结果
  expect(result).toBe(expected);
});
```

### 2. 测试独立性

- 每个测试应该独立运行
- 使用 `beforeEach` 和 `afterEach` 清理状态
- 避免测试之间的依赖

```typescript
describe("MyClass", () => {
  let instance: MyClass;

  beforeEach(() => {
    instance = new MyClass();
  });

  afterEach(() => {
    // 清理
  });
});
```

### 3. 测试命名

- 使用描述性的测试名称
- 遵循 "should [expected behavior] when [condition]" 模式

```typescript
it("should return formatted date when given valid input", () => {
  // ...
});

it("should throw error when input is null", () => {
  // ...
});
```

### 4. 测试边界情况

确保测试以下情况：

- **正常情况**: 标准输入和预期输出
- **边界情况**: 空值、null、undefined、空数组、空字符串
- **错误情况**: 无效输入、异常情况
- **极端情况**: 最大值、最小值、特殊字符

### 5. 避免测试实现细节

```typescript
// ❌ 不好：测试实现细节
it("should call internal method", () => {
  const spy = jest.spyOn(obj, "internalMethod");
  obj.publicMethod();
  expect(spy).toHaveBeenCalled();
});

// ✅ 好：测试公共接口和行为
it("should return correct result", () => {
  const result = obj.publicMethod();
  expect(result).toBe(expected);
});
```

### 6. 使用测试数据工厂

```typescript
// 创建测试数据工厂函数
function createTestNote(overrides?: Partial<NoteProps>): NoteProps {
  return {
    id: "test-id",
    title: "Test Note",
    body: "Test content",
    ...overrides,
  };
}

// 在测试中使用
it("should process note", () => {
  const note = createTestNote({ title: "Custom Title" });
  const result = processNote(note);
  expect(result).toBeDefined();
});
```

### 7. 异步测试

```typescript
// Promise
it("should resolve async operation", async () => {
  const result = await asyncFunction();
  expect(result).toBeDefined();
});

// 使用 resolves/rejects
it("should resolve with value", async () => {
  await expect(asyncFunction()).resolves.toBe("value");
});

it("should reject with error", async () => {
  await expect(asyncFunction()).rejects.toThrow("Error");
});
```

## 模块测试清单

以下是需要编写测试的主要模块清单：

### 核心工具模块

- [ ] `src/utils/stringUtil.ts` - 字符串工具函数
- [ ] `src/utils/dateFormatUtil.ts` - 日期格式化工具
- [ ] `src/utils/treeUtil.ts` - 树结构工具
- [ ] `src/utils/regex.ts` - 正则表达式工具
- [x] `src/utils/getJournalTitle` - 日志标题获取（已有测试）

### 配置模块

- [ ] `src/config.ts` - 配置相关工具
- [ ] `src/constants/configs/*` - 各种配置定义
- [ ] `src/utils/index.ts` - ConfigUtils 类

### API 模块

- [ ] `src/api.ts` - API 客户端
- [ ] `src/types/RemoteEndpoint.ts` - 远程端点类型

### Store 模块

- [ ] `src/store/NoteStore.ts` - 笔记存储
- [ ] `src/store/SchemaStore.ts` - Schema 存储
- [ ] `src/store/NoteMetadataStore.ts` - 笔记元数据存储
- [ ] `src/store/SchemaMetadataStore.ts` - Schema 元数据存储
- [ ] `src/store/FuseMetadataStore.ts` - Fuse 元数据存储

### 工具类

- [ ] `src/BacklinkUtils.ts` - 反向链接工具
- [ ] `src/DLinkUtils.ts` - 链接工具
- [ ] `src/LabelUtils.ts` - 标签工具
- [ ] `src/StatisticsUtils.ts` - 统计工具
- [ ] `src/VaultUtilsV2.ts` - Vault 工具

### 引擎模块

- [ ] `src/engine/EngineV3Base.ts` - 引擎基类
- [ ] `src/engine/EngineEventEmitter.ts` - 引擎事件发射器
- [ ] `src/FuseEngine.ts` - Fuse 搜索引擎

### 解析和验证

- [ ] `src/parse.ts` - 解析工具
- [ ] `src/schema.ts` - Schema 相关
- [ ] `src/yaml.ts` - YAML 处理

### 其他工具

- [ ] `src/util/cache/*` - 缓存工具
- [ ] `src/util/responseUtil.ts` - 响应工具
- [ ] `src/helpers.ts` - 辅助函数
- [ ] `src/assert.ts` - 断言工具

### 测试优先级建议

1. **高优先级**（核心功能）:
   - API 客户端 (`api.ts`)
   - Store 模块（数据存储）
   - 配置工具 (`ConfigUtils`)
   - 核心工具函数

2. **中优先级**（常用功能）:
   - 各种 Utils 类
   - 解析和验证模块
   - 引擎模块

3. **低优先级**（辅助功能）:
   - 类型定义
   - 常量定义
   - 简单的辅助函数

## 模块系统说明

### ESM 模块系统

项目使用 **ESM (ECMAScript Modules)** 作为模块系统，这是现代 JavaScript 的标准模块格式。

### 为什么使用 ESM？

1. **现代化**: ESM 是 JavaScript 的标准模块系统，2025 年已经是主流
2. **原生支持**: Node.js 18+ 原生支持 ESM，无需额外工具
3. **依赖兼容**: 许多新的 npm 包（如 `github-slugger@2.0.0`、`nanoid@5.1.6`）都是纯 ESM
4. **Tree-shaking**: ESM 支持更好的 tree-shaking，减少打包体积
5. **VSCode 插件兼容**: `vscode-plugin` 使用 `esbuild` 打包，可以无缝处理 ESM 依赖

### 配置要点

- `package.json` 中包含 `"type": "module"`
- TypeScript 配置使用 `"module": "ESNext"` 和 `"moduleResolution": "bundler"`
- Jest 配置使用 `jest.config.mjs` 并启用 ESM 支持
- 测试命令使用 `NODE_OPTIONS=--experimental-vm-modules`（Jest 的 ESM 支持仍在实验阶段）

### 导入/导出语法

项目使用标准的 ESM 语法：

```typescript
// 导入
import { something } from "./module.js";
import defaultExport from "package-name";

// 导出
export function myFunction() {}
export default myDefault;
export { namedExport };
```

**注意**: 在 TypeScript 中导入时不需要 `.js` 扩展名，但编译后的 JavaScript 代码会包含正确的扩展名。

## 常见问题

### Q: 如何测试私有方法？

**A**: 通常不建议直接测试私有方法。如果私有方法逻辑复杂，可以考虑：

1. 通过公共方法间接测试
2. 将复杂逻辑提取为独立的工具函数（可测试）
3. 使用 TypeScript 的 `@ts-ignore` 访问私有成员（不推荐）

### Q: 如何处理外部依赖？

**A**: 使用 Jest 的 mock 功能：

```typescript
jest.mock("axios", () => ({
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));
```

### Q: 如何测试错误处理？

**A**: 使用 `toThrow` 或 `rejects.toThrow`：

```typescript
it("should throw error", () => {
  expect(() => functionThatThrows()).toThrow("Error message");
});

it("should reject promise", async () => {
  await expect(asyncFunction()).rejects.toThrow("Error");
});
```

### Q: 如何测试时间相关代码？

**A**: 使用 Jest 的 `jest.useFakeTimers()`：

```typescript
beforeEach(() => {
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

it("should timeout after 1 second", () => {
  const callback = jest.fn();
  setTimeout(callback, 1000);
  
  jest.advanceTimersByTime(1000);
  expect(callback).toHaveBeenCalled();
});
```

### Q: 测试运行很慢怎么办？

**A**: 

1. 使用 `--maxWorkers` 限制并行数
2. 使用 `--testPathIgnorePatterns` 忽略某些测试
3. 优化测试，减少不必要的异步操作
4. 使用 `--runInBand` 串行运行（调试时）

### Q: 如何调试失败的测试？

**A**: 

1. 使用 `console.log` 输出调试信息
2. 使用 `debugger` 语句（需要 Node.js 调试器）
3. 使用 `--verbose` 查看详细输出
4. 使用 `--no-coverage` 加快运行速度

```bash
# 调试模式
node --inspect-brk node_modules/.bin/jest --runInBand test-file.test.ts
```

## 持续集成

### CI/CD 配置建议

在 CI/CD 流水线中添加测试步骤：

```yaml
# GitHub Actions 示例
- name: Run tests
  run: |
    cd packages/common-all
    pnpm test --coverage

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./packages/common-all/coverage/lcov.info
```

### 预提交钩子（可选）

使用 `husky` 和 `lint-staged` 在提交前运行测试：

```json
{
  "lint-staged": {
    "packages/common-all/src/**/*.ts": [
      "pnpm test --findRelatedTests"
    ]
  }
}
```

## 参考资料

- [Jest 官方文档](https://jestjs.io/docs/getting-started)
- [ts-jest 文档](https://kulshekhar.github.io/ts-jest/)
- [Testing Best Practices](https://github.com/goldbergyoni/javascript-testing-best-practices)

## 更新日志

- **2025-01-XX**: 迁移到 ESM 模块系统，更新 Jest 配置支持 ESM
- **2025-01-XX**: 初始版本，基于现有测试框架配置编写

---

**注意**: 本文档会随着项目发展持续更新。如有问题或建议，请提交 Issue 或 Pull Request。
