# Rhythm-PEMS 合并升级手册

> 状态：**已完成合并与闭环升级**  
> 版本：`sailserver 0.3.0`  
> 目标：将 Personal Energy Management System（PEMS）合并进 Rhythm 模块，统一个人精力/节奏管理入口；补齐 Android 端信息收集与提醒闭环。

---

## 1. 背景与决策

### 1.1 现状

- **PEMS**（`sail_server/model/pems_legacy.py` 审计参考）是早期实验模块，endpoints 以 `/api/v1/pems` 暴露，但从未上线。
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
| 提醒统一生成 | `reminder` 调度器扫描 Rhythm 数据，每日生成 `rhythm.daily_brief` / `rhythm.meal` / `rhythm.weight` / `rhythm.exercise` / `rhythm.work_focus` 提醒 |

---

## 2. 字段映射

### 2.1 ORM 字段

#### projects 表（PEMS 添加字段 → 删除）

| 原字段 | 来源 | 去向 | 原因 |
|--------|------|------|------|
| `energy_budget` | PEMS | 删除 | 能力并入 `rhythm_energy_profile` |
| `priority` | PEMS | 删除 | 用 `rhythm_affairs.importance` |
| `tags` | PEMS | 删除 | 未使用 |

（`timespan_id` 为项目模块原生字段，予以保留。）

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
| `kind_meta` | JSONB/Text | 扩展支持 `weight`/`meal`/`exercise`/`medication` 子结构 |
| `urgency_ddl` | DateTime nullable | 规划器任务竞争入口 |
| `energy_cost` | Int nullable | 任务精力消耗 |
| `day_id` | FK → days nullable | 绑定某日 |
| `timespan_id` | FK → timespans nullable | 周期复盘绑定 |


## 4. Schema 变更

### 4.1 删除字段（projects 表）

```sql
-- 仅作说明；因 PEMS 未上线，本次直接修改 ORM 并重建/增量即可
ALTER TABLE projects DROP COLUMN IF EXISTS energy_budget;
ALTER TABLE projects DROP COLUMN IF EXISTS priority;
ALTER TABLE projects DROP COLUMN IF EXISTS tags;
```

### 4.2 新增字段（rhythm_affairs 表）

```sql
ALTER TABLE rhythm_affairs ADD COLUMN IF NOT EXISTS info_collection_type VARCHAR(32) NULL;
```

### 4.3 kind_meta 扩展（健康速记）

```json
{
  "weight": {"value_kg": 70.5, "measured_at": "2026-10-27T08:00:00"},
  "meal": {"meal_type": "breakfast", "foods": ["燕麦", "鸡蛋"], "estimated_calories": 400},
  "exercise": {"activity": "跑步", "duration_minutes": 30, "intensity": "moderate"},
  "medication": {"name": "维生素D", "dose": "1粒", "taken_at": "2026-10-27T08:30:00"}
}
```

---

## 5. API 变更

### 5.1 删除的 endpoints

| Endpoint | 替代 |
|----------|------|
| `GET /api/v1/pems/day/{date}` | `GET /api/v1/rhythm/timeline/day-view?date=...` |
| `POST /api/v1/pems/day/{date}/plan` | `POST /api/v1/rhythm/affair/` + `POST /api/v1/rhythm/plan/day` |
| `POST /api/v1/pems/health` | `POST /api/v1/rhythm/checkin/health` |
| `GET /api/v1/pems/timespan/{id}` | `GET /api/v1/rhythm/review/timespan/{id}` |
| `GET /api/v1/pems/project/{id}/timeline` | `GET /api/v1/rhythm/review/project/{project_id}` |
| `GET /api/v1/pems/energy-budget` | `GET /api/v1/rhythm/energy/profile` |
| `GET /api/v1/pems/insight/daily` | `GET /api/v1/rhythm/review/day?date=...` |
| `GET /api/v1/pems/insight/weekly` | `GET /api/v1/rhythm/review/week?span=...` |

### 5.2 新增/扩展的 endpoints

| Endpoint | 方法 | 说明 |
|----------|------|------|
| `/api/v1/rhythm/affair/` | `GET` | 新增 `urgency_ddl_before`、`urgency_ddl_after` 过滤 |
| `/api/v1/rhythm/timeline/day-view` | `GET` | 统一日视图 |
| `/api/v1/rhythm/checkin/health` | `POST` | 健康速记 |
| `/api/v1/rhythm/review/timespan/{id}` | `GET` | 周期视图 |
| `/api/v1/rhythm/review/project/{project_id}` | `GET` | 项目时间线 |

---

## 6. Android 变更

### 6.1 DTO 新增

- `InfoCollectionType` 枚举
- `HealthCheckinRequest` / `HealthCheckinResponse`
- `RhythmDayViewDto` / `HealthSignalItemDto`
- `ProjectTimelineDto` / `ReviewTimespanDto`

### 6.2 API 新增

- `RhythmApi.healthCheckin`
- `RhythmApi.dayView`
- `RhythmApi.reviewTimespan`
- `RhythmApi.projectTimeline`

### 6.3 界面

- 新增 `feature/health/HealthCheckinScreen.kt`、`HealthCheckinViewModel.kt`。
- `CheckinScreen` 增加“健康打卡”入口，跳转 `health_checkin`。
- `TimelineScreen` 增加“今日健康信号摘要”卡片。
- `NavGraph` 增加 `health_checkin?type={type}` 路由，支持深链。
- `RhythmRepository` 支持离线健康打卡队列，`SyncWorker` 冲刷时补传。

---

## 7. 提醒闭环用例

| 用例 | 触发 | 推送 | 用户动作 | 回写 | 评分 |
|------|------|------|----------|------|------|
| 早安 brief | 调度器读取 `sleep_end` | `rhythm.daily_brief` | 打开 App | 无 | 无 |
| 体重打卡 | 调度器发现今日无 `weights` 记录 | `rhythm.weight` | 进入 HealthCheckinScreen | `POST /checkin/health` 双写 `weights` + `discipline_log` | 日复盘更新 |
| 三餐打卡 | 固定时间 08:00/12:00/18:30 | `rhythm.meal` | 记录饮食 | `POST /checkin/health` | 日复盘更新 |
| 运动提醒 | 调度器发现运动 habit 未完成 | `rhythm.exercise` | 完成运动打卡 | `POST /checkin/health` | 习惯一致性提升 |
| 工作焦点 | 09:30 | `rhythm.work_focus` | 查看 timeline | 无 | 无 |
| 睡眠提醒 | `sleep_start` 前 30 分钟 | `rhythm.daily_brief` | 早睡 | 无 | 睡眠窗守约率提升 |

### 7.1 深链参数

Reminder payload 支持以下字段，供 Android 路由使用：

- `affair_id`: 关联 rhythm_affair
- `checkin_kind`: `kept` / `violated` / `done` / `missed`
- `meal_type`: `早餐` / `午餐` / `晚餐` / `snack`
- `collection_type`: `weight` / `meal` / `exercise` / `medication` / `sleep` / `mood`
- `deep_link`: `health_checkin?type=weight`

### 7.2 安静时段

默认安静时段与 Rhythm 睡眠窗对齐，fallback 为 `22:00-07:00`。提醒投递与 scheduler 生成均会跳过安静时段。

---

## 8. 测试与验证

1. `uv run pytest tests/server` 全量通过。
2. `uv run python scripts/rhythm_pems_scope_check.py` 输出全部已覆盖。
3. 新增测试覆盖：`test_health_checkin_dual_write`、`test_rhythm_day_view`、`test_urgency_ddl_range_query`。
4. Android `./gradlew lintDebug` 无新增错误（如环境允许；当前环境 JDK 下载被锁，未能执行）。

---

## 9. Android 构建与验收步骤

1. 打开 `android/` 工程，等待 Gradle sync。
2. 配置服务器地址：`Settings → 服务器地址`（如 `http://<pc-ip>:8000`）。
3. 启动后端：`uv run python server.py`。
4. 在 Android Studio 运行 App（真机或模拟器）。
5. 验证：
   - 接收作息/运动/工作/事务提醒；
   - 记录体重、三餐、运动、剂量；
   - 查看时间线、打卡、事业、周评分；
   - 断网操作后恢复网络自动同步（离线队列）。

---

## 10. 回滚方案与已知限制

### 10.1 回滚

- 不直接 push；变更通过 `git format-patch` 输出到 `patches/YYYY-MM-DD-sailzen-rhythm-pems-merge.patch`。
- 回滚：不 apply patch 或 `git checkout` 还原。
- 无数据迁移脚本：PEMS 未上线，Rhythm 也处于调试阶段，schema 调整直接重建。

### 10.2 已知限制

- `review_timespan_impl` 目前按日聚合 `ReviewResponse` 近似计算，未完整实现 precept/habit/sleep 跨日统计。
- Android 健康打卡 UI 将体重/运动/饮食/用药/睡眠/心情整合在单屏，未拆分为四页。
- 真机/模拟器构建需在用户本地 Android Studio 完成，当前 CI 环境无法下载 JDK 25 工具链。

---

## 11. 相关文件

- `sail_server/model/pems_legacy.py`：审计参考（原 PEMS 模型）。
- `sail_server/model/rhythm.py`：Rhythm 业务模型。
- `sail_server/model/rhythm_planner.py`：排程与复盘算法。
- `sail_server/model/reminder.py`：提醒状态机与 payload 解析。
- `sail_server/model/reminder_scheduler.py`：调度扫描 + rhythm daily brief 生成。
- `sail_server/controller/rhythm.py`：Rhythm REST API。
- `scripts/rhythm_pems_scope_check.py`：合并范围检查脚本。
