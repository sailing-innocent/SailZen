package com.sailzen.app.core.tick

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.TickApi
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.TickMessageCreateRequest
import com.sailzen.app.core.network.dto.TickMessageDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TicketReplyRequest
import com.sailzen.app.core.network.dto.TicketSnoozeRequest
import kotlinx.serialization.json.JsonPrimitive

/**
 * SailTick AI 教练数据仓库：
 * - 获取健康页 AI 教练聚合摘要（动态计划 + 最新睡前日报 + 待回提问 + 今日主动记录）
 * - 回复/暂缓 AI 提问票据
 * - 主动静默发送餐饮/日常状态消息（无需等待 AI 即时回复）
 * - 浏览历史睡前体重与健康日报
 */
class TickRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "TickRepository"

        @Volatile
        private var instance: TickRepository? = null

        fun get(context: Context): TickRepository =
            instance ?: synchronized(this) {
                instance ?: TickRepository(context.applicationContext).also { instance = it }
            }
    }

    private val settings = SettingsManager.get(context)
    private val bus = DataChangeBus.get()

    private suspend fun api(): TickApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return ApiClient.tickApi(url, settings.apiToken())
    }

    suspend fun loadCoachSummary(): HealthCoachSummaryDto? {
        val client = api() ?: return null
        return try {
            client.healthCoachSummary()
        } catch (e: Exception) {
            Log.w(TAG, "loadCoachSummary failed: ${e.message}")
            null
        }
    }

    suspend fun loadDailyReports(limit: Int = 14): List<DailyReportDto> {
        val client = api() ?: return emptyList()
        return try {
            client.listDailyReports(limit)
        } catch (e: Exception) {
            Log.w(TAG, "loadDailyReports failed: ${e.message}")
            emptyList()
        }
    }

    suspend fun replyTicket(ticketId: Int, reply: String): TickTicketDto? {
        val client = api() ?: return null
        val trimmed = reply.trim()
        if (trimmed.isEmpty()) return null
        return try {
            val res = client.replyTicket(ticketId, TicketReplyRequest(trimmed))
            bus.emit(DataChangeEvent.HealthSignalChanged("tick"))
            res
        } catch (e: Exception) {
            Log.w(TAG, "replyTicket failed: ${e.message}")
            null
        }
    }

    suspend fun snoozeTicket(ticketId: Int, hours: Int = 24): TickTicketDto? {
        val client = api() ?: return null
        return try {
            val res = client.snoozeTicket(ticketId, TicketSnoozeRequest(hours))
            bus.emit(DataChangeEvent.HealthSignalChanged("tick"))
            res
        } catch (e: Exception) {
            Log.w(TAG, "snoozeTicket failed: ${e.message}")
            null
        }
    }

    suspend fun sendSilentMessage(
        content: String,
        category: String = "diet",
        mealType: String? = null,
    ): TickMessageDto? {
        val client = api() ?: return null
        val trimmed = content.trim()
        if (trimmed.isEmpty()) return null
        val meta = buildMap {
            if (!mealType.isNullOrBlank()) {
                put("meal_type", JsonPrimitive(mealType))
            }
        }
        return try {
            val res = client.sendMessage(
                TickMessageCreateRequest(
                    direction = "user_to_agent",
                    category = category,
                    content = trimmed,
                    meta = meta,
                    sourceChannel = "android",
                    autoLogDiet = (category == "diet"),
                )
            )
            bus.emit(DataChangeEvent.HealthSignalChanged(category))
            res
        } catch (e: Exception) {
            Log.w(TAG, "sendSilentMessage failed: ${e.message}")
            null
        }
    }
}
