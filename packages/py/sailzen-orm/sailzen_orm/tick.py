# -*- coding: utf-8 -*-
# @file tick.py
# @brief SailTick Ticket ORM Models (SailTick 用户交互票据)
# @author sailing-innocent
# @date 2026-10-27
# @version 1.0
# ---------------------------------
"""SailTick 票据 ORM 模型。

设计文档: doc/design/agent-system/sailtick.md §6
票据是 SailTick agent 与用户异步交互的载体，存于 SailZen 主库（共享数据），
网页 / Android / 插件都经 sail_server 访问。

状态机: pending → replied → resolved; pending → expired; pending → snoozed → pending
时间戳统一 naive TIMESTAMP（服务器本地时间，与现有模型一致）。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Index,
    Integer,
    String,
    TIMESTAMP,
    func,
)

from sailzen_orm import ORMBase
from sailzen_orm.types import JSONB


class SailTickTicket(ORMBase):
    """SailTick 交互票据。"""

    __tablename__ = "sail_tick_tickets"

    id = Column(Integer, primary_key=True)
    # 归属用户 ID（逻辑引用 user_profiles.id，默认单用户 owner=1）
    user_id = Column(Integer, default=1, index=True)
    # 关联统一收件箱条目 ID（逻辑引用 user_inbox_items.id）
    inbox_item_id = Column(Integer, nullable=True, index=True)
    # 创建它的 tick 实例（sailtick.db st_ticks.id，仅作追溯，无外键约束跨库不可行）
    tick_id = Column(String, default="", index=True)
    # question | task | approval | info
    type = Column(String, default="question", index=True)
    # 业务域分流：health | rhythm | finance | general
    domain = Column(String(32), default="general", index=True)
    # 交互角色：health_coach | rhythm_planner | finance_secretary | chief_steward
    persona = Column(String(32), default="")
    # 目标终端过滤列表：["android", "web", "vscode"]（空表示全端）
    target_clients = Column(JSONB, default=list)
    # 精确落地页深链（如 /plan?ticket=12 / /health/coach?ticket=12 / /money?ticket=12）
    deep_link = Column(String(128), default="")
    # 话题标识，用于防重复轰炸与冷却控制（如 profile_wake_time / diet_lunch / weight_checkin）
    topic = Column(String, default="", index=True)
    title = Column(String, nullable=False)
    body = Column(String, default="")
    # 扩展元信息（如 quick_replies / target_profile_key / report_date）
    meta = Column(JSONB, default=dict)
    # pending | replied | resolved | expired | snoozed
    status = Column(String, default="pending", index=True)
    # 期待回复时间（超期 → expired，AI 采用 fallback 假设继续）
    expected_reply_by = Column(TIMESTAMP, nullable=True)
    replied_at = Column(TIMESTAMP, nullable=True)
    reply = Column(String, nullable=True)
    resolved_at = Column(TIMESTAMP, nullable=True)
    resolution = Column(String, nullable=True)
    # 超期后 AI 采用的假设
    fallback_assumption = Column(String, default="")
    # low | normal | high | urgent
    priority = Column(String, default="normal", index=True)
    # web | mobile | plugin
    channel = Column(String, default="web")
    # 创建时是否请求推送（agent 侧已做安静时段判断；urgent 强制推送）
    push = Column(String, default="auto")  # auto | force | none
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        # SCAN 同步用：pending 按期待回复时间排序
        Index("ix_tick_tickets_status_expected", "status", "expected_reply_by"),
        Index("ix_tick_tickets_status_updated", "status", "updated_at"),
        Index("ix_tick_tickets_domain_status", "domain", "status"),
    )


class SailTickMessage(ORMBase):
    """用户与 SailTick 之间的异步轻量消息（支持用户主动发餐饮/日常信息，无需 AI 立即回复）。"""

    __tablename__ = "sail_tick_messages"

    id = Column(Integer, primary_key=True)
    # 归属用户 ID（逻辑引用 user_profiles.id，默认单用户 owner=1）
    user_id = Column(Integer, default=1, index=True)
    # user_to_agent | agent_to_user
    direction = Column(String, default="user_to_agent", index=True)
    # diet | weight | daily_info | mood | exercise | general
    category = Column(String, default="diet", index=True)
    # 业务域：health | rhythm | finance | general
    domain = Column(String(32), default="general", index=True)
    # 来源页面：android_health | android_plan | android_money | web_rhythm | vscode_workbench
    surface = Column(String(32), default="")
    content = Column(String, nullable=False)
    # 结构化元信息（如 meal_type, htime, linked_diet_id, extracted_calories 等）
    meta = Column(JSONB, default=dict)
    # android | web | sailtick
    source_channel = Column(String, default="android")
    # unread | ingested | archived
    status = Column(String, default="unread", index=True)
    ingested_by_tick_id = Column(String, nullable=True)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp(), index=True
    )
    ingested_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("ix_tick_messages_status_created", "status", "created_at"),
    )


class SailTickDailyReport(ORMBase):
    """SailTick 每日睡前体重与健康日报（存于主库供 Web/Android 健康页直接展示）。"""

    __tablename__ = "sail_tick_daily_reports"

    id = Column(Integer, primary_key=True)
    # YYYY-MM-DD（每天一份，重复生成则幂等 upsert 更新）
    report_date = Column(String, unique=True, nullable=False, index=True)
    tick_id = Column(String, default="")
    title = Column(String, nullable=False)
    # 一句话精炼摘要（推送通知正文 + 健康页卡片首屏展示）
    summary = Column(String, default="")
    # 完整 Markdown 日报正文
    body_markdown = Column(String, default="")
    # 分域结构化分节：{"health": {...}, "rhythm": {...}, "finance": {...}, "chief": {...}}
    sections = Column(JSONB, default=dict)
    # 结构化快照：最新体重、7日均值、环比变化、目标差距等
    weight_snapshot = Column(JSONB, default=dict)
    # 当日餐饮整合摘要：已记录餐次、条目摘要、结构亮点
    diet_summary = Column(JSONB, default=dict)
    # 动态计划状态/调整说明：版本、阶段名、调整理由、关注点
    plan_update = Column(JSONB, default=dict)
    # 明日 1-3 条轻量可执行建议
    tomorrow_focus = Column(JSONB, default=list)
    pushed = Column(Boolean, default=False)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class SailTickIntakeDraft(ORMBase):
    """SailTick 通用视觉识图草稿（传图 → AI 识图拆解 → 人工确认微调 → 结构化落库）。"""

    __tablename__ = "sail_tick_intake_drafts"

    id = Column(Integer, primary_key=True)
    # pending_confirm | committed | discarded
    status = Column(String, default="pending_confirm", index=True)
    # web | android | android_share
    source_channel = Column(String, default="android")
    # 可选关联票据 ID（从某张待回票据发起“传图回复”时写入）
    ticket_id = Column(Integer, nullable=True, index=True)
    # 媒体存储相对键，如 2026-11/20261123_221500_ab12cd34.jpg
    media_key = Column(String, nullable=False)
    media_mime = Column(String, default="image/jpeg")
    media_size = Column(Integer, default=0)
    original_filename = Column(String, default="")
    # 用户上传时附带的简短备注（可选）
    user_note = Column(String, default="")
    # AI 判定的主场景：diet | canteen_menu | sleep | exercise | weight | selfie_status | general
    scene = Column(String, default="general", index=True)
    # AI 一句话识别总结
    summary = Column(String, default="")
    # AI 即时轻量建议（如食堂点餐推荐、睡眠/气色温和提示）
    coach_advice = Column(String, default="")
    # 可选：触发 /v1/tools/ocr 辅助时保存的原始识别文本
    ocr_text = Column(String, default="")
    # 结构化可编辑候选条目数组：[{"selected": true, "kind": "diet", "title": "...", "confidence": 0.9, "data": {...}}]
    entries = Column(JSONB, default=list)
    # 确认落库后写入的关联记录引用：[{"kind": "diet", "id": 12}, {"kind": "message", "id": 34}]
    committed_refs = Column(JSONB, default=list)
    model_used = Column(String, default="deepseek-flash")
    usage = Column(JSONB, default=dict)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp(), index=True
    )
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    committed_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("ix_tick_intake_drafts_status_created", "status", "created_at"),
    )


class VaultJournalDigest(ORMBase):
    """本地 Dendron/Vault 日记的云端轻量只读上下文摘要（The Bridge）。

    原则：Notes are notes. Databases are databases. The Agent is the bridge.
    主笔记仍保存在本地 Git/Vault 中，云端仅缓存去重后的脱敏摘要与行为信号，
    供 SailTick 关联差旅/情绪/大额消费背景。
    """

    __tablename__ = "vault_journal_digests"

    id = Column(Integer, primary_key=True)
    # YYYY-MM-DD（每天一条，按 content_hash 幂等增量更新）
    note_date = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, default="")
    title = Column(String, default="")
    summary = Column(String, default="")
    excerpt = Column(String, default="")
    mood_hints = Column(JSONB, default=list)
    travel_hints = Column(JSONB, default=list)
    spend_context_hints = Column(JSONB, default=list)
    tags = Column(JSONB, default=list)
    content_hash = Column(String, default="", index=True)
    source_vault = Column(String, default="local")
    synced_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
    updated_at = Column(
        TIMESTAMP,
        default=datetime.now,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    __table_args__ = (
        Index("ix_vault_journal_digests_date", "note_date"),
    )
