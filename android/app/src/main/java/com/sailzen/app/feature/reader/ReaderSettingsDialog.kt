@file:OptIn(ExperimentalMaterial3Api::class)

package com.sailzen.app.feature.reader

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderMode
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderSettings
import com.sailzen.app.feature.reader.ReaderViewModel.ReaderTheme

@Composable
fun ReaderSettingsDialog(
    settings: ReaderSettings,
    onSave: (ReaderSettings) -> Unit,
    onDismiss: () -> Unit,
) {
    var fontSize by remember { mutableFloatStateOf(settings.fontSize.toFloat()) }
    var lineHeight by remember { mutableFloatStateOf(settings.lineHeight) }
    var theme by remember { mutableStateOf(settings.theme) }
    var mode by remember { mutableStateOf(settings.mode) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.reader_settings_title)) },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.reader_font_size), style = MaterialTheme.typography.bodyMedium)
                Slider(
                    value = fontSize,
                    onValueChange = { fontSize = it },
                    valueRange = 12f..32f,
                    steps = 19,
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("${fontSize.toInt()} sp")
                }
                Spacer(modifier = Modifier.height(16.dp))
                Text(stringResource(R.string.reader_line_height), style = MaterialTheme.typography.bodyMedium)
                Slider(
                    value = lineHeight,
                    onValueChange = { lineHeight = it },
                    valueRange = 1.0f..2.5f,
                    steps = 14,
                )
                Text("%.1f".format(lineHeight))
                Spacer(modifier = Modifier.height(16.dp))
                Text(stringResource(R.string.reader_theme), style = MaterialTheme.typography.bodyMedium)
                SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                    SegmentedButton(
                        selected = theme == ReaderTheme.LIGHT,
                        onClick = { theme = ReaderTheme.LIGHT },
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(stringResource(R.string.reader_theme_light))
                    }
                    SegmentedButton(
                        selected = theme == ReaderTheme.DARK,
                        onClick = { theme = ReaderTheme.DARK },
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(stringResource(R.string.reader_theme_dark))
                    }
                }
                Spacer(modifier = Modifier.height(16.dp))
                Text(stringResource(R.string.reader_mode), style = MaterialTheme.typography.bodyMedium)
                SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                    SegmentedButton(
                        selected = mode == ReaderMode.PAGE,
                        onClick = { mode = ReaderMode.PAGE },
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(stringResource(R.string.reader_mode_page))
                    }
                    SegmentedButton(
                        selected = mode == ReaderMode.SCROLL,
                        onClick = { mode = ReaderMode.SCROLL },
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(stringResource(R.string.reader_mode_scroll))
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        ReaderSettings(
                            fontSize = fontSize.toInt(),
                            lineHeight = lineHeight,
                            theme = theme,
                            mode = mode,
                        )
                    )
                }
            ) {
                Text(stringResource(R.string.dialog_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.dialog_cancel))
            }
        },
    )
}
