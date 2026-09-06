package com.sailzen.app.feature.health.bodydata

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.R
import com.sailzen.app.ui.components.DateRangeSelector
import com.sailzen.app.ui.components.LineChart

/**
 * 身体数据曲线页：指标选择 + 单指标时序折线；选中体重时叠加计划预期曲线。
 * 分析徽章（当前值 / 趋势 / 拟合度）来自 body-data analysis 端点。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BodyDataCurveScreen(
    onBack: () -> Unit,
    viewModel: BodyDataCurveViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.health_body_data_curve)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            item {
                DateRangeSelector(
                    options = listOf("近 7 天", "近 30 天", "近 90 天"),
                    selected = state.rangeLabel,
                    onSelected = { viewModel.selectRange(it) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(state.metrics, key = { it.key }) { metric ->
                        FilterChip(
                            selected = state.selectedMetric == metric.key,
                            onClick = { viewModel.selectMetric(metric.key) },
                            label = { Text(metric.labelZh) },
                        )
                    }
                }
            }
            item {
                Text(stringResource(R.string.health_body_data_actual), style = MaterialTheme.typography.titleSmall)
                val points = state.series?.points.orEmpty().map { it.htime to it.value }
                if (points.isNotEmpty()) {
                    LineChart(
                        points = points,
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                    )
                } else if (!state.loading) {
                    Text(stringResource(R.string.health_body_data_empty), color = Color.Gray)
                }
            }
            if (state.selectedMetric == "weight") {
                item {
                    Text(
                        stringResource(R.string.health_body_data_plan_expected),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    val expectedPoints = state.expected?.points
                    if (!expectedPoints.isNullOrEmpty()) {
                        LineChart(
                            points = expectedPoints.map { it.htime to it.expectedWeight },
                            modifier = Modifier.fillMaxWidth().height(200.dp),
                            lineColor = Color(0xFF4CAF50),
                        )
                    } else if (!state.loading) {
                        Text(stringResource(R.string.health_no_plan), color = Color.Gray)
                    }
                }
            }
            state.analysis?.let { analysis ->
                val current = (analysis["current_value"] as? Number)?.toDouble()
                val slope = (analysis["slope"] as? Number)?.toDouble()
                val rSquared = (analysis["r_squared"] as? Number)?.toDouble()
                if (current != null) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                            Text("当前 %.1f".format(current), style = MaterialTheme.typography.bodySmall)
                            slope?.let { Text("日变化 %.2f".format(it), style = MaterialTheme.typography.bodySmall) }
                            rSquared?.let { Text("拟合度 %.2f".format(it), style = MaterialTheme.typography.bodySmall) }
                        }
                    }
                }
            }
            if (state.loading) {
                item {
                    Box(modifier = Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            }
        }
    }
}
