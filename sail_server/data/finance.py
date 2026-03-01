# -*- coding: utf-8 -*-
# @file finance.py
# @brief The Finance Data Model - Enums and State Classes
# @author sailing-innocent
# @date 2025-04-21
# @version 4.0
# ---------------------------------

"""
财务模块枚举和状态类

注意：
- ORM 类已迁移到 sail_server.infrastructure.orm.finance
- DTOs 已迁移到 sail_server.application.dto.finance
- 工具函数已迁移到 sail_server.utils.finance_helpers

此文件保留向后兼容的 dataclass DTOs，供 model 层内部使用。
"""

from enum import IntEnum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from sail_server.utils.state import StateBits

__all__ = [
    # Enums
    "BudgetDirection",
    "ItemType",
    "ItemStatus",
    # State classes
    "AccountState",
    "TransactionState",
    # Backward compatible dataclass DTOs (for model layer)
    "AccountData",
    "TransactionData",
    "BudgetData",
    "BudgetItemData",
]


# ------------------------------------
# Enums
# ------------------------------------
class BudgetDirection(IntEnum):
    """预算方向（收入/支出）"""
    EXPENSE = 0  # 支出
    INCOME = 1   # 收入


class ItemType(IntEnum):
    """子项金额类型"""
    FIXED = 0     # 固定金额
    PERIODIC = 1  # 周期性金额


class ItemStatus(IntEnum):
    """子项状态"""
    PENDING = 0    # 待定
    CONFIRMED = 1  # 已确认
    CANCELLED = 2  # 已取消


# ------------------------------------
# State Classes
# ------------------------------------
class AccountState(StateBits):
    """账户状态"""
    def __init__(self, value: int):
        super().__init__(value)
        self.set_attrib_map({"valid": 0, "archived": 1})


class TransactionState(StateBits):
    """交易状态"""
    def __init__(self, value: int):
        super().__init__(value)
        self.set_attrib_map({
            "from_acc_valid": 0,
            "to_acc_valid": 1,
            "from_acc_updated": 2,
            "to_acc_updated": 3,
            "from_acc_changed": 4,
            "to_acc_changed": 5,
            "from_acc_deprecated": 6,
            "to_acc_deprecated": 7,
        })


# ------------------------------------
# Backward Compatible Dataclass DTOs
# ------------------------------------
# These are kept for internal model layer use
# Controllers should use Pydantic DTOs from application.dto.finance

@dataclass
class AccountData:
    """账户数据（dataclass，供model层内部使用）"""
    id: int = -1
    name: str = ""
    description: str = ""
    balance: str = "0.0"
    state: int = 0
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    prev_value: str = "0.0"


@dataclass
class TransactionData:
    """交易数据（dataclass，供model层内部使用）"""
    id: int = -1
    from_acc_id: int = -1
    to_acc_id: int = -1
    value: str = "0.0"
    description: str = ""
    tags: str = ""
    state: int = 0
    htime: float = 0.0
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    prev_value: str = "0.0"
    budget_id: Optional[int] = None


@dataclass
class BudgetItemData:
    """预算子项数据（dataclass，供model层内部使用）"""
    id: int = -1
    budget_id: int = -1
    name: str = ""
    description: str = ""
    direction: int = 0  # 0: 支出, 1: 收入
    item_type: int = 0  # 0: 固定金额, 1: 周期性金额
    amount: str = "0.0"
    period_count: int = 1
    is_refundable: int = 0
    refund_amount: str = "0.0"
    current_period: int = 0
    status: int = 0
    due_date: Optional[datetime] = None


@dataclass
class BudgetData:
    """预算数据（dataclass，供model层内部使用）"""
    id: int = -1
    name: str = ""
    description: str = ""
    total_amount: str = "0.0"
    consumed_amount: str = "0.0"
    tags: str = ""
    start_date: float = 0.0
    end_date: float = 0.0
    htime: float = 0.0
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    items: List[BudgetItemData] = field(default_factory=list)
