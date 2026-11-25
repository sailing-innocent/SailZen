# Finance 2.0 — SailTick 驱动的日常开销秘书架构设计

> **版本**: v2.0 | **日期**: 2026-11-25 | **状态**: ✅ Phase 1 + Phase 2 已实现
> **关联文档**: [SailTick Personal Agent 设计文档](../../agent-system/sailtick.md) · [Rhythm v2 设计文档](./rhythm.md) · [财务基础模型](./life_budget.md)
> **实施分期**:
> - **Phase 1（已完成）**: 数据模型升级（明细拆分/无感平账/清理队列）、后端 API、视觉 OCR 账单/小票识图、SailTick 慢快双脑全面接管、夜间按月倒推慢迭代回填、Web 财务秘书工作台、2 年历史账单诊断与安全清理脚本。
> - **Phase 2（已完成）**: Android 端小票/账单拍照与相册识图、一句话快脑记账、智能余额核对与分级清理队列，以及云端与本地 `D:\vault` 日记双向轻量桥接（`sailzen vault sync-journals` 摘要同步 + `sailzen vault export-finance-review` 月报回写 + SailTick 差旅/情绪消费上下文关联）。

---

## 1. 重构背景与目标定位

基于过去两年的真实记账数据（本地快照审计：2,538 笔有效交易，552 笔未打标，78 笔 `balance fix` 集中在 `1970-01-01` 伪时间戳，仅 9 个默认标签），原财务系统暴露出 5 个核心痛点：

1. **记账与纠错心智税过重**：日常只能大致记对，偶发漏记/重复记账难以靠人工翻查修正。
2. **小额漂移污染真实统计**：利息、红包、退款等小额收支难以逐笔追踪，只能定期 `fix_balance` 强制重置；旧实现写入 `htime=1` (`1970-01-01`) 且未与消费统计隔离，扭曲历史数据。
3. **标签粗颗粒与混合采购盲区**：仅有 9 个默认标签且依赖手动打标；超市/电商一笔混合采购同时包含日用品与零食时无法拆解，导致健康管理看不见真实零食摄入。
4. **数据脏乱阻塞深度分析**：未清洗的数据无法支撑固定/弹性支出拆解、现金流预测、应急储备评估与开源节流建议。
5. **跨领域孤岛**：账单与健康（零食/外卖/聚餐）、日程（高铁/机票/酒店行程）、个人笔记（`D:\vault` 日记上下文）彼此割裂。

### 核心定位

> **不是做一套严格复式记账的企业财务软件，而是做一个「懂我」的日常开销秘书。**
> 允许小额自然漂移存在（无感平账、不污染统计），让 AI 在夜间静默完成打标、体检、建模与跨领域关联，白天用自然语言或一张小票截图完成记账与核对。

---

## 2. 四项关键架构决议（已与用户确认）

| 维度 | 决议 | 说明 |
|---|---|---|
| **AI 写回自治度** | **分级自治（Graded Autonomy）** | 高置信度打标（≥0.90）、历史 `balance fix` 归类、小额平账（≤¥30）静默落库并记入可一键撤销的审计日志；大额异常、疑似重复删除、大额漂移与新标签创建进入「待审清理队列」或轻量票据确认。 |
| **混合采购拆分** | **单交易 + JSONB 明细（`meta.items`）** | 保持「1 笔真实支付 = 1 条 `Transaction`」与微信/支付宝/银行流水 1:1 对应；OCR 或手动拆出的多品类明细存于 `Transaction.meta["items"]`，统计与健康联动优先按明细汇总，无明细时回退交易主金额与主标签。 |
| **与 `D:\vault` 联动** | **云端轻量只读桥接（Phase 2 主力，Phase 1 预留接口）** | 通过 Git/CLI 将近期 `journal.daily.*` 轻量摘要同步至云端供 SailTick 关联差旅与消费动机，同时支持将周/月财务复盘 Markdown 导出回 `D:\vault`。 |
| **推进节奏** | **分阶段落地** | Phase 1 跑通「后端 + OCR + SailTick 慢快双脑 + Web 工作台 + 2 年历史数据体检清理」，Phase 2 跟进 Android 端升级与 Vault 桥接。 |

---

## 3. 数据模型演进（全量增量兼容，零破坏）

遵循 `AGENTS.md` 规范：ORM 统一定义于 `packages/py/sailzen-orm/sailzen_orm/finance.py`，PostgreSQL 迁移使用幂等 SQL 文件 `sail_server/migration/20261125_finance_sailtick_upgrade.sql`（Expand-Only，支持代码安全回滚）。

### 3.1 `transactions` 增量字段

| 字段 | 类型 | 默认值 | 职责 |
|---|---|---|---|
| `entry_kind` | `VARCHAR` | `'normal'` | `normal`（正常收支/转账）\| `micro_adjust`（小额无感平账）\| `balance_adjust`（大额/历史平账重置）\| `refund`（退款） |
| `exclude_from_stats` | `BOOLEAN` | `FALSE` | 为 `TRUE` 时不计入消费/收入趋势统计，但**仍计入账户余额计算**，彻底隔离平账噪音 |
| `meta` | `JSONB` | `'{}'` | 结构化扩展：`items`（混合小票多品类明细）、`reconcile`（对账快照）、`links`（关联 Diet/Rhythm/IntakeDraft/Vault）、`ai_audit`（AI 自动处理溯源） |

`meta.items` 规范格式：
```json
{
  "items": [
    {"name": "薯片+无糖可乐", "amount": "42.00", "tag": "零食", "is_snack": true, "health_hint": "高热量零食"},
    {"name": "洗衣液+抽纸", "amount": "86.00", "tag": "日用消耗", "is_snack": false}
  ],
  "links": {
    "intake_draft_id": 18,
    "diet_ids": [421],
    "rhythm_occupancy_id": null,
    "vault_date": "2026-11-25"
  },
  "ai_audit": {
    "source": "sailtick_hygiene",
    "confidence": 0.95,
    "proposal_id": 12
  }
}
```

### 3.2 `accounts` 增量字段

- `meta` (`JSONB`, default `'{}'`): 账户级配置（如 `exclude_from_consumption: true` 标记房贷账户、`drift_tolerance: 30.0` 自定义小额平账阈值、`last_reconciled_at`、`aliases` 供自然语言匹配）。

### 3.3 新增表 `finance_balance_checkpoints`（余额核对快照）

记录每次真实账户余额校准：
- `id`, `account_id` (FK `accounts.id`), `reported_balance`, `book_balance`, `drift_amount`, `handling` (`exact` \| `micro_adjusted` \| `large_drift_pending` \| `manual_reset`), `adjustment_tx_id` (nullable FK `transactions.id`), `note`, `source`, `created_at`。

### 3.4 新增表 `finance_hygiene_proposals`（分级自治清理与审计队列）

统一承载「AI 已静默处理（可一键撤销）」与「待人工确认」两类账单治理建议：
- `id`, `proposal_type` (`auto_tag` \| `legacy_fix_classify` \| `duplicate_merge` \| `large_drift` \| `micro_adjust_audit` \| `travel_rhythm_link` \| `mixed_split_hint` \| `new_tag_suggest`)
- `autonomy_level`: `auto_applied` \| `needs_review`
- `status`: `pending` \| `applied` \| `reverted` \| `dismissed`
- `target_tx_ids` (`JSONB`), `confidence` (`FLOAT`), `title`, `reason`
- `before_snapshot` (`JSONB`, 撤销恢复用), `after_payload` (`JSONB`), `created_by`, `created_at`, `resolved_at`

---

## 4. 后端 API 契约（`/api/v1/finance/...`）

| 方法与路径 | 职责 |
|---|---|
| `GET /finance/overview` | 财务秘书聚合视图：本月真实支出/收入/净结余、真实零食支出（含明细拆分）、标签覆盖率、待审/已托管条数、账户对账健康度、Top 标签 |
| `GET /finance/transaction/breakdown-stats` | 按品类/标签汇总真实消费（优先按 `meta.items` 拆分金额累加，无明细回退主标签；自动排除 `exclude_from_stats`） |
| `PUT /finance/transaction/{id}/meta` | 更新单笔交易的明细拆分 `items`、跨领域 `links`、`entry_kind` 与 `exclude_from_stats` |
| `POST /finance/account/reconcile` | 智能余额核对：自动计算差额 `Δ`；小额（默认 `≤ ¥30`）静默记 `micro_adjust`（不污染统计，当前时间戳，附可撤销审计）；大额创建 `large_drift` 待排查建议（或用户显式 `force_adjust=true` 强制平账） |
| `GET /finance/account/checkpoints` | 查询余额核对历史与累计漂移统计 |
| `POST /finance/hygiene/scan` | 运行确定性账单健康体检扫描（历史 `balance fix` 隔离、高置信度模式匹配打标、疑似重复交易检测、差旅/混合采购识别、长时间未记账提醒），支持 `auto_apply_safe=true` 分级自治执行 |
| `GET /finance/hygiene/proposals` | 分页/按状态过滤查询清理队列与 AI 托管审计日志 |
| `POST /finance/hygiene/proposals/{id}/approve` | 批准并执行待审建议 |
| `POST /finance/hygiene/proposals/{id}/dismiss` | 忽略待审建议 |
| `POST /finance/hygiene/proposals/{id}/revert` | 一键撤销任意 `applied` / `auto_applied` 操作（按 `before_snapshot` 精准回滚） |

> 兼容保证：原有 `/finance/transaction/stats/` 与 `/stats/batch/` 默认过滤 `exclude_from_stats=False`（同时通过 `include_excluded=true` 可按需查全量），旧 `POST /finance/account/fix_balance` 内部自动写入当前 `htime` + `entry_kind='balance_adjust'` + `exclude_from_stats=True`，彻底杜绝 `1970-01-01` 脏数据再生。

---

## 5. 视觉 OCR 账单与小票识图（复用 `tick_intake.py`）

扩展现有二段式确认识图引擎（`POST /api/v1/tick/intake/image` → 人工确认卡片 → `POST /api/v1/tick/intake/{id}/commit`）：

- **新增场景（`scene`）**：`receipt`（商超/餐饮小票）、`bill_screenshot`（微信/支付宝/美团/京东账单截图）、`account_balance`（账户余额页截图）。
- **新增条目类型（`kind`）**：
  - `transaction`：抽取金额、商户/描述、交易时间、收支方向、建议账户（如微信/支付宝）、主标签，以及**自动拆分的商品明细数组 `items`**（逐项标注 `tag` 与 `is_snack`）。
  - `account_balance_check`：抽取账户名与当前余额，确认后直接触发智能对账 `/account/reconcile`。
- **跨领域自动联动（落库时）**：
  - 若 `items` 中存在 `is_snack=true` 或餐饮类目且开启 `sync_to_health`（默认开启），自动向健康模块写入轻量 `DietLog` 并将 `diet_id` 回写到 `Transaction.meta.links.diet_ids`。
  - 若识别为高铁/机票/酒店订单且带出行日期，支持同步写入 `SailTickMessage` / 触发 Rhythm 差旅占用建议。

---

## 6. SailTick 统一 Personal Agent 财务接管（v4.0）

严格遵守**双库隔离红线**：`sailtick/finance_client.py` 仅经 HTTP 访问 `/api/v1/finance/*`，绝不直连主库。

### 6.1 夜间慢脑深度分析与「蚂蚁搬家式」历史慢迭代（`sailtick/finance_analytics.py` + `nightly.py`）

历史账单整理是跟随日常生活的**长期慢项目**，不急于一时、不靠手工一次性硬刷。每晚 `00:00` 在 `NightlySelfMaintenance` 中由 AI 自己记录进度、控制节奏静默推进：

1. **近期轻量巡检 + 按月倒推历史游标（`st_runtime_state["finance_backfill_progress"]`）**：
   - 先巡检近 14 天日常新流水，保持当下账本干净；
   - **待审水位背压限流**：查询 `pending_hygiene_count`，一旦达到水位上限（默认 `5` 条，`finance_backfill_pending_cap`），自动标记 `status="paused_backpressure"` 暂停历史深挖，**绝不给用户堆清理负担，也绝不发提问催促**；
   - 若水位有余量，调 `GET /finance/hygiene/months` 按最新→最早跳过已整洁月份，每晚**只推进 1 个有待整理账单的历史自然月**（单晚最多新增 `3` 条待审建议），高置信度补标与历史 `balance fix` 隔离静默落库（全部可一键撤销），AI 自动把 `cursor_month`、`completed_months` 与累计战果持久化到 `sailtick.db` 与语义记忆中；
   - **Stage 2 慢脑长尾研判**：对本晚推进的历史月剩余长尾未标交易（每晚最多 `4` 条），由慢脑 LLM 结合标签体系与长期记忆温和推断并仅写入 `needs_review` 建议（受同一水位预算约束，绝不越权改库）。
2. **确定性财务健康建模（`FinanceAnalyticsEngine`）**：
   - 剔除转账、平账与房贷类排除账户后的**真实月度收支、储蓄率、日均消费、月底支出预测**；
   - **真实零食消费追踪**（独立零食交易 + 混合小票 `meta.items[is_snack]` 汇总，直接喂给健康减重模块）；
   - **固定 vs 弹性支出结构**与周期性账单（房租/工资/订阅）识别；
   - **账户沉默检测**（常用消费账户连续多日无记录提示）与累计漂移追踪；
   - **跨领域信号发现**：差旅账单（高铁/酒店）提示关联 Rhythm 日程，深夜/高压期消费飙升提示结合睡眠与情绪关注；
   - 编译进统一 `expert_brief["finance"]`，产出 2–3 条具体可执行的「开源节流」洞察与最多 1 条高价值发问建议。

### 6.2 定时 Tick 与睡前综合日报（`tick_engine.py` + `datascan.py`）

- `DataScanner` 新增紧凑 `finance` 信号（本月支出、今日支出、真实零食开销、标签覆盖率、待审清理数、沉默账户列表）。
- `TickEngine` WORK 新增动作：`finance_log_tx`、`finance_reconcile_account`、`finance_run_hygiene`、`finance_batch_tag`。
- `pre_sleep_report` 升级为「健康 + 节奏 + 财务」三域合一睡前简报；财务与健康、节奏共享防轰炸票据配额（绝不刷屏）。

### 6.3 白天快反助手（`quick_agent.py`）

- **零延迟斜杠命令**：`/money`（`/账单` / `/财务`）、`/accounts`（`/余额`）。
- **自然语言秒级动作**：
  - 一句话记账（支持混合拆分）：「午饭外卖 32 微信」「盒马花了 128，零食 42 日用 86，支付宝」→ `finance_log_tx`
  - 一句话对账：「支付宝余额对齐到 2950.3」→ `finance_reconcile_account`
  - 一句话补标/纠错：「把刚才那笔打上日用消耗」→ `finance_batch_tag`
- 响应新增 `finance_updated: true`，触发 Web `/money` 页面即时刷新。

---

## 7. Web 财务秘书工作台（`site/src/pages/money.tsx`）

保留现有账户表、交易表、预算管理与统计图表，顶部与核心区升级为 SailTick 驱动的开销秘书工作台：
1. **SailTick 财务秘书即时协商条**：自然语言记账、对账、查询开销与快捷提问，daemon 离线时优雅降级入异步消息箱。
2. **秘书健康概览条**：本月真实支出、真实零食开销（含小票拆分）、标签覆盖率、待审清理数，一键打开「小票/账单 OCR 识图」或触发「智能体检」。
3. **分级自治清理与审计面板（`FinanceHygienePanel`）**：分「待人工确认」与「AI 已静默托管（可一键撤销）」双标签，支持单笔批准/忽略/撤销。
4. **智能余额核对弹窗**：输入当前真实余额后实时预览差额 `Δ` 与处理模式（无感小额平账 vs 大额排查）。

---

## 8. 账单体检 CLI（`scripts/finance_audit.py`，可选辅助）

日常历史清理**默认完全交由 SailTick 夜间按月倒推慢迭代静默消化**，无需人工手动执行。`scripts/finance_audit.py` 仅作为本地只读体检或按需诊断工具保留：
- `uv run python scripts/finance_audit.py --env dev --dry-run`：只读体检历史数据并回滚（零副作用），随时查看全历史标签覆盖率与问题分布。
- `uv run python scripts/finance_audit.py --env dev --apply-safe`：（可选）仅当需要手动在本地调试库快速验证批量清洗效果时使用。
