import { useEffect } from 'react'
import PageLayout from '@components/page_layout'
import QuarterBiweekCalendar from '@components/quarter_biweek_calendar'
import { type ProjectsState, useProjectsStore } from '@lib/store/project'
import { type MissionsState, useMissionsStore } from '@lib/store/project'
import { useServerStore } from '@lib/store'
import ProjectMissionBoard from '@components/project_mission_board'
import AddProjectDialog from '@components/project_add_dialog'
import AddMissionDialog from '@components/mission_add_dialog'
import { useIsMobile } from '@/hooks/use-mobile'

const ProjectPage = () => {
    const projects = useProjectsStore((state: ProjectsState) => state.projects)
    const missions = useMissionsStore((state: MissionsState) => state.missions)
    const fetchProjects = useProjectsStore((state: ProjectsState) => state.fetchProjects)
    const fetchMissions = useMissionsStore((state: MissionsState) => state.fetchMissions)
    const isMobile = useIsMobile()

    const serverHealth = useServerStore((state) => state.serverHealth)
    useEffect(() => {
        if (!serverHealth) {
            return
        }
        fetchProjects()
        fetchMissions()
    }, [fetchProjects, fetchMissions, serverHealth])

    return (
        <PageLayout>
            {/* 页面头部：标题与操作按钮 */}
            <header className="flex items-center justify-between px-2 md:px-0 shrink-0">
                <h1 className="text-xl md:text-2xl font-bold">项目管理</h1>
                <div className="flex gap-2 shrink-0">
                    <AddMissionDialog />
                    <AddProjectDialog />
                </div>
            </header>

            {/* 主内容区：MissionBoard 与 Calendar 并排，互不重叠 */}
            <main
                className={`flex w-full gap-4 md:gap-6 min-w-0 ${
                    isMobile ? 'flex-col' : 'flex-row'
                }`}
            >
                {/* 任务看板区域：桌面端占 3/5，移动端全宽 */}
                <section
                    className={`flex flex-col min-w-0 ${
                        isMobile ? 'w-full' : 'flex-1 basis-0'
                    }`}
                >
                    <ProjectMissionBoard projects={projects} missions={missions} />
                </section>

                {/* 日历区域：桌面端占 2/5，移动端全宽 */}
                <section
                    className={`flex flex-col min-w-0 ${
                        isMobile ? 'w-full' : 'shrink-0 basis-[40%] max-w-[420px]'
                    }`}
                >
                    <QuarterBiweekCalendar />
                </section>
            </main>
        </PageLayout>
    )
}

export default ProjectPage;