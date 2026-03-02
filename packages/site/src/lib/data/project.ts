export interface ProjectCreateProps {
    name: string,
    description: string,
    start_time_qbw: number,  // QBW format: YYYYQQWW
    end_time_qbw: number     // QBW format: YYYYQQWW
}

export interface ProjectData extends ProjectCreateProps {
    id: number,
    state: number | undefined
}


export interface MissionCreateProps {
    name: string,
    description?: string,
    parent_id?: number,
    project_id?: number,
    ddl?: number
}

export interface MissionData extends Omit<MissionCreateProps, 'ddl'> {
    id: number,
    state: number | undefined
    ddl: number | string | null | undefined  // Can be ISO string from API or number timestamp
}

// Mission State Constants
export const MissionState = {
    PENDING: 0,
    READY: 1,
    DOING: 2,
    DONE: 3,
    CANCELED: 4,
} as const

export type MissionStateType = typeof MissionState[keyof typeof MissionState]

// Mission State Labels (Chinese)
export const MissionStateLabels: Record<number, string> = {
    [MissionState.PENDING]: '待处理',
    [MissionState.READY]: '就绪',
    [MissionState.DOING]: '进行中',
    [MissionState.DONE]: '已完成',
    [MissionState.CANCELED]: '已取消',
}

// Mission State Colors (for badges)
export const MissionStateColors: Record<number, string> = {
    [MissionState.PENDING]: 'bg-gray-500',
    [MissionState.READY]: 'bg-blue-500',
    [MissionState.DOING]: 'bg-yellow-500',
    [MissionState.DONE]: 'bg-green-500',
    [MissionState.CANCELED]: 'bg-red-500',
}

// Helper function to check if mission is active (not done or canceled)
export const isMissionActive = (state: number | undefined): boolean => {
    return state !== MissionState.DONE && state !== MissionState.CANCELED
}

// Helper function to parse ddl (can be string ISO date or number timestamp in seconds)
export const parseDdl = (ddl: number | string | null | undefined): Date | null => {
    if (!ddl) return null
    if (typeof ddl === 'string') {
        const date = new Date(ddl)
        return isNaN(date.getTime()) ? null : date
    }
    if (typeof ddl === 'number') {
        // If it's a timestamp, check if it's in seconds (less than year 2000 timestamp in ms) or milliseconds
        const date = ddl < 946684800000 ? new Date(ddl * 1000) : new Date(ddl)
        return isNaN(date.getTime()) ? null : date
    }
    return null
}

// Helper function to get ddl as timestamp in seconds
export const getDdlTimestamp = (ddl: number | string | null | undefined): number | null => {
    const date = parseDdl(ddl)
    if (!date) return null
    return Math.floor(date.getTime() / 1000)
}

// Helper function to check if mission is overdue
export const isMissionOverdue = (ddl: number | string | null | undefined, state: number | undefined): boolean => {
    if (!isMissionActive(state)) return false
    const ddlTimestamp = getDdlTimestamp(ddl)
    if (ddlTimestamp === null) return false
    const now = Math.floor(Date.now() / 1000)
    return ddlTimestamp < now
}

// Helper function to get hours until deadline
export const getHoursUntilDeadline = (ddl: number | string | null | undefined): number => {
    const ddlTimestamp = getDdlTimestamp(ddl)
    if (ddlTimestamp === null) return Infinity
    const now = Math.floor(Date.now() / 1000)
    return (ddlTimestamp - now) / 3600
}

