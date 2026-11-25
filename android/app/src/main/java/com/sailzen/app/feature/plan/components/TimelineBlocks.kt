package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.outlined.RadioButtonUnchecked
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.Text
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.TimeBlockDto
import com.sailzen.app.core.network.dto.kindLabel
import com.sailzen.app.feature.plan.PlanViewModel
import kotlinx.serialization.json.JsonPrimitive

/** 块类型配色（含 Rhythm v2 `occupied` 临时占用） */
fun blockColor(blockType: String): Color = when (blockType) {
    "sleep" -> Color(0xFF3F51B5)
    "commute" -> Color(0xFF90A4AE)
    "work_window" -> Color(0xFFCFD8DC)
    "micro_rest" -> Color(0xFFE0E0E0)
    "meal" -> Color(0xFFFFCC80)
    "precept" -> Color(0xFF9C27B0)
    "habit" -> Color(0xFF4CAF50)
    "fixed" -> Color(0xFF1565C0)
    "occupied" -> Color(0xFFE91E63)
    "focus" -> Color(0xFF42A5F5)
    "light" -> Color(0xFF81D4FA)
    "career" -> Color(0xFFFF9800)
    "buffer" -> Color(0xFFBDBDBD)
    else -> Color(0xFF9E9E9E)
}

internal fun hhmm(iso: String): String =
    if (iso.length >= 16) iso.substring(11, 16) else iso

private fun refString(block: TimeBlockDto, key: String): String? =
    (block.ref[key] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() && it != "null" }

/** 当日日程区块头：版本号 + 完成时长进度 */
@Composable
fun TimelineSectionHeader(timeline: DayTimelineDto?) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 6.dp),
    ) {
        Text(
            text = if ((timeline?.planVersion ?: 0) > 0) "今日日程 · v${timeline?.planVersion}" else "今日日程",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
        Spacer(Modifier.weight(1f))
        timeline?.takeIf { it.plannedMinutes > 0 }?.let { tl ->
            Text(
                text = "已完成 ${PlanViewModel.formatMinutesCompact(tl.completedMinutes)} / ${PlanViewModel.formatMinutesCompact(tl.plannedMinutes)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/** SailTick AI 排程说明横幅 */
@Composable
fun AiRationaleBanner(rationale: String) {
    if (rationale.isBlank()) return
    var expanded by remember { mutableStateOf(false) }
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.7f),
        ),
        modifier = Modifier
            .fillMaxWidth()
            .clickable { expanded = !expanded },
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Icon(
                Icons.Default.AutoAwesome,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier
                    .padding(top = 2.dp)
                    .size(16.dp),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "SailTick 今日排程思路",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    text = rationale,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                    maxLines = if (expanded) Int.MAX_VALUE else 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun TimelineBlockItem(
    block: TimeBlockDto,
    onDone: () -> Unit,
    onDefer: () -> Unit,
    onDelete: () -> Unit,
    onLongPress: () -> Unit,
) {
    val isOccupied = block.blockType == "occupied"
    val deferrable = !isOccupied && block.affairId != null && !block.pinned && block.blockType != "fixed"
    val done = block.status == "DONE"
    val skipped = block.status == "SKIPPED"
    val title = block.affairTitle ?: refString(block, "label") ?: if (isOccupied) "占用时段" else block.blockType
    val note = refString(block, "note")

    val dismissState = rememberSwipeToDismissBoxState(
        confirmValueChange = { value ->
            when (value) {
                SwipeToDismissBoxValue.StartToEnd -> {
                    if (!isOccupied) onDone()
                    false
                }
                SwipeToDismissBoxValue.EndToStart -> {
                    if (deferrable) onDefer()
                    false
                }
                SwipeToDismissBoxValue.Settled -> true
            }
        },
        positionalThreshold = { it * 0.4f },
    )

    SwipeToDismissBox(
        state = dismissState,
        enableDismissFromStartToEnd = !isOccupied,
        enableDismissFromEndToStart = deferrable,
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
                    isOccupied -> MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.25f)
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
                modifier = Modifier.padding(horizontal = 10.dp, vertical = 10.dp),
            ) {
                Box(
                    modifier = Modifier
                        .width(5.dp)
                        .height(42.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(blockColor(block.blockType)),
                )
                Spacer(Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Text(
                            "${hhmm(block.startTime)} - ${hhmm(block.endTime)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (block.pinned) {
                            Icon(
                                Icons.Default.Lock,
                                contentDescription = "已钉住",
                                modifier = Modifier.size(12.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (isOccupied) {
                            Surface(
                                shape = RoundedCornerShape(999.dp),
                                color = Color(0xFFE91E63).copy(alpha = 0.14f),
                            ) {
                                Text(
                                    text = "占用",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color(0xFFC2185B),
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 1.dp),
                                )
                            }
                        } else {
                            block.affairKind?.let {
                                Text(
                                    kindLabel(it),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = blockColor(block.blockType),
                                )
                            }
                        }
                    }
                    Text(
                        text = title,
                        fontWeight = if (done) FontWeight.Normal else FontWeight.Medium,
                        color = if (done || skipped) Color.Gray else MaterialTheme.colorScheme.onSurface,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (!note.isNullOrBlank()) {
                        Text(
                            text = note,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                if (isOccupied) {
                    IconButton(onClick = onDelete, modifier = Modifier.size(34.dp)) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "取消占用",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(18.dp),
                        )
                    }
                } else {
                    IconButton(
                        onClick = { if (!done) onDone() },
                        enabled = !done,
                        modifier = Modifier.size(34.dp),
                    ) {
                        Icon(
                            imageVector = if (done) Icons.Default.CheckCircle else Icons.Outlined.RadioButtonUnchecked,
                            contentDescription = if (done) "已完成" else "标记完成",
                            tint = if (done) Color(0xFF4CAF50) else MaterialTheme.colorScheme.outline,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
            }
        }
    }
}
