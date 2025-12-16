import { useEffect } from 'react'
import PageLayout from '@components/page_layout'
import QuarterBiweekCalendar from '@components/quarter_biweek_calendar'
import { type ProjectsState, useProjectsStore } from '@lib/store/project'
import { type MissionsState, useMissionsStore } from '@lib/store/project'
import { useServerStore } from '@lib/store'
import ProjectMissionBoard from '@components/project_mission_board'
import AddProjectDialog from '@components/project_add_dialog'
import AddMissionDialog from '@components/mission_add_dialog'

const ProjectPage = () => {
    const projects = useProjectsStore((state: ProjectsState) => state.projects)
    const missions = useMissionsStore((state: MissionsState) => state.missions)
    const fetchProjects = useProjectsStore((state: ProjectsState) => state.fetchProjects)
    const fetchMissions = useMissionsStore((state: MissionsState) => state.fetchMissions)
    

    const serverHealth = useServerStore((state) => state.serverHealth)
    useEffect(() => {
        if (!serverHealth) {
            return 
        }
        fetchProjects()
        fetchMissions()
    }, [fetchProjects, fetchMissions, serverHealth])

    return (
        <>
            <PageLayout>
                <div className="flex items-center justify-between px-2 md:px-0">
                    <div className="text-xl md:text-2xl font-bold">项目管理</div>
                    <div className="flex gap-2">
                        <AddMissionDialog />
                        <AddProjectDialog />
                    </div>
                </div>
                <div className="grid grid-cols-5 gap-6">
                    <div className="col-span-3">
                        <ProjectMissionBoard projects={projects} missions={missions} />
                    </div>
                    <div className="col-span-2">
                        <QuarterBiweekCalendar />
                    </div>
                </div>
            </PageLayout>
        </>
    )
}

export default ProjectPage;