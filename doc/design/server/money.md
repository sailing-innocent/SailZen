# 金钱管理 API 文档

本文档描述 SailZen 系统的财务管理 API，包括账户、交易和预算管理功能。

**基础路径**: `/api/v1/finance`

---

## 1. 账户 API (Account)

### GET /finance/account/
获取账户列表

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过的记录数 |
| `limit` | int | -1 | 返回数量限制（-1 表示不限制）|

**响应示例：**
```json
[
  {
    "id": 1,
    "name": "现金",
    "description": "日常现金",
    "balance": "1000.00",
    "state": 1,
    "ctime": "2024-01-01T00:00:00",
    "mtime": "2024-01-15T10:30:00"
  }
]
```

### GET /finance/account/{account_id}
获取单个账户详情

### POST /finance/account/
创建新账户

**请求体：**
```json
{
  "name": "银行卡",
  "description": "招商银行储蓄卡",
  "balance": "5000.00"
}
```

### DELETE /finance/account/{account_id}
删除账户

### POST /finance/account/fix_balance/
修正账户余额（用于账户余额校准）

**请求体：**
```json
{
  "account_id": 1,
  "balance_fix": "100.00"
}
```

### GET /finance/account/update_balance/{account_id}
更新账户余额（根据交易记录重新计算）

### GET /finance/account/recalc_balance/{account_id}
重新计算账户余额

---

## 2. 交易 API (Transaction)

### GET /finance/transaction/
获取交易列表

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过的记录数 |
| `limit` | int | -1 | 返回数量限制 |

### GET /finance/transaction/paginated/
分页获取交易列表（推荐使用）

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码（从1开始）|
| `page_size` | int | 20 | 每页数量 |
| `from_time` | float | - | 开始时间戳 |
| `to_time` | float | - | 结束时间戳 |
| `tags` | str | "" | 标签筛选（逗号分隔）|
| `tag_op` | str | "and" | 标签操作：and/or |
| `description` | str | - | 描述筛选（模糊匹配）|
| `min_value` | float | - | 最小金额 |
| `max_value` | float | - | 最大金额 |
| `sort_by` | str | "htime" | 排序字段 |
| `sort_order` | str | "desc" | 排序方向：asc/desc |

**响应格式：**
```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

### GET /finance/transaction/{transaction_id}
获取单个交易详情

### POST /finance/transaction/
创建新交易

**请求体：**
```json
{
  "from_acc_id": 1,
  "to_acc_id": -1,
  "value": "100.00",
  "description": "午餐",
  "tags": "food,dining",
  "htime": 1640995200.0
}
```

**说明：**
- `from_acc_id`: 支出账户ID（-1 表示外部来源）
- `to_acc_id`: 收入账户ID（-1 表示外部支出）
- 收入：`from_acc_id=-1`, `to_acc_id>0`
- 支出：`from_acc_id>0`, `to_acc_id=-1`
- 转账：`from_acc_id>0`, `to_acc_id>0`

### PUT /finance/transaction/{transaction_id}
更新交易

### DELETE /finance/transaction/{transaction_id}
删除交易

---

## 3. 交易统计 API (Transaction Stats)

### GET /finance/transaction/stats/

This endpoint provides transaction statistics with flexible filtering options. It always returns summary statistics, and optionally includes transaction data based on the `return_list` parameter.

### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | int | 0 | Number of records to skip (for pagination) |
| `limit` | int | -1 | Maximum number of records to return (-1 for no limit) |
| `from_time` | float | None | Start timestamp for time period filtering |
| `to_time` | float | None | End timestamp for time period filtering |
| `tags` | str | "" | Comma-separated list of tags to filter by |
| `tag_op` | str | "and" | Tag operation: "and" or "or" |
| `description` | str | None | Description filter (partial match) |
| `min_value` | float | None | Minimum transaction value |
| `max_value` | float | None | Maximum transaction value |
| `return_list` | bool | False | If True, include transaction data in response; if False, only return stats |

### Response Format

The response always includes summary statistics, and optionally includes transaction data:

#### When `return_list=false` (default):
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00"
}
```

#### When `return_list=true`:
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00",
  "data": [
    {
      "id": 1,
      "from_acc_id": -1,
      "to_acc_id": 1,
      "value": "100.00",
      "description": "Salary",
      "tags": "income,salary",
      "htime": 1640995200.0,
      "ctime": "2024-01-01T00:00:00",
      "mtime": "2024-01-01T00:00:00"
    }
  ]
}
```

### Income and Expense Classification

- **Income**: Transactions where `from_acc_id=-1` and `to_acc_id>0`
- **Expense**: Transactions where `from_acc_id>0` and `to_acc_id=-1`

### Example Usage

#### Get summary statistics for all transactions:
```
GET /finance/transaction/stats/
```
Response:
```json
{
  "total_count": 10,
  "income_count": 6,
  "expense_count": 4,
  "income_total": "1500.00",
  "expense_total": "800.00",
  "net_total": "700.00"
}
```

#### Get summary statistics with transaction data for specific tags:
```
GET /finance/transaction/stats/?tags=food,groceries&tag_op=or&return_list=true
```
Response:
```json
{
  "total_count": 5,
  "income_count": 0,
  "expense_count": 5,
  "income_total": "0.00",
  "expense_total": "200.00",
  "net_total": "-200.00",
  "data": [
    {
      "id": 1,
      "from_acc_id": 1,
      "to_acc_id": -1,
      "value": "50.00",
      "description": "Grocery shopping",
      "tags": "food,groceries",
      "htime": 1640995200.0,
      "ctime": "2024-01-01T00:00:00",
      "mtime": "2024-01-01T00:00:00"
    }
  ]
}
```

#### Get summary for a specific time period:
```
GET /finance/transaction/stats/?from_time=1640995200&to_time=1643673600
```

#### Get high-value transactions with data:
```
GET /finance/transaction/stats/?min_value=1000&return_list=true
```

#### Get paginated transaction data:
```
GET /finance/transaction/stats/?skip=0&limit=10&return_list=true
```

### Error Responses

- **500 Internal Server Error**: When there's an error processing the request
  ```json
  {
    "detail": "Error getting transaction stats: [error message]"
  }
  ```

### POST /finance/transaction/stats/batch/
批量获取交易统计（用于图表展示）

**请求体：**
```json
{
  "queries": [
    {
      "name": "本月支出",
      "from_time": 1704067200,
      "to_time": 1706745600,
      "tags": "food,transport"
    },
    {
      "name": "上月支出",
      "from_time": 1701388800,
      "to_time": 1704067200
    }
  ]
}
```

**响应格式：**
```json
{
  "results": [
    {
      "name": "本月支出",
      "total_count": 50,
      "income_count": 5,
      "expense_count": 45,
      "income_total": "3000.00",
      "expense_total": "2500.00",
      "net_total": "500.00"
    },
    ...
  ]
}
```

---

## 4. 预算 API (Budget)

### GET /finance/budget/
获取预算列表

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `skip` | int | 0 | 跳过的记录数 |
| `limit` | int | -1 | 返回数量限制 |
| `from_time` | float | - | 开始时间戳 |
| `to_time` | float | - | 结束时间戳 |
| `tags` | str | "" | 标签筛选 |
| `tag_op` | str | "and" | 标签操作 |

### GET /finance/budget/{budget_id}
获取单个预算详情

### POST /finance/budget/
创建新预算

**请求体：**
```json
{
  "name": "本月餐饮预算",
  "amount": "2000.00",
  "description": "每月餐饮支出控制",
  "tags": "food,dining",
  "htime": 1704067200.0
}
```

### PUT /finance/budget/{budget_id}
更新预算

### DELETE /finance/budget/{budget_id}
删除预算

### GET /finance/budget/stats/
获取预算统计

**查询参数：** 同预算列表

**响应格式：**
```json
{
  "total_budget_count": 5,
  "total_budget_amount": "10000.00",
  "total_used_amount": "6500.00",
  "total_remaining_amount": "3500.00"
}
```

### GET /finance/budget/{budget_id}/analysis
获取预算执行分析

**响应格式：**
```json
{
  "budget": {...},
  "used_amount": "1500.00",
  "remaining_amount": "500.00",
  "usage_percentage": 75.0,
  "transactions": [...],
  "by_tag": {
    "food": {"amount": "1000.00", "count": 20},
    "dining": {"amount": "500.00", "count": 10}
  }
}
```

### POST /finance/budget/{budget_id}/consume
从预算创建交易（预算核销）

**请求体：**
```json
{
  "from_acc_id": 1,
  "to_acc_id": -1,
  "value": "100.00",
  "description": "午餐",
  "htime": 1704067200.0
}
```

**说明：** 核销金额不能超过预算剩余金额

### POST /finance/budget/{budget_id}/link/{transaction_id}
将现有交易关联到预算

### DELETE /finance/budget/unlink/{transaction_id}
取消交易与预算的关联

---

## 5. 数据模型

### Account 账户
```python
{
  "id": int,           # 主键
  "name": str,         # 账户名称
  "description": str,  # 账户描述
  "balance": str,      # 当前余额（Money 字符串）
  "state": int,        # 状态：1=有效, 0=归档
  "ctime": datetime,   # 创建时间
  "mtime": datetime    # 修改时间
}
```

### Transaction 交易
```python
{
  "id": int,           # 主键
  "from_acc_id": int,  # 支出账户ID（-1=外部）
  "to_acc_id": int,    # 收入账户ID（-1=外部）
  "budget_id": int,    # 关联预算ID（可选）
  "value": str,        # 交易金额
  "prev_value": str,   # 修改前金额
  "description": str,  # 交易描述
  "tags": str,         # 标签（逗号分隔）
  "state": int,        # 交易状态
  "htime": float,      # 发生时间（timestamp）
  "ctime": datetime,   # 创建时间
  "mtime": datetime    # 修改时间
}
```

### Budget 预算
```python
{
  "id": int,           # 主键
  "name": str,         # 预算名称
  "amount": str,       # 预算金额
  "description": str,  # 预算描述
  "tags": str,         # 标签
  "htime": float,      # 生效时间（timestamp）
  "ctime": datetime,   # 创建时间
  "mtime": datetime    # 修改时间
}
```

---

## 6. 收支分类说明

| 类型 | from_acc_id | to_acc_id | 说明 |
|------|-------------|-----------|------|
| 收入 | -1 | >0 | 外部资金进入账户 |
| 支出 | >0 | -1 | 账户资金流出 |
| 转账 | >0 | >0 | 账户间转账 |
