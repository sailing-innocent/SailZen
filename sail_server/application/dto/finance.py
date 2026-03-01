# -*- coding: utf-8 -*-
# @file finance.py
# @brief Finance Pydantic DTOs
# @author sailing-innocent
# @date 2026-03-01
# @version 1.0
# ---------------------------------

"""
财务模块 Pydantic DTOs

Phase 3 试点模块：将 dataclass DTOs 迁移到 Pydantic BaseModel

原位置: sail_server/data/finance.py (AccountData, TransactionData, BudgetData)
"""

from datetime import datetime
from typing import Optional, List
from enum import IntEnum

from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class AccountStateEnum(IntEnum):
    """账户状态"""
    VALID = 0      # 有效
    ARCHIVED = 1   # 已归档


class TransactionStateEnum(IntEnum):
    """交易状态"""
    CREATE = 0
    VALID = 1
    VIRTUAL = 2
    DONE = 3
    CANCEL = 4


class BudgetDirectionEnum(IntEnum):
    """预算方向"""
    EXPENSE = 0  # 支出
    INCOME = 1   # 收入


class ItemTypeEnum(IntEnum):
    """子项金额类型"""
    FIXED = 0     # 固定金额
    PERIODIC = 1  # 周期性金额


class ItemStatusEnum(IntEnum):
    """子项状态"""
    PENDING = 0   # 待定
    CONFIRMED = 1 # 已确认
    CANCELLED = 2 # 已取消


# ============================================================================
# Account DTOs
# ============================================================================

class AccountBase(BaseModel):
    """账户基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(default="", description="账户名称")
    description: str = Field(default="", description="账户描述")
    balance: str = Field(default="0.0", description="账户余额")
    state: int = Field(default=0, description="账户状态")


class AccountCreateRequest(AccountBase):
    """创建账户请求"""
    pass


class AccountUpdateRequest(BaseModel):
    """更新账户请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="账户名称")
    description: Optional[str] = Field(default=None, description="账户描述")
    balance: Optional[str] = Field(default=None, description="账户余额")
    state: Optional[int] = Field(default=None, description="账户状态")


class AccountResponse(AccountBase):
    """账户响应"""
    id: int = Field(description="账户ID")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class AccountListResponse(BaseModel):
    """账户列表响应"""
    accounts: List[AccountResponse]
    total: int


# ============================================================================
# Transaction DTOs
# ============================================================================

class TransactionBase(BaseModel):
    """交易基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    from_acc_id: int = Field(description="转出账户ID")
    to_acc_id: int = Field(description="转入账户ID")
    value: str = Field(description="交易金额")
    description: str = Field(default="", description="交易描述")
    tags: str = Field(default="", description="交易标签")
    budget_id: Optional[int] = Field(default=None, description="关联预算ID")


class TransactionCreateRequest(TransactionBase):
    """创建交易请求"""
    pass


class TransactionUpdateRequest(BaseModel):
    """更新交易请求"""
    model_config = ConfigDict(from_attributes=True)
    
    value: Optional[str] = Field(default=None, description="交易金额")
    description: Optional[str] = Field(default=None, description="交易描述")
    tags: Optional[str] = Field(default=None, description="交易标签")
    state: Optional[int] = Field(default=None, description="交易状态")


class TransactionResponse(TransactionBase):
    """交易响应"""
    id: int = Field(description="交易ID")
    prev_value: str = Field(default="0.0", description="交易前金额")
    state: int = Field(description="交易状态")
    htime: float = Field(description="发生时间戳")
    ctime: datetime = Field(description="创建时间")
    mtime: datetime = Field(description="修改时间")


class TransactionListResponse(BaseModel):
    """交易列表响应"""
    transactions: List[TransactionResponse]
    total: int


# ============================================================================
# Budget DTOs
# ============================================================================

class BudgetItemBase(BaseModel):
    """预算子项基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="子项名称")
    item_type: int = Field(default=0, description="子项类型 (0=固定, 1=周期)")
    status: int = Field(default=0, description="子项状态")
    direction: int = Field(default=0, description="方向 (0=支出, 1=收入)")
    amount: str = Field(description="金额")
    period_months: int = Field(default=1, description="周期月数")
    start_time: float = Field(description="开始时间戳")
    end_time: float = Field(description="结束时间戳")


class BudgetItemCreateRequest(BudgetItemBase):
    """创建预算子项请求"""
    pass


class BudgetItemResponse(BudgetItemBase):
    """预算子项响应"""
    id: int = Field(description="子项ID")
    budget_id: int = Field(description="所属预算ID")


class BudgetBase(BaseModel):
    """预算基础信息"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(description="预算名称")
    description: str = Field(default="", description="预算描述")
    start_time: float = Field(description="开始时间戳")
    end_time: float = Field(description="结束时间戳")
    status: int = Field(default=0, description="预算状态")


class BudgetCreateRequest(BudgetBase):
    """创建预算请求"""
    items: Optional[List[BudgetItemCreateRequest]] = Field(default=None, description="预算子项")


class BudgetUpdateRequest(BaseModel):
    """更新预算请求"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, description="预算名称")
    description: Optional[str] = Field(default=None, description="预算描述")
    status: Optional[int] = Field(default=None, description="预算状态")


class BudgetResponse(BudgetBase):
    """预算响应"""
    id: int = Field(description="预算ID")
    items: List[BudgetItemResponse] = Field(default_factory=list, description="预算子项")


class BudgetListResponse(BaseModel):
    """预算列表响应"""
    budgets: List[BudgetResponse]
    total: int
