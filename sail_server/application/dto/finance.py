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
from typing import Any, Dict, Optional, List
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
    meta: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


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
    entry_kind: str = Field(default="normal", description="账目类型: normal/micro_adjust/balance_adjust/refund")
    exclude_from_stats: bool = Field(default=False, description="是否从消费/收入统计中排除（仍计入余额）")
    meta: Dict[str, Any] = Field(default_factory=dict, description="扩展结构化元数据（含 items 多品类拆分与 links）")


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
    entry_kind: Optional[str] = Field(default=None, description="账目类型")
    exclude_from_stats: Optional[bool] = Field(default=None, description="是否排除统计")
    meta: Optional[Dict[str, Any]] = Field(default=None, description="扩展结构化元数据")


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
    meta: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
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
    entry_kind: str = Field(default="normal", description="账目类型")
    exclude_from_stats: bool = Field(default=False, description="是否排除统计")
    meta: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
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


# ============================================================================
# Finance 2.0 (SailTick Secretary) DTOs
# ============================================================================


class TransactionLineItem(BaseModel):
    """单笔交易的品类明细拆分项（如一次超市采购中的日用品 + 零食）"""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="商品/子项名称")
    amount: str = Field(description="子项金额")
    tag: str = Field(default="", description="归属财务标签")
    is_snack: bool = Field(default=False, description="是否属于零食/含糖饮品（联动健康模块）")
    health_hint: str = Field(default="", description="可选健康提示")


class TransactionMetaUpdateRequest(BaseModel):
    """更新单笔交易的明细拆分、跨领域关联或统计归类"""

    model_config = ConfigDict(from_attributes=True)

    items: Optional[List[TransactionLineItem]] = Field(default=None, description="多品类明细拆分数组")
    links: Optional[Dict[str, Any]] = Field(default=None, description="跨领域关联（diet/rhythm/vault）")
    entry_kind: Optional[str] = Field(default=None, description="账目类型: normal/micro_adjust/balance_adjust/refund")
    exclude_from_stats: Optional[bool] = Field(default=None, description="是否从消费/收入统计中排除")
    sync_tags_from_items: bool = Field(default=True, description="是否按明细标签自动同步交易主 tags")
    extra_meta: Optional[Dict[str, Any]] = Field(default=None, description="其他合并写入 meta 的键值")


class AccountReconcileRequest(BaseModel):
    """智能余额核对请求（小额自动无感平账，大额引导排查）"""

    model_config = ConfigDict(from_attributes=True)

    account_id: int = Field(description="账户ID")
    actual_balance: str = Field(description="用户看到的真实账户余额")
    micro_threshold: float = Field(default=30.0, description="小额无感平账阈值（元）")
    force_adjust: bool = Field(default=False, description="超过阈值时是否强制平账")
    note: str = Field(default="", description="备注")
    source: str = Field(default="manual", description="来源: manual/quick_chat/ocr/sailtick")


class BalanceCheckpointResponse(BaseModel):
    """余额核对快照响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    account_name: str = ""
    reported_balance: str
    book_balance: str
    drift_amount: str
    handling: str  # exact | micro_adjusted | large_drift_pending | manual_reset
    adjustment_tx_id: Optional[int] = None
    note: str = ""
    source: str = "manual"
    created_at: Optional[datetime] = None


class AccountReconcileResponse(BaseModel):
    """智能余额核对结果"""

    account: AccountResponse
    checkpoint: BalanceCheckpointResponse
    handling: str
    drift_amount: str
    message: str
    proposal_id: Optional[int] = None


class HygieneScanRequest(BaseModel):
    """账单健康体检与分级自治扫描请求"""

    model_config = ConfigDict(from_attributes=True)

    days: Optional[int] = Field(default=90, description="扫描最近 N 天（null/0=全历史；若提供 from_time/to_time 则按区间）")
    from_time: Optional[float] = Field(default=None, description="可选起始时间戳（用于按月倒推慢迭代）")
    to_time: Optional[float] = Field(default=None, description="可选截止时间戳（用于按月倒推慢迭代）")
    auto_apply_safe: bool = Field(default=True, description="是否静默执行高置信度安全动作（带可撤销审计）")
    min_auto_confidence: float = Field(default=0.90, description="自动执行最低置信度")
    max_review_proposals: int = Field(default=10, description="本次扫描最多新增多少条待人工确认建议（防轰炸）")
    include_legacy_fix: bool = Field(default=True, description="是否纳入 1970 伪时间戳历史 balance fix 隔离")
    created_by: str = Field(default="sailtick", description="触发来源")


class HygieneProposalCreateRequest(BaseModel):
    """由 SailTick 慢脑提交单条待人工确认清理建议（仅允许 needs_review，绝不静默删改）"""

    model_config = ConfigDict(from_attributes=True)

    proposal_type: str = Field(default="auto_tag", description="建议类型")
    target_tx_ids: List[int] = Field(default_factory=list, description="目标交易 ID 列表")
    confidence: float = Field(default=0.75, description="置信度 0-1")
    title: str = Field(description="简短标题")
    reason: str = Field(default="", description="推断理由")
    after_payload: Dict[str, Any] = Field(default_factory=dict, description="批准后执行的变更负载")
    created_by: str = Field(default="sailtick_nightly_llm", description="创建来源")


class HygieneProposalResponse(BaseModel):
    """清理建议 / 托管审计记录响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_type: str
    autonomy_level: str  # auto_applied | needs_review
    status: str  # pending | applied | reverted | dismissed
    target_tx_ids: List[int] = Field(default_factory=list)
    confidence: float = 0.0
    title: str
    reason: str = ""
    before_snapshot: Dict[str, Any] = Field(default_factory=dict)
    after_payload: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "sailtick"
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
