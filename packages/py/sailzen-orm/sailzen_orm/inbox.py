# -*- coding: utf-8 -*-
# @file inbox.py
# @brief UserInbox ORM Models (统一多端收件箱与单调游标同步)
# @author sailing-innocent
# @date 2026-11-24
# @version 1.0
# ---------------------------------
"""统一用户收件箱 ORM 模型。

所有面向用户的跨端消息（SailTick 提问/日报、Rhythm 提醒、Health 打卡提醒、
系统/业务通知）统一投影到 user_inbox_items，通过单调递增的 sync_seq 支持
Android / Web / CLI 多端增量同步、终态对账与实时撤回。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text,
    func,
)

from sailzen_orm import ORMBase
from sailzen_orm.types import JSONB


class UserInboxItem(ORMBase):
    """统一用户收件箱条目（全端唯一权威交互视图）。"""

    __tablename__ = "user_inbox_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 逻辑引用 user_profiles.id（避免破坏独立单测 SQLite 表顺序）
    user_id = Column(Integer, nullable=False, default=1, index=True)
    # 每次状态/内容变更严格递增，支持多端 since_seq 增量对账与终态撤回
    sync_seq = Column(BigInteger, nullable=False, default=0, index=True)
    # 来源域：sailtick | rhythm | health | finance | system | manual
    source_domain = Column(String(32), nullable=False, default="system", index=True)
    # 条目类型：question | action_reminder | report | approval | notice
    item_kind = Column(String(32), nullable=False, default="notice", index=True)
    # 语义话题键（如 diet_lunch / weight_checkin / daily_report）
    topic = Column(String(128), nullable=False, default="", index=True)
    # 去重幂等键（同 user 同 dedup_key 活跃条目自动合并）
    dedup_key = Column(String(191), nullable=False, default="", index=True)
    # 关联源实体类型与主键：tick_ticket | reminder | tick_daily_report | rhythm_affair | none
    ref_type = Column(String(64), nullable=False, default="")
    ref_id = Column(Integer, nullable=True)
    # 冗余保存关联提醒 ID / 票据 ID，便于 Android 通知栏精确撤回与跨端直达
    reminder_id = Column(Integer, nullable=True, index=True)
    ticket_id = Column(Integer, nullable=True, index=True)

    title = Column(String(255), nullable=False)
    body = Column(Text, default="")
    # low | normal | high | urgent
    priority = Column(String(16), nullable=False, default="normal", index=True)
    # 活跃态：pending | delivered | snoozed | opened
    # 终态：  answered | resolved | dismissed | expired | canceled
    status = Column(String(24), nullable=False, default="delivered", index=True)

    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(TIMESTAMP, nullable=True)

    # 声明式交互协议：quick_replies / allow_text_reply / allow_image_reply /
    # deep_link / auto_resolve_signals / payload
    action_schema = Column(JSONB, default=dict)

    # 消解/回复上下文
    reply_text = Column(Text, nullable=True)
    resolution_source = Column(String(64), nullable=False, default="")
    resolution_summary = Column(String(500), nullable=False, default="")
    resolution_ref = Column(JSONB, default=dict)

    trigger_at = Column(TIMESTAMP, nullable=True, index=True)
    snooze_until = Column(TIMESTAMP, nullable=True)
    expires_at = Column(TIMESTAMP, nullable=True)
    delivered_at = Column(TIMESTAMP, nullable=True)
    resolved_at = Column(TIMESTAMP, nullable=True)
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
        Index("ix_inbox_user_seq", "user_id", "sync_seq"),
        Index("ix_inbox_user_status_updated", "user_id", "status", "updated_at"),
        Index("ix_inbox_user_dedup_status", "user_id", "dedup_key", "status"),
        Index("ix_inbox_ref", "ref_type", "ref_id"),
    )


class UserInboxEvent(ORMBase):
    """收件箱生命周期不可变事件流（审计 + Agent 习惯学习）。"""

    __tablename__ = "user_inbox_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inbox_item_id = Column(
        Integer,
        ForeignKey("user_inbox_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, nullable=False, default=1, index=True)
    # created | delivered | read | opened | snoozed | answered |
    # auto_resolved | resolved | dismissed | expired | canceled
    event = Column(String(32), nullable=False, index=True)
    # android | web | sailtick | cli | qq_bot | system
    actor_client = Column(String(32), nullable=False, default="system")
    device_id = Column(String(128), nullable=False, default="")
    detail = Column(JSONB, default=dict)
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )
