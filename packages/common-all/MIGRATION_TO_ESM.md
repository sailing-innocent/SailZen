# ESM 迁移说明

## 概述

`@saili/common-all` 包已成功从 CommonJS 迁移到 ESM (ECMAScript Modules)。本文档记录了迁移过程中的所有更改。

## 迁移日期

2025-01-XX

## 主要更改

### 1. package.json

- ✅ 添加 `"type": "module"` 声明使用 ESM
- ✅ 更新 `main` 字段为 `"./lib/index.js"`（添加相对路径）
- ✅ 添加 `exports` 字段，提供标准的模块导出接口
- ✅ 更新 `engines.node` 要求为 `>=18.0.0`（ESM 需要 Node.js 14+，但推荐 18+）
- ✅ 添加 `cross-env` 作为开发依赖（用于跨平台环境变量设置）
- ✅ 更新测试脚本使用 `NODE_OPTIONS=--experimental-vm-modules`

### 2. TypeScript 配置

#### tsconfig.json
- ✅ `module`: `"commonjs"` → `"ESNext"`
- ✅ 添加 `moduleResolution`: `"bundler"`

#### tsconfig.build.json
- ✅ 覆盖 `module`: `"ESNext"`
- ✅ 覆盖 `moduleResolution`: `"bundler"`

### 3. Jest 配置

- ✅ 重命名 `jest.config.js` → `jest.config.mjs`（支持 ESM）
- ✅ 使用 `ts-jest/presets/default-esm` 预设
- ✅ 启用 `extensionsToTreatAsEsm: [".ts"]`
- ✅ 设置 `useESM: true` 在 transform 配置中
- ✅ 添加 `moduleNameMapper` 处理文件扩展名映射
- ✅ 删除不再需要的 ESM 包 mock（`github-slugger`, `nanoid` 等）

### 4. 删除的文件

- ❌ `jest.config.js`（已替换为 `jest.config.mjs`）
- ❌ `src/__mocks__/github-slugger.ts`（不再需要）
- ❌ `src/__mocks__/nanoid.ts`（不再需要）
- ❌ `src/__mocks__/nanoid-non-secure.ts`（不再需要）

### 5. 文档更新

- ✅ 更新 `TESTING.md` 反映 ESM 配置
- ✅ 删除 ESM 依赖处理章节（不再需要 mock）
- ✅ 更新配置示例和说明

## 验证结果

### 测试
```bash
✅ Test Suites: 1 passed, 1 total
✅ Tests:       30 passed, 30 total
```

### 编译
```bash
✅ TypeScript 编译成功，无错误
```

## 兼容性说明

### VSCode 插件兼容性

`vscode-plugin` 包使用 `esbuild` 打包，配置为：
```bash
esbuild --format=cjs --bundle
```

即使 `common-all` 是 ESM，`esbuild` 会将其打包成 CommonJS，因此完全兼容。

### 其他包的影响

如果其他包依赖 `@saili/common-all`，需要确保：
1. 使用 `import` 语法而不是 `require()`
2. Node.js 版本 >= 18.0.0
3. 如果使用 TypeScript，配置支持 ESM

## 注意事项

1. **实验性警告**: Jest 的 ESM 支持仍在实验阶段，运行测试时可能会看到警告：
   ```
   ExperimentalWarning: VM Modules is an experimental feature
   ```
   这是正常的，不影响功能。

2. **文件扩展名**: TypeScript 中导入时不需要 `.js` 扩展名，但编译后的代码会包含正确的扩展名。

3. **Node.js 版本**: 项目现在要求 Node.js >= 18.0.0。

## 后续工作

- [ ] 监控 Jest ESM 支持的稳定性
- [ ] 考虑移除 `--experimental-vm-modules` 标志（当 Jest 正式支持时）
- [ ] 更新其他相关包的配置（如果需要）

## 参考资源

- [Node.js ESM 文档](https://nodejs.org/api/esm.html)
- [Jest ESM 支持](https://jestjs.io/docs/ecmascript-modules)
- [TypeScript ESM 配置](https://www.typescriptlang.org/docs/handbook/esm-node.html)
