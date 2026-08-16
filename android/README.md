# SailZen Android App

SailZen 随身哨兵 —— 提醒触达与反馈终端（M1：提醒闭环最小可用）。

> 详细构建与验收步骤见 [`doc/design/android_app/ACCEPTANCE_M1.md`](../doc/design/android_app/ACCEPTANCE_M1.md)。

## 快速开始

1. 用 Android Studio（Koala/Ladybug+，JDK 17）**Open** 本目录（`android/`）。
2. 首次 sync 若无 wrapper，执行一次 `gradle wrapper --gradle-version 9.2`（或让 IDE 自动生成）。
3. Run `app` 到真机/模拟器（API ≥ 26，与服务器同局域网）。
4. 首次打开进入「设置」页填写服务器地址（如 `http://192.168.x.x:1974`）与 Token（服务端未配置 `SAILZEN_API_TOKEN` 可留空），保存后自动连接。

## 模块结构

```
app/src/main/java/com/sailzen/app/
├── SailZenApp.kt            # Application：通知渠道、周期同步、按需启动前台服务
├── MainActivity.kt          # 单 Activity + Navigation Compose + 通知权限
├── core/
│   ├── data/                # DataStore 设置 + Room（reminder_cache / pending_feedback）
│   ├── network/             # Retrofit API + OkHttp WebSocket 长连接（指数退避重连）
│   ├── reminder/            # 通知构建、动作路由、延后弹窗、AlarmManager 兜底
│   ├── bg/                  # 前台 Service（WS 保活 + 常驻通知）+ BootReceiver
│   └── sync/                # WorkManager 15min 补偿轮询 + 离线反馈冲刷
├── feature/
│   ├── inbox/               # 待处理列表 + 今日小结 + 历史
│   └── settings/            # 服务器/Token/安静时段/连接状态
└── ui/                      # Material3 主题 + 导航
```

## 健康管理模块（M1 升级）

本次升级将「健康」提升为底部独立 Tab，核心入口为 `HealthHomeScreen`，子模块包括：

- `feature/health/HealthHomeScreen`：今日概览、异常提示、模块入口、快速记录。
- `feature/health/weight/WeightCurveScreen` / `WeightPlanScreen`：体重曲线、计划进度与打卡状态。
- `feature/health/medication/MedicationScreen`：今日用药清单、服用打卡、添加用药。
- `feature/health/sleep/SleepScheduleScreen`：作息目标、睡眠记录、近 7 天柱状图。
- `feature/diet/DietScreen`：三餐记录、营养目标 vs 实际、热量/碳水/糖/蛋白质等。
- `feature/exercise/ExerciseScreen`：运动目标完成度、快速记录、自定义记录。
- `feature/health/HealthCheckinScreen`：统一快速入口，支持日期/时间与各类型结构化字段。

数据层：
- `core/network/HealthApi.kt` + `dto/HealthDtos.kt`：对接后端 `/api/v1/health/*`。
- `core/health/HealthRepository.kt`：封装 API 调用与日期/时间戳转换。
- `core/rhythm/RhythmRepository.kt`：离线队列已扩展 `health_*` 动作类型。
- `core/sync/SyncWorker.kt`：冲刷离线队列时同步刷新健康首页概览。

后端配套：
- `/api/v1/health/medication`、`/diet`、`/sleep`、`/sleep-schedule`、`/dashboard`。
- 健康速记 `/api/v1/rhythm/checkin/health` 已双写 `DietLog` / `Medication` / `Sleep` / `Mood` 专用表。

详见完整实施手册：`../doc/AndroidHealthPageHandbook.md`。
