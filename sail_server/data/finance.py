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

from sail_server.utils.state import StateBits
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from sail_server.utils.money import Money
from typing import List, Iterator, Optional

__all__ = [
    "Account",
    "AccountState",
    "AccountData",
    "Transaction",
    "TransactionData",
    "TransactionState",
    "Budget",
    "BudgetData",
    "BudgetItem",
    "BudgetItemData",
    "BudgetDirection",
    "ItemType",
    "ItemStatus",
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
    id = Column(Integer, primary_key=True, autoincrement=True)
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
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_acc_id = Column(Integer, ForeignKey("accounts.id"))
    to_acc_id = Column(Integer, ForeignKey("accounts.id"))
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=True)  # Link to budget
    # Define relationships with back_populates
    from_acc = relationship(
        "Account", back_populates="out_transactions", foreign_keys=[from_acc_id]
    )
    to_acc = relationship(
        "Account", back_populates="in_transactions", foreign_keys=[to_acc_id]
    )
    budget = relationship("Budget", back_populates="transactions", foreign_keys=[budget_id])

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
    budget_id: Optional[int] = field(default=None)  # Link to budget
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

from enum import IntEnum


class BudgetDirection(IntEnum):
    """预算方向（收入/支出）"""
    EXPENSE = 0     # 支出
    INCOME = 1      # 收入


class ItemType(IntEnum):
    """子项金额类型"""
    FIXED = 0       # 固定金额（如押金、首付、年终奖）
    PERIODIC = 1    # 周期性金额（如月租、月供、月薪）


class ItemStatus(IntEnum):
    """子项状态"""
    PENDING = 0     # 待执行
    IN_PROGRESS = 1 # 进行中
    COMPLETED = 2   # 已完成
    REFUNDED = 3    # 已退还


class Budget(ORMBase):
    """
    预算主体 - 通用预算模型
    
    设计理念：Budget 是一个容器，包含多个 BudgetItem。
    所有业务场景（租房、房贷、工资等）都使用相同的数据结构，
    通过不同的 items 配置来实现不同的业务逻辑。
    """
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)           # 预算名称
    description = Column(String, default="")        # 预算描述
    tags = Column(String, default="")               # 标签（逗号分隔）
    
    # 时间范围
    start_date = Column(TIMESTAMP)                  # 开始日期
    end_date = Column(TIMESTAMP)                    # 结束日期
    
    # 计算字段（由 items 汇总，存储用于快速查询）
    total_amount = Column(String, default="0.0")    # 总预算金额（items 汇总）
    direction = Column(Integer, default=0)          # 预算方向：0=支出, 1=收入（由子项决定）
    
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 生效时间
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationships
    transactions = relationship("Transaction", back_populates="budget", foreign_keys="Transaction.budget_id")
    items = relationship("BudgetItem", back_populates="budget", cascade="all, delete-orphan", order_by="BudgetItem.id")


class BudgetItem(ORMBase):
    """
    预算子项 - 通用预算项模型
    
    设计理念：所有预算项都可以用以下属性描述：
    - direction: 收入还是支出
    - item_type: 固定金额还是周期性金额
    - amount: 金额（固定型为总额，周期型为单期金额）
    - period_count: 期数（固定型为1，周期型为实际期数）
    - is_refundable: 是否可退还（如押金）
    
    示例：
    - 押金：direction=EXPENSE, item_type=FIXED, amount=7000, period_count=1, is_refundable=1
    - 月租：direction=EXPENSE, item_type=PERIODIC, amount=3500, period_count=12, is_refundable=0
    - 首付：direction=EXPENSE, item_type=FIXED, amount=500000, period_count=1, is_refundable=0
    - 月供：direction=EXPENSE, item_type=PERIODIC, amount=8000, period_count=360, is_refundable=0
    - 月薪：direction=INCOME, item_type=PERIODIC, amount=20000, period_count=12, is_refundable=0
    - 年终奖：direction=INCOME, item_type=FIXED, amount=50000, period_count=1, is_refundable=0
    """
    __tablename__ = "budget_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(Integer, ForeignKey("budgets.id"), nullable=False)
    
    # 基本信息
    name = Column(String, nullable=False)           # 子项名称
    description = Column(String, default="")        # 描述
    
    # 核心属性
    direction = Column(Integer, default=0)          # 0: 支出, 1: 收入
    item_type = Column(Integer, default=0)          # 0: 固定金额, 1: 周期性金额
    amount = Column(String, default="0.0")          # 金额（固定型=总额，周期型=单期金额）
    period_count = Column(Integer, default=1)       # 期数（固定型为1）
    
    # 可退还属性
    is_refundable = Column(Integer, default=0)      # 是否可退还
    refund_amount = Column(String, default="0.0")   # 已退还金额
    
    # 进度追踪
    current_period = Column(Integer, default=0)     # 当前已完成期数
    status = Column(Integer, default=0)             # 状态
    
    # 时间
    due_date = Column(TIMESTAMP)                    # 到期日期（可选）
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())
    
    # Relationship
    budget = relationship("Budget", back_populates="items")
    
    @property
    def total_amount(self) -> str:
        """计算子项总金额"""
        from sail_server.utils.money import Money
        if self.item_type == ItemType.FIXED:
            return self.amount
        else:
            return (Money(self.amount) * self.period_count).value_str
    
    @property
    def remaining_periods(self) -> int:
        """剩余期数"""
        return max(0, self.period_count - self.current_period)


@dataclass
class BudgetData:
    """预算数据传输对象"""
    id: int = field(default=-1)
    name: str = field(default="")
    description: str = field(default="")
    tags: str = field(default="")
    start_date: Optional[float] = field(default=None)
    end_date: Optional[float] = field(default=None)
    total_amount: str = field(default="0.0")
    direction: int = field(default=0)  # 0=支出, 1=收入
    htime: float = field(default_factory=lambda: datetime.now().timestamp())
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())
    items: List["BudgetItemData"] = field(default_factory=list)


@dataclass
class BudgetItemData:
    """预算子项数据传输对象"""
    id: int = field(default=-1)
    budget_id: int = field(default=-1)
    name: str = field(default="")
    description: str = field(default="")
    
    # 核心属性
    direction: int = field(default=0)               # 0: 支出, 1: 收入
    item_type: int = field(default=0)               # 0: 固定, 1: 周期性
    amount: str = field(default="0.0")              # 金额
    period_count: int = field(default=1)            # 期数
    
    # 可退还
    is_refundable: int = field(default=0)
    refund_amount: str = field(default="0.0")
    
    # 进度
    current_period: int = field(default=0)
    status: int = field(default=0)
    
    due_date: Optional[float] = field(default=None)
    ctime: datetime = field(default_factory=lambda: datetime.now())
    mtime: datetime = field(default_factory=lambda: datetime.now())
    
    # 计算属性（只读，由后端计算）
    total_amount: str = field(default="0.0")        # 子项总金额
    remaining_periods: int = field(default=0)       # 剩余期数
