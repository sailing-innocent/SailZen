# -*- coding: utf-8 -*-
# @file rhythm.py
# @brief Rhythm v2 ORM Models (极简项目/事务、AI 可视化时间线与轻量打卡)
# @author sailing-innocent
# @date 2026-11-24
# @version 2.0
# ---------------------------------

"""
节奏（Rhythm v2）模块 ORM 模型

重构理念（Rhythm → SailTick 统一 Personal Agent）：
- 废弃旧版重 PM 公式排程、骨架模板（RhythmDayTemplate）、精力权重配置（RhythmEnergyProfile）、
  守护策略（RhythmPolicy）与评分快照（RhythmReview）。
- Rhythm 退居为“结构化事实源 + 日程可视化画布”，由 SailTick 智能体通过异步交流与长期记忆理解用户，
  直接调度 Rhythm API 灵活编排时间线与项目倒排推进。

保留 3 张极简核心表：
- RhythmAffair        项目 / 任务 / 习惯 / 刚性安排表
- RhythmTimeBlock     日可视化时间线画布（SailTick AI 自主落库，plan_version 版本可回溯）
- RhythmDisciplineLog 轻量打卡日志（习惯 & 健康计划连续打卡兼容）
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

from sailzen_orm.orm_base import ORMBase
from sailzen_orm.types import JSONB


class RhythmAffair(ORMBase):
    """极简项目 / 任务 / 习惯 / 刚性安排表。

    常用 kind:
        venture          长期/重要项目（支持目标日倒排 + 里程碑子事务）
        task_oneoff      一次性任务
        fixed_plan       刚性固定安排（不可随意挪动）
        habit            周期习惯（轻量打卡）
        precept          长期戒律（轻量打卡）
        task_maintenance 周期维护任务
        generic          一句话随手记（可随时由 SailTick 整理归类）
    """

    __tablename__ = "rhythm_affairs"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    # 域: life / work / career
    domain = Column(String(16), nullable=True, index=True)
    # 事务种类
    kind = Column(String(32), nullable=False, default="task_oneoff", index=True)
    # 扩展元数据（venture.target_date / habit.freq_per_week / fixed_plan.fixed_start 等）
    kind_meta = Column(JSONB, default=dict)
    # 状态: INBOX / PLANNED / SCHEDULED / DOING / DONE / DEFERRED / CANCELED / ACTIVE / PAUSED / ARCHIVED
    state = Column(String(16), nullable=False, default="PLANNED", index=True)
    # 重要度 1-5（可选参考，不再由人工频繁调权重）
    importance = Column(Integer, default=3)
    # 截止/目标时间
    urgency_ddl = Column(TIMESTAMP, nullable=True)
    # 预估精力点数（可选参考）
    energy_cost = Column(Integer, default=10)
    # 预估花费（可选）
    money_cost = Column(Numeric(12, 2), default=0)
    # 关联 finance 预算（逻辑引用）
    budget_id = Column(Integer, nullable=True)
    # 单次预估时长（分钟）
    est_minutes = Column(Integer, default=30)
    # 弹性起止窗口（可选）
    window_start = Column(TIMESTAMP, nullable=True)
    window_end = Column(TIMESTAMP, nullable=True)
    splittable = Column(Boolean, default=False)
    min_chunk_minutes = Column(Integer, default=30)
    fallback_plan = Column(Text, default="")
    recurrence_rule_id = Column(Integer, nullable=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=True, index=True)
    timespan_id = Column(Integer, ForeignKey("timespans.id"), nullable=True)
    # 项目里程碑/子任务父引用
    parent_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=True)
    # 健康速记标记（weight / meal / exercise / medication / sleep / mood / energy）
    info_collection_type = Column(String(32), nullable=True, index=True)
    # SailTick 附注或建议快照
    ai_hint = Column(JSONB, default=dict)
    score = Column(Numeric(10, 4), default=0)
    ref = Column(JSONB, default=dict)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmTimeBlock(ORMBase):
    """日可视化时间线画布块（由 SailTick 自主排程写入或用户微调）。"""

    __tablename__ = "rhythm_time_blocks"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False, index=True)
    affair_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=True, index=True)
    # focus / career / habit / fixed / occupied / light / rest / meal / sleep / commute / buffer ...
    block_type = Column(String(16), nullable=False, index=True)
    start_time = Column(TIMESTAMP, nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)
    # PLANNED / DOING / DONE / SKIPPED / MOVED
    status = Column(String(16), nullable=False, default="PLANNED", index=True)
    # 刚性钉（会议/请假/固定行程为 true，AI 重排时保留不动）
    pinned = Column(Boolean, default=False)
    # 计划版本（AI 每次重排 +1，旧 PLANNED 块归档为 MOVED）
    plan_version = Column(Integer, default=1, index=True)
    # 扩展：{"label": "...", "source": "sailtick"|"manual"|"occupancy_api", "note": "...", "ai_rationale": "..."}
    ref = Column(JSONB, default=dict)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class RhythmDisciplineLog(ORMBase):
    """轻量打卡日志（习惯与健康计划连续打卡记录）。"""

    __tablename__ = "rhythm_discipline_logs"

    id = Column(Integer, primary_key=True)
    affair_id = Column(Integer, ForeignKey("rhythm_affairs.id"), nullable=False, index=True)
    log_date = Column(Date, nullable=False, index=True)
    cycle_key = Column(String(32), nullable=False, index=True)
    result = Column(String(16), nullable=False)
    note = Column(Text, default="")
    source = Column(String(16), default="manual")
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
