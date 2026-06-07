---
name: sailzen-cli
description: SailZen CLI 工具使用指南。通过 sailzen 命令行工具与远程 sail_server 交互，支持财务交易（transaction）的拉取/编辑/上传工作流。适用于需要批量修改交易记录、导出 CSV 离线编辑后回传等场景。
---

# SailZen CLI Skill

你是一个 SailZen CLI 工具的使用专家。核心工作流：**通过 HTTP API 从远程 sail_server 拉取数据 → 导出 CSV 供用户编辑 → 将修改后的 CSV 推送回服务器**。

`sailzen` 是一个通过 `uv tool install -e .` 安装的命令行工具，不直接连接数据库，所有操作通过 HTTP API 完成。

## 何时使用此 Skill

- 用户需要批量查看或修改财务交易（transaction）记录
- 用户提到 "sailzen"、"finance client"、"导出交易"、"修改交易" 等关键词
- 用户需要从远程服务器拉取 account 的 transaction 数据
- 用户编辑完 CSV 后需要将修改推送回服务器
- 用户想查看远程服务器上有哪些 account

## 安装

```bash
# 在 SailZen 项目根目录下
uv tool install -e .
```

安装后 `sailzen` 命令即可全局使用。

## 命令结构

```
sailzen <module> <command> [options]
```

当前支持的模块：
- `finance` — 财务交易管理

## 服务器地址

`sailzen` 会自动解析远程 sail_server 地址，**无需每次手动指定 `--server`**。

### 地址解析优先级（从高到低）

1. **`--server` 参数** — 命令行显式传入，最高优先级
2. **`SAIL_SERVER_URL` 环境变量**
3. **`.env.prod` 文件** — 读取 `SERVER_HOST` 和 `SERVER_PORT`（推荐，项目根目录下）
4. **`.env.dev` 文件** — 同上，`.env.prod` 不存在时回退
5. **`.env` 文件** — 同上，前两者都不存在时回退
6. **默认回退** — `http://localhost:8000`

### `.env.prod` 格式示例

在项目根目录放置 `.env.prod`：

```env
SERVER_HOST=192.168.1.100
SERVER_PORT=8000
```

`sailzen` 会自动拼接为 `http://192.168.1.100:8000`。

### 显式指定服务器地址

如需临时连接到其他服务器，使用 `--server` 参数覆盖：

```bash
--server http://<host>:<port>
```

## Finance 模块

### 子命令一览

| 命令 | 别名 | 说明 |
|------|------|------|
| `list-accounts` | `la` | 列出远程服务器上的所有账户 |
| `pull` | — | 拉取 transaction 记录并导出为 CSV |
| `push` | — | 从 CSV 读取修改并推送回服务器 |
| `create-from-csv` | `create` | 从 CSV 创建新 transaction（id 为空或缺失的行） |

### list-accounts — 列出账户

```bash
sailzen finance list-accounts
# 或使用别名
sailzen finance la

# 临时指定其他服务器
sailzen finance list-accounts --server http://192.168.1.100:8000
```

输出示例：
```
    ID  Name                            Balance  State
-----------------------------------------------------------------
     1  日常消费账户                      12345.67       1
     2  储蓄账户                         50000.00       1
```

### pull — 拉取交易并导出 CSV

```bash
# 拉取 account 1 的所有 transaction（自动从 .env.prod 读取服务器地址）
sailzen finance pull --account 1

# 指定输出文件名
sailzen finance pull --account 1 --output my_transactions.csv

# 拉取全部 transaction（不按 account 过滤）
sailzen finance pull

# 自定义分页大小
sailzen finance pull --account 1 --page-size 50

# 临时指定其他服务器
sailzen finance pull --account 1 --server http://192.168.1.100:8000
```

**参数说明：**

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--account` | `-a` | None | 按 account_id 过滤（可选） |
| `--output` | `-o` | `transactions_{id}.csv` | 输出 CSV 文件路径 |
| `--page-size` | — | 100 | 每页拉取数量（最大 100） |
| `--server` | — | 自动解析（见上方"服务器地址"章节） | sail_server 地址 |

**CSV 导出字段：**

| 字段 | 类型 | 说明 | 可编辑 |
|------|------|------|--------|
| `id` | int | 交易 ID（只读） | ❌ |
| `from_acc_id` | int | 转出账户 ID | ✅ |
| `to_acc_id` | int | 转入账户 ID | ✅ |
| `value` | str | 交易金额 | ✅ |
| `prev_value` | str | 交易前金额（只读） | ❌ |
| `description` | str | 交易描述 | ✅ |
| `tags` | str | 交易标签（逗号分隔） | ✅ |
| `state` | int | 交易状态（只读） | ❌ |
| `budget_id` | int | 关联预算 ID | ✅ |
| `htime` | float/ISO | 发生时间 | ✅ |
| `ctime` | datetime | 创建时间（只读） | ❌ |
| `mtime` | datetime | 修改时间（只读） | ❌ |

> ⚠️ **重要**：`push` 时只会发送标记为"可编辑"的字段到服务器。`id`、`prev_value`、`state`、`ctime`、`mtime` 等只读字段不会被上传。

### push — 推送修改回服务器

```bash
# 推送 CSV 中的修改
sailzen finance push transactions_1.csv

# 预览模式（不实际发送请求）
sailzen finance push transactions_1.csv --dry-run
sailzen finance push transactions_1.csv -n
```

**参数说明：**

| 参数 | 简写 | 说明 |
|------|------|------|
| `csv` | (位置参数) | CSV 文件路径 |
| `--dry-run` | `-n` | 仅预览，不实际发送请求 |
| `--server` | — | sail_server 地址 |

**push 行为：**
- 逐条调用 `PUT /api/v1/finance/transaction/{id}` 更新
- 每次请求间隔 0.1 秒，避免打爆服务器
- 只发送可编辑字段（`from_acc_id`, `to_acc_id`, `value`, `description`, `tags`, `budget_id`, `htime`）
- 部分失败不影响其他成功项
- 输出最终统计：成功数 / 失败数 / 错误详情

### create-from-csv — 从 CSV 创建新交易

用于批量导入**全新**的交易记录。CSV 中 `id` 列为空或缺失的行会被视为新交易，调用 `POST /api/v1/finance/transaction` 创建；有 `id` 的行会被跳过。

```bash
# 从 CSV 创建新交易
sailzen finance create-from-csv new_transactions.csv

# 使用别名
sailzen finance create new_transactions.csv

# 预览模式
sailzen finance create-from-csv new_transactions.csv --dry-run
```

**参数说明：**

| 参数 | 简写 | 说明 |
|------|------|------|
| `csv` | (位置参数) | CSV 文件路径 |
| `--dry-run` | `-n` | 仅预览，不实际发送请求 |
| `--server` | — | sail_server 地址 |

**新建 CSV 必填字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `from_acc_id` | int | 转出账户 ID |
| `to_acc_id` | int | 转入账户 ID |
| `value` | str | 交易金额 |

**新建 CSV 可选字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `description` | str | 交易描述 |
| `tags` | str | 交易标签（逗号分隔） |
| `budget_id` | int | 关联预算 ID |
| `htime` | float/ISO | 发生时间（默认当前时间） |

> ⚠️ **注意**：`id` 列必须为空或缺失，否则该行会被跳过（不会创建）。可以复用 `pull` 导出的 CSV 格式，只需删除 `id` 列的内容即可批量复制为新增记录。

## 典型工作流

### 场景：批量修改某账户的交易标签

```bash
# Step 1: 查看有哪些账户（自动读取 .env.prod 中的服务器地址）
sailzen finance list-accounts

# Step 2: 拉取 account 1 的交易到 CSV
sailzen finance pull --account 1
# → 生成 transactions_1.csv

# Step 3: 用户在 Excel / VS Code 中编辑 CSV
# 修改 tags 列、description 列等

# Step 4: 预览将要推送的修改
sailzen finance push transactions_1.csv --dry-run

# Step 5: 确认无误后推送
sailzen finance push transactions_1.csv
```

### 场景：拉取全部交易做数据分析

```bash
# 不指定 --account，拉取全部
sailzen finance pull
# → 生成 transactions_all.csv
```

### 场景：从 CSV 批量导入新交易

```bash
# Step 1: 查看有哪些账户，确认 from_acc_id / to_acc_id
sailzen finance list-accounts

# Step 2: 准备 CSV（例如 new_tx.csv），id 列为空
# from_acc_id,to_acc_id,value,description,tags,htime
# 1,2,100.00,午餐,餐饮,2026-05-10T12:00:00
# 2,1,5000.00,工资收入,收入,2026-05-01T09:00:00

# Step 3: 预览将要创建的记录
sailzen finance create-from-csv new_tx.csv --dry-run

# Step 4: 确认无误后导入
sailzen finance create-from-csv new_tx.csv
```

## 底层 API 映射

CLI 工具通过以下 HTTP API 与 sail_server 交互：

| CLI 命令 | HTTP 方法 | API 路径 |
|----------|-----------|----------|
| `list-accounts` | `GET` | `/api/v1/finance/account` |
| `pull` | `GET` | `/api/v1/finance/transaction/paginated/` (分页循环) |
| `push` | `PUT` | `/api/v1/finance/transaction/{id}` (逐条) |
| `create-from-csv` | `POST` | `/api/v1/finance/transaction` (逐条) |

**API 基础路径**：`{server_url}/api/v1/finance`

## 注意事项

1. **不直接连数据库** — 所有操作通过 HTTP API，需要 sail_server 在远程运行
2. **分页拉取** — `pull` 会自动分页循环直到拉完所有数据，每页间隔 0.1 秒
3. **本地过滤** — API 不支持直接按 account_id 过滤，CLI 拉取全部后在本地按 `from_acc_id` / `to_acc_id` 过滤
4. **CSV 编码** — 使用 UTF-8 BOM (`utf-8-sig`)，确保 Excel 能正确打开中文
5. **htime 格式** — 导出时转为 ISO 格式方便阅读，导入时自动转回时间戳
6. **dry-run 安全** — 推送前建议先用 `--dry-run` 预览
7. **幂等性** — `push` 是覆盖写入，重复推送相同数据不会产生副作用
8. **请求限速** — 每次 PUT/POST 请求间隔 0.1 秒，HTTP 超时 30 秒
9. **create-from-csv 跳过已有 id 的行** — 有 `id` 的行会被忽略，不会更新现有记录

## 故障排除

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| `Connection refused` | sail_server 未启动或地址错误 | 1) 确认远程服务器运行中；2) 检查 `.env.prod` 中的 `SERVER_HOST`/`SERVER_PORT` 是否正确；3) 使用 `--server` 显式指定 |
| `Account X not found` | account_id 不存在 | 先用 `list-accounts` 确认正确的 ID |
| `CSV file not found` | 文件路径错误 | 检查 CSV 文件路径是否正确 |
| push 后数据未变化 | 只编辑了只读字段 | 确认修改的是可编辑字段（见上表） |
| 中文乱码 | CSV 编码问题 | 确保用 UTF-8 编码保存 CSV |
| 连接到错误的 localhost:8000 | `.env.prod` 文件不存在或不在当前目录 | 确认在项目根目录执行命令，或检查 `.env.prod` 是否存在 |

## 扩展

`sailzen` 采用模块化设计，未来可扩展更多模块：

```
sailzen/
├── __main__.py          # 入口，路由到子模块
└── cli/
    ├── __init__.py
    └── finance_client.py  # FinanceClient 实现
```

添加新模块只需：
1. 在 `sailzen/cli/` 下创建新的 `xxx_client.py`
2. 在 `sailzen/__main__.py` 中添加路由
