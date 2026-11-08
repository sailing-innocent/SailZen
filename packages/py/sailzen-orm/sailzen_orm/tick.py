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
    Column,
    Index,
    Integer,
    String,
    TIMESTAMP,
    func,
)

from sailzen_orm import ORMBase


class SailTickTicket(ORMBase):
    """SailTick 交互票据。"""

    __tablename__ = "sail_tick_tickets"

    id = Column(Integer, primary_key=True)
    # 创建它的 tick 实例（sailtick.db st_ticks.id，仅作追溯，无外键约束跨库不可行）
    tick_id = Column(String, default="", index=True)
    # question | task | approval | info
    type = Column(String, default="question", index=True)
    title = Column(String, nullable=False)
    body = Column(String, default="")
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
    )
