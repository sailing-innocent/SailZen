package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.CheckinTodayItemDto

/**
 * 紧凑打卡分区：戒律 / 习惯合并为行式卡片（数据源 dayView.checkins，兜底 checkinToday）。
 */
@Composable
fun CheckinSection(
    checkins: CheckinTodayDto?,
    onPreceptKept: (CheckinTodayItemDto) -> Unit,
    onPreceptViolated: (CheckinTodayItemDto) -> Unit,
    onHabitDone: (CheckinTodayItemDto) -> Unit,
    onHabitMissed: (CheckinTodayItemDto) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "打卡 ${checkins?.date ?: ""}",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
        val precepts = checkins?.precepts ?: emptyList()
        if (precepts.isEmpty()) {
            Text("今日无戒律项", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
        precepts.forEach { item ->
            PreceptRow(
                item = item,
                onKept = { onPreceptKept(item) },
                onViolated = { onPreceptViolated(item) },
            )
        }
        val habits = checkins?.habits ?: emptyList()
        if (habits.isEmpty()) {
            Text("今日无习惯项", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
        habits.forEach { item ->
            HabitRow(
                item = item,
                onDone = { onHabitDone(item) },
                onMissed = { onHabitMissed(item) },
            )
        }
    }
}

@Composable
private fun PreceptRow(item: CheckinTodayItemDto, onKept: () -> Unit, onViolated: () -> Unit) {
    val ruleText = item.affair.kindMeta["rule_text"]?.toString()?.trim('"')
        ?: item.affair.title
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (item.doneToday) Color(0xFFF3E5F5) else MaterialTheme.colorScheme.surface,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(ruleText, fontWeight = FontWeight.Medium)
                Text(
                    when (item.lastResult) {
                        "kept" -> "已守住 ✓"
                        "violated" -> "已破戒 ✗"
                        "exempt" -> "已豁免"
                        else -> "待打卡"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = when (item.lastResult) {
                        "kept" -> Color(0xFF4CAF50)
                        "violated" -> Color(0xFFE53935)
                        else -> Color.Gray
                    },
                )
            }
            if (!item.doneToday) {
                IconButton(onClick = onKept) {
                    Icon(Icons.Default.Check, contentDescription = "守住", tint = Color(0xFF4CAF50))
                }
                IconButton(onClick = onViolated) {
                    Icon(Icons.Default.Close, contentDescription = "破戒", tint = Color(0xFFE53935))
                }
            }
        }
    }
}

@Composable
private fun HabitRow(item: CheckinTodayItemDto, onDone: () -> Unit, onMissed: () -> Unit) {
    val streak = item.affair.kindMeta["streak"]?.toString()?.toIntOrNull() ?: 0
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (item.doneToday) Color(0xFFE8F5E9) else MaterialTheme.colorScheme.surface,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(item.affair.title, fontWeight = FontWeight.Medium)
                    if (streak >= 3) {
                        Spacer(Modifier.size(6.dp))
                        Text("🔥$streak", style = MaterialTheme.typography.bodySmall)
                    }
                }
                Text(
                    "本周 ${item.weekDoneCount}/${item.weekTarget}" +
                        (if (item.doneToday) " · 今日已达成 ✓" else ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (item.doneToday) Color(0xFF4CAF50) else Color.Gray,
                )
            }
            if (!item.doneToday) {
                FilledTonalButton(onClick = onDone) { Text("达成") }
                TextButton(onClick = onMissed) { Text("缺卡", color = Color.Gray) }
            }
        }
    }
}
