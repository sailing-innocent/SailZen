# Rhythm v2 — SailTick 驱动的极简可视化日程画布与项目倒排底座

> **版本**: v2.0 | **更新**: 2026-11-24 | **状态**: ✅ Phase 1 已落地（Backend + SailTick 智能体接管 + Web 前端重构）；Android 端作为 Phase 2 跟进
> **关联文档**: [SailTick Personal Agent 设计文档](../../agent-system/sailtick.md)
> **实现**: `packages/py/sailzen-orm/sailzen_orm/rhythm.py` · `sail_server/{application/dto,model,controller,router}/rhythm.py` · `sailtick/{rhythm_client,rhythm_analytics,tick_engine,quick_agent,nightly,datascan}.py` · `site/src/pages/rhythm.tsx` · `tests/server/test_rhythm_v2.py` · `tests/sailtick/test_rhythm_integration.py`

---

## 1. 重构背景与核心原则

Rhythm v1 试图用确定性公式（`importance/urgency/domain_balance/energy_fit` 权重 + 8 步铺底硬排）管理全部工作与生活，但实践暴露出三大问题：

1. **PM 管理税过重**：人需要不断维护 10 类 `AffairKind`、精力曲线、骨架模板、守护策略与权重比例，精力消耗在“伺候系统”而非推动事情。
2. **意外情况无法公式化**：临时加会、没睡好、项目卡壳、提前下班等高频变动超出规则排程能力，生成的日程一旦不贴合当下状态，人就无法遵循。
3. **机械定时提醒打扰**：`reminder_scheduler.py` 写死的固定点位提醒脱离上下文，与 SailTick 冲突。

**Rhythm v2 核心范式**：

- **最终的日程只是一个可视化的前端，排布日程实际上是与 AI 长期交流、逐渐分析理解的过程。**
- **Rhythm 退居为“结构化项目/任务事实库 + 可视化日程画布”**：彻底移除旧公式排程器（`rhythm_planner.py` / `rhythm_scheduler.py`）、骨架模板表、精力权重配置表、守护策略表与评分快照表，关闭 `reminder_scheduler.py` 的机械日常提醒。
- **SailTick 升级为统一 Personal Agent 大脑**：慢脑（`TickEngine` + 夜间 `RhythmAnalyticsEngine`）负责长期学习真实高效/易打断时段与项目倒排风险，快脑（`QuickCoachAgent`）负责 1–3 秒响应突发变动并直接调 Rhythm API 写回时间线。

---

## 2. 极简数据模型（7 表 → 3 表）

| 表名 | ORM | 职责 |
|---|---|---|
| `rhythm_affairs` | `RhythmAffair` | 极简项目（`venture` + 目标日倒排）、一次性任务（`task_oneoff`）、刚性安排（`fixed_plan`）、轻量习惯（`habit`/`precept`）与随手记（`generic`） |
| `rhythm_time_blocks` | `RhythmTimeBlock` | 日可视化时间线画布（SailTick 自主落库，`plan_version` 版本化归档旧块，`pinned` 标记会议/请假等刚性块，`ref.ai_rationale` 记录当日排程说明） |
| `rhythm_discipline_logs` | `RhythmDisciplineLog` | 轻量习惯与健康计划连续打卡记录 |

已从 ORM 与代码中移除：`RhythmDayTemplate`、`RhythmEnergyProfile`、`RhythmPolicy`、`RhythmReview`、`rhythm_planner.py`、`rhythm_scheduler.py`。

---

## 3. REST API 契约（`/api/v1/rhythm`）

```text
# 可视化聚合入口
GET    /dashboard?date=YYYY-MM-DD            今日时间线 + 活跃项目倒排 + 焦点待办 + 占用 + 打卡

# AI 自主编排与时间线画布
GET    /timeline/day?date=YYYY-MM-DD         当日时间线（含 ai_rationale / completed_minutes / planned_minutes）
GET    /timeline/range?start_date=&end_date= 多日执行历史（供 SailTick 夜间学习真实高效与易打断时段）
GET    /timeline/day-view?date=YYYY-MM-DD    轻量日视图（兼容首页与 Android 端）
POST   /timeline/ai-sync                     【核心】SailTick AI 自主编排落库（保留 DONE/DOING 与 pinned，旧块置 MOVED 且 plan_version+1，自动推进关联任务为 SCHEDULED）
POST   /timeline/block                       手动/AI 补单块
DELETE /timeline/block/{id}                  移除时间块
POST   /timeline/block/{id}/status           标记 DONE / DOING / SKIPPED / PLANNED（habit 块 DONE 自动记打卡）
POST   /timeline/block/{id}/move             微调起止时间（pinned 拒绝 409）

# 重要项目倒排（Venture）
GET    /venture/projects                     全部活跃项目倒排进度与里程碑
GET    /venture/{id}/progress                单个项目倒排进度（days_left / recent_14d_hours / milestones / completion_ratio）
POST   /venture/{id}/milestone               添加里程碑子任务
POST   /venture/milestone/{mid}/done         一键勾选里程碑完成

# 极简事务（Affair）
POST   /affair/                              创建（默认 task_oneoff→PLANNED, venture/habit→ACTIVE, generic→INBOX）
GET    /affair/                              列表过滤（state/domain/kind/parent_id/urgency_ddl）
GET/PUT/DELETE /affair/{id}                  详情 / 三态编辑 / 删除
POST   /affair/{id}/state                    状态转移（finish/start/defer/pause/resume/graduate/cancel 等）
POST   /affair/{id}/split                    拆分子任务

# 刚性占用（会议/请假/出行）
POST   /occupancy/                           钉入刚性占用（幂等，AI 重排时强制保留）
GET    /occupancy/?date=                     查询某日占用
DELETE /occupancy/{block_id}                 删除占用

# 轻量打卡与健康速记
POST   /checkin/                             打卡记录
GET    /checkin/                             打卡查询
GET    /checkin/today?date=                  今日待打卡习惯
POST   /checkin/health                       健康速记双写
```

---

## 4. SailTick 调度闭环

- **客户端隔离**：`sailtick/rhythm_client.py` 严格经 HTTP 调用 `/api/v1/rhythm/*`，绝不直连主库。
- **夜间深度学习（`sailtick/rhythm_analytics.py`）**：统计近 21 天时间块完成率，自动识别「高效黄金时段」「易被打断时段」「过载减负信号」与「重要项目延期/停滞风险」，编译进统一 `expert_brief`。
- **慢脑异步排程（`TickEngine`）**：早间自动落库清爽今日画布、午间按上午实况弹性重排下午、晚间盘点并预排明日、睡前生成一份「健康 + 节奏」综合日报。日常排程直接落库，仅在重大项目取舍或明显延期风险时发最多 1 张轻量票据协商。
- **快脑实时应变（`QuickCoachAgent`）**：支持 `/today`、`/projects` 快捷指令，以及自然语言秒级处理临时加会、疲惫减负、新建项目/待办与重排当日剩余时间线。

---

## 5. Web 前端（`site/src/pages/rhythm.tsx`）

由原 8 个重配置 Tab 精简为单一清爽可视化工作台：

1. **顶部 SailTick 即时协商条**：一句话对话直接调用 `/api/v1/tick/quick-chat` 调整日程或项目（daemon 离线时自动降级写入异步消息箱），更新后自动刷新画布。
2. **左侧当日日程画布（`TimelineView`）**：展示 AI 排程说明（`ai_rationale`）、时间块列表、一键完成/进行中/跳过/改时间/删除，以及「钉占用」「补一块」快捷操作。
3. **右侧项目倒排与焦点待办**：只需填写项目名与目标日即可追踪倒计时与里程碑，支持随手记待办与轻量习惯打卡。
