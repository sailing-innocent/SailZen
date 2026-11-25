package com.sailzen.app.core.update

import android.app.PendingIntent
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.util.Log
import androidx.core.content.FileProvider
import com.sailzen.app.BuildConfig
import com.sailzen.app.core.bg.ReminderService
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.AppReleaseDto
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import retrofit2.HttpException

/** 应用内 OTA 更新状态机。 */
sealed interface AppUpdateState {
    data object Idle : AppUpdateState
    data object Checking : AppUpdateState
    data class UpToDate(val versionName: String, val versionCode: Int) : AppUpdateState
    data class UpdateAvailable(val release: AppReleaseDto) : AppUpdateState
    data class Downloading(
        val release: AppReleaseDto,
        val bytesRead: Long,
        val totalBytes: Long,
    ) : AppUpdateState
    data class ReadyToInstall(
        val release: AppReleaseDto,
        val apkFile: File,
        val needsInstallPermission: Boolean = false,
    ) : AppUpdateState
    data class Installing(
        val release: AppReleaseDto,
        val apkFile: File,
        val hint: String = "正在写入系统安装会话…",
    ) : AppUpdateState
    data class Error(val message: String) : AppUpdateState
}

/**
 * SailZen Android 应用内 OTA 更新管理器：
 * 1. 拉取 /api/v1/app/release/latest 并按 versionCode 判断是否有新版本；
 * 2. 流式下载 APK 至 cacheDir/updates/ 并校验 SHA-256；
 * 3. 通过 FileProvider 拉起系统原生安装器覆盖升级。
 */
object AppUpdateManager {

    private const val TAG = "AppUpdateManager"
    private const val UPDATES_SUBDIR = "updates"
    private const val APK_MIME = "application/vnd.android.package-archive"
    const val AUTO_CHECK_INTERVAL_MS = 10 * 60_000L

    /** 判断是否应触发前台自动检查更新（首次立即检查，之后按间隔节流避免打扰）。 */
    fun shouldAutoCheckUpdate(
        lastCheckMs: Long,
        nowMs: Long,
        minIntervalMs: Long = AUTO_CHECK_INTERVAL_MS,
    ): Boolean = lastCheckMs <= 0L || (nowMs - lastCheckMs) >= minIntervalMs

    /** 判断远端版本是否高于本地安装版本。 */
    fun isUpdateAvailable(
        remoteVersionCode: Int,
        currentVersionCode: Int = BuildConfig.VERSION_CODE,
    ): Boolean = remoteVersionCode > currentVersionCode

    /** 拼接完整 APK 下载 URL。 */
    fun resolveDownloadUrl(baseUrl: String, release: AppReleaseDto): String {
        val normalized = ApiClient.normalizeBaseUrl(baseUrl)
        val path = release.downloadPath.trim().ifBlank {
            "/api/v1/app/release/download/${release.fileName}"
        }
        return if (path.startsWith("http://") || path.startsWith("https://")) {
            path
        } else {
            val cleanPath = if (path.startsWith("/")) path else "/$path"
            "$normalized$cleanPath"
        }
    }

    /** 计算文件 SHA-256 十六进制（小写）。 */
    fun sha256Hex(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buf)
                if (read <= 0) break
                digest.update(buf, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /** 格式化文件体积（用于 UI 展示）。 */
    fun formatFileSize(bytes: Long): String {
        if (bytes <= 0L) return "0 B"
        val kb = 1024.0
        val mb = kb * 1024.0
        return when {
            bytes >= mb -> "%.1f MB".format(bytes / mb)
            bytes >= kb -> "%.1f KB".format(bytes / kb)
            else -> "$bytes B"
        }
    }

    /**
     * 检查远端是否有更新。
     * 返回 Result.success(release) 表示发现新版本；Result.success(null) 表示已是最新（或云端尚未发布包）。
     */
    suspend fun checkForUpdate(
        baseUrl: String,
        token: String,
        currentVersionCode: Int = BuildConfig.VERSION_CODE,
    ): Result<AppReleaseDto?> = withContext(Dispatchers.IO) {
        if (baseUrl.isBlank()) {
            return@withContext Result.failure(IllegalStateException("未配置服务器地址"))
        }
        try {
            val latest = ApiClient.appUpdateApi(baseUrl, token).getLatestRelease()
            if (isUpdateAvailable(latest.versionCode, currentVersionCode)) {
                Result.success(latest)
            } else {
                Result.success(null)
            }
        } catch (e: HttpException) {
            if (e.code() == 404) {
                Result.success(null)
            } else {
                Result.failure(IOException("检查更新失败 (HTTP ${e.code()})", e))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 流式下载 APK 至私有缓存目录，并在落盘后执行 SHA-256 完整性校验。
     * 若本地已缓存同文件名且 SHA-256 匹配的 APK，则直接复用。
     */
    suspend fun downloadApk(
        context: Context,
        baseUrl: String,
        token: String,
        release: AppReleaseDto,
        onProgress: (bytesRead: Long, totalBytes: Long) -> Unit,
    ): Result<File> = withContext(Dispatchers.IO) {
        val safeName = File(release.fileName).name
        if (!safeName.endsWith(".apk")) {
            return@withContext Result.failure(IllegalArgumentException("非法 APK 文件名: $safeName"))
        }

        val updatesDir = File(context.cacheDir, UPDATES_SUBDIR).apply { mkdirs() }
        val targetFile = File(updatesDir, safeName)
        val partFile = File(updatesDir, "$safeName.part")

        // 清理非目标版本的旧缓存文件，避免占用存储空间
        updatesDir.listFiles()?.forEach { f ->
            if (f.name != safeName) {
                f.delete()
            }
        }

        // 若本地已有同名 APK 且 SHA-256 匹配，直接复用
        val expectedSha = release.sha256.trim().lowercase()
        if (targetFile.isFile && expectedSha.isNotEmpty()) {
            val existingSha = runCatching { sha256Hex(targetFile) }.getOrNull()
            if (existingSha == expectedSha) {
                val len = targetFile.length()
                onProgress(len, len)
                return@withContext Result.success(targetFile)
            }
            targetFile.delete()
        }

        val url = resolveDownloadUrl(baseUrl, release)
        val request = Request.Builder().url(url).get().build()
        val client = ApiClient.downloadClient(token)

        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    return@withContext Result.failure(
                        IOException("下载失败 (HTTP ${response.code})"),
                    )
                }
                val body = response.body
                    ?: return@withContext Result.failure(IOException("服务端返回空响应体"))

                val total = body.contentLength().takeIf { it > 0L } ?: release.size
                val digest = MessageDigest.getInstance("SHA-256")
                var bytesRead = 0L
                var lastEmit = 0L

                body.byteStream().use { input ->
                    partFile.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val n = input.read(buffer)
                            if (n <= 0) break
                            output.write(buffer, 0, n)
                            digest.update(buffer, 0, n)
                            bytesRead += n
                            val now = System.currentTimeMillis()
                            if (now - lastEmit >= 120L || (total > 0L && bytesRead >= total)) {
                                onProgress(bytesRead, total)
                                lastEmit = now
                            }
                        }
                    }
                }
                onProgress(bytesRead, total.coerceAtLeast(bytesRead))

                if (expectedSha.isNotEmpty()) {
                    val actualSha = digest.digest().joinToString("") { "%02x".format(it) }
                    if (actualSha != expectedSha) {
                        partFile.delete()
                        return@withContext Result.failure(
                            IOException("APK 校验失败（SHA-256 不匹配），请重试下载"),
                        )
                    }
                }

                if (targetFile.exists()) {
                    targetFile.delete()
                }
                if (!partFile.renameTo(targetFile)) {
                    partFile.copyTo(targetFile, overwrite = true)
                    partFile.delete()
                }
                Result.success(targetFile)
            }
        } catch (e: Exception) {
            partFile.delete()
            Result.failure(e)
        }
    }

    /** 检查是否已获得“安装未知应用”权限（minSdk = 26，原生支持）。 */
    fun canInstallPackages(context: Context): Boolean =
        context.packageManager.canRequestPackageInstalls()

    /** 构造跳转系统“允许安装未知应用”设置页的 Intent。 */
    fun buildInstallPermissionIntent(context: Context): Intent =
        Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:${context.packageName}"),
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

    /**
     * 推荐安装方式（PackageInstaller.Session 流式安装）：
     * 1. 先将完整 APK 写入系统受管安装会话（/data/app/vmdl*.tmp），彻底解除系统安装器对本应用 FileProvider 存活的依赖；
     * 2. 提交安装前优雅停止常驻前台服务 ReminderService，避免 MagicOS / ColorOS 自我覆盖时卡死在「正在安装」；
     * 3. 由 [AppInstallReceiver] 接收 STATUS_PENDING_USER_ACTION 并拉起系统确认安装弹窗。
     */
    suspend fun installApkViaSession(context: Context, apkFile: File): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                if (!apkFile.isFile || apkFile.length() <= 0L) {
                    error("安装包文件不存在或为空，请重新下载")
                }
                val appContext = context.applicationContext
                val installer = appContext.packageManager.packageInstaller
                val params = PackageInstaller.SessionParams(
                    PackageInstaller.SessionParams.MODE_FULL_INSTALL,
                ).apply {
                    setSize(apkFile.length())
                    setAppPackageName(appContext.packageName)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                        setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)
                    }
                }
                val sessionId = installer.createSession(params)
                val session = installer.openSession(sessionId)
                try {
                    session.openWrite("sailzen_update.apk", 0L, apkFile.length()).use { out ->
                        apkFile.inputStream().use { input ->
                            val buf = ByteArray(64 * 1024)
                            while (true) {
                                val n = input.read(buf)
                                if (n <= 0) break
                                out.write(buf, 0, n)
                            }
                        }
                        session.fsync(out)
                    }
                    // 提交前优雅停止常驻前台服务，避免国产 ROM 自我覆盖安装时挂起卡死
                    runCatching { ReminderService.stop(appContext) }

                    val callbackIntent = Intent(appContext, AppInstallReceiver::class.java).apply {
                        action = AppInstallReceiver.ACTION_INSTALL_RESULT
                    }
                    val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                            PendingIntent.FLAG_MUTABLE
                        } else {
                            0
                        }
                    val pendingIntent = PendingIntent.getBroadcast(
                        appContext,
                        sessionId,
                        callbackIntent,
                        flags,
                    )
                    session.commit(pendingIntent.intentSender)
                } catch (e: Exception) {
                    runCatching { session.abandon() }
                    throw e
                } finally {
                    runCatching { session.close() }
                }
            }.onFailure { err ->
                Log.w(TAG, "installApkViaSession failed: ${err.message}", err)
            }
        }

    /** 兜底方式：通过 FileProvider + ACTION_VIEW 唤起系统原生 APK 安装器（附带 ClipData 授权）。 */
    fun installApk(context: Context, apkFile: File) {
        val appContext = context.applicationContext
        runCatching { ReminderService.stop(appContext) }
        val uri = FileProvider.getUriForFile(
            appContext,
            "${appContext.packageName}.fileprovider",
            apkFile,
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, APK_MIME)
            clipData = ClipData.newRawUri("apk", uri)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(intent)
    }
}
