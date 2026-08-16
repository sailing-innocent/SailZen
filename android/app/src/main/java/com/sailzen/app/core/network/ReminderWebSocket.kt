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
import java.net.UnknownHostException
import java.util.concurrent.TimeUnit
import kotlin.random.Random

/**
 * OkHttp WebSocket 长连接（设计文档通道 1）。
 *
 * - 连接 ws(s)://host/api/v1/reminder/ws?device_id=..&token=..
 * - 收到 reminder.delivered → onReminder 回调
 * - 30s 文本 ping 保活（服务端回 pong）
 * - 断线后快速重连：0s → 500ms → 1s → 2s → 5s → 10s → 30s → 60s → 5min（封顶）
 *   并加入 ±25% jitter，避免多设备同时冲击服务器。
 * - 曾成功连接过的会话断开后，从 0ms 开始重试，以最快恢复服务端重启/网络闪断。
 */
class ReminderWebSocket(
    private val scope: CoroutineScope,
    private val urlProvider: suspend () -> String?,
    private val onReminder: (ReminderDto) -> Unit,
    private val onStateChange: (connected: Boolean) -> Unit = {},
    private val onDetailedStateChange: (state: ConnectionState, detail: String) -> Unit = { _, _ -> },
) {

    companion object {
        private const val TAG = "ReminderWebSocket"
        private const val PING_INTERVAL_MS = 30_000L

        // 退避阶梯（毫秒）：第一次失败后立即重试，然后逐步加大
        private val BACKOFF_STEPS_MS = longArrayOf(0, 500, 1_000, 2_000, 5_000, 10_000, 30_000, 60_000, 300_000)
        private const val JITTER_PCT = 0.25

        // 曾成功连接后断开，从 0ms 开始立即重试，尽快恢复
        private const val RECONNECT_AFTER_OPENED_INDEX = 0
    }

    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS) // WS 长连接不设读超时
        .retryOnConnectionFailure(true)
        .build()

    private val json: Json = ApiClient.json

    @Volatile
    private var running = false

    private var loopJob: Job? = null
    private var pingJob: Job? = null
    private var socket: WebSocket? = null

    fun start() {
        if (running) {
            Log.d(TAG, "start() ignored: already running")
            return
        }
        running = true
        emitState(ConnectionState.DISCONNECTED, "starting reconnect loop")
        loopJob = scope.launch { reconnectLoop() }
    }

    fun stop() {
        Log.d(TAG, "stop() called")
        running = false
        loopJob?.cancel()
        pingJob?.cancel()
        try {
            socket?.close(1000, "client stop")
        } catch (_: Exception) {
        }
        socket = null
        emitConnected(false)
        emitState(ConnectionState.DISCONNECTED, "stopped by client")
    }

    private suspend fun reconnectLoop() {
        var attempt = 0
        var backoffIndex = 0
        while (running) {
            val url = try {
                urlProvider()
            } catch (e: Exception) {
                Log.w(TAG, "urlProvider failed: ${e.javaClass.simpleName}: ${e.message}")
                emitState(ConnectionState.ERROR, "urlProvider failed: ${e.javaClass.simpleName}: ${e.message}")
                delay(5_000)
                continue
            }

            if (url.isNullOrBlank()) {
                Log.d(TAG, "server URL not configured, waiting...")
                emitState(ConnectionState.WAITING, "server URL not configured")
                delay(5_000)
                continue
            }

            attempt++
            emitState(ConnectionState.CONNECTING, "attempt #$attempt -> $url")
            Log.i(TAG, "connection attempt #$attempt: $url")

            val opened = runSession(url)

            if (!running) {
                Log.d(TAG, "reconnect loop exiting: no longer running")
                break
            }

            // 会话结束：更新连接状态为 false
            emitConnected(false)

            // 选择退避档位
            val stepIndex = if (opened) {
                // 曾经连上 → 可能是服务端重启/网络闪断，从较快档位开始
                Log.d(TAG, "session was opened before disconnect; use faster reconnect")
                RECONNECT_AFTER_OPENED_INDEX.coerceAtMost(BACKOFF_STEPS_MS.lastIndex)
            } else {
                // 一直没连上 → 逐步退避
                (backoffIndex + 1).coerceAtMost(BACKOFF_STEPS_MS.lastIndex)
            }
            backoffIndex = stepIndex

            val baseWait = BACKOFF_STEPS_MS[stepIndex]
            val wait = if (baseWait > 0) {
                val jitter = (baseWait * JITTER_PCT * (Random.nextDouble() * 2 - 1)).toLong()
                (baseWait + jitter).coerceAtLeast(0)
            } else {
                0
            }

            Log.i(TAG, "reconnect in ${wait}ms (backoff step #$stepIndex, base=${baseWait}ms)")
            emitState(ConnectionState.WAITING, "reconnect in ${wait}ms (attempt #$attempt)")

            if (wait > 0) {
                delay(wait)
            }
        }
        emitState(ConnectionState.DISCONNECTED, "reconnect loop ended")
    }

    /**
     * 建立一次 WS 会话并挂起直到断开。
     * @return true 表示会话曾成功建立（收到 onOpen）
     */
    private suspend fun runSession(url: String): Boolean {
        val done = CompletableDeferred<Unit>()
        var opened = false
        var closeCode: Int? = null
        var closeReason: String? = null

        val request = Request.Builder().url(url).build()
        val ws = client.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    opened = true
                    Log.i(TAG, "ws opened: ${response.code} ${response.message}")
                    emitConnected(true)
                    emitState(ConnectionState.CONNECTED, "handshake OK")
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    Log.d(TAG, "ws message: ${text.take(200)}")
                    handleMessage(text)
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    Log.i(TAG, "ws closing: code=$code reason=$reason")
                    closeCode = code
                    closeReason = reason
                    webSocket.close(code, null)
                    if (!done.isCompleted) done.complete(Unit)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    Log.i(TAG, "ws closed: code=$code reason=$reason")
                    closeCode = code
                    closeReason = reason
                    if (!done.isCompleted) done.complete(Unit)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    val httpCode = response?.code
                    val headers = response?.headers?.toString()?.trim()?.replace("\n", " | ") ?: ""
                    val detail = classifyFailure(t, httpCode)
                    Log.w(
                        TAG,
                        "ws failure: $detail | http=${httpCode ?: "-"} | " +
                            "headers=[$headers] | throwable=${t.javaClass.simpleName}: ${t.message}"
                    )
                    emitState(ConnectionState.ERROR, "$detail (http=${httpCode ?: "-"})")
                    if (!done.isCompleted) done.complete(Unit)
                }
            },
        )
        socket = ws

        pingJob = scope.launch {
            while (running) {
                delay(PING_INTERVAL_MS)
                if (!running) break
                try {
                    val sent = ws.send("""{"type":"ping"}""")
                    Log.v(TAG, "ping sent=$sent")
                } catch (e: Exception) {
                    Log.w(TAG, "ping failed: ${e.javaClass.simpleName}: ${e.message}")
                    // 让 receive 抛异常自然结束会话，不在这里关闭，避免竞争
                    break
                }
            }
        }

        try {
            done.await()
        } catch (e: CancellationException) {
            Log.d(TAG, "runSession cancelled")
            try {
                ws.close(1000, "client cancelled")
            } catch (_: Exception) {
            }
            throw e
        } finally {
            Log.d(TAG, "runSession ended (opened=$opened, closeCode=$closeCode, closeReason=$closeReason)")
            pingJob?.cancel()
            pingJob = null
            socket = null
            // 主动 cancel 以释放 OkHttp 内部资源
            ws.cancel()
        }
        return opened
    }

    private fun classifyFailure(t: Throwable, httpCode: Int?): String {
        return when {
            t is UnknownHostException -> "DNS_UNKNOWN"
            httpCode == 401 || httpCode == 403 -> "AUTH_FAILED"
            httpCode != null && httpCode >= 400 -> "HTTP_$httpCode"
            t.message?.contains("ECONNREFUSED", ignoreCase = true) == true -> "CONN_REFUSED"
            t.message?.contains("ETIMEDOUT", ignoreCase = true) == true -> "CONN_TIMEOUT"
            t.message?.contains("Network is unreachable", ignoreCase = true) == true -> "NET_UNREACHABLE"
            else -> "TRANSPORT_ERROR"
        }
    }

    private fun handleMessage(text: String) {
        val message = try {
            json.decodeFromString(WsMessage.serializer(), text)
        } catch (e: Exception) {
            Log.w(TAG, "bad ws message: ${e.message} | text=${text.take(200)}")
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
            "connected" -> Log.i(TAG, "server acknowledged connection")
            "pong" -> Log.v(TAG, "pong received")
            else -> Log.d(TAG, "ignored ws message type: ${message.type}")
        }
    }

    private fun emitConnected(connected: Boolean) {
        scope.launch {
            onStateChange(connected)
        }
    }

    private fun emitState(state: ConnectionState, detail: String) {
        Log.d(TAG, "state=$state detail=$detail")
        scope.launch {
            onDetailedStateChange(state, detail)
        }
    }

    enum class ConnectionState {
        DISCONNECTED,
        CONNECTING,
        CONNECTED,
        WAITING,
        ERROR,
    }
}
