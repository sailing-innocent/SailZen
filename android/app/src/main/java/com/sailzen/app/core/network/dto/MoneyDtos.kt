package com.sailzen.app.core.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * 与 sail_server.application.dto.finance 对齐的财务网络 DTO。
 *
 * 契约来源：doc/api/finance.md + sail_server/router/finance.py 双重核对。
 * - 账户 / 交易列表接口返回纯 JSON 数组；
 * - htime 为 Unix 秒级时间戳（服务端 Optional[float]），DTO 以 Double 接收；
 * - 服务端异常时可能返回 200 + null body，序列化异常由 runOperation 统一捕获；
 * - ApiClient.json 已配置 ignoreUnknownKeys，ctime/mtime 等新增字段直接忽略。
 */

/**
 * 账户（对齐 AccountResponse）。
 *
 * state 语义采用 ORM + 前端实证（sail_server/infrastructure/orm/finance.py）：
 * 0 = physical account 物理账户（现金/银行卡/支付宝等），1 = budget pocket 预算口袋。
 * 注意 doc/api/finance.md 标注的 "1: 正常, 0: 禁用" 与代码不符（文档滞后，已知文档 bug）。
 */
@Serializable
data class AccountDto(
    val id: Int,
    val name: String = "",
    val description: String = "",
    val balance: String = "0.0",
    val state: Int = 0,
)

/** 交易（对齐 TransactionResponse）。 */
@Serializable
data class TransactionDto(
    val id: Int,
    @SerialName("from_acc_id") val fromAccId: Int,
    @SerialName("to_acc_id") val toAccId: Int,
    val value: String,
    val description: String = "",
    val tags: String = "",
    @SerialName("budget_id") val budgetId: Int? = null,
    @SerialName("prev_value") val prevValue: String = "0.0",
    val state: Int = 0,
    val htime: Double = 0.0,
    val ctime: String? = null,
    val mtime: String? = null,
)

/** 分页交易列表响应（对齐 GET /api/v1/finance/transaction/paginated/）。 */
@Serializable
data class PaginatedTransactionsDto(
    val data: List<TransactionDto> = emptyList(),
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 50,
    @SerialName("total_pages") val totalPages: Int = 1,
    @SerialName("has_next") val hasNext: Boolean = false,
    @SerialName("has_prev") val hasPrev: Boolean = false,
)

/** 交易汇总统计响应（对齐 GET /api/v1/finance/transaction/stats/）。 */
@Serializable
data class TransactionStatsDto(
    @SerialName("total_count") val totalCount: Int = 0,
    @SerialName("income_count") val incomeCount: Int = 0,
    @SerialName("expense_count") val expenseCount: Int = 0,
    @SerialName("income_total") val incomeTotal: String = "0.0",
    @SerialName("expense_total") val expenseTotal: String = "0.0",
    @SerialName("net_total") val netTotal: String = "0.0",
)

/**
 * 创建/更新交易请求体（对齐 TransactionCreateRequest / TransactionUpdateRequest）。
 * 本页面 tags 恒为空串、budget_id 不传；htime 缺省时服务端默认当前时间。
 */
@Serializable
data class TransactionUpsertRequest(
    @SerialName("from_acc_id") val fromAccId: Int,
    @SerialName("to_acc_id") val toAccId: Int,
    val value: String,
    val description: String = "",
    val tags: String = "",
    @SerialName("budget_id") val budgetId: Int? = null,
    val htime: Double? = null,
)

/** 删除交易响应：{id, status, message} */
@Serializable
data class TransactionDeleteResponse(
    val id: Int,
    val status: String = "",
    val message: String = "",
)

// ============================================================================
// Finance 2.0 (SailTick Personal Expense Secretary) DTOs
// ============================================================================

@Serializable
data class TagBreakdownItemDto(
    val tag: String = "",
    val amount: String = "0.00",
    val count: Int = 0,
    val pct: Double = 0.0,
)

@Serializable
data class SilentAccountHintDto(
    @SerialName("account_id") val accountId: Int = 0,
    val name: String = "",
    @SerialName("days_silent") val daysSilent: Int = 0,
    @SerialName("last_tx_date") val lastTxDate: String? = null,
)

@Serializable
data class AccountHealthItemDto(
    val id: Int = 0,
    val name: String = "",
    val balance: String = "0.00",
    @SerialName("days_since_last_tx") val daysSinceLastTx: Int? = null,
    @SerialName("last_reconciled_at") val lastReconciledAt: String? = null,
    @SerialName("last_drift") val lastDrift: String? = null,
    @SerialName("exclude_from_consumption") val excludeFromConsumption: Boolean = false,
)

@Serializable
data class FinanceOverviewDto(
    val month: String = "",
    @SerialName("today_expense") val todayExpense: String = "0.00",
    @SerialName("today_count") val todayCount: Int = 0,
    @SerialName("mtd_expense") val mtdExpense: String = "0.00",
    @SerialName("mtd_income") val mtdIncome: String = "0.00",
    @SerialName("mtd_net") val mtdNet: String = "0.00",
    @SerialName("mtd_expense_count") val mtdExpenseCount: Int = 0,
    @SerialName("mtd_snack_total") val mtdSnackTotal: String = "0.00",
    @SerialName("mtd_snack_from_split") val mtdSnackFromSplit: String = "0.00",
    @SerialName("mtd_snack_pct") val mtdSnackPct: Double = 0.0,
    @SerialName("mtd_split_tx_count") val mtdSplitTxCount: Int = 0,
    @SerialName("mtd_untagged_count") val mtdUntaggedCount: Int = 0,
    @SerialName("mtd_by_tag") val mtdByTag: List<TagBreakdownItemDto> = emptyList(),
    @SerialName("overall_tag_coverage_pct") val overallTagCoveragePct: Double = 100.0,
    @SerialName("overall_expense_count") val overallExpenseCount: Int = 0,
    @SerialName("overall_untagged_expense_count") val overallUntaggedExpenseCount: Int = 0,
    @SerialName("excluded_adjustments_count") val excludedAdjustmentsCount: Int = 0,
    @SerialName("pending_hygiene_count") val pendingHygieneCount: Int = 0,
    @SerialName("auto_applied_hygiene_count") val autoAppliedHygieneCount: Int = 0,
    @SerialName("silent_accounts") val silentAccounts: List<SilentAccountHintDto> = emptyList(),
    @SerialName("account_health") val accountHealth: List<AccountHealthItemDto> = emptyList(),
)

@Serializable
data class AccountReconcileRequestDto(
    @SerialName("account_id") val accountId: Int,
    @SerialName("actual_balance") val actualBalance: String,
    @SerialName("micro_threshold") val microThreshold: Double = 30.0,
    @SerialName("force_adjust") val forceAdjust: Boolean = false,
    val note: String = "",
    val source: String = "android",
)

@Serializable
data class BalanceCheckpointDto(
    val id: Int = 0,
    @SerialName("account_id") val accountId: Int = 0,
    @SerialName("account_name") val accountName: String = "",
    @SerialName("reported_balance") val reportedBalance: String = "0.00",
    @SerialName("book_balance") val bookBalance: String = "0.00",
    @SerialName("drift_amount") val driftAmount: String = "0.00",
    val handling: String = "",
    @SerialName("adjustment_tx_id") val adjustmentTxId: Int? = null,
    val note: String = "",
    val source: String = "android",
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class AccountReconcileResponseDto(
    val account: AccountDto,
    val checkpoint: BalanceCheckpointDto,
    val handling: String = "",
    @SerialName("drift_amount") val driftAmount: String = "0.00",
    val message: String = "",
    @SerialName("proposal_id") val proposalId: Int? = null,
)

@Serializable
data class HygieneScanRequestDto(
    val days: Int? = 90,
    @SerialName("auto_apply_safe") val autoApplySafe: Boolean = true,
    @SerialName("min_auto_confidence") val minAutoConfidence: Double = 0.90,
    @SerialName("max_review_proposals") val maxReviewProposals: Int = 8,
    @SerialName("include_legacy_fix") val includeLegacyFix: Boolean = true,
    @SerialName("created_by") val createdBy: String = "android",
)

@Serializable
data class HygieneScanResultDto(
    @SerialName("scanned_tx_count") val scannedTxCount: Int = 0,
    @SerialName("legacy_fix_isolated") val legacyFixIsolated: Int = 0,
    @SerialName("auto_tagged_count") val autoTaggedCount: Int = 0,
    @SerialName("review_proposals_created") val reviewProposalsCreated: Int = 0,
    @SerialName("duplicates_detected") val duplicatesDetected: Int = 0,
    @SerialName("travel_links_detected") val travelLinksDetected: Int = 0,
)

@Serializable
data class HygieneProposalDto(
    val id: Int,
    @SerialName("proposal_type") val proposalType: String = "",
    @SerialName("autonomy_level") val autonomyLevel: String = "",
    val status: String = "",
    @SerialName("target_tx_ids") val targetTxIds: List<Int> = emptyList(),
    val confidence: Double = 0.0,
    val title: String = "",
    val reason: String = "",
    @SerialName("created_by") val createdBy: String = "",
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
)
