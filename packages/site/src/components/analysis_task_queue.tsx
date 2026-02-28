/**
 * @file analysis_task_queue.tsx
 * @brief Analysis Task Queue Panel - 分析任务队列面板
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Play,
  Square,
  RotateCw,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Activity,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AnalysisTask, AnalysisTaskStatus, AnalysisTaskType } from '@lib/data/analysis'
import { getTaskStatusLabel, getTaskStatusColor, getTaskTypeLabel } from '@lib/data/analysis'

// ============================================================================
// Types
// ============================================================================

interface AnalysisTaskQueueProps {
  tasks: AnalysisTask[]
  onCancel?: (taskId: string) => void
  onRetry?: (taskId: string) => void
  onDelete?: (taskId: string) => void
  onSelect?: (task: AnalysisTask) => void
  selectedTaskId?: string | null
  className?: string
}

// ============================================================================
// Status Badge Component
// ============================================================================

interface StatusBadgeProps {
  status: AnalysisTaskStatus
  progress?: number
}

function StatusBadge({ status, progress }: StatusBadgeProps) {
  const config: Record<AnalysisTaskStatus, {
    icon: React.ReactNode
    variant: 'default' | 'secondary' | 'destructive' | 'outline'
    className?: string
  }> = {
    pending: {
      icon: <Clock className="w-3 h-3" />,
      variant: 'secondary',
      className: 'text-yellow-700 bg-yellow-100',
    },
    running: {
      icon: <Activity className="w-3 h-3 animate-pulse" />,
      variant: 'default',
    },
    completed: {
      icon: <CheckCircle className="w-3 h-3" />,
      variant: 'default',
      className: 'text-green-700 bg-green-100',
    },
    failed: {
      icon: <XCircle className="w-3 h-3" />,
      variant: 'destructive',
    },
    cancelled: {
      icon: <Square className="w-3 h-3" />,
      variant: 'outline',
    },
  }

  const { icon, variant, className } = config[status]

  return (
    <div className="flex items-center gap-2">
      <Badge variant={variant} className={cn("flex items-center gap-1", className)}>
        {icon}
        {getTaskStatusLabel(status)}
      </Badge>
      {status === 'running' && progress !== undefined && (
        <span className="text-xs text-muted-foreground">{progress}%</span>
      )}
    </div>
  )
}

// ============================================================================
// Task Card Component
// ============================================================================

interface TaskCardProps {
  task: AnalysisTask
  isSelected?: boolean
  onCancel?: () => void
  onRetry?: () => void
  onDelete?: () => void
  onClick?: () => void
}

function TaskCard({
  task,
  isSelected,
  onCancel,
  onRetry,
  onDelete,
  onClick,
}: TaskCardProps) {
  const isRunning = task.status === 'running'
  const isPending = task.status === 'pending'
  const isFailed = task.status === 'failed'
  const isCompleted = task.status === 'completed'

  return (
    <div
      className={cn(
        "p-3 rounded-lg border cursor-pointer transition-all",
        isSelected
          ? "border-primary bg-primary/5"
          : "border-border hover:border-primary/50 hover:bg-muted/50"
      )}
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">
              {getTaskTypeLabel(task.task_type)}
            </span>
            <span className="text-xs text-muted-foreground">
              #{task.id.slice(0, 8)}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {task.current_step || '等待执行'}
          </div>
        </div>
        <StatusBadge status={task.status} progress={task.progress} />
      </div>

      {/* Progress Bar */}
      {(isRunning || isCompleted) && (
        <div className="mb-3">
          <Progress value={task.progress} className="h-1.5" />
        </div>
      )}

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
        <div className="flex items-center gap-3">
          <span>创建于: {new Date(task.created_at).toLocaleDateString()}</span>
          {task.started_at && (
            <span>开始于: {new Date(task.started_at).toLocaleTimeString()}</span>
          )}
        </div>
      </div>

      {/* Error Message */}
      {task.error_message && (
        <div className="flex items-start gap-1.5 text-xs text-destructive mb-2 p-2 bg-destructive/10 rounded">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span className="line-clamp-2">{task.error_message}</span>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1">
        {(isRunning || isPending) && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-destructive hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation()
              onCancel?.()
            }}
          >
            <Square className="w-3 h-3 mr-1" />
            取消
          </Button>
        )}
        
        {isFailed && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2"
            onClick={(e) => {
              e.stopPropagation()
              onRetry?.()
            }}
          >
            <RotateCw className="w-3 h-3 mr-1" />
            重试
          </Button>
        )}

        {(isCompleted || isFailed || task.status === 'cancelled') && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-destructive hover:text-destructive ml-auto"
            onClick={(e) => {
              e.stopPropagation()
              onDelete?.()
            }}
          >
            <Trash2 className="w-3 h-3" />
          </Button>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Empty State Component
// ============================================================================

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="p-4 rounded-full bg-muted mb-4">
        <Activity className="w-6 h-6 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium mb-1">暂无任务</h3>
      <p className="text-sm text-muted-foreground">
        创建分析任务后，任务队列将显示在这里
      </p>
    </div>
  )
}

// ============================================================================
// Queue Stats Component
// ============================================================================

interface QueueStatsProps {
  tasks: AnalysisTask[]
}

function QueueStats({ tasks }: QueueStatsProps) {
  const stats = {
    total: tasks.length,
    pending: tasks.filter((t) => t.status === 'pending').length,
    running: tasks.filter((t) => t.status === 'running').length,
    completed: tasks.filter((t) => t.status === 'completed').length,
    failed: tasks.filter((t) => t.status === 'failed').length,
  }

  return (
    <div className="grid grid-cols-5 gap-2 p-3 bg-muted/50 rounded-lg">
      <div className="text-center">
        <div className="text-lg font-semibold">{stats.total}</div>
        <div className="text-xs text-muted-foreground">总计</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-semibold text-yellow-600">{stats.pending}</div>
        <div className="text-xs text-muted-foreground">待执行</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-semibold text-blue-600">{stats.running}</div>
        <div className="text-xs text-muted-foreground">运行中</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-semibold text-green-600">{stats.completed}</div>
        <div className="text-xs text-muted-foreground">已完成</div>
      </div>
      <div className="text-center">
        <div className="text-lg font-semibold text-red-600">{stats.failed}</div>
        <div className="text-xs text-muted-foreground">失败</div>
      </div>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export function AnalysisTaskQueue({
  tasks,
  onCancel,
  onRetry,
  onDelete,
  onSelect,
  selectedTaskId,
  className,
}: AnalysisTaskQueueProps) {
  const [filter, setFilter] = useState<AnalysisTaskStatus | 'all'>('all')

  // Filter tasks
  const filteredTasks = filter === 'all'
    ? tasks
    : tasks.filter((t) => t.status === filter)

  // Sort tasks: running first, then pending, then others by date
  const sortedTasks = [...filteredTasks].sort((a, b) => {
    const priority = { running: 0, pending: 1, completed: 2, failed: 3, cancelled: 4 }
    if (priority[a.status] !== priority[b.status]) {
      return priority[a.status] - priority[b.status]
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="w-4 h-4" />
            任务队列
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant={filter === 'all' ? 'default' : 'ghost'}
              className="h-7 text-xs"
              onClick={() => setFilter('all')}
            >
              全部
            </Button>
            <Button
              size="sm"
              variant={filter === 'running' ? 'default' : 'ghost'}
              className="h-7 text-xs"
              onClick={() => setFilter('running')}
            >
              运行中
            </Button>
            <Button
              size="sm"
              variant={filter === 'pending' ? 'default' : 'ghost'}
              className="h-7 text-xs"
              onClick={() => setFilter('pending')}
            >
              待执行
            </Button>
          </div>
        </div>
        <CardDescription>
          管理分析任务的执行和监控
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Stats */}
        <QueueStats tasks={tasks} />

        {/* Task List */}
        <ScrollArea className="h-[350px]">
          <div className="space-y-2">
            {sortedTasks.length > 0 ? (
              sortedTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  isSelected={selectedTaskId === task.id}
                  onCancel={() => onCancel?.(task.id)}
                  onRetry={() => onRetry?.(task.id)}
                  onDelete={() => onDelete?.(task.id)}
                  onClick={() => onSelect?.(task)}
                />
              ))
            ) : (
              <EmptyState />
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

export default AnalysisTaskQueue
