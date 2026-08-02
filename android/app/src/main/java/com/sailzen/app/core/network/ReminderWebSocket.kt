package com.sailzen.app.core.network

import android.util.Log
import com.sailzen.app.core.network.dto.ReminderDto
import com.sailzen.app.core.network.dto.WsMessage
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * OkHttp WebSocket 长连接（设计文档通道 1）。
 *
 * - 连接 ws(s)://host/api/v1/reminder/ws?device_id=..&token=..
 * - 收到 reminder.delivered → onReminder 回调
 * - 30s 文本 ping 保活（服务端回 pong）
 * - 断线指数退避重连：1s → 5s → 30s → 5min（封顶）
 */
class ReminderWebSocket(
    private val scope: CoroutineScope,
    private val urlProvider: suspend () -> String?,
    private val onReminder: (ReminderDto) -> Unit,
    private val onStateChange: (connected: Boolean) -> Unit = {},
) {

    companion object {
        private const val TAG = "ReminderWebSocket"
        private const val PING_INTERVAL_MS = 30_000L
        private val BACKOFF_STEPS_MS = longArrayOf(1_000L, 5_000L, 30_000L, 300_000L)
    }

    private val client = OkHttpClient.Builder()
        .readTimeout(0, java.util.concurrent.TimeUnit.MILLISECONDS) // WS 长连接不设读超时
        .retryOnConnectionFailure(true)
        .build()

    private val json: Json = ApiClient.json

    @Volatile
    private var running = false

    private var loopJob: Job? = null
    private var pingJob: Job? = null
    private var socket: WebSocket? = null

    fun start() {
        if (running) return
        running = true
        loopJob = scope.launch { reconnectLoop() }
    }

    fun stop() {
        running = false
        loopJob?.cancel()
        pingJob?.cancel()
        try {
            socket?.close(1000, null)
        } catch (_: Exception) {
        }
        socket = null
        onStateChange(false)
    }

    private suspend fun reconnectLoop() {
        var backoffIndex = 0
        while (running) {
            val url = try {
                urlProvider()
            } catch (e: Exception) {
                Log.w(TAG, "urlProvider failed: ${e.message}")
                null
            }
            if (url.isNullOrBlank()) {
                // 未配置服务器：低速轮询等待配置就绪
                delay(5_000)
                continue
            }
            val opened = runSession(url)
            if (!running) break
            onStateChange(false)
            if (opened) {
                backoffIndex = 1 // 曾连上过：从 5s 档开始退避
            } else {
                backoffIndex = (backoffIndex + 1).coerceAtMost(BACKOFF_STEPS_MS.lastIndex)
            }
            val wait = BACKOFF_STEPS_MS[backoffIndex]
            Log.d(TAG, "reconnect in ${wait}ms")
            delay(wait)
        }
    }

    /**
     * 建立一次 WS 会话并挂起直到断开。
     * @return true 表示会话曾成功建立（用于退避档位选择）
     */
    private suspend fun runSession(url: String): Boolean {
        val done = CompletableDeferred<Unit>()
        var opened = false

        val request = Request.Builder().url(url).build()
        val ws = client.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    opened = true
                    Log.d(TAG, "ws connected")
                    onStateChange(true)
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    handleMessage(text)
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    webSocket.close(code, null)
                    if (!done.isCompleted) done.complete(Unit)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    Log.d(TAG, "ws closed: $code $reason")
                    if (!done.isCompleted) done.complete(Unit)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.w(TAG, "ws failure: ${t.message} (http=${response?.code})")
                    if (!done.isCompleted) done.complete(Unit)
                }
            },
        )
        socket = ws

        pingJob = scope.launch {
            while (true) {
                delay(PING_INTERVAL_MS)
                try {
                    ws.send("""{"type":"ping"}""")
                } catch (_: Exception) {
                }
            }
        }

        try {
            done.await()
        } catch (e: CancellationException) {
            try {
                ws.close(1000, null)
            } catch (_: Exception) {
            }
            throw e
        } finally {
            pingJob?.cancel()
            socket = null
        }
        return opened
    }

    private fun handleMessage(text: String) {
        val message = try {
            json.decodeFromString(WsMessage.serializer(), text)
        } catch (e: Exception) {
            Log.w(TAG, "bad ws message: ${e.message}")
            return
        }
        when (message.type) {
            "reminder.delivered" -> {
                val data = message.data ?: return
                try {
                    val reminder = json.decodeFromJsonElement<ReminderDto>(data)
                    onReminder(reminder)
                } catch (e: Exception) {
                    Log.w(TAG, "bad reminder payload: ${e.message}")
                }
            }
            // connected / pong 等无需处理
            else -> Unit
        }
    }
}
