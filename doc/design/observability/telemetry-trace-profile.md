# SailZen AI Trace 与系统 Profile 埋点体系设计（v1.0）

> 日期: 2026-11-23 | 状态: 已落地实现 | 关联: [sailtick.md](../agent-system/sailtick.md)

## 1. 背景与目标

SailZen 3.0 进入 SailTick 常驻 AI 教练试运行阶段后，需要一套统一的**线上可观测与 Profile 基建**解决两大痛点：

1. **AI 全链路黑盒问题（SailTick Trace）**：每次定时唤醒（`WAKE → SCAN → PLAN → LLM → THROTTLE → WORK → HANDOFF`）中，若出现 LLM 超时、JSON 截断降级、票据被防轰炸限流、动作同步失败或熔断降级，需要能在 Web 端一眼看到每阶段耗时瀑布流、真实 Prompt 输入、AI 原始输出/思维链与动作执行结果，方便试运行期快速调优。
2. **全局性能与长期使用 Profile 缺失**：除 SailTick 外，财务、健康、节奏、文本、物资、提醒/WS、文件/博客均缺乏长期接口延迟（P50/P95/P99）、慢请求/5xx 留痕、业务数据增长与健康度（如未打标交易占比、票据回复率、WS 在线设备数）、以及前端页面访问热力与 JS 异常监控。

## 2. 总体架构（双层落库 + 零同步开销聚合）

```text
┌─────────────────────────────┐         POST /api/v1/telemetry/ai-traces
│ SailTick Daemon (:9070)     │ ───────────────────────────────────────┐
│  · TickTraceRecorder        │ (非致命异步上报，脱敏+截断 64KB)          ▼
│  · st_ai_traces / spans     │                             ┌──────────────────────────┐
│    (本地隔离 SQLite 权威副本) │                             │ sail_server (/api/v1)    │
└──────────────▲──────────────┘                             │  · logging_middleware    │
               │ 本地同机代理（3s超时，离线优雅降级）            │    └─ TelemetryCollector │
               └────────── GET /telemetry/sailtick/live ◄── │       (内存小时桶+30s刷盘) │
                                                            │  · sys_ai_traces / spans │
┌─────────────────────────────┐                             │  · sys_api_metric_buckets│
│ Web 管理台 /trace-debug      │ ◄── REST /api/v1/telemetry  │  · sys_telemetry_events  │
│  · SailTick AI Trace 瀑布流  │ ──► POST /telemetry/events  └──────────────────────────┘
│  · API 性能与慢请求 Profile  │     (页面访问/停留/JS异常)
│  · 全业务板块 & 运行时 Profile│
└─────────────────────────────┘
```

### 关键设计决策

- **双层存储、离线容错**：SailTick 每次 Tick 先落盘隔离库 `st_ai_traces` / `st_ai_trace_spans`，再非致命上报至 `sail_server` 主库 `sys_ai_traces` / `sys_ai_trace_spans`。既保证 `:9070` 无需暴露公网，也确保即便 Daemon 崩溃或停机，失败链路仍可在公网 `/trace-debug` 中完整回溯。
- **统一 AI Trace 协议**：`sys_ai_traces.service` 支持 `sailtick | sail_server | dag | cli`，未来财务自动打标、智能文本导入、健康顾问等 AI 流程均可直接复用同一套上报接口与瀑布流 UI。
- **脱敏与有界截断**：`sailtick/tracer.py` 在落库前自动脱敏 `Bearer ***`、`sk-***` 及数据库连接串密码，并将超大 Prompt/响应截断至 64KB。
- **低开销 API Profile**：`TelemetryCollector` 在 ASGI 中间件中仅做内存 `O(1)` 计数与有界分位采样（单桶上限 512 样本），每 30 秒后台批量 upsert 到 `sys_api_metric_buckets`，慢请求（默认 `>= 300ms`）与 5xx 写入 `sys_telemetry_events`；查询时自动合并 DB 历史与内存未刷盘增量，并按日自动清理 90 天前的旧埋点。

## 3. 数据模型

### 3.1 主库表（`packages/py/sailzen-orm/sailzen_orm/telemetry.py`）

| 表名 | 用途 | 保留策略 |
|---|---|---|
| `sys_ai_traces` | AI 全链路执行摘要（状态、规划源、耗时、Token/USD、票据/动作统计） | 长期保留 |
| `sys_ai_trace_spans` | 各阶段与子调用 Span（`wake/scan/plan/llm_call/throttle/work/ticket_emit/work_action/handoff/canary`） | 随 Trace 保留 |
| `sys_api_metric_buckets` | 小时级 API 聚合桶（按 `bucket_hour × module × method × endpoint × client_source` 唯一） | 90 天自动滚动清理 |
| `sys_telemetry_events` | 离散事件（`api_slow` / `api_error` / `page_view` / `web_vital` / `client_error`） | 90 天自动滚动清理 |

### 3.2 SailTick 隔离库表（`sailtick/db.py`）

- `st_ai_traces` / `st_ai_trace_spans`：与主库字段对齐的本地权威副本，不参与 `db_sync.py`。

## 4. REST API 契约（`/api/v1/telemetry`）

| 方法与路径 | 说明 |
|---|---|
| `POST /ai-traces` | 幂等上报一条 AI Trace 及其 Spans |
| `GET /ai-traces` | 分页筛选查询 Trace（`service/slot/status/plan_source/days/limit`） |
| `GET /ai-traces/stats` | 窗口期 KPI、按 Slot 聚合与每日趋势 |
| `GET /ai-traces/{trace_id}` | 单条 Trace 完整详情与有序 Spans |
| `POST /events` | 前端批量埋点上报（页面访问、停留时长、JS 异常） |
| `GET /profile/api` | API 全局/分模块/Top 慢接口/最热接口/客户端分布/近期慢与错误明细 |
| `GET /profile/modules` | SailZen 全业务板块数据规模、活跃度、健康度与前端访问热力 |
| `GET /profile/runtime` | 服务端运行时长、内存 RSS、DB 后端、在线 WS 设备、数据目录体积 |
| `GET /sailtick/live` | 同机代理查询 SailTick Daemon 实时健康/灰度/排程 |
| `POST /sailtick/trigger` | 从 Debug 页触发一次带独立幂等后缀的试跑 Tick |

## 5. 前端导航与图标防遗漏重构

原 `site/src/config/basic.ts` 使用纯字符串 `icon: string`，且 `pagebar.tsx` 与 `mobile_nav.tsx` 各自维护手写 `iconMap`，导致新增页面（如 `/tick` 教练页）极易遗漏图标。

重构后：
- `PageRoute.icon` 直接约束为 `LucideIcon` 组件类型，编译期强制绑定图标；
- 删除 `pagebar.tsx` 与 `mobile_nav.tsx` 中的重复 `iconMap`；
- 通过 `section: 'main' | 'system'` 自动区分主业务菜单与底部 `Observability` 专区（`/trace-debug`）。
