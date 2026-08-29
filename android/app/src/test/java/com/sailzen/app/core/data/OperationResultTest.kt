package com.sailzen.app.core.data

import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class OperationResultTest {

    @Test
    fun success_wrapsValue() {
        val result = OperationResult.Success(42)
        assertTrue(result.isSuccess())
        assertFalse(result.isFailure())
        assertEquals(42, result.getOrNull())
        assertNull(result.exceptionOrNull())
    }

    @Test
    fun failure_carriesMessageAndCause() {
        val cause = RuntimeException("boom")
        val result = OperationResult.Failure("failed", cause)
        assertFalse(result.isSuccess())
        assertTrue(result.isFailure())
        assertNull(result.getOrNull())
        assertSame(cause, result.exceptionOrNull())
        assertEquals("failed", (result as OperationResult.Failure).message)
    }

    @Test
    fun onSuccess_onlyRunsForSuccess() {
        var called = false
        OperationResult.Success(1).onSuccess { called = true }
        assertTrue(called)

        called = false
        OperationResult.Failure("err").onSuccess { called = true }
        assertFalse(called)
    }

    @Test
    fun onFailure_onlyRunsForFailure() {
        var called = false
        OperationResult.Failure("err").onFailure { called = true }
        assertTrue(called)

        called = false
        OperationResult.Success(1).onFailure { called = true }
        assertFalse(called)
    }

    @Test
    fun map_transformsSuccessValue() {
        val result: OperationResult<Int> = OperationResult.Success(2)
        val mapped: OperationResult<Int> = result.map { it * 3 }
        assertEquals(6, mapped.getOrNull())
    }

    @Test
    fun map_passesFailureThrough() {
        val result: OperationResult<Int> = OperationResult.Failure("err")
        val mapped: OperationResult<Int> = result.map { it + 1 }
        assertTrue(mapped.isFailure())
    }

    @Test
    fun runOperation_emitsEventOnSuccess() = runBlocking {
        val bus = DataChangeBus.get()
        val deferred = async { bus.events.first() }
        yield()

        val result = runOperation(bus, block = { "ok" }, onSuccess = { DataChangeEvent.WeightChanged() })

        assertTrue(result.isSuccess())
        assertEquals("ok", result.getOrNull())
        val received = deferred.await()
        assertTrue(received is DataChangeEvent.WeightChanged)
    }

    @Test
    fun runOperation_returnsFailureWithoutEvent() = runBlocking {
        val bus = DataChangeBus.get()
        var received = false
        val job = launch { bus.events.collect { received = true } }
        yield()

        val result = runOperation(bus, block = { error("fail") }, onSuccess = { DataChangeEvent.WeightChanged() })

        assertTrue(result.isFailure())
        assertEquals("fail", result.exceptionOrNull()?.message)
        delay(50)
        assertFalse(received)

        job.cancel()
    }
}
