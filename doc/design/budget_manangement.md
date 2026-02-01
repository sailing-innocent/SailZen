# 预算管理系统设计文档

## 概述

预算管理系统是在现有记账管理系统基础上扩展的功能模块，用于管理预算计划、跟踪预算执行情况，并支持从预算创建实际交易记录（预算核销）。

## 设计原则

1. **通用化设计**：使用统一的数据模型支持所有业务场景（租房、房贷、工资等）
2. **配置驱动**：模板只是前端的"预设配置"，后端提供通用 API
3. **可扩展性**：用户可以自定义预算项，不受预设模板限制
4. **RESTful API**：遵循 RESTful API 设计规范

---

## 核心概念

### Budget（预算）
预算是一个容器，包含多个 BudgetItem。预算本身只存储元信息（名称、日期、标签等），金额由子项汇总计算。

### BudgetItem（预算项）
预算的基本单元，所有业务场景都使用相同的数据结构。通过以下属性来描述不同的业务需求：

| 属性 | 说明 | 示例 |
|------|------|------|
| `direction` | 方向 | 0=支出, 1=收入 |
| `item_type` | 类型 | 0=固定金额, 1=周期性金额 |
| `amount` | 金额 | 固定型=总额, 周期型=单期金额 |
| `period_count` | 期数 | 固定型=1, 周期型=实际期数 |
| `is_refundable` | 可退还 | 0=否, 1=是（如押金） |

### 统一模型示例

| 业务场景 | 子项 | direction | item_type | amount | period_count | is_refundable |
|----------|------|-----------|-----------|--------|--------------|---------------|
| 租房 | 押金 | EXPENSE | FIXED | 7000 | 1 | 1 |
| 租房 | 月租 | EXPENSE | PERIODIC | 3500 | 12 | 0 |
| 房贷 | 首付 | EXPENSE | FIXED | 500000 | 1 | 0 |
| 房贷 | 月供 | EXPENSE | PERIODIC | 8000 | 360 | 0 |
| 工资 | 月薪 | INCOME | PERIODIC | 20000 | 12 | 0 |
| 工资 | 年终奖 | INCOME | FIXED | 50000 | 1 | 0 |

---

## 数据模型设计

### Budget 表

```sql
CREATE TABLE budgets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,           -- 预算名称
    description TEXT,                      -- 预算描述
    tags VARCHAR(255),                     -- 标签（逗号分隔）
    start_date TIMESTAMP,                  -- 开始日期
    end_date TIMESTAMP,                    -- 结束日期
    total_amount VARCHAR(50) DEFAULT '0.0', -- 总金额（由子项汇总）
    htime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 生效时间
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### BudgetItem 表

```sql
CREATE TABLE budget_items (
    id SERIAL PRIMARY KEY,
    budget_id INTEGER NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    
    -- 基本信息
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- 核心属性
    direction INTEGER DEFAULT 0,           -- 0: 支出, 1: 收入
    item_type INTEGER DEFAULT 0,           -- 0: 固定金额, 1: 周期性金额
    amount VARCHAR(50) DEFAULT '0.0',      -- 金额
    period_count INTEGER DEFAULT 1,        -- 期数
    
    -- 可退还属性
    is_refundable INTEGER DEFAULT 0,
    refund_amount VARCHAR(50) DEFAULT '0.0',
    
    -- 进度追踪
    current_period INTEGER DEFAULT 0,
    status INTEGER DEFAULT 0,              -- 0:待执行 1:进行中 2:已完成 3:已退还
    
    due_date TIMESTAMP,
    ctime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mtime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Python 数据类

```python
class BudgetDirection(IntEnum):
    EXPENSE = 0  # 支出
    INCOME = 1   # 收入

class ItemType(IntEnum):
    FIXED = 0     # 固定金额
    PERIODIC = 1  # 周期性金额

class ItemStatus(IntEnum):
    PENDING = 0     # 待执行
    IN_PROGRESS = 1 # 进行中
    COMPLETED = 2   # 已完成
    REFUNDED = 3    # 已退还

@dataclass
class BudgetItemData:
    id: int
    budget_id: int
    name: str
    description: str
    direction: int      # BudgetDirection
    item_type: int      # ItemType
    amount: str
    period_count: int
    is_refundable: int
    refund_amount: str
    current_period: int
    status: int         # ItemStatus
    due_date: Optional[float]
    total_amount: str       # 计算属性
    remaining_periods: int  # 计算属性
```

---

## API 设计

### Budget CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/budget/` | 获取预算列表 |
| GET | `/finance/budget/{id}` | 获取预算详情 |
| POST | `/finance/budget/` | 创建预算 |
| PUT | `/finance/budget/{id}` | 更新预算 |
| DELETE | `/finance/budget/{id}` | 删除预算 |
| GET | `/finance/budget/{id}/detail` | 获取预算（含子项） |

### Budget Item CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/budget/{id}/items` | 获取预算子项列表 |
| POST | `/finance/budget/{id}/items` | 创建预算子项 |
| PUT | `/finance/budget/items/{id}` | 更新预算子项 |
| DELETE | `/finance/budget/items/{id}` | 删除预算子项 |
| POST | `/finance/budget/items/{id}/refund` | 记录退还 |
| POST | `/finance/budget/items/{id}/advance` | 推进期数 |

### 创建预算子项请求体

```json
{
  "name": "月租金",
  "description": "每月租金",
  "direction": 0,        // 0: 支出, 1: 收入
  "item_type": 1,        // 0: 固定, 1: 周期性
  "amount": "3500",      // 单期金额
  "period_count": 12,    // 期数
  "is_refundable": 0     // 是否可退还
}
```

### 统计和分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/finance/budget/stats/` | 获取预算统计 |
| GET | `/finance/budget/{id}/analysis` | 获取预算分析 |

### 交易关联

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/finance/budget/{id}/consume` | 从预算创建交易 |
| POST | `/finance/budget/{id}/link/{trans_id}` | 关联交易到预算 |
| DELETE | `/finance/budget/unlink/{trans_id}` | 取消交易关联 |

---

## 前端设计

### 预设模板（配置驱动）

模板只是前端的预设配置，不需要后端专用 API。所有预算创建都使用统一的接口。

```typescript
// 预设模板定义
export const RENT_PRESET: BudgetPreset = {
  type: 'rent',
  name: '租房预算',
  description: '追踪租金和押金',
  defaultTags: 'rent,housing',
  itemPresets: [
    {
      name: '押金',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.FIXED,
      amount: '0',
      period_count: 1,
      is_refundable: 1,
    },
    {
      name: '月租金',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.PERIODIC,
      amount: '0',
      period_count: 12,
      is_refundable: 0,
    },
  ],
}
```

### 创建预算流程

1. 用户选择预设模板（租房/房贷/工资/自定义）
2. 模板自动填充预算项配置
3. 用户可以修改、添加、删除预算项
4. 提交时调用统一的 `create_budget_with_items` 接口

---

## 使用指南

### 场景一：租房合同管理

**步骤：**
1. 点击"预算模板"按钮
2. 选择"租房预算"预设
3. 填写：
   - 预算名称：如"2026年上海租房"
   - 开始/结束日期
   - 押金金额：如 7000
   - 月租金额：如 3500
   - 租期（期数）：如 12 个月
4. 点击"创建预算"

**追踪押金退还：**
- 合同结束后，在押金子项中点击"记录退还"
- 输入退还金额，系统自动更新状态

**追踪月租支付：**
- 每月支付租金后，关联交易记录到该预算
- 或使用"核销"功能从预算创建交易
- 子项会自动追踪已完成期数

### 场景二：购房贷款管理

**步骤：**
1. 选择"房贷预算"预设
2. 填写：
   - 首付款金额：如 500000
   - 月供金额：如 8000
   - 贷款期数：如 360（30年）
   - 贷款开始日期
3. 可选：添加"利息支出"子项追踪利息

### 场景三：年度收入管理

**步骤：**
1. 选择"工资收入"预设
2. 填写：
   - 月薪金额：如 20000
   - 期数：12
   - 年终奖金额：如 50000（可选）
3. 创建预算

**注意**：工资预算的子项 direction 为 INCOME（收入），只能关联收入类交易

### 场景四：自定义预算

1. 选择"自定义"预设
2. 点击"添加项目"创建子项
3. 为每个子项设置：
   - 名称
   - 方向（收入/支出）
   - 类型（固定/周期性）
   - 金额和期数
   - 是否可退还

---

## 设计优势

1. **DRY 原则**：所有业务场景使用同一套数据模型和 API，无代码重复
2. **可扩展性**：新增业务场景只需添加前端预设配置，无需修改后端
3. **灵活性**：用户可以自定义任意组合的预算项
4. **类型安全**：统一的数据结构便于类型检查和验证
5. **易维护**：单一代码路径，降低维护成本

---

## 与旧版本的区别

| 特性 | 旧版本 | 新版本 |
|------|--------|--------|
| 模板 | 后端硬编码 API | 前端配置驱动 |
| 数据模型 | 多种特化模型 | 统一通用模型 |
| 扩展性 | 需要后端改动 | 只需前端配置 |
| 代码量 | 重复代码多 | 精简统一 |

---

## 注意事项

1. **金额计算**：使用 Money 工具类确保精度
2. **时间处理**：统一使用 timestamp（秒级）
3. **总金额**：由子项自动汇总，创建/更新子项时自动重新计算
4. **状态管理**：子项状态由操作自动更新（advance、refund）
