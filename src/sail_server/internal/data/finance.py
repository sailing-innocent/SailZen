# -*- coding: utf-8 -*-
# @file finance.py
# @brief The Finance Data Model
# @author sailing-innocent
# @date 2025-04-21
# @version 1.0
# ---------------------------------

from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func
from .orm import ORMBase
from sqlalchemy.orm import relationship
import time

from utils.state import StateBits
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from utils.money import Money
from typing import List, Iterator

__all__ = [
    "Account",
    "AccountState",
    "AccountData",
    "Transaction",
    "TransactionData",
    "TransactionState",
    "_acc",
    "_acc_inv",
    "_htime",
    "_htime_inv",
    "transactions_money_iter",
]


# ------------------------------------
# Financial State
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
        # 处理无效日期或超出范围的日期
        # 可以返回一个默认值或者None
        return None


class Account(ORMBase):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    balance = Column(String)
    state = Column(Integer)  # 0: physical account 1: budget pocket
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Define relationships without circular foreign_keys
    in_transactions = relationship(
        "Transaction",
        back_populates="to_acc",
        primaryjoin="Account.id==Transaction.to_acc_id",
    )
    out_transactions = relationship(
        "Transaction",
        back_populates="from_acc",
        primaryjoin="Account.id==Transaction.from_acc_id",
    )


@dataclass
class AccountData:
    id: int = field(default=-1)
    name: str = field(default="")
    description: str = field(default="")
    balance: str = field(default=str(0.0))
    state: int = field(default_factory=lambda: AccountState(0).value)
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())


class AccountState(StateBits):
    def __init__(self, value: int):
        super().__init__(value)
        # State Machine
        self.set_attrib_map({"valid": 0, "archived": 1})

    def set_valid(self):
        self.set_attrib("valid")

    def unset_valid(self):
        self.unset_attrib("valid")

    def is_valid(self):
        return self.is_attrib("valid")

    def set_archived(self):
        self.set_attrib("archived")

    def unset_archived(self):
        self.unset_attrib("archived")

    def is_archived(self):
        return self.is_attrib("archived")


# transaction
class Transaction(ORMBase):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    from_acc_id = Column(Integer, ForeignKey("accounts.id"))
    to_acc_id = Column(Integer, ForeignKey("accounts.id"))
    # Define relationships with back_populates
    from_acc = relationship(
        "Account", back_populates="out_transactions", foreign_keys=[from_acc_id]
    )
    to_acc = relationship(
        "Account", back_populates="in_transactions", foreign_keys=[to_acc_id]
    )

    value = Column(String)  # Decimal float
    prev_value = Column(String)  # Decimal float
    description = Column(String)
    tags = Column(String)
    state = Column(Integer)  # 0: create 1: valid 2: virtual 3: done 4: cancel
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())


@dataclass
class TransactionData:
    from_acc_id: int
    to_acc_id: int
    value: str

    id: int = field(default=-1)
    prev_value: str = field(default="0.0")
    description: str = field(default="")
    tags: str = field(default="")
    state: int = field(default_factory=lambda: TransactionState(0).value)
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())

class TransactionState(StateBits):
    def __init__(self, value: int):
        super().__init__(value)
        # State Machine
        # INVALID -> VALID -> ....(Some Operations)
        # -> VALID -> (Update Operation) UPDATED
        # -> CHANGED -> (Change Operation) -> UPDATED -> ....(Some Operations)
        # -> DEPRECATED (Deprecate Ops)-> INVALID
        self.set_attrib_map(
            {
                "from_acc_valid": 0,
                "to_acc_valid": 1,
                "from_acc_updated": 2,
                "to_acc_updated": 3,
                "from_acc_changed": 4,
                "to_acc_changed": 5,
                "from_acc_deprecated": 6,
                "to_acc_deprecated": 7,
            }
        )

    def set_from_acc_valid(self):
        self.set_attrib("from_acc_valid")

    def unset_from_acc_valid(self):
        self.unset_attrib("from_acc_valid")

    def is_from_acc_valid(self):
        return self.is_attrib("from_acc_valid")

    def set_to_acc_valid(self):
        self.set_attrib("to_acc_valid")

    def unset_to_acc_valid(self):
        self.unset_attrib("to_acc_valid")

    def is_to_acc_valid(self):
        return self.is_attrib("to_acc_valid")

    def set_from_acc_updated(self):
        self.set_attrib("from_acc_updated")

    def unset_from_acc_updated(self):
        self.unset_attrib("from_acc_updated")

    def is_from_acc_updated(self):
        return self.is_attrib("from_acc_updated")

    def set_to_acc_updated(self):
        self.set_attrib("to_acc_updated")

    def unset_to_acc_updated(self):
        self.unset_attrib("to_acc_updated")

    def is_to_acc_updated(self):
        return self.is_attrib("to_acc_updated")

    def set_from_acc_changed(self):
        self.set_attrib("from_acc_changed")

    def unset_from_acc_changed(self):
        self.unset_attrib("from_acc_changed")

    def is_from_acc_changed(self):
        return self.is_attrib("from_acc_changed")

    def set_to_acc_changed(self):
        self.set_attrib("to_acc_changed")

    def unset_to_acc_changed(self):
        self.unset_attrib("to_acc_changed")

    def is_to_acc_changed(self):
        return self.is_attrib("to_acc_changed")

    def set_from_acc_deprecated(self):
        self.set_attrib("from_acc_deprecated")

    def unset_from_acc_deprecated(self):
        self.unset_attrib("from_acc_deprecated")

    def is_from_acc_deprecated(self):
        return self.is_attrib("from_acc_deprecated")

    def set_to_acc_deprecated(self):
        self.set_attrib("to_acc_deprecated")

    def unset_to_acc_deprecated(self):
        self.unset_attrib("to_acc_deprecated")

    def is_to_acc_deprecated(self):
        return self.is_attrib("to_acc_deprecated")

def transactions_money_iter(transactions: List[TransactionData]) -> Iterator[Money]:
    for transaction in transactions:
        if transaction.from_acc_id != -1:
            yield Money(transaction.value)
        else:
            yield -Money(transaction.value)


# Budget is a plan for future transactions, frequently used for project management

class Budget(ORMBase):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    amount = Column(String)  # Decimal float
    description = Column(String)
    tags = Column(String, default="")
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time

@dataclass
class BudgetData:
    id: int = field(default=-1)
    name: str = field(default="")
    amount: str = field(default="0.0")
    description: str = field(default="")
    tags: str = field(default="")
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
