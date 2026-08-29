package com.sailzen.app.core.data

import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DataChangeBusTest {

    @Test
    fun singleton_returnsSameInstance() {
        val a = DataChangeBus.get()
        val b = DataChangeBus.get()
        assertTrue(a === b)
    }

    @Test
    fun event_isDeliveredToActiveCollector() = runBlocking {
        val bus = DataChangeBus.get()
        val deferred = async { bus.events.first() }
        yield() // ensure collector is active

        bus.emit(DataChangeEvent.WeightChanged())
        val received = deferred.await()

        assertTrue(received is DataChangeEvent.WeightChanged)
    }

    @Test
    fun multipleCollectors_receiveEvent() = runBlocking {
        val bus = DataChangeBus.get()
        val deferredA = async { bus.events.first() }
        val deferredB = async { bus.events.first() }
        yield()

        bus.emit(DataChangeEvent.AffairChanged(affairId = 1, action = "delete"))

        val receivedA = deferredA.await() as DataChangeEvent.AffairChanged
        val receivedB = deferredB.await() as DataChangeEvent.AffairChanged
        assertEquals(1, receivedA.affairId)
        assertEquals("delete", receivedA.action)
        assertEquals(1, receivedB.affairId)
        assertEquals("delete", receivedB.action)
    }

    @Test
    fun lateSubscriber_doesNotReceiveOldEvent() = runBlocking {
        val bus = DataChangeBus.get()
        val early = async { bus.events.first() }
        yield()
        bus.emit(DataChangeEvent.WeightChanged())
        early.await()

        // 新订阅者不应收到旧事件；只有新事件到达时才会收到
        val late = async { bus.events.first() }
        yield()
        bus.emit(DataChangeEvent.DayViewChanged())
        val received = late.await()

        assertTrue(received is DataChangeEvent.DayViewChanged)
    }
}
