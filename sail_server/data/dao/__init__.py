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
- [x] finance 模块
- [x] analysis 模块
- [ ] 其他模块
"""

from .base import BaseDAO
from .finance import AccountDAO, TransactionDAO, BudgetDAO, BudgetItemDAO
from .analysis import (
    CharacterDAO, CharacterAliasDAO, CharacterAttributeDAO,
    OutlineDAO, OutlineNodeDAO, OutlineEventDAO,
    SettingDAO, SettingAttributeDAO,
    TextEvidenceDAO,
)

__all__ = [
    "BaseDAO",
    # Finance
    "AccountDAO", "TransactionDAO", "BudgetDAO", "BudgetItemDAO",
    # Analysis
    "CharacterDAO", "CharacterAliasDAO", "CharacterAttributeDAO",
    "OutlineDAO", "OutlineNodeDAO", "OutlineEventDAO",
    "SettingDAO", "SettingAttributeDAO",
    "TextEvidenceDAO",
]
