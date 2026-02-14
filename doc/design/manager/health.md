# 健康管理功能

## 概述

健康管理模块旨在帮助用户全面管理个人健康状况，包括体重追踪、健身记录、专项保养（口腔、皮肤）以及医疗杂项管理。

---

## 已实现功能

### 1. 体重管理 (Weight Management)

#### 功能描述

保持BMI长期位于健康区间

- 体重提交并展示折线图
- 体重变化趋势分析和预测功能
- 支持时间范围筛选（7天、30天、90天、1年、全部）
- 目标体重计算（线性逼近）

#### 后端实现 (sail_server)

##### 数据模型 (`data/health.py`)

```python
class Weight(ORMBase):
    __tablename__ = "weights"
    id = Column(Integer, primary_key=True)
    value = Column(String)  # 体重值 (kg)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 记录时间
    tag = Column(String, default="daily")  # 标签: raw, daily, weekly, monthly, yearly
    description = Column(String, default="")  # 描述

@dataclass
class WeightData:
    value: float
    htime: float  # Unix timestamp
    id: int = -1
    tag: str = "raw"
    description: str = ""
```

##### API 端点 (`controller/health.py`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health/weight/{weight_id}` | 获取单条体重记录 |
| GET | `/api/health/weight?skip=&limit=&start=&end=` | 获取体重列表（分页+时间过滤） |
| GET | `/api/health/weight/avg?start=&end=` | 获取时间段内平均体重 |
| GET | `/api/health/weight/target?date=` | 获取目标体重 |
| POST | `/api/health/weight` | 创建新体重记录 |

##### 业务逻辑层 (`model/health.py`)

- `create_weight_impl()` - 创建体重记录
- `read_weight_impl()` - 读取单条记录
- `read_weights_impl()` - 分页读取记录列表
- `read_weights_avg_impl()` - 计算平均体重
- `target_weight_impl()` - 线性逼近目标体重

#### 前端实现 (packages/site)

##### 页面组件 (`pages/health.tsx`)

- 日期范围选择器（预设选项 + 自定义日期）
- 体重录入对话框表单
- 体重图表容器

##### 图表组件 (`components/weight_chart.tsx`)

- 使用 Recharts 展示体重折线图
- X轴为时间，Y轴为体重值
- 支持加载状态和空数据提示

##### 状态管理 (`lib/store/health.ts`)

```typescript
interface HealthState {
  weights: WeightData[]
  isLoading: boolean
  fetchWeights: (skip, limit, start, end) => Promise<void>
  createWeight: (weight: WeightCreateProps) => Promise<void>
}
```

##### API 调用 (`lib/api/health.ts`)

- `api_get_weight(index)` - 获取单条记录
- `api_get_weights(skip, limit, start, end)` - 获取记录列表
- `api_create_weight(newWeight)` - 创建记录

---

### 2. 运动记录 (Exercise Record)

#### 功能描述

简化版的运动记录功能，用于记录日常运动活动。只包含发生时间和自然语言描述，便于快速记录。

- 运动记录的创建、查询、删除
- 自然语言描述支持
- 按时间范围筛选
- 记录列表展示

#### 后端实现 (sail_server)

##### 数据模型 (`data/health.py`)

```python
class Exercise(ORMBase):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 发生时间
    description = Column(String, default="")  # 自然语言描述

@dataclass
class ExerciseData:
    htime: float  # Unix timestamp
    id: int = -1
    description: str = ""
```

##### API 端点 (`controller/health.py`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health/exercise/{exercise_id}` | 获取单条运动记录 |
| GET | `/api/health/exercise?skip=&limit=&start=&end=` | 获取运动记录列表 |
| POST | `/api/health/exercise` | 创建新运动记录 |
| PUT | `/api/health/exercise/{exercise_id}` | 更新运动记录 |
| DELETE | `/api/health/exercise/{exercise_id}` | 删除运动记录 |

##### 业务逻辑层 (`model/health.py`)

- `create_exercise_impl()` - 创建运动记录
- `read_exercise_impl()` - 读取单条记录
- `read_exercises_impl()` - 分页读取记录列表
- `update_exercise_impl()` - 更新记录
- `delete_exercise_impl()` - 删除记录

#### 前端实现 (packages/site)

##### 数据类型 (`lib/data/health.ts`)

```typescript
export interface ExerciseCreateProps {
  htime: number
  description: string
}

export interface ExerciseData extends ExerciseCreateProps {
  id: number
}
```

##### 状态管理 (`lib/store/health.ts`)

```typescript
interface HealthState {
  // ... 体重管理状态
  exercises: ExerciseData[]
  fetchExercises: (skip, limit, start, end) => Promise<void>
  createExercise: (exercise: ExerciseCreateProps) => Promise<void>
  deleteExercise: (id: number) => Promise<void>
}
```

##### API 调用 (`lib/api/health.ts`)

- `api_get_exercises(skip, limit, start, end)` - 获取记录列表
- `api_create_exercise(newExercise)` - 创建记录
- `api_delete_exercise(id)` - 删除记录

##### 页面组件 (`pages/health.tsx`)

- 运动记录区域位于体重管理下方
- 添加运动记录按钮（打开对话框）
- 运动记录表单：
  - 日期时间选择器
  - 自然语言描述文本框
- 运动记录列表：
  - 按时间倒序排列
  - 显示日期时间和描述
  - 删除按钮

---

## 3. 健身管理 (Fitness Management) [规划中]

### 功能描述

记录和追踪日常健身活动，包括运动类型、时长、消耗热量等，帮助用户建立规律的运动习惯。

### 核心功能

- 健身记录的创建、查询、编辑、删除
- 多种运动类型支持（跑步、游泳、力量训练、瑜伽等）
- 运动统计与趋势分析
- 运动目标设定与完成度追踪
- 热量消耗估算

### 后端设计

#### 数据模型 (`data/fitness.py`)

```python
class Exercise(ORMBase):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    exercise_type = Column(String)  # 运动类型: running, swimming, strength, yoga, cycling, etc.
    duration = Column(Integer)  # 时长（分钟）
    calories = Column(Float, nullable=True)  # 消耗热量（可选，可自动估算）
    distance = Column(Float, nullable=True)  # 距离（公里，适用于跑步/骑行等）
    intensity = Column(String, default="medium")  # 强度: low, medium, high
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 运动时间
    notes = Column(String, default="")  # 备注

@dataclass
class ExerciseData:
    exercise_type: str
    duration: int
    htime: float
    id: int = -1
    calories: float = None
    distance: float = None
    intensity: str = "medium"
    notes: str = ""

class FitnessGoal(ORMBase):
    __tablename__ = "fitness_goals"
    id = Column(Integer, primary_key=True)
    goal_type = Column(String)  # weekly_duration, weekly_sessions, monthly_distance
    target_value = Column(Float)  # 目标值
    start_date = Column(TIMESTAMP)  # 开始日期
    end_date = Column(TIMESTAMP)  # 结束日期
    status = Column(String, default="active")  # active, completed, expired
```

#### API 端点 (`controller/fitness.py`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health/fitness/{id}` | 获取单条健身记录 |
| GET | `/api/health/fitness?start=&end=&type=` | 获取健身记录列表 |
| POST | `/api/health/fitness` | 创建健身记录 |
| PUT | `/api/health/fitness/{id}` | 更新健身记录 |
| DELETE | `/api/health/fitness/{id}` | 删除健身记录 |
| GET | `/api/health/fitness/stats?start=&end=` | 获取健身统计数据 |
| GET | `/api/health/fitness/goals` | 获取健身目标列表 |
| POST | `/api/health/fitness/goals` | 创建健身目标 |
| PUT | `/api/health/fitness/goals/{id}` | 更新健身目标 |

#### 业务逻辑 (`model/fitness.py`)

```python
# 伪代码示例
def create_exercise_impl(db, exercise: ExerciseData):
    """创建健身记录，自动估算热量（如未提供）"""
    if exercise.calories is None:
        exercise.calories = estimate_calories(exercise.exercise_type, 
                                               exercise.duration, 
                                               exercise.intensity)
    db_exercise = Exercise(**asdict(exercise))
    db.add(db_exercise)
    db.commit()
    return read_from_exercise(db_exercise)

def get_fitness_stats_impl(db, start_time, end_time):
    """获取时间段内的健身统计"""
    exercises = db.query(Exercise).filter(
        Exercise.htime >= start_time,
        Exercise.htime <= end_time
    ).all()
    return {
        "total_sessions": len(exercises),
        "total_duration": sum(e.duration for e in exercises),
        "total_calories": sum(e.calories for e in exercises if e.calories),
        "by_type": group_by_type(exercises)
    }

def check_goal_progress_impl(db, goal_id):
    """检查目标完成进度"""
    goal = db.query(FitnessGoal).get(goal_id)
    exercises = get_exercises_in_range(db, goal.start_date, goal.end_date)
    current_value = calculate_goal_value(exercises, goal.goal_type)
    return {
        "goal": goal,
        "current_value": current_value,
        "progress_percent": (current_value / goal.target_value) * 100
    }
```

### 前端设计

#### 数据类型 (`lib/data/fitness.ts`)

```typescript
interface ExerciseData {
  id: number
  exercise_type: string
  duration: number
  calories?: number
  distance?: number
  intensity: 'low' | 'medium' | 'high'
  htime: number
  notes: string
}

interface FitnessGoal {
  id: number
  goal_type: string
  target_value: number
  start_date: number
  end_date: number
  status: 'active' | 'completed' | 'expired'
}

interface FitnessStats {
  total_sessions: number
  total_duration: number
  total_calories: number
  by_type: Record<string, number>
}
```

#### 状态管理 (`lib/store/fitness.ts`)

```typescript
interface FitnessState {
  exercises: ExerciseData[]
  goals: FitnessGoal[]
  stats: FitnessStats | null
  isLoading: boolean
  
  fetchExercises: (start: number, end: number, type?: string) => Promise<void>
  createExercise: (exercise: ExerciseCreateProps) => Promise<void>
  updateExercise: (id: number, exercise: ExerciseUpdateProps) => Promise<void>
  deleteExercise: (id: number) => Promise<void>
  fetchStats: (start: number, end: number) => Promise<void>
  fetchGoals: () => Promise<void>
  createGoal: (goal: FitnessGoalCreateProps) => Promise<void>
}
```

#### 页面组件 (`pages/fitness.tsx`)

- 健身记录列表视图
- 日历视图（显示每日运动情况）
- 健身记录录入表单（对话框）
- 统计仪表盘（总时长、总热量、运动频率）
- 目标进度展示

#### UI 组件

- `FitnessCalendar` - 日历组件，标记有运动的日期
- `ExerciseCard` - 单条运动记录卡片
- `FitnessStatsChart` - 运动统计图表（柱状图/饼图）
- `GoalProgressBar` - 目标进度条

---

## 4. 专项保养 (Specialized Care) [规划中]

### 3.1 口腔保养 (Oral Care)

#### 功能描述

记录和管理口腔保养活动，包括日常刷牙、使用牙线、洗牙、牙科检查等，维护口腔健康。

#### 核心功能

- 日常口腔护理打卡（刷牙、牙线、漱口水）
- 牙科就诊记录（洗牙、补牙、治疗等）
- 定期提醒（洗牙提醒、复诊提醒）
- 口腔护理产品使用记录

#### 后端设计

##### 数据模型 (`data/care.py`)

```python
class OralCareRecord(ORMBase):
    __tablename__ = "oral_care_records"
    id = Column(Integer, primary_key=True)
    care_type = Column(String)  # daily_brush, floss, mouthwash, dental_visit, cleaning
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    notes = Column(String, default="")
    # 牙科就诊专用字段
    clinic_name = Column(String, nullable=True)  # 诊所名称
    dentist = Column(String, nullable=True)  # 医生
    cost = Column(Float, nullable=True)  # 费用
    next_visit = Column(TIMESTAMP, nullable=True)  # 下次就诊时间

class OralCareReminder(ORMBase):
    __tablename__ = "oral_care_reminders"
    id = Column(Integer, primary_key=True)
    reminder_type = Column(String)  # cleaning (洗牙), checkup (检查), treatment (治疗)
    remind_date = Column(TIMESTAMP)  # 提醒日期
    repeat_interval = Column(Integer, nullable=True)  # 重复间隔（天）
    status = Column(String, default="pending")  # pending, done, cancelled
    notes = Column(String, default="")
```

##### API 端点 (`controller/care.py`)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health/care/oral` | 获取口腔护理记录列表 |
| POST | `/api/health/care/oral` | 创建口腔护理记录 |
| POST | `/api/health/care/oral/daily-checkin` | 日常打卡（刷牙/牙线/漱口水） |
| GET | `/api/health/care/oral/dental-visits` | 获取牙科就诊记录 |
| POST | `/api/health/care/oral/dental-visits` | 创建牙科就诊记录 |
| GET | `/api/health/care/oral/reminders` | 获取提醒列表 |
| POST | `/api/health/care/oral/reminders` | 创建提醒 |
| PUT | `/api/health/care/oral/reminders/{id}` | 更新提醒 |

### 3.2 皮肤保养 (Skin Care)

#### 功能描述

记录和管理皮肤保养流程，追踪护肤品使用情况，监测皮肤状态变化。

#### 核心功能

- 日常护肤流程打卡（早晚护肤）
- 护肤品库存管理
- 护肤品使用效果记录
- 皮肤状态日志（干燥、出油、敏感等）
- 皮肤科就诊记录

#### 后端设计

##### 数据模型 (`data/care.py`)

```python
class SkinCareRoutine(ORMBase):
    __tablename__ = "skin_care_routines"
    id = Column(Integer, primary_key=True)
    routine_type = Column(String)  # morning, evening
    steps = Column(JSON)  # ["cleanser", "toner", "serum", "moisturizer", "sunscreen"]
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    notes = Column(String, default="")

class SkinCareProduct(ORMBase):
    __tablename__ = "skin_care_products"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # 产品名称
    brand = Column(String)  # 品牌
    category = Column(String)  # cleanser, toner, serum, moisturizer, sunscreen, mask
    purchase_date = Column(TIMESTAMP)  # 购买日期
    expiry_date = Column(TIMESTAMP, nullable=True)  # 过期日期
    open_date = Column(TIMESTAMP, nullable=True)  # 开封日期
    status = Column(String, default="in_use")  # in_use, finished, expired, discarded
    rating = Column(Integer, nullable=True)  # 评分 1-5
    notes = Column(String, default="")

class SkinConditionLog(ORMBase):
    __tablename__ = "skin_condition_logs"
    id = Column(Integer, primary_key=True)
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())
    condition = Column(String)  # normal, dry, oily, sensitive, acne, combination
    hydration = Column(Integer, nullable=True)  # 水分等级 1-10
    oiliness = Column(Integer, nullable=True)  # 油脂等级 1-10
    concerns = Column(JSON, default=[])  # ["acne", "dark_circles", "wrinkles"]
    notes = Column(String, default="")
```

##### API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health/care/skin/routines` | 获取护肤流程记录 |
| POST | `/api/health/care/skin/routines` | 创建护肤流程记录 |
| GET | `/api/health/care/skin/products` | 获取护肤品列表 |
| POST | `/api/health/care/skin/products` | 添加护肤品 |
| PUT | `/api/health/care/skin/products/{id}` | 更新护肤品信息 |
| GET | `/api/health/care/skin/condition` | 获取皮肤状态日志 |
| POST | `/api/health/care/skin/condition` | 记录皮肤状态 |

### 前端设计 (专项保养通用)

#### 数据类型 (`lib/data/care.ts`)

```typescript
// 口腔保养
interface OralCareRecord {
  id: number
  care_type: 'daily_brush' | 'floss' | 'mouthwash' | 'dental_visit' | 'cleaning'
  htime: number
  notes: string
  clinic_name?: string
  dentist?: string
  cost?: number
  next_visit?: number
}

// 皮肤保养
interface SkinCareRoutine {
  id: number
  routine_type: 'morning' | 'evening'
  steps: string[]
  htime: number
  notes: string
}

interface SkinCareProduct {
  id: number
  name: string
  brand: string
  category: string
  purchase_date: number
  expiry_date?: number
  open_date?: number
  status: 'in_use' | 'finished' | 'expired' | 'discarded'
  rating?: number
  notes: string
}

interface SkinConditionLog {
  id: number
  htime: number
  condition: string
  hydration?: number
  oiliness?: number
  concerns: string[]
  notes: string
}
```

#### 状态管理 (`lib/store/care.ts`)

```typescript
interface CareState {
  // 口腔保养
  oralRecords: OralCareRecord[]
  oralReminders: OralCareReminder[]
  
  // 皮肤保养
  skinRoutines: SkinCareRoutine[]
  skinProducts: SkinCareProduct[]
  skinConditions: SkinConditionLog[]
  
  isLoading: boolean
  
  // 口腔保养 actions
  fetchOralRecords: (start: number, end: number) => Promise<void>
  createOralRecord: (record: OralCareRecordCreateProps) => Promise<void>
  dailyOralCheckin: (types: string[]) => Promise<void>
  
  // 皮肤保养 actions
  fetchSkinRoutines: (start: number, end: number) => Promise<void>
  createSkinRoutine: (routine: SkinCareRoutineCreateProps) => Promise<void>
  fetchSkinProducts: () => Promise<void>
  addSkinProduct: (product: SkinCareProductCreateProps) => Promise<void>
  updateSkinProduct: (id: number, updates: Partial<SkinCareProduct>) => Promise<void>
  logSkinCondition: (condition: SkinConditionLogCreateProps) => Promise<void>
}
```

#### 页面组件 (`pages/care.tsx`)

- Tab 切换视图（口腔保养 / 皮肤保养）
- 日常打卡快捷面板
- 就诊/护理记录列表
- 产品库存管理面板
- 提醒管理

#### UI 组件

- `DailyCheckinCard` - 日常打卡卡片（支持多选打卡）
- `CareRecordList` - 护理记录列表
- `ProductInventory` - 产品库存管理组件
- `ReminderBadge` - 提醒徽章
- `SkinConditionLogger` - 皮肤状态记录表单

---

## 5. 医疗杂项 (Medical Miscellaneous) [规划中]

### 功能描述

管理与健康相关的杂项事务，包括医疗保险、日常药品、保养品、牙线、护手霜等日用健康物品的库存和使用管理。

### 核心功能

- 医疗保险信息管理
- 日用药品/保健品库存管理
- 健康日用品消耗追踪
- 购买记录和支出统计
- 库存预警和补货提醒

### 4.1 医疗保险管理

#### 后端设计

##### 数据模型 (`data/medical.py`)

```python
class MedicalInsurance(ORMBase):
    __tablename__ = "medical_insurances"
    id = Column(Integer, primary_key=True)
    insurance_name = Column(String)  # 保险名称
    insurance_type = Column(String)  # 类型: social (社保), commercial (商业险)
    provider = Column(String)  # 提供商/公司
    policy_number = Column(String, nullable=True)  # 保单号
    coverage_amount = Column(Float, nullable=True)  # 保额
    premium = Column(Float, nullable=True)  # 保费
    premium_period = Column(String, default="yearly")  # 缴费周期: monthly, yearly
    start_date = Column(TIMESTAMP)  # 生效日期
    end_date = Column(TIMESTAMP, nullable=True)  # 到期日期
    status = Column(String, default="active")  # active, expired, cancelled
    notes = Column(String, default="")

class InsuranceClaim(ORMBase):
    __tablename__ = "insurance_claims"
    id = Column(Integer, primary_key=True)
    insurance_id = Column(Integer, ForeignKey("medical_insurances.id"))
    claim_date = Column(TIMESTAMP)  # 理赔日期
    claim_amount = Column(Float)  # 理赔金额
    claim_type = Column(String)  # 理赔类型: outpatient, hospitalization, medication
    status = Column(String, default="pending")  # pending, approved, rejected, paid
    description = Column(String, default="")
```

### 4.2 健康用品库存管理

#### 后端设计

##### 数据模型 (`data/medical.py`)

```python
class HealthProduct(ORMBase):
    """健康用品库存"""
    __tablename__ = "health_products"
    id = Column(Integer, primary_key=True)
    name = Column(String)  # 产品名称
    category = Column(String)  # 分类: medicine (药品), supplement (保健品), 
                               #       daily_care (日用护理: 牙线、护手霜等)
    brand = Column(String, nullable=True)  # 品牌
    quantity = Column(Integer, default=1)  # 库存数量
    unit = Column(String, default="piece")  # 单位: piece, box, bottle, tube
    purchase_date = Column(TIMESTAMP, nullable=True)  # 购买日期
    expiry_date = Column(TIMESTAMP, nullable=True)  # 过期日期
    purchase_price = Column(Float, nullable=True)  # 购买价格
    purchase_location = Column(String, nullable=True)  # 购买地点
    min_stock = Column(Integer, default=1)  # 最低库存警戒线
    status = Column(String, default="in_stock")  # in_stock, low_stock, out_of_stock, expired
    notes = Column(String, default="")

class ProductUsageLog(ORMBase):
    """产品使用记录"""
    __tablename__ = "product_usage_logs"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("health_products.id"))
    usage_date = Column(TIMESTAMP, server_default=func.current_timestamp())
    quantity_used = Column(Integer, default=1)  # 使用数量
    notes = Column(String, default="")

class ProductPurchase(ORMBase):
    """产品购买记录"""
    __tablename__ = "product_purchases"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("health_products.id"))
    purchase_date = Column(TIMESTAMP)
    quantity = Column(Integer)  # 购买数量
    total_price = Column(Float)  # 总价
    purchase_location = Column(String, nullable=True)
    notes = Column(String, default="")
```

#### API 端点 (`controller/medical.py`)

| 方法 | 路径 | 描述 |
|------|------|------|
| **医疗保险** |||
| GET | `/api/health/medical/insurance` | 获取保险列表 |
| POST | `/api/health/medical/insurance` | 添加保险 |
| PUT | `/api/health/medical/insurance/{id}` | 更新保险信息 |
| DELETE | `/api/health/medical/insurance/{id}` | 删除保险 |
| GET | `/api/health/medical/insurance/{id}/claims` | 获取保险理赔记录 |
| POST | `/api/health/medical/insurance/{id}/claims` | 添加理赔记录 |
| **健康用品库存** |||
| GET | `/api/health/medical/products` | 获取产品列表 |
| GET | `/api/health/medical/products?category=&status=` | 按分类/状态筛选产品 |
| POST | `/api/health/medical/products` | 添加产品 |
| PUT | `/api/health/medical/products/{id}` | 更新产品信息 |
| DELETE | `/api/health/medical/products/{id}` | 删除产品 |
| POST | `/api/health/medical/products/{id}/use` | 记录产品使用 |
| POST | `/api/health/medical/products/{id}/purchase` | 记录产品购买/补货 |
| GET | `/api/health/medical/products/alerts` | 获取库存预警（低库存/过期） |
| **统计** |||
| GET | `/api/health/medical/stats/spending?start=&end=` | 获取支出统计 |

#### 业务逻辑 (`model/medical.py`)

```python
# 伪代码示例

def use_product_impl(db, product_id: int, quantity: int, notes: str = ""):
    """记录产品使用，更新库存"""
    product = db.query(HealthProduct).get(product_id)
    if product.quantity < quantity:
        raise ValueError("库存不足")
    
    # 记录使用
    usage_log = ProductUsageLog(
        product_id=product_id,
        quantity_used=quantity,
        notes=notes
    )
    db.add(usage_log)
    
    # 更新库存
    product.quantity -= quantity
    if product.quantity <= product.min_stock:
        product.status = "low_stock"
    if product.quantity == 0:
        product.status = "out_of_stock"
    
    db.commit()
    return product

def get_product_alerts_impl(db):
    """获取库存预警"""
    alerts = []
    
    # 低库存预警
    low_stock = db.query(HealthProduct).filter(
        HealthProduct.quantity <= HealthProduct.min_stock,
        HealthProduct.status != "out_of_stock"
    ).all()
    for p in low_stock:
        alerts.append({"type": "low_stock", "product": p, "message": f"{p.name} 库存不足"})
    
    # 过期预警（30天内过期）
    expiring_soon = db.query(HealthProduct).filter(
        HealthProduct.expiry_date <= datetime.now() + timedelta(days=30),
        HealthProduct.expiry_date > datetime.now()
    ).all()
    for p in expiring_soon:
        alerts.append({"type": "expiring", "product": p, "message": f"{p.name} 即将过期"})
    
    # 已过期
    expired = db.query(HealthProduct).filter(
        HealthProduct.expiry_date <= datetime.now()
    ).all()
    for p in expired:
        alerts.append({"type": "expired", "product": p, "message": f"{p.name} 已过期"})
    
    return alerts

def get_spending_stats_impl(db, start_time, end_time):
    """获取支出统计"""
    purchases = db.query(ProductPurchase).filter(
        ProductPurchase.purchase_date >= start_time,
        ProductPurchase.purchase_date <= end_time
    ).all()
    
    # 按类别统计
    by_category = {}
    for purchase in purchases:
        product = db.query(HealthProduct).get(purchase.product_id)
        category = product.category
        by_category[category] = by_category.get(category, 0) + purchase.total_price
    
    return {
        "total_spending": sum(p.total_price for p in purchases),
        "by_category": by_category,
        "purchase_count": len(purchases)
    }
```

### 前端设计

#### 数据类型 (`lib/data/medical.ts`)

```typescript
// 医疗保险
interface MedicalInsurance {
  id: number
  insurance_name: string
  insurance_type: 'social' | 'commercial'
  provider: string
  policy_number?: string
  coverage_amount?: number
  premium?: number
  premium_period: 'monthly' | 'yearly'
  start_date: number
  end_date?: number
  status: 'active' | 'expired' | 'cancelled'
  notes: string
}

interface InsuranceClaim {
  id: number
  insurance_id: number
  claim_date: number
  claim_amount: number
  claim_type: 'outpatient' | 'hospitalization' | 'medication'
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  description: string
}

// 健康用品
interface HealthProduct {
  id: number
  name: string
  category: 'medicine' | 'supplement' | 'daily_care'
  brand?: string
  quantity: number
  unit: string
  purchase_date?: number
  expiry_date?: number
  purchase_price?: number
  purchase_location?: string
  min_stock: number
  status: 'in_stock' | 'low_stock' | 'out_of_stock' | 'expired'
  notes: string
}

interface ProductAlert {
  type: 'low_stock' | 'expiring' | 'expired'
  product: HealthProduct
  message: string
}

interface SpendingStats {
  total_spending: number
  by_category: Record<string, number>
  purchase_count: number
}
```

#### 状态管理 (`lib/store/medical.ts`)

```typescript
interface MedicalState {
  // 保险
  insurances: MedicalInsurance[]
  claims: InsuranceClaim[]
  
  // 健康用品
  products: HealthProduct[]
  alerts: ProductAlert[]
  spendingStats: SpendingStats | null
  
  isLoading: boolean
  
  // 保险 actions
  fetchInsurances: () => Promise<void>
  addInsurance: (insurance: InsuranceCreateProps) => Promise<void>
  updateInsurance: (id: number, updates: Partial<MedicalInsurance>) => Promise<void>
  deleteInsurance: (id: number) => Promise<void>
  fetchClaims: (insuranceId: number) => Promise<void>
  addClaim: (insuranceId: number, claim: ClaimCreateProps) => Promise<void>
  
  // 健康用品 actions
  fetchProducts: (category?: string, status?: string) => Promise<void>
  addProduct: (product: ProductCreateProps) => Promise<void>
  updateProduct: (id: number, updates: Partial<HealthProduct>) => Promise<void>
  deleteProduct: (id: number) => Promise<void>
  useProduct: (id: number, quantity: number, notes?: string) => Promise<void>
  purchaseProduct: (id: number, purchase: PurchaseProps) => Promise<void>
  fetchAlerts: () => Promise<void>
  fetchSpendingStats: (start: number, end: number) => Promise<void>
}
```

#### 页面组件 (`pages/medical.tsx`)

- Tab 切换视图（医疗保险 / 健康用品）
- **保险管理面板**：
  - 保险卡片列表
  - 保险详情与理赔记录
  - 添加/编辑保险对话框
- **健康用品面板**：
  - 分类筛选（药品/保健品/日用护理）
  - 产品列表（卡片/表格视图切换）
  - 库存预警提示横幅
  - 添加产品对话框
  - 使用/补货快捷操作
  - 支出统计图表

#### UI 组件

- `InsuranceCard` - 保险信息卡片
- `ClaimHistoryList` - 理赔历史列表
- `ProductGrid` - 产品网格/列表视图
- `ProductCard` - 产品卡片（显示库存、过期状态）
- `StockAlertBanner` - 库存预警横幅
- `QuickUseButton` - 快速使用按钮
- `RestockDialog` - 补货对话框
- `SpendingChart` - 支出统计图表（按类别）

---

## 6. 路由规划

### 后端路由 (`router/health.py`)

```python
# 当前已实现的健康路由
router = Router(
    path="/health",
    dependencies={"router_dependency": Provide(get_db_dependency)},
    route_handlers=[
        WeightController,     # /api/health/weight
        ExerciseController,   # /api/health/exercise
    ],
)

# 规划中的路由
# FitnessController,    # /api/health/fitness
# CareController,       # /api/health/care (口腔/皮肤保养)
# MedicalController,    # /api/health/medical (保险/用品)
```

### 前端路由 (`App.tsx`)

```typescript
// 当前已实现的页面
<Route path="/health" element={<HealthPage />} />        {/* 体重管理 + 运动记录 */}

// 规划中的页面
<Route path="/fitness" element={<FitnessPage />} />      {/* 健身管理 */}
<Route path="/care" element={<CarePage />} />            {/* 专项保养 */}
<Route path="/medical" element={<MedicalPage />} />      {/* 医疗杂项 */}
```

---

## 7. 数据库表

### 已实现表

1. `weights` - 体重记录
2. `exercises` - 运动记录

### 规划中表

3. `fitness_goals` - 健身目标
4. `oral_care_records` - 口腔护理记录
5. `oral_care_reminders` - 口腔护理提醒
6. `skin_care_routines` - 护肤流程记录
7. `skin_care_products` - 护肤品库存
8. `skin_condition_logs` - 皮肤状态日志
9. `medical_insurances` - 医疗保险
10. `insurance_claims` - 保险理赔记录
11. `health_products` - 健康用品库存
12. `product_usage_logs` - 产品使用记录
13. `product_purchases` - 产品购买记录

---

## 8. 后续待办

- [ ] 评审数据模型设计
- [ ] 评审 API 端点设计
- [ ] 评审前端组件划分
- [ ] 确定实现优先级
- [ ] 编写详细 API 文档
- [ ] 设计 UI 原型图
- [ ] 开始实现第一阶段功能
