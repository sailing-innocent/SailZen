package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.feature.plan.PlanViewModel

/**
 * 待分拣分区（本次合并的核心修复点）：
 * 捕获/外部流入的 INBOX 事务在此原地出现并完成分拣，无需切换到事业页。
 * - 有 AI 建议的卡：建议种类 + 理由 + 驳回 / 采纳并确认
 * - 无建议的普通卡：kind 标签 + 启动 / 取消
 */
@Composable
fun InboxSection(
    inbox: List<AffairDto>,
    onAcceptHint: (AffairDto) -> Unit,
    onRejectHint: (AffairDto) -> Unit,
    onConfirm: (AffairDto) -> Unit,
    onCancel: (AffairDto) -> Unit,
) {
    val (hinted, plain) = PlanViewModel.splitInbox(inbox)

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "待分拣（${inbox.size}）",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
        if (inbox.isEmpty()) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Text(
                    "暂无待分拣事务，在顶部捕获一条试试",
                    modifier = Modifier.padding(16.dp),
                    color = Color.Gray,
                )
            }
        }
        hinted.forEach { affair ->
            HintCard(
                affair = affair,
                onAccept = { onAcceptHint(affair) },
                onReject = { onRejectHint(affair) },
            )
        }
        plain.forEach { affair ->
            InboxCard(
                affair = affair,
                onConfirm = { onConfirm(affair) },
                onCancel = { onCancel(affair) },
            )
        }
    }
}

@Composable
private fun HintCard(affair: AffairDto, onAccept: () -> Unit, onReject: () -> Unit) {
    val hintKind = affair.aiHint["kind"]?.toString()?.trim('"') ?: affair.kind
    val reason = affair.aiHint["reason"]?.toString()?.trim('"') ?: ""
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFF3E5F5)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(affair.title, fontWeight = FontWeight.Bold)
            Text(
                "建议判为「${kindLabel(hintKind)}」" + (if (reason.isNotBlank()) "：$reason" else ""),
                style = MaterialTheme.typography.bodySmall,
                color = Color(0xFF6A1B9A),
            )
            Row(
                horizontalArrangement = Arrangement.End,
                modifier = Modifier.fillMaxWidth(),
            ) {
                TextButton(onClick = onReject) { Text("驳回") }
                TextButton(onClick = onAccept) { Text("采纳并确认") }
            }
        }
    }
}

@Composable
private fun InboxCard(affair: AffairDto, onConfirm: () -> Unit, onCancel: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(containerColor = Color(0xFFE3F2FD)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(affair.title, fontWeight = FontWeight.Bold)
                    Text(
                        kindLabel(affair.kind),
                        style = MaterialTheme.typography.bodySmall,
                        color = Color.Gray,
                    )
                }
                TextButton(onClick = onConfirm) { Text("启动") }
                TextButton(onClick = onCancel) { Text("取消", color = Color.Gray) }
            }
        }
    }
}