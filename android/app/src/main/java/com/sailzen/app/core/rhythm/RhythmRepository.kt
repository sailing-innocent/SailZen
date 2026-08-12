package com.sailzen.app.core.rhythm

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.PendingRhythmAction
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.RhythmApi
import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairStateRequest
import com.sailzen.app.core.network.dto.BlockMoveRequest
import com.sailzen.app.core.network.dto.BlockStatusRequest
import com.sailzen.app.core.network.dto.CheckinRequest
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.ConfirmHintRequest
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.PlanDayDto
import com.sailzen.app.core.network.dto.PlanDayRequest
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.reminder.ReminderRepository.Companion.nowIso
import java.time.LocalDate
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject

/**
 * 节奏（Rhythm）数据层（M3）：
 * - 在线直发；失败入 pending_rhythm_action 离线队列（done/defer/checkin/capture）
 * - flushPending：SyncWorker 周期补传
 * - 服务端为唯一事实源，UI 动作后重新拉取 timeline/checkins 对齐
 */
class RhythmRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "RhythmRepository"

        @Volatile
        private var instance: RhythmRepository? = null

        fun get(context: Context): RhythmRepository =
            instance ?: synchronized(this) {
                instance ?: RhythmRepository(context.applicationContext).also { instance = it }
            }
    }

    private val settings = SettingsManager.get(context)
    private val db = AppDatabase.get(context)
    private val json = Json { ignoreUnknownKeys = true }

    // ------------------------------------------------------------------
    // 基础
    // ------------------------------------------------------------------

    suspend fun serverConfigured(): Boolean = settings.serverUrl().isNotBlank()

    private suspend fun apiOrNull(): RhythmApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.rhythmApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "api build failed: ${e.message}")
            null
        }
    }

    fun observeQueuedCount(): Flow<Int> = db.rhythmActionDao().observeCount()

    // ------------------------------------------------------------------
    // 快速捕获
    // ------------------------------------------------------------------

    suspend fun capture(title: String, kind: String = "generic", domain: String? = null): Boolean {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.capture(AffairCreateRequest(title = title, kind = kind, domain = domain))
                return true
            } catch (e: Exception) {
                Log.w(TAG, "capture failed, queue offline: ${e.message}")
            }
        }
        val payload = run {
            val o = org.json.JSONObject()
            o.put("title", title)
            o.put("kind", kind)
            if (domain != null) o.put("domain", domain)
            o.toString()
        }
        enqueue("capture", 0, payload)
        return false
    }

    /** 待分拣 INBOX（含 AI 建议卡） */
    suspend fun inbox(): List<AffairDto> = try {
        apiOrNull()?.listAffairs(state = "INBOX")?.affairs ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "inbox failed: ${e.message}")
        emptyList()
    }

    suspend fun confirmHint(affairId: Int, accept: Boolean): Boolean = try {
        apiOrNull()?.confirmHint(affairId, ConfirmHintRequest(accept)) != null
    } catch (e: Exception) {
        Log.w(TAG, "confirmHint failed: ${e.message}")
        false
    }

    suspend fun affairDetail(affairId: Int): AffairDto? = try {
        apiOrNull()?.getAffair(affairId)
    } catch (e: Exception) {
        Log.w(TAG, "affairDetail failed: ${e.message}")
        null
    }

    /** 一键采纳 AI 建议并确认（confirm-hint → confirm，对齐 CLI `confirm --accept-hint`） */
    suspend fun acceptHintAndConfirm(affairId: Int): Boolean {
        if (!confirmHint(affairId, accept = true)) return false
        return try {
            apiOrNull()?.transit(affairId, AffairStateRequest(action = "confirm")) != null
        } catch (e: Exception) {
            Log.w(TAG, "confirm after hint failed: ${e.message}")
            false
        }
    }

    // ------------------------------------------------------------------
    // 时间线 / 计划
    // ------------------------------------------------------------------

    suspend fun timeline(date: LocalDate = LocalDate.now()): DayTimelineDto? = try {
        apiOrNull()?.timelineDay(date.toString())
    } catch (e: Exception) {
        Log.w(TAG, "timeline failed: ${e.message}")
        null
    }

    suspend fun planDay(date: LocalDate = LocalDate.now(), force: Boolean = false): PlanDayDto? = try {
        apiOrNull()?.planDay(PlanDayRequest(date = date.toString(), force = force))
    } catch (e: Exception) {
        Log.w(TAG, "planDay failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // 块反馈（done/skip/move，离线入队）
    // ------------------------------------------------------------------

    suspend fun blockDone(blockId: Int) = blockStatus(blockId, "DONE")

    suspend fun blockSkip(blockId: Int) = blockStatus(blockId, "SKIPPED")

    private suspend fun blockStatus(blockId: Int, status: String): Boolean {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.blockStatus(blockId, BlockStatusRequest(status))
                return true
            } catch (e: Exception) {
                Log.w(TAG, "blockStatus failed, queue offline: ${e.message}")
            }
        }
        enqueue(
            if (status == "DONE") "block_done" else "block_skip",
            blockId,
            """{"status":"$status"}""",
        )
        return false
    }

    /** defer：事务级推迟（服务端 409 对 fixed_plan 拒绝） */
    suspend fun deferAffair(affairId: Int, deferToIso: String): Boolean {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.transit(affairId, AffairStateRequest(action = "defer", deferTo = deferToIso))
                return true
            } catch (e: Exception) {
                Log.w(TAG, "defer failed, queue offline: ${e.message}")
            }
        }
        enqueue("defer", affairId, """{"action":"defer","defer_to":"$deferToIso"}""")
        return false
    }

    // ------------------------------------------------------------------
    // 打卡（离线入队）
    // ------------------------------------------------------------------

    suspend fun checkin(affairId: Int, result: String, note: String = ""): Boolean {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.checkin(CheckinRequest(affairId = affairId, result = result, note = note))
                return true
            } catch (e: Exception) {
                Log.w(TAG, "checkin failed, queue offline: ${e.message}")
            }
        }
        val payload = run {
            val o = org.json.JSONObject()
            o.put("affair_id", affairId)
            o.put("result", result)
            o.put("note", note)
            o.toString()
        }
        enqueue("checkin", affairId, payload)
        return false
    }

    suspend fun checkinToday(): CheckinTodayDto? = try {
        apiOrNull()?.checkinToday()
    } catch (e: Exception) {
        Log.w(TAG, "checkinToday failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // 事业 / 复盘
    // ------------------------------------------------------------------

    suspend fun activeVentures(): List<AffairDto> = try {
        apiOrNull()?.listAffairs(state = "ACTIVE", kinds = listOf("venture"))?.affairs
            ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "activeVentures failed: ${e.message}")
        emptyList()
    }

    suspend fun ventureProgress(ventureId: Int): VentureProgressDto? = try {
        apiOrNull()?.ventureProgress(ventureId)
    } catch (e: Exception) {
        Log.w(TAG, "ventureProgress failed: ${e.message}")
        null
    }

    suspend fun milestoneDone(milestoneId: Int): Boolean = try {
        apiOrNull()?.milestoneDone(milestoneId) != null
    } catch (e: Exception) {
        Log.w(TAG, "milestoneDone failed: ${e.message}")
        false
    }

    suspend fun reviewWeek(span: String? = null): ReviewDto? = try {
        apiOrNull()?.reviewWeek(span)
    } catch (e: Exception) {
        Log.w(TAG, "reviewWeek failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // 离线队列
    // ------------------------------------------------------------------

    private suspend fun enqueue(actionType: String, targetId: Int, payloadJson: String) {
        // 校验 payload JSON 合法性（避免补传时炸队列）
        runCatching { json.parseToJsonElement(payloadJson).jsonObject }
            .onFailure { Log.e(TAG, "invalid payload json: $payloadJson"); return }
        db.rhythmActionDao().insert(
            PendingRhythmAction(
                actionType = actionType,
                targetId = targetId,
                payloadJson = payloadJson,
                clientEventTs = nowIso(),
            )
        )
    }

    /** 冲刷离线动作队列，返回成功补传条数 */
    suspend fun flushPending(): Int {
        val api = apiOrNull() ?: return 0
        val items = db.rhythmActionDao().all()
        var flushed = 0
        for (item in items) {
            try {
                when (item.actionType) {
                    "block_done", "block_skip" -> api.blockStatus(
                        item.targetId,
                        ApiClient.json.decodeFromString<BlockStatusRequest>(item.payloadJson),
                    )
                    "block_move" -> api.blockMove(
                        item.targetId,
                        ApiClient.json.decodeFromString<BlockMoveRequest>(item.payloadJson),
                    )
                    "checkin" -> api.checkin(
                        ApiClient.json.decodeFromString<CheckinRequest>(item.payloadJson),
                    )
                    "capture" -> api.capture(
                        ApiClient.json.decodeFromString<AffairCreateRequest>(item.payloadJson),
                    )
                    "defer" -> api.transit(
                        item.targetId,
                        ApiClient.json.decodeFromString<AffairStateRequest>(item.payloadJson),
                    )
                    else -> error("unknown actionType ${item.actionType}")
                }
                db.rhythmActionDao().delete(item.autoId)
                flushed++
            } catch (e: Exception) {
                Log.w(TAG, "flush ${item.actionType}#${item.autoId} failed: ${e.message}")
                db.rhythmActionDao().bumpRetry(item.autoId)
            }
        }
        return flushed
    }
}
