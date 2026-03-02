import type { ProjectData, MissionData } from '@lib/data/project'
import { isMissionActive } from '@lib/data/project'
import React, { useState } from 'react'
import { QBWDate } from '@lib/utils/qbw_date'
import { useIsMobile } from '@/hooks/use-mobile'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'
import { CheckCircle2, ChevronLeft, ChevronRight, FolderOpen, Maximize2, MoreHorizontal } from 'lucide-react'
import MissionCard from './mission_card'
import { cn } from '@lib/utils'

export interface ProjectMissionColumnProps {
    project: ProjectData
    missions: MissionData[]
    defaultCollapsed?: boolean
    viewMode?: 'grid' | 'list' | 'focused'
    onFocus?: () => void
}

/**
 * 格式化 QBW 时间范围为可读字符串
 */
function formatQBWRange(startTimeQBW: number, endTimeQBW: number): string {
    const startQBW = QBWDate.from_int(startTimeQBW)
    const endQBW = QBWDate.from_int(endTimeQBW)
    return `${startQBW.get_fmt_string()} - ${endQBW.get_fmt_string()}`
}

const ProjectMissionColumn: React.FC<ProjectMissionColumnProps> = ({
    project,
    missions,
    defaultCollapsed = false,
    viewMode = 'grid',
    onFocus
}) => {
    const isMobile = useIsMobile()
    const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed)

    // Count missions
    const activeMissions = missions.filter((m) => isMissionActive(m.state))
    const completedMissions = missions.filter((m) => !isMissionActive(m.state))
    const hasOverdue = activeMissions.some((m) => {
        const ddl = typeof m.ddl === 'string' ? new Date(m.ddl).getTime() / 1000 : m.ddl
        return ddl && ddl < Date.now() / 1000
    })

    // List mode - Compact horizontal card
    if (viewMode === 'list' && !isMobile) {
        return (
            <div className="flex items-center gap-3 p-3 hover:bg-muted/50 transition-colors">
                {/* Project Icon/Status */}
                <div className="flex-shrink-0">
                    {hasOverdue ? (
                        <div className="w-3 h-3 rounded-full bg-red-500" title="有逾期任务" />
                    ) : activeMissions.length > 0 ? (
                        <div className="w-3 h-3 rounded-full bg-blue-500" title="有进行中任务" />
                    ) : (
                        <div className="w-3 h-3 rounded-full bg-gray-300" title="无活跃任务" />
                    )}
                </div>

                {/* Project Info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <h3 className="font-medium text-sm truncate" title={project.name}>
                            {project.name}
                        </h3>
                        <Badge 
                            variant={activeMissions.length > 0 ? "default" : "outline"} 
                            className="text-[10px] h-4 px-1"
                        >
                            {activeMissions.length}/{missions.length}
                        </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground truncate">
                        {project.description || formatQBWRange(project.start_time_qbw, project.end_time_qbw)}
                    </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={(e) => {
                            e.stopPropagation()
                            onFocus?.()
                        }}
                        title="查看详情"
                    >
                        <Maximize2 className="h-3.5 w-3.5" />
                    </Button>
                </div>
            </div>
        )
    }

    // Collapsed state - Compact card with vertical text (desktop only)
    if (isCollapsed && !isMobile && viewMode === 'grid') {
        return (
            <div 
                className="flex flex-col min-w-[48px] max-w-[48px] border rounded-lg py-3 px-1 h-fit cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => setIsCollapsed(false)}
            >
                <div className="flex flex-col items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={(e) => {
                            e.stopPropagation()
                            setIsCollapsed(false)
                        }}
                        title="展开项目"
                    >
                        <ChevronRight className="h-4 w-4" />
                    </Button>

                    {/* Vertical Project Name */}
                    <div className="flex-1" title={project.name}>
                        <span 
                            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
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

    // Focused View - Full width with more details
    if (viewMode === 'focused') {
        return (
            <div className="flex flex-col h-full border rounded-lg p-4 bg-card">
                {/* Project Header */}
                <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <h2 className="text-xl font-bold truncate" title={project.name}>
                                {project.name}
                            </h2>
                            {hasOverdue && (
                                <Badge variant="destructive" className="text-xs shrink-0">
                                    有逾期
                                </Badge>
                            )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                            {project.description || '无描述'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            {formatQBWRange(project.start_time_qbw, project.end_time_qbw)}
                        </p>
                    </div>
                    <Badge 
                        variant={activeMissions.length > 0 ? "default" : "outline"} 
                        className="text-sm px-3 py-1 shrink-0"
                    >
                        {activeMissions.length} 进行中 / {missions.length} 总计
                    </Badge>
                </div>

                {/* Mission List - Scrollable */}
                <div className="flex-1 overflow-y-auto space-y-2 min-h-0 pr-1">
                    {missions.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <FolderOpen className="h-12 w-12 mb-3 opacity-50" />
                            <p className="text-sm">暂无任务</p>
                            <p className="text-xs mt-1">点击右上角添加任务</p>
                        </div>
                    ) : (
                        <>
                            {/* Active missions */}
                            <div className="space-y-2">
                                {activeMissions.map((mission) => (
                                    <MissionCard
                                        key={mission.id}
                                        mission={mission}
                                        project={project}
                                        compact={false}
                                    />
                                ))}
                            </div>

                            {/* Completed missions (collapsed) */}
                            {completedMissions.length > 0 && (
                                <Accordion type="single" collapsible className="mt-4">
                                    <AccordionItem value="completed" className="border-none">
                                        <AccordionTrigger className="py-2 text-sm text-muted-foreground hover:text-foreground hover:no-underline">
                                            <span className="flex items-center gap-2">
                                                <CheckCircle2 className="h-4 w-4" />
                                                已完成 ({completedMissions.length})
                                            </span>
                                        </AccordionTrigger>
                                        <AccordionContent className="pb-0">
                                            <div className="space-y-2 opacity-70">
                                                {completedMissions.map((mission) => (
                                                    <MissionCard
                                                        key={mission.id}
                                                        mission={mission}
                                                        project={project}
                                                        compact={false}
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

    // Standard Grid View
    return (
        <div className={cn(
            "flex flex-col",
            isMobile 
                ? 'w-full p-3 border rounded-lg mb-3' 
                : 'border rounded-lg p-3 h-fit'
        )}>
            {/* Project Header */}
            <div className="mb-3">
                <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1">
                            {!isMobile && viewMode === 'grid' && (
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
                                className="font-bold truncate text-base"
                                title={project.name}
                            >
                                {project.name}
                            </h2>
                        </div>
                        <p className="text-muted-foreground truncate text-xs mt-0.5">
                            {project.description}
                        </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                        {hasOverdue && (
                            <div className="w-2 h-2 rounded-full bg-red-500" title="有逾期任务" />
                        )}
                        <Badge 
                            variant={activeMissions.length > 0 ? "default" : "outline"} 
                            className="text-xs"
                        >
                            {activeMissions.length}/{missions.length}
                        </Badge>
                        {!isMobile && onFocus && (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 ml-1"
                                onClick={onFocus}
                                title="专注视图"
                            >
                                <Maximize2 className="h-3 w-3" />
                            </Button>
                        )}
                    </div>
                </div>
                <p className="text-muted-foreground text-xs mt-1">
                    {formatQBWRange(project.start_time_qbw, project.end_time_qbw)}
                </p>
            </div>

            {/* Mission List */}
            <div className="flex flex-col gap-2 max-h-[calc(100vh-300px)] overflow-y-auto">
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
