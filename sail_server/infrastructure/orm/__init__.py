# -*- coding: utf-8 -*-
# @file __init__.py
# @brief ORM Models Package
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
SQLAlchemy ORM 模型包

"""

from sail_server.infrastructure.orm.orm_base import ORMBase

# Analysis Models
from sail_server.infrastructure.orm.analysis import (
    Outline, OutlineNode, OutlineEvent,
    Character, CharacterAlias, CharacterAttribute, CharacterArc, CharacterRelation,
    Setting, SettingAttribute, SettingRelation, CharacterSettingLink,
    TextEvidence,
    AnalysisTask, AnalysisResult,
)

# Health Models
from sail_server.infrastructure.orm.health import (
    Weight, BodySize, Exercise, WeightPlan,
)

# Text Models
from sail_server.infrastructure.orm.text import (
    Work, Edition, DocumentNode, IngestJob,
)

# Project Models
from sail_server.infrastructure.orm.project import (
    Project, Mission,
)

# Necessity Models
from sail_server.infrastructure.orm.necessity import (
    ResidenceType, ContainerType, ItemType, ItemState,
    JourneyStatus, JourneyItemStatus, ReplenishmentSource,
    Residence, Container, ItemCategory, Item, Inventory,
    Journey, JourneyItem, Consumption, Replenishment,
)

# History Models
from sail_server.infrastructure.orm.history import (
    HistoryEvent,
)

# Life Models
from sail_server.infrastructure.orm.life import (
    ServiceAccount,
)

# Finance Models
from sail_server.infrastructure.orm.finance import (
    Account, Transaction, Budget, BudgetItem,
)

# Unified Agent Models
from sail_server.infrastructure.orm.unified_agent import (
    UnifiedAgentTask, UnifiedAgentStep, UnifiedAgentEvent,
)

__all__ = [
    # Base
    "ORMBase",
    
    # Analysis
    "Outline", "OutlineNode", "OutlineEvent",
    "Character", "CharacterAlias", "CharacterAttribute", "CharacterArc", "CharacterRelation",
    "Setting", "SettingAttribute", "SettingRelation", "CharacterSettingLink",
    "TextEvidence",
    "AnalysisTask", "AnalysisResult",
    
    # Health
    "Weight", "BodySize", "Exercise", "WeightPlan",
    
    # Text
    "Work", "Edition", "DocumentNode", "IngestJob",
    
    # Project
    "Project", "Mission",
    
    # Necessity Enums
    "ResidenceType", "ContainerType", "ItemType", "ItemState",
    "JourneyStatus", "JourneyItemStatus", "ReplenishmentSource",
    # Necessity Models
    "Residence", "Container", "ItemCategory", "Item", "Inventory",
    "Journey", "JourneyItem", "Consumption", "Replenishment",
    
    # History
    "HistoryEvent",
    
    # Life
    "ServiceAccount",
    
    # Finance
    "Account", "Transaction", "Budget", "BudgetItem",
    
    # Unified Agent
    "UnifiedAgentTask", "UnifiedAgentStep", "UnifiedAgentEvent",
]
