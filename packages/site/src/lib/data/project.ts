export interface ProjectCreateProps {
    name: string,
    description: string,
    start_time: number,
    end_time: number
}

export interface ProjectData extends ProjectCreateProps {
    id: number,
    state: number | undefined
}


export interface MissionCreateProps {
    name: string,
    description: string,
    parent_id: number,
    project_id: number,
    ddl: number
}

export interface MissionData extends MissionCreateProps {
    id: number,
    state: number | undefined
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

// Helper function to check if mission is overdue
export const isMissionOverdue = (ddl: number, state: number | undefined): boolean => {
    if (!isMissionActive(state)) return false
    const now = Date.now() / 1000
    return ddl < now
}

// Helper function to get hours until deadline
export const getHoursUntilDeadline = (ddl: number): number => {
    const now = Date.now() / 1000
    return (ddl - now) / 3600
}

