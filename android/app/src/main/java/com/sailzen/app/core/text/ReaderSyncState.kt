package com.sailzen.app.core.text

/**
 * 阅读模块同步状态（纯数据，JVM 可测）。
 *
 * 状态推导优先级（UI 以此展示同步状态 chip）：
 * 1. offline     —— 无网络（不论是否正在重试）
 * 2. syncing     —— 有同步任务在飞
 * 3. error       —— 在线空闲但最近一次同步失败
 * 4. synced      —— 在线空闲且最近同步成功
 * 5. idle        —— 在线但从未同步过（通常是新配置）
 */
data class ReaderSyncState(
    val online: Boolean = false,
    val syncing: Boolean = false,
    val lastSyncAtMillis: Long? = null,
    val lastError: String? = null,
) {
    sealed interface Display {
        data object Offline : Display
        data object Syncing : Display
        data class Error(val message: String?) : Display
        data class Synced(val atMillis: Long) : Display
        data object Idle : Display
    }

    val display: Display
        get() = when {
            !online -> Display.Offline
            syncing -> Display.Syncing
            lastError != null -> Display.Error(lastError)
            lastSyncAtMillis != null -> Display.Synced(lastSyncAtMillis)
            else -> Display.Idle
        }
}

/**
 * 同步状态归约器：同一时刻只统计一个同步任务（串行同步足够，避免弱网并发打爆）。
 */
class ReaderSyncStateReducer(private val clockMillis: () -> Long = System::currentTimeMillis) {

    private var state = ReaderSyncState()

    /** 网络状态变化：离线时清空 syncing（任务必然失败结束）与 error（恢复在线后重新尝试） */
    @Synchronized
    fun onOnlineChanged(online: Boolean): ReaderSyncState {
        state = state.copy(
            online = online,
            syncing = if (online) state.syncing else false,
            lastError = if (online) null else state.lastError,
        )
        return state
    }

    @Synchronized
    fun onSyncStart(): ReaderSyncState {
        state = state.copy(syncing = true)
        return state
    }

    @Synchronized
    fun onSyncSuccess(): ReaderSyncState {
        state = state.copy(syncing = false, lastSyncAtMillis = clockMillis(), lastError = null)
        return state
    }

    @Synchronized
    fun onSyncFailure(message: String?): ReaderSyncState {
        state = state.copy(syncing = false, lastError = message)
        return state
    }

    @Synchronized
    fun current(): ReaderSyncState = state
}
