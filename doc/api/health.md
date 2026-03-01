# 健康管理 API

> **版本**: v1.0 | **更新**: 2026-03-01 | **状态**: 已完成

---

## 📋 功能概述

健康管理模块提供体重记录追踪、运动记录、体重计划与预测等功能。

### 核心功能

| 功能 | 说明 |
|------|------|
| **体重记录** | 记录每日体重，支持时间范围查询 |
| **体重分析** | 趋势线分析、目标预测 |
| **体重计划** | 制定减重/增重计划，追踪进度 |
| **运动记录** | 记录运动类型、时长、消耗 |

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

*本文档由 AI Agent 维护，如有疑问请参考源代码或联系开发团队。*
