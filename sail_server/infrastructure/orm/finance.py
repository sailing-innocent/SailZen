# -*- coding: utf-8 -*-
# @file finance.py
# @brief Finance ORM Models
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
财务模块 ORM 模型

从 sail_server/data/finance.py 迁移
"""

from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship
from sail_server.infrastructure.orm.orm_base import ORMBase


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


class Transaction(ORMBase):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_acc_id = Column(Integer, ForeignKey("accounts.id"))
    to_acc_id = Column(Integer, ForeignKey("accounts.id"))
    budget_id = Column(
        Integer, ForeignKey("budgets.id"), nullable=True
    )  # Link to budget
    # Define relationships with back_populates
    from_acc = relationship(
        "Account", back_populates="out_transactions", foreign_keys=[from_acc_id]
    )
    to_acc = relationship(
        "Account", back_populates="in_transactions", foreign_keys=[to_acc_id]
    )
    budget = relationship(
        "Budget", back_populates="transactions", foreign_keys=[budget_id]
    )

    value = Column(String)  # Decimal float
    prev_value = Column(String)  # Decimal float
    description = Column(String)
    tags = Column(String)
    state = Column(Integer)  # 0: create 1: valid 2: virtual 3: done 4: cancel
    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # happen time
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())


class Budget(ORMBase):
    """
    预算主体 - 通用预算模型

    设计理念：Budget 是一个容器，包含多个 BudgetItem。
    所有业务场景（租房、房贷、工资等）都使用相同的数据结构，
    通过不同的 items 配置来实现不同的业务逻辑。
    """

    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # 预算名称
    description = Column(String, default="")  # 预算描述
    tags = Column(String, default="")  # 标签（逗号分隔）

    # 时间范围
    start_date = Column(TIMESTAMP)  # 开始日期
    end_date = Column(TIMESTAMP)  # 结束日期

    # 计算字段（由 items 汇总，存储用于快速查询）
    total_amount = Column(String, default="0.0")  # 总预算金额（items 汇总）
    direction = Column(Integer, default=0)  # 预算方向：0=支出, 1=收入（由子项决定）

    htime = Column(TIMESTAMP, server_default=func.current_timestamp())  # 生效时间
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    transactions = relationship(
        "Transaction", back_populates="budget", foreign_keys="Transaction.budget_id"
    )
    items = relationship(
        "BudgetItem",
        back_populates="budget",
        cascade="all, delete-orphan",
        order_by="BudgetItem.id",
    )


class FinanceTag(ORMBase):
    """
    财务标签表

    将 tag 从硬编码字符串提升为独立的数据库实体，
    支持自定义标签、颜色、分类和统计。
    """

    __tablename__ = "finance_tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)  # 标签名称（唯一）
    color = Column(String, default="#888888")  # 显示颜色（HEX）
    description = Column(String, default="")  # 标签描述
    category = Column(String, default="expense")  # 分类: expense / income / major / custom
    sort_order = Column(Integer, default=0)  # 排序权重（越小越靠前）
    is_active = Column(Integer, default=1)  # 是否启用 (1=启用, 0=停用)
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())


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
    name = Column(String, nullable=False)  # 子项名称
    description = Column(String, default="")  # 描述

    # 核心属性
    direction = Column(Integer, default=0)  # 0: 支出, 1: 收入
    item_type = Column(Integer, default=0)  # 0: 固定金额, 1: 周期性金额
    amount = Column(String, default="0.0")  # 金额（固定型=总额，周期型=单期金额）
    period_count = Column(Integer, default=1)  # 期数（固定型为1）

    # 可退还属性
    is_refundable = Column(Integer, default=0)  # 是否可退还
    refund_amount = Column(String, default="0.0")  # 已退还金额

    # 进度追踪
    current_period = Column(Integer, default=0)  # 当前已完成期数
    status = Column(Integer, default=0)  # 状态

    # 时间
    due_date = Column(TIMESTAMP)  # 到期日期（可选）
    ctime = Column(TIMESTAMP, server_default=func.current_timestamp())
    mtime = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationship
    budget = relationship("Budget", back_populates="items")
