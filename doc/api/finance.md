# 财务管理 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

财务管理模块提供个人账户管理、交易记录追踪、预算规划等功能。

### 核心概念

| 概念 | 说明 |
|------|------|
| **账户 (Account)** | 资金账户，如现金、银行卡、支付宝等 |
| **交易 (Transaction)** | 资金流动记录，包括收入、支出、转账 |
| **预算 (Budget)** | 预算规划，支持周期性预算项管理 |

### 交易类型说明

| 类型 | from_acc_id | to_acc_id | 说明 |
|------|-------------|-----------|------|
| 收入 | -1 | > 0 | 资金流入账户 |
| 支出 | > 0 | -1 | 资金流出账户 |
| 转账 | > 0 | > 0 | 账户间资金转移 |

---

## 💳 账户 API

### 获取账户列表

```http
GET /api/v1/finance/account/
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 -1） |

**响应:**
```json
[
  {
    "id": 1,
    "name": "现金",
    "balance": "1234.56",
    "state": 1
  }
]
```

---

### 获取单个账户

```http
GET /api/v1/finance/account/{account_id}
```

**响应:**
```json
{
  "id": 1,
  "name": "现金",
  "balance": "1234.56",
  "state": 1
}
```

---

### 创建账户

```http
POST /api/v1/finance/account/
```

**请求体:**
```json
{
  "name": "支付宝"
}
```

**响应:** 创建的账户对象

---

### 更新账户余额

```http
GET /api/v1/finance/account/update_balance/{account_id}
```

从交易记录重新计算账户余额。

---

### 修正账户余额

```http
POST /api/v1/finance/account/fix_balance
```

**请求体:**
```json
{
  "id": 1,
  "balance": "1000.00"
}
```

用于手动修正账户余额，会自动创建差额调整交易。

---

### 删除账户

```http
DELETE /api/v1/finance/account/{account_id}
```

**响应:**
```json
{
  "id": 1,
  "status": "success",
  "message": "Account 1 deleted successfully"
}
```

---

## 💸 交易 API

### 获取交易列表

```http
GET /api/v1/finance/transaction/
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数 |

---

### 分页查询交易

```http
GET /api/v1/finance/transaction/paginated/
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码（默认 1） |
| page_size | int | 否 | 每页大小（默认 20，最大 100） |
| from_time | float | 否 | 开始时间戳 |
| to_time | float | 否 | 结束时间戳 |
| tags | string | 否 | 标签筛选（逗号分隔） |
| tag_op | string | 否 | 标签逻辑：and/or（默认 and） |
| description | string | 否 | 描述模糊匹配 |
| min_value | float | 否 | 最小金额 |
| max_value | float | 否 | 最大金额 |
| sort_by | string | 否 | 排序字段（默认 htime） |
| sort_order | string | 否 | 排序方向：asc/desc（默认 desc） |

**响应:**
```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5,
  "has_next": true,
  "has_prev": false
}
```

---

### 获取交易统计

```http
GET /api/v1/finance/transaction/stats/
```

**参数:** 同分页查询

**响应:**
```json
{
  "total_count": 100,
  "income_count": 30,
  "expense_count": 70,
  "income_total": "5000.00",
  "expense_total": "3200.00",
  "net_total": "1800.00",
  "data": [...]  // return_list=true 时包含
}
```

---

### 批量获取交易统计

```http
POST /api/v1/finance/transaction/stats/batch/
```

**请求体:**
```json
[
  {
    "id": "query1",
    "from_time": 1700000000,
    "to_time": 1700000000,
    "tags": "餐饮,交通",
    "tag_op": "or",
    "return_list": false
  }
]
```

**响应:**
```json
[
  {
    "id": "query1",
    "stats": { ... }
  }
]
```

---

### 创建交易

```http
POST /api/v1/finance/transaction/
```

**请求体:**
```json
{
  "from_acc_id": 1,      // 支出账户ID，收入时为 -1
  "to_acc_id": -1,       // 收入账户ID，支出时为 -1
  "value": "100.00",     // 金额（字符串）
  "description": "超市购物",
  "htime": 1700000000,   // 交易时间（可选，默认当前时间）
  "tags": "生活,购物"     // 标签（可选）
}
```

---

### 更新交易

```http
PUT /api/v1/finance/transaction/{transaction_id}
```

**请求体:** 同创建交易

---

### 删除交易

```http
DELETE /api/v1/finance/transaction/{transaction_id}
```

---

## 📊 预算 API

### 获取预算列表

```http
GET /api/v1/finance/budget/
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数 |
| from_time | float | 否 | 开始时间筛选 |
| to_time | float | 否 | 结束时间筛选 |
| tags | string | 否 | 标签筛选 |
| tag_op | string | 否 | 标签逻辑 |

---

### 获取单个预算

```http
GET /api/v1/finance/budget/{budget_id}
```

**响应:**
```json
{
  "id": 1,
  "name": "月度生活费",
  "description": "日常开销预算",
  "start_time": 1700000000,
  "end_time": 1700000000,
  "status": 1,
  "total_amount": "3000.00",
  "direction": -1,
  "items": [...]
}
```

---

### 创建预算

```http
POST /api/v1/finance/budget/
```

**请求体:**
```json
{
  "name": "月度生活费",
  "description": "日常开销预算",
  "start_date": 1700000000,
  "end_date": 1700000000,
  "tags": "生活",
  "htime": 1700000000,
  "direction": -1  // -1 支出预算, 1 收入预算
}
```

**注意:** 预算总额会根据子项自动计算。

---

### 更新预算

```http
PUT /api/v1/finance/budget/{budget_id}
```

---

### 删除预算

```http
DELETE /api/v1/finance/budget/{budget_id}
```

---

### 预算消费

```http
POST /api/v1/finance/budget/{budget_id}/consume
```

从预算中消费，创建关联交易。

**请求体:**
```json
{
  "from_acc_id": 1,
  "to_acc_id": -1,
  "value": "100.00",
  "description": "预算消费",
  "htime": 1700000000,
  "tags": "餐饮"
}
```

---

### 关联交易到预算

```http
POST /api/v1/finance/budget/{budget_id}/link/{transaction_id}
```

将已有交易关联到预算。

---

### 批量关联交易

```http
POST /api/v1/finance/budget/{budget_id}/link-batch
```

**请求体:**
```json
{
  "transaction_ids": [1, 2, 3]
}
```

**响应:**
```json
{
  "success": [1, 2],
  "failed": [{"id": 3, "error": "..."}],
  "total": 3,
  "success_count": 2,
  "failed_count": 1
}
```

---

### 解除交易关联

```http
DELETE /api/v1/finance/budget/unlink/{transaction_id}
```

---

### 获取预算统计

```http
GET /api/v1/finance/budget/stats/
```

---

### 获取预算分析

```http
GET /api/v1/finance/budget/{budget_id}/analysis
```

---

## 📝 预算子项 API

### 获取子项列表

```http
GET /api/v1/finance/budget/{budget_id}/items
```

---

### 创建子项

```http
POST /api/v1/finance/budget/{budget_id}/items
```

**请求体:**
```json
{
  "name": "房租",
  "amount": "2000.00",
  "period_type": "monthly",  // once, daily, weekly, monthly, yearly
  "start_date": 1700000000,
  "end_date": 1700000000,
  "category": "住房",
  "is_refundable": false
}
```

---

### 更新子项

```http
PUT /api/v1/finance/budget/items/{item_id}
```

---

### 删除子项

```http
DELETE /api/v1/finance/budget/items/{item_id}
```

---

### 记录退款

```http
POST /api/v1/finance/budget/items/{item_id}/refund
```

对于可退款项目（如押金），记录退款金额。

**请求体:**
```json
{
  "refund_amount": "500.00"
}
```

---

### 推进周期

```http
POST /api/v1/finance/budget/items/{item_id}/advance
```

将周期性预算项推进到下一周期。

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 账户
  api_get_accounts,
  api_get_account,
  api_create_account,
  api_fix_account_balance,
  
  // 交易
  api_get_transactions_paginated,
  api_get_transactions_stats,
  api_get_transactions_stats_batch,
  api_create_transaction,
  api_update_transaction,
  api_delete_transaction,
  
  // 预算
  api_get_budgets,
  api_get_budget,
  api_create_budget,
  api_update_budget,
  api_delete_budget,
  api_consume_budget,
  api_link_transaction_to_budget,
  api_link_transactions_batch,
  api_unlink_transaction_from_budget,
  
  // 预算子项
  api_get_budget_items,
  api_create_budget_item,
  api_update_budget_item,
  api_delete_budget_item,
  api_record_item_refund,
  api_advance_item_period,
  api_get_budget_detail,
  api_create_budget_with_items,
} from '@lib/api/money'
```

### 使用示例

```typescript
// 获取账户列表
const accounts = await api_get_accounts()

// 创建支出交易
const transaction = await api_create_transaction({
  from_acc_id: 1,      // 从现金账户支出
  to_acc_id: -1,       // -1 表示支出
  value: '50.00',
  description: '午餐',
  tags: '餐饮'
})

// 创建收入交易
const income = await api_create_transaction({
  from_acc_id: -1,     // -1 表示收入
  to_acc_id: 2,        // 存入银行卡
  value: '5000.00',
  description: '工资',
  tags: '收入'
})

// 分页查询交易
const result = await api_get_transactions_paginated({
  page: 1,
  page_size: 20,
  tags: '餐饮',
  from_time: Date.now() / 1000 - 30 * 24 * 3600  // 最近30天
})

// 获取月度统计
const stats = await api_get_transactions_stats({
  from_time: 1700000000,
  to_time: 1700000000,
  tags: '餐饮,交通',
  tag_op: 'or',
  return_list: false
})

// 创建带子项的预算
const budget = await api_create_budget_with_items(
  {
    name: '月度预算',
    description: '每月开销',
    tags: '生活'
  },
  [
    { name: '房租', amount: '2000.00', period_type: 'monthly', category: '住房' },
    { name: '餐饮', amount: '1500.00', period_type: 'monthly', category: '生活' },
    { name: '交通', amount: '300.00', period_type: 'monthly', category: '生活' }
  ]
)

// 预算消费
await api_consume_budget(budget.id, {
  from_acc_id: 1,
  to_acc_id: -1,
  value: '50.00',
  description: '午餐',
  tags: '餐饮'
})
```

---

## 📦 数据类型

### AccountData

```typescript
interface AccountData {
  id: number
  name: string
  balance: string  // 使用字符串表示精确金额
  state: number    // 1: 正常, 0: 禁用
}
```

### TransactionData

```typescript
interface TransactionData {
  id: number
  from_acc_id: number   // -1 表示收入
  to_acc_id: number     // -1 表示支出
  value: string         // 金额
  description: string
  htime: number         // Unix 时间戳
  tags?: string
  budget_id?: number    // 关联的预算ID
}
```

### BudgetData

```typescript
interface BudgetData {
  id: number
  name: string
  description?: string
  start_time?: number
  end_time?: number
  status: number
  total_amount: string
  direction: number     // -1: 支出预算, 1: 收入预算
  items: BudgetItemData[]
}

interface BudgetItemData {
  id: number
  name: string
  amount: string
  period_type: 'once' | 'daily' | 'weekly' | 'monthly' | 'yearly'
  start_date?: number
  end_date?: number
  category?: string
  is_refundable: boolean
  refund_amount?: string
}
```

---

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
