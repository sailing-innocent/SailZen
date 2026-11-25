package com.sailzen.app.feature.money

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CleaningServices
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PhotoCamera
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.AccountDto
import com.sailzen.app.core.network.dto.FinanceOverviewDto
import com.sailzen.app.core.network.dto.HygieneProposalDto
import java.math.BigDecimal

private val PositiveDeltaColor = Color(0xFF2E7D32)
private val NegativeDeltaColor = Color(0xFFD32F2F)
private val MicroThreshold = BigDecimal("30.00")

/**
 * Finance 2.0 SailTick 开销秘书卡片：
 * - 汇总真实零食消费（含超市小票明细拆分）、标签覆盖率与沉默账户提醒；
 * - 一句话快脑记账/对账输入条；
 * - 一键入口：拍小票、相册账单识图、智能余额核对、分级清理队列（支持批准/忽略/撤销）。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SailTickSecretaryCard(
    overview: FinanceOverviewDto?,
    pendingProposals: List<HygieneProposalDto>,
    autoProposals: List<HygieneProposalDto>,
    hygieneExpanded: Boolean,
    hygieneTab: Int,
    hygieneBusyId: Int?,
    scanningHygiene: Boolean,
    chatInput: String,
    chatBusy: Boolean,
    chatReply: String?,
    analyzingImage: Boolean,
    onChatInputChange: (String) -> Unit,
    onSendChat: () -> Unit,
    onClearChatReply: () -> Unit,
    onPickGallery: () -> Unit,
    onTakePhoto: () -> Unit,
    onOpenReconcile: () -> Unit,
    onToggleHygiene: () -> Unit,
    onSelectHygieneTab: (Int) -> Unit,
    onRunHygieneScan: () -> Unit,
    onApproveProposal: (Int) -> Unit,
    onDismissProposal: (Int) -> Unit,
    onRevertProposal: (Int) -> Unit,
) {
    val pendingCount = overview?.pendingHygieneCount ?: pendingProposals.size

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.35f),
        ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            // 标题行
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(
                    imageVector = Icons.Filled.AutoAwesome,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                    tint = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = "SailTick 开销秘书",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (overview != null) {
                    Surface(
                        shape = RoundedCornerShape(10.dp),
                        color = MaterialTheme.colorScheme.surface,
                    ) {
                        Text(
                            text = "标签覆盖 ${"%.0f".format(overview.overallTagCoveragePct)}%",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        )
                    }
                }
            }

            // 指标速览行（仅在 overview 就绪时展示）
            if (overview != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    SecretaryMetricPill(
                        label = "今日支出",
                        value = MoneyViewModel.formatMoney(overview.todayExpense),
                        sub = "${overview.todayCount} 笔",
                        modifier = Modifier.weight(1f),
                    )
                    SecretaryMetricPill(
                        label = "本月真实零食",
                        value = MoneyViewModel.formatMoney(overview.mtdSnackTotal),
                        sub = if (overview.mtdSplitTxCount > 0) {
                            "含 ${overview.mtdSplitTxCount} 笔拆分"
                        } else {
                            "占 ${"%.1f".format(overview.mtdSnackPct)}%"
                        },
                        modifier = Modifier.weight(1f),
                    )
                    SecretaryMetricPill(
                        label = "待确认清理",
                        value = "$pendingCount 条",
                        sub = "自动托管 ${overview.autoAppliedHygieneCount}",
                        modifier = Modifier
                            .weight(1f)
                            .clickable(onClick = onToggleHygiene),
                    )
                }

                // 沉默账户轻提示（非打扰、温和文案）
                val silent = overview.silentAccounts
                if (silent.isNotEmpty()) {
                    val text = silent.take(2).joinToString("、") {
                        "${it.name}(${it.daysSilent}天未记)"
                    }
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.65f),
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(onClick = onOpenReconcile),
                    ) {
                        Text(
                            text = "轻提示：$text，点此可快速对账或补记",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onTertiaryContainer,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }

            // 一句话快脑记账 / 对账输入条
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = chatInput,
                    onValueChange = onChatInputChange,
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    placeholder = {
                        Text(
                            "如：午饭 32 微信 / 余额宝还有 5230",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                )
                FilledTonalIconButton(
                    onClick = onSendChat,
                    enabled = chatInput.isNotBlank() && !chatBusy,
                ) {
                    if (chatBusy) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send,
                            contentDescription = "发送给 SailTick",
                        )
                    }
                }
            }

            // 快脑回复气泡
            if (!chatReply.isNullOrBlank()) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.surface,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Text(
                            text = chatReply,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.weight(1f),
                        )
                        IconButton(
                            onClick = onClearChatReply,
                            modifier = Modifier.size(24.dp),
                        ) {
                            Icon(
                                Icons.Filled.Close,
                                contentDescription = "关闭回复",
                                modifier = Modifier.size(14.dp),
                            )
                        }
                    }
                }
            }

            // 快捷能力行：拍小票 / 相册识图 / 智能对账 / 清理队列
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                AssistChip(
                    onClick = onTakePhoto,
                    enabled = !analyzingImage,
                    label = { Text(if (analyzingImage) "识图中…" else "拍小票") },
                    leadingIcon = {
                        if (analyzingImage) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                            )
                        } else {
                            Icon(
                                Icons.Filled.PhotoCamera,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                            )
                        }
                    },
                )
                AssistChip(
                    onClick = onPickGallery,
                    enabled = !analyzingImage,
                    label = { Text("相册账单") },
                    leadingIcon = {
                        Icon(
                            Icons.Filled.PhotoLibrary,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                        )
                    },
                )
                AssistChip(
                    onClick = onOpenReconcile,
                    label = { Text("智能对账") },
                    leadingIcon = {
                        Icon(
                            Icons.Filled.AccountBalanceWallet,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                        )
                    },
                )
                AssistChip(
                    onClick = onToggleHygiene,
                    label = {
                        Text(
                            if (pendingCount > 0) "清理队列 ($pendingCount)" else "清理队列",
                        )
                    },
                    leadingIcon = {
                        Icon(
                            Icons.Filled.CleaningServices,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp),
                        )
                    },
                )
            }

            // 可展开的分级清理队列（待确认 + AI 自动托管可撤销）
            if (hygieneExpanded) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                HygieneQueueSection(
                    pendingProposals = pendingProposals,
                    autoProposals = autoProposals,
                    selectedTab = hygieneTab,
                    busyId = hygieneBusyId,
                    scanning = scanningHygiene,
                    onSelectTab = onSelectHygieneTab,
                    onRunScan = onRunHygieneScan,
                    onApprove = onApproveProposal,
                    onDismiss = onDismissProposal,
                    onRevert = onRevertProposal,
                )
            }
        }
    }
}

@Composable
private fun SecretaryMetricPill(
    label: String,
    value: String,
    sub: String,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 7.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = value,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = sub,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun HygieneQueueSection(
    pendingProposals: List<HygieneProposalDto>,
    autoProposals: List<HygieneProposalDto>,
    selectedTab: Int,
    busyId: Int?,
    scanning: Boolean,
    onSelectTab: (Int) -> Unit,
    onRunScan: () -> Unit,
    onApprove: (Int) -> Unit,
    onDismiss: (Int) -> Unit,
    onRevert: (Int) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(
                selected = selectedTab == 0,
                onClick = { onSelectTab(0) },
                label = { Text("待确认 (${pendingProposals.size})") },
            )
            FilterChip(
                selected = selectedTab == 1,
                onClick = { onSelectTab(1) },
                label = { Text("已自动托管 (${autoProposals.size})") },
            )
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onRunScan, enabled = !scanning) {
                Text(if (scanning) "扫描中…" else "体检近90天")
            }
        }

        val list = if (selectedTab == 0) pendingProposals else autoProposals
        if (list.isEmpty()) {
            Text(
                text = if (selectedTab == 0) {
                    "暂无需要确认的清理项，SailTick 会在夜间按月慢迭代渐进整理历史账单。"
                } else {
                    "暂无自动托管操作记录。"
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            list.take(6).forEach { prop ->
                val isBusy = busyId == prop.id
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.surface,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(
                        modifier = Modifier.padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        Text(
                            text = prop.title,
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Medium,
                        )
                        if (prop.reason.isNotBlank()) {
                            Text(
                                text = prop.reason,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.End,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            if (prop.status == "pending") {
                                TextButton(
                                    onClick = { onDismiss(prop.id) },
                                    enabled = !isBusy,
                                ) { Text("忽略") }
                                Spacer(Modifier.width(4.dp))
                                Button(
                                    onClick = { onApprove(prop.id) },
                                    enabled = !isBusy,
                                ) {
                                    Text(if (isBusy) "处理中…" else "批准")
                                }
                            } else if (prop.status == "applied") {
                                OutlinedButton(
                                    onClick = { onRevert(prop.id) },
                                    enabled = !isBusy,
                                ) {
                                    Text(if (isBusy) "撤销中…" else "一键撤销")
                                }
                            } else {
                                Text(
                                    text = when (prop.status) {
                                        "reverted" -> "已撤销"
                                        "dismissed" -> "已忽略"
                                        else -> prop.status
                                    },
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/**
 * 智能余额核对对话框：
 * - 选择物理账户并输入真实余额；
 * - 实时预览差额 Δ，≤ ¥30 自动无感平账（不污染消费统计且可撤销），> ¥30 引导排查或勾选强制平账。
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ReconcileAccountDialog(
    accounts: List<AccountDto>,
    selectedAccId: Int,
    actualBalance: String,
    note: String,
    forceAdjust: Boolean,
    busy: Boolean,
    onSelectAccount: (Int) -> Unit,
    onActualBalanceChange: (String) -> Unit,
    onNoteChange: (String) -> Unit,
    onForceAdjustChange: (Boolean) -> Unit,
    onSubmit: () -> Unit,
    onDismiss: () -> Unit,
) {
    val selectedAcc = accounts.firstOrNull { it.id == selectedAccId }
    val drift = remember(selectedAcc?.balance, actualBalance) {
        selectedAcc?.let { MoneyViewModel.computeReconcileDrift(it.balance, actualBalance) }
    }
    val absDrift = drift?.abs()
    val isLargeDrift = absDrift != null && absDrift > MicroThreshold

    AlertDialog(
        onDismissRequest = { if (!busy) onDismiss() },
        title = { Text("智能余额核对") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    text = "输入你在银行/微信/支付宝里看到的真实余额。≤ ¥30 差额将自动无感平账（不计入消费统计，随时可撤销）；较大差额可先排查漏记。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                if (accounts.isEmpty()) {
                    Text(
                        text = "暂无可核对的物理账户",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                } else {
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        accounts.forEach { acc ->
                            FilterChip(
                                selected = acc.id == selectedAccId,
                                onClick = { onSelectAccount(acc.id) },
                                label = { Text(acc.name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                            )
                        }
                    }
                }

                if (selectedAcc != null) {
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = MaterialTheme.colorScheme.surfaceContainerLow,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                text = "当前账面余额",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                text = MoneyViewModel.formatMoney(selectedAcc.balance),
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = actualBalance,
                    onValueChange = onActualBalanceChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("真实余额（元）") },
                    placeholder = { Text("例如：5230.50") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Decimal,
                        imeAction = ImeAction.Next,
                    ),
                )

                if (drift != null) {
                    val driftSign = if (drift > BigDecimal.ZERO) "+" else ""
                    val driftColor = when {
                        drift > BigDecimal.ZERO -> PositiveDeltaColor
                        drift < BigDecimal.ZERO -> NegativeDeltaColor
                        else -> MaterialTheme.colorScheme.onSurfaceVariant
                    }
                    val policyHint = when {
                        absDrift != null && absDrift < BigDecimal("0.01") -> "账实完全一致，仅记录校验快照。"
                        !isLargeDrift -> "差额 ≤ ¥30，提交后将自动无感平账（不污染消费统计）。"
                        forceAdjust -> "已勾选强制对齐，将生成不计入消费统计的平账记录。"
                        else -> "差额 > ¥30，提交后将进入待排查清单，保留原余额等你排查漏记。"
                    }
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = MaterialTheme.colorScheme.surfaceContainerLow,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(3.dp),
                        ) {
                            Text(
                                text = "预计差额 Δ：$driftSign¥${drift.toPlainString()}",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = driftColor,
                            )
                            Text(
                                text = policyHint,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                if (isLargeDrift) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onForceAdjustChange(!forceAdjust) },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = forceAdjust,
                            onCheckedChange = onForceAdjustChange,
                        )
                        Text(
                            text = "我确认无需排查漏记，直接对齐余额",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }

                OutlinedTextField(
                    value = note,
                    onValueChange = onNoteChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("备注（可选）") },
                    placeholder = { Text("如：月底核对 / 红包零钱") },
                    singleLine = true,
                )
                Spacer(Modifier.height(2.dp))
            }
        },
        confirmButton = {
            Button(
                onClick = onSubmit,
                enabled = !busy && selectedAcc != null && drift != null,
            ) {
                Text(if (busy) "提交中…" else "提交核对")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !busy) {
                Text("取消")
            }
        },
    )
}
