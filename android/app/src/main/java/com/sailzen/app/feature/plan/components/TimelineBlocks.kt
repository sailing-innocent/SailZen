package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.network.dto.kindLabel

/** 块类型配色（设计文档 §8：骨架淡色铺底、fixed 深蓝锁定、precept 紫、habit 绿、career 橙、buffer 灰） */
fun blockColor(blockType: String): Color = when (blockType) {
    "sleep" -> Color(0xFF3F51B5)
    "commute" -> Color(0xFF90A4AE)
    "work_window" -> Color(0xFFCFD8DC)
    "micro_rest" -> Color(0xFFE0E0E0)
    "meal" -> Color(0xFFFFCC80)
    "precept" -> Color(0xFF9C27B0)
    "habit" -> Color(0xFF4CAF50)
    "fixed" -> Color(0xFF1565C0)
    "focus" -> Color(0xFF42A5F5)
    "light" -> Color(0xFF81D4FA)
    "career" -> Color(0xFFFF9800)
    "buffer" -> Color(0xFFBDBDBD)
    else -> Color(0xFF9E9E9E)
}

internal fun hhmm(iso: String): String =
    if (iso.length >= 16) iso.substring(11, 16) else iso

/** 当日编排区块头：版本号 + 三域分钟 */
@Composable
fun TimelineSectionHeader(timeline: DayTimelineDto?) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(top = 8.dp),
    ) {
        Text(
            "当日编排 (v${timeline?.planVersion ?: 0})",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.weight(1f))
        timeline?.let { tl ->
            Text(
                "生活 ${tl.domainMinutes.life}m / 工作 ${tl.domainMinutes.work}m / " +
                    "事业 ${tl.domainMinutes.career}m",
                style = MaterialTheme.typography.bodySmall,
                color = Color.Gray,
            )
        }
    }
}

/** 缓冲余量 / 精力页脚 */
@Composable
fun TimelineBufferFooter(timeline: DayTimelineDto) {
    if (timeline.bufferTotalMinutes <= 0) return
    Column(modifier = Modifier.padding(vertical = 8.dp)) {
        Text(
            "缓冲余量 ${timeline.bufferFreeMinutes}/${timeline.bufferTotalMinutes}min · " +
                "精力 ${timeline.energyConsumed}/${timeline.energyBudget}",
            style = MaterialTheme.typography.bodySmall,
            color = Color.Gray,
        )
        LinearProgressIndicator(
            progress = {
                if (timeline.bufferTotalMinutes > 0)
                    timeline.bufferFreeMinutes.toFloat() / timeline.bufferTotalMinutes else 0f
            },
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 4.dp),
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun TimelineBlockItem(
    block: TimeBlockDto,
    onDone: () -> Unit,
    onDefer: () -> Unit,
    onLongPress: () -> Unit,
) {
    val deferrable = block.affairId != null && !block.pinned && block.blockType != "fixed"
    val done = block.status == "DONE"
    val skipped = block.status == "SKIPPED"

    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.StartToEnd -> { onDone(); false }
                SwipeToDismissBoxValue.EndToStart -> { if (deferrable) onDefer(); false }
                SwipeToDismissBoxValue.Settled -> true
            }
        },
        positionalThreshold = { it * 0.4f },
    )

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            val isDone = dismissState.dismissDirection == SwipeToDismissBoxValue.StartToEnd
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .clip(RoundedCornerShape(12.dp))
                    .background(if (isDone) Color(0xFF4CAF50) else Color(0xFFFFB74D))
                    .padding(horizontal = 20.dp),
                contentAlignment = if (isDone) Alignment.CenterStart else Alignment.CenterEnd,
            ) {
                Icon(
                    if (isDone) Icons.Default.Check else Icons.Default.Close,
                    contentDescription = null,
                    tint = Color.White,
                )
            }
        },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = when {
                    done -> Color(0xFFE8F5E9)
                    skipped -> Color(0xFFF5F5F5)
                    else -> MaterialTheme.colorScheme.surface
                },
            ),
            modifier = Modifier
                .fillMaxWidth()
                .combinedClickable(onClick = {}, onLongClick = onLongPress),
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(10.dp),
            ) {
                Box(
                    modifier = Modifier
                        .width(6.dp)
                        .height(40.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(blockColor(block.blockType)),
                )
                Spacer(Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "${hhmm(block.startTime)} - ${hhmm(block.endTime)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color.Gray,
                        )
                        if (block.pinned) {
                            Spacer(Modifier.width(4.dp))
                            Icon(
                                Icons.Default.Lock,
                                contentDescription = "pinned",
                                modifier = Modifier.size(12.dp),
                                tint = Color.Gray,
                            )
                        }
                        if (block.energyCost > 0) {
                            Spacer(Modifier.width(6.dp))
                            Text(
                                "⚡${block.energyCost}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFFF6F00),
                            )
                        }
                    }
                    Text(
                        block.affairTitle ?: (block.ref["label"]?.toString()?.trim('"') ?: block.blockType),
                        fontWeight = if (done) FontWeight.Normal else FontWeight.Medium,
                        color = if (done || skipped) Color.Gray else Color.Unspecified,
                    )
                    block.affairKind?.let {
                        Text(
                            kindLabel(it),
                            style = MaterialTheme.typography.labelSmall,
                            color = blockColor(block.blockType),
                        )
                    }
                }
                Text(
                    when (block.status) {
                        "DONE" -> "✓"
                        "SKIPPED" -> "—"
                        "DOING" -> "…"
                        else -> ""
                    },
                    color = if (block.status == "DONE") Color(0xFF4CAF50) else Color.Gray,
                )
            }
        }
    }
}
