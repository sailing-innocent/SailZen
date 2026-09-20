# SailZen

A personal knowledge management and productivity tool based on VSCode extension.

## sail_server/site maintain

## Android App Maintain

## Vscode-Plugin Maintain

```bash
pnpm version:patch
pnpm build-plugin
pnpm package-plugin
``` 

## SailZen CLI

SailZen CLI 已拆分为独立工具包 `packages/py/sailzen-cli`，与主服务共享数据库结构声明（`packages/py/sailzen-orm`）。基于 [click](https://click.palletsprojects.com/) 构建，独立进程运行，无需启动服务。

### 安装（uv tool）

```bash
# 从本地仓库安装为全局 CLI 工具（独立进程，不依赖仓库环境）
uv tool install --from ./packages/py/sailzen-cli sailzen-cli

# 验证
sailzen --version
```

> `uv tool` 会创建隔离环境并暴露 `sailzen` 命令到 PATH，可在任意目录（如笔记 vault 中）直接调用。
> CLI 与 `sail_server` 通过 HTTP API 交互，服务器地址解析顺序：`SAIL_SERVER_URL` 环境变量 → 当前目录 `.env.prod`/`.env.dev`/`.env` 的 `SERVER_HOST`+`SERVER_PORT` → `http://localhost:8000`。

### 升级 / 卸载

```bash
uv tool upgrade sailzen-cli
uv tool uninstall sailzen-cli
```

### 常用命令

```bash
sailzen finance list-accounts --server http://localhost:8000
sailzen finance pull --account 1 --server http://localhost:8000
sailzen health pull-weight --start 2026-01-01
sailzen notes list --vault ./notes
sailzen note list --category character
sailzen rhythm capture "每周运动3次" --json
```

### 开发模式（仓库内运行）

```bash
uv run --package sailzen-cli sailzen --help
```

