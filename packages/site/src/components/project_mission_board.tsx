import React, { useMemo } from 'react'
import type { ProjectData, MissionData } from '@lib/data/project'
import ProjectMissionColumn from './project_mission_column'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'

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
        return [...missions].sort((a, b) => a.id - b.id)
    }, [missions])
    const groupedMissions = useMemo(() => {
        return sortedMissions.reduce((acc, mission) => {
            acc[mission.project_id] = acc[mission.project_id] || []
            acc[mission.project_id].push(mission)
            return acc
        }, {} as Record<number, MissionData[]>)
    }, [sortedMissions])

    return (
        <Card className="flex flex-col h-full min-h-0 overflow-hidden">
            <CardHeader className={isMobile ? 'px-3 py-2' : ''}>
                <CardTitle className={isMobile ? 'text-lg' : ''}>
                    Project Mission Board
                </CardTitle>
            </CardHeader>
            <CardContent className={`flex-1 min-h-0 overflow-hidden ${isMobile ? 'px-2' : ''}`}>
                {/* 移动端垂直布局，桌面端横向滚动，内容不超出 Card 边界 */}
                <div
                    className={`flex items-start gap-4 h-full ${
                        isMobile
                            ? 'flex-col overflow-y-auto'
                            : 'flex-row overflow-x-auto overflow-y-hidden pb-2'
                    }`}
                >
                    {(groupedMissions[NullProject.id]?.length || 0) > 0 && (
                        <ProjectMissionColumn
                            key={NullProject.id}
                            project={NullProject}
                            missions={groupedMissions[NullProject.id] || []}
                        />
                    )}
                    {projects.map((project) => (
                        <ProjectMissionColumn
                            key={project.id}
                            project={project}
                            missions={groupedMissions[project.id] || []}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}

export default ProjectMissionBoard