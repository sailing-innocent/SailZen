# 健康管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| BodyData | 通用身体数据记录（一次打卡可携带多个指标） | htime, data(JSONB), tag, description, source, weight_id |
| BodyMetricDefinition | 指标定义（内置清单 + 自定义动态发现） | key, label_zh/en, unit, category, precision, min/max |
| WeightRecord | 体重记录（legacy，由 BodyData dual-write 维护） | value, record_time |
| WeightPlan | 体重计划 | target, deadline, daily_change |

## 身体数据（Body Data）

- 一次记录可携带多个指标（weight / bmi / body_fat / ...），缺失字段 = 未测量
- 指标定义由 `GET /body-data/metrics` 动态下发，客户端不硬编码清单
- 自定义指标：`x_` 前缀逃生舱，服务端从已有记录的 data key 动态发现并返回定义
- 校验：未知 key 拒绝；内置指标做 min/max 范围校验（越界 422）
- **dual-write**：`data` 含 `weight` 且 `source=manual` 时同步写 weights 表（savepoint 包裹），
  保证体重计划与旧 `/weight` 端点兼容；删除 body_data 记录时级联清理关联体重记录
- 历史体重数据由 `migration/20260906_backfill_body_data.py` 幂等回填（可重入）

## 功能

- 多指标身体数据记录与单指标趋势曲线
- 单指标趋势分析（线性拟合：当前值 / 日变化 / 拟合度 / 预测点）
- 体重记录与趋势图（经 dual-write 兼容保留）
- 平均体重计算、目标体重预测（线性逼近）
- 体重计划（减重/增重目标与进度追踪）
- 运动记录、睡眠记录、用药记录、饮食记录（见 API 文档）

## API 概览

```
GET    /api/v1/health/body-data            # 身体数据记录列表
POST   /api/v1/health/body-data            # 创建记录（多指标）
GET    /api/v1/health/body-data/metrics    # 指标定义（动态下发）
GET    /api/v1/health/body-data/series     # 单指标时序 ?metric=
GET    /api/v1/health/body-data/analysis   # 单指标趋势分析 ?metric=&model_type=
GET    /api/v1/health/body-data/{id}       # 单条记录
PUT    /api/v1/health/body-data/{id}       # 更新记录
DELETE /api/v1/health/body-data/{id}       # 删除（级联清理 weights）

GET  /api/v1/health/weight/                # 体重记录列表（legacy 兼容）
POST /api/v1/health/weight/                # 创建记录
GET  /api/v1/health/weight/stats           # 统计数据
GET  /api/v1/health/weight/predict         # 目标预测
```

## 三端实现

- 后端：`sail_server/{application/dto,model,controller}/body_data.py`，路由挂于 `router/health.py`
- 前端（site）：`site/src/lib/{data,api,store}/body_data.ts` + `components/health/body_{metric_picker,data_chart,data_record_dialog,data_history_list}.tsx`
- Android：`feature/health/bodydata/`（录入 + 曲线双页面）、`core/network/HealthApi.kt`、`core/health/HealthRepository.kt`

## 待实现

- 口腔/皮肤保养打卡
- 健康用品库存
