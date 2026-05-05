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

from sail_server.utils.state import StateBits


# ============================================================================
# State Classes (for model layer use)
# ============================================================================


class AccountState(StateBits):
    """账户状态"""

    def __init__(self, value: int):
        super().__init__(value)
        self.set_attrib_map(
            {
                "valid": 0,
                "archived": 1,
            }
        )


class TransactionState(StateBits):
    """交易状态"""

    def __init__(self, value: int):
        super().__init__(value)
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

    # Convenience methods for transaction state
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


# ============================================================================
# Enums
# ============================================================================


class AccountStateEnum(IntEnum):
    """账户状态"""

    VALID = 0  # 有效
    ARCHIVED = 1  # 已归档


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
    INCOME = 1  # 收入


class ItemTypeEnum(IntEnum):
    """子项金额类型"""

    FIXED = 0  # 固定金额
    PERIODIC = 1  # 周期性金额


class ItemStatusEnum(IntEnum):
    """子项状态"""

    PENDING = 0  # 待定
    CONFIRMED = 1  # 已确认
    CANCELLED = 2  # 已取消


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


class AccountFixBalanceRequest(BaseModel):
    """修复账户余额请求"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="账户ID")
    balance: str = Field(description="目标余额")


class AccountResponse(AccountBase):
    """账户响应"""

    id: int = Field(description="账户ID")
    ctime: Optional[datetime] = Field(default=None, description="创建时间")
    mtime: Optional[datetime] = Field(default=None, description="修改时间")


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

    htime: Optional[float] = Field(
        default=None, description="发生时间戳，默认为当前时间"
    )


class TransactionUpdateRequest(BaseModel):
    """更新交易请求"""

    model_config = ConfigDict(from_attributes=True)

    from_acc_id: int = Field(description="转出账户ID")
    to_acc_id: int = Field(description="转入账户ID")
    value: str = Field(description="交易金额")
    description: str = Field(default="", description="交易描述")
    tags: str = Field(default="", description="交易标签")
    budget_id: Optional[int] = Field(default=None, description="关联预算ID")
    htime: Optional[float] = Field(default=None, description="发生时间戳")


class TransactionResponse(TransactionBase):
    """交易响应"""

    id: int = Field(description="交易ID")
    prev_value: str = Field(default="0.0", description="交易前金额")
    state: int = Field(description="交易状态")
    htime: Optional[float] = Field(default=0.0, description="发生时间戳")
    ctime: Optional[datetime] = Field(default=None, description="创建时间")
    mtime: Optional[datetime] = Field(default=None, description="修改时间")


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
    start_time: Optional[float] = Field(default=None, description="开始时间戳")
    end_time: Optional[float] = Field(default=None, description="结束时间戳")
    status: int = Field(default=0, description="预算状态")


class BudgetCreateRequest(BaseModel):
    """创建预算请求"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="预算名称")
    description: str = Field(default="", description="预算描述")
    tags: str = Field(default="", description="标签")
    start_date: Optional[float] = Field(default=None, description="开始日期")
    end_date: Optional[float] = Field(default=None, description="结束日期")
    total_amount: Optional[str] = Field(
        default=None, description="预算总金额（可选，会从子项计算）"
    )
    direction: int = Field(default=0, description="预算方向 (0=支出, 1=收入)")
    htime: Optional[float] = Field(default=None, description="生效时间戳")
    items: Optional[List[BudgetItemCreateRequest]] = Field(
        default=None, description="预算子项"
    )


class BudgetUpdateRequest(BaseModel):
    """更新预算请求"""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(default=None, description="预算名称")
    description: Optional[str] = Field(default=None, description="预算描述")
    status: Optional[int] = Field(default=None, description="预算状态")


class BudgetResponse(BudgetBase):
    """预算响应"""

    id: int = Field(description="预算ID")
    total_amount: str = Field(default="0.0", description="预算总金额")
    direction: int = Field(default=0, description="预算方向 (0=支出, 1=收入)")
    items: List[BudgetItemResponse] = Field(
        default_factory=list, description="预算子项"
    )

    # 允许从 BudgetData 转换（字段别名兼容）
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BudgetListResponse(BaseModel):
    """预算列表响应"""

    budgets: List[BudgetResponse]
    total: int


# ============================================================================
# Legacy Data DTOs (for backward compatibility)
# ============================================================================


class AccountData(BaseModel):
    """账户数据 DTO (向后兼容)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=0, description="账户ID")
    name: str = Field(default="", description="账户名称")
    description: str = Field(default="", description="账户描述")
    balance: str = Field(default="0.0", description="账户余额")
    state: int = Field(default=0, description="账户状态")
    ctime: Optional[datetime] = Field(default=None, description="创建时间")
    mtime: Optional[datetime] = Field(default=None, description="修改时间")


class TransactionData(BaseModel):
    """交易数据 DTO (向后兼容)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=0, description="交易ID")
    from_acc_id: int = Field(default=0, description="转出账户ID")
    to_acc_id: int = Field(default=0, description="转入账户ID")
    value: str = Field(default="0.0", description="交易金额")
    prev_value: str = Field(default="0.0", description="交易前金额")
    description: str = Field(default="", description="交易描述")
    tags: str = Field(default="", description="交易标签")
    state: int = Field(default=0, description="交易状态")
    budget_id: Optional[int] = Field(default=None, description="关联预算ID")
    htime: Optional[float] = Field(default=0.0, description="发生时间戳")
    ctime: Optional[datetime] = Field(default=None, description="创建时间")
    mtime: Optional[datetime] = Field(default=None, description="修改时间")


class BudgetItemData(BaseModel):
    """预算子项数据 DTO (向后兼容)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=0, description="子项ID")
    budget_id: int = Field(default=0, description="预算ID")
    name: str = Field(default="", description="子项名称")
    item_type: int = Field(default=0, description="子项类型")
    status: int = Field(default=0, description="子项状态")
    direction: int = Field(default=0, description="方向")
    amount: str = Field(default="0.0", description="金额")
    period_months: int = Field(default=1, description="周期月数")
    start_time: float = Field(default=0.0, description="开始时间戳")
    end_time: float = Field(default=0.0, description="结束时间戳")


# ============================================================================
# FinanceTag DTOs
# ============================================================================


class FinanceTagCreateRequest(BaseModel):
    """创建标签请求"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="标签名称（唯一）")
    color: str = Field(default="#888888", description="显示颜色（HEX）")
    description: str = Field(default="", description="标签描述")
    category: str = Field(
        default="expense", description="分类: expense / income / major / custom"
    )
    sort_order: int = Field(default=0, description="排序权重（越小越靠前）")


class FinanceTagUpdateRequest(BaseModel):
    """更新标签请求"""

    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(default=None, description="标签名称")
    color: Optional[str] = Field(default=None, description="显示颜色（HEX）")
    description: Optional[str] = Field(default=None, description="标签描述")
    category: Optional[str] = Field(default=None, description="分类")
    sort_order: Optional[int] = Field(default=None, description="排序权重")
    is_active: Optional[int] = Field(
        default=None, description="是否启用 (1=启用, 0=停用)"
    )


class FinanceTagResponse(BaseModel):
    """标签响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="标签ID")
    name: str = Field(description="标签名称")
    color: str = Field(default="#888888", description="显示颜色")
    description: str = Field(default="", description="标签描述")
    category: str = Field(default="expense", description="分类")
    sort_order: int = Field(default=0, description="排序权重")
    is_active: int = Field(default=1, description="是否启用")


class FinanceTagListResponse(BaseModel):
    """标签列表响应"""

    tags: List[FinanceTagResponse]
    total: int


class BudgetData(BaseModel):
    """预算数据 DTO (向后兼容)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(default=0, description="预算ID")
    name: str = Field(default="", description="预算名称")
    description: str = Field(default="", description="预算描述")
    tags: str = Field(default="", description="标签")
    start_date: Optional[float] = Field(default=None, description="开始日期")
    end_date: Optional[float] = Field(default=None, description="结束日期")
    total_amount: str = Field(default="0.0", description="预算总金额")
    direction: int = Field(default=0, description="预算方向 (0=支出, 1=收入)")
    htime: Optional[float] = Field(default=None, description="生效时间戳")
    ctime: Optional[datetime] = Field(default=None, description="创建时间")
    mtime: Optional[datetime] = Field(default=None, description="修改时间")
    status: int = Field(default=0, description="预算状态")
    items: List[BudgetItemData] = Field(default_factory=list, description="预算子项")
