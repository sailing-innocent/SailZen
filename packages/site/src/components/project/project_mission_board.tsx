import React, { useMemo, useState, useEffect, useCallback } from 'react'
import type { ProjectData, MissionData } from '@lib/data/project'
import { isMissionActive } from '@lib/data/project'
import { isChallengeProject } from '@lib/data/challenge'
import ProjectMissionColumn from './project_mission_column'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
    LayoutGrid,
    LayoutList,
    ChevronDown,
    ChevronUp,
    FolderKanban,
    ListTodo
} from 'lucide-react'
import { cn } from '@lib/utils'
import { type ProjectsState, useProjectsStore, type MissionsState, useMissionsStore } from '@lib/store/project'
import { useServerStore } from '@lib/store'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

interface ProjectWithStats extends ProjectData {
    missionCount: number
    activeCount: number
    hasOverdue: boolean
}

// View mode types
type ViewMode = 'grid' | 'list' | 'focused'

const ProjectMissionBoard: React.FC = () => {
    const projects = useProjectsStore((state: ProjectsState) => state.projects)
    const missions = useMissionsStore((state: MissionsState) => state.missions)
    const fetchProjects = useProjectsStore((state: ProjectsState) => state.fetchProjects)
    const fetchMissions = useMissionsStore((state: MissionsState) => state.fetchMissions)
    
    const isMobile = useIsMobile()
    const [viewMode, setViewMode] = useState<ViewMode>(isMobile ? 'list' : 'grid')
    const [focusedProjectId, setFocusedProjectId] = useState<number | null>(null)
    const [collapsedProjects, setCollapsedProjects] = useState<Set<number>>(new Set())
    const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'overdue'>('all')

    const serverHealth = useServerStore((state) => state.serverHealth)
    
    // Data fetching
    useEffect(() => {
        if (!serverHealth) return
        fetchProjects()
        fetchMissions()
    }, [serverHealth, fetchProjects, fetchMissions])

    // NullProject represents missions not belonging to any project
    const NullProject: ProjectData = {
        id: 0,
        state: 0,
        name: '未分类任务',
        description: '不属于任何项目的任务',
        start_time_qbw: 0,
        end_time_qbw: 0,
    }

    // Filter out Challenge-related projects
    const regularProjects = useMemo(() => {
        return projects.filter(p => !isChallengeProject(p.name))
    }, [projects])

    // Filter out Challenge-related missions
    const regularMissions = useMemo(() => {
        const challengeProjectIds = new Set(
            projects.filter(p => isChallengeProject(p.name)).map(p => p.id)
        )
        return missions.filter(m => !challengeProjectIds.has(m.project_id))
    }, [missions, projects])

    // Group missions by project
    const groupedMissions = useMemo(() => {
        return regularMissions.reduce((acc, mission) => {
            acc[mission.project_id] = acc[mission.project_id] || []
            acc[mission.project_id].push(mission)
            return acc
        }, {} as Record<number, MissionData[]>)
    }, [regularMissions])

    // Calculate project stats
    const projectsWithStats: ProjectWithStats[] = useMemo(() => {
        const allProjects = [
            ...(groupedMissions[NullProject.id]?.length ? [NullProject] : []),
            ...regularProjects
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
    }, [regularProjects, groupedMissions])

    // Filter projects based on status
    const filteredProjects = useMemo(() => {
        if (filterStatus === 'all') return projectsWithStats
        if (filterStatus === 'active') return projectsWithStats.filter(p => p.activeCount > 0)
        if (filterStatus === 'overdue') return projectsWithStats.filter(p => p.hasOverdue)
        return projectsWithStats
    }, [projectsWithStats, filterStatus])

    // Auto-collapse if too many projects in grid mode
    useEffect(() => {
        if (viewMode === 'grid' && filteredProjects.length > 6 && collapsedProjects.size === 0) {
            // Keep first 4 expanded, collapse the rest
            const toCollapse = filteredProjects.slice(4).map(p => p.id)
            setCollapsedProjects(new Set(toCollapse))
        }
    }, [filteredProjects.length, viewMode, collapsedProjects.size])

    // Collapse/Expand handlers
    const collapseAll = () => {
        setCollapsedProjects(new Set(filteredProjects.map(p => p.id)))
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

    // Focused project data
    const focusedProject = useMemo(() => {
        if (!focusedProjectId) return null
        return filteredProjects.find(p => p.id === focusedProjectId) || null
    }, [focusedProjectId, filteredProjects])

    // Get grid columns based on screen size and view mode
    const getGridColumns = () => {
        if (viewMode === 'list') return 'grid-cols-1'
        if (viewMode === 'focused') return 'grid-cols-1'
        // Grid mode - responsive columns
        return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
    }

    // Calculate stats
    const totalStats = useMemo(() => {
        const total = filteredProjects.length
        const withActive = filteredProjects.filter(p => p.activeCount > 0).length
        const withOverdue = filteredProjects.filter(p => p.hasOverdue).length
        return { total, withActive, withOverdue }
    }, [filteredProjects])

    return (
        <Card className="flex flex-col h-full min-h-0 overflow-hidden">
            <CardHeader className={cn(
                "flex flex-col gap-3 shrink-0",
                isMobile ? 'px-3 py-3' : 'pb-4'
            )}>
                {/* Top row: Title and View Mode Toggle */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <CardTitle className={isMobile ? 'text-lg' : 'text-lg'}>
                            项目任务看板
                        </CardTitle>
                        <Badge variant="outline" className="text-xs">
                            {totalStats.withActive}/{totalStats.total}
                        </Badge>
                        {totalStats.withOverdue > 0 && (
                            <Badge variant="destructive" className="text-xs">
                                {totalStats.withOverdue} 逾期
                            </Badge>
                        )}
                    </div>
                    
                    {/* View Mode Toggle */}
                    <div className="flex items-center gap-1">
                        <Button
                            variant={viewMode === 'grid' ? 'default' : 'ghost'}
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => {
                                setViewMode('grid')
                                setFocusedProjectId(null)
                            }}
                            title="网格视图"
                        >
                            <LayoutGrid className="h-4 w-4" />
                        </Button>
                        <Button
                            variant={viewMode === 'list' ? 'default' : 'ghost'}
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => {
                                setViewMode('list')
                                setFocusedProjectId(null)
                            }}
                            title="列表视图"
                        >
                            <LayoutList className="h-4 w-4" />
                        </Button>
                        {focusedProjectId && (
                            <Button
                                variant={viewMode === 'focused' ? 'default' : 'ghost'}
                                size="sm"
                                className="h-8 px-2"
                                onClick={() => setViewMode('focused')}
                                title="专注视图"
                            >
                                <FolderKanban className="h-4 w-4 mr-1" />
                                专注
                            </Button>
                        )}
                    </div>
                </div>

                {/* Bottom row: Filters and Actions */}
                <div className="flex items-center justify-between gap-2">
                    {/* Status Filter */}
                    <Select value={filterStatus} onValueChange={(v: any) => setFilterStatus(v)}>
                        <SelectTrigger className="w-[120px] h-8 text-xs">
                            <SelectValue placeholder="筛选状态" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">
                                <span className="flex items-center gap-2">
                                    <ListTodo className="h-3 w-3" />
                                    全部项目
                                </span>
                            </SelectItem>
                            <SelectItem value="active">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                                    有进行中
                                </span>
                            </SelectItem>
                            <SelectItem value="overdue">
                                <span className="flex items-center gap-2">
                                    <span className="w-2 h-2 rounded-full bg-red-500" />
                                    有逾期
                                </span>
                            </SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Collapse/Expand Buttons */}
                    {viewMode !== 'focused' && (
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 text-xs"
                                onClick={expandAll}
                                disabled={collapsedProjects.size === 0}
                            >
                                <ChevronDown className="h-3 w-3 mr-1" />
                                全部展开
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 text-xs"
                                onClick={collapseAll}
                                disabled={collapsedProjects.size === filteredProjects.length}
                            >
                                <ChevronUp className="h-3 w-3 mr-1" />
                                全部折叠
                            </Button>
                        </div>
                    )}
                </div>

                {/* Focused View Header */}
                {viewMode === 'focused' && focusedProject && (
                    <div className="flex items-center justify-between bg-muted/50 rounded-lg p-2">
                        <div className="flex items-center gap-2">
                            <h3 className="font-medium">{focusedProject.name}</h3>
                            <Badge variant={focusedProject.activeCount > 0 ? "default" : "outline"} className="text-xs">
                                {focusedProject.activeCount}/{focusedProject.missionCount}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    const currentIndex = filteredProjects.findIndex(p => p.id === focusedProjectId)
                                    const prevProject = filteredProjects[currentIndex - 1]
                                    if (prevProject) setFocusedProjectId(prevProject.id)
                                }}
                                disabled={filteredProjects.findIndex(p => p.id === focusedProjectId) === 0}
                            >
                                上一个
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    const currentIndex = filteredProjects.findIndex(p => p.id === focusedProjectId)
                                    const nextProject = filteredProjects[currentIndex + 1]
                                    if (nextProject) setFocusedProjectId(nextProject.id)
                                }}
                                disabled={filteredProjects.findIndex(p => p.id === focusedProjectId) === filteredProjects.length - 1}
                            >
                                下一个
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    setFocusedProjectId(null)
                                    setViewMode('grid')
                                }}
                            >
                                退出专注
                            </Button>
                        </div>
                    </div>
                )}
            </CardHeader>
            
            <CardContent className={cn(
                "flex-1 min-h-0 overflow-auto",
                isMobile ? 'px-2' : 'px-4 pb-4'
            )}>
                {viewMode === 'focused' && focusedProject ? (
                    // Focused View - Single Project
                    <div className="h-full">
                        <ProjectMissionColumn
                            project={focusedProject}
                            missions={groupedMissions[focusedProject.id] || []}
                            defaultCollapsed={false}
                        />
                    </div>
                ) : (
                    // Grid or List View
                    <div className={cn(
                        "grid gap-3",
                        getGridColumns()
                    )}>
                        {filteredProjects.map((project) => (
                            <div 
                                key={project.id}
                                className={cn(
                                    "relative",
                                    viewMode === 'list' && "border rounded-lg hover:border-primary/50 transition-colors"
                                )}
                                onClick={() => {
                                    if (viewMode === 'list') {
                                        setFocusedProjectId(project.id)
                                        setViewMode('focused')
                                    }
                                }}
                            >
                                {viewMode === 'list' && (
                                    <div className="absolute inset-0 cursor-pointer" />
                                )}
                                <ProjectMissionColumn
                                    project={project}
                                    missions={groupedMissions[project.id] || []}
                                    defaultCollapsed={collapsedProjects.has(project.id)}
                                    viewMode={viewMode}
                                    onFocus={() => {
                                        setFocusedProjectId(project.id)
                                        setViewMode('focused')
                                    }}
                                />
                            </div>
                        ))}
                        
                        {filteredProjects.length === 0 && (
                            <div className="col-span-full flex flex-col items-center justify-center py-12 text-muted-foreground">
                                <FolderKanban className="h-12 w-12 mb-4 opacity-30" />
                                <p className="text-sm">暂无项目</p>
                                <p className="text-xs mt-1">点击右上角添加项目</p>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default ProjectMissionBoard
