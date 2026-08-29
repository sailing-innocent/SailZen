# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm ORM Models (生活/工作节奏综合优先级调节工具)
# @author sailing-innocent
# @date 2026-10-26
# @version 1.0
# ---------------------------------

"""
节奏（Rhythm）模块 ORM 模型

对应设计文档 doc/design/manager/rhythm.md：

- RhythmAffair        统一事务表（9 类 kind × 3 域 domain，双生命周期）
- RhythmTimeBlock     日时间线块（plan_day 产物，plan_version 支持回滚）
- RhythmDayTemplate   基础节奏骨架模板（weekday/weekend/travel_day）
- RhythmDisciplineLog 戒律/习惯打卡日志（kept/violated/done/missed/exempt）
- RhythmEnergyProfile 精力画像（单行配置 + 能量曲线 + 业余时间区 + 三域权重）
- RhythmPolicy        节奏守护策略（protect_window/domain_cap/kind_min_freq/...）
- RhythmReview        节奏复盘快照（日评/周评，含三域投入与合规明细）

时间戳统一 naive TIMESTAMP（服务器本地时间，与 reminder 等现有模块一致）；
JSON 字段使用 sail_server.data.types.JSONB（PG 原生 / SQLite Text+JSON）。

不修改 life/reminder/finance 既有表语义，仅以外键引用：
- day_id          → life.days(id)
- timespan_id     → life.timespans(id)
- recurrence_rule_id → reminder.reminder_rules(id)（逻辑引用，不建硬外键）
- budget_id       → finance.budgets(id)（逻辑引用，不建硬外键）
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    TIMESTAMP,
    Text,
    func,
)

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm.orm_base import ORMBase


class RhythmAffair(ORMBase):
    """统一事务表

    kind（事务种类，9 类）:
        base_rhythm / precept / habit / fixed_plan / task_oneoff /
        task_maintenance / venture / buffer / generic

    双生命周期:
        一次性流: INBOX→PLANNED→SCHEDULED→DOING→DONE (+DEFERRED/CANCELED)
        长期流:   INBOX→ACTIVE⇄PAUSED→ARCHIVED (venture 可 GRADUATE→DONE)
    """

    __tablename__ = "rhythm_affairs"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    # 域: life / work / career（generic 可暂空，分拣后必填）
    domain = Column(String(16), nullable=True, index=True)
    # 事务种类（默认 generic 待分拣）
    kind = Column(String(32), nullable=False, default="generic", index=True)
    # 分类型元数据（按 kind 校验 schema，见 dto/rhythm.py）
    kind_meta = Column(JSONB, default=dict)
    # 状态机（字符串枚举，对齐 reminder 风格）
    state = Column(String(16), nullable=False, default="INBOX", index=True)
    # 重要性 1-5
    importance = Column(Integer, default=3)
    # 截止时间（task_oneoff/fixed_plan 用）
    urgency_ddl = Column(TIMESTAMP, nullable=True)
    # 单次预估精力点数（默认 10）
    energy_cost = Column(Integer, default=10)
    # 预估花费
    money_cost = Column(Numeric(12, 2), default=0)
    # 关联 finance 预算（逻辑引用）
    budget_id = Column(Integer, nullable=True)
    # 单次预估时长（分钟）
    est_minutes = Column(Integer, default=30)
    # 弹性窗口：可排程区间
    window_start = Column(TIMESTAMP, nullable=True)
    window_end = Column(TIMESTAMP, nullable=True)
    # 是否可拆分
    splittable = Column(Boolean, default=False)
    # 最小连续块（拆分约束，分钟）
    min_chunk_minutes = Column(Integer, default=30)
    # 备用方案（Plan B 文字描述）
    fallback_plan = Column(Text, default="")
    # 关联 reminder.rules（周期提醒复用 reminder cron 基础设施，逻辑引用）
    recurrence_rule_id = Column(Integer, nullable=True)
    # 目标日锚点（一次性事务用）
    day_id = Column(Integer, ForeignKey("days.id"), nullable=True, index=True)
    # venture 挂靠的目标 TimeSpan（季度/双周）
    timespan_id = Column(Integer, ForeignKey("timespans.id"), nullable=True)
    # 拆分树/里程碑链/行程段（自引用）
    parent_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=True)
    # 信息收集类型：weight / meal / exercise / medication / sleep / mood
    # 用于健康速记等场景，与 kind 正交，仅作元数据标记
    info_collection_type = Column(String(32), nullable=True, index=True)
    # AI 建议快照（含 kind 分拣建议、kind_meta 草案、理由、置信度）
    ai_hint = Column(JSONB, default=dict)
    # 最近一次优先级评分（冗余，便于排序）
    score = Column(Numeric(10, 4), default=0)
    # 扩展字段
    ref = Column(JSONB, default=dict)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmTimeBlock(ORMBase):
    """日时间线块"""

    __tablename__ = "rhythm_time_blocks"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False, index=True)
    # 关联事务；buffer/micro_rest/sleep 块可空
    affair_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=True, index=True)
    # sleep/commute/work_window/micro_rest/meal/precept/habit/fixed/focus/light/career/rest/buffer
    block_type = Column(String(16), nullable=False, index=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    # PLANNED/DOING/DONE/SKIPPED/MOVED
    status = Column(String(16), nullable=False, default="PLANNED", index=True)
    # 刚性钉标记（fixed_plan/base_rhythm 骨架块为 true，rebalance 不动）
    pinned = Column(Boolean, default=False)
    # 所属计划版本（再平衡时 +1，支持方案对比与回滚）
    plan_version = Column(Integer, default=1, index=True)
    # 扩展：{"plan_b_of": block_id, "micro_cycle": 1, "overtime": true, "label": "通勤"}
    ref = Column(JSONB, default=dict)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmDayTemplate(ORMBase):
    """基础节奏骨架模板"""

    __tablename__ = "rhythm_day_templates"

    id = Column(Integer, primary_key=True)
    # 模板名：weekday / weekend / travel_day ...
    name = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(Text, default="")
    # 适用星期 [1,1,1,1,1,0,0]（周一为索引 0）
    weekday_mask = Column(JSONB, default=list)
    # 骨架槽位:
    # [{"label":"通勤","start":"08:20","end":"09:00","block_type":"commute"},
    #  {"label":"上午工作窗","start":"09:00","end":"12:00","block_type":"work_window",
    #   "micro_cycle":{"work_min":90,"rest_min":15}}, ...]
    slots = Column(JSONB, default=list)
    enabled = Column(Boolean, default=True)
    # 多模板冲突时按 priority 取高
    priority = Column(Integer, default=0)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmDisciplineLog(ORMBase):
    """戒律/习惯打卡日志"""

    __tablename__ = "rhythm_discipline_logs"

    id = Column(Integer, primary_key=True)
    affair_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=False, index=True)
    # 归属日
    log_date = Column(Date, nullable=False, index=True)
    # 周期键: daily → 2026-10-26; weekly → W2026-44（对齐 TimeSpan WEEK 名）
    cycle_key = Column(String(32), nullable=False, index=True)
    # precept: kept/violated/exempt; habit: done/missed/exempt
    result = Column(String(16), nullable=False)
    # 备注（破戒原因等，供 AI 复盘归因）
    note = Column(Text, default="")
    # manual（人打卡）/ agent（AI 代记待确认）/ auto（块完成联动）
    source = Column(String(16), default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class RhythmEnergyProfile(ORMBase):
    """精力画像（单行配置 + 曲线模板）"""

    __tablename__ = "rhythm_energy_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True, default="default")
    # 每日精力总点（默认 100）
    daily_energy_budget = Column(Integer, default=100)
    # 24 段能量系数（0.0-1.0），区分 weekday/weekend 两套:
    # {"weekday": [0.5, ...24], "weekend": [...]}
    curve_template = Column(JSONB, default=dict)
    # 睡眠守护窗（与 precept 睡眠戒律联动）
    sleep_start = Column(String(8), default="23:30")
    sleep_end = Column(String(8), default="07:00")
    # 每日工作时长上限（小时）
    work_hours_cap = Column(Numeric(4, 1), default=8.0)
    # 业余时间区（venture 专用）:
    # {"weekday":[["19:30","22:30"]],"weekend":[["09:00","12:00"],["14:00","18:00"]]}
    spare_time_windows = Column(JSONB, default=dict)
    # 强制缓冲占比（默认 0.15）
    min_buffer_ratio = Column(Numeric(4, 3), default=0.15)
    # 三域节奏权重（用户可调）
    life_weight = Column(Numeric(4, 2), default=1.0)
    work_weight = Column(Numeric(4, 2), default=1.0)
    career_weight = Column(Numeric(4, 2), default=0.6)
    # 评分权重（w_i/w_u/w_b/w_e/w_s，见 planner §5.1）
    score_weights = Column(JSONB, default=dict)
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmPolicy(ORMBase):
    """节奏守护策略（可多条、可启停）"""

    __tablename__ = "rhythm_policies"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False)
    enabled = Column(Boolean, default=True)
    # protect_window / domain_cap / kind_min_freq / max_consecutive_focus / spare_time_guard
    rule_type = Column(String(32), nullable=False, index=True)
    # 参数: {"domain":"work","hours":8} / {"kind":"habit","min_count":3} ...
    params = Column(JSONB, default=dict)
    # day / week
    scope = Column(String(8), default="day")
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmReview(ORMBase):
    """节奏复盘快照"""

    __tablename__ = "rhythm_reviews"

    id = Column(Integer, primary_key=True)
    # day / week
    scope = Column(String(8), nullable=False, index=True)
    # 2026-10-26 / W2026-44
    period_key = Column(String(32), nullable=False, index=True)
    # 综合节奏分 0-100
    rhythm_score = Column(Numeric(6, 2), default=0)
    # 三域实际投入分钟数 {"life": x, "work": y, "career": z}
    domain_minutes = Column(JSONB, default=dict)
    # 戒律合规率 = kept/(kept+violated)
    precept_compliance_rate = Column(Numeric(5, 4), default=0)
    # 习惯达标率（各 ACTIVE habit 本周完成/频率目标 的均值，封顶 1.0）
    habit_consistency = Column(Numeric(5, 4), default=0)
    # 睡眠窗守约率
    sleep_window_keeping = Column(Numeric(5, 4), default=0)
    # 事业周预算达成率（封顶 1.2）
    venture_budget_fulfillment = Column(Numeric(5, 4), default=0)
    # 缓冲被吃掉的比例
    buffer_consumed = Column(Numeric(5, 4), default=0)
    # 侵占事件数组
    encroachments = Column(JSONB, default=list)
    # Agent 生成的周评语
    ai_summary = Column(Text, default="")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
