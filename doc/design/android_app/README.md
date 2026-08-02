# SailZen Android App 设计文档

> **版本**: v0.1 (Draft)
> **更新**: 2026-08-02
> **状态**: 📋 待 Review
> **关联文档**: [PRD](../../PRD.md) | [系统架构总览](../overview.md) | [Autonomous Agent 设计](../agent-system/autonomous-agent.md)

---

## 1. 背景与定位

### 1.1 为什么需要 Android 原生 App

当前 SailZen 已有 `sail_server`（永不休眠的后端）与 `packages/site`（Web 管理台），但二者都依赖**用户主动打开浏览器**才能产生价值。日常管理中有一类场景本质上是"被动"的——人不记得去看网页，事情就过去了：

| 场景 | 主动网页访问的缺陷 | App 的解法 |
|------|---------------------|------------|
| 消息提醒（喝水/吃药/休息/任务到期） | 不开网页就永远看不到 | 系统级通知直接触达 |
| 拍摄记录饮食 | 要先开电脑/开网页/传照片，摩擦过大 | 掏出手机拍照即完成 |
| 随手记录日常（灵感、心情、日记切片） | 灵感转瞬即逝，等打开网页已经忘了 | 秒开输入框/语音输入 |
| 打卡上下班 | 人已经到公司/离开公司，不会再开网页补 | 到点提醒 + 一键打卡 |
| 长期事务跟进 | 长期事务的难点正是"容易被日常淹没" | 周期性被动提醒维持存在感 |

这些场景的共性是：**需要系统在合适的时刻主动找到人，而不是人等系统**。只有常驻手机的原生 App 具备后台监控、系统通知、相机、定位、锁屏可见这些能力。PWA / 移动网页在国产 ROM 上无法保证后台存活与可靠推送，因此选择 **Android 原生**而非跨端方案。

### 1.2 产品定位

> **App 不是 Web 功能的搬运工，而是 SailZen 的"触手与哨兵"。**

- **sail_site** = 主动管理台：坐在电脑前做规划、复盘、深度编辑。
- **vscode_plugin** = 笔记工作台：长文本与知识体系的维护。
- **Android App** = 随身哨兵：被动接收提醒并给出反馈、在产生数据的第一现场随手采集。

设计原则：

1. **被动触达优先**：App 的第一公民是"提醒"而非"页面"。所有功能模块都从提醒入口反向组织。
2. **三秒原则**：任何采集类操作（拍照、随手记、打卡）从解锁手机到完成不超过 3 秒、不超过 3 次点击。
3. **反馈即数据**：用户对提醒的每一次反馈（忽视/延后/处理）都必须落库，成为 Agent 学习用户习惯的语料。
4. **Server 是唯一事实源**：App 本地只做缓存与离线队列，不产生权威数据，换机/重装不丢数据。
5. **私有部署友好**：不依赖 FCM / Google Play 服务，适配国内 ROM 环境。

### 1.3 在整体架构中的位置

```
┌────────────────────────────────────────────────────────────────────────┐
│                              用户触点层                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │  Web Browser │  │ VSCode Plugin│  │   Android App (本文档)        │  │
│  │  (site)      │  │              │  │   ┌────────────────────────┐ │  │
│  │  主动管理台   │  │ 笔记工作台    │  │   │ 提醒收件箱 / 随手采集  │ │  │
│  └──────┬───────┘  └──────┬───────┘  │   │ 后台长连接 / 本地闹钟   │ │  │
│         │                 │          │   └────────────────────────┘ │  │
│         │                 │          └──────────────┬───────────────┘  │
│         │      HTTP /api/v1 (WebSocket 用于实时推送) │                 │
│         └─────────────────┼─────────────────────────┘                  │
│                           │                                            │
│              ┌────────────▼────────────┐                               │
│              │   sail_server (Litestar)│                               │
│              │   + reminder 模块(新增)  │◄── 提醒调度与反馈状态机        │
│              │   + attendance 模块(新增)│                               │
│              │   PostgreSQL            │                               │
│              └────────────▲────────────┘                               │
│                           │ HTTP API only                               │
│              ┌────────────┴────────────┐                               │
│              │  Autonomous Agent        │ 提醒的"生产者"：               │
│              │  (cron pipelines + LLM)  │ 扫描数据 → 生成提醒意图        │
│              └─────────────────────────┘                               │
└────────────────────────────────────────────────────────────────────────┘
```

职责边界（遵循 Agent 系统的隔离原则）：

- **Agent 是提醒的生产者**：通过 cron pipeline（如 `finance_anomaly_scan`、`health_monitor`）发现"该提醒的事"，调用 sail_server 的 reminder API 创建提醒。Agent **不直接**接触 App。
- **sail_server reminder 模块是调度与状态中枢**：负责持久化提醒、按时投递、接收反馈、执行反馈对应的后续策略、维护状态机。
- **App 是触达与反馈终端**：维持长连接接收提醒、以系统通知呈现、采集用户反馈上报、提供采集类功能入口。

---

## 2. 核心机制：提醒与反馈闭环

这是整个 App 的灵魂，先于任何具体功能模块设计。

### 2.1 概念模型

| 概念 | 说明 |
|------|------|
| `Reminder` | 一条待触达的提醒。包含触发时间、内容、优先级、关联业务对象、可用动作 |
| `ReminderEvent` | 提醒生命周期中发生的每一次事件（创建/投递/反馈/升级/过期），不可变日志 |
| `Feedback` | 用户对提醒的一次反馈：**忽略 (dismiss) / 延后 (snooze) / 处理 (handle)** |
| `ReminderRule` | 某类提醒的行为策略：重试间隔、升级阈值、安静时段、反馈后处理方案 |
| `Device` | 注册的 App 设备，用于长连接寻址与投递确认 |

### 2.2 提醒生命周期状态机

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
  PENDING ──投递──► DELIVERED ──dismiss──► IGNORED ──► ARCHIVED│
    ▲  ▲            │                                          │
    │  │            ├──snooze────► SNOOZED ──到点──► (回到 PENDING，snooze_count+1)
    │  │            │
    │  │            ├──handle────► OPENED ──完成业务动作──► RESOLVED
    │  │            │                  │
    │  │            │                  └──未完成退出──► (回到 DELIVERED，打开次数+1)
    │  │            │
    │  │            └──超时无反馈──► EXPIRED ──按规则重投──┘
    │  │
    │  └──snooze 到点重新入队
    │
    └──Agent/调度器创建
```

| 状态 | 含义 |
|------|------|
| `PENDING` | 已入队，等待到达触发时间 |
| `DELIVERED` | 已推送到设备并以系统通知展示 |
| `SNOOZED` | 用户选择延后，携带 `next_trigger_time` 等待再次触发 |
| `OPENED` | 用户点击"处理"进入 App，但业务动作尚未完成 |
| `RESOLVED` | 业务动作完成（终态） |
| `IGNORED` | 用户明确忽略（终态，进入学习数据） |
| `EXPIRED` | 投递后超过有效期无任何反馈，按规则重投或归档 |
| `CANCELED` | 被创建者（Agent/用户）撤销（终态） |

### 2.3 三类反馈与后续处理方案

用户要求的"每一次反馈要对应不同的后续处理方案"是设计的核心约束：

#### 2.3.1 处理 (Handle / Act)

通知栏按钮：`处理`（点击打开 App 内对应处理页）

后续处理：
1. 上报 `feedback=handle`，状态 → `OPENED`，App 深链打开对应业务页（见 §2.4 动作路由表）。
2. 用户在处理页完成业务动作（如：确认打卡、提交饮食记录、把任务标记完成）后，客户端调用业务 API + `feedback=resolve`，状态 → `RESOLVED`。
3. 若用户打开后未完成就退出：保留 `OPENED`，30 分钟后降级回 `DELIVERED` 并可触发一次温和的系统通知（"刚才的事还没处理完"）。
4. `RESOLVED` 时向 Agent 回写事件，作为 pipeline 的输入（例如任务完成后更新项目进度快照）。

#### 2.3.2 延后 (Snooze)

通知栏按钮：`延后`（展开二级选项：15分钟 / 1小时 / 今晚 / 明天）

后续处理：
1. 上报 `feedback=snooze` + `snooze_option`，服务端计算 `next_trigger_time`，状态 → `SNOOZED`，`snooze_count += 1`。
2. 到点自动重新入队投递。
3. **连续延后升级策略**（可配置，默认值）：
   - `snooze_count >= 3`：优先级提升一级（normal → high），通知改为强提醒（响铃+震动）。
   - `snooze_count >= 5`：触发 `escalated` 事件，通知 Agent 重新评估——该提醒是否时间设定不合理？是否应该拆小、改时段、或者与用户"谈谈"（生成一条由 LLM 撰写的、更有针对性的提醒文案）。
   - 升级事件写入 `ReminderEvent`，供周报展示"本周你逃避最多的事"。
4. 部分类型（如上下班打卡）支持**智能延后**：结合地理位置，到地理围栏边界内才重新提醒。

#### 2.3.3 忽略 (Dismiss)

通知栏按钮：`忽略`（通知左滑清除等价于忽略）

后续处理：
1. 上报 `feedback=dismiss`，状态 → `IGNORED`，本次提醒终止，**当日不再重投**。
2. 忽略不是免费动作，进入习惯学习：
   - 同类型提醒 7 日内被忽略 ≥ 3 次 → 服务端自动下调该类型提醒频率一个档位（如每日 → 隔日），并在周报中提示"这类提醒你可能不需要了，建议调整规则"。
   - 同类型提醒连续 14 日 100% 被忽略 → 自动暂停该规则，转入 `ARCHIVED`，由用户在设置中手动恢复。
3. 忽略事件全部提供给 Agent 的长期记忆：Agent 逐渐学会"这个人在什么时段/什么场景下从不理某类提醒"，调整未来的提醒生成策略。
4. 高优先级提醒（`priority=urgent`）不允许单次滑动忽略——必须显式点击"忽略"并二次确认，防止误触。

#### 2.3.4 无反馈 (Expire)

通知展示超过有效期（默认 4 小时，按类型可配）未产生任何交互：
1. 状态 → `EXPIRED`，记录 `expired` 事件。
2. 按 `ReminderRule.retry_policy` 决定：重投（最多 N 次）、改时段重投、或直接归档。
3. 长期无反馈的类型与忽略同等对待，进入习惯学习。

#### 2.3.5 反馈与后续处理对照总表

| 反馈 | 即时效果 | 服务端后续处理 | Agent 学习 |
|------|----------|----------------|------------|
| 处理→完成 | 状态 `RESOLVED` | 回写业务模块（打卡/饮食/任务状态） | 正向样本：该时段/形式有效 |
| 处理→未完成退出 | 状态回落 `DELIVERED` | 30min 后温和复提一次 | 记录"打开但未完成"摩擦点 |
| 延后 | 到点重投 | 累计次数，3 次升级优先级，5 次触发 Agent 重评估 | 学习最佳提醒时段 |
| 忽略 | 当日终止 | 7日3次降频，14日全忽略暂停规则 | 负向样本：该类提醒贬值 |
| 无反馈过期 | 按策略重投/归档 | 同忽略的学习通道 | 优化投递时机 |

### 2.4 提醒类型与动作路由

提醒的 `action` 字段决定点击"处理"后打开哪里：

| type | 示例场景 | 处理动作 (deep link) | 快捷完成动作（通知栏直接完成） |
|------|----------|----------------------|-------------------------------|
| `attendance.checkin` | 上班打卡提醒 | `/attendance` 打卡页 | 通知栏"打卡"按钮直接完成 |
| `attendance.checkout` | 下班打卡提醒 | `/attendance` 打卡页 | 同上 |
| `diet.log` | 午餐/晚餐拍照提醒 | `/diet/capture` 相机页 | —（必须拍照，无快捷完成） |
| `health.weight` | 晨起称重提醒 | `/health/weight` 录入页 | 通知栏输入框直填体重 |
| `mission.due` | 任务到期/逾期 | `/mission/{id}` 任务详情 | "标记完成" |
| `mission.followup` | 长期事务例行跟进 | `/mission/{id}` + 进度速记 | "进展正常"/"无进展" |
| `agent.message` | Agent 生成的自由提醒/建议 | `/inbox/{id}` 详情页 | "知道了"(=resolve) |
| `quick.note` | 日记/随手记习惯提醒 | `/capture/note` 速记页 | — |

### 2.5 提醒来源

| 来源 | 说明 | 示例 |
|------|------|------|
| `schedule` | 用户在 App/Server 配置的固定规则（时间、周期） | 每天 08:55 上班打卡提醒 |
| `agent` | Autonomous Agent 扫描数据后生成 | 零食消费连续超标、体重一周未记录 |
| `business` | 业务模块状态驱动 | 任务 DDL 前 24h、库存不足 |
| `geofence` | App 端地理围栏触发后上报服务端登记 | 进入公司范围触发上班打卡提醒 |

---

## 3. 功能模块设计

App 内的功能模块**围绕提醒闭环组织**，每个模块都是"一类提醒 + 一个现场采集页 + 一个历史列表"。

### 3.1 消息提醒中心 (Inbox) — P0

App 的首页，所有提醒的收件箱视图：

- **待处理列表**：当前处于 `DELIVERED`/`OPENED`/`SNOOZED`（即将到点）的提醒卡片，支持在列表内直接进行 处理/延后/忽略 操作。
- **历史列表**：按日分组的所有提醒与最终状态，可筛选类型。
- **每日小结卡片**：今日待办提醒数量、已完成数量、被忽略数量（来自服务端聚合）。
- 与系统通知的关系：系统通知是"触达"，Inbox 是"兜底"——即使用户清掉了通知，Inbox 中依然可以处理。

### 3.2 饮食拍摄记录 (Diet Capture) — P0

对应健康模块的长期目标（追踪零食消费、理解饮食行为）。

- **入口**：餐点提醒的"处理"动作、App 首页 FAB、桌面小组件。
- **流程**：打开即相机（CameraX）→ 拍摄 → 可选一句话备注/餐次选择（早/午/晚/加餐零食）→ 提交即结束。后台静默上传。
- **服务端**：照片经文件存储接口落盘（需扩展二进制支持，见 §5.3），记录 `DietLog(id, photo_path, meal_type, note, taken_at)`；后续由 Agent 定时调用 LLM 视觉能力做内容分析（识别食物、估算热量、零食识别），产物回写健康分析。
- **离线**：照片与元数据先进本地 Room 队列，网络恢复后自动续传。

### 3.3 随手记 (Quick Capture) — P0

对应"日记切片"与灵感捕捉，落地到 SailZen 既有的笔记体系（Notes are notes）。

- **形态**：文字速记（主）、语音输入转文字、照片+一句话。
- **落地**：默认追加到当日日记笔记（`workspace/notes/diary/YYYY-MM-DD.md` 时间戳小节，与 `life` 模块的 Day 概念对齐）；支持打上 `#tag`，后续由 Agent 定期把速记内容归类整理进正式笔记（人物/历史/事务）。
- **入口**：首页 FAB、桌面小组件、通知栏常驻快捷磁贴（Quick Settings Tile）、每日晚间提醒（"今天有什么想留下的？"）。

### 3.4 上下班打卡 (Attendance) — P0

- **打卡方式**：提醒"处理"→ 打卡页一键打卡；通知栏快捷按钮直接打卡；打卡页显示当日上下班时间与本周工时。
- **智能提醒**：固定时间提醒（如 08:55 / 18:05）+ 地理围栏辅助（进入/离开公司范围时若未打卡则补提醒）。
- **服务端新增 `attendance` 模块**：`AttendanceRecord(id, type[checkin|checkout], ts, location, source)`；提供月度工时统计 API，供 site 报表与 Agent 工作/生活平衡分析复用。
- **反馈策略特化**：打卡提醒"延后"最多生效到当日 23:00，过期自动转为 `EXPIRED` 并在晚间小结中提示补卡。

### 3.5 长期事务跟进 (Long-term Mission) — P1

复用现有 project/mission 模型，App 侧只做"轻跟进"：

- **每日焦点**：服务端按规则（DDL 临近、长期未更新、用户置顶）选出 1~3 个焦点 mission，晨间推送。
- **进度速记**：跟进提醒的"处理"动作打开 mission 详情，提供快捷按钮：进展正常 / 无进展 / 写一句进展（追加到 mission 备注并刷新 mtime）。
- **逾期提醒**：复用 `get_overdue_missions_impl` 能力，每日晚间聚合推送一条（不逐个轰炸）。
- **连续"无进展"升级**：同一 mission 连续 N 次反馈"无进展"→ 触发 Agent 介入（建议拆解、建议暂停、或生成一条深度复盘提醒到周末）。

### 3.6 桌面小组件与快捷入口 — P1

| 形式 | 功能 |
|------|------|
| 桌面小组件 (App Widget) | 今日待处理提醒数 + 一键速记/拍照/打卡按钮 |
| 常驻通知 (Foreground Service) | 显示今日剩余提醒数，展开含快捷操作 |
| Quick Settings Tile | 下拉栏一键打开速记 |
| 快捷方式 (App Shortcuts) | 长按图标：速记 / 拍饮食 / 打卡 |

---

## 4. App 端技术设计

### 4.1 技术选型

| 维度 | 选型 | 理由 |
|------|------|------|
| 语言 / UI | Kotlin + Jetpack Compose + Material 3 | 原生体验、声明式 UI |
| 架构 | MVVM + Repository，单 Activity | 个人项目控制复杂度 |
| 网络 | OkHttp + Retrofit + Kotlin Serialization；WebSocket (OkHttp) 长连接 | 与 `/api/v1` REST 对齐 |
| 本地存储 | Room（提醒缓存/离线队列）+ DataStore（设置/凭证） | 官方方案 |
| 后台任务 | WorkManager（周期同步/补偿轮询）+ AlarmManager（本地精确提醒）+ Foreground Service（长连接保活） | 见 §4.3 |
| 相机 | CameraX | 简单可靠 |
| 定位 | FusedLocationProvider + Geofencing API | 打卡围栏 |
| 通知 | NotificationCompat + Notification Channels（按优先级分渠道） | 动作按钮/回复输入原生支持 |
| 最低版本 | minSdk 26 (Android 8.0) | 覆盖渠道通知/后台限制后的现代行为 |

### 4.2 客户端模块划分

```
app/
├── core/
│   ├── network/        # API client, WebSocket manager, auth interceptor
│   ├── reminder/       # 提醒本地缓存、反馈上报、通知构建器、动作路由
│   ├── sync/           # WorkManager 同步任务、离线队列
│   └── bg/             # ForegroundService, BootReceiver, 保活逻辑
├── feature/
│   ├── inbox/          # 提醒中心
│   ├── diet/           # 饮食拍摄
│   ├── capture/        # 随手记
│   ├── attendance/     # 打卡
│   ├── mission/        # 长期事务轻跟进
│   └── settings/       # 服务器地址、凭证、提醒规则、安静时段
└── widget/             # 桌面小组件、Quick Tile、Shortcuts
```

### 4.3 后台监控与推送通道

私有部署、无 FCM 前提下的三级通道设计：

```
通道1 (主): Foreground Service 维持 WebSocket 长连接
           ws://server/api/v1/reminder/ws
           ─ 实时收到 reminder.delivered 事件 → 立即构建系统通知
           ─ 常驻通知满足 Android 前台服务要求，同时显示今日待办数

通道2 (兜底): WorkManager 周期任务 (15min 最小间隔)
           ─ 拉取 GET /api/v1/reminder/pending 补偿漏收
           ─ 同时执行离线队列上传

通道3 (离线保障): AlarmManager 本地闹钟
           ─ 服务端投递提醒时附带 trigger_time，App 落库后设置本地闹钟
           ─ 即使断网/进程被杀，本地提醒依然准时弹出
           ─ 反馈因断网暂存本地，联网后批量上报
```

- **投递确认**：App 收到推送后回 ACK；服务端未收到 ACK 的提醒由通道 2 的轮询兜回，保证不丢。
- **断连重试**：WebSocket 指数退避重连（1s→5s→30s→5min 封顶）。
- **保活与合规**：
  - 首次启动引导用户授予：通知权限、电池优化白名单、自启动权限（按厂商跳转对应设置页）。
  - 国产 ROM（MIUI/HarmonyOS/ColorOS）在设置页提供图文引导。
  - 前台服务通知明确展示用途，符合应用市场审核规范。
- **安静时段**：默认 23:00–08:00 仅 `urgent` 优先级强提醒，其余静默入库（与 Agent 的 notification_engine 策略对齐）。

### 4.4 离线策略

| 数据类型 | 策略 |
|----------|------|
| 提醒反馈 | 本地队列暂存，联网批量上报；服务端按 `client_event_ts` 还原时序 |
| 照片/随手记 | Room 队列 + 文件暂存区，WorkManager 联网续传，失败指数退避 |
| 提醒本体 | 全量缓存最近 7 天，断网可查看历史、可收到本地闹钟提醒 |
| 业务数据（mission 等） | 只读缓存 + 写入排队；冲突以服务端为准（last-write-wins 于服务端字段） |

### 4.5 App 端本地存储 (Room)

```
reminder_cache      # 提醒缓存: id, type, title, body, priority, trigger_time,
                    #   state, payload_json, snooze_count, updated_at
pending_feedback    # 待上报反馈: reminder_id, action, option, client_event_ts
upload_queue        # 待上传: kind[photo|note], local_uri, meta_json, retry_count
attendance_cache    # 最近打卡记录缓存
```

设置与凭证存 DataStore（服务器地址、API Token、安静时段、提醒规则本地副本）。

---

## 5. 服务端配套设计 (sail_server 新增)

App 的落地需要 sail_server 增加两个模块与一个升级点。**沿用现有 Router-Controller-Model 模式与 `/api/v1/<domain>` 约定。**

### 5.1 新增数据模型

```python
# model/reminder.py
class Reminder(Base):
    id: int
    type: str                # attendance.checkin / diet.log / mission.due / ...
    title: str
    body: str
    priority: str            # low | normal | high | urgent
    source: str              # schedule | agent | business | geofence
    state: str               # 见 §2.2 状态机
    trigger_time: datetime
    expire_after_minutes: int = 240
    snooze_count: int = 0
    next_trigger_time: datetime | None
    payload: JSON            # {"mission_id": 3} / {"meal_type": "lunch"} ...
    rule_id: int | None      # 关联 ReminderRule（schedule 来源）
    created_at / updated_at

class ReminderEvent(Base):   # 不可变事件日志
    id: int
    reminder_id: int         # FK
    event: str               # created|delivered|ack|snoozed|opened|resolved|
                             # dismissed|expired|escalated|canceled
    detail: JSON             # {"snooze_option": "1h"} / {"client_ts": ...}
    client_event_ts: datetime | None   # 客户端实际发生时间(离线补偿)
    created_at: datetime     # 服务端收到时间

class ReminderRule(Base):    # 周期提醒规则 + 行为策略
    id: int
    type: str
    cron: str | None         # schedule 来源的周期表达式
    enabled: bool
    priority: str
    retry_policy: JSON       # {"max_retry": 2, "snooze_escalate_at": 3, ...}
    quiet_hours: JSON | None # 类型级安静时段覆盖
    frequency_level: int = 0 # 习惯学习降频档位

class Device(Base):
    id: int
    device_name: str
    platform: str            # android
    app_version: str
    push_token: str | None   # 预留(FCM 等)
    last_seen_at: datetime

# model/attendance.py
class AttendanceRecord(Base):
    id: int
    type: str                # checkin | checkout
    ts: datetime
    location: JSON | None    # {"lat": ..., "lng": ..., "label": "公司"}
    source: str              # app_notification | app_page | web | manual
    note: str | None

# model/health/diet.py (或 life 模块下)
class DietLog(Base):
    id: int
    photo_path: str          # 文件存储相对路径
    meal_type: str           # breakfast | lunch | dinner | snack
    note: str | None
    taken_at: datetime
    analysis: JSON | None    # Agent 视觉分析产物(食物/热量/是否零食)
```

### 5.2 新增 API 概览

```
# --- 设备与通道 ---
POST   /api/v1/reminder/device/register        # 注册/心跳设备
WS     /api/v1/reminder/ws                     # App 长连接, 服务端推送 reminder.delivered
POST   /api/v1/reminder/ack                    # 投递确认

# --- 提醒本体 ---
GET    /api/v1/reminder/pending?since=         # 待处理/补偿拉取
GET    /api/v1/reminder/history?date=&type=    # 历史
POST   /api/v1/reminder/                       # 创建提醒(Agent/业务模块调用)
DELETE /api/v1/reminder/{id}                   # 撤销
POST   /api/v1/reminder/{id}/feedback          # 反馈: {action: dismiss|snooze|open|resolve,
                                               #         option?, client_event_ts?}

# --- 提醒规则 ---
GET/POST/PUT /api/v1/reminder/rules            # 规则 CRUD (周期、优先级、升级策略)

# --- 打卡 ---
POST   /api/v1/attendance/check                # {type: checkin|checkout, location?}
GET    /api/v1/attendance/today
GET    /api/v1/attendance/stats?month=

# --- 饮食 ---
POST   /api/v1/health/diet/log                 # multipart: photo + meta
GET    /api/v1/health/diet/logs?date=

# --- 随手记 ---
POST   /api/v1/life/quick-note                 # {text, tags[], photo_path?}
                                               # 服务端追加到当日日记 md + NoteItem 索引
```

**反馈处理路由 (`POST /reminder/{id}/feedback`) 是闭环的中枢**，服务端收到反馈后：

```
dismiss ──► state=IGNORED, 记录事件, 更新规则降频计数, 推送事件给 Agent
snooze  ──► state=SNOOZED, 计算 next_trigger_time, 检查升级阈值(3次升优先级/5次通知Agent)
open    ──► state=OPENED, 启动 30min 回落计时
resolve ──► state=RESOLVED, 按 type 路由回写业务模块(打卡落库/任务置完成/...), 事件给 Agent
```

### 5.3 现有模块的升级点

| 模块 | 升级内容 |
|------|----------|
| `file_storage` | 当前限制 10MB 文本文件，需扩展支持二进制图片（jpg/heic）、按日期分目录、生成缩略图 |
| `life` (Day/TimeSpan) | 随手记落点复用 Day 概念，增加 quick-note 控制器 |
| `project` | mission 反馈回调入口：`resolve` 类型为 `mission.due` 时联动置 DONE；暴露"每日焦点"查询 |
| `autonomous_agent` | 新增 pipeline `reminder_escalation_scan`（处理升级事件）、`habit_learning`（消费忽略/无反馈数据，产出规则调整建议）；既有 pipeline（如 `health_monitor`、`finance_anomaly_scan`）的 notify 出口由 Lark 单通道扩展为 **App reminder 为主通道、Lark 为备用通道** |

### 5.4 提醒调度服务

sail_server 内新增轻量调度器（APScheduler，与 Agent 的调度器相互独立、仅操作 reminder 表）：

- 每分钟扫描 `PENDING` 且 `trigger_time <= now` 的提醒 → 通过 WebSocket 投递（设备不在线则标记待轮询拉取）。
- 每分钟扫描 `SNOOZED` 到点的提醒 → 重新入队。
- 扫描 `OPENED` 超 30 分钟 → 回落 `DELIVERED` + 温和复提。
- 扫描 `DELIVERED` 超过 `expire_after_minutes` → `EXPIRED` + 按 `retry_policy` 处理。
- 每日 23:30 聚合当日反馈生成小结数据（供 Inbox 与周报）。

---

## 6. UI/UX 设计要点

### 6.1 页面结构

```
底部导航: [提醒] [随手记] [打卡] [事务] [我的]

提醒(Inbox)     ── 待处理卡片流(可直接 处理/延后/忽略) + 今日小结 + 历史Tab
随手记(Capture) ── 打开即输入框, 顶部今日已记条目流, 支持照片/语音
打卡(Attendance)── 大按钮上班/下班打卡, 当日时间轴, 本周工时条
事务(Mission)   ── 今日焦点 + 逾期列表(轻量), 点入详情可速记进展
我的(Settings)  ── 服务器配置, 提醒规则管理, 安静时段, 权限引导, 数据同步状态
```

拍照页不占底部导航，从提醒"处理"动作 / FAB / 小组件直达（打开即取景框）。

### 6.2 系统通知样式规范

```
┌─────────────────────────────────────┐
│ 🍚 该记录午餐了            12:05     │
│ 拍照记录一下今天的午餐               │
│ ┌──────┐ ┌──────┐ ┌──────┐         │
│ │ 处理 │ │ 延后 │ │ 忽略 │         │
│ └──────┘ └──────┘ └──────┘         │
└─────────────────────────────────────┘
```

- 通知渠道按优先级划分：`urgent`（响铃震动可穿透勿扰）、`reminder`（默认）、`silent`（静默入库）。
- "延后"点击后展开二级动作组（15分钟/1小时/今晚/明天），无需打开 App。
- 支持快捷完成的类型（打卡、标记任务完成）在通知栏直接提供完成按钮，点击后走 `resolve` 路径并回执一个"已完成 ✓"的瞬时通知。

---

## 7. 安全与部署

| 项 | 方案 |
|----|------|
| 认证 | API Token（设置页手动配置/扫码从 site 复制），请求头 `Authorization: Bearer <token>`；Token 存 DataStore，不落日志 |
| 传输 | 家庭/办公网络走局域网直连；外网访问经 VPN 或 HTTPS 反向代理，禁止裸 HTTP 公网暴露 |
| WebSocket | 复用同一 Token 鉴权，连接后 10s 内未认证自动断开 |
| 照片隐私 | 照片仅存私有服务器磁盘，不上传任何第三方；LLM 视觉分析在服务端按需调用，用户可在设置中关闭 |
| 权限最小化 | 相机（仅拍照时）、定位（仅打卡围栏）、通知、后台运行——逐项说明用途 |

---

## 8. 里程碑规划

| 里程碑 | 范围 | 验收标准 |
|--------|------|----------|
| **M1 提醒闭环最小可用** | 服务端 reminder 模块（模型/状态机/反馈路由/调度器）+ App 长连接 + 系统通知三动作 + Inbox | 创建一条测试提醒 → 手机收到通知 → 三种反馈均正确驱动状态机与事件日志；断网本地闹钟兜底生效 |
| **M2 随手采集** | 随手记（文字/照片）+ 饮食拍摄 + file_storage 二进制扩展 + 离线队列 | 飞行模式下拍照+速记，联网后自动全部到达服务端且时序正确 |
| **M3 打卡** | attendance 模块 + 打卡页 + 定时提醒 + 通知栏快捷打卡 | 提醒→快捷打卡→site/服务端可见当日记录与工时统计 |
| **M4 事务跟进 + 习惯学习** | 每日焦点推送 + mission 速记 + 忽略降频/延后升级策略 + 周报数据 | 连续忽略 3 次某类提醒后规则自动降频；连续延后 5 次产生 escalated 事件 |
| **M5 Agent 协同 + 体验完善** | Agent pipeline 出口切到 App 主通道 + 地理围栏打卡提醒 + 桌面小组件 + 安静时段 | Agent 生成的提醒出现在手机通知栏且可反馈；进入公司围栏自动弹出打卡提醒 |

M1 是全部价值的地基，优先保证；M2 之后各里程碑相对独立可按需调整顺序。

---

## 9. 开放问题 (Review 已确认)

1. **推送通道是否预留 FCM？** 当前设计为纯长连接+本地闹钟。不考虑海外ROM设备
2. **随手记落点**：和天气系统一样，由postgresql管理后在vscode_plugin中可以通过预览查看，后续会支持导出到md落盘，这样让全流程异步
3. **饮食分析时机**：上传后即时调用视觉模型（成本高、反馈快）vs 夜间批量（成本低、次日可见），倾向夜间批量 + 手动触发即时分析。
4. **打卡定位精度**：不用定位，只需要当时提醒+后续如果缺失则补卡提醒即可
5. **iOS 是否考虑**：本设计仅 Android。若未来需要 iOS，提醒状态机与服务端 API 可直接复用，仅需重写客户端。
6. **与 Lark 通道的关系**：M5 后 App 为主通道，Lark通道限制太多，承担的功能主要是Agent开发交互，和Android app随身触达定位不一致

---

## 变更记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-08-02 | 初稿，待 Review |
| v0.2 | 2026-08-03 | M1（提醒闭环最小可用）已实现：服务端 reminder 模块 + Android 工程代码，验收见 [ACCEPTANCE_M1.md](./ACCEPTANCE_M1.md) |
