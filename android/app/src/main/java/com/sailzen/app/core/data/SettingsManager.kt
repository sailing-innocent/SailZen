package com.sailzen.app.core.data

import android.content.Context
import com.sailzen.app.BuildConfig
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.time.LocalTime
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "sailzen_settings")

/**
 * 设置与凭证（DataStore）：服务器地址、API Token、deviceId（首启生成 UUID）、
 * 安静时段、上次增量同步游标。
 */
class SettingsManager private constructor(private val context: Context) {

    companion object {
        private val KEY_SERVER_URL = stringPreferencesKey("server_url")
        private val KEY_API_TOKEN = stringPreferencesKey("api_token")
        private val KEY_DEVICE_ID = stringPreferencesKey("device_id")
        private val KEY_QUIET_START = stringPreferencesKey("quiet_start") // "HH:mm"
        private val KEY_QUIET_END = stringPreferencesKey("quiet_end") // "HH:mm"
        private val KEY_LAST_SYNC_EPOCH = longPreferencesKey("last_sync_epoch")
        private val KEY_IGNORED_UPDATE_VERSION_CODE = intPreferencesKey("ignored_update_version_code")
        private val KEY_USER_DISPLAY_NAME = stringPreferencesKey("user_display_name")
        private val KEY_USER_SLUG = stringPreferencesKey("user_slug")
        private val KEY_LAST_INBOX_SYNC_SEQ = longPreferencesKey("last_inbox_sync_seq")

        const val DEFAULT_QUIET_START = "23:00"
        const val DEFAULT_QUIET_END = "08:00"

        @Volatile
        private var instance: SettingsManager? = null

        fun get(context: Context): SettingsManager =
            instance ?: synchronized(this) {
                instance ?: SettingsManager(context.applicationContext).also { instance = it }
            }
    }

    // ------------------------------------------------------------------
    // Flows（UI 订阅）
    // ------------------------------------------------------------------

    val serverUrlFlow: Flow<String> =
        context.dataStore.data.map { prefs ->
            resolveEffectiveServerUrl(prefs[KEY_SERVER_URL])
        }

    val apiTokenFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_API_TOKEN] ?: "" }

    val deviceIdFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_DEVICE_ID] ?: "" }

    val quietStartFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_QUIET_START] ?: DEFAULT_QUIET_START }

    val quietEndFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_QUIET_END] ?: DEFAULT_QUIET_END }

    val userDisplayNameFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_USER_DISPLAY_NAME] ?: "SailZen Owner" }

    val userSlugFlow: Flow<String> =
        context.dataStore.data.map { it[KEY_USER_SLUG] ?: "owner" }

    // ------------------------------------------------------------------
    // 读取
    // ------------------------------------------------------------------

    suspend fun serverUrl(): String =
        resolveEffectiveServerUrl(context.dataStore.data.first()[KEY_SERVER_URL])

    /**
     * 解析最终生效的服务器地址：
     * - Release 锁定模式下始终使用构建期注入的 BuildConfig.SERVER_URL，
     *   避免旧版安装或 Android AutoBackup 遗留的空串/旧地址导致永久连不上。
     * - Debug 模式下若 DataStore 未配置或为空，则回退默认地址。
     */
    private fun resolveEffectiveServerUrl(stored: String?): String {
        val fallback = defaultServerUrl().trim().trimEnd('/')
        if (BuildConfig.SERVER_URL_LOCKED && fallback.isNotBlank()) {
            return fallback
        }
        return stored?.trim()?.trimEnd('/')?.takeIf { it.isNotBlank() } ?: fallback
    }

    suspend fun apiToken(): String =
        context.dataStore.data.first()[KEY_API_TOKEN] ?: ""

    /**
     * 获取稳定设备标识（Device Identity v2）：
     * - 优先采用基于 ANDROID_ID + 厂商/型号派生的确定性 ID，卸载重装不漂移；
     * - 无法获取时回退 DataStore 持久化 UUID。
     */
    suspend fun getOrCreateDeviceId(): String {
        val stable = DeviceIdentity.resolve(context).stableDeviceId
        val existing = context.dataStore.data.first()[KEY_DEVICE_ID]
        if (!stable.isNullOrBlank()) {
            if (existing != stable) {
                context.dataStore.edit { it[KEY_DEVICE_ID] = stable }
            }
            return stable
        }
        if (!existing.isNullOrBlank()) return existing
        val id = UUID.randomUUID().toString()
        context.dataStore.edit { it[KEY_DEVICE_ID] = id }
        return id
    }

    suspend fun quietStart(): String =
        context.dataStore.data.first()[KEY_QUIET_START] ?: DEFAULT_QUIET_START

    suspend fun quietEnd(): String =
        context.dataStore.data.first()[KEY_QUIET_END] ?: DEFAULT_QUIET_END

    suspend fun lastSyncEpoch(): Long =
        context.dataStore.data.first()[KEY_LAST_SYNC_EPOCH] ?: 0L

    suspend fun ignoredUpdateVersionCode(): Int =
        context.dataStore.data.first()[KEY_IGNORED_UPDATE_VERSION_CODE] ?: 0

    suspend fun lastInboxSyncSeq(): Long =
        context.dataStore.data.first()[KEY_LAST_INBOX_SYNC_SEQ] ?: 0L

    suspend fun userDisplayName(): String =
        context.dataStore.data.first()[KEY_USER_DISPLAY_NAME] ?: "SailZen Owner"

    // ------------------------------------------------------------------
    // 写入
    // ------------------------------------------------------------------

    suspend fun saveServerConfig(serverUrl: String, apiToken: String) {
        val url = if (BuildConfig.SERVER_URL_LOCKED) {
            defaultServerUrl()
        } else {
            serverUrl.trim().trimEnd('/')
        }
        context.dataStore.edit {
            it[KEY_SERVER_URL] = url
            it[KEY_API_TOKEN] = apiToken.trim()
        }
    }

    suspend fun saveQuietHours(start: String, end: String) {
        context.dataStore.edit {
            it[KEY_QUIET_START] = start.trim().ifBlank { DEFAULT_QUIET_START }
            it[KEY_QUIET_END] = end.trim().ifBlank { DEFAULT_QUIET_END }
        }
    }

    suspend fun saveLastSyncEpoch(epochMillis: Long) {
        context.dataStore.edit { it[KEY_LAST_SYNC_EPOCH] = epochMillis }
    }

    suspend fun saveIgnoredUpdateVersionCode(versionCode: Int) {
        context.dataStore.edit { it[KEY_IGNORED_UPDATE_VERSION_CODE] = versionCode }
    }

    suspend fun saveLastInboxSyncSeq(seq: Long) {
        context.dataStore.edit { it[KEY_LAST_INBOX_SYNC_SEQ] = seq }
    }

    suspend fun saveUserProfileLocal(displayName: String, slug: String = "owner") {
        context.dataStore.edit {
            if (displayName.isNotBlank()) it[KEY_USER_DISPLAY_NAME] = displayName.trim()
            if (slug.isNotBlank()) it[KEY_USER_SLUG] = slug.trim()
        }
    }

    // ------------------------------------------------------------------
    // 安静时段
    // ------------------------------------------------------------------

    /** 当前是否处于安静时段（支持跨午夜，如 23:00–08:00） */
    suspend fun isQuietNow(): Boolean = isQuietNow(quietStart(), quietEnd())

    fun isQuietNow(start: String, end: String): Boolean {
        val s = parseHm(start) ?: return false
        val e = parseHm(end) ?: return false
        val now = LocalTime.now()
        return if (s <= e) {
            // 同日窗口，如 12:00–14:00
            !now.isBefore(s) && now.isBefore(e)
        } else {
            // 跨午夜窗口，如 23:00–08:00
            !now.isBefore(s) || now.isBefore(e)
        }
    }

    private fun parseHm(value: String): LocalTime? =
        try {
            LocalTime.parse(value.trim())
        } catch (_: Exception) {
            null
        }

    /** 返回当前构建类型默认服务器地址；release 构建中被锁定，禁止用户修改。 */
    fun defaultServerUrl(): String = BuildConfig.SERVER_URL

    /** 服务器地址是否已被发布包锁定。 */
    fun isServerUrlLocked(): Boolean = BuildConfig.SERVER_URL_LOCKED
}
