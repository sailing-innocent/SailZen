import React, { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Clock,
  MoreHorizontal,
  Play,
  CheckCircle,
  XCircle,
  Calendar,
  AlertTriangle,
  ExternalLink,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useMissionsStore, type MissionsState } from '@lib/store/project'
import {
  type MissionData,
  MissionState,
  MissionStateLabels,
  isMissionActive,
  isMissionOverdue,
  getHoursUntilDeadline,
  parseDdl,
} from '@lib/data/project'
import { cn } from '@lib/utils'
import MissionPostponeDialog from './mission_postpone_dialog'

export interface MissionCardProps {
  mission: MissionData
  compact?: boolean
  showProject?: boolean
  onComplete?: () => void
}

const MissionCard: React.FC<MissionCardProps> = ({
  mission,
  compact = false,
  showProject = false,
  onComplete,
}) => {
  const navigate = useNavigate()
  const [isPostponeOpen, setIsPostponeOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const doingMission = useMissionsStore((state: MissionsState) => state.doingMission)
  const doneMission = useMissionsStore((state: MissionsState) => state.doneMission)
  const cancelMission = useMissionsStore((state: MissionsState) => state.cancelMission)
  const pendingMission = useMissionsStore((state: MissionsState) => state.pendingMission)

  const isOverdue = isMissionOverdue(mission.ddl, mission.state)
  const isActive = isMissionActive(mission.state)
  const hoursUntilDeadline = getHoursUntilDeadline(mission.ddl)

  // Get priority based on deadline
  const getPriority = (): 'urgent' | 'high' | 'normal' | 'low' => {
    if (!isActive) return 'low'
    if (isOverdue) return 'urgent'
    if (hoursUntilDeadline <= 2) return 'urgent'
    if (hoursUntilDeadline <= 24) return 'high'
    if (hoursUntilDeadline <= 72) return 'normal'
    return 'low'
  }

  const priority = getPriority()

  // Format deadline display
  const formatDeadline = (): string => {
    const date = parseDdl(mission.ddl)
    if (!date) return '无截止日期'
    const now = new Date()
    const diffHours = (date.getTime() - now.getTime()) / (1000 * 60 * 60)

    if (diffHours < 0) {
      const overdueDays = Math.floor(Math.abs(diffHours) / 24)
      if (overdueDays > 0) {
        return `已逾期 ${overdueDays} 天`
      }
      return `已逾期 ${Math.floor(Math.abs(diffHours))} 小时`
    } else if (diffHours < 1) {
      return `${Math.floor(diffHours * 60)} 分钟后`
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)} 小时后`
    } else if (diffHours < 72) {
      return `${Math.floor(diffHours / 24)} 天后`
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    }
  }

  // State badge color
  const getStateBadgeVariant = (): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (mission.state) {
      case MissionState.DOING:
        return 'default'
      case MissionState.DONE:
        return 'secondary'
      case MissionState.CANCELED:
        return 'destructive'
      default:
        return 'outline'
    }
  }

  // Handle state transitions
  const handleStartDoing = async () => {
    setIsLoading(true)
    try {
      await doingMission(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleComplete = async () => {
    setIsLoading(true)
    try {
      await doneMission(mission.id)
      onComplete?.()
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancel = async () => {
    setIsLoading(true)
    try {
      await cancelMission(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReopen = async () => {
    setIsLoading(true)
    try {
      await pendingMission(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleNavigateToProject = () => {
    navigate(`/project?mission=${mission.id}`)
  }


  return (
    <>
      <Card
        className={cn(
          'group transition-all hover:shadow-md',
          priority === 'urgent' && isActive && 'border-l-4 border-l-red-500',
          priority === 'high' && isActive && 'border-l-4 border-l-orange-500',
          !isActive && 'opacity-60'
        )}
      >
        <CardContent className={cn('p-4', compact && 'p-3')}>
          <div className="flex items-start gap-3">
            {/* Checkbox for quick complete */}
            <Checkbox
              checked={mission.state === MissionState.DONE}
              disabled={isLoading || mission.state === MissionState.CANCELED}
              onCheckedChange={(checked) => {
                if (checked) {
                  handleComplete()
                } else {
                  handleReopen()
                }
              }}
              className="mt-1"
            />

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={cn(
                    'font-medium truncate',
                    mission.state === MissionState.DONE && 'line-through text-muted-foreground'
                  )}
                >
                  {mission.name}
                </span>
                {isOverdue && isActive && (
                  <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
                )}
              </div>

              {!compact && mission.description && (
                <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                  {mission.description}
                </p>
              )}

              <div className="flex items-center gap-2 flex-wrap text-xs">
                {/* State badge */}
                <Badge variant={getStateBadgeVariant()} className="text-xs">
                  {MissionStateLabels[mission.state ?? 0]}
                </Badge>

                {/* Deadline */}
                {mission.ddl && isActive && (
                  <span
                    className={cn(
                      'flex items-center gap-1',
                      isOverdue ? 'text-red-500' : 'text-muted-foreground'
                    )}
                  >
                    <Clock className="h-3 w-3" />
                    {formatDeadline()}
                  </span>
                )}

                {/* Project ID if showing */}
                {showProject && mission.project_id > 0 && (
                  <span className="text-muted-foreground">
                    项目 #{mission.project_id}
                  </span>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {/* Quick action based on current state */}
              {isActive && mission.state !== MissionState.DOING && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleStartDoing}
                  disabled={isLoading}
                  title="开始执行"
                >
                  <Play className="h-4 w-4" />
                </Button>
              )}

              {isActive && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleComplete}
                  disabled={isLoading}
                  title="标记完成"
                >
                  <CheckCircle className="h-4 w-4" />
                </Button>
              )}

              {/* More actions dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {isActive && (
                    <>
                      <DropdownMenuItem onClick={() => setIsPostponeOpen(true)}>
                        <Calendar className="h-4 w-4 mr-2" />
                        延期
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}
                  
                  <DropdownMenuItem onClick={handleNavigateToProject}>
                    <ExternalLink className="h-4 w-4 mr-2" />
                    查看详情
                  </DropdownMenuItem>

                  {isActive && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={handleCancel}
                        className="text-destructive"
                      >
                        <XCircle className="h-4 w-4 mr-2" />
                        取消任务
                      </DropdownMenuItem>
                    </>
                  )}

                  {!isActive && (
                    <DropdownMenuItem onClick={handleReopen}>
                      <Play className="h-4 w-4 mr-2" />
                      重新打开
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Postpone Dialog */}
      <MissionPostponeDialog
        mission={mission}
        open={isPostponeOpen}
        onOpenChange={setIsPostponeOpen}
      />
    </>
  )
}

export default MissionCard
