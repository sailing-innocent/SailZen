package com.sailzen.app.feature.affair

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class AffairDetailViewModelFactory(
    private val application: Application,
    private val affairId: Int,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        AffairDetailViewModel(application, affairId) as T
}
