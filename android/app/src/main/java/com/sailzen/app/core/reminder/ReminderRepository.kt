package com.sailzen.app.core.reminder

import android.content.Context
import android.os.Build
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.CachedReminder
import com.sailzen.app.core.data.db.CachedSourceConfig
import com.sailzen.app.core.data.db.PendingFeedback
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.ReminderApi
import com.sailzen.app.core.network.dto.AckRequest
import com.sailzen.app.core.network.dto.DeviceRegisterRequest
import com.sailzen.app.core.network.dto.FeedbackRequest
import com.sailzen.app.core.network.dto.ReminderDto
import com.sailzen.app.core.network.dto.SourceConfigDto
import com.sailzen.app.core.network.dto.SummaryDto
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

/**
 * 提醒核心协调者：
 * - processDelivered：WS 收到 reminder.delivered → 落缓存 + 弹通知 + 回 ACK
 * - sendFeedback：在线直发 / 失败入 pending_feedback 离线队列
 * - flushPendingFeedback：离线反馈批量上报
 * - syncPending：GET /pending 补偿对账 + 未来 PENDING 排本地闹钟
 */
class ReminderRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "ReminderRepository"

        @Volatile
        private var instance: ReminderRepository? = null

        fun get(context: Context): ReminderRepository =
            instance ?: synchronized(this) {
                instance ?: ReminderRepository(context.applicationContext).also { instance = it }
            }

        /** 当前时间 ISO-8601（秒精度，与服务端 naive 本地时间口径一致） */
        fun nowIso(): String = LocalDateTime.now().withNano(0).toString()

        /** 解析服务端 ISO 时间（兼容带/不带毫秒） */
        fun parseServerTime(value: String?): LocalDateTime? {
            if (value.isNullOrBlank()) return null
            return try {
                LocalDateTime.parse(value)
            } catch (_: Exception) {
                null
            }
        }

        /** snooze option → 触发时刻（与服务端换算表一致，用于离线兜底闹钟） */
        fun computeSnoozeMillis(option: String): Long? {
            val now = LocalDateTime.now()
            val target = when (option) {
                "15m" -> now.plusMinutes(15)
                "1h" -> now.plusHours(1)
                "tonight" -> {
                    val tonight = now.withHour(20).withMinute(0).withSecond(0).withNano(0)
                    if (tonight.isAfter(now)) tonight else now.plusHours(1)
                }
                "tomorrow" -> now.plusDays(1).withHour(9).withMinute(0).withSecond(0).withNano(0)
                else -> return null
            }
            return target.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        }

        fun ReminderDto.toCached(): CachedReminder = CachedReminder(
            id = id,
            type = type,
            title = title,
            body = body,
            priority = priority,
            state = state,
            triggerTime = triggerTime,
            expireAfterMinutes = expireAfterMinutes,
            snoozeCount = snoozeCount,
            payloadJson = payload.toString(),
            updatedAt = updatedAt ?: nowIso(),
        )

        fun SourceConfigDto.toCached(): CachedSourceConfig = CachedSourceConfig(
            source = source,
            sourceType = sourceType,
            enabled = enabled,
            defaultPriority = defaultPriority,
            allowedChannelsJson = Json.Default.encodeToString(allowedChannels),
            quietHoursOverrideJson = quietHoursOverride?.let { Json.Default.encodeToString(it) },
            description = description,
            updatedAt = updatedAt ?: nowIso(),
        )
    }

    private val settings = SettingsManager.get(context)
    private val db = AppDatabase.get(context)
    private val json = Json { ignoreUnknownKeys = true }

    // ------------------------------------------------------------------
    // 订阅（UI）
    // ------------------------------------------------------------------

    fun observeActive(): Flow<List<CachedReminder>> = db.reminderDao().observeActive()

    fun observeQueuedFeedbackCount(): Flow<Int> = db.feedbackDao().observeCount()

    fun observeSourceConfigs(): Flow<List<CachedSourceConfig>> = db.sourceConfigDao().observeAll()

    suspend fun getSourceConfig(source: String): CachedSourceConfig? = db.sourceConfigDao().bySource(source)

    /** 从服务端拉取全部 source-config，覆盖本地缓存，返回拉取条数 */
    suspend fun syncSourceConfigs(): Int {
        val api = apiOrNull() ?: return 0
        return try {
            val list = api.sourceConfigs()
            db.sourceConfigDao().upsertAll(list.map { it.toCached() })
            list.size
        } catch (e: Exception) {
            Log.w(TAG, "syncSourceConfigs failed: ${e.message}")
            0
        }
    }

    suspend fun upsertSourceConfig(dto: SourceConfigDto): SourceConfigDto? {
        val api = apiOrNull() ?: return null
        return try {
            val result = api.upsertSourceConfig(dto)
            db.sourceConfigDao().upsert(result.toCached())
            result
        } catch (e: Exception) {
            Log.w(TAG, "upsertSourceConfig failed: ${e.message}")
            null
        }
    }

    /** 服务端没有配置时的兜底规则 */
    suspend fun defaultSourceConfig(source: String): CachedSourceConfig {
        val isRhythm = source.startsWith("rhythm.")
        val allowed = if (isRhythm) {
            mapOf("notification" to true, "popup" to false, "alarm" to false, "aod" to true)
        } else {
            mapOf("notification" to true, "popup" to true, "alarm" to true, "aod" to true)
        }
        return CachedSourceConfig(
            source = source,
            sourceType = if (isRhythm) "rhythm" else "",
            enabled = true,
            defaultPriority = "normal",
            allowedChannelsJson = json.encodeToString(allowed),
            quietHoursOverrideJson = null,
            description = "",
            updatedAt = nowIso(),
        )
    }

    /** 同步提醒 + 来源配置，返回 pending 条数 */
    suspend fun syncAll(): Int {
        val n = syncPending()
        syncSourceConfigs()
        return n
    }

    // ------------------------------------------------------------------
    // 基础
    // ------------------------------------------------------------------

    suspend fun serverConfigured(): Boolean = settings.serverUrl().isNotBlank()

    private suspend fun apiOrNull(): ReminderApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.api(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "api build failed: ${e.message}")
            null
        }
    }

    suspend fun registerDevice(): Boolean {
        val api = apiOrNull() ?: return false
        return try {
            api.registerDevice(
                DeviceRegisterRequest(
                    deviceId = settings.getOrCreateDeviceId(),
                    deviceName = Build.MODEL ?: "android",
                    appVersion = appVersion(),
                )
            )
            true
        } catch (e: Exception) {
            Log.w(TAG, "registerDevice failed: ${e.message}")
            false
        }
    }

    private fun appVersion(): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
    } catch (_: Exception) {
        ""
    }

    // ------------------------------------------------------------------
    // WS 投递处理
    // ------------------------------------------------------------------

    suspend fun processDelivered(dto: ReminderDto) {
        db.reminderDao().upsert(dto.toCached())
        // 已投递：取消该提醒的本地兜底闹钟
        AlarmScheduler.cancel(context, dto.id)
        val sourceConfig = getSourceConfig(dto.source) ?: defaultSourceConfig(dto.source)
        notifyFor(dto.id, dto.title, dto.body, dto.priority, dto.source, sourceConfig)
        // 投递确认（失败不阻塞：服务端由轮询 /pending 兜回）
        try {
            apiOrNull()?.ack(
                AckRequest(
                    reminderId = dto.id,
                    deviceId = settings.getOrCreateDeviceId(),
                    clientEventTs = nowIso(),
                )
            )
        } catch (e: Exception) {
            Log.w(TAG, "ack failed: ${e.message}")
        }
    }

    private suspend fun notifyFor(
        reminderId: Int,
        title: String,
        body: String,
        priority: String,
        source: String,
        sourceConfig: CachedSourceConfig? = null,
    ) {
        val quiet = priority != "urgent" && settings.isQuietNow()
        NotificationHelper.notifyReminder(
            context,
            reminderId,
            title,
            body,
            priority,
            quiet,
            source,
            sourceConfig,
        )
    }

    // ------------------------------------------------------------------
    // 反馈（在线直发 / 离线入队）
    // ------------------------------------------------------------------

    suspend fun sendFeedback(reminderId: Int, action: String, option: String? = null) {
        var delivered = false
        val api = apiOrNull()
        if (api != null) {
            try {
                api.feedback(reminderId, FeedbackRequest(action, option, nowIso()))
                delivered = true
            } catch (e: Exception) {
                Log.w(TAG, "feedback failed, queue offline: ${e.message}")
            }
        }
        if (!delivered) {
            db.feedbackDao().insert(
                PendingFeedback(
                    reminderId = reminderId,
                    action = action,
                    option = option,
                    clientEventTs = nowIso(),
                )
            )
        }

        // 本地缓存状态同步（UI 即时反馈；服务端为唯一事实源，下次 sync 会对齐）
        when (action) {
            "dismiss" -> updateLocalState(reminderId, "IGNORED")
            "resolve" -> updateLocalState(reminderId, "RESOLVED")
            "open" -> updateLocalState(reminderId, "OPENED")
            "snooze" -> updateLocalState(reminderId, "SNOOZED")
        }
        when (action) {
            "dismiss", "resolve" -> {
                NotificationHelper.cancel(context, reminderId)
                AlarmScheduler.cancel(context, reminderId)
            }
            "snooze" -> {
                NotificationHelper.cancel(context, reminderId)
                AlarmScheduler.cancel(context, reminderId)
                // 离线兜底闹钟（在线时服务端会准时重投，此闹钟为断网保障）
                option?.let { opt ->
                    computeSnoozeMillis(opt)?.let { at ->
                        AlarmScheduler.schedule(context, reminderId, at)
                    }
                }
            }
        }
    }

    private suspend fun updateLocalState(reminderId: Int, state: String) {
        val cached = db.reminderDao().byId(reminderId) ?: return
        db.reminderDao().upsert(cached.copy(state = state, updatedAt = nowIso()))
    }

    // ------------------------------------------------------------------
    // 离线队列与补偿同步
    // ------------------------------------------------------------------

    /** 冲刷离线反馈队列，返回成功上报条数 */
    suspend fun flushPendingFeedback(): Int {
        val api = apiOrNull() ?: return 0
        val items = db.feedbackDao().all()
        var flushed = 0
        for (item in items) {
            try {
                api.feedback(
                    item.reminderId,
                    FeedbackRequest(item.action, item.option, item.clientEventTs),
                )
                db.feedbackDao().delete(item.autoId)
                flushed++
            } catch (e: Exception) {
                Log.w(TAG, "flush feedback ${item.autoId} failed: ${e.message}")
                db.feedbackDao().bumpRetry(item.autoId)
            }
        }
        return flushed
    }

    /** 补偿同步：GET /pending 对账缓存 + 未来 PENDING 排闹钟 + 冲刷离线反馈 */
    suspend fun syncPending(): Int {
        val api = apiOrNull() ?: return 0
        return try {
            val list = api.pending()
            db.reminderDao().upsertAll(list.map { it.toCached() })
            scheduleAlarmsForFuture(list)
            flushPendingFeedback()
            list.size
        } catch (e: Exception) {
            Log.w(TAG, "syncPending failed: ${e.message}")
            0
        }
    }

    private fun scheduleAlarmsForFuture(list: List<ReminderDto>) {
        val nowMs = System.currentTimeMillis()
        list.filter { it.state == "PENDING" }.forEach { dto ->
            parseServerTime(dto.triggerTime)?.let { trigger ->
                val at = trigger.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
                if (at > nowMs) {
                    AlarmScheduler.schedule(context, dto.id, at)
                }
            }
        }
    }

    /** 重排全部未来闹钟（开机/进程重启后调用） */
    suspend fun rescheduleAllAlarms() {
        val future = db.reminderDao().futurePending(nowIso())
        val nowMs = System.currentTimeMillis()
        future.forEach { cached ->
            parseServerTime(cached.triggerTime)?.let { trigger ->
                val at = trigger.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
                if (at > nowMs) {
                    AlarmScheduler.schedule(context, cached.id, at)
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // 查询（Inbox）
    // ------------------------------------------------------------------

    suspend fun summaryToday(): SummaryDto? = try {
        apiOrNull()?.summaryToday()
    } catch (e: Exception) {
        Log.w(TAG, "summaryToday failed: ${e.message}")
        null
    }

    suspend fun historyToday(): List<ReminderDto> = try {
        apiOrNull()?.history(LocalDate.now().toString()) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "history failed: ${e.message}")
        emptyList()
    }
}
