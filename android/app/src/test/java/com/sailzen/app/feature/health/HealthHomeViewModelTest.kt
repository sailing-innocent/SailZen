package com.sailzen.app.feature.health

import org.junit.Assert.assertEquals
import org.junit.Test

class HealthHomeViewModelTest {

    @Test
    fun weightLabelRes_mapsStatusToStringResources() {
        assertEquals(com.sailzen.app.R.string.health_weight_status_above, HealthHomeViewModel.weightLabelRes("above"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_below, HealthHomeViewModel.weightLabelRes("below"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_normal, HealthHomeViewModel.weightLabelRes("normal"))
        assertEquals(com.sailzen.app.R.string.health_weight_status_normal, HealthHomeViewModel.weightLabelRes("unknown"))
    }
}
