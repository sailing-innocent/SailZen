# -*- coding: utf-8 -*-
# @file __init__.py
# @brief DAO Package
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
数据访问对象 (DAO) 包

Phase 4 重构目标：将数据访问逻辑从 Model 层提取到 DAO 层

设计原则:
1. DAO 只负责数据库 CRUD 操作
2. DAO 返回 ORM 对象或原始数据
3. 业务逻辑保留在 Model/Service 层
4. 支持依赖注入

当前迁移状态：
- [x] analysis 模块
- [x] finance 模块
- [x] health 模块
- [x] history 模块
- [x] life 模块
- [x] necessity 模块
- [x] project 模块
- [x] text 模块
- [x] unified_agent 模块
"""

from .base import BaseDAO

# Analysis
from .analysis import (
    CharacterDAO, CharacterAliasDAO, CharacterAttributeDAO,
    OutlineDAO, OutlineNodeDAO, OutlineEventDAO,
    SettingDAO, SettingAttributeDAO,
    TextEvidenceDAO,
)

# Finance
from .finance import AccountDAO, TransactionDAO, BudgetDAO, BudgetItemDAO

# Health
from .health import WeightDAO, BodySizeDAO, ExerciseDAO, WeightPlanDAO

# Text
from .text import WorkDAO, EditionDAO, DocumentNodeDAO, IngestJobDAO

# Project
from .project import ProjectDAO, MissionDAO

# Necessity
from .necessity import (
    ResidenceDAO, ContainerDAO, ItemCategoryDAO, ItemDAO,
    InventoryDAO, JourneyDAO, JourneyItemDAO,
)

# History
from .history import HistoryEventDAO

# Life
from .life import ServiceAccountDAO

# Unified Agent
from .unified_agent import (
    UnifiedAgentTaskDAO, UnifiedAgentStepDAO, UnifiedAgentEventDAO
)

__all__ = [
    "BaseDAO",
    # Analysis
    "CharacterDAO", "CharacterAliasDAO", "CharacterAttributeDAO",
    "OutlineDAO", "OutlineNodeDAO", "OutlineEventDAO",
    "SettingDAO", "SettingAttributeDAO",
    "TextEvidenceDAO",
    # Finance
    "AccountDAO", "TransactionDAO", "BudgetDAO", "BudgetItemDAO",
    # Health
    "WeightDAO", "BodySizeDAO", "ExerciseDAO", "WeightPlanDAO",
    # Text
    "WorkDAO", "EditionDAO", "DocumentNodeDAO", "IngestJobDAO",
    # Project
    "ProjectDAO", "MissionDAO",
    # Necessity
    "ResidenceDAO", "ContainerDAO", "ItemCategoryDAO",
    "ItemDAO", "InventoryDAO", "JourneyDAO", "JourneyItemDAO",
    # History
    "HistoryEventDAO",
    # Life
    "ServiceAccountDAO",
    # Unified Agent
    "UnifiedAgentTaskDAO", "UnifiedAgentStepDAO", "UnifiedAgentEventDAO",
]
