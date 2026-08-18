import React, { useMemo, useState, useEffect } from 'react'
import type { AffairData } from '@lib/data/affair'
import { AffairState, isAffairActive, getDdlTimestamp, isAffairOverdue } from '@lib/data/affair'
import { isChallengeAffair } from '@lib/data/challenge'
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
import { type AffairsState, useAffairsStore } from '@lib/store/affair'
import { useServerStore } from '@lib/store'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

interface VentureWithStats extends AffairData {
    taskCount: number
    activeCount: number
    hasOverdue: boolean
}

// View mode types
type ViewMode = 'grid' | 'list' | 'focused'

const ProjectMissionBoard: React.FC = () => {
    const ventures = useAffairsStore((state: AffairsState) => state.ventures)
    const tasks = useAffairsStore((state: AffairsState) => state.tasks)
    const fetchVentures = useAffairsStore((state: AffairsState) => state.fetchVentures)
    const fetchTasks = useAffairsStore((state: AffairsState) => state.fetchTasks)
    
    const isMobile = useIsMobile()
    const [viewMode, setViewMode] = useState<ViewMode>(isMobile ? 'list' : 'grid')
    const [focusedVentureId, setFocusedVentureId] = useState<number | null>(null)
    const [collapsedProjects, setCollapsedProjects] = useState<Set<number>>(new Set())
    const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'overdue'>('all')

    const serverHealth = useServerStore((state) => state.serverHealth)
    
    // Data fetching
    useEffect(() => {
        if (!serverHealth) return
        fetchVentures()
        fetchTasks()
    }, [serverHealth, fetchVentures, fetchTasks])

    // NullVenture represents tasks not belonging to any venture
    const NullVenture: AffairData = {
        id: 0,
        title: '未分类任务',
        description: '不属于任何事业的任务',
        kind: 'venture',
        domain: 'career',
        state: AffairState.INBOX,
        kind_meta: {},
        importance: 3,
        urgency_ddl: null,
        energy_cost: 0,
        money_cost: 0,
        budget_id: null,
        est_minutes: 0,
        splittable: false,
        min_chunk_minutes: 30,
        fallback_plan: '',
        recurrence_rule_id: null,
        mission_id: null,
        day_id: null,
        timespan_id: null,
        parent_id: null,
        info_collection_type: null,
        ai_hint: {},
        score: 0,
        ref: {},
    }

    // Filter out Challenge-related ventures
    const regularVentures = useMemo(() => {
        return ventures.filter(v => !isChallengeAffair(v.title))
    }, [ventures])

    // Filter out Challenge-related tasks
    const regularTasks = useMemo(() => {
        const challengeVentureIds = new Set(
            ventures.filter(v => isChallengeAffair(v.title)).map(v => v.id)
        )
        return tasks.filter(t => t.parent_id === null || !challengeVentureIds.has(t.parent_id))
    }, [tasks, ventures])

    // Group tasks by parent venture (parent_id === null → unclassified)
    const groupedTasks = useMemo(() => {
        return regularTasks.reduce((acc, task) => {
            const parentId = task.parent_id ?? NullVenture.id
            acc[parentId] = acc[parentId] || []
            acc[parentId].push(task)
            return acc
        }, {} as Record<number, AffairData[]>)
    }, [regularTasks])

    // Calculate venture stats
    const venturesWithStats: VentureWithStats[] = useMemo(() => {
        const allVentures = [
            ...(groupedTasks[NullVenture.id]?.length ? [NullVenture] : []),
            ...regularVentures
        ]
        return allVentures.map(v => {
            const ventureTasks = groupedTasks[v.id] || []
            const activeTasks = ventureTasks.filter(t => isAffairActive(t.state))
            const hasOverdue = activeTasks.some(t => isAffairOverdue(t.urgency_ddl, t.state))
            return {
                ...v,
                taskCount: ventureTasks.length,
                activeCount: activeTasks.length,
                hasOverdue
            }
        })
    }, [regularVentures, groupedTasks])

    // Filter ventures based on status
    const filteredVentures = useMemo(() => {
        if (filterStatus === 'all') return venturesWithStats
        if (filterStatus === 'active') return venturesWithStats.filter(v => v.activeCount > 0)
        if (filterStatus === 'overdue') return venturesWithStats.filter(v => v.hasOverdue)
        return venturesWithStats
    }, [venturesWithStats, filterStatus])

    // Auto-collapse if too many ventures in grid mode
    useEffect(() => {
        if (viewMode === 'grid' && filteredVentures.length > 6 && collapsedProjects.size === 0) {
            // Keep first 4 expanded, collapse the rest
            const toCollapse = filteredVentures.slice(4).map(v => v.id)
            setCollapsedProjects(new Set(toCollapse))
        }
    }, [filteredVentures.length, viewMode, collapsedProjects.size])

    // Collapse/Expand handlers
    const collapseAll = () => {
        setCollapsedProjects(new Set(filteredVentures.map(v => v.id)))
    }

    const expandAll = () => {
        setCollapsedProjects(new Set())
    }

    const toggleVenture = (ventureId: number) => {
        const newCollapsed = new Set(collapsedProjects)
        if (newCollapsed.has(ventureId)) {
            newCollapsed.delete(ventureId)
        } else {
            newCollapsed.add(ventureId)
        }
        setCollapsedProjects(newCollapsed)
    }

    // Focused venture data
    const focusedVenture = useMemo(() => {
        if (!focusedVentureId) return null
        return filteredVentures.find(v => v.id === focusedVentureId) || null
    }, [focusedVentureId, filteredVentures])

    // Get grid columns based on screen size and view mode
    const getGridColumns = () => {
        if (viewMode === 'list') return 'grid-cols-1'
        if (viewMode === 'focused') return 'grid-cols-1'
        // Grid mode - responsive columns
        return 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
    }

    // Calculate stats
    const totalStats = useMemo(() => {
        const total = filteredVentures.length
        const withActive = filteredVentures.filter(v => v.activeCount > 0).length
        const withOverdue = filteredVentures.filter(v => v.hasOverdue).length
        return { total, withActive, withOverdue }
    }, [filteredVentures])

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
                            事业任务看板
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
                        {focusedVentureId && (
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
                                    全部事业
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
                                disabled={collapsedProjects.size === filteredVentures.length}
                            >
                                <ChevronUp className="h-3 w-3 mr-1" />
                                全部折叠
                            </Button>
                        </div>
                    )}
                </div>

                {/* Focused View Header */}
                {viewMode === 'focused' && focusedVenture && (
                    <div className="flex items-center justify-between bg-muted/50 rounded-lg p-2">
                        <div className="flex items-center gap-2">
                            <h3 className="font-medium">{focusedVenture.title}</h3>
                            <Badge variant={focusedVenture.activeCount > 0 ? "default" : "outline"} className="text-xs">
                                {focusedVenture.activeCount}/{focusedVenture.taskCount}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-1">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    const currentIndex = filteredVentures.findIndex(v => v.id === focusedVentureId)
                                    const prevVenture = filteredVentures[currentIndex - 1]
                                    if (prevVenture) setFocusedVentureId(prevVenture.id)
                                }}
                                disabled={filteredVentures.findIndex(v => v.id === focusedVentureId) === 0}
                            >
                                上一个
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    const currentIndex = filteredVentures.findIndex(v => v.id === focusedVentureId)
                                    const nextVenture = filteredVentures[currentIndex + 1]
                                    if (nextVenture) setFocusedVentureId(nextVenture.id)
                                }}
                                disabled={filteredVentures.findIndex(v => v.id === focusedVentureId) === filteredVentures.length - 1}
                            >
                                下一个
                            </Button>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 text-xs"
                                onClick={() => {
                                    setFocusedVentureId(null)
                                    setViewMode('grid')
                                }}
                            >
                                返回
                            </Button>
                        </div>
                    </div>
                )}
            </CardHeader>
            
            <CardContent className={cn(
                "flex-1 min-h-0 overflow-auto",
                isMobile ? 'px-2' : 'px-4 pb-4'
            )}>
                {viewMode === 'focused' && focusedVenture ? (
                    // Focused View - Single Venture
                    <div className="h-full">
                        <ProjectMissionColumn
                            project={focusedVenture}
                            missions={groupedTasks[focusedVenture.id] || []}
                            defaultCollapsed={false}
                        />
                    </div>
                ) : (
                    // Grid or List View
                    <div className={cn(
                        "grid gap-3",
                        getGridColumns()
                    )}>
                        {filteredVentures.map((venture) => (
                            <div
                                key={venture.id}
                                className={cn(
                                    "relative",
                                    viewMode === 'list' && "border rounded-lg hover:border-primary/50 transition-colors"
                                )}
                                onClick={() => {
                                    if (viewMode === 'list') {
                                        setFocusedVentureId(venture.id)
                                        setViewMode('focused')
                                    }
                                }}
                            >
                                {viewMode === 'list' && (
                                    <div className="absolute inset-0 cursor-pointer" />
                                )}
                                <ProjectMissionColumn
                                    project={venture}
                                    missions={groupedTasks[venture.id] || []}
                                    defaultCollapsed={collapsedProjects.has(venture.id)}
                                    viewMode={viewMode}
                                    onFocus={() => {
                                        setFocusedVentureId(venture.id)
                                        setViewMode('focused')
                                    }}
                                />
                            </div>
                        ))}

                        {filteredVentures.length === 0 && (
                            <div className="col-span-full flex flex-col items-center justify-center py-12 text-muted-foreground">
                                <FolderKanban className="h-12 w-12 mb-4 opacity-30" />
                                <p className="text-sm">暂无事业</p>
                                <p className="text-xs mt-1">点击右上角添加事业</p>
                            </div>
                        )}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default ProjectMissionBoard
