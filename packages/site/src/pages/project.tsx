import PageLayout from '@components/page_layout'
import ProjectMissionBoard from '@components/project_mission_board'
import AddProjectDialog from '@components/project_add_dialog'
import AddMissionDialog from '@components/mission_add_dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FolderKanban, Target } from 'lucide-react'
import { useState } from 'react'

// 动态导入 ChallengeView 以避免循环依赖
import ChallengeView from '@components/challenge_view'

const ProjectPage = () => {
    const [activeTab, setActiveTab] = useState('missions')

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
                    <ProjectMissionBoard />
                </TabsContent>

                {/* 打卡挑战标签页 */}
                <TabsContent value="challenges" className="mt-4 px-2 md:px-0">
                    <ChallengeView />
                </TabsContent>
            </Tabs>
        </PageLayout>
    )
}

export default ProjectPage
