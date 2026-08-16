package com.sailzen.app.feature.health

import android.app.Application
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mock
import org.mockito.junit.MockitoJUnitRunner

@RunWith(MockitoJUnitRunner::class)
class HealthHomeViewModelTest {

    @Mock
    lateinit var application: Application

    @Test
    fun weightLabelRes_mapsStatusToStringResources() {
        val viewModel = HealthHomeViewModel(application)
        assertEquals(com.sailzen.app.R.string.health_weight_status_above, viewModel.weightLabelRes("above"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_below, viewModel.weightLabelRes("below"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_normal, viewModel.weightLabelRes("normal"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_normal, viewModel.weightLabelRes("unknown"))
    }
}
