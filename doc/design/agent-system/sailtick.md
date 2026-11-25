# SailTick — 私人减肥监督教练（设计文档 v1.0）

> 版本: v1.0 | 状态: 已评审基线 | 关联: [sailtick-migration-notes.md](./sailtick-migration-notes.md)
> 前置阅读: 计划稿《SailTick 私人减肥监督教练 — 总体实施计划》

## 1. 愿景与 KPI

SailTick 是部署在与 SailZen 同机的云服务器上、24 小时在线、**每 6 小时唤醒一次（Tick 驱动）、每次 3 小时工作时间**的私人 AI 减肥监督教练。

核心差异：AI 主导（人只给模糊 KPI 与必要配合）、异步 Tick 交互（不阻塞，决策项写成票据）、
每 Tick 从零组装上下文（无长 session 堆积）、长期逐步摸清用户作息/食堂/健身房/工作压力并动态调整计划。

### 1.1 KPI 定义

| 类别 | 指标 | 说明 |
|---|---|---|
| 结果 KPI | 体重减至 70kg | 用户给定唯一硬目标；时间线由 AI 依据数据渐进细化，bootstrap 时不假设 |
| 过程指标 | 体重记录频率 ≥ 每日 1 次 | 快速记体重是网页 /tick 的一键操作 |
| 过程指标 | 每周有效运动次数 | 来自 health 运动记录 + 计划完成度 |
| 过程指标 | 睡眠规律性 | 来自 health 睡眠记录 + rhythm 打卡 |
| 过程指标 | 票据响应率 | AI 提问 → 用户 24h 内回复的比例（衡量打扰度是否可接受） |
| 健康红线 | 不损害健康/工作 | 任一 Tick 检测到体重异常波动/睡眠崩塌/压力爆表 → 计划自动让路并开 info 票据 |

### 1.2 开放问题决议（计划 §8，已与用户确认）

| # | 问题 | 决议 |
|---|---|---|
| 1 | Tick 时刻表 00/06/12/18 + 3h 预算 | 确认。周末无差异化——Tick 是 AI 概念，周末只影响**对人类回复的期待时间**，不影响 AI 自身排程 |
| 2 | 安静时段 | 23:00–08:00 作为默认值；profile 学到用户作息后可动态调整 |
| 3 | LLM 预算 | deepseek flash 层级模型视为无限量；仍保留每 Tick/每日记账与软上限（防代码 bug 失控，非经济压力） |
| 4 | 移动端 | 网页（PWA）+ Android 原生入口为高优先；插件面板 P2 |
| 5 | 最小 profile | bootstrap 保持最小假设（目标 70kg 之外不预填身高/当前体重），多一轮问答；理由：SailTick 未来可能扩展管理财务/社交等综合状态，保持最小假设是通用姿态 |
| 6 | 服务器部署路径 | `sailtick.yaml` 配置 + 示例注释，由用户部署时填写（见 §10 与验收文档） |

## 2. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ 服务器 (同机)                                                  │
│                                                              │
│  ┌────────────┐   HTTP    ┌──────────────────────────┐       │
│  │ sail_server │ ◄────────► │ sailtick daemon (:9070) │       │
│  │  (Litestar) │  /api/v1  │  · TickEngine 状态机     │       │
│  │  · tickets  │  tick/*   │  · APScheduler 6h 唤醒    │       │
│  │  · health   │           │  · 上下文组装器           │       │
│  │  · rhythm   │           │  · handoff 读写           │       │
│  │  · reminder │  WS push  │  · 4 层记忆              │       │
│  │    WS ──────┼──────────► │  · LLM Gateway + 记账    │       │
│  └─────┬──────┘           └───┬───────┬───────┬────────┘       │
│        │                      │       │       │                │
│   SQLite/PG              SQLite  handoffs  runs/artifacts      │
│   (主库, tickets)     sailtick.db  (md)   data/sailtick/        │
│                                                              │
│  浏览器 /tick (PWA) ──────► sail_server (静态+REST)            │
│  Android App ─────────────► sail_server REST + WS             │
└──────────────────────────────────────────────────────────────┘
```

**进程模型（D2）**：常驻 daemon（24h 在线 + 管理 API + 收件箱轮询），
内部 TickEngine 状态机在 00/06/12/18（Asia/Shanghai）唤醒，3h 工作预算。
上下文隔离靠**构造**（每 Tick 从零组装：system prompt + handoff + 记忆摘要 + 数据扫描），
不靠重启。

**存储切分（D3）**：
- Agent 自身状态（记忆/handoff/tick 日志/计划版本）→ 隔离 SQLite `data/sailtick/db/sailtick.db`（**禁止 db_sync**，已加入排除清单）
- 用户交互票据 → SailZen 主库 `sail_tick_tickets` 表 + `/api/v1/tick/*`（网页/手机/插件都要经 sail_server 访问）

**代码归属（D1）**：顶层包 `sailtick/`（与 `sail_server/`、`sailzen/` 平级），
迁移修复 `sailzen/autonomous_agent` 的可复用部分；旧包 Phase 9 归档删除。

## 3. Tick 生命周期状态机

```
                 ┌─────────┐   00/06/12/18 唤醒    ┌──────────┐
                 │  SLEEP  │ ────────────────────► │   WAKE   │
                 └─────────┘                        └────┬─────┘
                     ▲                                   │ 初始化 tick 行 / 幂等键
                     │                                   ▼
                 ┌───┴────┐  预算耗尽/完成   ┌──────────┐  健康检查+数据拉取+票据同步
                 │ HANDOFF│ ◄────────────── │   SCAN   │
                 └───┬────┘                 └────┬─────┘
                     │ 写交接文档/压缩记忆/        │ ≤15min
                     │ 记录成本                   ▼
                     │                    ┌──────────┐  LLM 生成本窗口任务清单
                     │                    │   PLAN   │
                     │                    └────┬─────┘
                     │                         │ ≤20min
                     │                         ▼
                     │   硬截止=唤醒+3h   ┌──────────┐
                     └────────────────── │  WORK    │
                                         └────┬─────┘
                                              │ 执行到预算耗尽或任务清空
                                              ▼
                                        ┌──────────┐
                                        │  HANDOFF │──► SLEEP
                                        └──────────┘
```

### 3.1 状态说明

| 状态 | 职责 | 预算 |
|---|---|---|
| WAKE | 建 tick 实例（幂等键=slot+日期）、加载 handoff、组装上下文 | 1min |
| SCAN | 依赖健康检查（sail_server/LLM）、数据扫描（datascan.py）、票据收件箱同步 | ≤15min |
| PLAN | LLM 决策本窗口任务清单（夜间/白天人格不同），产出计划 JSON | ≤20min |
| WORK | 按计划执行：直接工具调用或经 dag_client 跑 pipeline；硬截止=唤醒+3h | 剩余预算 |
| HANDOFF | 写交接文档、压缩记忆、记录成本、设下次 Tick 建议 | ≤10min |
| SLEEP | 仅保留 daemon 心跳（heartbeat_interval）、inbox 轮询、API | — |

### 3.2 slot 人格

| slot | 时间 | 人格 | EXECUTE 限定 |
|---|---|---|---|
| `morning_checkin` | 06:00 | 早间问候：问起床时间/上午状态/午饭打算 → 规划晚饭/锻炼建议 | 交互优先 |
| `midday_checkin` | 12:00 | 午间巡检：上午执行情况、午饭实际摄入、下午安排 | 交互优先 |
| `evening_review` | 18:00 | 晚间复盘：晚饭计划、今日运动/饮食/睡眠核对、明日预排 | 交互优先 |
| `nightly_maintenance` | 00:00 | 无声工作：开发/维护/数据整理/记忆压缩/票据清理（**不推送非 urgent**） | 无声任务 |

### 3.3 中断与补跑策略

- **预算中断**：WORK 到点未完成的计划项 → 记入 handoff「未完成事项」，下个 Tick 优先续跑。
- **错过 tick**（服务器维护/宕机）：daemon 启动时补跑，**最多补 1 个**（取最近错过的 slot），更早的丢弃并在 handoff 记录。
- **重叠防护**：tick 幂等键 `(slot, date)`；同键 tick 未完成时新唤醒直接跳过（记 skip）。
- **崩溃恢复**：tick 行状态持久化于 `st_ticks`，daemon 重启时将 `running` 态 tick 标记为 `interrupted`，其 handoff 由下个 Tick 基于 DB 状态重建。

## 4. 上下文组装协议

每 Tick 输入（从零组装，token 预算见右）：

| 组成 | 来源 | 预算 |
|---|---|---|
| system prompt | `prompts/coach/v1/system.md`（人设：温和/不苛责/打工人同理心/压力优先于热量/长期主义） | ~1k |
| 计划文档（当前版本） | `st_plans` active 版本 + rationale | ~2k |
| handoff 摘要 | 上一 Tick handoff 文档（压缩版） | ~2k |
| 记忆摘要 | 四层记忆检索（§5） | ~2k |
| 数据包 | datascan.py 输出（§8 数据源，截断） | ~4k |
| 待回票据 | 主库 pending/snoozed 票据摘要 | ~1k |
| 问卷题库切片 | 当次计划提问所需的题目（含"为什么问这个"） | ~1k |
| **合计** | | **~13k 输入预算** |

最小化原则（D9）：prompt 组装只带当次推理所需字段；原始明细永不出 agent DB。

## 5. 记忆模型（四层 + handoff）

| 层 | 存什么 | 存储 | TTL |
|---|---|---|---|
| profile | 用户画像：作息/食堂/健身房/应酬频率/压力源/禁忌；`confidence` + `source`(asked/observed/assumed) | `st_profile` | 永久，可修订 |
| episodic | Tick 事件流：每次 Tick 做了什么/发现什么/问了什么 | `st_episodes` | 90 天，摘要后归档 |
| semantic | 学到的规律："周三应酬高发""周末早餐常省略" | `st_memories(type=semantic)` | 永久，可失效 |
| procedural | 怎么做事：有效提醒话术、问卷转化经验、排期偏好 | `st_memories(type=procedural)` | 永久 |

handoff 文档（`data/sailtick/handoffs/YYYY-MM-DD_<slot>.md` + `st_handoffs` 指针）格式 v1：

```markdown
# Handoff 2026-11-09 morning_checkin (tick <id>)
## 上 Tick 摘要        — 3-5 行
## 未完成事项          — 带原因与续跑建议
## 当前计划版本        — version + 一句话变化
## 待回复票据          — id/问题/期待回复时间/fallback 假设
## 用户状态摘要        — 最近体重趋势/睡眠/压力信号
## 下次 Tick 建议      — PLAN 阶段的提示词素材
```

压缩策略：HANDOFF 阶段由 LLM 将本 Tick episodic 摘要压入 semantic/procedural；
handoff 文档超过 ~200 行时按节压缩。

## 6. 票据协议

### 6.1 字段（主库 `sail_tick_tickets`）

| 字段 | 说明 |
|---|---|
| id | 自增主键 |
| tick_id | 创建它的 tick 实例（st_ticks.id，便于追溯） |
| type | `question`（提问）/ `task`（用户配合事项，如"明早称体重"）/ `approval`（合入 review 请求）/ `info`（告知） |
| title / body | 标题/正文（body 支持 Markdown，含"为什么问这个"） |
| status | `pending` → `replied` → `resolved`；`pending` → `expired`；`pending` → `snoozed` → `pending` |
| expected_reply_by | 期待回复时间（ISO）；超期 → expired，AI 采用 fallback 假设继续 |
| fallback_assumption | 超期后 AI 采用的假设（写入 handoff 与下轮推理） |
| priority | low/normal/high/urgent（urgent 安静时段也推送） |
| channel | web/mobile（P2）/plugin（P2） |
| reply / replied_at | 用户回复内容/时间 |
| resolved_at / resolution | 关闭时间与方式 |

### 6.2 状态机

```
pending ──用户回复──► replied ──AI 确认完成──► resolved
   │                       │
   ├─超 expected_reply_by─► expired        （AI 永不阻塞：fallback 假设推进，
   │                                        下 Tick 重评估）
   └─用户 snooze────► snoozed ──到期──► pending
```

### 6.3 节流与打扰控制

- 每 Tick 最多新开 **2 张**票据；同主题合并。
- 默认 `expected_reply_by` 宽松（question=48h、task=当日晚、approval=72h）。
- 23:00–08:00 安静时段：非 urgent 票据落库但不推送；urgent 走 WS push。
- 用户可对整张票据 snooze；连续 3 张同主题票据无回复 → 该主题进入 profile「不敏感区」。

## 7. 通道矩阵

| 通道 | MVP | P2 | P3 |
|---|---|---|---|
| 网页 /tick | ✅ 收件箱+今日计划+快速记体重 | 历史分析图表 | — |
| 手机 | ✅ PWA 网页 + reminder WS push | Android 原生 Tick 页 | — |
| 插件 | — | VSCode 侧边栏树 | — |
| IM（飞书/QQ） | — | — | 复用 bot.py 模式 |

推送联动：sail_server 建/更新 high/urgent 票据时调用 `utils/reminder_ws.py` push manager 广播 `tick.ticket` 报文（Android 端现有轮询/推送机制兜回）。

## 8. 减肥领域模型与数据信号源

| 信号 | 来源 API | 用途 |
|---|---|---|
| 体重/身体数据 | `GET /api/v1/health/...`（body_data） | 趋势、里程碑、波动告警 |
| 饮食 | health 饮食记录 + finance 餐饮消费 | 摄入结构与外卖/食堂识别 |
| 运动 | health 运动记录 | 每周有效运动次数 |
| 睡眠 | health 睡眠 + rhythm 打卡 | 规律性、恢复质量 |
| 心情 | health mood | 压力信号（优先于热量） |
| 消费 | finance 交易（餐饮 tag） | 应酬/外卖频率交叉验证 |
| 打卡/复盘 | rhythm 打卡 + 周复盘 | 计划执行度；周日晚 Tick 与 rhythm 周复盘对齐 |
| 笔记 | NoteItem 摘要 | 用户自述上下文 |

`datascan.py` 负责按 token 预算组装「本 Tick 数据包」：每源取最近 N 条 + 周聚合，
超预算时按信号优先级截断（体重 > 睡眠 > 饮食 > 运动 > mood > 消费 > 笔记）。

## 9. 安全与成本护栏

| 护栏 | 机制 |
|---|---|
| 自我开发隔离（D5） | 仅 `agent/sailtick-dev` 分支；guard.py 硬护栏（禁 checkout main 写、禁 push、禁动 `data/`、`.env*`；目录白名单） |
| 测试门槛 | 自我开发任务跑通 `pytest tests/sailtick -m "not current"` + ruff 才允许开 approval 票据 |
| 人工合入 | 完成后开 approval 票据，用户 review 后合入 main |
| 成本（D8） | 每 Tick token 软上限（默认 200k）+ 每日软上限（默认 1M）；超预算自动切便宜模型；`st_ticks.cost_tokens/cost_usd` 记账可查 |
| 隐私（D9） | 数据全留自有服务器；唯一外部暴露是 LLM API；prompt 最小化；key 仅环境变量 |
| LLM 降级 | LLM 不可用时：白天 slot 跳过 PLAN 用规则模板，夜间 slot 照常跑无声任务；连续 3 次失败开 info 票据 |

## 10. 配置（`sailtick.yaml`）

见仓库根 `sailtick.yaml` 模板（Phase 8 交付），关键项：

```yaml
sailtick:
  db_path: data/sailtick/db/sailtick.db
  data_dir: data/sailtick
  log_dir: logs/sailtick
  api_port: 9070          # 避开 dag 9050 与旧 agent 9060
  timezone: Asia/Shanghai
  tick_hours: [0, 6, 12, 18]
  work_budget_minutes: 180
  quiet_hours: {start: 23, end: 8}
  llm:
    default: deepseek     # flash 级视为无限量；记账仍保留
    providers: { deepseek: {model: deepseek-chat, base_url: ...} }
    per_tick_token_cap: 200000
    daily_token_cap: 1000000
  sail_server:
    api_base: http://127.0.0.1:1974/api/v1   # 同机部署按实际端口填
    auth_token: ${SAILZEN_API_TOKEN}
  self_dev:
    repo_dir: /path/to/SailZen   # 服务器仓库路径，部署时填写
    branch: agent/sailtick-dev
    whitelist_dirs: [sailtick, tests/sailtick, doc/design/agent-system]
```

环境变量覆盖（`SAILTICK_*`）见 `.env.template` SAILTICK 段。

## 11. 故障模式

| 故障 | 检测 | 处理 |
|---|---|---|
| LLM 不可用 | 调用异常/超时 | 降级规则模板；3 次失败开 info 票据；夜间无声任务照常 |
| sail_server 不可用 | SCAN 健康检查 | 本 Tick 跳过依赖数据的任务，只做本地维护；连续失败在恢复后补数据扫描 |
| sailtick.db 不可用 | 启动自检 | daemon 拒绝启动（fail-fast），systemd 重启兜回 |
| 重复 tick | 幂等键 (slot,date) | skip 并记 log |
| 错过 tick | 启动对比当前时刻 | 最多补 1 个；更早丢弃并记录 |
| 票据表写入失败 | inbox 客户端异常 | 通知通道降级为 log；下轮重试；不阻塞 Tick |

## 12. 路线图

- **M1（可演示）**：Phase 0-2 + 6 → daemon 本地跑通完整 Tick 循环 + handoff。
- **M2（可上线）**：+ Phase 3/4/8 → 服务器部署，网页 /tick 异步交互（Day-1 剧本）。
- **M3（完整体验）**：+ Phase 5/7 全量测试 + Android 原生页/插件面板（P2）。
- **P2/P3 backlog**：自动计划调整 v2、周报生成、管理维度扩展（财务/社交）、跨设备提醒同步。

## 13. 夜间深度自维护 & 白天快反双系统（v2.0 架构演进）

为解决「夜间定时 Tick 用户无消息导致空转」与「白天突发变动（早下班/同学聚餐/顺手设提醒）需要秒级响应」的矛盾，SailTick 演进为**慢脑专家 + 快脑助手**双系统：

### 13.1 慢脑夜间深度自维护（`nightly.py` / `analytics.py` / `knowledge.py`）

`nightly_maintenance`（00:00）静默执行四步自我迭代（也可通过 `POST /nightly/run` 或 `uv run python -m sailtick nightly-analyze` 手动触发）：

1. **长周期深度数据扫描（`DataScanner.collect_deep(days=90)`）**：分页拉取 `/finance/transaction/paginated/` 与 90 天体重/饮食/睡眠/运动/心情，细化餐饮交易分类（`snack_drink` / `takeout` / `social_dining` / `late_night`）。
2. **数学建模与精准预测（`WeightModelingEngine` → `st_model_snapshots`）**：
   - EWMA（alpha=0.25）过滤水分/高盐短期波动，分离真实代谢体重与日波动残差；
   - 时间衰减加权最小二乘回归（WLS）与代谢适应指数趋近模型择优，产出 7/14/30 天预测区间、70kg 预计达标日期（乐观/中位/保守）、14 天柔和 `daily_targets` 与信心指数；
   - 自动检测平台期、周末反弹、熬夜/聚餐/零食次日体重影响，并产出高价值「精准发问建议」喂给白天 Tick。
3. **自主食物热量库与专业健康师知识库（`st_food_nutrition` / `st_knowledge_items`）**：
   - 内置中式日常/食堂/外卖/零食基准库；夜间自动提取饮食/消费/白天快脑入队的未知食物，经可插拔公网检索 + LLM 营养师校验落库；
   - 按当前数据痛点自主整理覆盖**饮食营养 / 运动处方 / 心理调节 / 睡眠修复**的结构化健康师知识卡片。
4. **编译专家简报（`st_runtime_state["expert_brief"]` / `GET /expert/brief`）**：将数学模型预测、阶段策略、行为规律与早下班/聚餐应急预案打包成紧凑简报，供白天 Tick 与快反助手秒级复用。

### 13.2 白天快反助手 & QQ Bot 接入（`quick_agent.py` / `qq_bot.py`）

无需重做网页聊天 UI，白天交互采用轻量快反代理（优先路由 `llm.fast_model` 如 `deepseek-chat`，1-3s 响应），**只查专家简报与本地知识库，负责转达结论、灵活微调计划与顺手建提醒**：

- **接口与渠道**：
  - SailTick daemon (`:9070`): `POST /chat/quick`、`POST /onebot/webhook`（标准 OneBot v11，直接对接 NapCatQQ / Lagrange.OneBot / LLOneBot，支持 `X-Signature` 验签与 QQ 白名单）、`GET /expert/brief`、`GET /modeling/latest`、`GET /knowledge/foods`、`GET /knowledge/articles`；
  - `sail_server` 轻量透传：`GET /api/v1/tick/expert-brief`、`POST /api/v1/tick/quick-chat`；
  - CLI：`uv run python -m sailtick chat "下班前提醒我别忘了买洗衣液和七号电池"`、`uv run python -m sailtick brief`。
- **高频能力**：
  - **早下班/聚餐灵活调度**：即时给出分档运动+晚餐或聚餐控损方案，并自动发一条 `SailTickMessage` 给慢脑在晚间日报/下轮 Tick 同步微调动态计划；
  - **一句话定时提醒**：解析「下班前」「30分钟后」「明早8点半」等中文时间，落库 `sail_server` `POST /api/v1/reminder/`（Android 到点推送）并写入本地 `st_scheduled_nudges`（启用 QQ Bot 时到点同步私聊提醒，双保险）；
  - **快脑提需求 → 慢脑夜间查证**：白天问到未收录食物热量时，先给估算并将食物入队 `pending_food_research`，夜间自动联网核查补全。

## 14. 统一 Personal Agent 演进：接管 Rhythm 体系（v3.0）

SailTick 从单一「减肥监督教练」升级为**健康 + 项目与日程节奏（Rhythm）统一 Personal Agent 大脑**，共享 4 层记忆、防轰炸票据配额与每日睡前综合日报（身体睡眠/压力状态直接联动调节当日日程负载）：

- **严格 HTTP 调度客户端（`sailtick/rhythm_client.py`）**：只通过 `/api/v1/rhythm/*` 读写，绝不直连主库。
- **夜间节奏规律引擎（`sailtick/rhythm_analytics.py`）**：接入 `NightlySelfMaintenance`，从近 21 天 `/rhythm/timeline/range` 与活跃项目中自动学习「高效黄金时段」「易被打断时段」「过载减负信号」及「项目倒排风险（`on_track` / `attention` / `at_risk` / `stalled` / `overdue`）」，编译进统一 `expert_brief`，彻底取代人工维护精力曲线与权重公式。
- **慢脑自主排程权（`TickEngine` WORK 动作）**：新增 7 类 Rhythm 动作（`rhythm_sync_timeline`、`rhythm_upsert_affair`、`rhythm_transit_affair`、`rhythm_milestone_done`、`rhythm_occupancy`、`rhythm_block_status`、`rhythm_checkin`），日常直接调用 `POST /api/v1/rhythm/timeline/ai-sync` 落库可视化日程（自动保留已完成与刚性钉块），仅在重大项目取舍或明显延期风险时发轻量票据协商；`pre_sleep_report` 合并输出「健康 + 节奏」综合睡前日报。
- **快脑实时日程应变（`QuickCoachAgent`）**：新增 `/today`、`/projects` 快捷指令与实时 Rhythm 上下文注入，支持白天一句话钉入临时会议/请假、新建项目/任务、反馈完成状态或直接秒级重排今日剩余时间线（返回 `rhythm_updated: true` 触发前端即时刷新）。

## 15. 附录：目录结构

```
sailtick/
├── __init__.py  __main__.py  config.py  daemon.py
├── db.py  tick_engine.py  handoff.py  memory.py  llm.py
├── notify.py  inbox.py  datascan.py  state.py  scheduler.py
├── api/routes.py
├── executor/ (tick_scan, tick_plan, ticket_emit, weight_trend, condition, handoff_write)
├── dev/ (repo.py, tasks.py, guard.py)
├── pipelines/ (morning_checkin, midday_checkin, evening_review, nightly_maintenance).yaml
└── prompts/coach/v1/ (system.md, question_bank.yaml, plan_template.md, slot_*.md)
data/sailtick/{db,handoffs,runs,backups}/
logs/sailtick/
```
