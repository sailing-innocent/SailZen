package com.sailzen.app.core.tick

import android.net.Uri
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 接收来自系统分享菜单（ACTION_SEND 图片分享）的待识图图片。
 * MainActivity 收到分享 Intent 后立即将图片拷贝至应用缓存并发布到此通道，
 * 随后导航至 HealthCoachScreen，由 ViewModel 自动消费并触发识图。
 */
data class SharedImagePayload(
    val uri: Uri,
    val note: String = "",
    val sourceChannel: String = "android_share",
    val receivedAtMs: Long = System.currentTimeMillis(),
)

object SharedImageInbox {
    private val _pending = MutableStateFlow<SharedImagePayload?>(null)
    val pending: StateFlow<SharedImagePayload?> = _pending.asStateFlow()

    fun offer(payload: SharedImagePayload) {
        _pending.value = payload
    }

    fun consume(): SharedImagePayload? {
        val current = _pending.value
        _pending.value = null
        return current
    }
}
