import {
    type ProjectCreateProps,
    type ProjectData,
    type MissionCreateProps,
    type MissionData,
} from '@lib/data/project'

import { SERVER_URL, API_BASE } from './config'
const PROJECT_API_BASE = API_BASE + '/project'

// Project APIs
const api_get_projects = async (): Promise<ProjectData[]> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/project/`)
    return response.json()
}

const api_get_project = async (id: number): Promise<ProjectData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/project/${id}`)
    return response.json()
}

const api_create_project = async (project: ProjectCreateProps): Promise<ProjectData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/project/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(project),
    })
    return response.json()
}

const api_update_project = async (id: number, project: ProjectCreateProps): Promise<ProjectData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/project/${id}` , {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(project),
    })
    return response.json()
}

const api_delete_project = async (id: number): Promise<{ id: number, status: string, message?: string }> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/project/${id}`, {
        method: 'DELETE',
    })
    return response.json()
}

// Mission APIs
const api_get_missions = async (projectId?: number): Promise<MissionData[]> => {
    const url = projectId === undefined
        ? `${SERVER_URL}/${PROJECT_API_BASE}/mission/`
        : `${SERVER_URL}/${PROJECT_API_BASE}/mission/?project_id=${projectId}`
    const response = await fetch(url)
    return response.json()
}

const api_get_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}`)
    return response.json()
}

const api_create_mission = async (mission: MissionCreateProps): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(mission),
    })
    return response.json()
}

const api_update_mission = async (id: number, mission: MissionCreateProps): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(mission),
    })
    return response.json()
}

const api_delete_mission = async (id: number): Promise<{ id: number, status: string, message?: string }> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}`, {
        method: 'DELETE',
    })
    return response.json()
}

// Mission State Transition APIs
const api_pending_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/pending`, {
        method: 'POST',
    })
    return response.json()
}

const api_ready_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/ready`, {
        method: 'POST',
    })
    return response.json()
}

const api_doing_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/doing`, {
        method: 'POST',
    })
    return response.json()
}

const api_done_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/done`, {
        method: 'POST',
    })
    return response.json()
}

const api_cancel_mission = async (id: number): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/cancel`, {
        method: 'POST',
    })
    return response.json()
}

const api_postpone_mission = async (id: number, days: number = 7): Promise<MissionData> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/${id}/postpone?days=${days}`, {
        method: 'POST',
    })
    return response.json()
}

// Mission Reminder APIs
const api_get_upcoming_missions = async (hours: number = 24): Promise<MissionData[]> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/upcoming?hours=${hours}`)
    return response.json()
}

const api_get_overdue_missions = async (): Promise<MissionData[]> => {
    const response = await fetch(`${SERVER_URL}/${PROJECT_API_BASE}/mission/overdue`)
    return response.json()
}

export {
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
    // State transition APIs
    api_pending_mission,
    api_ready_mission,
    api_doing_mission,
    api_done_mission,
    api_cancel_mission,
    api_postpone_mission,
    // Reminder APIs
    api_get_upcoming_missions,
    api_get_overdue_missions,
}
