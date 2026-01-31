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
│   ├── logger.ts           # 日志系统
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
  --sources-content=true
```

> **注意**: `--sourcemap=inline` 和 `--sources-content=true` 确保调试时可以在 TypeScript 源码中设置断点。

## 调试流程

### 快速开始

1. 在 VSCode 中打开项目根目录
2. 按 `F5` 或在调试面板选择 "Run Extension"
3. 等待扩展开发主机窗口打开
4. 在新窗口中测试插件功能

### 调试配置

项目已配置 `.vscode/launch.json`，提供以下调试模式：

| 配置名称 | 说明 |
|---------|------|
| **Run Extension** | 启动监听模式并调试（推荐） |
| **Run Extension (No Watch)** | 不启动监听，直接调试已编译代码 |
| **Run Extension (Production)** | 模拟生产环境调试 |
| **Run Web Extension** | Web 扩展调试 |

### VSCode 任务

通过 `Ctrl+Shift+B` 或命令面板 `Tasks: Run Task` 执行：

| 任务名称 | 说明 |
|---------|------|
| `watch-plugin` | 监听模式编译（后台运行） |
| `compile-plugin` | 一次性编译（默认构建任务） |
| `build-plugin` | 完整构建 |
| `precompile-deps` | 预编译依赖包 |
| `package-plugin` | 打包 .vsix 文件 |
| `clean-plugin` | 清理构建产物 |

### 断点调试

#### 设置断点

1. 在 TypeScript 源码中点击行号左侧设置断点
2. 启动调试 (F5)
3. 在扩展开发主机中触发相关功能
4. 断点会在源码位置命中

#### 条件断点

右键断点可设置条件：
- **条件表达式**: 如 `opts.fname === 'test'`
- **命中次数**: 如 `> 5` (第5次后才中断)
- **日志消息**: 不中断，仅输出日志

#### 调试控制台

在断点处可以：
- 查看和修改变量值
- 执行表达式
- 调用函数进行测试

### 环境变量

调试时自动设置的环境变量：

| 变量名 | 值 | 说明 |
|-------|-----|------|
| `VSCODE_DEBUGGING_EXTENSION` | `true` | 标识开发调试模式 |
| `LOG_LEVEL` | `debug` | 日志级别 |

开发模式下：
- `VSCodeUtils.isDevMode()` 返回 `true`
- 设置 `dendron:devMode` 上下文
- 显示仅开发时可见的命令（如 `Dendron:Dev: Dev Trigger`）

## 日志系统

### Logger 类

插件使用自定义 `Logger` 类（位于 `src/logger.ts`）进行日志记录。

### 日志级别

| 级别 | 方法 | 说明 |
|-----|------|------|
| debug | `Logger.debug()` | 详细调试信息 |
| info | `Logger.info()` | 普通信息（可选显示通知） |
| warn | `Logger.warn()` | 警告（不上报 Sentry） |
| error | `Logger.error()` | 错误（显示错误提示） |

### 使用示例

```typescript
import { Logger } from "./logger";

// 基本日志
Logger.debug({ ctx: "MyCommand", msg: "调试信息" });
Logger.info({ ctx: "MyCommand", msg: "操作完成" });
Logger.warn({ ctx: "MyCommand", msg: "配置可能有问题" });

// 错误日志
Logger.error({ 
  ctx: "MyCommand", 
  msg: "操作失败",
  error: someError 
});

// 带额外数据
Logger.info({ 
  ctx: "MyCommand:execute",
  msg: "处理笔记",
  noteId: note.id,
  vault: note.vault.fsPath
});
```

### 日志查看位置

#### 1. VSCode 输出面板

1. 打开 `查看 > 输出` 或按 `Ctrl+Shift+U`
2. 在下拉菜单中选择 **"Dendron"**
3. 实时查看日志输出

#### 2. 日志文件

通过命令打开日志文件：
1. `Ctrl+Shift+P` 打开命令面板
2. 输入 `Dendron:Dev: Open Logs`
3. 自动打开 `dendron.log` 文件

日志文件位置：`{VSCode日志目录}/dendron.log`

#### 3. 开发者工具控制台

1. 在扩展开发主机窗口中
2. `帮助 > 切换开发人员工具` 或 `Ctrl+Shift+I`
3. 切换到 **Console** 标签页
4. 查看 `console.log` 输出

### 日志级别配置

在 VSCode 设置中配置：

```json
{
  "dendron.logLevel": "debug"  // "debug" | "info" | "error"
}
```

或在 `settings.json` 中：

```json
{
  "dendron.logLevel": "debug",
  "dendron.trace.server": "verbose"  // LSP 日志级别
}
```

### 日志最佳实践

```typescript
// 1. 使用 ctx 标识上下文
Logger.info({ ctx: "ClassName:methodName", msg: "..." });

// 2. 记录函数入口和出口
async execute(opts: MyOpts) {
  const ctx = "MyCommand:execute";
  Logger.info({ ctx, msg: "enter", opts });
  
  // ... 业务逻辑 ...
  
  Logger.info({ ctx, msg: "done", result });
  return result;
}

// 3. 错误处理
try {
  // ...
} catch (err) {
  Logger.error({ 
    ctx, 
    msg: "操作失败",
    error: err instanceof Error ? err : new Error(String(err))
  });
  throw err;
}

// 4. 调试时临时日志
if (Logger.isDebug()) {
  Logger.debug({ ctx, msg: "详细状态", state: complexObject });
}
```

## 开发者工具使用

### 打开开发者工具

在扩展开发主机窗口中：
- 快捷键: `Ctrl+Shift+I` (Windows/Linux) 或 `Cmd+Option+I` (Mac)
- 菜单: `帮助 > 切换开发人员工具`

### Console 面板

- 查看 `console.log()` 输出
- 查看错误堆栈
- 执行 JavaScript 代码

### Network 面板

- 监控 API 请求
- 查看请求/响应数据
- 分析性能问题

### Sources 面板

- 查看加载的脚本
- 在 JavaScript 层面设置断点
- 查看调用堆栈

### Application 面板

- 查看扩展存储（globalState、workspaceState）
- 清除缓存数据

## 开发命令

### 开发相关命令

| 命令 | 快捷键 | 说明 |
|------|--------|------|
| `Dendron:Dev: Open Logs` | - | 打开日志文件 |
| `Dendron:Dev: Dev Trigger` | - | 开发触发器（仅 devMode） |
| `Dendron:Dev: Dump State` | - | 导出引擎状态 |
| `Dendron:Dev: Diagnostics Report` | - | 生成诊断报告 |
| `Dendron:Dev: Reset Config` | - | 重置配置 |
| `Dendron: Doctor` | - | 诊断并修复问题 |

### 常用开发快捷键

| 操作 | 快捷键 |
|------|--------|
| 重新加载窗口 | `Ctrl+Shift+P` > "Developer: Reload Window" |
| 重启扩展主机 | `Ctrl+Shift+P` > "Developer: Restart Extension Host" |
| 打开开发者工具 | `Ctrl+Shift+I` |

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
import { Logger } from "../logger";

type MyCommandOpts = {
  fname: string;
};

export class MyCommand extends BasicCommand<MyCommandOpts, void> {
  key = "dendron.myCommand";

  async execute(opts: MyCommandOpts): Promise<void> {
    const ctx = "MyCommand:execute";
    Logger.info({ ctx, msg: "enter", opts });
    
    // 实现逻辑
    
    Logger.info({ ctx, msg: "done" });
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

1. 确保已完成编译 (`dist/extension.js` 存在)
2. 检查 VSCode 输出面板错误信息
3. 尝试重新加载窗口

### 断点不生效

1. 确保使用 `--sourcemap=inline` 编译
2. 检查 `launch.json` 中的 `outFiles` 路径
3. 尝试在 JavaScript 文件中设置断点确认

### 日志不显示

1. 检查 `dendron.logLevel` 设置
2. 确认选择了正确的输出通道 "Dendron"
3. 检查 Logger 是否正确初始化

### 扩展激活失败

1. 查看输出面板 "Dendron" 和 "Extension Host" 的错误
2. 打开开发者工具查看 Console 错误
3. 检查依赖包是否正确构建

## 调试技巧

### 1. 快速重载

修改代码后，在扩展开发主机中按 `Ctrl+Shift+P`，执行 "Developer: Reload Window"。

### 2. 日志断点

在断点上右键选择 "Log Message"，输入如 `Value: {myVar}`，无需中断即可记录变量值。

### 3. 监视表达式

在调试面板的 "Watch" 区域添加表达式，实时监视变量变化。

### 4. 调用堆栈导航

在 "Call Stack" 面板点击不同帧，快速跳转到调用位置。

### 5. 异常断点

在断点面板勾选 "Uncaught Exceptions"，自动在未捕获异常处中断。

## 相关文档

- [源码结构](./source.md)
- [设计概述](../../design/plugin/overview.md)
- [Vault 结构](../../design/plugin/vault.md)
