package com.sailzen.app.feature.project

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class MissionDetailViewModelFactory(
    private val application: Application,
    private val missionId: Int,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass == MissionDetailViewModel::class.java)
        return MissionDetailViewModel(
            application = application,
            missionId = missionId,
        ) as T
    }
}
