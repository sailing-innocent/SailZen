package com.sailzen.app.core.network

import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Retrofit / OkHttp 客户端工厂。
 * 按 (baseUrl, token) 缓存实例，设置变更后自动重建。
 */
object ApiClient {

    private var cachedKey: String? = null
    private var cachedApi: ReminderApi? = null
    private var cachedHealthKey: String? = null
    private var cachedHealthApi: HealthApi? = null

    val json: Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        encodeDefaults = true
    }

    private fun buildRetrofit(baseUrl: String, token: String): Retrofit {
        val normalized = normalizeBaseUrl(baseUrl)
        val okHttp = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val request = if (token.isNotBlank()) {
                    chain.request().newBuilder()
                        .header("Authorization", "Bearer $token")
                        .build()
                } else {
                    chain.request()
                }
                chain.proceed(request)
            }
            .addInterceptor(
                HttpLoggingInterceptor().apply {
                    level = HttpLoggingInterceptor.Level.BASIC
                }
            )
            .build()

        return Retrofit.Builder()
            .baseUrl("$normalized/")
            .client(okHttp)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }

    @Synchronized
    fun api(baseUrl: String, token: String): ReminderApi {
        val normalized = normalizeBaseUrl(baseUrl)
        val key = "$normalized|$token"
        cachedApi?.let { if (cachedKey == key) return it }
        return buildRetrofit(normalized, token).create(ReminderApi::class.java).also {
            cachedKey = key
            cachedApi = it
        }
    }

    /** Health API（缓存键独立） */
    @Synchronized
    fun healthApi(baseUrl: String, token: String): HealthApi {
        val normalized = normalizeBaseUrl(baseUrl)
        val key = "$normalized|$token"
        cachedHealthApi?.let { if (cachedHealthKey == key) return it }
        return buildRetrofit(normalized, token).create(HealthApi::class.java).also {
            cachedHealthKey = key
            cachedHealthApi = it
        }
    }

    /** Rhythm API（M3，缓存键与 ReminderApi/HealthApi 独立） */
    @Synchronized
    fun rhythmApi(baseUrl: String, token: String): RhythmApi {
        val normalized = normalizeBaseUrl(baseUrl)
        val key = "$normalized|$token"
        cachedRhythmApi?.let { if (cachedRhythmKey == key) return it }
        return buildRetrofit(normalized, token).create(RhythmApi::class.java).also {
            cachedRhythmKey = key
            cachedRhythmApi = it
        }
    }

    /** 构造 WebSocket 地址：ws(s)://host/api/v1/reminder/ws?device_id=..&token=.. */
    fun wsUrl(baseUrl: String, deviceId: String, token: String): String {
        var url = normalizeBaseUrl(baseUrl)
        url = when {
            url.startsWith("https://") -> "wss://" + url.removePrefix("https://")
            url.startsWith("http://") -> "ws://" + url.removePrefix("http://")
            else -> "ws://$url"
        }
        val encodedToken = URLEncoder.encode(token, "UTF-8")
        return "$url/api/v1/reminder/ws?device_id=$deviceId&token=$encodedToken"
    }

    /** 容忍用户输入不带 scheme 的地址（默认补 http://），去掉末尾 / */
    fun normalizeBaseUrl(raw: String): String {
        var url = raw.trim().trimEnd('/')
        if (url.isNotBlank() && !url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://$url"
        }
        return url
    }
}
