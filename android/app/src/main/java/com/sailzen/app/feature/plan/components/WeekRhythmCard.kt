package com.sailzen.app.feature.plan.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sailzen.app.core.network.dto.ReviewDto

/** 周节奏卡片：rhythm_score 环形图 + 戒律/习惯/事业三指标（点击看周报） */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeekRhythmCard(review: ReviewDto, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(containerColor = Color(0xFFE8F5E9)),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(12.dp),
        ) {
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(56.dp)) {
                CircularProgressIndicator(
                    progress = { (review.rhythmScore / 100.0).toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxSize(),
                    color = when {
                        review.rhythmScore >= 80 -> Color(0xFF4CAF50)
                        review.rhythmScore >= 60 -> Color(0xFFFFB300)
                        else -> Color(0xFFE53935)
                    },
                    strokeWidth = 5.dp,
                )
                Text(
                    "%.0f".format(review.rhythmScore),
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Spacer(Modifier.width(14.dp))
            Column {
                Text("本周节奏 ${review.periodKey}", fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(4.dp))
                Text(
                    "戒律 %.0f%% · 习惯 %.0f%% · 事业 %.0f%%".format(
                        review.preceptComplianceRate * 100,
                        review.habitConsistency * 100,
                        review.ventureBudgetFulfillment * 100,
                    ),
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF2E7D32),
                )
                Text(
                    "点击查看周报",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color.Gray,
                )
            }
        }
    }
}
