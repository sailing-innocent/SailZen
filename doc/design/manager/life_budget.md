# 财务管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Account | 资金账户 | name, balance, state |
| Transaction | 交易记录 | from_acc_id, to_acc_id, value, tags |
| Budget | 预算 | name, amount, tags |

## 交易类型

- **收入**: from_acc_id = -1
- **支出**: to_acc_id = -1
- **转账**: 两者均 > 0

## API 概览

```
GET  /api/v1/finance/account/          # 账户列表
GET  /api/v1/finance/transaction/      # 交易列表（支持筛选）
POST /api/v1/finance/transaction/      # 创建交易
GET  /api/v1/finance/budget/           # 预算列表
POST /api/v1/finance/budget/consume    # 预算消费
```

## 前端组件

| 组件 | 功能 |
|------|------|
| AccountsDataTable | 账户列表与余额 |
| TransactionsDataTable | 交易记录与筛选 |
| BudgetsDataTable | 预算展示与消费 |
| Statistics | 收支统计图表 |
