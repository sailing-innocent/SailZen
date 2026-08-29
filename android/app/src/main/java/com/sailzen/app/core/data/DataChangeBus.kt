package com.sailzen.app.core.data

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * 应用级数据变更总线（单例）。
 *
 * Repository 在原子操作成功后发送 [DataChangeEvent]，
 * ViewModel 在生命周期内订阅相关事件以刷新跨页面数据。
 * 使用 SharedFlow 广播：replay=0，避免新订阅者收到旧事件导致重复刷新；
 * extraBufferCapacity=64 保证在 ViewModel 激活期间的事件可被及时消费。
 */
class DataChangeBus private constructor() {

    private val _events = MutableSharedFlow<DataChangeEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<DataChangeEvent> = _events.asSharedFlow()

    suspend fun emit(event: DataChangeEvent) {
        _events.emit(event)
    }

    companion object {
        @Volatile
        private var instance: DataChangeBus? = null

        fun get(): DataChangeBus = instance ?: synchronized(this) {
            instance ?: DataChangeBus().also { instance = it }
        }
    }
}
