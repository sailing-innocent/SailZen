package com.sailzen.app.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Badge
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val savedMessage = stringResource(R.string.settings_saved)

    LaunchedEffect(state.saved) {
        if (state.saved) {
            snackbarHostState.showSnackbar(savedMessage)
            viewModel.consumeSaved()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            // 连接状态
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = if (state.connected) {
                        stringResource(R.string.settings_connected)
                    } else {
                        stringResource(R.string.settings_disconnected)
                    },
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                Badge(
                    containerColor = if (state.connected) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.error
                    },
                )
            }
            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = state.serverUrl,
                onValueChange = viewModel::onServerUrlChange,
                label = { Text(stringResource(R.string.settings_server_url)) },
                placeholder = { Text("http://192.168.x.x:1974") },
                singleLine = true,
                enabled = !state.serverUrlLocked,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            if (state.serverUrlLocked) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = stringResource(R.string.settings_server_url_locked_hint),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = state.apiToken,
                onValueChange = viewModel::onApiTokenChange,
                label = { Text(stringResource(R.string.settings_api_token)) },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(modifier = Modifier.height(16.dp))

            Text(text = "安静时段", style = MaterialTheme.typography.titleSmall)
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = state.quietStart,
                    onValueChange = viewModel::onQuietStartChange,
                    label = { Text(stringResource(R.string.settings_quiet_start)) },
                    placeholder = { Text("23:00") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                OutlinedTextField(
                    value = state.quietEnd,
                    onValueChange = viewModel::onQuietEndChange,
                    label = { Text(stringResource(R.string.settings_quiet_end)) },
                    placeholder = { Text("08:00") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = { viewModel.save() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.settings_save))
            }
            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = stringResource(R.string.settings_device_id),
                style = MaterialTheme.typography.titleSmall,
            )
            Text(
                text = state.deviceId,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(24.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(16.dp))

            // 应用内 OTA 更新
            Text(
                text = stringResource(R.string.update_section_title),
                style = MaterialTheme.typography.titleSmall,
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = stringResource(
                    R.string.update_current_version,
                    state.currentVersionName,
                    state.currentVersionCode,
                ),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(modifier = Modifier.height(12.dp))

            when (val update = state.updateState) {
                is AppUpdateState.Idle -> {
                    OutlinedButton(
                        onClick = viewModel::checkForUpdate,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.update_check_button))
                    }
                }

                is AppUpdateState.Checking -> {
                    Text(
                        text = stringResource(R.string.update_checking),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }

                is AppUpdateState.UpToDate -> {
                    Text(
                        text = stringResource(R.string.update_up_to_date),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = viewModel::checkForUpdate,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.update_check_button))
                    }
                }

                is AppUpdateState.UpdateAvailable -> {
                    Text(
                        text = stringResource(
                            R.string.update_available_title,
                            update.release.versionName,
                            update.release.versionCode,
                        ),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    if (update.release.size > 0L) {
                        Text(
                            text = "安装包大小：${AppUpdateManager.formatFileSize(update.release.size)}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (update.release.releaseNotes.isNotBlank()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = update.release.releaseNotes,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(
                        onClick = { viewModel.downloadAndInstall(update.release) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.update_download_button))
                    }
                }

                is AppUpdateState.Downloading -> {
                    val progress = if (update.totalBytes > 0L) {
                        (update.bytesRead.toFloat() / update.totalBytes.toFloat()).coerceIn(0f, 1f)
                    } else {
                        null
                    }
                    val statusText = if (progress != null) {
                        stringResource(
                            R.string.update_downloading,
                            AppUpdateManager.formatFileSize(update.bytesRead),
                            AppUpdateManager.formatFileSize(update.totalBytes),
                            (progress * 100).toInt(),
                        )
                    } else {
                        stringResource(
                            R.string.update_downloading_unknown,
                            AppUpdateManager.formatFileSize(update.bytesRead),
                        )
                    }
                    Text(
                        text = statusText,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    if (progress != null) {
                        LinearProgressIndicator(
                            progress = { progress },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    } else {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                }

                is AppUpdateState.ReadyToInstall -> {
                    Text(
                        text = if (update.needsInstallPermission) {
                            stringResource(R.string.update_permission_required)
                        } else {
                            stringResource(R.string.update_ready_hint)
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (update.needsInstallPermission) {
                            MaterialTheme.colorScheme.error
                        } else {
                            MaterialTheme.colorScheme.primary
                        },
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    if (update.needsInstallPermission) {
                        OutlinedButton(
                            onClick = viewModel::openInstallPermissionSettings,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(stringResource(R.string.update_open_permission_settings))
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                    Button(
                        onClick = viewModel::triggerInstall,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.update_install_button))
                    }
                }

                is AppUpdateState.Error -> {
                    Text(
                        text = update.message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = viewModel::checkForUpdate,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.update_check_button))
                    }
                }
            }
        }
    }
}
