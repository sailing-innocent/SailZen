# Vault API Server 设计文档

> **状态**: 已实现  
> **版本**: 1.0  
> **日期**: 2026-05-06

## 概述

Vault API Server 是对 `@saili/engine-server`（Sail 引擎）的独立 HTTP 封装，允许在不启动 VSCode 插件的情况下，通过标准 HTTP API 对 vault（本地 Markdown 笔记库）进行读写操作。

---

## 架构

```
┌─────────────────────────────────────────────────┐
│            调用方（AI Agent / Python 脚本）        │
│                                                   │
│   sailzen/cli/vault_client.py  (Python HTTP客户端) │
└───────────────────┬─────────────────────────────┘
                    │ HTTP (localhost:3005)
                    ▼
┌─────────────────────────────────────────────────┐
│         Vault API Server                         │
│   packages/api_server/src/standalone.ts          │
│   ┌─────────────────────────────────────────┐   │
│   │  Express HTTP Server (port 3005)         │   │
│   │  路由: /api/note/*, /api/workspace/*     │   │
│   └──────────────────┬──────────────────────┘   │
│                       │                          │
│   ┌──────────────────▼──────────────────────┐   │
│   │  WorkspaceController (自动初始化)         │   │
│   │  SailEngineV3 (引擎核心)              │   │
│   └──────────────────┬──────────────────────┘   │
└──────────────────────┼──────────────────────────┘
                       │ 读写文件系统
                       ▼
┌─────────────────────────────────────────────────┐
│              Vault (本地 Markdown 文件)           │
│   $WS_ROOT/                                      │
│   ├── sail.yml                                │
│   ├── vault1/                                    │
│   │   ├── root.md                                │
│   │   ├── daily.2026-05-06.md                    │
│   │   └── ...                                    │
│   └── vault2/                                    │
└─────────────────────────────────────────────────┘
```

### 与原有架构的区别

原有架构中，`api_server` 是由 VSCode 插件作为子进程启动的，且工作区初始化需要插件手动触发：

```
vscode_plugin → (spawn) → api_server → engine-server → vault
                               ↑
                          插件手动调用
                    POST /api/workspace/initialize
```

新的 standalone 模式在启动时**自动完成工作区初始化**，无需 VSCode：

```
node lib/standalone.js
    → 启动 Express
    → 自动调用 WorkspaceController.init({ uri: WS_ROOT })
    → 就绪，接受请求
```

---

## 服务端：standalone.ts

**文件路径**: `packages/api_server/src/standalone.ts`

### 启动方式

```bash
# 开发模式（无需构建，使用 tsx）
cd packages/api_server
WS_ROOT=/path/to/vault npx tsx src/standalone.ts

# 生产模式（先构建）
pnpm --filter @saili/api-server build
WS_ROOT=/path/to/vault node lib/standalone.js

# 通过 pnpm scripts
WS_ROOT=/path/to/vault pnpm --filter @saili/api-server vault-server:dev
WS_ROOT=/path/to/vault pnpm --filter @saili/api-server vault-server

# Windows PowerShell
$env:WS_ROOT="D:/my-vault"; $env:PORT=3005
pnpm --filter @saili/api-server vault-server:dev
```

### 环境变量

| 变量 | 必须 | 默认值 | 说明 |
|------|------|--------|------|
| `WS_ROOT` | ✅ | - | vault 根目录路径（含 `sail.yml` 的目录） |
| `PORT` | ❌ | `3005` | HTTP 监听端口 |
| `LOG_DST` | ❌ | `stdout` | 日志输出路径 |

### pnpm Scripts

| 命令 | 说明 |
|------|------|
| `vault-server` | 生产模式（需先 `build`） |
| `vault-server:dev` | 开发模式（tsx，无需构建） |
| `vault-server:watch` | 开发监听模式（文件变更自动重启） |

---

## API 参考

所有笔记相关 API 都需要传入 `ws` 参数（vault 根目录路径，与启动时 `WS_ROOT` 一致）。

### 查询笔记

```http
GET /api/note/query?ws=<root>&q=<query>
```

| 参数 | 说明 |
|------|------|
| `ws` | vault 根目录路径 |
| `q` | 查询字符串，`*` 返回所有，或指定 fname 前缀 |

**响应示例**:
```json
{
  "data": [
    { "id": "abc123", "fname": "daily.2026-05-06", "title": "Daily Note", "updated": 1746512000 }
  ]
}
```

### 获取笔记完整内容

```http
GET /api/note/get?ws=<root>&id=<note-id>
```

**响应示例**:
```json
{
  "data": {
    "id": "abc123",
    "fname": "daily.2026-05-06",
    "title": "Daily Note",
    "body": "# Daily\n\n今天的内容...",
    "vault": { "fsPath": "/path/to/vault" },
    "tags": [],
    "updated": 1746512000,
    "created": 1746512000
  }
}
```

### 按条件查找笔记

```http
POST /api/note/find
Content-Type: application/json

{
  "ws": "/path/to/vault",
  "fname": "daily.2026",
  "excludeStub": true
}
```

### 写入/更新笔记

```http
POST /api/note/write
Content-Type: application/json

{
  "ws": "/path/to/vault",
  "node": {
    "id": "abc123",
    "fname": "my.new.note",
    "title": "My New Note",
    "body": "# My New Note\n\nContent here.",
    "vault": { "fsPath": "/path/to/vault/vault1" }
  },
  "opts": { "updateExisting": true }
}
```

### 删除笔记

```http
POST /api/note/delete
Content-Type: application/json

{ "ws": "/path/to/vault", "id": "abc123" }
```

### 获取 Engine 信息

```http
GET /api/note/info
```

---

## 客户端：vault_client.py

**文件路径**: `sailzen/cli/vault_client.py`

Python CLI 工具，对上述 HTTP API 的完整封装，供 AI Agent、脚本和手动调试使用。

### 配置

优先级：命令行参数 > 环境变量 > 默认值

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `VAULT_SERVER_URL` | `http://localhost:3005` | Vault API Server 地址 |
| `VAULT_WS_ROOT` | - | vault 根目录路径 |

推荐在 `.env.dev` 或 shell profile 中设置：

```bash
export VAULT_SERVER_URL=http://localhost:3005
export VAULT_WS_ROOT=/path/to/your/vault
```

### 命令速查

```bash
# 检查服务器是否在线
python sailzen/cli/vault_client.py status

# 查询所有笔记
python sailzen/cli/vault_client.py query

# 搜索 fname 前缀匹配
python sailzen/cli/vault_client.py query --q "daily.2026"

# 获取单条笔记（含正文）
python sailzen/cli/vault_client.py get --id <note-id>

# 只输出正文 Markdown（适合 AI 读取）
python sailzen/cli/vault_client.py get --id <note-id> --body-only

# 按文件名前缀查找
python sailzen/cli/vault_client.py find --fname "daily.2026"

# 写入笔记（从 JSON 文件）
python sailzen/cli/vault_client.py write --file note.json

# 删除笔记（跳过确认）
python sailzen/cli/vault_client.py delete --id <note-id> --yes
```

### 在代码中使用 VaultClient

```python
from sailzen.cli.vault_client import VaultClient

client = VaultClient(
    server_url="http://localhost:3005",
    ws_root="/path/to/vault",
)

# 查询所有笔记
notes = client.query("*")

# 获取单条笔记
note = client.get("abc123")
print(note["body"])

# 查找特定笔记
daily_notes = client.find_meta(fname="daily.2026")

# 写入笔记
client.write({
    "id": "newid123",
    "fname": "ai.generated.note",
    "title": "AI Generated Note",
    "body": "# Content\n\nGenerated by AI.",
    "vault": {"fsPath": "/path/to/vault/vault1"},
})
```

---

## 完整工作流示例

### 启动服务器 + AI 读写笔记

```bash
# 终端 1: 启动 Vault API Server
$env:WS_ROOT="D:/my-vault"
pnpm --filter @saili/api-server vault-server:dev

# 终端 2: 使用 Python 客户端
$env:VAULT_WS_ROOT="D:/my-vault"
python sailzen/cli/vault_client.py status
python sailzen/cli/vault_client.py query
python sailzen/cli/vault_client.py get --id <id> --body-only
```

---

## 依赖关系

```
vault_client.py (Python)
    └── requests

standalone.ts (TypeScript)
    ├── @saili/api-server    (Express 路由层)
    │   ├── @saili/engine-server  (SailEngineV3)
    │   │   ├── @saili/common-all
    │   │   ├── @saili/common-server
    │   │   └── @saili/unified
    │   └── express
```

---

## 已知限制

1. **Vault 初始化**：服务器启动时只初始化一次 vault，如果 vault 文件在外部被修改，需要调用 `POST /api/workspace/initialize` 重新加载（或重启服务器）。
2. **单 vault 模式**：当前启动命令通过 `WS_ROOT` 只能初始化一个工作区；如需多工作区，可在服务器启动后额外调用 `/api/workspace/initialize`。
3. **认证**：当前没有 API 认证，仅适合本地使用，不建议暴露到公网。
