package com.sailzen.app.feature.reader

/**
 * 通用 access-order LRU 缓存（不依赖 android.util.LruCache，保证 JVM 单测可跑）。
 */
class LruCache<K, V>(private val maxEntries: Int = 24) {

    private val map = object : LinkedHashMap<K, V>(maxEntries, 0.75f, true) {
        override fun removeEldestEntry(eldest: Map.Entry<K, V>): Boolean = size > maxEntries
    }

    @Synchronized
    fun get(key: K): V? = map[key]

    @Synchronized
    fun put(key: K, value: V) {
        map[key] = value
    }

    @Synchronized
    fun clear() {
        map.clear()
    }
}

/**
 * 分页结果 LRU 缓存：消灭「重复打开/字号微调/横竖屏切换」时的重复排版，
 * 也是预排版（后台排好下一章）的落地处。
 */
class PageLayoutCache(maxEntries: Int = 24) {

    /**
     * 排版缓存键：把 float 参数量化为整型，避免位模式差异导致的缓存失效。
     * 分页与行序排版共用同一键空间。
     */
    data class Key(
        val chapterId: Int,
        val widthPx: Int,
        val heightPx: Int,
        val fontSizeQ: Int,      // fontSizePx * 100 取整
        val lineSpacingQ: Int,   // lineSpacingMult * 100 取整
        val paragraphSpacingPx: Int,
        val paddingPx: Int,
    ) {
        companion object {
            fun of(
                chapterId: Int,
                spec: ReaderTextEngine.LayoutSpec,
            ): Key = Key(
                chapterId = chapterId,
                widthPx = spec.widthPx,
                heightPx = spec.heightPx,
                fontSizeQ = (spec.fontSizePx * 100f).toInt(),
                lineSpacingQ = (spec.lineSpacingMult * 100f).toInt(),
                paragraphSpacingPx = spec.paragraphSpacingPx,
                paddingPx = spec.paddingPx,
            )
        }
    }

    private val store = LruCache<Key, List<ReaderTextEngine.Page>>(maxEntries)

    fun get(key: Key): List<ReaderTextEngine.Page>? = store.get(key)

    fun put(key: Key, pages: List<ReaderTextEngine.Page>) = store.put(key, pages)

    fun clear() = store.clear()
}

/**
 * 行序排版 LRU 缓存（滚动模式）：切章/字号微调/旋转不重排行。
 */
class LineLayoutCache(maxEntries: Int = 24) {

    private val store = LruCache<PageLayoutCache.Key, List<ReaderTextEngine.Line>>(maxEntries)

    fun get(key: PageLayoutCache.Key): List<ReaderTextEngine.Line>? = store.get(key)

    fun put(key: PageLayoutCache.Key, lines: List<ReaderTextEngine.Line>) = store.put(key, lines)

    fun clear() = store.clear()
}
