import type { ProjectData, MissionData } from '@lib/data/project'
import { isMissionActive } from '@lib/data/project'
import React, { useState } from 'react'
import { QBWDate } from '@lib/utils/qbw_date'
import { useIsMobile } from '@/hooks/use-mobile'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'
import { CheckCircle2, ChevronLeft, ChevronRight, FolderOpen } from 'lucide-react'
import MissionCard from './mission_card'

export interface ProjectMissionColumnProps {
    project: ProjectData
    missions: MissionData[] // a sorted list of missions belong to this project
    defaultCollapsed?: boolean
}

/**
 * 格式化 QBW 时间范围为可读字符串
 */
function formatQBWRange(startTimeQBW: number, endTimeQBW: number): string {
    // 使用 QBWDate 解析
    const startQBW = QBWDate.from_int(startTimeQBW)
    const endQBW = QBWDate.from_int(endTimeQBW)
    
    return `${startQBW.get_fmt_string()} - ${endQBW.get_fmt_string()}`
}

const ProjectMissionColumn: React.FC<ProjectMissionColumnProps> = ({
    project,
    missions,
    defaultCollapsed = false
}) => {

    const isMobile = useIsMobile()
    const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed)

    // Count active missions
    const activeMissions = missions.filter((m) => isMissionActive(m.state))
    const completedMissions = missions.filter((m) => !isMissionActive(m.state))
    const hasOverdue = activeMissions.some((m) => {
        const ddl = typeof m.ddl === 'string' ? new Date(m.ddl).getTime() / 1000 : m.ddl
        return ddl && ddl < Date.now() / 1000
    })

    // Collapsed state - compact vertical card
    if (isCollapsed && !isMobile) {
        return (
            <div className="flex flex-col min-w-[48px] max-w-[48px] border rounded-lg py-3 px-1 h-fit">
                {/* Collapsed Header - Vertical text */}
                <div className="flex flex-col items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={() => setIsCollapsed(false)}
                        title="展开项目"
                    >
                        <ChevronRight className="h-4 w-4" />
                    </Button>

                    {/* Vertical Project Name */}
                    <div 
                        className="flex-1 cursor-pointer"
                        onClick={() => setIsCollapsed(false)}
                        title={project.name}
                    >
                        <span 
                            className="writing-mode-vertical text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                            style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
                        >
                            {project.name}
                        </span>
                    </div>

                    {/* Badge at bottom */}
                    <div className="flex flex-col items-center gap-1">
                        {hasOverdue && (
                            <div className="w-2 h-2 rounded-full bg-red-500" title="有逾期任务" />
                        )}
                        <Badge 
                            variant={activeMissions.length > 0 ? "default" : "outline"} 
                            className="text-[10px] px-1 py-0 h-4 min-w-[20px] justify-center"
                        >
                            {activeMissions.length}
                        </Badge>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className={`flex flex-col ${
            isMobile 
                ? 'w-full p-3 border rounded-lg mb-3' 
                : 'min-w-[280px] max-w-[320px] border rounded-lg p-3'
        }`}>
            {/* Project Header */}
            <div className="mb-3">
                <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            {!isMobile && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 shrink-0 -ml-1"
                                    onClick={() => setIsCollapsed(true)}
                                    title="折叠项目"
                                >
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                            )}
                            <h2 
                                className={`font-bold truncate ${isMobile ? 'text-base' : 'text-base'}`}
                                title={project.name}
                            >
                                {project.name}
                            </h2>
                        </div>
                        <p className={`text-muted-foreground truncate ${isMobile ? 'text-xs' : 'text-xs'} mt-0.5`}>
                            {project.description}
                        </p>
                    </div>
                    <Badge 
                        variant={activeMissions.length > 0 ? "default" : "outline"} 
                        className="text-xs shrink-0"
                    >
                        {activeMissions.length}/{missions.length}
                    </Badge>
                </div>
                <p className={`text-muted-foreground ${isMobile ? 'text-xs' : 'text-xs'} mt-1`}>
                    {formatQBWRange(project.start_time_qbw, project.end_time_qbw)}
                </p>
            </div>

            {/* Mission List */}
            <div className="flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-280px)]">
                {missions.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-6 text-muted-foreground">
                        <FolderOpen className="h-8 w-8 mb-2 opacity-50" />
                        <p className="text-sm">暂无任务</p>
                    </div>
                ) : (
                    <>
                        {/* Active missions first */}
                        {activeMissions.map((mission) => (
                            <MissionCard
                                key={mission.id}
                                mission={mission}
                                project={project}
                                compact
                            />
                        ))}

                        {/* Completed missions (collapsed) */}
                        {completedMissions.length > 0 && (
                            <Accordion type="single" collapsible className="mt-2">
                                <AccordionItem value="completed" className="border-none">
                                    <AccordionTrigger className="py-2 text-xs text-muted-foreground hover:text-foreground hover:no-underline">
                                        <span className="flex items-center gap-1">
                                            <CheckCircle2 className="h-3 w-3" />
                                            已完成 ({completedMissions.length})
                                        </span>
                                    </AccordionTrigger>
                                    <AccordionContent className="pb-0">
                                        <div className="space-y-2">
                                            {completedMissions.map((mission) => (
                                                <MissionCard
                                                    key={mission.id}
                                                    mission={mission}
                                                    project={project}
                                                    compact
                                                />
                                            ))}
                                        </div>
                                    </AccordionContent>
                                </AccordionItem>
                            </Accordion>
                        )}
                    </>
                )}
            </div>
        </div>
    )
}

export default ProjectMissionColumn
