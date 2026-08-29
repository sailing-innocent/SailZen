package com.sailzen.app.core.rhythm

import android.content.Context
import android.util.Log
import com.sailzen.app.R
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.OperationResult
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.data.db.AppDatabase
import com.sailzen.app.core.data.db.PendingRhythmAction
import com.sailzen.app.core.data.runOperation
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.HealthApi
import com.sailzen.app.core.network.RhythmApi
import com.sailzen.app.core.network.dto.AffairCreateRequest
import com.sailzen.app.core.network.dto.AffairDto
import com.sailzen.app.core.network.dto.AffairStateRequest
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.network.dto.AffairUpdateRequest
import com.sailzen.app.core.network.dto.BlockMoveRequest
import com.sailzen.app.core.network.dto.BlockStatusRequest
import com.sailzen.app.core.network.dto.CheckinRequest
import com.sailzen.app.core.network.dto.CheckinTodayDto
import com.sailzen.app.core.network.dto.ConfirmHintRequest
import com.sailzen.app.core.network.dto.DayTimelineDto
import com.sailzen.app.core.network.dto.DietCreateRequest
import com.sailzen.app.core.network.dto.ExerciseCreateRequest
import com.sailzen.app.core.network.dto.HealthCheckinRequest
import com.sailzen.app.core.network.dto.HealthCheckinResponse
import com.sailzen.app.core.network.dto.InfoCollectionType
import com.sailzen.app.core.network.dto.MedicationCreateRequest
import com.sailzen.app.core.network.dto.PlanDayDto
import com.sailzen.app.core.network.dto.PlanDayRequest
import com.sailzen.app.core.network.dto.ReviewDto
import com.sailzen.app.core.network.dto.ReviewTimespanDto
import com.sailzen.app.core.network.dto.RhythmDayViewDto
import com.sailzen.app.core.network.dto.SleepCreateRequest
import com.sailzen.app.core.network.dto.VentureMilestoneRequest
import com.sailzen.app.core.network.dto.VentureProgressDto
import com.sailzen.app.core.network.dto.WeightCreateRequest
import com.sailzen.app.core.reminder.NotificationHelper
import com.sailzen.app.core.reminder.ReminderRepository.Companion.nowIso
import java.time.LocalDate
import java.time.LocalDateTime
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject

/**
 * 节奏（Rhythm）数据层（M3）：
 * - 在线直发；失败入 pending_rhythm_action 离线队列（done/defer/checkin/capture）
 * - flushPending：SyncWorker 周期补传
 * - 服务端为唯一事实源，操作成功后通过 [DataChangeBus] 广播领域事件，
 *   让事务首页、详情、时间线、打卡等页面自动刷新到最新状态。
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
    private val bus = DataChangeBus.get()
    private val json = Json { ignoreUnknownKeys = true }

    // ------------------------------------------------------------------
    // 基础
    // ------------------------------------------------------------------

    suspend fun serverConfigured(): Boolean = settings.serverUrl().isNotBlank()

    private suspend fun healthApiOrNull(): HealthApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.healthApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "health api build failed: ${e.message}")
            null
        }
    }

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

    /**
     * 通用原子写操作封装：在线成功后发射 [DataChangeEvent] 驱动跨页面刷新。
     * 写操作失败（网络/服务端异常）返回 [OperationResult.Failure]，调用方提示用户。
     */
    private suspend fun <T> write(
        block: suspend () -> T,
        event: (T) -> DataChangeEvent,
    ): OperationResult<T> = runOperation(bus, block, onSuccess = { event(it) })

    // ------------------------------------------------------------------
    // 快速捕获
    // ------------------------------------------------------------------

    /**
     * 快速捕获一条事务。
     * @return Success(true) 服务端确认；Success(false) 离线已入队；Failure 发生错误。
     */
    suspend fun capture(title: String, kind: String = "generic", domain: String? = null): OperationResult<Boolean> {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.capture(AffairCreateRequest(title = title, kind = kind, domain = domain))
                bus.emit(DataChangeEvent.AffairChanged(action = "capture"))
                bus.emit(DataChangeEvent.DayViewChanged())
                return OperationResult.Success(true)
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
        return if (enqueue("capture", 0, payload)) {
            OperationResult.Success(false)
        } else {
            OperationResult.Failure("捕获失败，无法保存到本地队列")
        }
    }

    /** 待分拣 INBOX（含 AI 建议卡） */
    suspend fun inbox(): List<AffairDto> = try {
        apiOrNull()?.listAffairs(state = "INBOX")?.affairs ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "inbox failed: ${e.message}")
        emptyList()
    }

    suspend fun confirmHint(affairId: Int, accept: Boolean): OperationResult<Boolean> = write(
        block = {
            apiOrNull()?.confirmHint(affairId, ConfirmHintRequest(accept))
                ?: error("采纳 AI 建议失败")
            true
        },
        event = { DataChangeEvent.AffairChanged(affairId = affairId, action = if (accept) "hint_accept" else "hint_reject") },
    )

    suspend fun affairDetail(affairId: Int): AffairDto? = try {
        apiOrNull()?.getAffair(affairId)
    } catch (e: Exception) {
        Log.w(TAG, "affairDetail failed: ${e.message}")
        null
    }

    /** 一键采纳 AI 建议并确认（confirm-hint → confirm，对齐 CLI `confirm --accept-hint`） */
    suspend fun acceptHintAndConfirm(affairId: Int): OperationResult<Boolean> = write(
        block = {
            apiOrNull()?.confirmHint(affairId, ConfirmHintRequest(accept = true))
                ?: error("采纳 AI 建议失败")
            apiOrNull()?.transit(affairId, AffairStateRequest(action = "confirm"))
                ?: error("确认事务失败")
            true
        },
        event = { DataChangeEvent.AffairChanged(affairId = affairId, action = "confirm") },
    )

    // ------------------------------------------------------------------
    // 事务 CRUD（统一 Affair 模型：长期事业 = kind=venture，任务 = 其余 kind）
    // ------------------------------------------------------------------

    suspend fun listAffairs(
        state: String? = null,
        domain: String? = null,
        kinds: List<String>? = null,
        parentId: Int? = null,
        limit: Int = -1,
    ): List<AffairDto> = try {
        apiOrNull()?.listAffairs(
            state = state,
            domain = domain,
            kinds = kinds,
            parentId = parentId,
            limit = limit,
        )?.affairs ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "listAffairs failed: ${e.message}")
        emptyList()
    }

    suspend fun createAffair(body: AffairCreateRequest): OperationResult<AffairDto> = write(
        block = { apiOrNull()?.capture(body) ?: error("创建事务失败") },
        event = {
            DataChangeEvent.AffairChanged(
                affairId = it.id,
                parentId = it.parentId,
                action = "create",
            )
        },
    )

    suspend fun updateAffair(affairId: Int, body: AffairUpdateRequest): OperationResult<AffairDto> = write(
        block = { apiOrNull()?.updateAffair(affairId, body) ?: error("更新事务失败") },
        event = { DataChangeEvent.AffairChanged(affairId = it.id, parentId = it.parentId, action = "update") },
    )

    suspend fun deleteAffair(affairId: Int): OperationResult<Boolean> = write(
        block = {
            val resp = apiOrNull()?.deleteAffair(affairId)
            if (resp?.status == "success") true else error("删除事务失败")
        },
        event = { DataChangeEvent.AffairChanged(affairId = affairId, action = "delete") },
    )

    /** 状态转移：confirm/start/finish/cancel/pause/resume/archive/graduate/replan */
    suspend fun transit(affairId: Int, action: String): OperationResult<AffairDto> = write(
        block = { apiOrNull()?.transit(affairId, AffairStateRequest(action = action)) ?: error("状态转移失败") },
        event = { DataChangeEvent.AffairChanged(affairId = it.id, parentId = it.parentId, action = action) },
    )

    // ------------------------------------------------------------------
    // 时间线 / 计划
    // ------------------------------------------------------------------

    suspend fun timeline(date: LocalDate = LocalDate.now()): DayTimelineDto? = try {
        apiOrNull()?.timelineDay(date.toString())
    } catch (e: Exception) {
        Log.w(TAG, "timeline failed: ${e.message}")
        null
    }

    suspend fun planDay(date: LocalDate = LocalDate.now(), force: Boolean = false): OperationResult<PlanDayDto> = write(
        block = { apiOrNull()?.planDay(PlanDayRequest(date = date.toString(), force = force)) ?: error("生成日计划失败") },
        event = { DataChangeEvent.DayViewChanged(date = date) },
    )

    // ------------------------------------------------------------------
    // 块反馈（done/skip/move，离线入队）
    // ------------------------------------------------------------------

    suspend fun blockDone(blockId: Int): OperationResult<Boolean> = blockStatus(blockId, "DONE")

    suspend fun blockSkip(blockId: Int): OperationResult<Boolean> = blockStatus(blockId, "SKIPPED")

    private suspend fun blockStatus(blockId: Int, status: String): OperationResult<Boolean> {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.blockStatus(blockId, BlockStatusRequest(status))
                bus.emit(DataChangeEvent.DayViewChanged())
                bus.emit(DataChangeEvent.CheckinChanged())
                return OperationResult.Success(true)
            } catch (e: Exception) {
                Log.w(TAG, "blockStatus failed, queue offline: ${e.message}")
            }
        }
        val enqueued = enqueue(
            if (status == "DONE") "block_done" else "block_skip",
            blockId,
            """{"status":"$status"}""",
        )
        return if (enqueued) OperationResult.Success(false) else OperationResult.Failure("块状态保存失败")
    }

    /** defer：事务级推迟（服务端 409 对 fixed_plan 拒绝） */
    suspend fun deferAffair(affairId: Int, deferToIso: String): OperationResult<Boolean> {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.transit(affairId, AffairStateRequest(action = "defer", deferTo = deferToIso))
                bus.emit(DataChangeEvent.AffairChanged(affairId = affairId, action = "defer"))
                bus.emit(DataChangeEvent.DayViewChanged())
                return OperationResult.Success(true)
            } catch (e: Exception) {
                Log.w(TAG, "defer failed, queue offline: ${e.message}")
            }
        }
        val enqueued = enqueue(
            "defer",
            affairId,
            """{"action":"defer","defer_to":"$deferToIso"}""",
        )
        return if (enqueued) OperationResult.Success(false) else OperationResult.Failure("推迟保存失败")
    }

    // ------------------------------------------------------------------
    // 打卡（离线入队）
    // ------------------------------------------------------------------

    /**
     * 打卡。
     * @return Success(true) 服务端确认；Success(false) 离线已入队；Failure 发生错误。
     */
    suspend fun checkin(affairId: Int, result: String, note: String = ""): OperationResult<Boolean> {
        val api = apiOrNull()
        if (api != null) {
            try {
                api.checkin(CheckinRequest(affairId = affairId, result = result, note = note))
                bus.emit(DataChangeEvent.CheckinChanged(affairId = affairId))
                bus.emit(DataChangeEvent.AffairChanged(affairId = affairId, action = "checkin"))
                return OperationResult.Success(true)
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
        return if (enqueue("checkin", affairId, payload)) {
            OperationResult.Success(false)
        } else {
            OperationResult.Failure("打卡保存失败")
        }
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

    suspend fun addMilestone(ventureId: Int, body: VentureMilestoneRequest): OperationResult<AffairDto> = write(
        block = { apiOrNull()?.addMilestone(ventureId, body) ?: error("添加里程碑失败") },
        event = { DataChangeEvent.AffairChanged(affairId = it.id, parentId = ventureId, action = "milestone") },
    )

    suspend fun milestoneDone(milestoneId: Int): OperationResult<Boolean> = write(
        block = {
            apiOrNull()?.milestoneDone(milestoneId) ?: error("里程碑完成失败")
            true
        },
        event = { DataChangeEvent.AffairChanged(affairId = milestoneId, action = "milestone_done") },
    )

    /**
     * 事务提醒同步：逾期与 24h 内到期的未完成事务转本地通知。
     */
    suspend fun syncAffairReminders(withinHours: Int = 24) {
        val api = apiOrNull() ?: return
        val now = LocalDateTime.now()
        val affairs = try {
            api.listAffairs(
                urgencyDdlBefore = RhythmTime.format(now.plusHours(withinHours.toLong())),
            ).affairs
        } catch (e: Exception) {
            Log.w(TAG, "syncAffairReminders failed: ${e.message}")
            return
        }
        affairs.filter { it.state !in AffairStates.TERMINAL && it.urgencyDdl != null }
            .forEach { affair ->
                val overdue = RhythmTime.hoursUntil(affair.urgencyDdl, now) < 0
                NotificationHelper.notifyAffairReminder(
                    context = context,
                    affairId = affair.id,
                    title = context.getString(
                        if (overdue) R.string.affair_overdue_title else R.string.affair_upcoming_title,
                    ),
                    body = affair.title,
                    isOverdue = overdue,
                )
            }
    }

    suspend fun reviewWeek(span: String? = null): ReviewDto? = try {
        apiOrNull()?.reviewWeek(span)
    } catch (e: Exception) {
        Log.w(TAG, "reviewWeek failed: ${e.message}")
        null
    }

    suspend fun reviewTimespan(timespanId: Int): ReviewTimespanDto? = try {
        apiOrNull()?.reviewTimespan(timespanId)
    } catch (e: Exception) {
        Log.w(TAG, "reviewTimespan failed: ${e.message}")
        null
    }


    // ------------------------------------------------------------------
    // 统一日视图 / 健康速记
    // ------------------------------------------------------------------

    suspend fun dayView(date: LocalDate = LocalDate.now()): RhythmDayViewDto? = try {
        apiOrNull()?.dayView(date.toString())
    } catch (e: Exception) {
        Log.w(TAG, "dayView failed: ${e.message}")
        null
    }

    suspend fun healthCheckin(
        collectionType: InfoCollectionType,
        payload: Map<String, Any?>,
        note: String = "",
        date: LocalDate = LocalDate.now(),
    ): OperationResult<HealthCheckinResponse?> {
        val jsonPayload = org.json.JSONObject(payload).toString()
        val body = HealthCheckinRequest(
            collectionType = collectionType,
            logDate = date.toString(),
            payload = json.parseToJsonElement(jsonPayload).jsonObject,
            note = note,
        )
        val api = apiOrNull()
        if (api != null) {
            try {
                val response = api.healthCheckin(body)
                emitHealthEvent(collectionType)
                return OperationResult.Success(response)
            } catch (e: Exception) {
                Log.w(TAG, "healthCheckin failed, queue offline: ${e.message}")
            }
        }
        return if (enqueue(
                "health_checkin",
                0,
                ApiClient.json.encodeToString(body),
            )
        ) {
            OperationResult.Success(null)
        } else {
            OperationResult.Failure("健康速记保存失败")
        }
    }

    private suspend fun emitHealthEvent(collectionType: InfoCollectionType) {
        when (collectionType) {
            InfoCollectionType.weight -> bus.emit(DataChangeEvent.WeightChanged())
            InfoCollectionType.meal -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "meal"))
            InfoCollectionType.exercise -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "exercise"))
            InfoCollectionType.medication -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "medication"))
            InfoCollectionType.sleep -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "sleep"))
            InfoCollectionType.mood -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "mood"))
        }
    }

    // ------------------------------------------------------------------
    // 离线队列
    // ------------------------------------------------------------------

    private suspend fun enqueue(actionType: String, targetId: Int, payloadJson: String): Boolean {
        // 校验 payload JSON 合法性（避免补传时炸队列）
        runCatching { json.parseToJsonElement(payloadJson).jsonObject }
            .onFailure { Log.e(TAG, "invalid payload json: $payloadJson"); return false }
        db.rhythmActionDao().insert(
            PendingRhythmAction(
                actionType = actionType,
                targetId = targetId,
                payloadJson = payloadJson,
                clientEventTs = nowIso(),
            )
        )
        return true
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
                    "health_checkin" -> api.healthCheckin(
                        ApiClient.json.decodeFromString<HealthCheckinRequest>(item.payloadJson),
                    )
                    "health_weight" -> healthApiOrNull()?.createWeight(
                        ApiClient.json.decodeFromString<WeightCreateRequest>(item.payloadJson),
                    )
                    "health_exercise" -> healthApiOrNull()?.createExercise(
                        ApiClient.json.decodeFromString<ExerciseCreateRequest>(item.payloadJson),
                    )
                    "health_sleep" -> healthApiOrNull()?.createSleep(
                        ApiClient.json.decodeFromString<SleepCreateRequest>(item.payloadJson),
                    )
                    "health_medication" -> healthApiOrNull()?.createMedication(
                        ApiClient.json.decodeFromString<MedicationCreateRequest>(item.payloadJson),
                    )
                    "health_diet" -> healthApiOrNull()?.createDiet(
                        ApiClient.json.decodeFromString<DietCreateRequest>(item.payloadJson),
                    )
                    "defer" -> api.transit(
                        item.targetId,
                        ApiClient.json.decodeFromString<AffairStateRequest>(item.payloadJson),
                    )
                    else -> error("unknown actionType ${item.actionType}")
                }
                db.rhythmActionDao().delete(item.autoId)
                emitEventForFlushed(item.actionType)
                flushed++
            } catch (e: Exception) {
                Log.w(TAG, "flush ${item.actionType}#${item.autoId} failed: ${e.message}")
                db.rhythmActionDao().bumpRetry(item.autoId)
            }
        }
        return flushed
    }

    private suspend fun emitEventForFlushed(actionType: String) {
        when (actionType) {
            "block_done", "block_skip", "block_move" -> {
                bus.emit(DataChangeEvent.DayViewChanged())
                bus.emit(DataChangeEvent.CheckinChanged())
            }
            "checkin" -> {
                bus.emit(DataChangeEvent.CheckinChanged())
                bus.emit(DataChangeEvent.AffairChanged(action = "checkin"))
            }
            "capture" -> bus.emit(DataChangeEvent.AffairChanged(action = "capture"))
            "health_checkin", "health_weight" -> bus.emit(DataChangeEvent.WeightChanged())
            "health_exercise" -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "exercise"))
            "health_sleep" -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "sleep"))
            "health_medication" -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "medication"))
            "health_diet" -> bus.emit(DataChangeEvent.HealthSignalChanged(collectionType = "meal"))
            "defer" -> {
                bus.emit(DataChangeEvent.AffairChanged(action = "defer"))
                bus.emit(DataChangeEvent.DayViewChanged())
            }
        }
    }
}
