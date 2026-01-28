/**
 * @file project.ts
 * @brief Stores for Projects and Missions
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import { type ProjectCreateProps, type ProjectData, type MissionCreateProps, type MissionData } from '@lib/data/project'

import {
  api_get_projects,
  api_get_project,
  api_create_project,
  api_update_project,
  api_delete_project,
  api_get_missions,
  api_get_mission,
  api_create_mission,
  api_update_mission,
  api_delete_mission,
  api_pending_mission,
  api_ready_mission,
  api_doing_mission,
  api_done_mission,
  api_cancel_mission,
  api_postpone_mission,
  api_get_upcoming_missions,
  api_get_overdue_missions,
} from '@lib/api/project'

export interface ProjectsState {
  projects: ProjectData[]
  isLoading: boolean
  fetchProjects: () => Promise<void>
  fetchProject: (id: number) => Promise<ProjectData>
  createProject: (project: ProjectCreateProps) => Promise<ProjectData>
  updateProject: (id: number, project: ProjectCreateProps) => Promise<ProjectData>
  deleteProject: (id: number) => Promise<boolean>
}

export const useProjectsStore: UseBoundStore<StoreApi<ProjectsState>> = create<ProjectsState>((set) => ({
  projects: [],
  isLoading: false,
  fetchProjects: async (): Promise<void> => {
    set({ isLoading: true })
    try {
      const projects = await api_get_projects()
      set({ projects: projects, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  fetchProject: async (id: number): Promise<ProjectData> => {
    const project = await api_get_project(id)
    set((state: ProjectsState): ProjectsState => {
      const index = state.projects.findIndex((p: ProjectData) => p.id === project.id)
      const nextState: ProjectsState = {
        ...state,
        projects: [...state.projects],
      }
      if (index !== -1) {
        nextState.projects[index] = project
      } else {
        nextState.projects.push(project)
      }
      return nextState
    })
    return project
  },
  createProject: async (project: ProjectCreateProps): Promise<ProjectData> => {
    const newProject = await api_create_project(project)
    set((state: ProjectsState): ProjectsState => ({
      ...state,
      projects: [...state.projects, newProject],
    }))
    return newProject
  },
  updateProject: async (id: number, project: ProjectCreateProps): Promise<ProjectData> => {
    const updatedProject = await api_update_project(id, project)
    set((state: ProjectsState): ProjectsState => {
      const index = state.projects.findIndex((p: ProjectData) => p.id === updatedProject.id)
      const nextState: ProjectsState = {
        ...state,
        projects: [...state.projects],
      }
      if (index !== -1) {
        nextState.projects[index] = updatedProject
        return nextState
      }
      return state
    })
    return updatedProject
  },
  deleteProject: async (id: number): Promise<boolean> => {
    const response = await api_delete_project(id)
    set((state: ProjectsState): ProjectsState => ({
      ...state,
      projects: state.projects.filter((p: ProjectData) => p.id !== id),
    }))
    return response.status === 'success'
  },
}))

export interface MissionsState {
  missions: MissionData[]
  upcomingMissions: MissionData[]
  overdueMissions: MissionData[]
  isLoading: boolean
  fetchMissions: (projectId?: number) => Promise<void>
  fetchMission: (id: number) => Promise<MissionData>
  createMission: (mission: MissionCreateProps) => Promise<MissionData>
  updateMission: (id: number, mission: MissionCreateProps) => Promise<MissionData>
  deleteMission: (id: number) => Promise<boolean>
  // State transitions
  pendingMission: (id: number) => Promise<MissionData>
  readyMission: (id: number) => Promise<MissionData>
  doingMission: (id: number) => Promise<MissionData>
  doneMission: (id: number) => Promise<MissionData>
  cancelMission: (id: number) => Promise<MissionData>
  postponeMission: (id: number, days?: number) => Promise<MissionData>
  // Reminder queries
  fetchUpcomingMissions: (hours?: number) => Promise<void>
  fetchOverdueMissions: () => Promise<void>
}

export const useMissionsStore: UseBoundStore<StoreApi<MissionsState>> = create<MissionsState>((set) => ({
  missions: [],
  upcomingMissions: [],
  overdueMissions: [],
  isLoading: false,
  fetchMissions: async (projectId?: number): Promise<void> => {
    set({ isLoading: true })
    try {
      const missions = await api_get_missions(projectId)
      set({ missions: missions, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  fetchMission: async (id: number): Promise<MissionData> => {
    const mission = await api_get_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === mission.id)
      const nextState: MissionsState = {
        ...state,
        missions: [...state.missions],
      }
      if (index !== -1) {
        nextState.missions[index] = mission
      } else {
        nextState.missions.push(mission)
      }
      return nextState
    })
    return mission
  },
  createMission: async (mission: MissionCreateProps): Promise<MissionData> => {
    const newMission = await api_create_mission(mission)
    set((state: MissionsState): MissionsState => ({
      ...state,
      missions: [...state.missions, newMission],
    }))
    return newMission
  },
  updateMission: async (id: number, mission: MissionCreateProps): Promise<MissionData> => {
    const updatedMission = await api_update_mission(id, mission)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      const nextState: MissionsState = {
        ...state,
        missions: [...state.missions],
      }
      if (index !== -1) {
        nextState.missions[index] = updatedMission
        return nextState
      }
      return state
    })
    return updatedMission
  },
  deleteMission: async (id: number): Promise<boolean> => {
    const response = await api_delete_mission(id)
    set((state: MissionsState): MissionsState => ({
      ...state,
      missions: state.missions.filter((m: MissionData) => m.id !== id),
    }))
    return response.status === 'success'
  },
  
  // Helper function to update mission in state
  _updateMissionInState: (updatedMission: MissionData, state: MissionsState): MissionsState => {
    const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
    const nextState: MissionsState = {
      ...state,
      missions: [...state.missions],
    }
    if (index !== -1) {
      nextState.missions[index] = updatedMission
    }
    return nextState
  },

  // State transitions
  pendingMission: async (id: number): Promise<MissionData> => {
    const updatedMission = await api_pending_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },
  
  readyMission: async (id: number): Promise<MissionData> => {
    const updatedMission = await api_ready_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },
  
  doingMission: async (id: number): Promise<MissionData> => {
    const updatedMission = await api_doing_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },
  
  doneMission: async (id: number): Promise<MissionData> => {
    const updatedMission = await api_done_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },
  
  cancelMission: async (id: number): Promise<MissionData> => {
    const updatedMission = await api_cancel_mission(id)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },
  
  postponeMission: async (id: number, days: number = 7): Promise<MissionData> => {
    const updatedMission = await api_postpone_mission(id, days)
    set((state: MissionsState): MissionsState => {
      const index = state.missions.findIndex((m: MissionData) => m.id === updatedMission.id)
      if (index !== -1) {
        const missions = [...state.missions]
        missions[index] = updatedMission
        return { ...state, missions }
      }
      return state
    })
    return updatedMission
  },

  // Reminder queries
  fetchUpcomingMissions: async (hours: number = 24): Promise<void> => {
    try {
      const missions = await api_get_upcoming_missions(hours)
      set({ upcomingMissions: missions })
    } catch (error) {
      console.error('Failed to fetch upcoming missions:', error)
    }
  },
  
  fetchOverdueMissions: async (): Promise<void> => {
    try {
      const missions = await api_get_overdue_missions()
      set({ overdueMissions: missions })
    } catch (error) {
      console.error('Failed to fetch overdue missions:', error)
    }
  },
}))


