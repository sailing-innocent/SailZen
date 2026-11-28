package com.sailzen.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.rememberNavController
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.reminder.ReminderActionReceiver
import com.sailzen.app.core.rhythm.QuickCaptureTileService
import com.sailzen.app.core.tick.SharedImageInbox
import com.sailzen.app.core.tick.SharedImagePayload
import com.sailzen.app.core.update.AppInstallEvent
import com.sailzen.app.core.update.AppInstallReceiver
import com.sailzen.app.core.update.AppUpdateManager
import com.sailzen.app.core.update.AppUpdateState
import com.sailzen.app.core.user.UserInboxRepository
import com.sailzen.app.ui.components.AppUpdateDialog
import com.sailzen.app.ui.navigation.Routes
import com.sailzen.app.ui.navigation.SailZenNavGraph
import com.sailzen.app.ui.theme.SailZenTheme
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    /** 通知跳入的 reminder_id（-1 表示无） */
    private val reminderIdState = mutableIntStateOf(-1)

    /** 通知跳入的目标深链与域（用于直达规划/健康/记账 Tab） */
    private val deepLinkTargetState = mutableStateOf<Pair<String, String>?>(null)

    /** 事务通知跳入目标 */
    private val affairIdState = mutableIntStateOf(-1)

    /** 快速捕获磁贴跳入标记 */
    private val openCaptureState = mutableStateOf(false)

    /** 系统分享图片跳入 AI 教练页的时间戳触发器 */
    private val openCoachForShareToken = mutableLongStateOf(0L)

    /** 前台恢复时间戳触发器（保活切回前台时节流检查云端 OTA 更新） */
    private val foregroundResumeToken = mutableLongStateOf(0L)
    private var lastAutoUpdateCheckMs: Long = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
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

                // 通知跳入：优先按 deepLink / domain 路由至对应业务 Tab，未携带深链时落 Inbox 高亮
                val highlightId by reminderIdState
                val deepLinkTarget by deepLinkTargetState
                LaunchedEffect(highlightId, deepLinkTarget) {
                    val dl = deepLinkTarget
                    if (dl != null) {
                        val (domain, deepLink) = dl
                        val route = when {
                            deepLink.startsWith("/money") || domain == "finance" -> Routes.MONEY
                            deepLink.startsWith("/rhythm") || domain == "rhythm" -> Routes.PLAN
                            deepLink.startsWith("/health/coach") || domain == "health" -> Routes.HEALTH_COACH
                            deepLink.startsWith("/health") -> Routes.HEALTH
                            else -> Routes.inbox(if (highlightId > 0) highlightId else -1)
                        }
                        navController.navigate(route) {
                            launchSingleTop = true
                        }
                        deepLinkTargetState.value = null
                        reminderIdState.intValue = -1
                    } else if (highlightId > 0) {
                        navController.navigate(Routes.inbox(highlightId))
                        reminderIdState.intValue = -1
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

                // 系统分享图片跳入：直达 SailTick AI 教练页自动识图
                val shareToken by openCoachForShareToken
                LaunchedEffect(shareToken) {
                    if (shareToken > 0L) {
                        navController.navigate(Routes.HEALTH_COACH) {
                            launchSingleTop = true
                        }
                        openCoachForShareToken.longValue = 0L
                    }
                }

                SailZenNavGraph(
                    navController = navController,
                    openCapture = openCaptureState.value,
                )

                // 前台恢复静默检查云端 APK 更新（冷启动立即检查，保活切回前台按 10 分钟节流检查）
                var updateState by remember { mutableStateOf<AppUpdateState>(AppUpdateState.Idle) }
                val updateScope = rememberCoroutineScope()
                val settings = remember { SettingsManager.get(applicationContext) }
                val resumeTick by foregroundResumeToken

                // 订阅 PackageInstaller.Session 安装结果回调
                LaunchedEffect(Unit) {
                    AppInstallReceiver.events.collect { ev ->
                        when (ev) {
                            is AppInstallEvent.PendingUserAction -> {
                                val cur = updateState
                                if (cur is AppUpdateState.Installing) {
                                    updateState = cur.copy(hint = "已提交至系统安装器，请在系统弹窗中确认安装")
                                }
                            }
                            is AppInstallEvent.Success -> {
                                updateState = AppUpdateState.Idle
                            }
                            is AppInstallEvent.Failure -> {
                                updateState = AppUpdateState.Error(ev.message)
                                ReminderService.ensureStarted(applicationContext)
                            }
                        }
                    }
                }

                LaunchedEffect(resumeTick) {
                    // 若刚从“安装未知应用”权限设置页返回，刷新权限状态
                    val cur = updateState
                    if (cur is AppUpdateState.ReadyToInstall && cur.needsInstallPermission) {
                        if (AppUpdateManager.canInstallPackages(applicationContext)) {
                            updateState = cur.copy(needsInstallPermission = false)
                        }
                    }
                    // 已在展示/下载/安装流程中时不再重复打扰
                    if (updateState !is AppUpdateState.Idle) return@LaunchedEffect

                    val nowMs = System.currentTimeMillis()
                    if (!AppUpdateManager.shouldAutoCheckUpdate(lastAutoUpdateCheckMs, nowMs)) {
                        return@LaunchedEffect
                    }
                    val baseUrl = settings.serverUrl()
                    if (baseUrl.isBlank()) return@LaunchedEffect
                    val token = settings.apiToken()
                    val ignoredCode = settings.ignoredUpdateVersionCode()
                    lastAutoUpdateCheckMs = nowMs
                    AppUpdateManager.checkForUpdate(baseUrl, token).onSuccess { release ->
                        if (release != null && release.versionCode != ignoredCode) {
                            updateState = AppUpdateState.UpdateAvailable(release)
                        }
                    }
                }

                fun launchSessionInstall(release: com.sailzen.app.core.network.AppReleaseDto, apkFile: File) {
                    updateScope.launch {
                        updateState = AppUpdateState.Installing(
                            release = release,
                            apkFile = apkFile,
                            hint = "正在写入系统安装会话，稍后弹出系统确认框…",
                        )
                        AppUpdateManager.installApkViaSession(this@MainActivity, apkFile)
                            .onFailure { err ->
                                runCatching {
                                    AppUpdateManager.installApk(this@MainActivity, apkFile)
                                    updateState = AppUpdateState.ReadyToInstall(
                                        release = release,
                                        apkFile = apkFile,
                                        needsInstallPermission = false,
                                    )
                                }.onFailure { fallbackErr ->
                                    updateState = AppUpdateState.Error(
                                        "拉起安装器失败: ${fallbackErr.message ?: err.message}",
                                    )
                                }
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
                                    if (canInstall) {
                                        launchSessionInstall(release, apkFile)
                                    } else {
                                        updateState = AppUpdateState.ReadyToInstall(
                                            release = release,
                                            apkFile = apkFile,
                                            needsInstallPermission = true,
                                        )
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
                            launchSessionInstall(ready.release, ready.apkFile)
                        }
                    },
                    onInstallFallback = { apkFile ->
                        runCatching {
                            AppUpdateManager.installApk(this@MainActivity, apkFile)
                        }.onFailure { err ->
                            updateState = AppUpdateState.Error("拉起安装器失败: ${err.message}")
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

    override fun onStart() {
        super.onStart()
        foregroundResumeToken.longValue = System.currentTimeMillis()
        // 前台生命周期保证 ReminderService 一定能正常拉起，并静默引导 UserProfile 与对账收件箱
        lifecycleScope.launch(Dispatchers.IO) {
            if (SettingsManager.get(applicationContext).serverUrl().isNotBlank()) {
                ReminderService.ensureStarted(applicationContext)
                val userInbox = UserInboxRepository.get(applicationContext)
                userInbox.bootstrapSilently()
                userInbox.syncInbox(full = false)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        val reminderId = intent?.getIntExtra(ReminderActionReceiver.EXTRA_REMINDER_ID, -1) ?: -1
        val deepLink = intent?.getStringExtra(ReminderActionReceiver.EXTRA_DEEP_LINK).orEmpty()
        val domain = intent?.getStringExtra(ReminderActionReceiver.EXTRA_DOMAIN).orEmpty()
        if (deepLink.isNotBlank() || domain in setOf("health", "rhythm", "finance")) {
            deepLinkTargetState.value = domain to deepLink
        }
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
        // 处理系统「分享图片到 SailZen」（ACTION_SEND image/*）
        if (intent?.action == Intent.ACTION_SEND && intent.type?.startsWith("image/") == true) {
            val streamUri: Uri? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(Intent.EXTRA_STREAM)
            }
            val sharedText = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty().trim()
            if (streamUri != null) {
                // 立即清除 action，防止配置变更重复触发
                intent.action = Intent.ACTION_MAIN
                lifecycleScope.launch(Dispatchers.IO) {
                    val cachedUri = copySharedImageToCache(streamUri) ?: streamUri
                    SharedImageInbox.offer(
                        SharedImagePayload(
                            uri = cachedUri,
                            note = sharedText,
                            sourceChannel = "android_share",
                        ),
                    )
                    openCoachForShareToken.longValue = System.currentTimeMillis()
                }
            }
        }
    }

    private fun copySharedImageToCache(sourceUri: Uri): Uri? {
        return runCatching {
            val dir = File(cacheDir, "shared_intake").apply { mkdirs() }
            // 清理较旧缓存，仅保留最近 10 张
            dir.listFiles()?.sortedByDescending { it.lastModified() }?.drop(10)?.forEach { it.delete() }
            val outFile = File(dir, "share_${System.currentTimeMillis()}.jpg")
            contentResolver.openInputStream(sourceUri)?.use { input ->
                outFile.outputStream().use { output -> input.copyTo(output) }
            } ?: return null
            FileProvider.getUriForFile(this, "${packageName}.fileprovider", outFile)
        }.getOrNull()
    }
}
