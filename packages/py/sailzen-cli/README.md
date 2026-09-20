# sailzen-cli

SailZen 命令行工具。独立进程运行，可通过 `uv tool` 安装，与 `sail_server` 共享数据库结构声明（`sailzen-orm`）。

## 安装

```bash
# 从仓库 workspace 安装为全局 CLI 工具
uv tool install ./packages/py/sailzen-cli

# 验证
sailzen --version
```

## 模块

| 命令组 | 说明 |
|--------|------|
| `sailzen finance` | 财务交易管理（拉取/修改/上传 transaction） |
| `sailzen health` | 健康数据管理（体重/运动/减重计划导出分析） |
| `sailzen notes` | 本地 Markdown 笔记库管理（git 托管） |
| `sailzen note` | 服务器 NoteItem / 创作笔记同步管理 |
| `sailzen rhythm` | 生活/工作节奏综合优先级调节 |
| `sailzen vault` | 通过 Vault API Server 读写笔记 |

## 示例

```bash
sailzen finance list-accounts --server http://localhost:8000
sailzen finance pull --account 1 --server http://localhost:8000
sailzen health pull-weight --start 2026-01-01 --server http://localhost:8000
sailzen notes list --vault ./notes
sailzen note pull --id 42 --workspace ./workspace
```

## 服务器地址解析

优先级：`SAIL_SERVER_URL` 环境变量 → `.env.prod` / `.env.dev` / `.env` 中 `SERVER_HOST`+`SERVER_PORT` → `http://localhost:8000`。
