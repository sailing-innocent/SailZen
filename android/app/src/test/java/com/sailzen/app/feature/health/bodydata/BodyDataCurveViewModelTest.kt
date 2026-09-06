package com.sailzen.app.feature.health.bodydata

import android.app.Application
import android.content.Context
import androidx.lifecycle.viewModelScope
import com.sailzen.app.core.network.dto.BUILTIN_BODY_METRICS
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * 曲线页 ViewModel 状态测试（JVM，手写 FakeApplication）：
 * 默认选中 weight、内置指标 fallback、指标/区间切换即时生效；
 * 无服务器环境下加载 fail-soft 不崩溃。
 *
 * tearDown 取消 VM scope，避免孤儿 bus collector 在 resetMain 后污染后续测试。
 */
@OptIn(ExperimentalCoroutinesApi::class)
class BodyDataCurveViewModelTest {

    private val testDispatcher = UnconfinedTestDispatcher()
    private val vms = mutableListOf<BodyDataCurveViewModel>()

    /** 最小 Application fake：仅提供自引用 applicationContext 与临时 filesDir。 */
    private class FakeApplication : Application() {
        override fun getApplicationContext(): Context = this
        override fun getFilesDir(): File =
            File(System.getProperty("java.io.tmpdir") ?: ".", "sailzen-test-files")
    }

    private fun newVm(): BodyDataCurveViewModel =
        BodyDataCurveViewModel(FakeApplication()).also(vms::add)

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        vms.forEach { it.viewModelScope.cancel() }
        vms.clear()
        Dispatchers.resetMain()
    }

    @Test
    fun initialState_defaultsToWeightWithBuiltinMetrics() {
        val vm = newVm()
        assertEquals("weight", vm.uiState.value.selectedMetric)
        assertEquals("近 7 天", vm.uiState.value.rangeLabel)
        assertEquals(BUILTIN_BODY_METRICS, vm.uiState.value.metrics)
    }

    @Test
    fun selectMetric_updatesState() {
        val vm = newVm()
        vm.selectMetric("waist")
        assertEquals("waist", vm.uiState.value.selectedMetric)
    }

    @Test
    fun selectRange_updatesState() {
        val vm = newVm()
        vm.selectRange("近 90 天")
        assertEquals("近 90 天", vm.uiState.value.rangeLabel)
    }

    @Test
    fun loadWithoutServerFailsSoft() = runBlocking {
        val vm = newVm()
        vm.load()
        // 等待 viewModelScope 协程完成（异步恢复经 TestMainDispatcher 调度）
        withTimeoutOrNull(3000) {
            while (vm.uiState.value.loading) delay(50)
        }
        // 无服务器：series/analysis 为 null，加载结束且无异常抛出
        assertTrue(!vm.uiState.value.loading)
        assertEquals(null, vm.uiState.value.series)
    }
}
