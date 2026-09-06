package com.sailzen.app.feature.health.bodydata

import android.app.Application
import android.content.Context
import androidx.lifecycle.viewModelScope
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
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * 记录页 ViewModel 语义测试（JVM，手写 FakeApplication）：
 * - 空输入 = 未测量，不进 data；
 * - 自定义指标仅在键合法且数值有效时并入；
 * - 全部留空时 submit 给出可读错误（repository 在无服务器环境下 fail-soft）。
 *
 * 说明：
 * - android.jar 位于 bootstrap classpath，Mockito inline 无法插桩 Application，
 *   故使用最小 fake（仅自引用 applicationContext + 临时 filesDir）；
 * - debug 构建 SERVER_URL 为空字符串 → apiOrNull 早退 null → 不触网；
 * - viewModelScope 的异步恢复经 TestMainDispatcher 调度，断言前需等待协程完成；
 *   tearDown 必须取消 VM scope，否则孤儿 collector 会在 resetMain 后污染
 *   后续测试（如 DataChangeBusTest）。
 */
@OptIn(ExperimentalCoroutinesApi::class)
class BodyDataRecordViewModelTest {

    private val testDispatcher = UnconfinedTestDispatcher()
    private val vms = mutableListOf<BodyDataRecordViewModel>()

    /** 最小 Application fake：仅提供自引用 applicationContext 与临时 filesDir。 */
    private class FakeApplication : Application() {
        override fun getApplicationContext(): Context = this
        override fun getFilesDir(): File =
            File(System.getProperty("java.io.tmpdir") ?: ".", "sailzen-test-files")
    }

    private fun newVm(): BodyDataRecordViewModel =
        BodyDataRecordViewModel(FakeApplication()).also(vms::add)

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
    fun buildMeasuredData_blankAndInvalidInputsAreNotMeasured() {
        val vm = newVm()
        val state = BodyDataRecordViewModel.UiState(
            values = mapOf(
                "weight" to "70.5",
                "water" to "",
                "waist" to "not-a-number",
            ),
        )
        assertEquals(mapOf("weight" to 70.5), vm.buildMeasuredData(state))
    }

    @Test
    fun buildMeasuredData_customMetricOnlyWhenKeyValidAndValueParses() {
        val vm = newVm()
        val valid = BodyDataRecordViewModel.UiState(
            values = mapOf("weight" to "70.5"),
            customKey = "x_steps",
            customValue = "8000",
        )
        assertEquals(8000.0, vm.buildMeasuredData(valid)["x_steps"]!!, 0.0)

        val invalidKey = valid.copy(customKey = "Steps", customValue = "8000")
        assertNull(vm.buildMeasuredData(invalidKey)["x_steps"])

        val invalidValue = valid.copy(customValue = "abc")
        assertNull(vm.buildMeasuredData(invalidValue)["x_steps"])
    }

    @Test
    fun submit_allBlankReportsError() {
        val vm = newVm()
        vm.submit()
        assertEquals("请至少填写一项指标", vm.uiState.value.error)
        assertTrue(!vm.uiState.value.submitted)
    }

    @Test
    fun submit_validInputWithoutServerFailsSoftWithError() = runBlocking {
        val vm = newVm()
        vm.setValue("weight", "70.5")
        vm.submit()
        // 等待 viewModelScope 协程完成（异步恢复经 TestMainDispatcher 调度）
        withTimeoutOrNull(3000) {
            while (vm.uiState.value.submitting && vm.uiState.value.error == null) delay(50)
        }
        // debug 构建 SERVER_URL 为空 → apiOrNull 返回 null → repository 返回 Failure，
        // UI 呈现错误且不崩溃
        assertNotNull(vm.uiState.value.error)
        assertTrue(!vm.uiState.value.submitting)
        assertTrue(!vm.uiState.value.submitted)
    }
}
