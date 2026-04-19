# SailZen VSCode Plugin Test Setup

> 禁止直接调用 jest.cmd。统一使用 pnpm 命令运行测试。

## 运行测试

### 从项目根目录
```bash
# 运行 vscode_plugin 全部测试
pnpm run test:vscode-plugin
```

### 从 vscode_plugin 目录
```bash
cd packages/vscode_plugin
pnpm test
```

### 运行特定测试文件
```bash
cd packages/vscode_plugin
pnpm test -- src/docEngine/__tests__/profileResolver.test.ts
```

### 带参数运行（必须在目录内）
```bash
cd packages/vscode_plugin
pnpm exec jest --no-cache --verbose
pnpm exec jest --watch
```

> ⚠️ **注意**: 从根目录通过 `pnpm run test:vscode-plugin -- --args` 传递参数时，pnpm 会将 `--` 也传给 jest，导致 jest 将后续参数解释为 testPathPattern 而非选项。因此带参数时请务必 cd 到 `packages/vscode_plugin` 目录内执行。

## 关键配置说明

### Jest 配置 (`packages/vscode_plugin/jest.config.mjs`)

- **不使用 `--experimental-vm-modules`**: ts-jest 的 `useESM: true` 已能处理 ESM 转换，无需 Node.js 实验性 ESM 标志。
- **ts-jest 使用 `tsconfig.test.json`**: 该配置文件继承 `tsconfig.json` 并覆盖：
  - `"module": "ESNext"`
  - `"moduleResolution": "bundler"`
  - `"allowJs": true`（关键！用于转换 `common-all/lib/index.js` 等编译后的 ESM `.js` 文件）
- **`transformIgnorePatterns` 必须包含 `@saili/common-all`**: `common-all` 通过 pnpm workspace 软链接到 `node_modules`，默认会被 Jest 忽略转换。必须显式排除：
  ```js
  transformIgnorePatterns: [
    "node_modules/(?!.*(github-slugger|nanoid|vscode-uri|@saili/common-all))",
  ]
  ```
- **不使用 `@saili/common-all` 的 `moduleNameMapper`**: 让 Jest 通过 pnpm 软链接自然解析到 `node_modules/@saili/common-all`，然后由 ts-jest 转换其 ESM `.js` 输出。

### 跨包 ESM 依赖处理

`@saili/common-all` 是 ESM 包（`"type": "module"`），其 `lib/index.js` 是编译后的 ESM。Jest 需要：
1. `transformIgnorePatterns` 不忽略它
2. ts-jest 匹配 `.js` 文件并启用 `allowJs`
3. `moduleNameMapper` 中的 `"^(\\.{1,2}/.*)\\.js$": "$1"` 处理相对路径 `.js` 扩展名

### 历史问题与修复

| 问题 | 原因 | 修复 |
|------|------|------|
| `SyntaxError: Cannot use import statement outside a module` | `common-all/lib/index.js` 未被 ts-jest 转换（被 `transformIgnorePatterns` 忽略） | 将 `@saili/common-all` 加入 `transformIgnorePatterns` 例外 |
| `ReferenceError: exports is not defined` | `.tsx?$` transform 使用 `tsconfig.json`（`"module": "commonjs"`），在 ESM 上下文中输出 CJS | 统一使用 `tsconfig.test.json`（`"module": "ESNext"`） |
| `ts-jest[ts-compiler] (WARN) allowJs` | `tsconfig.test.json` 缺少 `allowJs: true` | 添加 `"allowJs": true` |
| `ReferenceError: jest is not defined` | `NODE_OPTIONS=--experimental-vm-modules` 下 jest 不作为全局变量 | 移除 `--experimental-vm-modules`，恢复 jest 全局 |

## 禁止事项

- ❌ 禁止直接调用 `packages/vscode_plugin/node_modules/.bin/jest.cmd`
- ❌ 禁止从根目录用 `pnpm run test:vscode-plugin -- --args` 传参
- ❌ 禁止在 `moduleNameMapper` 中将 `@saili/common-all` 直接映射到源码路径（绕过 `"type": "module"` 上下文）
