# SailZen Monorepo 测试框架

本文档描述了 SailZen monorepo 的统一测试框架配置和使用方法。

## 概述

测试框架基于以下技术栈：
- **Jest** (v30+) - 测试运行器
- **ts-jest** (v29+) - TypeScript 支持
- **ESM** - 原生 ES 模块支持

## 目录结构

```
SailZen/
├── jest.config.base.mjs          # 共享的 Jest 基础配置
├── TESTING.md                    # 本文档
├── packages/
│   ├── common-all/
│   │   ├── jest.config.mjs       # 继承基础配置
│   │   ├── src/
│   │   │   └── __tests__/        # 测试文件目录
│   │   │       └── *.test.ts
│   │   └── tsconfig.build.json   # 排除测试文件
│   ├── common-server/
│   │   ├── jest.config.mjs
│   │   ├── src/
│   │   │   └── __tests__/
│   │   │       └── *.test.ts
│   │   └── tsconfig.build.json
│   └── unified/
│       ├── jest.config.mjs
│       ├── src/
│       │   ├── __tests__/
│       │   │   ├── fixtures/     # 测试数据和 mock
│       │   │   ├── utils/        # 测试辅助函数
│       │   │   └── *.test.ts
│       │   ├── remark/
│       │   │   └── __tests__/    # remark 插件测试
│       │   └── rehype/
│       │       └── __tests__/    # rehype 插件测试
│       └── tsconfig.build.json
```

## 测试文件规范

### 命名约定

- 测试文件必须以 `.test.ts` 结尾
- 测试文件放置在对应模块的 `__tests__` 目录中
- 测试辅助文件放在 `__tests__/utils/` 目录
- 测试数据和 fixtures 放在 `__tests__/fixtures/` 目录

### 测试模式匹配

基础配置只匹配以下模式的测试文件：

```
**/src/**/__tests__/**/*.test.ts
**/src/**/__tests__/**/*.test.tsx
```

## 运行测试

### 运行所有包的测试

```bash
# 在根目录运行
pnpm test
```

### 运行特定包的测试

```bash
# 运行 common-all 包的测试
pnpm test:common-all

# 运行 common-server 包的测试
pnpm test:common-server

# 运行 unified 包的测试
pnpm test:unified
```

### 在包目录中运行

```bash
# 进入包目录
cd packages/common-all

# 运行测试
pnpm test

# 监视模式
pnpm test:watch

# 生成覆盖率报告
pnpm test:coverage
```

### 运行特定测试文件

```bash
# 在包目录中
pnpm test -- --testPathPattern="files.test.ts"

# 或者运行特定 describe 块
pnpm test -- --testNamePattern="cleanFileName"
```

## Jest 配置

### 基础配置 (jest.config.base.mjs)

所有包都继承根目录的 `jest.config.base.mjs`，主要配置包括：

- **preset**: `ts-jest/presets/default-esm` - 支持 ESM 的 TypeScript 预设
- **testEnvironment**: `node` - Node.js 测试环境
- **transform**: 使用 ts-jest 转换 TypeScript 文件
- **moduleNameMapper**: 处理 ESM 导入扩展名

### 包级配置

每个包的 `jest.config.mjs` 继承基础配置并可添加包特定的覆盖：

```javascript
import baseConfig from "../../jest.config.base.mjs";

export default {
  ...baseConfig,
  displayName: "package-name",
  // 包特定的配置覆盖
};
```

## 编写测试

### 基本测试结构

```typescript
import { functionToTest } from "../module.js";

describe("ModuleName", () => {
  describe("functionToTest", () => {
    it("should do something specific", () => {
      const result = functionToTest("input");
      expect(result).toBe("expected");
    });

    it("should handle edge cases", () => {
      expect(() => functionToTest(null)).toThrow();
    });
  });
});
```

### 异步测试

```typescript
describe("asyncFunction", () => {
  it("should resolve with expected value", async () => {
    const result = await asyncFunction();
    expect(result).toBe("expected");
  });

  it("should reject with error", async () => {
    await expect(asyncFunction("invalid")).rejects.toThrow("error message");
  });
});
```

### 使用 Fixtures

```typescript
import { createTestNote } from "./fixtures/testNotes";

describe("NoteProcessor", () => {
  it("should process note correctly", () => {
    const note = createTestNote({ body: "test content" });
    const result = processNote(note);
    expect(result).toContain("test content");
  });
});
```

### Setup 和 Teardown

```typescript
describe("FileOperations", () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "test-"));
  });

  afterEach(() => {
    if (fs.existsSync(tempDir)) {
      fs.removeSync(tempDir);
    }
  });

  it("should create file in temp directory", () => {
    // 使用 tempDir
  });
});
```

## 覆盖率

### 配置

覆盖率收集配置在基础配置中：

```javascript
collectCoverageFrom: [
  "src/**/*.{ts,tsx}",
  "!src/**/*.d.ts",
  "!src/**/__tests__/**",
  "!src/**/index.ts",
],
coverageThreshold: {
  global: {
    branches: 10,
    functions: 10,
    lines: 10,
    statements: 10,
  },
},
```

### 运行覆盖率报告

```bash
# 所有包
pnpm test:coverage

# 特定包
cd packages/common-all
pnpm test:coverage
```

覆盖率报告生成在 `coverage/` 目录中：
- `coverage/lcov-report/index.html` - HTML 报告
- `coverage/lcov.info` - LCOV 格式

### 覆盖率目标

| 阶段 | 目标 |
|------|------|
| 当前 | 10%  |
| 短期 | 30%  |
| 中期 | 60%  |
| 长期 | 80%+ |

## ESM 注意事项

### NODE_OPTIONS

由于使用 ESM，运行测试需要设置 `NODE_OPTIONS=--experimental-vm-modules`：

```bash
pnpm exec cross-env NODE_OPTIONS=--experimental-vm-modules jest
```

这已在各包的 `package.json` 中配置好。

### 导入语法

测试文件中导入源文件时，使用 `.js` 扩展名：

```typescript
// 正确
import { someFunction } from "../module.js";

// 错误 (可能无法正确解析)
import { someFunction } from "../module";
```

Jest 配置中的 `moduleNameMapper` 会处理扩展名映射。

## TypeScript 配置

### tsconfig.build.json

每个包的 `tsconfig.build.json` 必须排除测试文件，以避免编译到输出目录：

```json
{
  "exclude": [
    "node_modules",
    "**/*-spec.ts",
    "**/*.test.ts",
    "**/__tests__/**/*",
    "**/*.d.ts"
  ]
}
```

### tsconfig.json

开发时的 `tsconfig.json` 应包含 jest 类型：

```json
{
  "compilerOptions": {
    "types": ["node", "jest"]
  }
}
```

## 最佳实践

### 1. 测试组织

- 每个源文件对应一个测试文件
- 使用 `describe` 块组织相关测试
- 测试描述使用 "should ..." 格式

### 2. 测试隔离

- 每个测试应该独立运行
- 使用 `beforeEach`/`afterEach` 管理状态
- 避免测试间共享可变状态

### 3. Mock 和 Stub

```typescript
// Mock 模块
jest.mock("../dependency", () => ({
  dependencyFunction: jest.fn(),
}));

// Spy on 方法
const spy = jest.spyOn(object, "method");
expect(spy).toHaveBeenCalledWith("arg");
```

### 4. 断言

- 使用最具体的断言
- 测试预期行为，而非实现细节
- 确保测试失败时提供有用的错误信息

## 常见问题

### Q: 测试找不到模块？

A: 检查以下几点：
1. 导入路径是否正确（包括 `.js` 扩展名）
2. `tsconfig.json` 中的 `types` 是否包含 `jest`
3. 是否运行了 `pnpm install`

### Q: ESM 相关错误？

A: 确保：
1. `NODE_OPTIONS=--experimental-vm-modules` 已设置
2. `package.json` 中有 `"type": "module"`
3. Jest 配置使用了正确的 ESM 预设

### Q: 测试文件未被发现？

A: 检查：
1. 文件是否在 `__tests__` 目录中
2. 文件名是否以 `.test.ts` 结尾
3. Jest 配置的 `testMatch` 模式是否正确

## 参考资源

- [Jest 文档](https://jestjs.io/docs/getting-started)
- [ts-jest 文档](https://kulshekhar.github.io/ts-jest/)
- [ESM in Jest](https://jestjs.io/docs/ecmascript-modules)
