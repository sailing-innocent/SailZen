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
