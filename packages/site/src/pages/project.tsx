import { useEffect, useState, lazy, Suspense } from 'react'
import PageLayout from '@components/page_layout'
import QuarterBiweekCalendar from '@components/quarter_biweek_calendar'
import { type ProjectsState, useProjectsStore } from '@lib/store/project'
import { type MissionsState, useMissionsStore } from '@lib/store/project'
import { useServerStore } from '@lib/store'
import ProjectMissionBoard from '@components/project_mission_board'
import AddProjectDialog from '@components/project_add_dialog'
import AddMissionDialog from '@components/mission_add_dialog'
import { useIsMobile } from '@/hooks/use-mobile'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FolderKanban, Target } from 'lucide-react'

// 动态导入 ChallengeView 以避免循环依赖
const ChallengeView = lazy(() => import('@components/challenge_view'))

const ProjectPage = () => {
    const projects = useProjectsStore((state: ProjectsState) => state.projects)
    const missions = useMissionsStore((state: MissionsState) => state.missions)
    const fetchProjects = useProjectsStore((state: ProjectsState) => state.fetchProjects)
    const fetchMissions = useMissionsStore((state: MissionsState) => state.fetchMissions)
    const isMobile = useIsMobile()
    const [activeTab, setActiveTab] = useState('missions')

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
                    {activeTab === 'missions' ? (
                        <>
                            <AddMissionDialog />
                            <AddProjectDialog />
                        </>
                    ) : null}
                </div>
            </header>

            {/* 标签页切换 */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full max-w-md grid-cols-2 mx-2 md:mx-0">
                    <TabsTrigger value="missions" className="gap-2">
                        <FolderKanban className="h-4 w-4" />
                        任务看板
                    </TabsTrigger>
                    <TabsTrigger value="challenges" className="gap-2">
                        <Target className="h-4 w-4" />
                        打卡挑战
                    </TabsTrigger>
                </TabsList>

                {/* 任务看板标签页 */}
                <TabsContent value="missions" className="mt-4">
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
                </TabsContent>

                {/* 打卡挑战标签页 */}
                <TabsContent value="challenges" className="mt-4 px-2 md:px-0">
                    <Suspense fallback={
                        <div className="flex items-center justify-center h-64">
                            <div className="text-muted-foreground">加载中...</div>
                        </div>
                    }>
                        <ChallengeView />
                    </Suspense>
                </TabsContent>
            </Tabs>
        </PageLayout>
    )
}

export default ProjectPage;
