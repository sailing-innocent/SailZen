package com.sailzen.app.feature.money

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.sailzen.app.core.money.MoneyRepository

/**
 * MoneyViewModel 工厂：构造器带默认 repository 参数，默认 AndroidViewModelFactory
 * 只能实例化仅含 (Application) 或空参构造的 AndroidViewModel，无法创建本类
 * （会直接 IllegalArgumentException 导致记账页打开即崩溃），必须显式提供工厂。
 * 模式与 affair/AffairDetailViewModelFactory 保持一致。
 */
class MoneyViewModelFactory(
    private val application: Application,
    private val repository: MoneyRepository? = null,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        MoneyViewModel(
            application,
            repository ?: MoneyRepository.get(application),
        ) as T
}
