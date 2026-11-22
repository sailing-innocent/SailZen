package com.sailzen.app.core.update

import com.sailzen.app.core.network.AppReleaseDto
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class AppUpdateManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    @Test
    fun `isUpdateAvailable compares strictly by versionCode`() {
        assertTrue(AppUpdateManager.isUpdateAvailable(remoteVersionCode = 2, currentVersionCode = 1))
        assertFalse(AppUpdateManager.isUpdateAvailable(remoteVersionCode = 1, currentVersionCode = 1))
        assertFalse(AppUpdateManager.isUpdateAvailable(remoteVersionCode = 1, currentVersionCode = 2))
    }

    @Test
    fun `resolveDownloadUrl handles relative and fallback download paths`() {
        val withPath = AppReleaseDto(
            versionCode = 2,
            versionName = "0.2.0",
            fileName = "SailZen-0.2.0-vc2-release.apk",
            downloadPath = "/api/v1/app/release/download/SailZen-0.2.0-vc2-release.apk",
        )
        assertEquals(
            "https://sail.example.com/api/v1/app/release/download/SailZen-0.2.0-vc2-release.apk",
            AppUpdateManager.resolveDownloadUrl("https://sail.example.com/", withPath),
        )

        val withoutPath = withPath.copy(downloadPath = "")
        assertEquals(
            "http://1.2.3.4:1974/api/v1/app/release/download/SailZen-0.2.0-vc2-release.apk",
            AppUpdateManager.resolveDownloadUrl("1.2.3.4:1974", withoutPath),
        )
    }

    @Test
    fun `sha256Hex matches expected digest`() {
        val f: File = tempFolder.newFile("sample.apk")
        f.writeText("sailzen-ota-test", Charsets.UTF_8)
        assertEquals(
            "c89766b28fdecfe5c9b635953fb550ddc2c327db5a8f52326b6ea0eed9c5cf5e",
            AppUpdateManager.sha256Hex(f),
        )
    }

    @Test
    fun `formatFileSize formats bytes KB and MB`() {
        assertEquals("512 B", AppUpdateManager.formatFileSize(512))
        assertEquals("2.0 KB", AppUpdateManager.formatFileSize(2048))
        assertEquals("12.5 MB", AppUpdateManager.formatFileSize((12.5 * 1024 * 1024).toLong()))
    }
}
