import type { ProjectData, MissionData } from '@lib/data/project'
import React from 'react'
import { QBWDate } from '@lib/utils/qbw_date'
import { useIsMobile } from '@/hooks/use-mobile'

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
    const isMobile = useIsMobile()
    const projectDisplayData: ProjectDisplayData = {
        ...project,
        start_time_qbw: QBWDate.from_int(project.start_time),
        end_time_qbw: QBWDate.from_int(project.end_time)
    }
    return (
        <div className={`flex flex-col ${
            isMobile 
                ? 'w-full p-3 border rounded-lg mb-3' 
                : 'items-center justify-center min-w-[250px]'
        }`}>
            <h1 className={`font-bold mb-2 ${isMobile ? 'text-base' : 'text-lg'}`}>
                {projectDisplayData.name}
            </h1>
            <div>
                <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-sm'}`}>
                    {projectDisplayData.description}
                </p>
                <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-sm'}`}>
                    {projectDisplayData.start_time_qbw.get_fmt_string()} - {projectDisplayData.end_time_qbw.get_fmt_string()}
                </p>
            </div>
            <div className={`flex flex-col gap-2 mt-3 ${isMobile ? '' : 'items-center justify-center'}`}>
                {missions.map((mission) => (
                    <div key={mission.id} className={`p-2 bg-muted rounded ${isMobile ? '' : ''}`}>
                        <h3 className={`font-medium ${isMobile ? 'text-sm' : 'text-base'}`}>
                            {mission.name}
                        </h3>
                        <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-sm'}`}>
                            {mission.description}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default ProjectMissionColumn