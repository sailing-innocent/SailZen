import React, { useMemo, useState, useRef, useEffect } from 'react'
import type { ProjectData, MissionData } from '@lib/data/project'
import { isMissionActive } from '@lib/data/project'
import ProjectMissionColumn from './project_mission_column'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
    ChevronLeft, 
    ChevronRight, 
    PanelLeftClose, 
    PanelLeftOpen,
    LayoutGrid,
    ChevronFirst,
    ChevronLast
} from 'lucide-react'
import { cn } from '@lib/utils'

export interface ProjectMissionBoardProps {
    projects: ProjectData[]
    missions: MissionData[]
}

interface ProjectWithStats extends ProjectData {
    missionCount: number
    activeCount: number
    hasOverdue: boolean
}

const ProjectMissionBoard: React.FC<ProjectMissionBoardProps> = ({ projects, missions }) => {
    const isMobile = useIsMobile()
    const scrollContainerRef = useRef<HTMLDivElement>(null)
    const [showProjectNav, setShowProjectNav] = useState(false)
    const [canScrollLeft, setCanScrollLeft] = useState(false)
    const [canScrollRight, setCanScrollRight] = useState(false)
    const [collapsedProjects, setCollapsedProjects] = useState<Set<number>>(new Set())

    // NullProject is used to represent a list of missions that are not belong to any project
    const NullProject: ProjectData = {
        id: 0,
        state: 0,
        name: '未分类任务',
        description: '不属于任何项目的任务',
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

    // Calculate project stats
    const projectsWithStats: ProjectWithStats[] = useMemo(() => {
        const allProjects = [
            ...(groupedMissions[NullProject.id]?.length ? [NullProject] : []),
            ...projects
        ]
        return allProjects.map(p => {
            const projectMissions = groupedMissions[p.id] || []
            const activeMissions = projectMissions.filter(m => isMissionActive(m.state))
            const hasOverdue = activeMissions.some(m => {
                const ddl = typeof m.ddl === 'string' ? new Date(m.ddl).getTime() / 1000 : m.ddl
                return ddl && ddl < Date.now() / 1000
            })
            return {
                ...p,
                missionCount: projectMissions.length,
                activeCount: activeMissions.length,
                hasOverdue
            }
        })
    }, [projects, groupedMissions])

    // Check scroll position
    const checkScroll = () => {
        const container = scrollContainerRef.current
        if (!container) return
        setCanScrollLeft(container.scrollLeft > 0)
        setCanScrollRight(
            container.scrollLeft < container.scrollWidth - container.clientWidth - 10
        )
    }

    useEffect(() => {
        checkScroll()
        const container = scrollContainerRef.current
        if (container) {
            container.addEventListener('scroll', checkScroll)
            return () => container.removeEventListener('scroll', checkScroll)
        }
    }, [projects, missions, collapsedProjects])

    // Scroll handlers
    const scroll = (direction: 'left' | 'right' | 'start' | 'end') => {
        const container = scrollContainerRef.current
        if (!container) return
        const scrollAmount = 320
        if (direction === 'left') {
            container.scrollBy({ left: -scrollAmount, behavior: 'smooth' })
        } else if (direction === 'right') {
            container.scrollBy({ left: scrollAmount, behavior: 'smooth' })
        } else if (direction === 'start') {
            container.scrollTo({ left: 0, behavior: 'smooth' })
        } else {
            container.scrollTo({ left: container.scrollWidth, behavior: 'smooth' })
        }
    }

    // Collapse/Expand all
    const collapseAll = () => {
        setCollapsedProjects(new Set(projectsWithStats.map(p => p.id)))
    }

    const expandAll = () => {
        setCollapsedProjects(new Set())
    }

    const toggleProject = (projectId: number) => {
        const newCollapsed = new Set(collapsedProjects)
        if (newCollapsed.has(projectId)) {
            newCollapsed.delete(projectId)
        } else {
            newCollapsed.add(projectId)
        }
        setCollapsedProjects(newCollapsed)
    }

    // Auto-collapse if too many projects (more than 4)
    useEffect(() => {
        if (projectsWithStats.length > 4 && collapsedProjects.size === 0) {
            // Keep first 3 expanded, collapse the rest
            const toCollapse = projectsWithStats.slice(3).map(p => p.id)
            setCollapsedProjects(new Set(toCollapse))
        }
    }, [projectsWithStats.length])

    return (
        <Card className="flex flex-col h-full min-h-0 overflow-hidden">
            <CardHeader className={cn("flex flex-row items-center justify-between", isMobile ? 'px-3 py-2' : 'pb-2')}>
                <div className="flex items-center gap-2">
                    <CardTitle className={isMobile ? 'text-lg' : 'text-lg'}>
                        项目任务看板
                    </CardTitle>
                    <Badge variant="outline" className="text-xs">
                        {projectsWithStats.length} 项目
                    </Badge>
                </div>
                
                {!isMobile && (
                    <div className="flex items-center gap-1">
                        {/* Project Nav Toggle */}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 gap-1"
                            onClick={() => setShowProjectNav(!showProjectNav)}
                        >
                            {showProjectNav ? (
                                <><PanelLeftClose className="h-4 w-4" /> 隐藏导航</>
                            ) : (
                                <><PanelLeftOpen className="h-4 w-4" /> 项目导航</>
                            )}
                        </Button>
                        
                        {/* Collapse/Expand */}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="h-8"
                            onClick={collapsedProjects.size > 0 ? expandAll : collapseAll}
                        >
                            <LayoutGrid className="h-4 w-4 mr-1" />
                            {collapsedProjects.size > 0 ? '全部展开' : '全部折叠'}
                        </Button>
                    </div>
                )}
            </CardHeader>
            
            <CardContent className={`flex-1 min-h-0 overflow-hidden ${isMobile ? 'px-2' : 'px-3 pb-3'}`}>
                <div className="flex h-full gap-3">
                    {/* Project Navigation Sidebar */}
                    {!isMobile && showProjectNav && (
                        <div className="w-48 flex-shrink-0 border rounded-lg p-2 overflow-y-auto">
                            <h3 className="text-xs font-medium text-muted-foreground mb-2 px-2">
                                项目列表
                            </h3>
                            <div className="space-y-1">
                                {projectsWithStats.map((project) => (
                                    <button
                                        key={project.id}
                                        onClick={() => toggleProject(project.id)}
                                        className={cn(
                                            "w-full text-left px-2 py-1.5 rounded text-sm transition-colors flex items-center justify-between group",
                                            collapsedProjects.has(project.id) 
                                                ? "hover:bg-muted" 
                                                : "bg-muted/50 hover:bg-muted"
                                        )}
                                    >
                                        <span className="truncate flex-1">{project.name}</span>
                                        <div className="flex items-center gap-1">
                                            {project.hasOverdue && (
                                                <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                                            )}
                                            <Badge 
                                                variant={project.activeCount > 0 ? "default" : "outline"}
                                                className="text-[10px] h-4 px-1"
                                            >
                                                {project.activeCount}
                                            </Badge>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                    
                    {/* Main Content */}
                    <div className="flex-1 min-w-0 relative">
                        {/* Scroll Controls */}
                        {!isMobile && (
                            <>
                                {/* Left scroll button */}
                                {canScrollLeft && (
                                    <Button
                                        variant="secondary"
                                        size="icon"
                                        className="absolute left-0 top-1/2 -translate-y-1/2 z-10 h-8 w-8 rounded-full shadow-md"
                                        onClick={() => scroll('left')}
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                    </Button>
                                )}
                                
                                {/* Right scroll button */}
                                {canScrollRight && (
                                    <Button
                                        variant="secondary"
                                        size="icon"
                                        className="absolute right-0 top-1/2 -translate-y-1/2 z-10 h-8 w-8 rounded-full shadow-md"
                                        onClick={() => scroll('right')}
                                    >
                                        <ChevronRight className="h-4 w-4" />
                                    </Button>
                                )}
                                
                                {/* Jump to start/end */}
                                <div className="absolute bottom-2 right-2 flex gap-1 z-10">
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7"
                                        onClick={() => scroll('start')}
                                        disabled={!canScrollLeft}
                                    >
                                        <ChevronFirst className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="h-7 w-7"
                                        onClick={() => scroll('end')}
                                        disabled={!canScrollRight}
                                    >
                                        <ChevronLast className="h-4 w-4" />
                                    </Button>
                                </div>
                            </>
                        )}
                        
                        {/* Mission Columns */}
                        <div
                            ref={scrollContainerRef}
                            className={cn(
                                "flex items-start gap-3 h-full",
                                isMobile
                                    ? "flex-col overflow-y-auto"
                                    : "flex-row overflow-x-auto overflow-y-hidden pb-2 px-1"
                            )}
                        >
                            {projectsWithStats.map((project) => (
                                <ProjectMissionColumn
                                    key={project.id}
                                    project={project}
                                    missions={groupedMissions[project.id] || []}
                                    defaultCollapsed={collapsedProjects.has(project.id)}
                                />
                            ))}
                            
                            {projectsWithStats.length === 0 && (
                                <div className="flex-1 flex items-center justify-center text-muted-foreground">
                                    暂无项目
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

export default ProjectMissionBoard
