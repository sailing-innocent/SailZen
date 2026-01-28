# 生活预算管理

## 1. 概述

生活预算管理模块是 SailZen 系统中的财务管理核心功能，提供个人财务的全面管理能力，包括账户管理、交易记录、预算规划和统计分析。

### 1.1 功能定位

- **账户管理**：管理多个资金账户（银行卡、钱包、电子支付等）
- **交易追踪**：记录收入、支出和转账交易
- **预算规划**：制定和追踪预算执行情况
- **统计分析**：多维度的财务数据分析和可视化

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (packages/site)                  │
├─────────────────────────────────────────────────────────────┤
│  Pages: money.tsx                                           │
│  Components: accounts, transactions, budgets, statistics    │
│  Store: Zustand (useAccountsStore, useTransactionsStore,   │
│         useBudgetsStore)                                    │
│  API Client: lib/api/money.ts                              │
├─────────────────────────────────────────────────────────────┤
│                    Backend (sail_server)                     │
├─────────────────────────────────────────────────────────────┤
│  Controllers: finance.py (Account/Transaction/Budget)       │
│  Models: model/finance/ (account, transaction, budget)      │
│  Data: data/finance.py (ORM models)                        │
│  Utils: utils/money.py (货币计算)                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念与数据模型

### 2.1 账户 (Account)

账户是资金的载体，代表实际的资金存放位置。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| name | String | 账户名称（必填） |
| description | String | 账户描述 |
| balance | String | 账户余额（字符串存储的十进制数） |
| state | Integer | 状态：0=实体账户，1=预算口袋 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**特殊账户**：
- `id = -1`：外部账户，用于表示收入来源或支出去向

### 2.2 交易 (Transaction)

交易记录资金在账户间的流动。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| from_acc_id | Integer | 来源账户ID（-1=外部收入） |
| to_acc_id | Integer | 目标账户ID（-1=外部支出） |
| budget_id | Integer | 关联预算ID（可选） |
| value | String | 交易金额 |
| prev_value | String | 变更前金额（用于追踪修改） |
| description | String | 交易描述 |
| tags | String | 标签（逗号分隔） |
| state | Integer | 状态（状态机，追踪余额更新状态） |
| htime | TIMESTAMP | 发生时间 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

**交易类型**：
- **收入**：`from_acc_id = -1`, `to_acc_id > 0`
- **支出**：`from_acc_id > 0`, `to_acc_id = -1`
- **转账**：`from_acc_id > 0`, `to_acc_id > 0`

### 2.3 预算 (Budget)

预算用于规划和控制支出。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键，自增 |
| name | String | 预算名称（必填） |
| amount | String | 预算金额（必填） |
| description | String | 预算描述 |
| tags | String | 关联标签（用于匹配交易） |
| htime | TIMESTAMP | 生效时间 |
| ctime | TIMESTAMP | 创建时间 |
| mtime | TIMESTAMP | 修改时间 |

### 2.4 预设标签

系统内置的交易分类标签：
- `零食` - 零食消费
- `交通` - 交通费用
- `日用消耗` - 日常用品
- `大宗电器` - 家电等大额消费
- `娱乐休闲` - 娱乐活动
- `人际交往` - 社交支出
- `医药健康` - 医疗健康
- `衣物` - 服装购置
- `大宗收支` - 其他大额收支

---

## 3. 前端功能模块

### 3.1 主页面布局 (`money.tsx`)

页面采用响应式设计：
- **桌面端**：账户表格(30%) + 交易表格(70%)
- **移动端**：垂直堆叠布局

主要区域：
1. 账户管理区
2. 交易管理区
3. 预算管理区
4. 统计图表区

### 3.2 账户管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| AccountsDataTable | `accounts_data_table.tsx` | 账户列表展示，分页，操作按钮 |
| AccountColumn | `account_column.tsx` | 表格列定义（名称、描述、余额、操作） |
| AccountAddDialog | `account_add_dialog.tsx` | 新建账户对话框 |
| AccountFixDialog | `account_fix_dialog.tsx` | 修正账户余额对话框 |

**功能特性**：
- 查看所有账户及余额
- 创建新账户
- 手动修正账户余额
- 重新计算/更新账户余额
- 过滤活跃账户（state == 0）

### 3.3 交易管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| TransactionsDataTable | `transactions_data_table.tsx` | 交易列表，分页，筛选 |
| TransactionColumn | `transaction_column.tsx` | 表格列定义 |
| TransactionAddCard | `transaction_add_card.tsx` | 新建交易表单 |
| TransactionEditCard | `transaction_edit_card.tsx` | 编辑交易表单 |
| TransactionFilters | `transaction_filters.tsx` | 高级筛选（日期、标签、金额） |
| TransactionSearchDialog | `transaction_search_dialog.tsx` | 交易搜索（用于关联预算） |

**功能特性**：
- 分页展示交易（移动端5条，桌面端10条）
- 创建/编辑/删除交易
- 多维度筛选：
  - 日期范围（预设：今天、本周、本月、本季、本年）
  - 标签筛选
  - 金额范围（预设：小额、中额、大额、自定义）
- 交易与预算关联

### 3.4 预算管理组件

| 组件 | 文件 | 功能 |
|------|------|------|
| BudgetsDataTable | `budgets_data_table.tsx` | 预算列表（手风琴视图） |
| BudgetAddDialog | `budget_add_dialog.tsx` | 新建预算对话框 |
| BudgetConsumeDialog | `budget_consume_dialog.tsx` | 预算消费对话框 |
| BudgetAnalysisCard | `budget_analysis_card.tsx` | 预算分析详情 |

**功能特性**：
- 手风琴式展开预算详情
- 显示预算统计：已用金额、剩余金额、交易数量
- 预算消费：
  - 创建新交易并关联预算
  - 关联已有交易到预算
- 取消交易与预算的关联
- 剩余不足20%时红色高亮提醒
- 删除预算

### 3.5 统计分析组件 (`statistics.tsx`)

提供多维度财务数据可视化：

**时间维度选择**：
- 月度统计
- 季度统计
- 年度统计

**图表类型**：
- 支出总体趋势图
- 日常零碎支出趋势
- 大宗收支趋势
- 大宗电器趋势
- 日常消费标签分布

**统计卡片**：
- 标签统计汇总
- 大宗项目明细
- 日常消费明细

---

## 4. 后端 API 接口

### 4.1 账户接口 (`/api/v1/finance/account`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取账户列表 |
| GET | `/{id}` | 获取账户详情 |
| POST | `/` | 创建账户 |
| DELETE | `/{id}` | 删除账户 |
| GET | `/recalc_balance/{id}` | 重新计算余额（从所有交易） |
| GET | `/update_balance/{id}` | 增量更新余额 |
| POST | `/fix_balance` | 修正余额（创建调整交易） |

### 4.2 交易接口 (`/api/v1/finance/transaction`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取交易列表（支持分页） |
| GET | `/{id}` | 获取交易详情 |
| POST | `/` | 创建交易 |
| PUT | `/{id}` | 更新交易 |
| DELETE | `/{id}` | 删除交易（软删除） |
| GET | `/stats/` | 获取交易统计 |

**统计接口参数**：
- `skip`, `limit`: 分页
- `from_time`, `to_time`: 时间范围
- `tags`: 标签筛选
- `tag_op`: 标签运算符（AND/OR）
- `description`: 描述搜索
- `min_value`, `max_value`: 金额范围
- `return_list`: 是否返回交易列表

**统计接口返回**：
```json
{
  "total_count": 100,
  "income_count": 30,
  "expense_count": 70,
  "income_total": "10000.00 CNY",
  "expense_total": "8000.00 CNY",
  "net_total": "2000.00 CNY",
  "data": [...]  // 可选
}
```

### 4.3 预算接口 (`/api/v1/finance/budget`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取预算列表 |
| GET | `/{id}` | 获取预算详情 |
| POST | `/` | 创建预算 |
| PUT | `/{id}` | 更新预算 |
| DELETE | `/{id}` | 删除预算 |
| GET | `/stats/` | 获取预算统计 |
| GET | `/{id}/analysis` | 获取预算分析 |
| POST | `/{id}/consume` | 消费预算 |
| POST | `/{budget_id}/link/{transaction_id}` | 关联交易 |
| DELETE | `/unlink/{transaction_id}` | 取消关联 |

**预算统计返回**：
```json
{
  "total_budget_count": 5,
  "total_budget_amount": "5000.00 CNY",
  "total_used_amount": "3500.00 CNY",
  "total_remaining_amount": "1500.00 CNY",
  "budgets": [...]  // 可选
}
```

**预算分析返回**：
```json
{
  "budget": {...},
  "used_amount": "3500.00 CNY",
  "remaining_amount": "1500.00 CNY",
  "usage_percentage": 70.0,
  "transactions": [...],
  "by_tag": {
    "零食": "1000.00 CNY",
    "日用消耗": "2500.00 CNY"
  }
}
```

---

## 5. 核心业务逻辑

### 5.1 账户余额管理

**增量更新机制**：
- 基于交易状态标记，仅处理未应用的交易
- 使用状态机追踪每笔交易对账户余额的影响

**重新计算机制**：
- 从所有相关交易重新计算余额
- 用于修正可能的不一致

**余额修正机制**：
- 创建一笔调整交易来修正差额
- 保持交易历史的完整性

### 5.2 交易状态机

交易的 `state` 字段使用位标记追踪余额更新状态：
- 追踪来源账户是否已扣款
- 追踪目标账户是否已入账
- 支持变更追踪（通过 prev_value）

### 5.3 预算消费计算

**已用金额计算优先级**：
1. **直接关联**：通过 `budget_id` 直接关联的交易
2. **标签匹配**：按标签（OR运算）和时间范围匹配的交易

**消费验证**：
- 验证消费金额不超过预算剩余
- 创建交易时自动关联预算
- 继承预算的标签和描述

### 5.4 货币处理

使用字符串存储十进制金额，避免浮点数精度问题。

**Money 工具类功能**：
- 支持多种初始化方式：`Money("1000.00 CNY")`, `Money(1000.00, "CNY")`
- 算术运算：加、减、乘、除
- 比较运算：相等、大于、小于等
- 格式化输出
- 支持货币：CNY、USD、EUR

---

## 6. 典型使用场景

### 6.1 日常记账

1. 打开财务管理页面
2. 点击"添加交易"
3. 选择来源账户（如"微信钱包"）和目标账户（选择"其他"表示支出）
4. 输入金额和描述
5. 选择标签分类
6. 确认保存

### 6.2 预算规划

1. 创建预算：设置名称、金额、标签、生效时间
2. 日常消费时选择从预算消费，自动创建关联交易
3. 或者事后将已有交易关联到预算
4. 随时查看预算执行情况和剩余金额

### 6.3 财务分析

1. 选择统计时间维度（月/季/年）
2. 查看支出趋势图表
3. 分析各标签分类的支出占比
4. 识别大宗支出项目
5. 对比不同时期的收支情况

### 6.4 账户余额核对

1. 对比实际账户余额与系统记录
2. 如有差异，使用"修正余额"功能
3. 系统自动创建调整交易保持记录完整

---

## 7. 状态管理 (Zustand)

### 7.1 AccountsStore

```typescript
interface AccountsStore {
  accounts: AccountData[];
  isLoading: boolean;
  
  fetchAccounts(): Promise<void>;
  getOptions(): AccountOption[];
  updateAccount(id: number, refresh?: boolean): Promise<void>;
  fixAccount(id: number, newBalance: string): Promise<void>;
  createAccount(name: string): Promise<void>;
}
```

### 7.2 TransactionsStore

```typescript
interface TransactionsStore {
  transactions: TransactionData[];
  isLoading: boolean;
  
  fetchTransactions(limit: number): Promise<void>;
  createTransaction(transaction: TransactionCreateProps): Promise<void>;
  updateTransaction(id: number, transaction: Partial<TransactionData>): Promise<void>;
  deleteTransaction(id: number): Promise<void>;
  getSupportedTags(): string[];
}
```

### 7.3 BudgetsStore

```typescript
interface BudgetsStore {
  budgets: BudgetData[];
  isLoading: boolean;
  
  fetchBudgets(params?: BudgetQueryParams): Promise<void>;
  createBudget(budget: BudgetCreateProps): Promise<void>;
  updateBudget(id: number, budget: Partial<BudgetData>): Promise<void>;
  deleteBudget(id: number): Promise<void>;
  consumeBudget(id: number, consume: BudgetConsumeProps): Promise<void>;
  linkTransaction(budget_id: number, transaction_id: number): Promise<void>;
  unlinkTransaction(transaction_id: number): Promise<void>;
  getBudgetStats(params?: BudgetStatsParams): Promise<BudgetStats>;
  getBudgetAnalysis(id: number): Promise<BudgetAnalysis>;
}
```

---

## 8. 数据库迁移

相关迁移文件：
- `add_budget_id_to_transaction.sql` - 添加交易与预算的关联字段
- `alter_table_transaction.sql` - 时间戳类型转换
- `alter_table_account.sql` - 时间戳类型转换
- `fix_transactions_sequence.sql` - 修复交易ID序列
- `transaction_htime.sql` - 添加交易发生时间字段

---

## 9. 技术要点

### 9.1 架构模式

- **分层架构**：数据层 → 业务逻辑层 → 控制器层 → 路由层
- **DTO 模式**：区分创建/更新/读取的数据传输对象
- **状态机模式**：交易状态追踪账户余额更新
- **软删除**：交易标记废弃而非物理删除

### 9.2 数据完整性

- 外键约束
- 交易状态验证
- 预算消费金额验证
- 账户余额一致性检查

### 9.3 查询能力

- 分页查询（skip/limit）
- 时间范围筛选
- 标签筛选（支持 AND/OR）
- 描述关键词搜索
- 金额范围筛选
- 组合筛选

### 9.4 响应式设计

- 桌面端双栏布局
- 移动端单栏堆叠
- 分页数量自适应
- 折叠/展开交互

---

## 10. 待优化项

1. **标签管理**：当前标签为硬编码，考虑支持用户自定义标签
2. **多币种**：后端已支持多币种，前端待完善
3. **账户添加**：添加账户对话框功能待完善
4. **数据导出**：支持交易记录导出为 CSV/Excel
5. **定期交易**：支持设置定期重复交易
6. **预算提醒**：预算即将用尽时主动提醒
7. **图表优化**：增加更多图表类型和交互功能
