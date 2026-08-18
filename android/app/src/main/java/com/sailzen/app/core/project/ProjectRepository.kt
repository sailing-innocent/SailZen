package com.sailzen.app.core.project

import android.content.Context
import android.util.Log
import com.sailzen.app.core.data.SettingsManager
import com.sailzen.app.core.network.ApiClient
import com.sailzen.app.core.network.ProjectApi
import com.sailzen.app.core.network.dto.MissionCreateRequest
import com.sailzen.app.core.network.dto.MissionDto
import com.sailzen.app.core.network.dto.MissionUpdateRequest
import com.sailzen.app.core.network.dto.ProjectCreateRequest
import com.sailzen.app.core.network.dto.ProjectDto
import com.sailzen.app.core.network.dto.ProjectUpdateRequest
import com.sailzen.app.core.reminder.NotificationHelper

/**
 * 项目/任务数据仓库：封装 ProjectApi，提供与 site store 同名的能力。
 * 所有网络异常捕获并返回空/失败结果，不崩溃。
 */
class ProjectRepository private constructor(private val context: Context) {

    companion object {
        private const val TAG = "ProjectRepository"
        @Volatile
        private var instance: ProjectRepository? = null

        fun get(context: Context): ProjectRepository =
            instance ?: synchronized(this) {
                instance ?: ProjectRepository(context.applicationContext).also { instance = it }
            }
    }

    private val settings = SettingsManager.get(context)

    private suspend fun apiOrNull(): ProjectApi? {
        val url = settings.serverUrl()
        if (url.isBlank()) return null
        return try {
            ApiClient.projectApi(url, settings.apiToken())
        } catch (e: Exception) {
            Log.w(TAG, "api build failed: ${e.message}")
            null
        }
    }

    // ------------------------------------------------------------------
    // Project
    // ------------------------------------------------------------------

    suspend fun getProjects(): List<ProjectDto> = try {
        apiOrNull()?.getProjects() ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "getProjects failed: ${e.message}")
        emptyList()
    }

    suspend fun getProject(id: Int): ProjectDto? = try {
        apiOrNull()?.getProject(id)
    } catch (e: Exception) {
        Log.w(TAG, "getProject failed: ${e.message}")
        null
    }

    suspend fun createProject(body: ProjectCreateRequest): ProjectDto? = try {
        apiOrNull()?.createProject(body)
    } catch (e: Exception) {
        Log.w(TAG, "createProject failed: ${e.message}")
        null
    }

    suspend fun updateProject(id: Int, body: ProjectUpdateRequest): ProjectDto? = try {
        apiOrNull()?.updateProject(id, body)
    } catch (e: Exception) {
        Log.w(TAG, "updateProject failed: ${e.message}")
        null
    }

    suspend fun deleteProject(id: Int): Boolean = try {
        apiOrNull()?.deleteProject(id)?.status == "success"
    } catch (e: Exception) {
        Log.w(TAG, "deleteProject failed: ${e.message}")
        false
    }

    // ------------------------------------------------------------------
    // Mission
    // ------------------------------------------------------------------

    suspend fun getMissions(projectId: Int? = null): List<MissionDto> = try {
        apiOrNull()?.getMissions(projectId = projectId) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "getMissions failed: ${e.message}")
        emptyList()
    }

    suspend fun getMission(id: Int): MissionDto? = try {
        apiOrNull()?.getMission(id)
    } catch (e: Exception) {
        Log.w(TAG, "getMission failed: ${e.message}")
        null
    }

    suspend fun createMission(body: MissionCreateRequest): MissionDto? = try {
        apiOrNull()?.createMission(body)
    } catch (e: Exception) {
        Log.w(TAG, "createMission failed: ${e.message}")
        null
    }

    suspend fun updateMission(id: Int, body: MissionUpdateRequest): MissionDto? = try {
        apiOrNull()?.updateMission(id, body)
    } catch (e: Exception) {
        Log.w(TAG, "updateMission failed: ${e.message}")
        null
    }

    suspend fun deleteMission(id: Int): Boolean = try {
        apiOrNull()?.deleteMission(id)?.status == "success"
    } catch (e: Exception) {
        Log.w(TAG, "deleteMission failed: ${e.message}")
        false
    }

    suspend fun pendingMission(id: Int): MissionDto? = stateTransition(id) { it.pendingMission(id) }
    suspend fun readyMission(id: Int): MissionDto? = stateTransition(id) { it.readyMission(id) }
    suspend fun doingMission(id: Int): MissionDto? = stateTransition(id) { it.doingMission(id) }
    suspend fun doneMission(id: Int): MissionDto? = stateTransition(id) { it.doneMission(id) }
    suspend fun cancelMission(id: Int): MissionDto? = stateTransition(id) { it.cancelMission(id) }
    suspend fun postponeMission(id: Int, days: Int = 7): MissionDto? = stateTransition(id) { it.postponeMission(id, days) }

    private suspend fun stateTransition(id: Int, block: suspend (ProjectApi) -> MissionDto): MissionDto? = try {
        val api = apiOrNull() ?: return null
        block(api)
    } catch (e: Exception) {
        Log.w(TAG, "mission state transition failed: ${e.message}")
        null
    }

    // ------------------------------------------------------------------
    // Reminder queries
    // ------------------------------------------------------------------

    suspend fun getUpcomingMissions(hours: Int = 24): List<MissionDto> = try {
        apiOrNull()?.getUpcomingMissions(hours) ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "getUpcomingMissions failed: ${e.message}")
        emptyList()
    }

    suspend fun getOverdueMissions(): List<MissionDto> = try {
        apiOrNull()?.getOverdueMissions() ?: emptyList()
    } catch (e: Exception) {
        Log.w(TAG, "getOverdueMissions failed: ${e.message}")
        emptyList()
    }

    // ------------------------------------------------------------------
    // Local notification sync
    // ------------------------------------------------------------------

    /**
     * 周期同步 mission 提醒：将逾期/临近任务转换为本地通知。
     * 以 mission id 作为通知 id 的一部分，避免重复通知。
     */
    suspend fun syncMissionReminders() {
        val overdue = getOverdueMissions()
        val upcoming = getUpcomingMissions(hours = 24)

        overdue.forEach { mission ->
            NotificationHelper.notifyMissionReminder(
                context = context,
                missionId = mission.id,
                projectId = mission.projectId,
                title = context.getString(com.sailzen.app.R.string.mission_overdue_title),
                body = mission.name,
                isOverdue = true,
            )
        }

        upcoming.forEach { mission ->
            NotificationHelper.notifyMissionReminder(
                context = context,
                missionId = mission.id,
                projectId = mission.projectId,
                title = context.getString(com.sailzen.app.R.string.mission_upcoming_title),
                body = mission.name,
                isOverdue = false,
            )
        }
    }
}
