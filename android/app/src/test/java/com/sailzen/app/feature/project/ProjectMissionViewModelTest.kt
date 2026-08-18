package com.sailzen.app.feature.project

import com.sailzen.app.core.network.dto.MissionState
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.hoursUntilDeadline
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.isMissionActive
import com.sailzen.app.feature.project.ProjectMissionViewModel.Companion.isOverdue
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectMissionViewModelTest {

    @Test
    fun isMissionActive_doneAndCanceledAreInactive() {
        assertFalse(isMissionActive(MissionState.DONE))
        assertFalse(isMissionActive(MissionState.CANCELED))
        assertTrue(isMissionActive(MissionState.PENDING))
        assertTrue(isMissionActive(MissionState.DOING))
    }

    @Test
    fun isOverdue_activeMissionWithPastDdlIsOverdue() {
        val pastDdl = (System.currentTimeMillis() / TimeUnit.SECONDS.toMillis(1)) - 3600.0
        assertTrue(isOverdue(pastDdl, MissionState.PENDING))
        assertFalse(isOverdue(pastDdl, MissionState.DONE))
    }

    @Test
    fun isOverdue_futureDdlIsNotOverdue() {
        val futureDdl = (System.currentTimeMillis() / TimeUnit.SECONDS.toMillis(1)) + 3600.0
        assertFalse(isOverdue(futureDdl, MissionState.PENDING))
    }

    @Test
    fun hoursUntilDeadline_calculatesDifferenceFromNow() {
        val nowSeconds = System.currentTimeMillis() / TimeUnit.SECONDS.toMillis(1)
        val ddl = nowSeconds + 7200.0
        assertEquals(2.0, hoursUntilDeadline(ddl), 0.05)
    }

    @Test
    fun hoursUntilDeadline_nullDdlReturnsInfinity() {
        assertEquals(Double.POSITIVE_INFINITY, hoursUntilDeadline(null), 0.0)
    }
}
