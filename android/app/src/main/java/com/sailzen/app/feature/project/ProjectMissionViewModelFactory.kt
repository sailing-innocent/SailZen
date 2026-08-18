package com.sailzen.app.feature.project

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider

class ProjectMissionViewModelFactory(
    private val application: Application,
    private val projectId: Int,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass == ProjectMissionViewModel::class.java)
        return ProjectMissionViewModel(
            application = application,
            projectId = projectId,
        ) as T
    }
}
