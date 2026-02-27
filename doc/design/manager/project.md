# 项目管理设计

## 核心模型

| 模型 | 说明 | 关键字段 |
|------|------|----------|
| Project | 项目 | name, state, start_time, end_time |
| Mission | 任务 | name, project_id, state, ddl, parent_id |

## 状态机

### 项目状态
```
INVALID → VALID → PREPARE → TRACKING → DONE
                              ↓
                           PENDING
任意状态 → CANCELED
```

### 任务状态
```
PENDING → READY → DOING → DONE
任意状态 → CANCELED
```

## API 概览

```
GET  /api/v1/project/project/           # 项目列表
GET  /api/v1/project/mission/           # 任务列表
POST /api/v1/project/mission/{id}/done  # 完成任务
POST /api/v1/project/mission/{id}/postpone # 延期任务
GET  /api/v1/project/mission/upcoming   # 即将到期
GET  /api/v1/project/mission/overdue    # 逾期任务
```

## 时间系统

使用 `QuarterBiWeekTime` 进行项目规划：
- 每年4季度，每季度6个双周
- 格式: `[year][quarter][biweek]` (如 202611 表示 2026年Q1第1个双周)
