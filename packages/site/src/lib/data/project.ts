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

