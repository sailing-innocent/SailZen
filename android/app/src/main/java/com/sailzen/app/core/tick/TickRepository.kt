package com.sailzen.app.core.tick

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Log
import com.sailzen.app.core.data.DataChangeBus
import com.sailzen.app.core.data.DataChangeEvent
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.TickApi
import com.sailzen.app.core.network.dto.DailyReportDto
import com.sailzen.app.core.network.dto.HealthCoachSummaryDto
import com.sailzen.app.core.network.dto.ImageIntakeCommitRequest
import com.sailzen.app.core.network.dto.ImageIntakeCommitResponse
import com.sailzen.app.core.network.dto.ImageIntakeDraftDto
import com.sailzen.app.core.network.dto.TickMessageCreateRequest
import com.sailzen.app.core.network.dto.TickMessageDto
import com.sailzen.app.core.network.dto.TickTicketDto
import com.sailzen.app.core.network.dto.TicketReplyRequest
import com.sailzen.app.core.network.dto.TicketSnoozeRequest
import java.io.ByteArrayOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

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

    /**
     * 读取并按需等比压缩本地图片 Uri 为 JPEG 字节流（控制长边 <= 1600px，省流量且提速）。
     */
    suspend fun readAndCompressUri(uri: Uri, maxEdge: Int = 1600): Result<ByteArray> =
        withContext(Dispatchers.IO) {
            runCatching {
                val raw = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: error("无法读取所选图片")
                if (raw.isEmpty()) error("图片内容为空")
                val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeByteArray(raw, 0, raw.size, bounds)
                val w = bounds.outWidth
                val h = bounds.outHeight
                if (w <= 0 || h <= 0) {
                    // 无法解码但可能是 WebP/其他受服务端支持的格式，直接传原字节
                    return@runCatching raw
                }
                val aspect = maxOf(w, h).toFloat() / maxOf(1, minOf(w, h)).toFloat()
                val effectiveMax = if (aspect >= 2.4f) 2400 else maxEdge
                var sample = 1
                while (maxOf(w, h) / (sample * 2) >= effectiveMax) {
                    sample *= 2
                }
                val decodeOpts = BitmapFactory.Options().apply { inSampleSize = sample }
                val bmp = BitmapFactory.decodeByteArray(raw, 0, raw.size, decodeOpts)
                    ?: return@runCatching raw
                val finalBmp = if (maxOf(bmp.width, bmp.height) > effectiveMax) {
                    val scale = effectiveMax.toFloat() / maxOf(bmp.width, bmp.height).toFloat()
                    val nw = maxOf(1, (bmp.width * scale).toInt())
                    val nh = maxOf(1, (bmp.height * scale).toInt())
                    Bitmap.createScaledBitmap(bmp, nw, nh, true).also {
                        if (it !== bmp) bmp.recycle()
                    }
                } else {
                    bmp
                }
                val baos = ByteArrayOutputStream()
                finalBmp.compress(Bitmap.CompressFormat.JPEG, 86, baos)
                finalBmp.recycle()
                baos.toByteArray()
            }
        }

    /**
     * 上传图片至后端进行 DeepSeek Vision/OCR 识图分析，返回待人工确认草稿。
     */
    suspend fun analyzeImageIntake(
        imageBytes: ByteArray,
        filename: String = "capture.jpg",
        note: String = "",
        sourceChannel: String = "android",
        ticketId: Int? = null,
        useOcrAssist: String = "auto",
    ): Result<ImageIntakeDraftDto> {
        val client = api() ?: return Result.failure(IllegalStateException("尚未配置服务器地址"))
        return runCatching {
            val fileBody = imageBytes.toRequestBody("image/jpeg".toMediaType())
            val filePart = MultipartBody.Part.createFormData("file", filename, fileBody)
            val textPlain = "text/plain".toMediaType()
            client.analyzeImageIntake(
                file = filePart,
                note = note.trim().toRequestBody(textPlain),
                sourceChannel = sourceChannel.toRequestBody(textPlain),
                useOcrAssist = useOcrAssist.toRequestBody(textPlain),
                ticketId = ticketId?.toString()?.toRequestBody(textPlain),
            )
        }.onFailure { e ->
            Log.w(TAG, "analyzeImageIntake failed: ${e.message}")
        }
    }

    /** 确认并提交识图草稿，写入健康主表与教练消息。 */
    suspend fun commitIntakeDraft(
        draftId: Int,
        request: ImageIntakeCommitRequest,
    ): Result<ImageIntakeCommitResponse> {
        val client = api() ?: return Result.failure(IllegalStateException("尚未配置服务器地址"))
        return runCatching {
            val res = client.commitIntakeDraft(draftId, request)
            bus.emit(DataChangeEvent.HealthSignalChanged("intake"))
            res
        }.onFailure { e ->
            Log.w(TAG, "commitIntakeDraft failed: ${e.message}")
        }
    }

    /** 丢弃待确认识图草稿。 */
    suspend fun discardIntakeDraft(draftId: Int): Result<ImageIntakeDraftDto> {
        val client = api() ?: return Result.failure(IllegalStateException("尚未配置服务器地址"))
        return runCatching {
            client.discardIntakeDraft(draftId)
        }.onFailure { e ->
            Log.w(TAG, "discardIntakeDraft failed: ${e.message}")
        }
    }

    /** 拉取服务端已留存草稿的预览图字节（用于跨设备恢复未确认草稿时展示缩略图）。 */
    suspend fun fetchMediaBytes(mediaUrl: String): ByteArray? = withContext(Dispatchers.IO) {
        if (mediaUrl.isBlank()) return@withContext null
        val baseUrl = settings.serverUrl()
        if (baseUrl.isBlank()) return@withContext null
        val normalized = ApiClient.normalizeBaseUrl(baseUrl)
        val fullUrl = if (mediaUrl.startsWith("http")) {
            mediaUrl
        } else {
            "$normalized${if (mediaUrl.startsWith("/")) mediaUrl else "/$mediaUrl"}"
        }
        runCatching {
            val req = Request.Builder().url(fullUrl).get().build()
            ApiClient.downloadClient(settings.apiToken()).newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@use null
                resp.body?.bytes()
            }
        }.getOrNull()
    }
}
