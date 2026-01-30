# SailZen VSCode插件 开发环境

## 环境要求

### 系统要求
- **Node.js**: >= 18.0.0
- **pnpm**: >= 8.0.0 (包管理器)
- **VSCode**: >= 1.107.0

### 推荐工具
- VSCode + 官方 TypeScript 扩展
- ESLint 扩展
- Git

## 项目结构

```
packages/vscode_plugin/
├── src/                    # 源代码
│   ├── extension.ts        # 入口文件
│   ├── _extension.ts       # 核心激活逻辑
│   ├── commands/           # 命令实现
│   ├── features/           # 语言特性
│   ├── services/           # 核心服务
│   ├── views/              # 视图实现
│   └── workspace/          # 工作区管理
├── scripts/                # 构建脚本
│   ├── fix-import-meta.js  # 修复 import.meta 兼容性
│   ├── copy-prisma-assets.js # 复制 Prisma 资源
│   └── genConfig.ts        # 生成配置
├── assets/                 # 静态资源
├── media/                  # 图标、字体
├── dist/                   # 构建输出
├── package.json            # 扩展清单
├── tsconfig.json           # TypeScript 配置
└── .eslintrc.json          # ESLint 配置
```

## 安装依赖

在项目根目录执行：

```bash
# 安装所有依赖
pnpm install

# 或者只安装插件依赖
cd packages/vscode_plugin
pnpm install
```

## 编译流程

### 完整构建

```bash
pnpm run build
```

构建过程：
1. **预编译** - 构建依赖包 `@saili/engine-server`
2. **编译** - 使用 esbuild 打包 TypeScript
3. **后处理** - 修复 `import.meta.url` 兼容性
4. **资源复制** - 复制 Prisma 客户端文件

### 增量编译

```bash
pnpm run compile
```

### 监听模式

开发时推荐使用监听模式，自动重新编译：

```bash
pnpm run watch
```

### 构建配置

esbuild 配置：

```javascript
esbuild src/extension.ts
  --bundle
  --outfile=dist/extension.js
  --platform=node
  --external:vscode
  --external:better-sqlite3
  --external:unist
  --external:mdast
  --format=cjs
  --sourcemap=inline
```

## 调试流程

### 启动调试

1. 在 VSCode 中打开项目
2. 按 `F5` 启动扩展开发主机
3. 在新窗口中测试插件功能

### 调试配置

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Run Extension",
      "type": "extensionHost",
      "request": "launch",
      "args": [
        "--extensionDevelopmentPath=${workspaceFolder}/packages/vscode_plugin"
      ],
      "outFiles": [
        "${workspaceFolder}/packages/vscode_plugin/dist/**/*.js"
      ],
      "preLaunchTask": "npm: watch"
    }
  ]
}
```

### 查看日志

- **输出面板**: `查看 > 输出 > Dendron`
- **开发者工具**: `帮助 > 切换开发人员工具`
- **日志文件**: 通过 `Dendron:Dev: Open Logs` 命令

## 测试流程

### 单元测试

```bash
pnpm test
```

### 集成测试

在扩展开发主机中手动测试：

1. 创建测试工作区
2. 执行各命令验证功能
3. 检查日志输出

## 发布流程

### 打包

```bash
pnpm run package
```

生成 `.vsix` 文件。

### 发布到市场

```bash
# 使用 vsce 发布
npx vsce publish
```

### 版本管理

在 `package.json` 中更新版本号：

```json
{
  "version": "0.2.3"
}
```

遵循语义化版本规范：
- **主版本号**: 不兼容的 API 变更
- **次版本号**: 向后兼容的功能新增
- **修订号**: 向后兼容的问题修正

## 开发规范

### TypeScript 配置

```json
{
  "compilerOptions": {
    "target": "ES2024",
    "module": "CommonJS",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

### 代码风格

- 使用 ESLint 进行代码检查
- 遵循项目 `.eslintrc.json` 配置
- 使用 Prettier 格式化代码

### 命令开发

新建命令需要：

1. 在 `src/commands/` 下创建命令类
2. 继承 `BasicCommand` 基类
3. 在 `src/commands/index.ts` 中注册
4. 在 `package.json` 中声明命令

```typescript
// src/commands/MyCommand.ts
import { BasicCommand } from "./base";

export class MyCommand extends BasicCommand<MyOpts, void> {
  key = "dendron.myCommand";

  async execute(opts: MyOpts): Promise<void> {
    // 实现逻辑
  }
}
```

## 常见问题

### 依赖安装失败

```bash
# 清理并重新安装
pnpm run clean
pnpm install
```

### 编译错误

1. 确保已构建依赖包
2. 检查 TypeScript 版本兼容性
3. 运行 `pnpm run precompile` 预编译依赖

### 调试无法启动

1. 确保已完成编译
2. 检查 `dist/extension.js` 是否存在
3. 查看 VSCode 输出面板错误信息

## 相关文档

- [源码结构](./source.md)
- [设计概述](../../design/plugin/overview.md)
- [Vault 结构](../../design/plugin/vault.md)
