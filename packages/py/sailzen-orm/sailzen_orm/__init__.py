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

# Reminder Models
from sailzen_orm.reminder import (
    Reminder,
    ReminderEvent,
    ReminderRule,
    Device,
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
)

# Rhythm Models
from sailzen_orm.rhythm import (
    RhythmAffair,
    RhythmTimeBlock,
    RhythmDayTemplate,
    RhythmDisciplineLog,
    RhythmEnergyProfile,
    RhythmPolicy,
    RhythmReview,
)

__all__ = [
    # Base
    "ORMBase",
    # Reminder
    "Reminder",
    "ReminderEvent",
    "ReminderRule",
    "Device",
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
    # Rhythm
    "RhythmAffair",
    "RhythmTimeBlock",
    "RhythmDayTemplate",
    "RhythmDisciplineLog",
    "RhythmEnergyProfile",
    "RhythmPolicy",
    "RhythmReview",
]
