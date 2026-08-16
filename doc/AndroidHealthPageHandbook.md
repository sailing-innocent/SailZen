# SailZen Android 健康管理页面升级实施手册

> 本手册记录本次 AI Agent 对健康模块升级的实施结果，供后续人工接手构建、调试时核对。

## 一、后端变更

### 1.1 数据模型扩展

文件: `sail_server/infrastructure/orm/health.py`

- `Exercise` 新增字段：`exercise_type`、`duration_minutes`、`calories`、`completed`、`source`。
- 新增 `Medication` 表：记录药品/保健品、剂量、频次、计划日期、服用状态。
- 新增 `DietLog` 表：记录三餐/零食、热量、碳水、糖、蛋白质、脂肪、纤维、钠、微量元素。
- 新增 `NutritionGoal` 表：按日期设定营养目标。
- 新增 `SleepScheduleGoal` 表：按日期设定就寝/起床时间与目标睡眠时长。

### 1.2 DTO 扩展

文件: `sail_server/application/dto/health.py`

- `ExerciseBase` / `ExerciseCreateRequest` / `ExerciseResponse` 增加结构化字段。
- 新增 `Medication*`、`Diet*`、`NutritionGoal*`、`SleepScheduleGoal*` DTO。
- 新增 `HealthDashboardResponse` 及子项 DTO。

### 1.3 业务层实现

文件: `sail_server/model/health.py`

- 用药 CRUD、今日清单、依从性统计。
- 饮食 CRUD、当日汇总、营养目标读写。
- 作息目标读写。
- 健康首页聚合 `health_dashboard_impl`，含体重/睡眠/运动/用药/饮食/心情概览与警告生成。

### 1.4 控制器与路由

文件: `sail_server/controller/health.py`、`sail_server/router/health.py`

新增 Controller：
- `SleepController`
- `SleepScheduleController`
- `MedicationController`
- `DietController`
- `HealthDashboardController`
- `MoodController`

新增路由挂载：`/sleep`、`/sleep-schedule`、`/medication`、`/diet`、`/dashboard`、`/mood`。

### 1.5 Rhythm 健康速记双写

文件: `sail_server/model/rhythm.py`

`health_checkin_impl` 在收到 `meal`/`medication`/`sleep`/`mood` 时，不再只写 `HealthSignal`，而是分别调用 `create_diet_impl`、`create_medication_impl`、`create_sleep_impl`、`create_mood_impl`，并保留 `HealthSignal` 双写。

### 1.6 数据库迁移

文件: `sail_server/migration/20261120_health_upgrade.sql`

包含 `exercises` 扩展、`medications`、`diet_logs`、`nutrition_goals`、`sleep_schedule_goals` 建表及索引。

### 1.7 健康闹钟本地提醒（Phase 5 部分）

- `HealthAlarmScheduler`：根据今日未服用用药计划和作息目标设置 `AlarmManager`。
- `AlarmReceiver` 扩展：识别用药/就寝/起床闹钟并弹出通知。
- `NotificationHelper` 新增健康通知渠道与用药/作息通知。
- `HealthAlarmActionReceiver`：处理「已服用」动作，直接上报服务端。
- `MedicationViewModel` / `SleepScheduleViewModel` 在加载数据后调度本地提醒。

## 二、Android 数据层变更

### 2.1 DTO 与 API

文件: `android/app/src/main/java/com/sailzen/app/core/network/dto/HealthDtos.kt`
文件: `android/app/src/main/java/com/sailzen/app/core/network/HealthApi.kt`

新增所有健康相关 DTO 与 Retrofit 接口，覆盖体重/体重计划/运动/睡眠/作息/用药/饮食/营养目标/聚合首页。

### 2.2 客户端工厂

文件: `android/app/src/main/java/com/sailzen/app/core/network/ApiClient.kt`

新增 `healthApi(...)` 缓存工厂。

### 2.3 仓库

文件: `android/app/src/main/java/com/sailzen/app/core/health/HealthRepository.kt`

封装 HealthApi，提供首页/体重/计划/运动/睡眠/作息/用药/饮食/营养目标的读写方法，并统一日期/时间戳转换。

### 2.4 离线队列扩展

文件: `android/app/src/main/java/com/sailzen/app/core/rhythm/RhythmRepository.kt`

`flushPending` 增加 `health_weight`、`health_exercise`、`health_sleep`、`health_medication`、`health_diet` 补传逻辑。

## 三、Android UI 变更

### 3.1 导航与 Tab

文件: `android/app/src/main/java/com/sailzen/app/ui/navigation/NavGraph.kt`

- 底部导航新增「健康」Tab（`Routes.HEALTH`）。
- 新增子路由：体重曲线、体重计划、用药节律、作息节律、饮食三餐、必备运动、健康速记。

### 3.2 新增页面

- `HealthHomeScreen` + `HealthHomeViewModel`：今日概览、模块入口、异常提示、快速记录菜单。
- `WeightCurveScreen` + `WeightCurveViewModel`：实际记录与计划预期曲线（Canvas 自绘）。
- `WeightPlanScreen` + `WeightPlanViewModel`：活跃计划、创建/编辑计划、控制率与打卡状态。
- `MedicationScreen` + `MedicationViewModel` + `MedicationEditDialog`：今日清单、服用打卡、添加用药。
- `SleepScheduleScreen` + `SleepScheduleViewModel`：作息目标、记录睡眠、近 7 天柱状图。
- `DietScreen` + `DietViewModel` + `DietEditDialog`：营养目标 vs 实际、三餐列表、添加饮食。
- `ExerciseScreen` + `ExerciseViewModel`：运动目标完成度、快速记录、自定义记录。

### 3.3 通用组件

文件: `android/app/src/main/java/com/sailzen/app/ui/components/`

- `SectionCard.kt`：首页模块卡片。
- `Charts.kt`：Canvas 折线图、柱状图。
- `ProgressRing.kt`：环形进度。
- `DateRangeSelector.kt`：日期范围选择。

### 3.4 健康速记扩展

文件: `android/app/src/main/java/com/sailzen/app/feature/health/HealthCheckinScreen.kt`
文件: `android/app/src/main/java/com/sailzen/app/feature/health/HealthCheckinViewModel.kt`

新增日期/时间选择，各类型字段对齐新 DTO：体重测量时间、饮食餐次/热量、用药名称剂量/已服用、睡眠时长/质量、运动类型/时长/热量。

### 3.5 文案

文件: `android/app/src/main/res/values/strings.xml`

新增健康模块相关文案。

## 四、测试与验证

- 后端已跑通：`uv run pytest tests/server/test_health_api.py`（10 passed）
- 后端已跑通：`uv run pytest tests/server/test_rhythm_checkin.py tests/server/test_rhythm_api.py`（23 passed）
- Android 构建因环境无 gradle 未运行，需人工在 Android Studio 中完成编译与测试。

## 五、已知待完善项（后续人工/迭代）

1. **Phase 4 剩余**：为 medication/exercise/sleep/diet 创建独立 `RhythmAffair` 并联动打卡统计；目前仅通过 `health_checkin` 统一写入日志。
2. **Phase 5 已完成项**：用药/作息本地 `AlarmManager` 提醒与通知动作已 wired；`SCHEDULE_EXACT_ALARM` 已在 `AndroidManifest.xml` 声明。开机后需重新调度（可后续在 `BootReceiver` 中补充）。
3. **Android 测试**：已新增 `HealthDateUtilsTest` 与 `HealthHomeViewModelTest` 作为起点；Android 编译需人工在 Android Studio 中验证。
4. **图表优化**：当前 Canvas 图表为 M1 简化版，后续可替换为 MPAndroidChart 或 Compose 图表库。
5. **日期选择器**：HealthHomeScreen 当前仅用 TextButton 占位，需接入 Material DatePicker。

## 六、文件清单汇总

### 后端
- `sail_server/infrastructure/orm/health.py`
- `sail_server/infrastructure/orm/__init__.py`
- `sail_server/application/dto/health.py`
- `sail_server/model/health.py`
- `sail_server/model/rhythm.py`
- `sail_server/controller/health.py`
- `sail_server/router/health.py`
- `sail_server/migration/20261120_health_upgrade.sql`

### Android
- `android/app/src/main/java/com/sailzen/app/core/network/dto/HealthDtos.kt`
- `android/app/src/main/java/com/sailzen/app/core/network/HealthApi.kt`
- `android/app/src/main/java/com/sailzen/app/core/network/ApiClient.kt`
- `android/app/src/main/java/com/sailzen/app/core/health/HealthAlarmScheduler.kt`
- `android/app/src/main/java/com/sailzen/app/core/health/HealthAlarmActionReceiver.kt`
- `android/app/src/main/java/com/sailzen/app/core/health/HealthDateUtils.kt`
- `android/app/src/main/java/com/sailzen/app/core/rhythm/RhythmRepository.kt`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/sailzen/app/core/reminder/AlarmReceiver.kt`
- `android/app/src/main/java/com/sailzen/app/core/reminder/NotificationHelper.kt`
- `android/app/src/test/java/com/sailzen/app/core/health/HealthDateUtilsTest.kt`
- `android/app/src/test/java/com/sailzen/app/feature/health/HealthHomeViewModelTest.kt`
- `android/app/src/main/java/com/sailzen/app/ui/navigation/NavGraph.kt`
- `android/app/src/main/java/com/sailzen/app/ui/components/*.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/HealthHomeScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/HealthHomeViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/HealthCheckinScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/HealthCheckinViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/weight/WeightCurveScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/weight/WeightCurveViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/weight/WeightPlanScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/weight/WeightPlanViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/medication/MedicationScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/medication/MedicationViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/sleep/SleepScheduleScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/health/sleep/SleepScheduleViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/diet/DietScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/diet/DietViewModel.kt`
- `android/app/src/main/java/com/sailzen/app/feature/exercise/ExerciseScreen.kt`
- `android/app/src/main/java/com/sailzen/app/feature/exercise/ExerciseViewModel.kt`
- `android/app/src/main/res/values/strings.xml`

### 文档
- `doc/api/health.md`
- `doc/AndroidHealthPageHandbook.md`

---

*手册由 AI Agent 根据升级计划生成，后续请按 Phase 4/5 剩余项继续迭代。*
