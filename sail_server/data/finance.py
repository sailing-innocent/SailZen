# -*- coding: utf-8 -*-
# @file finance.py
# @brief The Finance Data Model - Utilities and Enums
# @author sailing-innocent
# @date 2025-04-21
# @version 3.0
# ---------------------------------

"""
财务模块工具函数和枚举

注意：
- ORM 类已迁移到 sail_server.infrastructure.orm.finance
- DTOs 已迁移到 sail_server.application.dto.finance
"""

from datetime import datetime
from enum import IntEnum
from typing import Iterator, List

from sail_server.utils.money import Money
from sail_server.utils.state import StateBits

__all__ = [
    # Enums
    "BudgetDirection",
    "ItemType",
    "ItemStatus",
    # State classes
    "AccountState",
    "TransactionState",
    # Utility functions
    "_acc",
    "_acc_inv",
    "_htime",
    "_htime_inv",
    "transactions_money_iter",
]


# ------------------------------------
# Utility Functions
# ------------------------------------
def _acc(x):
    return x if x != -1 else None


def _acc_inv(x):
    return x if x is not None else -1


def _htime(x: float):
    try:
        return datetime.fromtimestamp(x) if x is not None else None
    except (ValueError, OSError):
        return None


def _htime_inv(x: datetime):
    if x is None:
        return None
    try:
        return x.timestamp()
    except (ValueError, OSError):
        return None


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
# Iterator Functions
# ------------------------------------
def transactions_money_iter(transactions: List) -> Iterator[Money]:
    """将交易列表转换为 Money 迭代器"""
    for transaction in transactions:
        if transaction.from_acc_id != -1:
            yield Money(transaction.value)
        else:
            yield -Money(transaction.value)
