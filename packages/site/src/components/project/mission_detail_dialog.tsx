import React from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Calendar, Clock, CheckCircle2, Circle, PlayCircle, XCircle, Folder } from 'lucide-react'
import type { AffairData } from '@lib/data/affair'
import {
  AffairStateLabels,
  AffairState,
  parseDdl,
  isAffairActive,
  isAffairOverdue,
} from '@lib/data/affair'
import { cn } from '@lib/utils'

export interface MissionDetailDialogProps {
  mission: AffairData | null
  project?: AffairData | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const MissionDetailDialog: React.FC<MissionDetailDialogProps> = ({
  mission,
  project,
  open,
  onOpenChange,
}) => {
  if (!mission) return null

  const isActive = isAffairActive(mission.state)
  const isOverdue = isAffairOverdue(mission.urgency_ddl, mission.state)
  const deadline = parseDdl(mission.urgency_ddl)

  const getStateIcon = () => {
    switch (mission.state) {
      case AffairState.DONE:
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case AffairState.DOING:
        return <PlayCircle className="h-5 w-5 text-yellow-500" />
      case AffairState.CANCELED:
        return <XCircle className="h-5 w-5 text-red-500" />
      case AffairState.PLANNED:
      case AffairState.SCHEDULED:
        return <Circle className="h-5 w-5 text-blue-500" />
      default:
        return <Circle className="h-5 w-5 text-gray-500" />
    }
  }

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {getStateIcon()}
            <span>任务详情</span>
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          <div className="space-y-2">
            <Label className="text-muted-foreground">任务名称</Label>
            <p className={cn(
              "text-lg font-medium",
              mission.state === AffairState.DONE && "line-through text-muted-foreground"
            )}>
              {mission.title}
            </p>
          </div>

          <div className="space-y-2">
            <Label className="text-muted-foreground">任务状态</Label>
            <div className="flex items-center gap-2">
              <Badge variant={getStateBadgeVariant()}>
                {AffairStateLabels[mission.state]}
              </Badge>
              {isOverdue && (
                <Badge variant="destructive" className="gap-1">
                  <Clock className="h-3 w-3" />
                  已逾期
                </Badge>
              )}
            </div>
          </div>

          {project && project.id > 0 && (
            <div className="space-y-2">
              <Label className="text-muted-foreground">所属事业</Label>
              <div className="flex items-center gap-2 text-sm">
                <Folder className="h-4 w-4 text-muted-foreground" />
                <span>{project.title}</span>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label className="text-muted-foreground">截止日期</Label>
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className={cn(
                "text-sm",
                isOverdue && "text-red-500 font-medium"
              )}>
                {deadline
                  ? deadline.toLocaleString('zh-CN', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      weekday: 'long',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : '未设置截止日期'}
              </span>
            </div>
          </div>

          {(mission.est_minutes !== undefined || mission.energy_cost !== undefined) && (
            <div className="space-y-2">
              <Label className="text-muted-foreground">精力与耗时</Label>
              <div className="flex flex-wrap gap-2">
                {mission.est_minutes !== undefined && mission.est_minutes > 0 && (
                  <Badge variant="outline" className="text-xs">
                    预计 {mission.est_minutes} 分钟
                  </Badge>
                )}
                {mission.energy_cost !== undefined && mission.energy_cost > 0 && (
                  <Badge variant="outline" className="text-xs">
                    精力 {mission.energy_cost}
                  </Badge>
                )}
              </div>
            </div>
          )}

          {mission.description && (
            <div className="space-y-2">
              <Label className="text-muted-foreground">任务描述</Label>
              <div className="p-3 bg-muted rounded-md">
                <p className="text-sm whitespace-pre-wrap">{mission.description}</p>
              </div>
            </div>
          )}

          <div className="pt-4 border-t">
            <p className="text-xs text-muted-foreground">
              任务 ID: {mission.id}
            </p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default MissionDetailDialog
