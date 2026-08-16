package com.sailzen.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp

/**
 * 简单折线图（Canvas 自绘，M1 不引入第三方图表库）。
 * points: Pair<x 秒时间戳, y 数值>，自动按 x 排序并归一化坐标。
 */
@Composable
fun LineChart(
    points: List<Pair<Double, Double>>,
    modifier: Modifier = Modifier,
    lineColor: Color = Color(0xFF2196F3),
    pointColor: Color = Color(0xFF1565C0),
) {
    Canvas(modifier = modifier.fillMaxWidth().height(160.dp)) {
        if (points.size < 2) return@Canvas
        val sorted = points.sortedBy { it.first }
        val minX = sorted.first().first
        val maxX = sorted.last().first
        val minY = sorted.minOf { it.second }
        val maxY = sorted.maxOf { it.second }
        val rangeX = if (maxX > minX) maxX - minX else 1.0
        val rangeY = if (maxY > minY) maxY - minY else 1.0

        fun toOffset(p: Pair<Double, Double>): Offset {
            val x = ((p.first - minX) / rangeX).toFloat() * size.width
            val y = (1f - ((p.second - minY) / rangeY).toFloat()) * size.height
            return Offset(x, y.coerceIn(0f, size.height))
        }

        val path = androidx.compose.ui.graphics.Path().apply {
            moveTo(toOffset(sorted[0]).x, toOffset(sorted[0]).y)
            sorted.drop(1).forEach { p ->
                lineTo(toOffset(p).x, toOffset(p).y)
            }
        }
        drawPath(path, color = lineColor, style = Stroke(width = 3f))
        sorted.forEach { p ->
            drawCircle(
                color = pointColor,
                radius = 5f,
                center = toOffset(p),
            )
        }
    }
}

/**
 * 简单柱状图。bars: Pair<标签, 数值>。
 */
@Composable
fun BarChart(
    bars: List<Pair<String, Double>>,
    modifier: Modifier = Modifier,
    barColor: Color = Color(0xFF4CAF50),
) {
    Canvas(modifier = modifier.fillMaxWidth().height(160.dp)) {
        if (bars.isEmpty()) return@Canvas
        val maxValue = bars.maxOf { it.second }.coerceAtLeast(1.0)
        val count = bars.size
        val gap = 8.dp.toPx()
        val barWidth = (size.width - gap * (count + 1)) / count
        bars.forEachIndexed { index, (_, value) ->
            val barHeight = ((value / maxValue).toFloat() * size.height).coerceIn(0f, size.height)
            val left = gap + index * (barWidth + gap)
            val top = size.height - barHeight
            drawRect(
                color = barColor,
                topLeft = Offset(left, top),
                size = androidx.compose.ui.geometry.Size(barWidth, barHeight),
            )
        }
    }
}
