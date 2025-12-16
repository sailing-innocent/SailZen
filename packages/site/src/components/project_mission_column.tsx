import type { ProjectData, MissionData } from '@lib/data/project'
import React from 'react'
import { QBWDate } from '@lib/utils/qbw_date'

export interface ProjectMissionColumnProps {
    project: ProjectData
    missions: MissionData[] // a sorted list of missions belong to this project
}

interface ProjectDisplayData extends ProjectData {
    start_time_qbw: QBWDate,
    end_time_qbw: QBWDate
}

interface MissionDisplayData extends MissionData {
}

const ProjectMissionColumn: React.FC<ProjectMissionColumnProps> = ({ project, missions }) => {
    const projectDisplayData: ProjectDisplayData = {
        ...project,
        start_time_qbw: QBWDate.from_int(project.start_time),
        end_time_qbw: QBWDate.from_int(project.end_time)
    }
    return (
        <div className="flex flex-col items-center justify-center">
            <h1 className="text-2xl font-bold mb-4">Project Mission Column</h1>
            <div>
                <h2 className="text-lg font-bold mb-2">{projectDisplayData.name}</h2>
                <p className="text-sm text-muted-foreground">{projectDisplayData.description}</p>
                <p className="text-sm text-muted-foreground">{projectDisplayData.start_time_qbw.get_fmt_string()} - {projectDisplayData.end_time_qbw.get_fmt_string()}</p>
            </div>
            <div className="flex flex-col items-center justify-center">
                {missions.map((mission) => (
                    <div key={mission.id}>
                        <h2 className="text-lg font-bold mb-2">{mission.name}</h2>
                        <p className="text-sm text-muted-foreground">{mission.description}</p>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default ProjectMissionColumn