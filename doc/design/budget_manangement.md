# 预算管理系统设计文档

## 概述

预算管理系统是在现有记账管理系统基础上扩展的功能模块，用于管理预算计划、跟踪预算执行情况，并支持从预算创建实际交易记录（预算核销）。

## 设计原则

1. **与现有系统保持一致**：遵循现有的代码风格和架构模式
2. **数据模型扩展**：在现有Account和Transaction模型基础上扩展Budget模型
3. **前后端分离**：保持前后端分离的架构
4. **RESTful API**：遵循RESTful API设计规范

## 数据模型设计

### Budget模型

```python
class Budget(ORMBase):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # 预算名称
    amount = Column(String)  # 预算金额（Decimal float）
    description = Column(String)  # 预算描述
    tags = Column(String, default="")  # 标签（用于分类和筛选）
    htime = Column(TIMESTAMP)  # 预算生效时间（happen time）
    ctime = Column(TIMESTAMP)  # 创建时间
    mtime = Column(TIMESTAMP)  # 修改时间
    
    # 关联关系：一个预算可以对应多个交易记录（通过tags关联）
    # 注意：这里不直接建立外键关系，而是通过tags和htime来关联
```

### BudgetData数据类

```python
@dataclass
class BudgetData:
    id: int = field(default=-1)
    name: str = field(default="")
    amount: str = field(default="0.0")
    description: str = field(default="")
    tags: str = field(default="")
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())
```

### Transaction扩展

Transaction模型已经存在，预算核销时创建的Transaction会：
- 使用budget的tags作为transaction的tags
- 使用budget的htime作为transaction的htime（或用户指定的时间）
- 在description中标注来源budget的id或name

## API设计

### 1. Budget CRUD操作

#### GET /finance/budget/
获取预算列表
- Query参数：
  - `skip`: int (默认0) - 分页偏移
  - `limit`: int (默认-1) - 返回数量限制
  - `tags`: str (可选) - 标签筛选（逗号分隔）
  - `from_time`: float (可选) - 开始时间戳
  - `to_time`: float (可选) - 结束时间戳
- 返回：`BudgetData[]`

#### GET /finance/budget/{budget_id}
获取单个预算详情
- 返回：`BudgetData`

#### POST /finance/budget/
创建新预算
- Body: `BudgetData` (排除id, ctime, mtime)
- 返回：`BudgetData`

#### PUT /finance/budget/{budget_id}
更新预算
- Body: `BudgetData` (排除id, ctime, mtime)
- 返回：`BudgetData`

#### DELETE /finance/budget/{budget_id}
删除预算
- 返回：`{id: int, status: string, message: string}`

### 2. Budget统计和分析

#### GET /finance/budget/stats/
获取预算统计信息
- Query参数：
  - `from_time`: float (可选) - 开始时间戳
  - `to_time`: float (可选) - 结束时间戳
  - `tags`: str (可选) - 标签筛选
- 返回：
```json
{
  "total_budget_count": int,
  "total_budget_amount": str,
  "total_used_amount": str,  // 已核销金额
  "total_remaining_amount": str,  // 剩余预算
  "budgets": [  // 可选，当return_list=true时返回
    {
      "budget": BudgetData,
      "used_amount": str,
      "remaining_amount": str,
      "transaction_count": int
    }
  ]
}
```

### 3. Budget核销（创建Transaction）

#### POST /finance/budget/{budget_id}/consume
从预算创建交易记录（预算核销）
- Body:
```json
{
  "from_acc_id": int,  // 支出账户ID（-1表示外部）
  "to_acc_id": int,    // 收入账户ID（-1表示外部）
  "value": str,        // 核销金额
  "description": str, // 交易描述（可选）
  "htime": float       // 交易时间戳（可选，默认使用budget的htime）
}
```
- 返回：`TransactionData`（创建的交易记录）

注意：
- 核销金额不能超过预算剩余金额
- 创建的Transaction会自动继承budget的tags
- 在description中自动添加预算信息

### 4. Budget与实际对比分析

#### GET /finance/budget/{budget_id}/analysis
获取预算执行情况分析
- 返回：
```json
{
  "budget": BudgetData,
  "used_amount": str,
  "remaining_amount": str,
  "usage_percentage": float,  // 使用百分比
  "transactions": TransactionData[],  // 关联的交易记录
  "by_tag": {  // 按标签分组统计
    "tag_name": {
      "amount": str,
      "count": int
    }
  }
}
```

### 5. Budget与Transaction关联 ✅ 已实现

#### POST /finance/budget/{budget_id}/link/{transaction_id}
将交易记录关联到预算
- 说明：将现有的交易记录关联到指定预算，用于追踪预算使用情况
- 返回：`TransactionData`（更新后的交易记录）

#### DELETE /finance/budget/unlink/{transaction_id}
取消交易与预算的关联
- 说明：解除交易记录与预算的关联
- 返回：`TransactionData`（更新后的交易记录）

**使用场景**：
- 导入历史交易后，将其关联到对应的预算
- 手动调整预算执行记录
- 批量管理预算与交易的对应关系

## 业务逻辑设计

### 1. 预算创建
- 验证预算名称不为空
- 验证预算金额为正数
- 自动设置创建时间和修改时间

### 2. 预算核销
- 验证预算存在且有效
- 验证核销金额不超过剩余预算
- 创建Transaction时：
  - 继承budget的tags
  - 使用budget的htime（如果用户未指定）
  - 在description中添加预算信息：`[预算: {budget.name}] {user_description}`
- 更新预算的修改时间（可选，用于追踪最后核销时间）

### 3. 预算统计
- 通过tags和时间范围匹配Transaction
- 计算已核销金额：统计所有匹配的expense transactions（from_acc_id>0, to_acc_id=-1）
- 计算剩余预算：预算金额 - 已核销金额

### 4. 预算对比分析
- 获取预算信息
- 查询关联的交易记录（通过tags和时间范围匹配）
- 按标签分组统计
- 计算使用率

## 前端设计

### 1. 组件结构

#### BudgetsDataTable
- 显示预算列表
- 支持筛选（标签、时间范围）
- 显示预算金额、已使用金额、剩余金额
- 支持创建、编辑、删除预算

#### BudgetAddCard / BudgetEditCard
- 创建/编辑预算表单
- 字段：名称、金额、描述、标签、生效时间

#### BudgetConsumeDialog
- 预算核销对话框
- 选择账户、输入金额、描述
- 显示剩余预算

#### BudgetAnalysisCard
- 预算执行情况分析
- 显示使用率、关联交易、按标签统计

### 2. Store设计

```typescript
interface BudgetsState {
  budgets: BudgetData[]
  isLoading: boolean
  fetchBudgets: (params?: BudgetQueryParams) => Promise<BudgetData[]>
  createBudget: (budget: BudgetCreateProps) => Promise<BudgetData>
  updateBudget: (id: number, budget: BudgetCreateProps) => Promise<BudgetData>
  deleteBudget: (id: number) => Promise<boolean>
  consumeBudget: (id: number, consume: BudgetConsumeProps) => Promise<TransactionData>
  getBudgetStats: (params?: BudgetStatsParams) => Promise<BudgetStats>
  getBudgetAnalysis: (id: number) => Promise<BudgetAnalysis>
}
```

### 3. API设计

```typescript
// lib/api/money.ts
api_get_budgets(params?: BudgetQueryParams): Promise<BudgetData[]>
api_get_budget(id: number): Promise<BudgetData>
api_create_budget(budget: BudgetCreateProps): Promise<BudgetData>
api_update_budget(id: number, budget: BudgetCreateProps): Promise<BudgetData>
api_delete_budget(id: number): Promise<BudgetResponse>
api_get_budget_stats(params?: BudgetStatsParams): Promise<BudgetStats>
api_consume_budget(id: number, consume: BudgetConsumeProps): Promise<TransactionData>
api_get_budget_analysis(id: number): Promise<BudgetAnalysis>
```

## 实现步骤

1. **后端实现** ✅ 已完成
   - [x] Budget模型（`sail_server/model/finance/budget.py`）
   - [x] Budget数据层（`sail_server/data/finance.py`）
   - [x] Budget控制器（`sail_server/controller/finance.py`）
   - [x] Budget路由（`sail_server/router/finance.py`）
   - [x] Budget与Transaction关联（link/unlink API）

2. **前端实现** ✅ 已完成
   - [x] Budget数据类型（`lib/data/money.ts`）
   - [x] Budget API调用（`lib/api/money.ts`）
   - [x] Budget Store（`lib/store/money.ts` - `useBudgetsStore`）
   - [x] Budget组件：
     - `budgets_data_table.tsx` - 预算列表
     - `budget_add_dialog.tsx` - 新建预算对话框
     - `budget_consume_dialog.tsx` - 预算核销对话框
     - `budget_analysis_card.tsx` - 预算分析卡片
   - [x] 集成到money页面

3. **功能测试**
   - [x] 预算CRUD功能
   - [x] 预算核销功能
   - [x] 预算统计功能
   - [x] 预算对比分析功能
   - [x] 交易关联/取消关联预算功能

## 注意事项

1. **预算与交易的关联**：通过tags和时间范围来关联，而不是直接外键
2. **金额计算**：使用Money工具类确保精度
3. **时间处理**：统一使用timestamp（秒级）
4. **错误处理**：完善的错误处理和用户提示
5. **数据一致性**：核销时验证预算剩余金额

## 扩展功能（已实现）

### 1. 预算类型支持 ✅

系统现在支持两种预算类型：
- **支出预算（EXPENSE）**：用于追踪支出，如租金、房贷、购物等
- **收入预算（INCOME）**：用于追踪收入，如工资、奖金等

### 2. 预算周期支持 ✅

支持以下周期类型：
- **一次性（ONCE）**：一次性预算，如首付款
- **月度（MONTHLY）**：每月重复，如月租、月供
- **季度（QUARTERLY）**：每季度重复
- **年度（YEARLY）**：每年重复，如年度工资

### 3. 预算子项 ✅

每个预算可以包含多个子项（BudgetItem），用于细分预算：
- 子项可以是可退还的（如押金）
- 子项支持分期追踪（如12期月租）
- 子项有独立的状态：待执行、进行中、已完成、已退还

### 4. 预算模板 ✅

系统提供三种预设模板：

#### 租房预算模板
自动创建：
- 押金子项（可退还）
- 月租金子项（按期追踪）

#### 房贷预算模板
自动创建：
- 首付款子项
- 月供子项（按期追踪）
- 利息支出子项

#### 工资预算模板
自动创建：
- 月薪子项（12期）
- 年终奖子项（可选）

---

## 使用指南

### 场景一：租房合同管理

**步骤：**
1. 点击"预算模板"按钮，选择"租房预算"
2. 填写：
   - 预算名称：如"2026年上海租房"
   - 月租金：如 3500
   - 押金：如 7000（押一付一则为一个月租金）
   - 合同开始/结束日期
3. 系统自动计算总预算并创建子项

**追踪押金退还：**
- 合同结束后，在押金子项中点击"记录退还"
- 输入退还金额，系统自动更新子项状态

**追踪月租支付：**
- 每月支付租金后，关联交易记录到该预算
- 或使用"核销"功能从预算创建交易

### 场景二：购房贷款管理

**步骤：**
1. 点击"预算模板"按钮，选择"房贷预算"
2. 填写：
   - 预算名称：如"购房贷款2026"
   - 首付款：如 500000
   - 月供：如 8000
   - 月均利息：如 3000（可选，用于追踪利息支出）
   - 贷款期数：如 360（30年）
   - 贷款开始日期

**追踪月供：**
- 每月还款后，关联交易记录到该预算
- 月供子项会自动追踪已完成期数

### 场景三：年度收入管理

**步骤：**
1. 点击"预算模板"按钮，选择"工资预算"
2. 填写：
   - 预算名称：如"2026年工资收入"
   - 月薪（税后）：如 20000
   - 年份：如 2026
   - 年终奖（可选）：如 50000

**追踪收入：**
- 每月发工资后，将收入交易关联到该预算
- 系统自动统计实际收入与预算的对比

### API 接口说明

#### 预算模板 API

```
POST /api/v1/finance/budget/template/rent
POST /api/v1/finance/budget/template/mortgage
POST /api/v1/finance/budget/template/salary
```

#### 预算子项 API

```
GET    /api/v1/finance/budget/{budget_id}/items     # 获取预算子项列表
POST   /api/v1/finance/budget/{budget_id}/items     # 创建预算子项
PUT    /api/v1/finance/budget/items/{item_id}       # 更新预算子项
DELETE /api/v1/finance/budget/items/{item_id}       # 删除预算子项
POST   /api/v1/finance/budget/items/{item_id}/refund   # 记录退还
POST   /api/v1/finance/budget/items/{item_id}/advance  # 推进期数
GET    /api/v1/finance/budget/{budget_id}/detail    # 获取预算详情（含子项）
```

---

## 数据模型扩展

### Budget 表新增字段

```sql
ALTER TABLE budgets ADD COLUMN budget_type INTEGER DEFAULT 0;  -- 0: 支出, 1: 收入
ALTER TABLE budgets ADD COLUMN period_type INTEGER DEFAULT 0;  -- 0: 一次性, 1: 月度, 2: 季度, 3: 年度
ALTER TABLE budgets ADD COLUMN start_date TIMESTAMP;           -- 开始日期
ALTER TABLE budgets ADD COLUMN end_date TIMESTAMP;             -- 结束日期
ALTER TABLE budgets ADD COLUMN category VARCHAR(50);           -- 分类: rent, mortgage, salary
```

### BudgetItem 表（新增）

```sql
CREATE TABLE budget_items (
    id SERIAL PRIMARY KEY,
    budget_id INTEGER NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    amount VARCHAR(50),
    description TEXT,
    is_refundable INTEGER DEFAULT 0,
    refund_amount VARCHAR(50) DEFAULT '0.0',
    status INTEGER DEFAULT 0,
    period_count INTEGER DEFAULT 1,
    current_period INTEGER DEFAULT 0,
    due_date TIMESTAMP,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 未来扩展（待实现）

1. 预算提醒：当预算使用率达到阈值时提醒
2. 预算审批流程：多级审批流程
3. 预算报表：生成预算执行报表
4. 预算复制：快速复制现有预算
5. 批量操作：批量关联交易到预算
