package com.sailzen.app.feature.affair

import com.sailzen.app.core.network.dto.AffairActions
import com.sailzen.app.core.network.dto.AffairStates
import com.sailzen.app.core.rhythm.RhythmTime
import com.sailzen.app.feature.affair.AffairHomeViewModel.Companion.availableActions
import com.sailzen.app.feature.affair.AffairHomeViewModel.Companion.isOverdue
import com.sailzen.app.feature.affair.AffairHomeViewModel.Companion.isTerminal
import java.time.LocalDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AffairHomeViewModelTest {

    @Test
    fun isTerminal_coversDoneCanceledArchived() {
        assertTrue(isTerminal(AffairStates.DONE))
        assertTrue(isTerminal(AffairStates.CANCELED))
        assertTrue(isTerminal(AffairStates.ARCHIVED))
        assertFalse(isTerminal(AffairStates.DOING))
        assertFalse(isTerminal(AffairStates.ACTIVE))
    }

    @Test
    fun isOverdue_pastDdlOnActiveAffair() {
        val past = RhythmTime.format(LocalDateTime.now().minusHours(2))
        assertTrue(isOverdue(past, AffairStates.PLANNED))
        assertFalse(isOverdue(past, AffairStates.DONE))
    }

    @Test
    fun isOverdue_futureOrMissingDdlIsNotOverdue() {
        val future = RhythmTime.format(LocalDateTime.now().plusHours(2))
        assertFalse(isOverdue(future, AffairStates.PLANNED))
        assertFalse(isOverdue(null, AffairStates.PLANNED))
    }

    @Test
    fun availableActions_ventureUsesLongtermFlow() {
        val actions = availableActions("venture", AffairStates.ACTIVE).map { it.first }
        assertEquals(listOf(AffairActions.PAUSE, AffairActions.GRADUATE, AffairActions.ARCHIVE), actions)
    }

    @Test
    fun availableActions_habitHasNoGraduate() {
        val actions = availableActions("habit", AffairStates.ACTIVE).map { it.first }
        assertEquals(listOf(AffairActions.PAUSE, AffairActions.ARCHIVE), actions)
    }

    @Test
    fun availableActions_oneoffTaskFlow() {
        assertEquals(
            listOf(AffairActions.CONFIRM, AffairActions.CANCEL),
            availableActions("task_oneoff", AffairStates.INBOX).map { it.first },
        )
        assertEquals(
            listOf(AffairActions.FINISH),
            availableActions("task_oneoff", AffairStates.DOING).map { it.first },
        )
    }

    @Test
    fun availableActions_terminalStateHasNoAction() {
        assertTrue(availableActions("task_oneoff", AffairStates.DONE).isEmpty())
        assertTrue(availableActions("venture", AffairStates.ARCHIVED).isEmpty())
    }

    @Test
    fun rhythmTime_parsesNaiveAndZonedIso() {
        val expected = LocalDateTime.of(2026, 8, 18, 9, 0, 0)
        assertEquals(expected, RhythmTime.parse("2026-08-18T09:00:00"))
        assertEquals(expected, RhythmTime.parse("2026-08-18T09:00:00Z"))
        assertEquals(expected, RhythmTime.parse("2026-08-18T09:00:00+08:00"))
        assertEquals(LocalDateTime.of(2026, 8, 18, 0, 0), RhythmTime.parse("2026-08-18"))
        assertNull(RhythmTime.parse(null))
        assertNull(RhythmTime.parse("  "))
    }

    @Test
    fun rhythmTime_hoursUntil() {
        val now = LocalDateTime.of(2026, 8, 18, 9, 0, 0)
        assertEquals(2.0, RhythmTime.hoursUntil("2026-08-18T11:00:00", now), 0.001)
        assertEquals(-1.0, RhythmTime.hoursUntil("2026-08-18T08:00:00", now), 0.001)
        assertEquals(Double.POSITIVE_INFINITY, RhythmTime.hoursUntil(null, now), 0.0)
    }
}
