# Rhythm — 生活/工作节奏综合优先级调节工具

> **版本**: v1.0 | **更新**: 2026-10-26 | **状态**: ✅ M1(服务端)/M2(CLI) 已实现
> **实现**: `sail_server/{infrastructure/orm,application/dto,model,controller,router}/rhythm.py` + `sail_server/model/rhythm_planner.py` + `sailzen/cli/rhythm_client.py` + `tests/server/test_rhythm_*.py` + `scripts/rhythm_smoke.py`

生活与工作同等重要。Rhythm 把生活必须项（戒律/习惯/基础节奏/刚性规划）与工作事项
（一次性任务/长期维护）及个人长期事业（venture）放进**同一优先级坐标系**，
通过统一事务模型 `Affair` + 日时间线 `TimeBlock` + 确定性排程器 `plan_day`
实现"生活地板不可侵占"的每日编排。AI 后台只通过 HTTP API / `sailzen rhythm` CLI
消费服务并产出"建议"，人确认后生效（Human-in-the-loop）。

---

## 1. 事务分类学（AffairKind，10 类）

两个正交维度：

- **domain（域）**: `life`（生活）/ `work`（工作）/ `career`（个人长期事业，业余推进）。
  用于三域平衡计量（§5.1）。
- **kind（事务种类）**: 决定生命周期形态、排程行为、元数据 schema、复盘指标。

| kind | 中文 | 典型 domain | 生命周期 | 排程行为 | 示例 |
|------|------|------------|----------|----------|------|
| `base_rhythm` | 基础节奏 | life/work | 长期 | 每日骨架：由 DayTemplate 实例化，plan_day 最早铺底；定义通勤、工作窗、午间休息、90/15 微节律 | 08:20–09:00 通勤；09:00–12:00 工作窗 |
| `precept` | 戒律 | life | 长期 | 按日/按周规则：轻量打卡块 + 到点核销提醒；severity=hard 参与铺底（生活地板） | 23:30 前入睡；三餐定时；每周一天无零食日 |
| `habit` | 习惯养成 | life | 长期 | 频率目标制：每周 N 次、单次最小时长、偏好槽位；按"周缺口压力"竞争弹性区；streak 激励 | 每周运动 3 次，每次 ≥30min，偏好 19:00–21:00 |
| `fixed_plan` | 刚性规划 | life/work | 一次性 | 刚性钉：固定起止 immovable，排程器绕开它；禁 defer；可挂子事务（行程段） | 10.1–10.5 家人旅行；周四 14:00 高铁赴沪 |
| `task_oneoff` | 一次性工作任务 | work | 一次性 | 按 ddl 紧迫度竞争弹性工作区（工作窗内优先，超窗标记 overtime） | 写季度总结；修复线上 bug |
| `task_maintenance` | 长期维护任务 | work | 长期 | SLA 周期制：interval_days + last_done_at，越接近/超期紧迫度越高 | 每周代码巡检；服务器月度维护 |
| `venture` | 长期事业 | career | 长期，可毕业 | 目标日倒排：target_date + 每周业余小时预算 + 里程碑链；仅排业余时间区 | 2027-04 独立游戏上线：每周 8h |
| `async_callback` | 异步回调 | work/career | 长期，多阶段 | 阶段化排程：KICKOFF/REVIEWING 排实时窗（work_hours_only 限工作窗）；DELEGATED 画 informational 提醒块；round+1 返工，max_rounds 上限 | 让 AI 起草方案→24h 后审阅→不满意返工 |
| `buffer` | 系统缓冲 | — | 系统生成 | 强制留白(min_buffer_ratio)，分散插入，只读禁编辑 | — |
| `generic` | 未分类 | 待定 | 一次性 | 捕获默认值；停留 INBOX 等待 AI 分拣 + 人确认改判 | "给车做保养"（一句话捕获） |

**分拣判定规则（precept vs habit 边界）**：

- 惩罚性/禁止性规则（不吃零食、23:30 前睡）→ `precept`
- 建设性/累计性目标（每周 3 次运动）→ `habit`
- 固定起止不可移动（旅行/车票）→ `fixed_plan`
- 业余长期推进且有目标日 → `venture`(career)
- 工作一次性交付 → `task_oneoff`(work)；周期性维护 → `task_maintenance`(work)
- 多阶段 + 含等待期 + 可返工（构思→委托→审阅→返工） → `async_callback`(work，对外业务回调置 work_hours_only=true)

`python -m sailzen rhythm kinds` 输出即为本表的权威机器可读版本（文档/CLI/prompt 三处同源）。

### kind_meta（JSON，写入时按 kind 分发校验）

| kind | kind_meta 字段 |
|------|----------------|
| base_rhythm | `{"template_id": int?}` |
| precept | `{"rule_text": str, "cycle": "daily"\|"weekly", "weekday_mask": [7], "check_time": "HH:MM", "severity": "hard"\|"soft", "block_minutes": int}` |
| habit | `{"freq_per_week": int, "min_session_minutes": int, "preferred_slots": ["HH:MM-HH:MM"], "streak": int, "best_streak": int, "last_done_date": date?}` |
| task_maintenance | `{"interval_days": int, "last_done_at": datetime?, "session_minutes": int}` |
| venture | `{"target_date": date, "weekly_budget_hours": float, "spare_time_only": bool, "total_est_hours": float}` |
| fixed_plan | `{"immovable": bool, "fixed_start": datetime, "fixed_end": datetime, "legs": [int]}` |
| async_callback | `{"phases": [{"name","est_minutes","energy_cost"}×3], "current_phase": str, "round": int, "max_rounds": int, "work_hours_only": bool, "delegate_to": str, "est_wait_hours": float, "last_handoff_at": dt?, "last_return_at": dt?, "next_review_at": dt?, "revision_history": [...]}` |
| task_oneoff / generic / buffer | `{}`（无额外约束） |

校验策略：M1 宽松（缺字段补默认值；类型错误 400），M2 起 CLI `hint`/`capture`/`split`
与服务端写入共用 `sail_server.application.dto.rhythm.validate_kind_meta` 同源校验。

## 2. 双生命周期状态机

**一次性流**（fixed_plan / task_oneoff / generic / venture 里程碑子项）:

```
INBOX ──confirm──► PLANNED ──plan-day──► SCHEDULED ──start──► DOING ──finish──► DONE(终)
  │                  │                      │  │
  ├─dismiss─► CANCELED(终)                  │  └─defer──► DEFERRED ──replan──► PLANNED
  └─AI triage 仅写 ai_hint，不改状态        └─rebalance 内移动保持 SCHEDULED
```

- `defer` 必须携带 `defer_to`（新窗口写入 window_start/window_end），否则 400。
- `fixed_plan` 特例：confirm 后按 kind_meta.fixed_start/end **直接钉入 SCHEDULED**
  （每日切一片 pinned 块），跳过排程竞争；`defer` 被拒绝（409），只能 cancel
  或人工改 fixed_start/end。
- `generic` 未分拣禁止 confirm/start/finish/defer（409），先 confirm-hint 或 PUT 改判。

**长期流**（base_rhythm / precept / habit / task_maintenance / venture 本体）:

```
INBOX ──confirm──► ACTIVE ⇄ PAUSED ──► ARCHIVED(终)
                     │（venture 限定）graduate ──► DONE(终/毕业)
```

- ACTIVE 期间由 plan_day 每日/每周实例化 occurrence（TimeBlock；precept/habit 另有
  DisciplineLog 核销）。
- PAUSED 暂停实例化（如旅行期间暂停运动 habit）；合规统计对 PAUSED 周期记 exempt。
- `buffer` 由系统生成，禁止人工创建/编辑/删除（400）。

**async_callback 阶段机**（长期流子集，独立状态机；CONFIRM→ACTIVE 即 KICKOFF 起步）:

```
INBOX ──confirm──► ACTIVE(=KICKOFF) ──handoff──► DELEGATED ──return_review──► REVIEWING
                                  │                                              │
                                  │                                              ├─approve──► COMPLETED(终)
                                  │                                              └─request_revision──► DELEGATED（round+1，≤max_rounds）
                                  └─pause──► PAUSED ──resume──► ACTIVE
```

- KICKOFF/REVIEWING 阶段排实时窗（work_hours_only=true 时仅进 work_window）。
- DELEGATED 阶段不占实时窗，由 plan_day 在 next_review_at 落点画 informational
  `async_wait` 提醒块（0 精力，允许 focus 跨越）。
- `REQUEST_REVISION` 触发 round+1 并回 DELEGATED；超过 max_rounds → 400 拒绝（建议 APPROVE 接受或 CANCEL）。
- work_hours_only 事务的 next_review_at 自动顺延到下个工作窗（09-12/14-18 工作日）。

## 3. 数据模型（7 张表，前缀 rhythm_）

| 表 | 说明 |
|----|------|
| `rhythm_affairs` | 统一事务（kind/kind_meta/state/importance/urgency_ddl/energy_cost/money_cost/budget_id/est_minutes/window/splittable/fallback_plan/recurrence_rule_id/mission_id/day_id/timespan_id/parent_id/ai_hint/score） |
| `rhythm_time_blocks` | 日时间线块（day_id/affair_id?/block_type×13/start/end/status/pinned/plan_version/ref） |
| `rhythm_day_templates` | 基础节奏骨架模板（name/weekday_mask/slots[label,start,end,block_type,micro_cycle]/enabled/priority） |
| `rhythm_discipline_logs` | 戒律/习惯打卡日志（affair_id/log_date/cycle_key/result/note/source） |
| `rhythm_energy_profiles` | 精力画像（单行：daily_energy_budget/curve_template/sleep_start/end/work_hours_cap/spare_time_windows/min_buffer_ratio/三域权重/score_weights） |
| `rhythm_policies` | 守护策略（rule_type×5/params/scope/enabled） |
| `rhythm_reviews` | 节奏复盘快照（scope/period_key/rhythm_score/domain_minutes/四项明细/encroachments/ai_summary） |

- block_type: `sleep/commute/work_window/micro_rest/meal/precept/habit/fixed/focus/light/career/rest/buffer/async_kickoff/async_review/async_wait`
- 打卡 result: precept → `kept/violated/exempt`；habit → `done/missed/exempt`
- cycle_key: daily → `2026-10-26`；weekly → `W2026-44`（ISO 周）
- 迁移 SQL: `sail_server/migration/20261026_add_rhythm.sql`（PG）；SQLite 由 create_all 自动建表

## 4. 核心算法（model/rhythm_planner.py，服务端确定性）

### 4.1 统一优先级评分

分类紧迫度 u(kind)：

| kind | u |
|------|---|
| task_oneoff | ddl≤1d→1.0, ≤3d→0.8, ≤7d→0.5, else 0.2 |
| task_maintenance | clamp((now-last_done_at)/interval_days, 0, 1.2)；从未完成→1.0 |
| habit | 本周剩余目标次数 / 本周剩余可排日数（封顶 1.2） |
| venture | 剩余估算工时 / (剩余周数 × weekly_budget_hours)（封顶 1.2） |
| async_callback | DELEGATED→0；kickoff/review 按 ddl≤1d→1.0/≤3d→0.8/≤7d→0.5，无 ddl 用 next_review_at 反推（≤6h→1.0/≤24h→0.8/≤72h→0.5），否则 0.3 |
| fixed/precept/base_rhythm/buffer | 不参与评分（刚性/规则铺底） |

```
score = 100 * ( w_i*importance/5 + w_u*u + w_b*domain_balance_boost
              + w_e*energy_fit + w_s*streak_boost )
默认权重 w_i=0.30 w_u=0.30 w_b=0.20 w_e=0.15 w_s=0.05（profile.score_weights 可调）
domain_balance_boost：最近 7 天三域实际比 vs 目标权重的欠投入度 0..1
energy_fit：候选小时的能量曲线系数 0..1
streak_boost：habit streak≥3 → 1.0
生活地板：未达周目标的 habit，score 抬升至当日 work/career 事务最高分之上
```

### 4.2 精力模型

每日 100 点；energy_cost 粗刻度：轻量 5 / 常规 10 / 深度 25 / 重决策 40；
运动 habit 15–25；通勤 micro 5。曲线 curve_template 分 weekday/weekend 各 24 段。
当日已排+DONE 精力 > 预算 110% → `energy_overload` warning。

### 4.3 财力校验

money_cost>0 且指定 budget_id：查 finance 预算（total_amount − 关联 transaction 合计）。
不足 → `budget_insufficient` warning；非 force 时该事务 unplaced(预算不足)；
fixed_plan 超预算只警告不阻止钉入。

### 4.4 plan_day 八步铺底（顺序即优先级）

1. **睡眠守护**：profile 睡眠窗 → 晨/夜两个 pinned sleep 块
2. **基础节奏骨架**：命中模板（weekday_mask，priority 高者优先）实例化槽位；
   work_window 是"容器"（不占排程空间，focus 排入其中）；micro_cycle 生成
   informational 微休息提示块（允许 focus 跨越）
3. **刚性钉**：fixed_plan 钉入；与骨架/他块冲突 → `fixed_conflict` warning，**不移动**
4. **戒律打卡块**：soft precept（block_minutes>0）避开工作窗排轻量块
5. **缓冲扣除**：min_buffer_ratio × 清醒窗，分散插入（工作窗边界/睡前），
   不足 → `buffer_short` warning
6. **事业块**：ACTIVE venture 仅排 spare_time_windows；周预算耗尽 → unplaced
7. **习惯与工作任务竞争**：habit 按周缺口先排（生活地板），task 按 score 降序
   贪心进工作窗；放不下 → 超窗 `overtime` warning；
   `max_consecutive_focus` policy（params.minutes）超长的 focus 块后强制插 15min rest
8. **产出** `PlanDayResponse{blocks, warnings, unplaced}`；plan_version+1，
   旧 PLANNED 非 pinned 块置 MOVED（可回滚）；pinned 与 DONE/DOING 冻结；
   `domain_cap` policy（params.domain/hours）按域核算实际占用（容器块不计），
   超限 → `domain_cap_exceeded` warning

> policy 职责分工：`spare_time_guard`（默认启用）与 `max_consecutive_focus`、
> `domain_cap` 由排程器消费；`protect_window` 由侵占检测消费；
> `kind_min_freq` 由 habit 周缺口压力等效覆盖（agent habit_watch 管线巡检）。

### 4.5 侵占检测与再平衡

- `GET /plan/conflicts?date=`：protect_window 穿透 / career 越界 / fixed 被挤 / overtime
- `POST /plan/rebalance`：增量重跑 plan_day（pinned + DONE/DOING 冻结），
  diff 由 plan_version 推导

### 4.6 节奏评分（Review）

```
rhythm_score = 0.25*precept_compliance_rate + 0.20*habit_consistency
             + 0.15*sleep_window_keeping   + 0.15*(1−三域偏离度)
             + 0.15*min(venture_budget_fulfillment,1.0) + 0.10*(1−buffer_consumed)
（无 ACTIVE venture 时 0.15 并入三域偏离项 → 0.30）
```

日评 `scope=day`（period_key=2026-10-26）；周评 `scope=week`（period_key=W2026-44），
计算后 upsert 落库 rhythm_reviews；`PUT /review/{scope}/{key}/summary` 供 Agent 写回周评。

## 5. REST API（/api/v1/rhythm）

```
# 事务
POST   /affair/                     快速捕获（仅 title 即可，kind=generic → INBOX）
GET    /affair/                     列表（state/domain/kind[多值]/day_id/parent_id）
GET    /affair/{id}                 详情
PUT    /affair/{id}                 编辑（kind 改判 + kind_meta 校验 + ai_hint 写回）
DELETE /affair/{id}                 删除
POST   /affair/{id}/state           状态转移 {action, defer_to?, defer_end?, force?}
POST   /affair/{id}/confirm-hint    采纳/驳回 AI 建议 {accept, overrides?}
POST   /affair/{id}/split           拆分落地 {children[]}
# 模板
GET/POST /template/                 列表 / upsert（按 name）
GET    /template/{id}               详情
PUT    /template/{id}               更新
DELETE /template/{id}               删除
GET    /template/active?date=       某日命中模板
# 打卡
POST   /checkin/                    打卡 {affair_id, result, log_date?, note?, source?}
GET    /checkin/                    日志查询
GET    /checkin/today?date=         今日待打卡清单
# 事业
GET    /venture/{id}/progress       倒排进度
POST   /venture/{id}/milestone      添加里程碑（timespan_id 锚定）
POST   /venture/milestone/{mid}/done 勾选里程碑完成
# 时间线
GET    /timeline/day?date=          日时间线（blocks+三域统计+待打卡）
POST   /timeline/block              手动建块
POST   /timeline/block/{id}/status  块反馈 {status: DONE|SKIPPED|DOING|PLANNED}
POST   /timeline/block/{id}/move    手动拖改（pinned → 409）
# 计划
POST   /plan/day                    生成/重生成日计划 {date, preserve_done?, force?}
POST   /plan/rebalance              再平衡 {date, trigger}
GET    /plan/conflicts?date=        侵占报告
# 配置
GET/PUT /energy/profile             精力画像（单行 upsert）
GET/POST/PUT/DELETE /policy/...     守护策略 CRUD + 启停
# 复盘
GET    /review/day?date=            日评分（即时计算并落库）
GET    /review/week?span=           周评分（span=W2026-44 或日期；缺省本周）
PUT    /review/{scope}/{key}/summary Agent 写回周评语
GET    /review/encroachments        侵占事件列表（默认最近 7 天）
```

鉴权：`SAILZEN_API_TOKEN` 非空时校验 `Authorization: Bearer <token>`（复用 reminder 模式）。

## 6. CLI（python -m sailzen rhythm …）

全命令支持 `--json`（AI 解析，stdout 纯 JSON）与默认人类可读表格。

```
sailzen rhythm capture "给车做保养" [--kind habit --meta '{...}' --domain life]
sailzen rhythm kinds                          # 分类学权威输出（分拣 prompt 同源）
sailzen rhythm inbox [--limit 50]
sailzen rhythm suggest-triage [--limit 20]    # 【AI】拉 INBOX + 分类学/schema 规范
sailzen rhythm hint <id> --kind habit --meta '{...}' [--importance 4 --energy 15
                        --est 60 --money 200 --window start/end --fallback "..." --reason "..."]
sailzen rhythm suggest-split <id>             # 【AI】拆分草案（不落库）
sailzen rhythm split <id> --file split.json   # 确认后落库（CLI 侧先校验）
sailzen rhythm confirm <id> [--accept-hint]
sailzen rhythm defer <id> --to 2026-10-29
sailzen rhythm template list|show <id>|upsert --file t.json|active --date D
sailzen rhythm checkin <id> --result kept|violated|done|missed [--note "..."]
sailzen rhythm checkin today
sailzen rhythm habit board
sailzen rhythm venture status [<id>]
sailzen rhythm venture milestone <id> --title "demo 完成" [--span Y2027Q2|B0049]
sailzen rhythm plan today|YYYY-MM-DD [--force]
sailzen rhythm timeline [today]
sailzen rhythm done <block_id> | skip <block_id>
sailzen rhythm rebalance [today] [--trigger manual]
sailzen rhythm score [--week] [--span W2026-44]
sailzen rhythm review --week --md             # Markdown 周报（供 notes 归档）
sailzen rhythm conflicts [today]              # 冲突/侵占报告
sailzen rhythm summary --scope week [--key W2026-44] [--file s.md | --text "..."]
                                              # 【AI】写回复盘评语 ai_summary
sailzen rhythm profile show | set [--work-cap 7 --buffer 0.2 --career-weight 0.6 ...]
sailzen rhythm policy list | add --name X --rule-type spare_time_guard | toggle <id>
```

服务器地址解析：`SAIL_SERVER_URL` > `.env.prod/.env.dev` 的 SERVER_HOST/PORT > `http://localhost:8000`；
token 取 `SAILZEN_API_TOKEN`。

## 7. AI 调用契约

**隔离红线**：Agent 只调 CLI/HTTP，绝不直连主库。LLM 配置走 Agent 自带 LLMGateway。

1. **分拣**：Agent 调 `sailzen rhythm suggest-triage --json` → 获得 INBOX 事务 +
   kinds 分类定义 + hint_schema → LLM 按固定 JSON Schema 产出建议：
   `{kind(九选一), domain, kind_meta(按 kind), importance(1-5), energy_cost(5/10/25/40),
     est_minutes, window, fallback_plan, split_children[]}`
   → 逐项 `sailzen rhythm hint <id> ...` 写回（CLI 同源校验 kind_meta，非法即拒绝，
   exit code 2）→ 人在 Android/CLI `confirm --accept-hint` 采纳生效。
2. **拆分**：`suggest-split <id>` 出草案 → 人确认 → `split <id> --file split.json` 落库。
3. **周评**：`review --week --md` → LLM 生成周评 → `PUT /review/week/{key}/summary` 写回
   → notes 归档。
4. **prompt 模板**（分拣系统提示节选）：

   ```
   你是节奏分拣员。按 kinds 定义把 INBOX 事务分拣为恰好一种 kind 并给出 kind_meta 草案。
   规则：惩罚性/禁止性 → precept；建设性/累计性 → habit；固定起止 → fixed_plan；
   业余长期事业 → venture；工作一次性 → task_oneoff；周期维护 → task_maintenance。
   输出严格 JSON（不要多余文字）：{"kind": "...", "domain": "...", "kind_meta": {...},
   "importance": 1-5, "energy_cost": 5|10|25|40, "est_minutes": int,
   "window": "start/end"|null, "fallback_plan": "...", "reason": "..."}
   ```

## 8. Android 端（M3）

- `feature/timeline/`（今日时间线：块按 block_type 着色、滑动 done/defer、长按 Plan B、顶部周节奏卡片 rhythm_score 环形图 + 三指标点击看周报）
- `feature/checkin/`（打卡中心：戒律 kept/violated + 备注、习惯 done/missed、streak 火焰、周进度环）
- `feature/venture/`（事业看板：倒计时、周预算进度条、里程碑、倒排压力灯）
- 快速捕获（可选 kind，默认 generic 交 AI 分拣）+ AI 建议采纳卡
- `core/network/RhythmApi`（Retrofit，仿 ReminderApi）；done/defer/checkin 离线排队补传

## 9. Agent 管线（M4，sailzen/autonomous_agent/pipelines/rhythm_*.yaml）

| 管线 | 调度 | 流程 |
|------|------|------|
| rhythm_nightly_plan | 0 22 * * * | 明日模板+INBOX/PLANNED/ACTIVE → LLM 预审 hint → plan tomorrow → warnings 非空 → reminder |
| rhythm_precept_check | 0 22:30 * * * | 当日戒律未核销 → reminder；连续破戒 ≥3 天 → LLM 归因建议 |
| rhythm_habit_watch | 0 20 * * * | habit 周缺口压力 >0.8 → 提醒/最小剂量 fallback 建议 |
| rhythm_venture_weekly | 0 20 * * 0 | 预算达成/倒排压力 → LLM 下周事业安排建议（待确认） |
| rhythm_goal_decompose | 0 9 * * 1 | venture 按双周拆里程碑草案 → suggest-split 待确认 |
| rhythm_encroachment_watch | 每小时 | plan/conflicts → high 优先级 reminder |
| rhythm_weekly_review | 0 21 * * 0 | review --week --md → LLM 周评 → `summary` 写回 ai_summary → `notes write` 归档 → 推送 |
| rhythm_evening_check | 0 21 * * * | hard precept 未守/habit 未完且窗口将尽 → fallback/defer 提示 |

## 10. 风险与开放问题

| 风险/问题 | 对策 |
|-----------|------|
| 分类学理解成本 | generic 兜底 + AI 分拣；kinds 与文档/CLI 同源；M1 宽松校验，M2 CLI 收紧 |
| base_rhythm 模板 vs policy 职责重叠 | 模板负责"生成骨架"，policy 负责"校验约束"；模板不校验、policy 不生成 |
| 精力点数估计主观 | M1 粗刻度；M4 后用睡眠/体重/完成率回归校准 curve_template |
| 与 Mission 双写一致性 | affair.mission_id 单向引用，最终一致（M1 接受） |
| venture 与家庭 fixed_plan 冲突周 | travel_day 模板 + habit/venture 建议 PAUSED；周报记 exempt |
| plan_day 贪心次优 | 预留 strategy 参数，后续可换 CP-SAT（scipy 已在栈内） |
| 隐私 | 全部本地/局域网；SAILZEN_API_TOKEN 复用 reminder 鉴权 |
| 时间口径 | 全链路 naive local（对齐 reminder `_now()` 约定） |
