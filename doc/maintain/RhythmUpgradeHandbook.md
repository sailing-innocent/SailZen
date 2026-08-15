# Rhythm-PEMS 合并升级手册

> 状态：Phase 1 审计完成，正在实施 Phase 2–5  
> 目标：将 Personal Energy Management System（PEMS）合并进 Rhythm 模块，统一个人精力/节奏管理入口；同步升级 Android 提醒-打卡闭环。

## 1. 背景与决策

### 1.1 现状

- **PEMS**（`sail_server/model/pems.py`、`controller/pems.py`、`application/dto/pems.py`、`router/pems.py`）是早期实验模块， endpoints 以 `/api/v1/pems` 暴露，但从未上线。
- **Rhythm**（`/api/v1/rhythm`）是当前活跃模块，已有事务生命周期、打卡、计划、复盘、能量配置等能力。
- Android 端当前通过 `RhythmApi` 访问 Rhythm，并通过 Reminder 模块接收推送；没有 PEMS 客户端。

### 1.2 关键决策

| 决策 | 说明 |
|------|------|
| PEMS API 整体删除 | 不保留兼容层，避免双模块维护；PEMS 未上线，无兼容风险 |
| 能力下沉到 Rhythm | DayView、能量预算、健康速记、挑战打卡、项目时间线、周期复盘全部用 Rhythm 原语重新实现 |
| 无数据迁移脚本 | PEMS schema 未执行、Rhythm 仍调试阶段，允许重建 schema |
| Android 扩展现有 Rhythm 客户端 | 不新增 PEMS client；在 `RhythmDtos.kt` / `RhythmApi.kt` 增加健康相关 DTO/接口 |
| 能量预算唯一来源 | `rhythm_energy_profile.daily_energy_budget` + 规划器计算；删除 PEMS 独立预算 |

## 2. 字段映射

### 2.1 ORM 字段

#### projects 表（PEMS 添加字段 → 删除）

| 原字段 | 来源 | 去向 | 原因 |
|--------|------|------|------|
| `timespan_id` | PEMS | 删除 | 从未迁移，Rhythm 用 `timespan_id` 在 `rhythm_affairs` |
| `energy_budget` | PEMS | 删除 | 能力并入 `rhythm_energy_profile` |
| `priority` | PEMS | 删除 | 用 `rhythm_affairs.importance` |
| `tags` | PEMS | 删除 | 未使用 |

#### missions 表（基础字段保留，但不再由 PEMS 写）

| 字段 | 说明 |
|------|------|
| `planned_minutes` | 保留，项目模块原生 |
| `actual_minutes` | 保留，项目模块原生 |
| `energy_cost` | 保留，项目模块原生 |
| `day_id` | 保留，项目模块原生 |
| `milestone_id` | 保留，项目模块原生 |
| `health_constraint` | 保留，项目模块原生 |

#### rhythm_affairs 表（新增/扩展）

| 新增/扩展字段 | 类型 | 说明 |
|---------------|------|------|
| `info_collection_type` | VARCHAR(32) nullable | `weight` / `meal` / `exercise` / `medication` / `sleep` / `mood`；用于健康速记 affair |
| `kind_meta` | JSONB/Text | 扩展支持 `weight`/`meal`/`exercise`/`medication` 子结构（见 3.3） |
| `urgency_ddl` | DateTime nullable | 已存在；规划器任务竞争入口 |
| `energy_cost` | Int nullable | 已存在；作为任务精力消耗 |
| `day_id` | FK → days nullable | 已存在；用于绑定某日 |
| `timespan_id` | FK → timespans nullable | 已存在；周期复盘绑定 |

### 2.2 DTO 映射

| PEMS DTO | Rhythm DTO | 说明 |
|----------|------------|------|
| `DayViewResponse` | `RhythmDayViewResponse`（新增） | 合并 budget、health signals、planned missions、challenge checkins、insights、note |
| `HealthLogRequest` | `HealthCheckinRequest`（新增） | 统一健康速记入口 |
| `TimespanViewResponse` | `ReviewTimespanResponse`（新增） | 绑定 `timespan_id` 的周期复盘 |
| `ProjectTimelineResponse` | `ProjectTimelineResponse`（新增） | 项目级别时间线，复用 `TimeBlockResponse` |
| `EnergyBudgetResponse` | `EnergyProfileResponse` | 直接使用能量配置 |
| `InsightDailyResponse` / `InsightWeeklyResponse` | `ReviewResponse` | 日复盘/周复盘统一 |

### 2.3 PEMS 功能 → Rhythm 功能

| PEMS 功能 | 对应 Rhythm 功能 | 实现位置 |
|-----------|------------------|----------|
| `_compute_energy_budget` | `get_or_create_profile` + planner energy budget | `model/rhythm.py`、`model/rhythm_planner.py` |
| `get_day_view_impl` | `get_rhythm_day_view_impl` | `model/rhythm.py` |
| `plan_mission_on_day_impl` | 直接创建 `task_oneoff` 并 `confirm`/`plan_day` | `controller/rhythm.py` |
| `log_health_on_day_impl` | `health_checkin_impl`（双写 `health.*` + `rhythm_discipline_log`） | `model/rhythm.py` |
| `get_timespan_view_impl` | `review_timespan_impl` + `ReviewController` | `model/rhythm.py`、`controller/rhythm.py` |
| `review_timespan_impl` | `review_timespan_impl` | `model/rhythm.py` |
| `get_project_timeline_impl` | `project_timeline_impl` | `model/rhythm.py` |
| `get_energy_budget_impl` | `get_energy_profile_impl` | `model/rhythm.py` |
| `get_insight_daily_impl` | `get_review_impl(date, scope="day")` | `model/rhythm.py` |
| `get_insight_weekly_impl` | `review_week_impl` | `model/rhythm.py` |
| `_challenge_checkins` | `precept`/`habit` affairs + `RhythmDisciplineLog` | `model/rhythm.py` |

## 3. Schema 变更详情

### 3.1 删除字段（projects 表）

```sql
-- 仅作说明；因 PEMS 未上线，本次直接修改 ORM 并重建/增量即可
ALTER TABLE projects DROP COLUMN IF EXISTS timespan_id;
ALTER TABLE projects DROP COLUMN IF EXISTS energy_budget;
ALTER TABLE projects DROP COLUMN IF EXISTS priority;
ALTER TABLE projects DROP COLUMN IF EXISTS tags;
```

### 3.2 新增字段（rhythm_affairs 表）

```sql
ALTER TABLE rhythm_affairs ADD COLUMN IF NOT EXISTS info_collection_type VARCHAR(32) NULL;
```

### 3.3 kind_meta 扩展（健康速记）

```json
{
  "weight": {"value_kg": 70.5, "measured_at": "2026-10-27T08:00:00"},
  "meal": {"meal_type": "breakfast", "foods": ["燕麦", "鸡蛋"], "estimated_calories": 400},
  "exercise": {"activity": "跑步", "duration_minutes": 30, "intensity": "moderate"},
  "medication": {"name": "维生素D", "dose": "1粒", "taken_at": "2026-10-27T08:30:00"}
}
```

## 4. API 变更

### 4.1 删除的 endpoints

| Endpoint | 替代 |
|----------|------|
| `GET /api/v1/pems/day/{date}` | `GET /api/v1/rhythm/day-view?date=...` |
| `POST /api/v1/pems/day/{date}/plan` | `POST /api/v1/rhythm/affair/` + `POST /api/v1/rhythm/plan/day` |
| `POST /api/v1/pems/health` | `POST /api/v1/rhythm/health-checkin` |
| `GET /api/v1/pems/timespan/{id}` | `GET /api/v1/rhythm/review/timespan/{id}` |
| `POST /api/v1/pems/timespan/{id}/review` | `POST /api/v1/rhythm/review/timespan/{id}` |
| `GET /api/v1/pems/project/{id}/timeline` | `GET /api/v1/rhythm/review/project/{id}/timeline` |
| `GET /api/v1/pems/energy-budget` | `GET /api/v1/rhythm/energy/profile` |
| `GET /api/v1/pems/insight/daily` | `GET /api/v1/rhythm/review/day?date=...` |
| `GET /api/v1/pems/insight/weekly` | `GET /api/v1/rhythm/review/week?span=...` |

### 4.2 新增/扩展的 endpoints

| Endpoint | 方法 | 说明 |
|----------|------|------|
| `/api/v1/rhythm/affair/` | `GET` | 新增 `urgency_ddl_before`、`urgency_ddl_after` 过滤 |
| `/api/v1/rhythm/day-view` | `GET` | 统一日视图 |
| `/api/v1/rhythm/health-checkin` | `POST` | 健康速记 |
| `/api/v1/rhythm/review/timespan/{id}` | `GET/POST` | 周期视图/复盘 |
| `/api/v1/rhythm/review/project/{id}/timeline` | `GET` | 项目时间线 |

## 5. Android 变更

### 5.1 DTO 新增

- `HealthCheckinRequest`：字段 `collection_type`、`log_date`、`payload: JsonObject`。
- `HealthCheckinPayloadWeight` / `Meal` / `Exercise` / `Medication`：具体 payload 结构。
- `RhythmDayViewDto`：合并时间线、能量、打卡、健康信号。

### 5.2 API 新增

- `RhythmApi.healthCheckin(body: HealthCheckinRequest): HealthCheckinLogDto`
- `RhythmApi.dayView(date: String): RhythmDayViewDto`
- `RhythmApi.reviewTimespan(timespanId: Int): ReviewDto`
- `RhythmApi.projectTimeline(projectId: Int): ProjectTimelineDto`

### 5.3 界面

- 新增 `feature/health/HealthCheckinScreen.kt`、`HealthCheckinViewModel.kt`。
- `NavGraph` 增加 `health_checkin` route（从提醒/推送 deep link 进入）。
- 提醒 ActionReceiver 增加 `checkin_weight`、`checkin_meal` 等 action 路由。

## 6. 提醒系统对接

- Reminder payload 增加解析字段：`<affair_id>`、`<checkin_kind>`、`<meal_type>`、`<collection_type>`。
- `rhythm_daily_brief` 类型的提醒由 scheduler 生成（TBD）。
- 静音时段默认取 sleep window（`rhythm_energy_profile.sleep_start/end`），fallback `22:00-07:00`。

## 7. 测试与验证

1. `uv run pytest tests/server/test_rhythm_*.py` 全部通过。
2. 新增测试：`test_health_checkin_dual_write`、`test_rhythm_day_view`、`test_urgency_ddl_range_query`。
3. Android `./gradlew lintDebug` 无新增错误（如环境允许）。

## 8. 回滚与补丁

- 不直接 push；变更通过 `git format-patch` 输出到 `patches/YYYY-MM-DD-sailzen-rhythm-pems-merge.patch`。
- 回滚：不 apply patch 或 `git checkout` 还原。
