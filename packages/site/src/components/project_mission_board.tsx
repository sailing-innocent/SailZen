import React, { useEffect, useMemo } from 'react'
import type { ProjectData, MissionData } from '@lib/data/project'
import ProjectMissionColumn from './project_mission_column'
import { useIsMobile } from '@/hooks/use-mobile'

export interface ProjectMissionBoardProps {
    projects: ProjectData[]
    missions: MissionData[]
}

const ProjectMissionBoard: React.FC<ProjectMissionBoardProps> = ({ projects, missions }) => {
    const isMobile = useIsMobile()
    
    // NullProject is used to represent a list of missions that are not belong to any project
    const NullProject: ProjectData = {
        id: 0,
        state: 0,
        name: 'Null Project',
        description: 'Null Project Description',
        start_time: 0,
        end_time: 0,
    }

    // sort and group missions by project
    const sortedMissions = useMemo(() => {
        return missions.sort((a, b) => a.id - b.id)
    }, [missions])
    const groupedMissions = useMemo(() => {
        return sortedMissions.reduce((acc, mission) => {
            acc[mission.project_id] = acc[mission.project_id] || []
            acc[mission.project_id].push(mission)
            return acc
        }, {} as Record<number, MissionData[]>)
    }, [sortedMissions])

    return (
        <div className="flex flex-col items-center justify-center">
            <h1 className={`font-bold mb-4 ${isMobile ? 'text-lg' : 'text-2xl'}`}>
                Project Mission Board
            </h1>
            {/* 移动端垂直布局，桌面端横向滚动 */}
            <div className={`flex items-start gap-4 ${
                isMobile 
                    ? 'flex-col w-full' 
                    : 'flex-row overflow-x-auto pb-4'
            }`}>
                <ProjectMissionColumn 
                    key={NullProject.id} 
                    project={NullProject} 
                    missions={groupedMissions[NullProject.id] || []} 
                />
                {projects.map((project) => (
                    <ProjectMissionColumn 
                        key={project.id} 
                        project={project} 
                        missions={groupedMissions[project.id] || []} 
                    />
                ))}
            </div>            
        </div>
    )
}

export default ProjectMissionBoard