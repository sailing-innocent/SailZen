package com.sailzen.app.core.update

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.util.Log
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/** PackageInstaller.Session 安装回调事件（供 MainActivity 与 SettingsViewModel 订阅）。 */
sealed interface AppInstallEvent {
    data object PendingUserAction : AppInstallEvent
    data object Success : AppInstallEvent
    data class Failure(val status: Int, val message: String) : AppInstallEvent
}

/**
 * 接收 Android PackageInstaller.Session 提交结果的广播接收器。
 * - STATUS_PENDING_USER_ACTION：拉起系统确认安装页面（不再依赖本应用 FileProvider 存活）；
 * - STATUS_SUCCESS / STATUS_FAILURE*：发射事件给 UI，彻底杜绝静默卡死。
 */
class AppInstallReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "AppInstallReceiver"
        const val ACTION_INSTALL_RESULT = "com.sailzen.app.action.PACKAGE_INSTALL_RESULT"

        private val _events = MutableSharedFlow<AppInstallEvent>(extraBufferCapacity = 8)
        val events: SharedFlow<AppInstallEvent> = _events.asSharedFlow()

        fun mapFailureMessage(status: Int, rawMessage: String?): String = when (status) {
            PackageInstaller.STATUS_FAILURE_ABORTED -> "已取消安装（如需更新请重新点击安装）"
            PackageInstaller.STATUS_FAILURE_BLOCKED -> "安装被系统拦截，请检查系统安全设置"
            PackageInstaller.STATUS_FAILURE_CONFLICT -> "安装包签名或版本与已安装版本冲突，请先卸载旧版后再安装"
            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> "安装包与当前设备架构或系统版本不兼容"
            PackageInstaller.STATUS_FAILURE_INVALID -> "安装包文件损坏或无效，请重新下载"
            PackageInstaller.STATUS_FAILURE_STORAGE -> "设备存储空间不足，请清理空间后重试"
            else -> rawMessage?.takeIf { it.isNotBlank() }?.let { "安装失败：$it" }
                ?: "安装失败（状态码 $status），可尝试下方“系统安装器重试”"
        }
    }

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION_INSTALL_RESULT) return
        val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
        val rawMessage = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
        Log.i(TAG, "PackageInstaller callback status=$status message=$rawMessage")

        when (status) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirmIntent: Intent? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(Intent.EXTRA_INTENT)
                }
                if (confirmIntent != null) {
                    confirmIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    runCatching {
                        context.startActivity(confirmIntent)
                        _events.tryEmit(AppInstallEvent.PendingUserAction)
                    }.onFailure { err ->
                        Log.e(TAG, "Failed to launch confirm intent: ${err.message}", err)
                        _events.tryEmit(
                            AppInstallEvent.Failure(
                                status,
                                "无法拉起系统安装确认页：${err.message ?: "请尝试用系统安装器重试"}",
                            ),
                        )
                    }
                } else {
                    _events.tryEmit(
                        AppInstallEvent.Failure(status, "系统未返回安装确认页，请点击“系统安装器重试”"),
                    )
                }
            }

            PackageInstaller.STATUS_SUCCESS -> {
                _events.tryEmit(AppInstallEvent.Success)
            }

            else -> {
                _events.tryEmit(AppInstallEvent.Failure(status, mapFailureMessage(status, rawMessage)))
            }
        }
    }
}
