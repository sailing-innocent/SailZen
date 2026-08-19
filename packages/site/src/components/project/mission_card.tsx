import React, { useState, useMemo } from 'react'
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
  Target,
} from 'lucide-react'
import MissionDetailDialog from './mission_detail_dialog'
import { useAffairsStore, type AffairsState } from '@lib/store/affair'
import {
  type AffairData,
  AffairState,
  AffairStateLabels,
  isAffairActive,
  isAffairOverdue,
  getHoursUntilDeadline,
  formatDeadline,
  getAffairPriority,
  getAffairDeadline,
} from '@lib/data/affair'
import { cn } from '@/lib/utils'
import MissionPostponeDialog from './mission_postpone_dialog'
import { isChallengeAffair, parseChallengeName, ChallengeTypeIcons, ChallengeTypeLabels } from '@lib/data/challenge'

export interface MissionCardProps {
  mission: AffairData
  compact?: boolean
  showProject?: boolean
  project?: AffairData
  onComplete?: () => void
}

const MissionCard: React.FC<MissionCardProps> = ({
  mission,
  compact = false,
  showProject = false,
  project,
  onComplete,
}) => {
  const [isPostponeOpen, setIsPostponeOpen] = useState(false)
  const [isDetailOpen, setIsDetailOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const startTask = useAffairsStore((state: AffairsState) => state.startTask)
  const finishTask = useAffairsStore((state: AffairsState) => state.finishTask)
  const cancelTask = useAffairsStore((state: AffairsState) => state.cancelTask)
  const reopenTask = useAffairsStore((state: AffairsState) => state.reopenTask)

  const displayDeadline = getAffairDeadline(mission)
  const isOverdue = isAffairOverdue(displayDeadline, mission.state)
  const isActive = isAffairActive(mission.state)
  const hoursUntilDeadline = getHoursUntilDeadline(displayDeadline)

  // Check if this mission belongs to a Challenge venture
  const challengeInfo = useMemo(() => {
    if (!project || !isChallengeAffair(project.title)) {
      return null
    }
    const parsed = parseChallengeName(project.title)
    if (!parsed) return null
    return {
      type: parsed.type,
      typeLabel: ChallengeTypeLabels[parsed.type],
      icon: ChallengeTypeIcons[parsed.type],
      title: parsed.title,
      days: parsed.days,
    }
  }, [project])

  const priority = getAffairPriority(displayDeadline, mission.state)

  // State badge color
  const getStateBadgeVariant = (): 'default' | 'secondary' | 'destructive' | 'outline' => {
    switch (mission.state) {
      case AffairState.DOING:
        return 'default'
      case AffairState.DONE:
        return 'secondary'
      case AffairState.CANCELED:
        return 'destructive'
      default:
        return 'outline'
    }
  }

  // Handle state transitions
  const handleStartDoing = async () => {
    setIsLoading(true)
    try {
      await startTask(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleComplete = async () => {
    setIsLoading(true)
    try {
      await finishTask(mission.id)
      onComplete?.()
    } finally {
      setIsLoading(false)
    }
  }

  const handleCancel = async () => {
    setIsLoading(true)
    try {
      await cancelTask(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReopen = async () => {
    setIsLoading(true)
    try {
      await reopenTask(mission.id)
    } finally {
      setIsLoading(false)
    }
  }

  const handleViewDetail = () => {
    setIsDetailOpen(true)
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
            <Checkbox
              checked={mission.state === AffairState.DONE}
              disabled={isLoading || mission.state === AffairState.CANCELED}
              onCheckedChange={(checked) => {
                if (checked) {
                  handleComplete()
                } else {
                  handleReopen()
                }
              }}
              className="mt-1"
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                {challengeInfo && (
                  <span className="text-lg" title={`${challengeInfo.typeLabel}挑战`}>
                    {challengeInfo.icon}
                  </span>
                )}
                {challengeInfo && (
                  <span className="text-sm text-muted-foreground truncate max-w-[120px]">
                    {challengeInfo.title}
                  </span>
                )}
                <span
                  className={cn(
                    'font-medium truncate',
                    mission.state === AffairState.DONE && 'line-through text-muted-foreground'
                  )}
                >
                  {mission.title}
                </span>
                {isOverdue && isActive && (
                  <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" />
                )}
              </div>

              {!compact && mission.description && !challengeInfo && (
                <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
                  {mission.description}
                </p>
              )}

              {challengeInfo && (
                <div className="flex items-center gap-1 mb-2">
                  <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
                    <Target className="h-3 w-3 mr-1" />
                    {challengeInfo.typeLabel}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {challengeInfo.days}天挑战
                  </span>
                </div>
              )}

              <div className="flex items-center gap-2 flex-wrap text-xs">
                <Badge variant={getStateBadgeVariant()} className="text-xs">
                  {AffairStateLabels[mission.state]}
                </Badge>

                {displayDeadline && isActive && (
                  <span
                    className={cn(
                      'flex items-center gap-1',
                      isOverdue ? 'text-red-500' : 'text-muted-foreground'
                    )}
                  >
                    <Clock className="h-3 w-3" />
                    {mission.state === AffairState.DEFERRED
                      ? `延期至 ${formatDeadline(displayDeadline)}`
                      : formatDeadline(displayDeadline)}
                  </span>
                )}

                {showProject && mission.parent_id && mission.parent_id > 0 && (
                  <span className="text-muted-foreground">
                    事业 #{mission.parent_id}
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {isActive && mission.state !== AffairState.DOING && (
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

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {(mission.state === AffairState.INBOX ||
                    mission.state === AffairState.PLANNED ||
                    mission.state === AffairState.SCHEDULED) && (
                    <>
                      <DropdownMenuItem onClick={() => setIsPostponeOpen(true)}>
                        <Calendar className="h-4 w-4 mr-2" />
                        延期
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                    </>
                  )}

                  <DropdownMenuItem onClick={handleViewDetail}>
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

      <MissionPostponeDialog
        mission={mission}
        open={isPostponeOpen}
        onOpenChange={setIsPostponeOpen}
      />

      <MissionDetailDialog
        mission={mission}
        project={project}
        open={isDetailOpen}
        onOpenChange={setIsDetailOpen}
      />
    </>
  )
}

export default MissionCard
