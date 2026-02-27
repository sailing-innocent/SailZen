# 健康管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| WeightRecord | 体重记录 | value, record_time |

## 功能

- 体重记录与趋势图
- 平均体重计算
- 目标体重预测（线性逼近）

## API 概览

```
GET  /api/v1/health/weight/          # 体重记录列表
POST /api/v1/health/weight/          # 创建记录
GET  /api/v1/health/weight/stats     # 统计数据
GET  /api/v1/health/weight/predict   # 目标预测
```

## 待实现

- 健身管理（运动类型、时长、热量）
- 口腔/皮肤保养打卡
- 健康用品库存
