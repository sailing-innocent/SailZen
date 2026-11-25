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

from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    func,
)
from sqlalchemy.orm import relationship
from sailzen_orm.orm_base import ORMBase
from sailzen_orm.types import JSONB


class Account(ORMBase):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    description = Column(String)
    balance = Column(String)
    state = Column(Integer)  # 0: physical account 1: budget pocket / archived
    meta = Column(JSONB, default=dict)  # exclude_from_consumption, drift_tolerance, last_reconciled_at, aliases
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
    # Finance 2.0 (SailTick): 区分正常消费/小额平账/大额重置/退款，支持单交易 JSONB 明细拆分
    entry_kind = Column(String, default="normal")  # normal | micro_adjust | balance_adjust | refund
    exclude_from_stats = Column(Boolean, default=False)
    meta = Column(JSONB, default=dict)  # items: [{name, amount, tag, is_snack}], links: {...}, ai_audit: {...}
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
    category = Column(
        String, default="expense"
    )  # 分类: expense / income / major / custom
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


class FinanceBalanceCheckpoint(ORMBase):
    """账户真实余额核对快照（替代旧版 1970-01-01 balance fix 强制重置）。"""

    __tablename__ = "finance_balance_checkpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    reported_balance = Column(String, nullable=False)  # 用户上报的真实余额
    book_balance = Column(String, nullable=False)  # 核对前账面余额
    drift_amount = Column(String, nullable=False, default="0.00")  # reported - book
    # exact | micro_adjusted | large_drift_pending | manual_reset
    handling = Column(String, nullable=False, default="exact")
    adjustment_tx_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    note = Column(String, default="")
    source = Column(String, default="manual")  # manual | quick_chat | ocr | sailtick
    created_at = Column(TIMESTAMP, default=datetime.now, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_finance_checkpoints_acc_created", "account_id", "created_at"),
    )


class FinanceHygieneProposal(ORMBase):
    """SailTick 分级自治账单治理建议与可撤销审计日志。"""

    __tablename__ = "finance_hygiene_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # auto_tag | legacy_fix_classify | duplicate_merge | large_drift | micro_adjust_audit
    # | travel_rhythm_link | mixed_split_hint | new_tag_suggest
    proposal_type = Column(String, nullable=False, index=True)
    # auto_applied (已静默落库，支持一键撤销) | needs_review (待人工确认)
    autonomy_level = Column(String, nullable=False, default="needs_review")
    # pending | applied | reverted | dismissed
    status = Column(String, nullable=False, default="pending", index=True)
    target_tx_ids = Column(JSONB, default=list)
    confidence = Column(Float, default=0.0)
    title = Column(String, nullable=False)
    reason = Column(String, default="")
    before_snapshot = Column(JSONB, default=dict)
    after_payload = Column(JSONB, default=dict)
    created_by = Column(String, default="sailtick")
    created_at = Column(TIMESTAMP, default=datetime.now, server_default=func.current_timestamp())
    resolved_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("ix_finance_hygiene_status_created", "status", "created_at"),
        Index("ix_finance_hygiene_type_status", "proposal_type", "status"),
    )
