package com.sailzen.app.core.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.GET

/** 云端最新 Android Release 元数据（对应 GET /api/v1/app/release/latest） */
@Serializable
data class AppReleaseDto(
    @SerialName("version_code") val versionCode: Int,
    @SerialName("version_name") val versionName: String,
    @SerialName("file_name") val fileName: String,
    val size: Long = 0L,
    val sha256: String = "",
    @SerialName("release_notes") val releaseNotes: String = "",
    @SerialName("published_at") val publishedAt: String = "",
    @SerialName("download_path") val downloadPath: String = "",
)

interface AppUpdateApi {
    @GET("api/v1/app/release/latest")
    suspend fun getLatestRelease(): AppReleaseDto
}
