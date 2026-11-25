# -*- coding: utf-8 -*-
# @file __init__.py
# @brief ORM Models Package
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
SQLAlchemy ORM 模型包（sailzen-orm）

SailZen 共享数据库结构声明层：sail_server 与 sailzen-cli 共用。
"""

from sailzen_orm.orm_base import ORMBase

# User & Unified Inbox Models
from sailzen_orm.user import UserProfile
from sailzen_orm.inbox import UserInboxItem, UserInboxEvent

# Reminder Models
from sailzen_orm.reminder import (
    Reminder,
    ReminderEvent,
    ReminderRule,
    Device,
    ReminderSourceConfig,
)

# Health Models
from sailzen_orm.health import (
    Weight,
    BodySize,
    BodyData,
    Exercise,
    WeightPlan,
    Sleep,
    EnergyLevel,
    Mood,
    HealthSignal,
    Medication,
    DietLog,
    NutritionGoal,
    SleepScheduleGoal,
)

# Text Models
from sailzen_orm.text import Work, Edition, DocumentNode, NoteItem

# Necessity Models
from sailzen_orm.necessity import (
    ResidenceType,
    ContainerType,
    ItemType,
    ItemState,
    JourneyStatus,
    JourneyItemStatus,
    ReplenishmentSource,
    Residence,
    Container,
    ItemCategory,
    Item,
    Inventory,
    Journey,
    JourneyItem,
    Consumption,
    Replenishment,
)

# History Models
from sailzen_orm.history import (
    HistoryEvent,
    Person,
)

# Life Models
from sailzen_orm.life import (
    ServiceAccount,
    Day,
    TimeSpan,
)

# Finance Models
from sailzen_orm.finance import (
    Account,
    Transaction,
    Budget,
    BudgetItem,
    FinanceTag,
    FinanceBalanceCheckpoint,
    FinanceHygieneProposal,
)

# Rhythm Models (v2 极简核心 3 表)
from sailzen_orm.rhythm import (
    RhythmAffair,
    RhythmTimeBlock,
    RhythmDisciplineLog,
)
# SailTick Models
from sailzen_orm.tick import (
    SailTickTicket,
    SailTickMessage,
    SailTickDailyReport,
    SailTickIntakeDraft,
    VaultJournalDigest,
)

# Telemetry & AI Trace Models
from sailzen_orm.telemetry import (
    SysAITrace,
    SysAITraceSpan,
    SysApiMetricBucket,
    SysTelemetryEvent,
)

__all__ = [
    # Base
    "ORMBase",
    # User & Unified Inbox
    "UserProfile",
    "UserInboxItem",
    "UserInboxEvent",
    # Reminder
    "Reminder",
    "ReminderEvent",
    "ReminderRule",
    "Device",
    "ReminderSourceConfig",
    # Health
    "Weight",
    "BodySize",
    "BodyData",
    "Exercise",
    "WeightPlan",
    "Sleep",
    "EnergyLevel",
    "Mood",
    "HealthSignal",
    "Medication",
    "DietLog",
    "NutritionGoal",
    "SleepScheduleGoal",
    # Text
    "Work",
    "Edition",
    "DocumentNode",
    "NoteItem",
    # Necessity Enums
    "ResidenceType",
    "ContainerType",
    "ItemType",
    "ItemState",
    "JourneyStatus",
    "JourneyItemStatus",
    "ReplenishmentSource",
    # Necessity Models
    "Residence",
    "Container",
    "ItemCategory",
    "Item",
    "Inventory",
    "Journey",
    "JourneyItem",
    "Consumption",
    "Replenishment",
    # History
    "HistoryEvent",
    "Person",
    # Life
    "ServiceAccount",
    "Day",
    "TimeSpan",
    # Finance
    "Account",
    "Transaction",
    "Budget",
    "BudgetItem",
    "FinanceTag",
    "FinanceBalanceCheckpoint",
    "FinanceHygieneProposal",
    # Rhythm
    "RhythmAffair",
    "RhythmTimeBlock",
    "RhythmDisciplineLog",
    # SailTick
    "SailTickTicket",
    "SailTickMessage",
    "SailTickDailyReport",
    "SailTickIntakeDraft",
    "VaultJournalDigest",
    # Telemetry & AI Trace
    "SysAITrace",
    "SysAITraceSpan",
    "SysApiMetricBucket",
    "SysTelemetryEvent",
]
