import React, { useEffect, useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import {
  RefreshCw,
  Plus,
  CheckCircle2,
  AlertCircle,
  Clock,
  AlertTriangle,
} from 'lucide-react'
import MissionCard from './mission_card'
import AddMissionDialog from './mission_add_dialog'
import { useMissionsStore, type MissionsState, useProjectsStore, type ProjectsState } from '@lib/store/project'
import { useServerStore } from '@lib/store'
import { isChallengeProject } from '@lib/data/challenge'
import {
  type MissionData,
  MissionState,
  isMissionActive,
  isMissionOverdue,
  parseDdl,
  getHoursUntilDeadline,
  getDdlTimestamp,
} from '@lib/data/project'
import { useIsMobile } from '@/hooks/use-mobile'

export interface ReminderTodoListProps {
  title?: string
  showFilters?: boolean
  maxItems?: number
}

const ReminderTodoList: React.FC<ReminderTodoListProps> = ({
  title = '待办任务',
  showFilters = true,
  maxItems,
}) => {
  const isMobile = useIsMobile()
  const serverHealth = useServerStore((state) => state.serverHealth)

  const missions = useMissionsStore((state: MissionsState) => state.missions)
  const upcomingMissions = useMissionsStore((state: MissionsState) => state.upcomingMissions)
  const overdueMissions = useMissionsStore((state: MissionsState) => state.overdueMissions)
  const isMissionsLoading = useMissionsStore((state: MissionsState) => state.isLoading)
  const fetchMissions = useMissionsStore((state: MissionsState) => state.fetchMissions)
  const fetchUpcomingMissions = useMissionsStore((state: MissionsState) => state.fetchUpcomingMissions)
  const fetchOverdueMissions = useMissionsStore((state: MissionsState) => state.fetchOverdueMissions)
  
  // Get projects to filter out Challenge-related missions
  const projects = useProjectsStore((state: ProjectsState) => state.projects)
  const isProjectsLoading = useProjectsStore((state: ProjectsState) => state.isLoading)
  const fetchProjects = useProjectsStore((state: ProjectsState) => state.fetchProjects)
  
  // Filter out Challenge-related missions
  const regularMissions = useMemo(() => {
    const challengeProjectIds = new Set(
      projects.filter(p => isChallengeProject(p.name)).map(p => p.id)
    )
    return missions.filter(m => !challengeProjectIds.has(m.project_id))
  }, [missions, projects])
  
  const regularUpcomingMissions = useMemo(() => {
    const challengeProjectIds = new Set(
      projects.filter(p => isChallengeProject(p.name)).map(p => p.id)
    )
    return upcomingMissions.filter(m => !challengeProjectIds.has(m.project_id))
  }, [upcomingMissions, projects])
  
  const regularOverdueMissions = useMemo(() => {
    const challengeProjectIds = new Set(
      projects.filter(p => isChallengeProject(p.name)).map(p => p.id)
    )
    return overdueMissions.filter(m => !challengeProjectIds.has(m.project_id))
  }, [overdueMissions, projects])

  // Helper function to get project by ID
  const getProjectById = (projectId: number) => {
    return projects.find(p => p.id === projectId)
  }

  const [activeTab, setActiveTab] = useState('all')
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Combined loading state for initial data fetch
  const isInitialLoading = isMissionsLoading || isProjectsLoading

  // Fetch data on mount - load both projects and missions in parallel
  useEffect(() => {
    if (!serverHealth) return
    
    // Load projects first, then missions (missions need projects for filtering)
    const loadData = async () => {
      await fetchProjects()
      await Promise.all([
        fetchMissions(),
        fetchUpcomingMissions(72), // Get missions due in next 72 hours
        fetchOverdueMissions(),
      ])
    }
    
    loadData()

    // Auto-refresh every 5 minutes
    const interval = setInterval(() => {
      fetchUpcomingMissions(72)
      fetchOverdueMissions()
    }, 5 * 60 * 1000)

    return () => clearInterval(interval)
  }, [serverHealth, fetchProjects, fetchMissions, fetchUpcomingMissions, fetchOverdueMissions])

  // Filter active missions (excluding Challenge-related)
  const activeMissions = regularMissions.filter((m) => isMissionActive(m.state))

  // Sort by priority (overdue first, then by deadline)
  const sortedMissions = [...activeMissions].sort((a, b) => {
    const aOverdue = isMissionOverdue(a.ddl, a.state)
    const bOverdue = isMissionOverdue(b.ddl, b.state)

    // Overdue missions first
    if (aOverdue && !bOverdue) return -1
    if (!aOverdue && bOverdue) return 1

    // Then by deadline (earliest first)
    const aDdl = getDdlTimestamp(a.ddl) ?? Infinity
    const bDdl = getDdlTimestamp(b.ddl) ?? Infinity
    return aDdl - bDdl
  })

  // Get missions for each tab
  const getTabMissions = (): MissionData[] => {
    switch (activeTab) {
      case 'urgent':
        return sortedMissions.filter(
          (m) => isMissionOverdue(m.ddl, m.state) || getHoursUntilDeadline(m.ddl) <= 24
        )
      case 'today':
        return sortedMissions.filter((m) => {
          const ddlDate = parseDdl(m.ddl)
          if (!ddlDate) return false
          const today = new Date()
          return ddlDate.toDateString() === today.toDateString()
        })
      case 'doing':
        return sortedMissions.filter((m) => m.state === MissionState.DOING)
      default:
        return sortedMissions
    }
  }

  const displayMissions = maxItems
    ? getTabMissions().slice(0, maxItems)
    : getTabMissions()

  // Counts (excluding Challenge-related)
  const urgentCount = sortedMissions.filter(
    (m) => isMissionOverdue(m.ddl, m.state) || getHoursUntilDeadline(m.ddl) <= 24
  ).length
  const doingCount = sortedMissions.filter((m) => m.state === MissionState.DOING).length
  const overdueCount = regularOverdueMissions.length

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await fetchProjects()
      await Promise.all([
        fetchMissions(),
        fetchUpcomingMissions(72),
        fetchOverdueMissions(),
      ])
    } finally {
      setIsRefreshing(false)
    }
  }

  if (!serverHealth) {
    return (
      <Card className="border-destructive">
        <CardContent className="p-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>服务器连接失败</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className={isMobile ? 'text-base' : 'text-lg'}>{title}</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">
                {activeMissions.length} 待办
              </Badge>
              {overdueCount > 0 && (
                <Badge variant="destructive">
                  {overdueCount} 逾期
                </Badge>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
            <AddMissionDialog />
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {showFilters && (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="all" className="gap-1">
                全部
                <Badge variant="secondary" className="ml-1 h-5 px-1.5">
                  {activeMissions.length}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="urgent" className="gap-1">
                <AlertTriangle className="h-3 w-3" />
                紧急
                {urgentCount > 0 && (
                  <Badge variant="destructive" className="ml-1 h-5 px-1.5">
                    {urgentCount}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="doing" className="gap-1">
                <Clock className="h-3 w-3" />
                进行中
                {doingCount > 0 && (
                  <Badge variant="default" className="ml-1 h-5 px-1.5">
                    {doingCount}
                  </Badge>
                )}
              </TabsTrigger>
            </TabsList>

            <TabsContent value={activeTab} className="mt-0">
              {isInitialLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : displayMissions.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mb-4 text-green-500" />
                  <p className="text-lg font-medium">暂无待办任务</p>
                  <p className="text-sm">
                    {activeTab === 'urgent'
                      ? '没有紧急任务，继续保持！'
                      : activeTab === 'doing'
                      ? '没有正在进行的任务'
                      : '所有任务都已完成！'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Overdue section */}
                  {activeTab === 'all' && overdueMissions.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-1">
                        <AlertTriangle className="h-4 w-4" />
                        已逾期（需要立即处理）
                      </h4>
                      <div className="space-y-2">
                        {regularOverdueMissions.map((mission) => (
                          <MissionCard
                            key={mission.id}
                            mission={mission}
                            project={getProjectById(mission.project_id)}
                            compact
                            showProject
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Regular missions */}
                  {displayMissions
                    .filter((m) => !isMissionOverdue(m.ddl, m.state) || activeTab !== 'all')
                    .map((mission) => (
                      <MissionCard
                        key={mission.id}
                        mission={mission}
                        project={getProjectById(mission.project_id)}
                        compact
                        showProject
                      />
                    ))}

                  {/* Show more button */}
                  {maxItems && getTabMissions().length > maxItems && (
                    <Button variant="ghost" className="w-full">
                      查看全部 {getTabMissions().length} 项
                    </Button>
                  )}
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}

        {!showFilters && (
          <>
            {isInitialLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : displayMissions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <CheckCircle2 className="h-10 w-10 mb-3 text-green-500" />
                <p className="font-medium">暂无待办任务</p>
              </div>
            ) : (
              <div className="space-y-2">
                {displayMissions.map((mission) => (
                  <MissionCard
                    key={mission.id}
                    mission={mission}
                    compact
                    showProject
                  />
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default ReminderTodoList
