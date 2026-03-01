# 开发指南

## 环境准备

### 依赖安装

```bash
# 安装所有依赖
pnpm install

# 安装插件依赖
pnpm install-plugin

# 安装网站依赖
pnpm install-site

# Python 依赖
uv sync
```

### 环境配置

基于 `.env.template` 创建：
- `.env.dev` - 开发环境
- `.env.prod` - 生产环境

必需变量：
```bash
SERVER_PORT=4399
POSTGRE_URI=postgresql:///main
GOOGLE_API_KEY=...
OPENAI_API_KEY=...
```

## 常用命令

### TypeScript

```bash
# 构建包及其依赖
pnpm run build-with-deps @saili/engine-server

# 构建插件
pnpm run build-plugin

# 构建网站
pnpm run build-site

# 版本管理
node scripts/bump-version.js patch
```

### Python

```bash
# 运行服务器
uv run server.py

# 运行任务
uv run main.py --task <task_name>

# 导入文本
uv run python .agents/skills/sailzen-ai-text-import/scripts/import_with_ai.py <file.txt>
```

### 测试

```bash
# TypeScript 测试
pnpm test

# Python 测试
uv run pytest
```

## Windows PowerShell 注意事项

- 使用 `;` 而不是 `&&` 连接命令
- 设置环境变量: `$env:VAR="value"`
- 修复编码: `chcp 65001`

## 新功能快速参考

### 大纲提取 V2 (Checkpoint-Resume)

- [快速参考](./outline-extraction-v2-quickstart.md)
- [完整设计文档](../design/outline-extraction-v2.md)
- [数据库迁移指南](../../sail_server/migration/README_outline_checkpoint.md)

**一键升级**:
```bash
psql -U postgres -d sailzen -f sail_server/migration/add_outline_extraction_checkpoints.sql
uv run server.py
pnpm run build-site
```
