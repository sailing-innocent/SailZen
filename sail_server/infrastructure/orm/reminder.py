# -*- coding: utf-8 -*-
# @file reminder.py
# @brief Reminder ORM Models (Android App M1 提醒闭环)
# @author sailing-innocent
# @date 2026-08-03
# @version 1.0
# ---------------------------------

"""
提醒模块 ORM 模型

对应设计文档 doc/design/android_app/README.md §2.1 概念模型：

- Reminder       一条待触达的提醒（状态机见 model/reminder.py）
- ReminderEvent  提醒生命周期事件日志（不可变，仅追加）
- ReminderRule   某类提醒的行为策略（重试/安静时段/降频档位）
- Device         注册的 App 设备（长连接寻址与投递确认）

时间戳统一 naive TIMESTAMP（服务器本地时间，与现有模型一致）；
JSON 字段使用 sail_server.data.types.JSONB（PG 原生 / SQLite Text+JSON）。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    TIMESTAMP,
    func,
)

from sail_server.data.types import JSONB
from sail_server.infrastructure.orm import ORMBase


class Reminder(ORMBase):
    """提醒本体"""

    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    # 提醒类型：attendance.checkin / diet.log / mission.due / agent.message / test.ping ...
    type = Column(String, index=True)
    title = Column(String)
    body = Column(String, default="")
    # 优先级：low | normal | high | urgent
    priority = Column(String, default="normal")
    # 来源：schedule | agent | business | geofence | manual
    source = Column(String, default="manual")
    # 状态机：PENDING / DELIVERED / SNOOZED / OPENED /
    #         RESOLVED(终) / IGNORED(终) / EXPIRED / CANCELED(终) / ARCHIVED(终)
    state = Column(String, default="PENDING", index=True)
    trigger_time = Column(TIMESTAMP, index=True)
    expire_after_minutes = Column(Integer, default=240)
    snooze_count = Column(Integer, default=0)
    # EXPIRED 重投已用次数（消费 rule.retry_policy.max_retry）
    retry_count = Column(Integer, default=0)
    # SNOOZED 到点时间
    next_trigger_time = Column(TIMESTAMP, nullable=True)
    # 最近一次投递时间（EXPIRED / OPENED 回落判定依据）
    last_delivered_at = Column(TIMESTAMP, nullable=True)
    # 业务负载：{"mission_id": 3} / {"meal_type": "lunch"} ...
    payload = Column(JSONB, default=dict)
    rule_id = Column(Integer, ForeignKey("reminder_rules.id"), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class ReminderEvent(ORMBase):
    """提醒生命周期事件日志（不可变，仅追加）"""

    __tablename__ = "reminder_events"

    id = Column(Integer, primary_key=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), index=True)
    # created | delivered | redelivered | ack | snoozed | opened |
    # resolved | dismissed | expired | escalated | canceled
    event = Column(String)
    detail = Column(JSONB, default=dict)
    # 客户端实际发生时间（离线补偿），naive 本地时间
    client_event_ts = Column(TIMESTAMP, nullable=True)
    # 服务端收到时间（ORM 插入走 Python 侧 naive local，对齐模块时间口径；
    # server_default 仅为裸 SQL 兼容——SQLite CURRENT_TIMESTAMP 是 UTC 会导致口径偏差）
    created_at = Column(
        TIMESTAMP, default=datetime.now, server_default=func.current_timestamp()
    )


class ReminderRule(ORMBase):
    """提醒规则（M1 仅建表 + CRUD + retry_policy 消费，cron 生成不在 M1）"""

    __tablename__ = "reminder_rules"

    id = Column(Integer, primary_key=True)
    type = Column(String, index=True)
    # schedule 来源的周期表达式（M1 仅存储不消费）
    cron = Column(String, nullable=True)
    enabled = Column(Boolean, default=True)
    priority = Column(String, default="normal")
    # {"max_retry": 2, "retry_interval_minutes": 60}
    retry_policy = Column(JSONB, default=dict)
    # 类型级安静时段覆盖（M1 存储不消费）
    quiet_hours = Column(JSONB, nullable=True)
    # 习惯学习降频档位（M4 用）
    frequency_level = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Device(ORMBase):
    """注册的 App 设备"""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    # App 端 UUID（DataStore 持久）
    device_id = Column(String, unique=True, index=True)
    device_name = Column(String, default="")
    platform = Column(String, default="android")
    app_version = Column(String, default="")
    # 预留（FCM 等），M1 不使用
    push_token = Column(String, nullable=True)
    last_seen_at = Column(TIMESTAMP, server_default=func.current_timestamp())
