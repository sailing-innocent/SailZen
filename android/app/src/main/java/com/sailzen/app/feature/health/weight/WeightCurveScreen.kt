package com.sailzen.app.feature.health.weight

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.sailzen.app.ui.components.DateRangeSelector
import com.sailzen.app.ui.components.LineChart

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeightCurveScreen(
    onBack: () -> Unit,
    viewModel: WeightCurveViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("体重曲线") },
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
                Text("实际记录", style = MaterialTheme.typography.titleSmall)
                if (state.weights.isNotEmpty()) {
                    LineChart(
                        points = state.weights.mapNotNull { w ->
                            w.htime?.let { it to w.value }
                        },
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                    )
                } else if (!state.loading) {
                    Text("暂无记录", color = Color.Gray)
                }
            }

            item {
                Text("计划预期", style = MaterialTheme.typography.titleSmall)
                val expectedPoints = state.expected?.points
                if (!expectedPoints.isNullOrEmpty()) {
                    LineChart(
                        points = expectedPoints.map { it.htime to it.expectedWeight },
                        modifier = Modifier.fillMaxWidth().height(200.dp),
                        lineColor = Color(0xFF4CAF50),
                    )
                } else if (!state.loading) {
                    Text("无活跃体重计划", color = Color.Gray)
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
