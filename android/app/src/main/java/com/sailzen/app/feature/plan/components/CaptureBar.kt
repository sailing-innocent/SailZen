package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.CAPTURE_KINDS
import com.sailzen.app.core.network.dto.kindLabel

/**
 * 吸顶常驻捕获栏（规划页核心入口）：一句话事务 + 类型下拉 + 捕获按钮。
 * 捕获成功后 INBOX 分区原地刷新出现新卡片，无需离开本页。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureBar(onCapture: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("generic") }
    var expanded by remember { mutableStateOf(false) }

    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            OutlinedTextField(
                value = title,
                onValueChange = { title = it },
                placeholder = { Text("一句话事务…") },
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = it },
                modifier = Modifier.width(118.dp),
            ) {
                OutlinedTextField(
                    value = kindLabel(kind),
                    onValueChange = {},
                    readOnly = true,
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(),
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    CAPTURE_KINDS.forEach { k ->
                        DropdownMenuItem(
                            text = { Text(kindLabel(k)) },
                            onClick = { kind = k; expanded = false },
                        )
                    }
                }
            }
            Spacer(Modifier.width(8.dp))
            Button(
                onClick = {
                    if (title.isNotBlank()) {
                        onCapture(title.trim(), kind)
                        title = ""
                    }
                },
                enabled = title.isNotBlank(),
            ) { Text("捕获") }
        }
    }
}

/** 磁贴深链（openCapture=true）触发的完整捕获弹窗，行为同旧版时间线页。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureDialog(onDismiss: () -> Unit, onConfirm: (String, String) -> Unit) {
    var title by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("generic") }
    var expanded by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("快速捕获") },
        text = {
            Column {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("一句话事务") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
                    OutlinedTextField(
                        value = kindLabel(kind),
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("种类（默认未分类，交给 AI 分拣）") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor(),
                    )
                    ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                        CAPTURE_KINDS.forEach { k ->
                            DropdownMenuItem(
                                text = { Text(kindLabel(k)) },
                                onClick = { kind = k; expanded = false },
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(title, kind) }, enabled = title.isNotBlank()) {
                Text("捕获")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
