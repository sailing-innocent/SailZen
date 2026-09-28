package com.sailzen.app.core.text

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 同步状态归约器测试：离线/同步中/已同步/失败的显示优先级与状态迁移。
 */
class ReaderSyncStateTest {

    private fun reducer(): ReaderSyncStateReducer =
        ReaderSyncStateReducer(clockMillis = { 1_700_000_000_000L })

    @Test
    fun `offline takes display priority over everything`() {
        val r = reducer()
        r.onOnlineChanged(true)
        r.onSyncStart()
        r.onOnlineChanged(false)
        assertEquals(ReaderSyncState.Display.Offline, r.current().display)
        assertTrue(!r.current().syncing)
    }

    @Test
    fun `syncing shows while online and in flight`() {
        val r = reducer()
        r.onOnlineChanged(true)
        r.onSyncStart()
        assertEquals(ReaderSyncState.Display.Syncing, r.current().display)
    }

    @Test
    fun `success records timestamp and clears error`() {
        val r = reducer()
        r.onOnlineChanged(true)
        r.onSyncStart()
        r.onSyncFailure("boom")
        r.onSyncStart()
        r.onSyncSuccess()
        val state = r.current()
        assertEquals(ReaderSyncState.Display.Synced(1_700_000_000_000L), state.display)
        assertNull(state.lastError)
    }

    @Test
    fun `error shows when idle online and last sync failed`() {
        val r = reducer()
        r.onOnlineChanged(true)
        r.onSyncStart()
        r.onSyncFailure("timeout")
        val state = r.current()
        assertEquals(ReaderSyncState.Display.Error("timeout"), state.display)
    }

    @Test
    fun `going online clears previous error but keeps offline display`() {
        val r = reducer()
        r.onOnlineChanged(true)
        r.onSyncStart()
        r.onSyncFailure("timeout")
        r.onOnlineChanged(false)
        assertEquals(ReaderSyncState.Display.Offline, r.current().display)
        r.onOnlineChanged(true)
        // 恢复在线：错误被清空，回到 Idle（等待下次同步）
        assertEquals(ReaderSyncState.Display.Idle, r.current().display)
    }

    @Test
    fun `initial state is idle offline`() {
        val r = reducer()
        assertEquals(ReaderSyncState.Display.Offline, r.current().display)
    }
}
