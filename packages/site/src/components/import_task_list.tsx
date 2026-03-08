/**
 * @file import_task_list.tsx
 * @brief Import Task List Component
 * @author sailing-innocent
 * @date 2026-03-08
 */

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { getImportTasks, cancelImportTask, deleteImportTask } from '@lib/api/asyncImport'
import type { ImportTask } from '@lib/data/text'

export default function ImportTaskList() {
  const [tasks, setTasks] = useState<ImportTask[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string | undefined>(undefined)

  const fetchTasks = async () => {
    try {
      const response = await getImportTasks(filter)
      setTasks(response.tasks)
    } catch (err) {
      console.error('Failed to fetch tasks:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 5000) // 每5秒刷新
    return () => clearInterval(interval)
  }, [filter])

  const handleCancel = async (taskId: number) => {
    try {
      await cancelImportTask(taskId)
      fetchTasks()
    } catch (err) {
      console.error('Failed to cancel task:', err)
    }
  }

  const handleDelete = async (taskId: number) => {
    if (!confirm('确定要删除这个任务记录吗？')) return
    try {
      await deleteImportTask(taskId)
      fetchTasks()
    } catch (err) {
      console.error('Failed to delete task:', err)
    }
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      pending: 'bg-yellow-500',
      scheduled: 'bg-blue-500',
      running: 'bg-green-500',
      completed: 'bg-green-600',
      failed: 'bg-red-500',
      cancelled: 'bg-gray-500',
    }
    const labels: Record<string, string> = {
      pending: '等待中',
      scheduled: '已调度',
      running: '进行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    }
    return <Badge className={variants[status] || 'bg-gray-500'}>{labels[status] || status}</Badge>
  }

  if (loading) {
    return <div>加载中...</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button
          variant={filter === undefined ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter(undefined)}
        >
          全部
        </Button>
        <Button
          variant={filter === 'running' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('running')}
        >
          进行中
        </Button>
        <Button
          variant={filter === 'completed' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('completed')}
        >
          已完成
        </Button>
        <Button
          variant={filter === 'failed' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('failed')}
        >
          失败
        </Button>
      </div>

      {tasks.length === 0 ? (
        <div className="text-center text-muted-foreground py-8">暂无导入任务</div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{task.work_title}</span>
                  {task.work_author && (
                    <span className="text-sm text-muted-foreground">
                      by {task.work_author}
                    </span>
                  )}
                </div>
                {getStatusBadge(task.status)}
              </div>

              <div className="mb-2">
                <Progress value={task.progress} />
                <div className="text-xs text-muted-foreground mt-1">
                  {task.progress}% - {task.current_phase || '等待中'}
                </div>
              </div>

              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>任务ID: {task.id}</span>
                <span>{new Date(task.created_at).toLocaleString()}</span>
              </div>

              <div className="flex gap-2 mt-2">
                {['pending', 'scheduled', 'running'].includes(task.status) && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleCancel(task.id)}
                  >
                    取消
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(task.id)}
                >
                  删除
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
