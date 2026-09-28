package com.sailzen.app.feature.reader

import com.sailzen.app.core.data.db.CachedAnnotation

/**
 * 批注裁剪结果：批注 + 相对锚点（段落/行）起点的区间。
 */
data class ClippedAnnotation(
    val annotation: CachedAnnotation,
    val relStart: Int,
    val relEnd: Int,
)

/**
 * 将全局偏移批注裁剪为「锚点 startOffset → 相对区间」映射。
 *
 * 渲染列表（段落或行）按锚点切块：无批注的块直接渲染纯 Text，只有命中的
 * 块才构建 AnnotatedString。锚点必须按 start 升序且 start 唯一。
 * 复杂度 O(A·logN + 相交数)。
 */
fun clipAnnotationsByRanges(
    anchors: List<IntRange>,
    annotations: List<CachedAnnotation>,
): Map<Int, List<ClippedAnnotation>> {
    if (anchors.isEmpty() || annotations.isEmpty()) return emptyMap()
    val result = HashMap<Int, MutableList<ClippedAnnotation>>()
    val starts = IntArray(anchors.size) { anchors[it].first }
    for (anno in annotations) {
        var idx = starts.binarySearch(anno.startOffset)
        if (idx < 0) idx = -idx - 2
        idx = idx.coerceAtLeast(0)
        while (idx < anchors.size && anchors[idx].first < anno.endOffset) {
            val anchor = anchors[idx]
            val anchorLen = anchor.last - anchor.first
            if (anchor.last > anno.startOffset && anchorLen > 0) {
                val s = (anno.startOffset - anchor.first).coerceIn(0, anchorLen)
                val e = (anno.endOffset - anchor.first).coerceIn(s, anchorLen)
                if (s < e) {
                    result.getOrPut(anchor.first) { mutableListOf() }
                        .add(ClippedAnnotation(anno, s, e))
                }
            }
            idx++
        }
    }
    return result
}

/**
 * 段落级裁剪（兼容旧调用）。段落有序且 startOffset 唯一。
 */
fun clipAnnotationsByParagraph(
    paragraphs: List<Paragraph>,
    annotations: List<CachedAnnotation>,
): Map<Int, List<ClippedAnnotation>> =
    clipAnnotationsByRanges(paragraphs.map { it.startOffset..it.endOffset }, annotations)
