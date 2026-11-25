package com.sailzen.app.core.user

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.DeviceIdentity
import com.sailzen.app.core.data.SettingsManager
import kotlinx.serialization.json.JsonPrimitive
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.CachedInboxItem
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.UserInboxApi
import com.sailzen.app.core.network.dto.InboxDismissRequest
import com.sailzen.app.core.network.dto.InboxItemDto
import com.sailzen.app.core.network.dto.InboxReplyRequest
import com.sailzen.app.core.network.dto.InboxResolveRequest
import com.sailzen.app.core.network.dto.InboxSnoozeRequest
import com.sailzen.app.core.network.dto.InboxSummaryDto
import com.sailzen.app.core.network.dto.QuietHoursDto
import com.sailzen.app.core.network.dto.UserBootstrapDto
import com.sailzen.app.core.network.dto.UserDeviceRegisterRequest
import com.sailzen.app.core.network.dto.UserProfileDto
import com.sailzen.app.core.network.dto.UserProfileUpdateRequest
import com.sailzen.app.core.network.dto.WsInboxResolvedDto
import com.sailzen.app.core.reminder.AlarmScheduler
import com.sailzen.app.core.reminder.NotificationHelper
import com.sailzen.app.core.reminder.ReminderRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 统一 UserProfile 与 UserInbox 协调器：
 * - 单用户免登录静默 Bootstrap（GET /api/v1/user/bootstrap）并同步全局安静时段
 * - 基于单调游标 sync_seq 的增量对账（含终态变更 + active_ids 清理本地残留）
 * - WS 收到 inbox.item_resolved 时立即更新 Room 缓存并撤回系统通知栏与本地闹钟
 */
class UserInboxRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "UserInboxRepository"

        private val ACTIVE_STATUSES = setOf("pending", "delivered", "snoozed", "opened")
        private const val INBOX_NOTIFY_ID_OFFSET = 500_000

        @Volatile
        private var instance: UserInboxRepository? = null

        fun get(context: Context): UserInboxRepository =
            instance ?: synchronized(this) {
                instance ?: UserInboxRepository(context.applicationContext).also { instance = it }
            }

        fun InboxItemDto.toCached(): CachedInboxItem = CachedInboxItem(
            id = id,
            syncSeq = syncSeq,
            sourceDomain = sourceDomain,
            itemKind = itemKind,
            topic = topic,
            refType = refType,
            refId = refId,
            reminderId = reminderId,
            ticketId = ticketId,
            title = title,
            body = body,
            priority = priority,
            status = status,
            isRead = isRead,
            actionSchemaJson = actionSchema.toString(),
            replyText = replyText,
            resolutionSource = resolutionSource,
            resolutionSummary = resolutionSummary,
            updatedAt = updatedAt ?: ReminderRepository.nowIso(),
        )
    }

    private val settings = SettingsManager.get(context)
    private val db = AppDatabase.get(context)

    private val _profileState = MutableStateFlow<UserProfileDto?>(null)
    val profileState: StateFlow<UserProfileDto?> = _profileState.asStateFlow()

    fun observeActive(): Flow<List<CachedInboxItem>> = db.inboxDao().observeActive()

    fun observeHistory(): Flow<List<CachedInboxItem>> = db.inboxDao().observeHistory()

    suspend fun activeCountLocal(): Int = db.inboxDao().activeList().size

    private suspend fun apiOrNull(): UserInboxApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.userInboxApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "userInboxApi build failed: ${e.message}")
            null
        }
    }

    private fun appVersion(): String = try {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
    } catch (_: Exception) {
        ""
    }

    // ------------------------------------------------------------------
    // 单用户免登录静默引导 & Profile 同步
    // ------------------------------------------------------------------

    suspend fun bootstrapSilently(): UserBootstrapDto? {
        val api = apiOrNull() ?: return null
        return try {
            val boot = api.bootstrap()
            applyProfileLocally(boot.user)
            val identity = DeviceIdentity.resolve(context)
            runCatching {
                api.registerDevice(
                    UserDeviceRegisterRequest(
                        deviceId = settings.getOrCreateDeviceId(),
                        deviceName = identity.displayName,
                        platform = "android",
                        clientType = "android",
                        appVersion = appVersion(),
                        fingerprint = identity.fingerprint,
                        isEmulator = identity.isEmulator,
                        capabilities = buildMap {
                            put("identity_v", JsonPrimitive(2))
                            if (identity.fingerprint.isNotBlank()) put("fingerprint", JsonPrimitive(identity.fingerprint))
                            put("manufacturer", JsonPrimitive(identity.manufacturer))
                            put("model", JsonPrimitive(identity.model))
                            put("os_version", JsonPrimitive(identity.osVersion))
                            put("is_emulator", JsonPrimitive(identity.isEmulator))
                            put("push_ws", JsonPrimitive(true))
                            put("system_notification", JsonPrimitive(true))
                        },
                    )
                )
            }
            boot
        } catch (e: Exception) {
            Log.w(TAG, "bootstrapSilently failed: ${e.message}")
            null
        }
    }

    suspend fun applyProfileLocally(profile: UserProfileDto) {
        _profileState.value = profile
        settings.saveUserProfileLocal(profile.displayName, profile.slug)
        if (profile.quietHours.start.isNotBlank() && profile.quietHours.end.isNotBlank()) {
            settings.saveQuietHours(profile.quietHours.start, profile.quietHours.end)
        }
    }

    suspend fun updateProfile(
        displayName: String,
        quietStart: String,
        quietEnd: String,
    ): UserProfileDto? {
        settings.saveUserProfileLocal(displayName)
        settings.saveQuietHours(quietStart, quietEnd)
        val api = apiOrNull() ?: return null
        return try {
            val updated = api.updateProfile(
                UserProfileUpdateRequest(
                    displayName = displayName.trim().ifBlank { null },
                    quietHours = QuietHoursDto(
                        enabled = true,
                        start = quietStart.trim().ifBlank { SettingsManager.DEFAULT_QUIET_START },
                        end = quietEnd.trim().ifBlank { SettingsManager.DEFAULT_QUIET_END },
                    ),
                )
            )
            applyProfileLocally(updated)
            updated
        } catch (e: Exception) {
            Log.w(TAG, "updateProfile failed: ${e.message}")
            null
        }
    }

    // ------------------------------------------------------------------
    // 单调游标增量对账（根治已答消息在收件箱残留）
    // ------------------------------------------------------------------

    suspend fun syncInbox(full: Boolean = false): Int {
        val api = apiOrNull() ?: return 0
        return try {
            val since = if (full) 0L else settings.lastInboxSyncSeq()
            val res = api.syncInbox(sinceSeq = since, limit = 200)
            if (res.changes.isNotEmpty()) {
                db.inboxDao().upsertAll(res.changes.map { it.toCached() })
                for (item in res.changes) {
                    if (item.status !in ACTIVE_STATUSES) {
                        cancelNotificationsForItem(item.id, item.reminderId)
                        markLinkedReminderResolvedLocally(item.reminderId, item.status)
                    }
                }
            }
            // 兜底对账：本地仍标为活跃态但已不在服务端 active_ids 中的条目，立刻标为 resolved 并清通知
            val activeIdSet = res.activeIds.toSet()
            val localActive = db.inboxDao().activeList()
            for (stale in localActive) {
                if (stale.id !in activeIdSet) {
                    db.inboxDao().upsert(
                        stale.copy(
                            status = "resolved",
                            isRead = true,
                            updatedAt = ReminderRepository.nowIso(),
                        )
                    )
                    cancelNotificationsForItem(stale.id, stale.reminderId)
                    markLinkedReminderResolvedLocally(stale.reminderId, "resolved")
                }
            }
            if (res.latestSeq > 0L) {
                settings.saveLastInboxSyncSeq(res.latestSeq)
            }
            res.activeCount
        } catch (e: Exception) {
            Log.w(TAG, "syncInbox failed: ${e.message}")
            0
        }
    }

    suspend fun summaryToday(): InboxSummaryDto? = try {
        apiOrNull()?.summary()
    } catch (e: Exception) {
        Log.w(TAG, "summaryToday failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // WebSocket 实时上行/撤回处理
    // ------------------------------------------------------------------

    suspend fun processWsUpserted(dto: InboxItemDto, shouldNotify: Boolean) {
        db.inboxDao().upsert(dto.toCached())
        if (dto.syncSeq > settings.lastInboxSyncSeq()) {
            settings.saveLastInboxSyncSeq(dto.syncSeq)
        }
        if (dto.status !in ACTIVE_STATUSES) {
            cancelNotificationsForItem(dto.id, dto.reminderId)
            markLinkedReminderResolvedLocally(dto.reminderId, dto.status)
            return
        }
        // 若不挂 reminder_id（非 legacy reminder 路径），由此处兜底系统通知
        if (shouldNotify && dto.reminderId == null) {
            val quiet = dto.priority != "urgent" && settings.isQuietNow()
            NotificationHelper.notifyReminder(
                context = context,
                reminderId = INBOX_NOTIFY_ID_OFFSET + dto.id,
                title = dto.title,
                body = dto.body,
                priority = dto.priority,
                isQuiet = quiet,
                source = dto.sourceDomain,
            )
        }
    }

    suspend fun processWsResolved(ev: WsInboxResolvedDto) {
        if (ev.inboxItemId > 0) {
            val existing = db.inboxDao().byId(ev.inboxItemId)
            if (existing != null) {
                db.inboxDao().upsert(
                    existing.copy(
                        status = ev.status.ifBlank { "resolved" },
                        isRead = true,
                        syncSeq = maxOf(existing.syncSeq, ev.syncSeq),
                        resolutionSource = ev.resolutionSource.ifBlank { existing.resolutionSource },
                        resolutionSummary = ev.resolutionSummary.ifBlank { existing.resolutionSummary },
                        replyText = ev.replyText ?: existing.replyText,
                        updatedAt = ReminderRepository.nowIso(),
                    )
                )
            }
            cancelNotificationsForItem(ev.inboxItemId, ev.reminderId)
            markLinkedReminderResolvedLocally(ev.reminderId, ev.status)
        } else if (ev.reminderId != null) {
            cancelNotificationsForItem(0, ev.reminderId)
            markLinkedReminderResolvedLocally(ev.reminderId, ev.status)
        }
        if (ev.syncSeq > settings.lastInboxSyncSeq()) {
            settings.saveLastInboxSyncSeq(ev.syncSeq)
        }
    }

    // ------------------------------------------------------------------
    // 统一交互动作（回复 / 完成 / 延后 / 忽略）
    // ------------------------------------------------------------------

    suspend fun replyItem(itemId: Int, reply: String): InboxItemDto? {
        val text = reply.trim()
        if (text.isEmpty()) return null
        val api = apiOrNull() ?: return null
        return try {
            val res = api.reply(itemId, InboxReplyRequest(reply = text, source = "android:inbox"))
            db.inboxDao().upsert(res.toCached())
            cancelNotificationsForItem(res.id, res.reminderId)
            markLinkedReminderResolvedLocally(res.reminderId, res.status)
            res
        } catch (e: Exception) {
            Log.w(TAG, "replyItem($itemId) failed: ${e.message}")
            null
        }
    }

    suspend fun resolveItem(itemId: Int, summary: String = ""): InboxItemDto? {
        val api = apiOrNull() ?: return null
        return try {
            val res = api.resolve(itemId, InboxResolveRequest(resolutionSummary = summary))
            db.inboxDao().upsert(res.toCached())
            cancelNotificationsForItem(res.id, res.reminderId)
            markLinkedReminderResolvedLocally(res.reminderId, res.status)
            res
        } catch (e: Exception) {
            Log.w(TAG, "resolveItem($itemId) failed: ${e.message}")
            null
        }
    }

    suspend fun snoozeItem(itemId: Int, option: String): InboxItemDto? {
        val api = apiOrNull() ?: return null
        return try {
            val res = api.snooze(itemId, InboxSnoozeRequest(option = option))
            db.inboxDao().upsert(res.toCached())
            cancelNotificationsForItem(res.id, res.reminderId)
            res
        } catch (e: Exception) {
            Log.w(TAG, "snoozeItem($itemId) failed: ${e.message}")
            null
        }
    }

    suspend fun dismissItem(itemId: Int): InboxItemDto? {
        val api = apiOrNull() ?: return null
        return try {
            val res = api.dismiss(itemId, InboxDismissRequest())
            db.inboxDao().upsert(res.toCached())
            cancelNotificationsForItem(res.id, res.reminderId)
            markLinkedReminderResolvedLocally(res.reminderId, res.status)
            res
        } catch (e: Exception) {
            Log.w(TAG, "dismissItem($itemId) failed: ${e.message}")
            null
        }
    }

    private fun cancelNotificationsForItem(inboxItemId: Int, reminderId: Int?) {
        if (reminderId != null && reminderId > 0) {
            NotificationHelper.cancel(context, reminderId)
            AlarmScheduler.cancel(context, reminderId)
        }
        if (inboxItemId > 0) {
            NotificationHelper.cancel(context, INBOX_NOTIFY_ID_OFFSET + inboxItemId)
        }
    }

    private suspend fun markLinkedReminderResolvedLocally(reminderId: Int?, inboxStatus: String) {
        if (reminderId == null || reminderId <= 0) return
        val cached = db.reminderDao().byId(reminderId) ?: return
        val mapped = when (inboxStatus) {
            "dismissed" -> "IGNORED"
            "canceled" -> "CANCELED"
            "expired" -> "ARCHIVED"
            else -> "RESOLVED"
        }
        if (cached.state != mapped) {
            db.reminderDao().upsert(cached.copy(state = mapped, updatedAt = ReminderRepository.nowIso()))
        }
    }
}
