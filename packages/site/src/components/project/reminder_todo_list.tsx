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
import { type AffairsState, useAffairsStore } from '@lib/store/affair'
import { useServerStore } from '@lib/store'
import { isChallengeAffair } from '@lib/data/challenge'
import {
  type AffairData,
  AffairState,
  isAffairActive,
  isAffairOverdue,
  parseDdl,
  getHoursUntilDeadline,
  getDdlTimestamp,
} from '@lib/data/affair'
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

  const tasks = useAffairsStore((state: AffairsState) => state.tasks)
  const upcomingTasks = useAffairsStore((state: AffairsState) => state.upcomingTasks)
  const overdueTasks = useAffairsStore((state: AffairsState) => state.overdueTasks)
  const isLoading = useAffairsStore((state: AffairsState) => state.isLoading)
  const fetchTasks = useAffairsStore((state: AffairsState) => state.fetchTasks)
  const fetchUpcomingTasks = useAffairsStore((state: AffairsState) => state.fetchUpcomingTasks)
  const fetchOverdueTasks = useAffairsStore((state: AffairsState) => state.fetchOverdueTasks)

  const ventures = useAffairsStore((state: AffairsState) => state.ventures)
  const fetchVentures = useAffairsStore((state: AffairsState) => state.fetchVentures)

  const regularTasks = useMemo(() => {
    const challengeVentureIds = new Set(
      ventures.filter(v => isChallengeAffair(v.title)).map(v => v.id)
    )
    return tasks.filter(t => t.parent_id === null || !challengeVentureIds.has(t.parent_id))
  }, [tasks, ventures])

  const regularUpcomingTasks = useMemo(() => {
    const challengeVentureIds = new Set(
      ventures.filter(v => isChallengeAffair(v.title)).map(v => v.id)
    )
    return upcomingTasks.filter(t => t.parent_id === null || !challengeVentureIds.has(t.parent_id))
  }, [upcomingTasks, ventures])

  const regularOverdueTasks = useMemo(() => {
    const challengeVentureIds = new Set(
      ventures.filter(v => isChallengeAffair(v.title)).map(v => v.id)
    )
    return overdueTasks.filter(t => t.parent_id === null || !challengeVentureIds.has(t.parent_id))
  }, [overdueTasks, ventures])

  const getVentureById = (parentId: number | null) => {
    if (!parentId) return undefined
    return ventures.find(v => v.id === parentId)
  }

  const [activeTab, setActiveTab] = useState('all')
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    if (!serverHealth) return
    const loadData = async () => {
      await fetchVentures()
      await Promise.all([
        fetchTasks(),
        fetchUpcomingTasks(72),
        fetchOverdueTasks(),
      ])
    }
    loadData()

    const interval = setInterval(() => {
      fetchUpcomingTasks(72)
      fetchOverdueTasks()
    }, 5 * 60 * 1000)

    return () => clearInterval(interval)
  }, [serverHealth, fetchVentures, fetchTasks, fetchUpcomingTasks, fetchOverdueTasks])

  const activeTasks = regularTasks.filter((t) => isAffairActive(t.state))

  const sortedTasks = [...activeTasks].sort((a, b) => {
    const aOverdue = isAffairOverdue(a.urgency_ddl, a.state)
    const bOverdue = isAffairOverdue(b.urgency_ddl, b.state)

    if (aOverdue && !bOverdue) return -1
    if (!aOverdue && bOverdue) return 1

    const aDdl = getDdlTimestamp(a.urgency_ddl) ?? Infinity
    const bDdl = getDdlTimestamp(b.urgency_ddl) ?? Infinity
    return aDdl - bDdl
  })

  const getTabTasks = (): AffairData[] => {
    switch (activeTab) {
      case 'urgent':
        return sortedTasks.filter(
          (t) => isAffairOverdue(t.urgency_ddl, t.state) || getHoursUntilDeadline(t.urgency_ddl) <= 24
        )
      case 'today':
        return sortedTasks.filter((t) => {
          const ddlDate = parseDdl(t.urgency_ddl)
          if (!ddlDate) return false
          const today = new Date()
          return ddlDate.toDateString() === today.toDateString()
        })
      case 'doing':
        return sortedTasks.filter((t) => t.state === AffairState.DOING)
      default:
        return sortedTasks
    }
  }

  const displayTasks = maxItems
    ? getTabTasks().slice(0, maxItems)
    : getTabTasks()

  const urgentCount = sortedTasks.filter(
    (t) => isAffairOverdue(t.urgency_ddl, t.state) || getHoursUntilDeadline(t.urgency_ddl) <= 24
  ).length
  const doingCount = sortedTasks.filter((t) => t.state === AffairState.DOING).length
  const overdueCount = regularOverdueTasks.length

  const handleRefresh = async () => {
    setIsRefreshing(true)
    try {
      await fetchVentures()
      await Promise.all([
        fetchTasks(),
        fetchUpcomingTasks(72),
        fetchOverdueTasks(),
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
                {activeTasks.length} 待办
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
                  {activeTasks.length}
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
              {isLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              ) : displayTasks.length === 0 ? (
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
                  {activeTab === 'all' && overdueTasks.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-red-600 mb-2 flex items-center gap-1">
                        <AlertTriangle className="h-4 w-4" />
                        已逾期（需要立即处理）
                      </h4>
                      <div className="space-y-2">
                        {regularOverdueTasks.map((task) => (
                          <MissionCard
                            key={task.id}
                            mission={task}
                            project={getVentureById(task.parent_id)}
                            compact
                            showProject
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {displayTasks
                    .filter((t) => !isAffairOverdue(t.urgency_ddl, t.state) || activeTab !== 'all')
                    .map((task) => (
                      <MissionCard
                        key={task.id}
                        mission={task}
                        project={getVentureById(task.parent_id)}
                        compact
                        showProject
                      />
                    ))}

                  {maxItems && getTabTasks().length > maxItems && (
                    <Button variant="ghost" className="w-full">
                      查看全部 {getTabTasks().length} 项
                    </Button>
                  )}
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}

        {!showFilters && (
          <>
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : displayTasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <CheckCircle2 className="h-10 w-10 mb-3 text-green-500" />
                <p className="font-medium">暂无待办任务</p>
              </div>
            ) : (
              <div className="space-y-2">
                {displayTasks.map((task) => (
                  <MissionCard
                    key={task.id}
                    mission={task}
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
