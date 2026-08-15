# SailZen Android App MVP — M1 验收文档（提醒闭环最小可用）

> **版本**: v1.0
> **日期**: 2026-08-03
> **范围**: 设计文档 [README.md](./README.md) §8 里程碑 **M1（提醒闭环最小可用）**
> **交付形态**: 服务端代码 + 单元测试（本机已验证通过）+ Android 完整工程代码（未编译，需按本文 §4 在用户机器构建验收）+ 一键联调脚本

---

## 1. 概述

本次交付实现设计文档 §8 的 **M1：提醒闭环最小可用**：

- **服务端 reminder 模块**：4 张表（Reminder / ReminderEvent / ReminderRule / Device）+ 状态机 + 反馈中枢（`POST /reminder/{id}/feedback`：dismiss / snooze / open / resolve）+ 调度扫描循环（到点投递 / snooze 重投 / OPENED 回落 / 过期重投或归档）+ WebSocket 推送通道 + 投递确认 + 补偿拉取 + 当日小结 + 事件日志查询 + 设备注册 + 规则 CRUD。
- **Android App**：长连接（指数退避重连）+ 系统通知三动作（处理/延后/忽略 + 延后二级弹窗）+ Inbox（待处理/今日小结/历史）+ 设置页 + 前台 Service 保活 + WorkManager 补偿轮询 + AlarmManager 断网兜底闹钟 + 离线反馈队列。

### 1.1 与设计文档的有意偏差

| 设计文档 | M1 实现 | 理由 |
|---|---|---|
| §5.4 APScheduler 调度器 | asyncio 循环（仿 `model/weather.py::weather_update_loop`），30s 扫描粒度 | 复用现有启停模式（`on_startup`/`on_shutdown` 钩子），零新基础设施；`scan_once` 为纯同步函数可单测，后续可平滑替换触发器 |
| §2.2 状态机含 ARCHIVED | 保留 ARCHIVED 终态（EXPIRED 重投耗尽后归档），仅调度器内部使用，无独立 API | 与文档一致 |
| §2.4 通知栏快捷完成（打卡类） | M1 通知仅 处理/延后/忽略 三动作；"完成"在 Inbox 卡片内提供 | 快捷完成属 M3 类型特化 |
| §7 Token 扫码配置 | 设置页手动粘贴 Token | 扫码依赖 site 改造，超出 M1 |
| §2.2 SNOOZED 到点"回到 PENDING" | SNOOZED 到点直接转 DELIVERED 并记 `delivered{redelivery:true}` 事件 | 语义等价（PENDING 仅为入队暂态），减少一次状态往返，事件链更清晰 |
| 实施计划 §3.5 `ReminderPushManager` 用 `asyncio.Lock` | 实现采用 `threading.Lock`（临界区仅 dict 读写） | 单例跨事件循环场景（如 pytest 多次 `asyncio.run`）下 `asyncio.Lock` 存在 loop 绑定问题，功能等价且更稳健 |
| 实施计划 §3.3 转移表未覆盖 EXPIRED 态反馈 | EXPIRED 按 DELIVERED 同等处理（可 dismiss/snooze/open/resolve） | EXPIRED 是调度器中间态，用户迟到反馈不应 409，避免竞态 |

### 1.2 实现期本机验证结果

- `uv run pytest tests/unit/test_reminder.py -v`：**17/17 通过**；全量 `tests/unit`：**235 passed, 7 skipped**（无回归）。
- `uv run scripts/reminder_e2e_check.py`（对运行中的真实服务端，含 WS 监听）：**22/22 PASS**。
- OpenAPI `/api_docs` 可见全部 11 个 reminder REST 端点。

---

## 2. 交付物清单

### 2.1 服务端（sail_server）

| 类型 | 文件 | 职责 |
|---|---|---|
| 新增 | `sail_server/infrastructure/orm/reminder.py` | 4 张 ORM 表（reminders / reminder_events / reminder_rules / devices） |
| 新增 | `sail_server/application/dto/reminder.py` | Pydantic DTO（请求/响应/事件/规则/设备/小结），tz 时间归一化为 naive 本地时间 |
| 新增 | `sail_server/model/reminder.py` | 状态机 + 全部 `*_impl` 业务函数（反馈中枢/snooze 换算/升级策略/小结聚合） |
| 新增 | `sail_server/model/reminder_scheduler.py` | 调度扫描循环 `reminder_scan_loop` + 纯同步 `scan_once`（投递/重投/回落/过期） |
| 新增 | `sail_server/utils/reminder_ws.py` | `ReminderPushManager` 单例（device_id → WebSocket 字典 + 广播） |
| 新增 | `sail_server/controller/reminder.py` | Litestar Controller（REST + 可选 Bearer 鉴权 + 异常→404/409/400 映射） |
| 新增 | `sail_server/router/reminder.py` | Router（含 `@websocket("/ws")` 长连接 handler） |
| 新增 | `tests/unit/test_reminder.py` | 单元测试 17 例（自带 SQLite 内存 fixture，不依赖 PG） |
| 新增 | `scripts/reminder_e2e_check.py` | 一键联调验收脚本（httpx + websockets） |
| 修改 | `sail_server/db.py` | ORM 导入区追加 `reminder`（`create_all` 自动建表） |
| 修改 | `server.py` | 注册 reminder router；`on_startup` 启动调度 task、`on_shutdown` 取消（`REMINDER_ENABLED` 控制） |
| 修改 | `tests/conftest.py` | ORM 导入列表追加 `reminder` |

### 2.2 Android（android/，独立 Gradle 工程）

```
android/
├── settings.gradle.kts / build.gradle.kts / gradle.properties / .gitignore / README.md
└── app/
    ├── build.gradle.kts / proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/sailzen/app/
        │   ├── SailZenApp.kt                  # Application：通知渠道/周期同步/按需启 Service
        │   ├── MainActivity.kt                # 单 Activity + NavHost + 通知权限(33+) + reminder_id 导航
        │   ├── core/
        │   │   ├── data/SettingsManager.kt    # DataStore：serverUrl/token/deviceId/安静时段
        │   │   ├── data/db/                   # Room：AppDatabase + Entities + Daos（reminder_cache/pending_feedback）
        │   │   ├── network/                   # Dtos + ReminderApi + ApiClient + ReminderWebSocket（退避重连）
        │   │   ├── reminder/                  # NotificationHelper / ReminderActionReceiver / SnoozeDialogActivity
        │   │   │                              #   AlarmScheduler / AlarmReceiver / ReminderRepository
        │   │   ├── bg/ReminderService.kt      # 前台 Service（WS 保活 + 常驻通知"今日待办 N 条"）
        │   │   ├── bg/BootReceiver.kt         # BOOT_COMPLETED 重启 Service + 重排闹钟
        │   │   └── sync/SyncWorker.kt         # WorkManager 15min 补偿轮询 + 离线反馈冲刷
        │   ├── feature/inbox/                 # InboxViewModel + InboxScreen（小结卡片 + 待处理/历史 Tab）
        │   ├── feature/settings/              # SettingsViewModel + SettingsScreen
        │   └── ui/                            # Material3 主题 + NavGraph
        └── res/                               # strings/themes/colors + 矢量图标 + adaptive icon（免 PNG）
```

### 2.3 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `REMINDER_ENABLED` | `true` | 是否启动提醒调度循环 |
| `REMINDER_SCAN_INTERVAL_SECONDS` | `30` | 调度扫描间隔（验收时建议设 `5` 加速） |
| `SAILZEN_API_TOKEN` | 空 | 可选 Bearer Token；未设置则 REST/WS 全部放行（MVP 局域网自用） |

---

## 3. 服务端验收（本机/服务器直接可验）

### 3.1 启动服务端

```powershell
# .env.dev 中设置 DB_BACKEND=sqlite（或使用 PG 的 POSTGRE_URI）
# 验收加速：调小扫描间隔
$env:REMINDER_SCAN_INTERVAL_SECONDS="5"
uv sync
uv run server.py --dev
# 默认监听 0.0.0.0:1974，日志出现 [Startup] Reminder scan loop started 即生效
```

### 3.2 自动化单元测试

```powershell
uv run pytest tests/unit/test_reminder.py -v
```

预期：**17 passed**。覆盖：创建/四动作反馈/snooze 升级（3 次升优先级、5 次 agent_review）/终态幂等与 409/cancel/ack/scan_once 四类扫描/带 rule 重投/小结计数/设备 upsert/推送管理器。

### 3.3 一键联调脚本

```powershell
# 服务端运行中执行（另开终端）
uv run scripts/reminder_e2e_check.py --base-url http://127.0.0.1:1974
# 可选：--token <SAILZEN_API_TOKEN>  --skip-ws  --wait-redelivery（真实等待15分钟验证 snooze 重投）
```

脚本流程：health → 注册设备 → WS 监听 → A（创建 3s 后触发→等 DELIVERED→ack→open→resolve→核对事件序列 `created→delivered→ack→opened→resolved`）→ B（snooze 15m→核对 SNOOZED/next_trigger_time/snoozed 事件→dismiss 收尾）→ C（dismiss→IGNORED）→ summary/history 检查 → 打印 PASS/FAIL 汇总（全部通过 exit 0）。

### 3.4 手工 curl 对照表

> 以下假设 `BASE=http://127.0.0.1:1974/api/v1/reminder`；若配置了 `SAILZEN_API_TOKEN`，所有请求加 `-H "Authorization: Bearer <token>"`。

```bash
# 1) 注册设备 → 201，返回 {"id":1,"device_id":"dev-1",...}
curl -X POST $BASE/device/register -H "Content-Type: application/json" \
  -d '{"device_id":"dev-1","device_name":"curl","app_version":"0.1.0"}'

# 2) 创建提醒（10 秒后触发）→ 201，state=PENDING
curl -X POST $BASE/ -H "Content-Type: application/json" \
  -d "{\"type\":\"test.ping\",\"title\":\"喝水\",\"body\":\"起来活动一下\",\"trigger_time\":\"$(date -d '+10 seconds' '+%Y-%m-%dT%H:%M:%S')\"}"
# Windows PowerShell 时间串：
# (Get-Date).AddSeconds(10).ToString("yyyy-MM-ddTHH:mm:ss")

# 3) 等一个扫描周期后查 pending → 该提醒 state=DELIVERED
curl $BASE/pending

# 4) 投递确认 → {"ok":true}
curl -X POST $BASE/ack -H "Content-Type: application/json" \
  -d '{"reminder_id":1,"device_id":"dev-1"}'

# 5) 反馈中枢：open → state=OPENED；resolve → state=RESOLVED
curl -X POST $BASE/1/feedback -H "Content-Type: application/json" -d '{"action":"open"}'
curl -X POST $BASE/1/feedback -H "Content-Type: application/json" -d '{"action":"resolve"}'

# 6) snooze（先再建一条并等 DELIVERED）→ state=SNOOZED，snooze_count=1，next_trigger_time≈+15min
curl -X POST $BASE/2/feedback -H "Content-Type: application/json" -d '{"action":"snooze","option":"15m"}'

# 7) dismiss → state=IGNORED（终态）；终态后 resolve → HTTP 409
curl -X POST $BASE/2/feedback -H "Content-Type: application/json" -d '{"action":"dismiss"}'
curl -X POST $BASE/2/feedback -H "Content-Type: application/json" -d '{"action":"resolve"}'   # 409

# 8) 事件日志核对 → 按序出现 created/delivered/ack/opened/resolved 等
curl $BASE/1/events

# 9) 当日小结 → {"date":"YYYY-MM-DD","pending":N,"resolved":N,"ignored":N,"expired":N,"delivered_total":N}
curl $BASE/summary/today

# 10) 历史 → 当日全部提醒（含终态）
curl "$BASE/history?date=$(date '+%Y-%m-%d')"

# 11) 规则 CRUD → retry_policy 影响过期重投
curl -X POST $BASE/rules -H "Content-Type: application/json" \
  -d '{"type":"test.ping","retry_policy":{"max_retry":1,"retry_interval_minutes":30}}'
curl $BASE/rules
curl -X PUT $BASE/rules/1 -H "Content-Type: application/json" -d '{"enabled":false}'

# 12) 撤销 → state=CANCELED；终态撤销 → 409
curl -X DELETE $BASE/3
```

### 3.5 WebSocket 验证

```python
# uv run python 内执行（websockets 已在依赖中）
import asyncio, json, websockets

async def listen():
    url = "ws://127.0.0.1:1974/api/v1/reminder/ws?device_id=dev-1&token="
    async with websockets.connect(url) as ws:
        while True:
            msg = json.loads(await ws.recv())
            print(msg["type"], msg.get("data", {}).get("id"))
            # 预期：先收到 connected；创建到点提醒后一个扫描周期内收到 reminder.delivered

asyncio.run(listen())
```

若服务端设置了 `SAILZEN_API_TOKEN` 而 query token 不符，连接会以 **close code 4401** 拒绝。

### 3.6 事件日志核对 SQL

```sql
-- SQLite: data/sailzen.db；PG 同表名
select event, detail, client_event_ts, created_at
from reminder_events where reminder_id = ? order by id;
```

---

## 4. Android 构建验收（用户机器）

### 4.1 环境要求

- Android Studio Koala / Ladybug 或更新；JDK 17（Android Studio 自带 JBR 17 即可）
- Android SDK 34（Platform + Build Tools）
- 真机或模拟器 **API ≥ 26**，与服务器处于**同一局域网**

### 4.2 构建步骤

1. Android Studio → **Open** → 选择仓库内 `android/` 目录。
2. 首次 sync：工程未提交 gradle wrapper（本环境无 Android 工具链无法生成）。任选其一：
   - 让 IDE 自动配置（推荐，弹出"Gradle wrapper not found"时按提示 OK）；
   - 或本机有 Gradle 时执行 `gradle wrapper --gradle-version 8.9`；
   - 或直接复制任意现有 Android 工程的 `gradle/wrapper/` 与 `gradlew*` 过来。
3. 若 sync 报版本不兼容，按 IDE 提示微调 AGP / Kotlin 版本（本工程选型见 §4.4 附录，均为已知相互兼容组合）。
4. **Run 'app'**（debug 变体）安装到设备。
5. 首次启动授予**通知权限**；进入底部之外右上角齿轮 → **设置页**：填服务器地址（如 `http://192.168.x.x:1974`）与 Token（服务端未配置 `SAILZEN_API_TOKEN` 则留空）→ **保存并连接** → 顶部徽标变为"已连接"。
6. 建议按 §4.5 完成国产 ROM 保活引导（电池白名单/自启动）。

### 4.3 构建常见问题

| 问题 | 处理 |
|---|---|
| Gradle wrapper 缺失 | `gradle wrapper --gradle-version 8.9` 或让 IDE 自动生成 |
| `Kotlin plugin.compose` 找不到 | 确认 settings.gradle.kts 的 pluginManagement 含 `google()`；Kotlin 2.0.20 起 Compose 编译器为独立插件，版本必须与 Kotlin 一致 |
| KSP 版本不匹配 | KSP 版本须为 `<kotlin版本>-<ksp版本>`，本工程 `2.0.20-1.0.25`；升级 Kotlin 时同步改 KSP |
| JDK 版本错误 | Settings → Build → Gradle → Gradle JDK 选 17 |
| 局域网 HTTP 被拦 | 工程已在 manifest 声明 `usesCleartextTraffic="true"`（**仅限内网调试**，公网部署必须改走 HTTPS/VPN 并移除该标志） |
| 通知不弹 | 检查系统通知权限、是否处于安静时段（落 silent 渠道无声）、渠道是否被手动关闭 |
| 闹钟不准（API 31+） | 系统设置中允许"闹钟和提醒"精确闹钟权限；未授权时代码自动降级 inexact |

### 4.4 版本选型附录

| 项 | 版本 | 项 | 版本 |
|---|---|---|---|
| Gradle | 8.9 | Compose BOM | 2024.09.03 |
| AGP | 8.5.2 | activity-compose / lifecycle / navigation | 1.9.3 / 2.8.6 / 2.8.3 |
| Kotlin | 2.0.20 | Retrofit / OkHttp | 2.11.0 / 4.12.0 |
| KSP | 2.0.20-1.0.25 | kotlinx-serialization-json / coroutines | 1.7.3 / 1.8.1 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 26 | Room / WorkManager / DataStore | 2.6.1 / 2.9.1 / 1.1.1 |

### 4.5 国产 ROM 保活引导（验收 E8 前完成）

- 系统设置 → 应用管理 → SailZen → **电池**：设为"不优化/无限制"。
- **自启动/关联启动**：允许（MIUI：安全中心→应用管理→权限→自启动；HarmonyOS：设置→应用→应用启动管理→关闭自动管理并允许后台活动；ColorOS：电池→应用耗电管理→允许后台运行）。
- 最近任务列表锁定 App（可选）。

---

## 5. 端到端联调验收用例表

> 前置：服务端按 §3.1 启动（建议 `REMINDER_SCAN_INTERVAL_SECONDS=5`）；App 按 §4 装好并连接成功。创建提醒可用 §3.4 的 curl 第 2 条。

| # | 用例 | 步骤 | 预期 |
|---|---|---|---|
| E1 | 实时触达 | 创建 trigger_time=now+10s 的提醒 | 一个扫描周期内手机弹系统通知（含 处理/延后/忽略 三按钮）；服务端事件含 `delivered` + `ack` |
| E2 | 处理→完成 | 通知点"处理"→ 进入 App → 卡片点"完成" | 状态 OPENED→RESOLVED；事件序列 `…→opened→resolved`；卡片从待处理消失 |
| E3 | 延后 | 通知点"延后"→ 选 15 分钟 | 状态 SNOOZED（snooze_count=1，next_trigger_time≈+15min）；15 分钟后再次弹出（事件 `delivered{redelivery:true}`） |
| E4 | 延后升级 | 同一提醒连续延后 3 次 | priority normal→high；出现 `escalated{level:"priority_up"}` 事件；通知走强提醒渠道 |
| E5 | 忽略 | 通知点"忽略" | 状态 IGNORED（终态）；当日不再重投；再次 resolve 返回 409 |
| E6 | 过期 | 创建 expire_after_minutes=1 的提醒，不操作 | 超期后事件含 `expired`；无 rule 时状态最终 ARCHIVED；配 rule(max_retry≥1) 时回 PENDING 重投 |
| E7 | 断网闹钟兜底 | 创建未来 2 分钟提醒→ App 同步后断网 → 等到点 | 本地闹钟准时弹出；恢复网络后断网期间的反馈经 pending_feedback 补报，服务端事件 `client_event_ts` 为真实操作时间 |
| E8 | 杀进程恢复 | 强杀 App → 重启手机（或手动重开 App） | Service 自启、WS 自动重连（退避 1s→5s→30s→5min）；漏收提醒经 SyncWorker/启动同步兜回 |
| E9 | Inbox | 打开 App | 待处理列表/今日小结/历史与 `GET /pending`、`/summary/today`、`/history` 数据一致 |
| E10 | 安静时段 | 设置安静时段覆盖当前时间后创建 normal 提醒 | 走 silent 渠道无声入库；urgent 提醒仍强提醒 |

**核对方法**：每个用例结束后执行 `curl $BASE/{id}/events`（或 §3.6 SQL）核对事件序列与 `detail` 字段；事件类型全集见附录 A。

---

## 6. 已知限制清单

1. **Android 代码未经编译验证**（开发机无 Android 环境）：存在语法/API 级错误的可能，首次构建按 §4.3 微调即可；全部使用官方最常见范式与保守版本组合。
2. M1 不含 ReminderRule 的 **cron 自动生成提醒**（表与 CRUD 已备好，retry_policy 已被调度器消费）。
3. M1 不含**习惯学习**（7 日 3 次降频 / 14 日暂停）：忽略/延后事件已全部落库，M4 直接消费。
4. WS 推送为**全设备广播**（多设备同收），未按 device 维度定向；单机自用无影响。
5. 时间为 **naive 服务器本地时间**全链路口径；客户端 `client_event_ts` 带本地 ISO 时间，服务端归一化入库。
6. `usesCleartextTraffic="true"` 仅限内网调试；公网访问必须 VPN/HTTPS 反代。
7. snooze 到点重投的最小粒度受 `REMINDER_SCAN_INTERVAL_SECONDS`（默认 30s）限制。
8. resolve 的业务回写（打卡落库/任务置完成）不在 M1：M1 resolve 仅改状态 + 记事件。

---

## 7. 后续里程碑指引（对齐设计文档 §8）

| 里程碑 | 范围 | 依赖本次交付 |
|---|---|---|
| M2 随手采集 | 随手记/饮食拍摄/file_storage 二进制/上传队列 | Room 队列模式、WorkManager 续传范式 |
| M3 打卡 | attendance 模块 + 打卡页 + 通知栏快捷打卡 | 反馈中枢新增"快捷完成"动作路由 |
| M4 事务跟进 + 习惯学习 | 焦点推送/mission 速记/降频/周报 | 消费 reminder_events 语料 + ReminderRule.frequency_level |
| M5 Agent 协同 + 体验完善 | pipeline 出口切换/地理围栏/小组件/安静时段 | `escalated{agent_review}` 事件对接 Agent；quiet_hours 规则消费 |

---

## 附录 A：服务端事件类型速查

`created / delivered / redelivered(open_timeout|retry) / ack / snoozed / opened / resolved / dismissed / expired / escalated(priority_up|agent_review) / canceled`

## 附录 B：snooze option 契约

| option | 服务端换算 | 客户端入口 |
|---|---|---|
| `15m` | +15 分钟 | 通知"延后"弹窗 / Inbox 卡片"延后" |
| `1h` | +1 小时 | 同上 |
| `tonight` | 当日 20:00（已过则 +1 小时） | 同上 |
| `tomorrow` | 次日 09:00 | 同上 |

## 附录 C：通知渠道

| channel | importance | 用途 |
|---|---|---|
| `urgent` | HIGH + 响铃震动 | priority=urgent 或连续延后升级后的强提醒 |
| `reminder` | DEFAULT | 常规提醒 |
| `silent` | LOW | 安静时段非 urgent |
| `service` | MIN | 前台 Service 常驻通知（今日待办数） |
