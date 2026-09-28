package com.sailzen.app.feature.reader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 分页 LRU 缓存测试：
 * - 相同 key 命中并返回同一实例（避免重复排版）；
 * - float 参数量化后命中（字号/行距微小浮差不导致缓存失效）；
 * - LRU 淘汰最久未访问项。
 */
class PageLayoutCacheTest {

    private fun spec(
        widthPx: Int = 1080,
        heightPx: Int = 2000,
        fontSizePx: Float = 48f,
        lineSpacingMult: Float = 1.5f,
        paragraphSpacingPx: Int = 24,
        paddingPx: Int = 48,
    ) = ReaderTextEngine.LayoutSpec(
        widthPx = widthPx,
        heightPx = heightPx,
        fontSizePx = fontSizePx,
        lineSpacingMult = lineSpacingMult,
        paragraphSpacingPx = paragraphSpacingPx,
        paddingPx = paddingPx,
    )

    private val samplePages = listOf(ReaderTextEngine.Page("abc", 0, 3))

    @Test
    fun `same spec hits cache and returns same instance`() {
        val cache = PageLayoutCache()
        val key = PageLayoutCache.Key.of(1, spec())
        cache.put(key, samplePages)

        val hit = cache.get(PageLayoutCache.Key.of(1, spec()))
        assertSame(samplePages, hit)
    }

    @Test
    fun `float spec values are quantized to key`() {
        val cache = PageLayoutCache()
        val key = PageLayoutCache.Key.of(1, spec(fontSizePx = 48f, lineSpacingMult = 1.5f))
        cache.put(key, samplePages)

        // 48.001f 量化后与 48f 同键；1.501f 量化后与 1.5f 同键
        val nearKey = PageLayoutCache.Key.of(1, spec(fontSizePx = 48.001f, lineSpacingMult = 1.501f))
        assertEquals(key, nearKey)
        assertSame(samplePages, cache.get(nearKey))
    }

    @Test
    fun `different chapters or sizes miss cache`() {
        val cache = PageLayoutCache()
        cache.put(PageLayoutCache.Key.of(1, spec()), samplePages)

        assertNull(cache.get(PageLayoutCache.Key.of(2, spec())))
        assertNull(cache.get(PageLayoutCache.Key.of(1, spec(fontSizePx = 60f))))
        assertNull(cache.get(PageLayoutCache.Key.of(1, spec(heightPx = 2400))))
    }

    @Test
    fun `lru evicts least recently accessed entry`() {
        val cache = PageLayoutCache(maxEntries = 2)
        val keyA = PageLayoutCache.Key.of(1, spec())
        val keyB = PageLayoutCache.Key.of(2, spec())
        val keyC = PageLayoutCache.Key.of(3, spec())
        cache.put(keyA, samplePages)
        cache.put(keyB, samplePages)
        // 访问 A，使 B 成为最久未访问
        cache.get(keyA)
        cache.put(keyC, samplePages)

        assertNull(cache.get(keyB))
        assertSame(samplePages, cache.get(keyA))
        assertSame(samplePages, cache.get(keyC))
    }
}
