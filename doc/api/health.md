# 健康管理 API

## 📋 功能概述

健康管理模块提供通用身体数据记录与趋势分析、体重记录追踪、运动记录、体重计划与预测等功能。

### 核心功能

| 功能 | 说明 |
|------|------|
| **身体数据** | 多指标记录（体重/BMI/体脂等），指标定义动态下发，单指标曲线与趋势分析 |
| **体重记录** | 记录每日体重，支持时间范围查询（由身体数据 dual-write 兼容维护） |
| **体重分析** | 趋势线分析、目标预测 |
| **体重计划** | 制定减重/增重计划，追踪进度 |
| **运动记录** | 记录运动类型、时长、消耗 |
| **睡眠记录** | 记录睡眠时长与质量 |
| **用药记录** | 每日用药计划、打卡、依从性 |
| **饮食记录** | 三餐记录、营养目标与实际对比 |
| **作息目标** | 设定就寝/起床时间与目标睡眠时长 |
| **健康概览** | 首页聚合今日/近 7 天健康数据 |

---

## ⚖️ 体重记录 API

### 获取体重记录列表

```http
GET /api/v1/health/weight
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 10，-1 表示全部） |
| start | float | 否 | 开始时间戳 |
| end | float | 否 | 结束时间戳 |

**响应:**
```json
[
  {
    "id": 1,
    "value": 70.5,
    "record_time": 1700000000,
    "htime": 1700000000
  }
]
```

---

### 获取单个体重记录

```http
GET /api/v1/health/weight/{weight_id}
```

---

### 获取目标体重

```http
GET /api/v1/health/weight/target?date=2024-01-15
```

根据当前体重计划，获取指定日期的目标体重。

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 是 | 日期格式 YYYY-MM-DD |

---

### 创建体重记录

```http
POST /api/v1/health/weight/
```

**请求体:**
```json
{
  "value": 70.5,           // 体重值（kg）
  "record_time": 1700000000  // 记录时间（可选，默认当前时间）
}
```

**响应:**
```json
{
  "id": 1,
  "value": 70.5,
  "record_time": 1700000000,
  "htime": 1700000000
}
```

---

### 获取平均体重

```http
GET /api/v1/health/weight/avg
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start | float | 否 | 开始时间戳 |
| end | float | 否 | 结束时间戳 |

**响应:**
```json
{
  "result": 70.25
}
```

---

## 📈 体重分析 API

### 体重趋势分析

```http
GET /api/v1/health/weight/analysis
```

分析体重变化趋势，返回线性或多项式拟合结果。

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start | float | 否 | 开始时间戳 |
| end | float | 否 | 结束时间戳 |
| model_type | string | 否 | 模型类型：linear（默认）/ polynomial |

**响应:**
```json
{
  "slope": -0.05,              // 每日变化斜率（kg/天）
  "intercept": 75.0,           // 截距
  "r_squared": 0.85,           // 拟合度
  "current_trend": "decreasing", // 趋势：decreasing/increasing/stable
  "daily_change": -0.05,       // 日均变化
  "weekly_change": -0.35,      // 周均变化
  "model": "linear"            // 使用的模型
}
```

---

### 体重预测

```http
GET /api/v1/health/weight/prediction
```

预测未来某时间的体重。

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| target_time | float | 是 | 目标时间戳 |
| model_type | string | 否 | 模型类型（默认 linear） |
| start | float | 否 | 数据开始时间 |
| end | float | 否 | 数据结束时间 |

**响应:**
```json
{
  "predicted_weight": 68.5,
  "target_time": 1700000000
}
```

---

## 🎯 体重计划 API

### 获取当前体重计划

```http
GET /api/v1/health/weight/plan/
```

**响应:**
```json
{
  "id": 1,
  "start_weight": 75.0,
  "target_weight": 65.0,
  "start_time": 1700000000,
  "target_time": 1704067200,
  "daily_change": -0.1,
  "is_active": true
}
```

---

### 创建体重计划

```http
POST /api/v1/health/weight/plan/
```

**请求体:**
```json
{
  "start_weight": 75.0,      // 起始体重
  "target_weight": 65.0,     // 目标体重
  "start_time": 1700000000,  // 开始时间
  "target_time": 1704067200  // 目标达成时间
}
```

**说明:** 系统会自动计算 `daily_change`（每日应减重量）。

---

### 获取计划进度

```http
GET /api/v1/health/weight/plan/progress
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| plan_id | int | 否 | 计划ID（默认当前激活计划） |

**响应:**
```json
{
  "plan": { ... },              // 计划详情
  "current_weight": 70.5,       // 当前体重
  "expected_weight": 71.0,      // 计划预期体重
  "progress_percent": 45.0,     // 进度百分比
  "control_rate": 0.8,          // 控制率（实际/预期）
  "remaining_days": 30,         // 剩余天数
  "predicted_completion": 1703000000  // 预测完成时间
}
```

---

### 获取带状态的体重记录

```http
GET /api/v1/health/weight/plan/weights-with-status
```

获取体重记录并与计划对比，显示状态。

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start | float | 否 | 开始时间戳 |
| end | float | 否 | 结束时间戳 |
| plan_id | int | 否 | 计划ID |

**响应:**
```json
[
  {
    "id": 1,
    "value": 70.5,
    "record_time": 1700000000,
    "expected_value": 71.0,
    "status": "below",    // below: 低于预期（好，绿色）
    "diff": -0.5          // above: 高于预期（差，红色）
  }                       // normal: 正常范围（蓝色）
]
```

---

## 📊 身体数据 API

通用身体数据记录：一次打卡可携带多个指标，指标定义由服务端动态下发。`data` 含 `weight` 且 `source=manual` 时服务端 dual-write 到体重记录表，体重计划与旧体重端点保持兼容；删除记录时级联清理关联体重记录。

### 获取身体数据记录列表
```http
GET /api/v1/health/body-data
```
**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 10，-1 表示全部） |
| start | float | 否 | 开始时间戳（秒） |
| end | float | 否 | 结束时间戳（秒） |

**响应:** `BodyDataResponse[]`（按时间降序）
---
### 创建身体数据记录
```http
POST /api/v1/health/body-data
```
**请求体:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| htime | float | 否 | 发生时间戳（秒），None 为当前时间 |
| data | object | 是 | 指标集合，如 `{"weight": 70.5, "body_fat": 18.2}`；缺失字段视为未测量 |
| tag | string | 否 | 记录标签（默认 `raw`） |
| description | string | 否 | 记录描述 |

**校验：** 未知指标 key 拒绝（自定义 key 须 `x_` 前缀）；内置指标做 min/max 范围校验（越界 422）。`data` 含 `weight` 时同步写体重记录。
---
### 获取指标定义列表
```http
GET /api/v1/health/body-data/metrics
```
返回内置指标 + 历史记录中发现的自定义指标，含中文标签、单位、分类、小数位与合法范围。

**响应:** `BodyMetricDefinition[]`
---
### 获取单指标时序
```http
GET /api/v1/health/body-data/series?metric=weight
```
**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| metric | string | 是 | 指标 key |
| start | float | 否 | 开始时间戳（秒） |
| end | float | 否 | 结束时间戳（秒） |

**响应:** `{ "metric": "weight", "unit": "kg", "points": [{ "id": 1, "htime": 1700000000, "value": 70.5 }] }`（按时间升序）
---
### 获取单指标趋势分析
```http
GET /api/v1/health/body-data/analysis?metric=weight
```
**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| metric | string | 是 | 指标 key |
| model_type | string | 否 | 拟合模型（默认线性） |
| start | float | 否 | 开始时间戳（秒） |
| end | float | 否 | 结束时间戳（秒） |

**响应:** `{ "current_value": 70.5, "slope": -0.05, "r_squared": 0.92, "predicted_points": [...] }`
---
### 获取单条身体数据记录
```http
GET /api/v1/health/body-data/{record_id}
```
---
### 更新身体数据记录
```http
PUT /api/v1/health/body-data/{record_id}
```
**请求体:** 同创建，字段均可选；`weight` 变化会同步更新关联体重记录。
---
### 删除身体数据记录
```http
DELETE /api/v1/health/body-data/{record_id}
```
**响应:** `{ "deleted": true, "id": 1 }`；若 dual-write 产生过体重记录则级联删除。
---
## 🏃 运动记录 API

### 获取运动记录列表

```http
GET /api/v1/health/exercise
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| skip | int | 否 | 跳过记录数（默认 0） |
| limit | int | 否 | 返回记录数（默认 -1） |
| start | float | 否 | 开始时间戳 |
| end | float | 否 | 结束时间戳 |

**响应:**
```json
[
  {
    "id": 1,
    "exercise_type": "跑步",
    "duration": 30,          // 分钟
    "calories": 300,         // 千卡
    "record_time": 1700000000,
    "htime": 1700000000
  }
]
```

---

### 获取单个运动记录

```http
GET /api/v1/health/exercise/{exercise_id}
```

---

### 创建运动记录

```http
POST /api/v1/health/exercise/
```

**请求体:**
```json
{
  "exercise_type": "跑步",
  "duration": 30,
  "calories": 300,
  "record_time": 1700000000  // 可选，默认当前时间
}
```

---

### 更新运动记录

```http
PUT /api/v1/health/exercise/{exercise_id}
```

**请求体:** 同创建

---

### 删除运动记录

```http
DELETE /api/v1/health/exercise/{exercise_id}
```

---

## 🖥️ 前端 API 客户端

### 导入

```typescript
import {
  // 体重记录
  api_get_weights,
  api_get_weight,
  api_create_weight,
  api_get_weights_avg,
  
  // 体重分析
  api_analyze_weight_trend,
  api_predict_weight,
  
  // 体重计划
  api_get_weight_plan,
  api_create_weight_plan,
  api_get_weight_plan_progress,
  api_get_weights_with_status,
  
  // 运动记录
  api_get_exercises,
  api_create_exercise,
  api_delete_exercise,
} from '@lib/api/health'
```

### 使用示例

```typescript
// 记录今日体重
const weight = await api_create_weight({
  value: 70.5,
  record_time: Date.now() / 1000
})

// 获取最近30天的体重记录
const thirtyDaysAgo = Date.now() / 1000 - 30 * 24 * 3600
const weights = await api_get_weights(0, -1, thirtyDaysAgo)

// 获取体重趋势分析
const analysis = await api_analyze_weight_trend(
  thirtyDaysAgo,
  undefined,
  'linear'
)
console.log(`日均变化: ${analysis.daily_change} kg`)
console.log(`趋势: ${analysis.current_trend}`)

// 预测30天后的体重
const futureTime = Date.now() / 1000 + 30 * 24 * 3600
const prediction = await api_predict_weight(futureTime)
console.log(`预测体重: ${prediction.predicted_weight} kg`)

// 创建减重计划
const plan = await api_create_weight_plan({
  start_weight: 75.0,
  target_weight: 65.0,
  start_time: Date.now() / 1000,
  target_time: Date.now() / 1000 + 90 * 24 * 3600  // 90天
})

// 获取计划进度
const progress = await api_get_weight_plan_progress()
console.log(`进度: ${progress.progress_percent}%`)
console.log(`控制率: ${progress.control_rate}`)

// 获取带状态的体重记录
const weightsWithStatus = await api_get_weights_with_status()
weightsWithStatus.forEach(w => {
  const statusText = w.status === 'below' ? '✅ 低于预期' :
                     w.status === 'above' ? '⚠️ 高于预期' : '➡️ 正常'
  console.log(`${new Date(w.record_time * 1000).toLocaleDateString()}: ${w.value}kg ${statusText}`)
})

// 记录运动
const exercise = await api_create_exercise({
  exercise_type: '跑步',
  duration: 30,
  calories: 300
})
```

---

## 📦 数据类型

### WeightData

```typescript
interface WeightData {
  id: number
  value: number        // 体重（kg）
  record_time: number  // 记录时间戳
  htime: number        // 创建时间戳
}
```

### WeightAnalysisResult

```typescript
interface WeightAnalysisResult {
  slope: number           // 斜率
  intercept: number       // 截距
  r_squared: number       // 拟合度
  current_trend: 'decreasing' | 'increasing' | 'stable'
  daily_change: number    // 日均变化
  weekly_change: number   // 周均变化
  model: string
}
```

### WeightPlanData

```typescript
interface WeightPlanData {
  id: number
  start_weight: number    // 起始体重
  target_weight: number   // 目标体重
  start_time: number      // 开始时间
  target_time: number     // 目标时间
  daily_change: number    // 每日应减重量
  is_active: boolean      // 是否激活
}
```

### WeightPlanProgress

```typescript
interface WeightPlanProgress {
  plan: WeightPlanData
  current_weight: number
  expected_weight: number
  progress_percent: number
  control_rate: number    // >1 表示比预期慢，<1 表示比预期快
  remaining_days: number
  predicted_completion?: number
}
```

### WeightRecordWithStatus

```typescript
interface WeightRecordWithStatus {
  id: number
  value: number
  record_time: number
  expected_value: number  // 计划预期体重
  status: 'above' | 'below' | 'normal'
  diff: number           // 与预期的差值
}
```

### ExerciseData

```typescript
interface ExerciseData {
  id: number
  exercise_type: string   // 运动类型
  duration: number        // 时长（分钟）
  calories: number        // 消耗热量（千卡）
  record_time: number
  htime: number
}
```

### ExerciseCreateProps

```typescript
interface ExerciseCreateProps {
  exercise_type: string
  duration: number
  calories: number
  record_time?: number
}
```

---

### BodyDataResponse
```typescript
interface BodyDataResponse {
  id: number
  htime: number          // 发生时间戳（秒）
  data: Record<string, number>  // 本次测量的指标集合
  tag: string
  description: string
  source: string         // 记录来源（manual 等）
  weight_id?: number     // dual-write 关联的体重记录 ID
}
```
---
### BodyDataCreateRequest
```typescript
interface BodyDataCreateRequest {
  htime?: number
  data: Record<string, number>
  tag?: string
  description?: string
}
```
---
### BodyMetricDefinition
```typescript
interface BodyMetricDefinition {
  key: string            // 唯一标识，自定义指标以 x_ 开头
  label_zh: string
  label_en: string
  unit: string           // kg / cm / % 等
  category: string       // 体成分/围度/生命体征/... 
  precision: number
  min?: number
  max?: number
  higher_is_better: boolean
  builtin: boolean
}
```
---
*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
---
## 💊 用药记录 API

## 💊 用药记录 API

### 获取用药记录列表

```http
GET /api/v1/health/medication
```

**参数:**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| date | string | 否 | 日期 YYYY-MM-DD |
| taken | bool | 否 | 是否已服用 |
| skip | int | 否 | 跳过记录数 |
| limit | int | 否 | 返回记录数，-1 表示全部 |

**响应:**
```json
[
  {
    "id": 1,
    "name": "维生素 D",
    "dosage": "500mg",
    "frequency": "daily",
    "schedule_times": ["08:00", "20:00"],
    "planned_date": "2026-08-10",
    "taken": true,
    "taken_at": 1700000000
  }
]
```

### 创建用药记录

```http
POST /api/v1/health/medication
```

**请求体:**
```json
{
  "name": "维生素 D",
  "dosage": "500mg",
  "frequency": "daily",
  "schedule_times": ["08:00", "20:00"],
  "planned_date": "2026-08-10",
  "taken": false,
  "is_supplement": true
}
```

### 更新服用状态

```http
PUT /api/v1/health/medication/{id}
```

**请求体:**
```json
{
  "taken": true,
  "taken_at": 1700000000
}
```

### 今日用药清单与完成率

```http
GET /api/v1/health/medication/today?date=2026-08-10
```

### 近 N 天依从性统计

```http
GET /api/v1/health/medication/stats?days=7&end_date=2026-08-10
```

---

## 🍽️ 饮食记录 API

### 获取饮食记录

```http
GET /api/v1/health/diet?date=2026-08-10&meal_type=lunch
```

### 创建饮食记录

```http
POST /api/v1/health/diet
```

**请求体:**
```json
{
  "meal_type": "lunch",
  "description": "鸡胸肉沙拉",
  "calories": 450,
  "carbs": 30,
  "sugar": 5,
  "protein": 35,
  "fat": 12,
  "fiber": 8,
  "sodium": 320
}
```

### 当日饮食汇总与目标对比

```http
GET /api/v1/health/diet/summary?date=2026-08-10
```

### 设置/获取营养目标

```http
POST /api/v1/health/diet/goal
GET /api/v1/health/diet/goal?date=2026-08-10
```

---

## 😴 睡眠/作息 API

### 睡眠记录

```http
GET /api/v1/health/sleep
POST /api/v1/health/sleep
```

**POST 请求体:**
```json
{
  "hours": 7.5,
  "quality": 4,
  "description": ""
}
```

### 作息目标

```http
GET /api/v1/health/sleep-schedule?date=2026-08-10
POST /api/v1/health/sleep-schedule
```

**POST 请求体:**
```json
{
  "date": "2026-08-10",
  "bed_time": "23:00",
  "wake_time": "07:00",
  "target_hours": 8.0
}
```

---

## 📊 健康首页聚合 API

```http
GET /api/v1/health/dashboard?date=2026-08-10
```

**响应:**
```json
{
  "date": "2026-08-10",
  "weight": { "latest": 70.5, "plan_target": 70.0, "status": "normal" },
  "sleep": { "last_night_hours": 7.5, "goal": 8.0, "status": "normal" },
  "exercise": { "today_minutes": 30, "goal_minutes": 45, "completed": false },
  "medication": { "total": 3, "taken": 2, "compliance": 0.67 },
  "diet": { "calories_actual": 1800, "calories_goal": 2000, "sugar_actual": 45, "sugar_goal": 50 },
  "mood": { "score": 4 },
  "warnings": ["今日运动未达标", "昨日睡眠不足"]
}
```

---

*本文档由 AI Agent 维护，已同步 M1 健康升级。*
