# -*- coding: utf-8 -*-
# @file finance_helpers.py
# @brief Finance utility functions for data conversion and iteration
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------
"""
财务模块工具函数

包含用于财务数据处理的工具函数：
- 账户ID转换 (_acc, _acc_inv)
- 时间戳转换 (_htime, _htime_inv)
- 交易金额迭代器 (transactions_money_iter)
"""

from datetime import datetime
from typing import Iterator, List

from sail_server.utils.money import Money


def _acc(x):
    """将 -1 转换为 None（用于数据库中的可选账户ID）"""
    return x if x != -1 else None


def _acc_inv(x):
    """将 None 转换为 -1（用于数据库中的可选账户ID）"""
    return x if x is not None else -1


def _htime(x: float):
    """将时间戳转换为 datetime 对象"""
    try:
        return datetime.fromtimestamp(x) if x is not None else None
    except (ValueError, OSError):
        return None


def _htime_inv(x: datetime):
    """将 datetime 对象转换为时间戳"""
    if x is None:
        return None
    try:
        return x.timestamp()
    except (ValueError, OSError):
        return None


def transactions_money_iter(transactions: List) -> Iterator[Money]:
    """将交易列表转换为 Money 迭代器
    
    根据交易方向返回正或负的 Money 值：
    - 从账户转出 (from_acc_id != -1): 返回正值
    - 转入账户 (to_acc_id != -1): 返回负值
    """
    for transaction in transactions:
        if transaction.from_acc_id != -1:
            yield Money(transaction.value)
        else:
            yield -Money(transaction.value)


__all__ = [
    "_acc",
    "_acc_inv",
    "_htime",
    "_htime_inv",
    "transactions_money_iter",
]
