# SailTick Round 2 架构升级：记忆与控本系统 + 多端多 Tab 消息与角色分流

> **状态**: 已实施并完成多端构建与单测验收 | **日期**: 2026-11-28 | **依据**: [sailtick_review_round_1.md](./sailtick_review_round_1.md)

---

## 1. 升级背景与生产基线

基于首周生产埋点与 `prod_week_20261128` / `prod_48h_20261128` 快照复盘，识别出两类结构性瓶颈：

1. **记忆膨胀与成本漂移**：
   - `st_memories` 缺少 `(memory_type, key)` 幂等 Upsert，导致 6 天内日间 Tick 输入 Token 膨胀 4×（`2,480 → 10,288`）；
   - 所有窗口均默认走 `deepseek-reasoner` 并注入全量 Action Schema；
   - `quick_chat` Token 记账字段读取错误导致 Trace 显示为 0；
   - 食物研究混入泛词/长句且串行执行；`nightly` Span 均为 `0ms` 瞬时点且内层 LLM 未归因。
2. **多端多 Tab 角色与消息串台**：
   - 所有 SailTick 票据与日报统一投递至 `source_domain="sailtick"`、`deep_link="/health/coach"`，导致健康 Tab 与健康通知中混入日程/项目/账单内容；
   - VSCode Workbench `sendQuickChat` 传参 `message` 字段引发 4xx；
   - Android 离线提醒反馈队列对终态 4xx（`409`/`404`）无限重试造成 4xx 风暴。

---

## 2. 支柱一：基于 SailTick 节奏的记忆与控本架构

### 2.1 冷热分层与 FTS5 毫秒检索

- **冷层（原始证据零丢失）**：
  - `data/sailtick/snapshots/{date}_{slot}_{kind}.json.gz` + `st_raw_snapshots` 元数据指针表（留存 30 天）；
  - `data/sailtick/archives/episodes_{YYYY-MM}.jsonl.gz`（超 30 天事件自动压缩冷归档）；
  - `st_memories.value` 保留完整原始 JSON，`status` 区分 `active | superseded | archived`。
- **热层（Prompt 极简与快查）**：
  - `st_memories` 增量补齐 `domain / summary(<=100字) / confidence / salience / hit_count / status / superseded_by / updated_at / last_used_at`，`AgentMemory.save()` 强制按 `(memory_type, key)` 幂等 Upsert；
  - `st_domain_briefs` 物化 4 份分域精简热视图（`health / rhythm / finance / chief`，每域 `<= 450` 字符）；
  - SQLite `FTS5` 虚表 `st_memory_fts`（中文 2-gram + `unicode61` 切词，不可用时自动降级 `LIKE`）提供毫秒级检索，开放 `GET /api/v1/tick/memory/search`。

### 2.2 预算裁剪、分级模型路由与 JSON 三段自愈

- `sailtick/context_budget.py`：`PromptBudgeter` 按 Slot 白名单裁剪 Action Schema 并对 9 个 Prompt 区块实施硬字符截断，将总字数明细写入 Trace `prompt_budget` Span。
- `sailtick/llm.py`：新增 `resolve_slot_route()` / `chat_for_slot()`：
  - `morning_checkin` / `midday_checkin` 默认走 `fast`（`deepseek-chat`），触发异常/红线自动升档 `default`（`deepseek-reasoner`）；
  - 当日累计消耗超 `daily_soft_cap`（40k）自动降档 `fast`；超 `daily_research_cap`（80k）跳过非核心夜间长尾研究；
  - 修复 `LLMResponse.prompt_tokens / completion_tokens / total_tokens` 属性与 `QuickCoachAgent` Trace 记账。
- `parse_json_with_repair()`：确定性语法修复（去围栏、去尾逗号、补跨行逗号与截断闭合）→ 至多 1 次 `chat_fast` 廉价修复 → 规则兜底。
- `sailtick/knowledge.py` & `sailtick/nightly.py`：强化食物停用词/长句清洗、并发限流（`Semaphore(2)` + 45s 超时）、夜间真实耗时 Span 与 LLM 用量归因、确定性夜间记忆压实（`compact_memories`）。
- 视觉识图优化（`sail_server/model/tick_intake.py`）：标准餐盘/自拍压缩至长边 1280px 并默认 `detail="auto"`，仅账单/小票/长截图/显式 OCR 开启 `detail="high"`。

---

## 3. 支柱二：三维消息路由与多端多 Tab 交互分流

### 3.1 规范业务域与角色矩阵

| `domain` | `persona`（显示名） | 默认 `deep_link` | 默认 `target_clients` | 共享 QuickChat 会话键 |
|---|---|---|---|---|
| `health` | `health_coach`（健康教练） | `/health/coach` | `["android", "web"]` | `owner:health` |
| `rhythm` | `rhythm_planner`（节奏规划师） | `/rhythm` | `["android", "web", "vscode"]` | `owner:rhythm` |
| `finance` | `finance_secretary`（财务秘书） | `/money` | `["android", "web"]` | `owner:finance` |
| `general` | `chief_steward`（生活总管） | `/tick` | `["android", "web"]` | `owner:general` |

- **睡前总览日报**：保持每晚 1 条低打扰 `[今日总览]` 推送，`SailTickDailyReport.sections` 按 `health / rhythm / finance / chief` 分别存储，各业务 Tab 仅渲染本域摘录，Inbox / `/tick` 展示完整总览。
- **跨端共享会话**：同一业务域跨 Web / Android / VSCode 共享 `owner:{domain}` 会话（如 VSCode Workbench 与手机规划页、Web `/rhythm` 无缝续聊），不同业务域严格隔离。

### 3.2 后端与数据模型（Expand-Only 幂等迁移）

- ORM（`packages/py/sailzen-orm/sailzen_orm/tick.py`, `inbox.py`）与迁移（`sail_server/migration/20261128_sailtick_domain_routing.sql`）：
  - `sailtick_tickets` 新增 `domain / persona / target_clients / deep_link` 及复合索引 `ix_tick_tickets_domain_status`；
  - `sailtick_messages` 新增 `domain / surface`；
  - `sailtick_daily_reports` 新增 `sections`；
  - `user_inbox_items` 新增 `target_domain / persona / target_clients` 及索引 `ix_inbox_user_target_domain`，并按 `topic` 幂等回填存量数据。
- 新增/升级 API：
  - `GET /api/v1/tick/domain-summary?domain=...`：各端分域聚合（待回票据 + 本域日报摘录 + 本域消息/草稿）；
  - `GET /api/v1/tick/quick-chat/history?domain=...`：拉取跨端共享的持久化分域对话历史；
  - `GET /api/v1/tick/memory/search?q=...&domain=...`：代理 SailTick FTS5 记忆检索；
  - `POST /api/v1/tick/quick-chat`：支持 `domain / surface / context_hints` 并兼容 `text | message` 别名；
  - `GET /api/v1/tick/health-summary` 严格过滤 `domain == "health"`；
  - `GET /api/v1/workbench/bootstrap` 严格过滤 `rhythm / approval / vscode` 票据；
  - `broadcast_inbox_upserted()` 支持按 `client_types` 定向推送 WebSocket。

### 3.3 多端交互落地

- **Web（`site/`）**：
  - `UserInboxPanel.tsx`：分域过滤胶囊 + 角色徽章 + 按 `deep_link / target_domain` 精准跳转；
  - 新增 `DomainAssistantBar.tsx` 复用于 `/rhythm`、`/money`、`/health`，展示本域待回票据、本域日报摘录与跨端共享对话；
  - `/tick` 升级为生活总管总控台（全量分域筛选、结构化多域日报、FTS5 长期记忆快查）。
- **VSCode 工作台（`packages/sailzen-workbench/`）**：
  - 修复 `sendQuickChat` `message → text` 4xx Bug，绑定 `domain="rhythm", surface="vscode_workbench"` 并加载 `owner:rhythm` 历史与快捷按钮；
  - `rhythmView` 票据支持点击弹出 `QuickPick`（快捷回复 / 自由回复 / 延后 1h / 延后 24h）；
  - `statusBar` 新增无打扰 `⚡ N` 待办票据微提示，全程严守 `PrivacyGuard`。
- **Android（`android/`）**：
  - `AppDatabase` 升至 v9，`CachedInboxItem` 新增 `targetDomain / persona`；
  - `NotificationHelper` 拆分 4 个 SailTick 通知渠道（`sailtick_health / sailtick_rhythm / sailtick_finance / sailtick_digest`），通知点击按 `EXTRA_DEEP_LINK / EXTRA_DOMAIN` 路由直达对应业务 Tab；
  - `InboxScreen` 新增分域过滤胶囊、角色标签与按域跳转按钮；
  - `PlanScreen / TodayTab`、`MoneyScreen`、`HealthCoachScreen` 各自隔离本域票据、本域日报摘录与跨端共享 `owner:{domain}` 会话；
  - 修复 `ReminderRepository` 对终态 HTTP 4xx（400–499）无限入队重试的 B5 风暴问题。
