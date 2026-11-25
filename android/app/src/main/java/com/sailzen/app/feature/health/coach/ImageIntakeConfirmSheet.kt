package com.sailzen.app.feature.health.coach

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.ImageIntakeDraftDto
import com.sailzen.app.core.network.dto.IntakeEntryDto
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull

private val SCENE_LABELS = mapOf(
    "diet" to "餐饮记录",
    "canteen_menu" to "食堂/点餐菜单",
    "sleep" to "睡眠节律",
    "exercise" to "运动记录",
    "weight" to "体重/体脂",
    "selfie_status" to "气色/状态",
    "receipt" to "消费小票/订单",
    "bill_screenshot" to "账单流水截图",
    "account_balance" to "账户余额核对",
    "general" to "日常记录",
)

private val KIND_CHOICES = listOf(
    "diet" to "饮食",
    "canteen_menu" to "菜单",
    "sleep" to "睡眠",
    "exercise" to "运动",
    "weight" to "体重",
    "mood" to "气色/状态",
    "transaction" to "账单",
    "account_balance_check" to "余额核对",
    "daily_info" to "日常",
)

private val MEAL_CHOICES = listOf(
    "breakfast" to "早餐",
    "lunch" to "午餐",
    "dinner" to "晚餐",
    "snack" to "加餐",
)

private fun JsonObject.str(key: String): String =
    (this[key] as? JsonPrimitive)?.contentOrNull.orEmpty()

private fun JsonObject.bool(key: String): Boolean =
    (this[key] as? JsonPrimitive)?.booleanOrNull ?: false

private fun JsonObject.strList(key: String): List<String> =
    (this[key] as? JsonArray)
        ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
        ?.filter { it.isNotBlank() }
        .orEmpty()

private fun numberOrNullJson(raw: String): JsonElement {
    val trimmed = raw.trim()
    if (trimmed.isEmpty()) return JsonNull
    return trimmed.toDoubleOrNull()?.let { JsonPrimitive(it) } ?: JsonNull
}

private fun intOrZeroJson(raw: String): JsonElement {
    val trimmed = raw.trim()
    return JsonPrimitive(trimmed.toIntOrNull() ?: 0)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImageIntakeConfirmSheet(
    draft: ImageIntakeDraftDto,
    entries: List<IntakeEntryDto>,
    summary: String,
    replyText: String,
    previewBytes: ByteArray?,
    committing: Boolean,
    onDismiss: () -> Unit,
    onSummaryChange: (String) -> Unit,
    onReplyTextChange: (String) -> Unit,
    onToggleEntry: (Int, Boolean) -> Unit,
    onEntryKindChange: (Int, String) -> Unit,
    onEntryTitleChange: (Int, String) -> Unit,
    onEntryFieldChange: (Int, String, JsonElement) -> Unit,
    onCommit: () -> Unit,
    onDiscard: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val previewBitmap = remember(previewBytes) {
        previewBytes?.let { bytes ->
            runCatching { BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap() }.getOrNull()
        }
    }
    val selectedCount = entries.count { it.selected }

    ModalBottomSheet(
        onDismissRequest = { if (!committing) onDismiss() },
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .navigationBarsPadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp)
                .padding(bottom = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // 顶部标题与场景徽标
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    "确认 AI 识图结果",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                AssistChip(
                    onClick = {},
                    label = {
                        Text(
                            "${SCENE_LABELS[draft.scene] ?: draft.scene} · ${draft.modelUsed}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    },
                )
            }

            // 图片缩略预览 + 摘要 + 教练简评
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.Top,
            ) {
                if (previewBitmap != null) {
                    Image(
                        bitmap = previewBitmap,
                        contentDescription = "待确认图片预览",
                        modifier = Modifier
                            .size(92.dp)
                            .clip(RoundedCornerShape(10.dp)),
                        contentScale = ContentScale.Crop,
                    )
                }
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    OutlinedTextField(
                        value = summary,
                        onValueChange = onSummaryChange,
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("识别摘要") },
                        textStyle = MaterialTheme.typography.bodySmall,
                        maxLines = 3,
                    )
                }
            }

            if (draft.coachAdvice.isNotBlank()) {
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.45f),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier.padding(10.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Icon(
                            Icons.Default.AutoAwesome,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            draft.coachAdvice,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            HorizontalDivider()

            // 可编辑候选条目列表
            entries.forEachIndexed { idx, entry ->
                IntakeEntryEditorCard(
                    entry = entry,
                    onToggle = { onToggleEntry(idx, it) },
                    onKindChange = { onEntryKindChange(idx, it) },
                    onTitleChange = { onEntryTitleChange(idx, it) },
                    onFieldChange = { key, value -> onEntryFieldChange(idx, key, value) },
                )
            }

            if (draft.ticketId != null) {
                OutlinedTextField(
                    value = replyText,
                    onValueChange = onReplyTextChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("附带回复票据 #${draft.ticketId}（留空则自动汇总）") },
                    singleLine = true,
                )
            }

            // 底部动作行
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                OutlinedButton(
                    onClick = onDiscard,
                    enabled = !committing,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Default.DeleteOutline, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.size(4.dp))
                    Text("丢弃")
                }
                Button(
                    onClick = onCommit,
                    enabled = !committing && selectedCount > 0,
                    modifier = Modifier.weight(2f),
                ) {
                    if (committing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                        Spacer(Modifier.size(8.dp))
                        Text("正在落库…")
                    } else {
                        Icon(Icons.Default.CheckCircle, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.size(6.dp))
                        Text("确认落库（$selectedCount 项）")
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun IntakeEntryEditorCard(
    entry: IntakeEntryDto,
    onToggle: (Boolean) -> Unit,
    onKindChange: (String) -> Unit,
    onTitleChange: (String) -> Unit,
    onFieldChange: (String, JsonElement) -> Unit,
) {
    val containerColor = if (entry.selected) {
        MaterialTheme.colorScheme.surfaceContainerLow
    } else {
        MaterialTheme.colorScheme.surfaceContainerLowest
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = containerColor),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(checked = entry.selected, onCheckedChange = onToggle)
                OutlinedTextField(
                    value = entry.title,
                    onValueChange = onTitleChange,
                    modifier = Modifier.weight(1f),
                    label = { Text("条目标题") },
                    singleLine = true,
                    textStyle = MaterialTheme.typography.bodySmall,
                )
            }

            // 类型快速切换 Chips
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                KIND_CHOICES.forEach { (k, label) ->
                    FilterChip(
                        selected = entry.kind == k,
                        onClick = { onKindChange(k) },
                        label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }

            // 按条目类型展示结构化微调表单
            when (entry.kind) {
                "diet" -> {
                    val mealType = entry.data.str("meal_type").ifBlank { "lunch" }
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        MEAL_CHOICES.forEach { (m, label) ->
                            FilterChip(
                                selected = mealType == m,
                                onClick = { onFieldChange("meal_type", JsonPrimitive(m)) },
                                label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                            )
                        }
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("calories"),
                            onValueChange = { onFieldChange("calories", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("热量 kcal") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("protein"),
                            onValueChange = { onFieldChange("protein", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("蛋白 g") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("carbs"),
                            onValueChange = { onFieldChange("carbs", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("碳水 g") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("饮食内容") },
                        maxLines = 3,
                    )
                }

                "canteen_menu" -> {
                    val rec = entry.data.strList("recommended_items")
                    if (rec.isNotEmpty()) {
                        Text(
                            "推荐点餐：${rec.joinToString("、")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Medium,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("菜单摘要与搭配建议") },
                        maxLines = 3,
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text("同时记为本餐饮食记录", style = MaterialTheme.typography.bodySmall)
                        Switch(
                            checked = entry.data.bool("log_as_diet"),
                            onCheckedChange = { onFieldChange("log_as_diet", JsonPrimitive(it)) },
                        )
                    }
                }

                "sleep" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("hours"),
                            onValueChange = { onFieldChange("hours", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("睡眠时长(小时)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("quality"),
                            onValueChange = { onFieldChange("quality", intOrZeroJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("质量(1-5)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("入睡/醒来与深浅睡摘要") },
                        maxLines = 3,
                    )
                }

                "exercise" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("exercise_type"),
                            onValueChange = { onFieldChange("exercise_type", JsonPrimitive(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("类型") },
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("duration_minutes"),
                            onValueChange = { onFieldChange("duration_minutes", intOrZeroJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("时长(分)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("calories"),
                            onValueChange = { onFieldChange("calories", intOrZeroJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("消耗 kcal") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("运动详情") },
                        maxLines = 3,
                    )
                }

                "weight" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("value"),
                            onValueChange = { onFieldChange("value", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("体重 (kg)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("body_fat"),
                            onValueChange = { onFieldChange("body_fat", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("体脂 (%)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("备注") },
                        singleLine = true,
                    )
                }

                "mood" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("score"),
                            onValueChange = { onFieldChange("score", intOrZeroJson(it)) },
                            modifier = Modifier.weight(0.35f),
                            label = { Text("状态(1-5)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("description"),
                            onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                            modifier = Modifier.weight(0.65f),
                            label = { Text("气色/精神状态观察") },
                            maxLines = 3,
                        )
                    }
                }

                "transaction" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("amount"),
                            onValueChange = { onFieldChange("amount", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("金额 (¥)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("account_hint"),
                            onValueChange = { onFieldChange("account_hint", JsonPrimitive(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("账户(微信/支付宝)") },
                            singleLine = true,
                        )
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("tags"),
                            onValueChange = { onFieldChange("tags", JsonPrimitive(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("标签(逗号分隔)") },
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("htime"),
                            onValueChange = { onFieldChange("htime", JsonPrimitive(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("交易时间") },
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("商户 / 消费描述") },
                        singleLine = true,
                    )
                    val itemsArr = entry.data["items"] as? JsonArray
                    if (itemsArr != null && itemsArr.isNotEmpty()) {
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = MaterialTheme.colorScheme.surfaceContainerHigh,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(
                                modifier = Modifier.padding(10.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                Text(
                                    "已拆出 ${itemsArr.size} 项商品明细（主账单保持 1 笔流水）",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.primary,
                                    fontWeight = FontWeight.Medium,
                                )
                                itemsArr.forEach { elem ->
                                    val obj = elem as? JsonObject ?: return@forEach
                                    val name = obj.str("name").ifBlank { "商品" }
                                    val amt = obj.str("amount")
                                    val tag = obj.str("tag").ifBlank { "未分类" }
                                    val snackMark = if (obj.bool("is_snack") || tag == "零食") " [零食]" else ""
                                    Text(
                                        "• $name$snackMark — [$tag] ¥$amt",
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            }
                        }
                    }
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            "含零食/餐饮时同步联动健康饮食",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Switch(
                            checked = entry.data.bool("sync_to_health"),
                            onCheckedChange = { onFieldChange("sync_to_health", JsonPrimitive(it)) },
                        )
                    }
                }

                "account_balance_check" -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = entry.data.str("account_hint"),
                            onValueChange = { onFieldChange("account_hint", JsonPrimitive(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("账户名") },
                            singleLine = true,
                        )
                        OutlinedTextField(
                            value = entry.data.str("actual_balance"),
                            onValueChange = { onFieldChange("actual_balance", numberOrNullJson(it)) },
                            modifier = Modifier.weight(1f),
                            label = { Text("真实余额 (¥)") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true,
                        )
                    }
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("核对备注") },
                        singleLine = true,
                    )
                }

                else -> {
                    OutlinedTextField(
                        value = entry.data.str("description"),
                        onValueChange = { onFieldChange("description", JsonPrimitive(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("记录内容") },
                        maxLines = 3,
                    )
                }
            }
        }
    }
}
