package com.sailzen.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.navigation.compose.rememberNavController
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.reminder.ReminderActionReceiver
import com.sailzen.app.core.rhythm.QuickCaptureTileService
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState
import com.sailzen.app.ui.components.AppUpdateDialog
import com.sailzen.app.ui.navigation.Routes
import com.sailzen.app.ui.navigation.SailZenNavGraph
import com.sailzen.app.ui.theme.SailZenTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    /** 通知跳入的 reminder_id（-1 表示无） */
    private val reminderIdState = mutableIntStateOf(-1)

    /** 事务通知跳入目标 */
    private val affairIdState = mutableIntStateOf(-1)

    /** 快速捕获磁贴跳入标记 */
    private val openCaptureState = mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleIntent(intent)
        setContent {
            SailZenTheme {
                val navController = rememberNavController()

                // 通知权限请求（API 33+）
                val permissionLauncher = rememberLauncherForActivityResult(
                    ActivityResultContracts.RequestPermission(),
                ) { }
                LaunchedEffect(Unit) {
                    if (Build.VERSION.SDK_INT >= 33 &&
                        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    }
                }

                // 通知跳入：导航到 Inbox 并高亮该提醒
                val highlightId by reminderIdState
                LaunchedEffect(highlightId) {
                    if (highlightId > 0) {
                        navController.navigate(Routes.inbox(highlightId))
                    }
                }

                // 事务通知跳入：导航到事务详情
                val affairId by affairIdState
                LaunchedEffect(affairId) {
                    if (affairId > 0) {
                        navController.navigate(Routes.affairDetail(affairId))
                        affairIdState.intValue = -1
                    }
                }

                SailZenNavGraph(
                    navController = navController,
                    openCapture = openCaptureState.value,
                )

                // 启动静默检查云端 APK 更新（静默失败，不打扰日常使用）
                var updateState by remember { mutableStateOf<AppUpdateState>(AppUpdateState.Idle) }
                val updateScope = rememberCoroutineScope()
                val settings = remember { SettingsManager.get(applicationContext) }

                LaunchedEffect(Unit) {
                    val baseUrl = settings.serverUrl()
                    if (baseUrl.isBlank()) return@LaunchedEffect
                    val token = settings.apiToken()
                    val ignoredCode = settings.ignoredUpdateVersionCode()
                    AppUpdateManager.checkForUpdate(baseUrl, token).onSuccess { release ->
                        if (release != null && release.versionCode != ignoredCode) {
                            updateState = AppUpdateState.UpdateAvailable(release)
                        }
                    }
                }

                AppUpdateDialog(
                    state = updateState,
                    onStartDownload = { release ->
                        updateScope.launch {
                            val baseUrl = settings.serverUrl()
                            val token = settings.apiToken()
                            updateState = AppUpdateState.Downloading(release, 0L, release.size)
                            val result = AppUpdateManager.downloadApk(
                                context = applicationContext,
                                baseUrl = baseUrl,
                                token = token,
                                release = release,
                            ) { read, total ->
                                updateState = AppUpdateState.Downloading(release, read, total)
                            }
                            result.fold(
                                onSuccess = { apkFile ->
                                    val canInstall = AppUpdateManager.canInstallPackages(applicationContext)
                                    updateState = AppUpdateState.ReadyToInstall(
                                        release = release,
                                        apkFile = apkFile,
                                        needsInstallPermission = !canInstall,
                                    )
                                    if (canInstall) {
                                        runCatching {
                                            AppUpdateManager.installApk(this@MainActivity, apkFile)
                                        }.onFailure { err ->
                                            updateState = AppUpdateState.Error("拉起安装器失败: ${err.message}")
                                        }
                                    }
                                },
                                onFailure = { err ->
                                    updateState = AppUpdateState.Error(err.message ?: "下载失败")
                                },
                            )
                        }
                    },
                    onInstallNow = { ready ->
                        if (!AppUpdateManager.canInstallPackages(applicationContext)) {
                            updateState = ready.copy(needsInstallPermission = true)
                            runCatching {
                                startActivity(AppUpdateManager.buildInstallPermissionIntent(this@MainActivity))
                            }
                        } else {
                            updateState = ready.copy(needsInstallPermission = false)
                            runCatching {
                                AppUpdateManager.installApk(this@MainActivity, ready.apkFile)
                            }.onFailure { err ->
                                updateState = AppUpdateState.Error("拉起安装器失败: ${err.message}")
                            }
                        }
                    },
                    onOpenPermissionSettings = {
                        runCatching {
                            startActivity(AppUpdateManager.buildInstallPermissionIntent(this@MainActivity))
                        }
                    },
                    onSkipVersion = { versionCode ->
                        updateScope.launch { settings.saveIgnoredUpdateVersionCode(versionCode) }
                        updateState = AppUpdateState.Idle
                    },
                    onDismiss = { updateState = AppUpdateState.Idle },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        val reminderId = intent?.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1) ?: -1
        if (reminderId > 0) {
            reminderIdState.intValue = reminderId
        }
        val affairId = intent?.getIntExtra(ReminderActionReceiver.EXTRA_AFFAIR_ID, -1) ?: -1
        if (affairId > 0) {
            affairIdState.intValue = affairId
        }
        if (intent?.getBooleanExtra(QuickCaptureTileService.EXTRA_OPEN_CAPTURE, false) == true) {
            openCaptureState.value = true
            // 消费掉，避免重复弹窗
            intent.removeExtra(QuickCaptureTileService.EXTRA_OPEN_CAPTURE)
        }
    }
}
