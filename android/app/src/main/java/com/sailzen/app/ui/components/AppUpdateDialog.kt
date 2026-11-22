package com.sailzen.app.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sailzen.app.R
import com.sailzen.app.core.network.AppReleaseDto
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState

/** 启动检测到新版本时的应用内更新弹窗。 */
@Composable
fun AppUpdateDialog(
    state: AppUpdateState,
    onStartDownload: (AppReleaseDto) -> Unit,
    onInstallNow: (AppUpdateState.ReadyToInstall) -> Unit,
    onOpenPermissionSettings: () -> Unit,
    onSkipVersion: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    when (state) {
        is AppUpdateState.UpdateAvailable -> {
            val release = state.release
            AlertDialog(
                onDismissRequest = onDismiss,
                title = {
                    Text(
                        stringResource(
                            R.string.update_available_title,
                            release.versionName,
                            release.versionCode,
                        ),
                    )
                },
                text = {
                    Column {
                        if (release.size > 0L) {
                            Text(
                                text = "安装包大小：${AppUpdateManager.formatFileSize(release.size)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                        }
                        if (release.releaseNotes.isNotBlank()) {
                            Text(
                                text = release.releaseNotes,
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        } else {
                            Text(
                                text = "发现来自云端的新版本，是否立即下载并安装？",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                },
                confirmButton = {
                    Button(onClick = { onStartDownload(release) }) {
                        Text(stringResource(R.string.update_download_button))
                    }
                },
                dismissButton = {
                    TextButton(onClick = { onSkipVersion(release.versionCode) }) {
                        Text(stringResource(R.string.update_skip_version))
                    }
                    TextButton(onClick = onDismiss) {
                        Text(stringResource(R.string.update_later))
                    }
                },
            )
        }

        is AppUpdateState.Downloading -> {
            val total = state.totalBytes
            val progress = if (total > 0L) {
                (state.bytesRead.toFloat() / total.toFloat()).coerceIn(0f, 1f)
            } else {
                null
            }
            val progressText = if (progress != null) {
                stringResource(
                    R.string.update_downloading,
                    AppUpdateManager.formatFileSize(state.bytesRead),
                    AppUpdateManager.formatFileSize(total),
                    (progress * 100).toInt(),
                )
            } else {
                stringResource(
                    R.string.update_downloading_unknown,
                    AppUpdateManager.formatFileSize(state.bytesRead),
                )
            }
            AlertDialog(
                onDismissRequest = { /* 下载进行中禁止点外部误关 */ },
                title = {
                    Text(
                        stringResource(
                            R.string.update_available_title,
                            state.release.versionName,
                            state.release.versionCode,
                        ),
                    )
                },
                text = {
                    Column {
                        Text(text = progressText, style = MaterialTheme.typography.bodyMedium)
                        Spacer(modifier = Modifier.height(12.dp))
                        if (progress != null) {
                            LinearProgressIndicator(
                                progress = { progress },
                                modifier = Modifier.fillMaxWidth(),
                            )
                        } else {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                        }
                    }
                },
                confirmButton = {},
            )
        }

        is AppUpdateState.ReadyToInstall -> {
            AlertDialog(
                onDismissRequest = onDismiss,
                title = {
                    Text(
                        stringResource(
                            R.string.update_available_title,
                            state.release.versionName,
                            state.release.versionCode,
                        ),
                    )
                },
                text = {
                    Text(
                        text = if (state.needsInstallPermission) {
                            stringResource(R.string.update_permission_required)
                        } else {
                            stringResource(R.string.update_ready_hint)
                        },
                        style = MaterialTheme.typography.bodyMedium,
                    )
                },
                confirmButton = {
                    if (state.needsInstallPermission) {
                        Button(onClick = onOpenPermissionSettings) {
                            Text(stringResource(R.string.update_open_permission_settings))
                        }
                    } else {
                        Button(onClick = { onInstallNow(state) }) {
                            Text(stringResource(R.string.update_install_button))
                        }
                    }
                },
                dismissButton = {
                    if (state.needsInstallPermission) {
                        TextButton(onClick = { onInstallNow(state) }) {
                            Text(stringResource(R.string.update_install_button))
                        }
                    }
                    TextButton(onClick = onDismiss) {
                        Text(stringResource(R.string.update_later))
                    }
                },
            )
        }

        is AppUpdateState.Error -> {
            AlertDialog(
                onDismissRequest = onDismiss,
                title = { Text(stringResource(R.string.update_section_title)) },
                text = { Text(text = state.message, style = MaterialTheme.typography.bodyMedium) },
                confirmButton = {
                    TextButton(onClick = onDismiss) {
                        Text(stringResource(R.string.dialog_confirm))
                    }
                },
            )
        }

        else -> Unit
    }
}
