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
import type { MissionData, ProjectData } from '@lib/data/project'
import {
  MissionStateLabels,
  MissionState,
  parseDdl,
  isMissionActive,
  isMissionOverdue,
} from '@lib/data/project'
import { cn } from '@lib/utils'

export interface MissionDetailDialogProps {
  mission: MissionData | null
  project?: ProjectData | null
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

  const isActive = isMissionActive(mission.state)
  const isOverdue = isMissionOverdue(mission.ddl, mission.state)
  const deadline = parseDdl(mission.ddl)

  // Get state icon
  const getStateIcon = () => {
    switch (mission.state) {
      case MissionState.DONE:
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case MissionState.DOING:
        return <PlayCircle className="h-5 w-5 text-yellow-500" />
      case MissionState.CANCELED:
        return <XCircle className="h-5 w-5 text-red-500" />
      case MissionState.READY:
        return <Circle className="h-5 w-5 text-blue-500" />
      default:
        return <Circle className="h-5 w-5 text-gray-500" />
    }
  }

  // Get state badge variant
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
          {/* Task Name */}
          <div className="space-y-2">
            <Label className="text-muted-foreground">任务名称</Label>
            <p className={cn(
              "text-lg font-medium",
              mission.state === MissionState.DONE && "line-through text-muted-foreground"
            )}>
              {mission.name}
            </p>
          </div>

          {/* Task State */}
          <div className="space-y-2">
            <Label className="text-muted-foreground">任务状态</Label>
            <div className="flex items-center gap-2">
              <Badge variant={getStateBadgeVariant()}>
                {MissionStateLabels[mission.state ?? 0]}
              </Badge>
              {isOverdue && (
                <Badge variant="destructive" className="gap-1">
                  <Clock className="h-3 w-3" />
                  已逾期
                </Badge>
              )}
            </div>
          </div>

          {/* Project Info */}
          {project && project.id > 0 && (
            <div className="space-y-2">
              <Label className="text-muted-foreground">所属项目</Label>
              <div className="flex items-center gap-2 text-sm">
                <Folder className="h-4 w-4 text-muted-foreground" />
                <span>{project.name}</span>
              </div>
            </div>
          )}

          {/* Deadline */}
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

          {/* Description */}
          {mission.description && (
            <div className="space-y-2">
              <Label className="text-muted-foreground">任务描述</Label>
              <div className="p-3 bg-muted rounded-md">
                <p className="text-sm whitespace-pre-wrap">{mission.description}</p>
              </div>
            </div>
          )}

          {/* Task ID (for reference) */}
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
