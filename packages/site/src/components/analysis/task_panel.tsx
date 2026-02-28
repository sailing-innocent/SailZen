/**
 * @file task_panel.tsx
 * @brief Analysis Task Management Panel - 分析任务管理面板
 * @author sailing-innocent
 * @date 2025-02-02
 * 
 * 提供完整的任务管理功能：创建、执行、监控、审核
 */

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  api_create_analysis_task,
  api_get_tasks_by_edition,
  api_get_task_results,
  api_approve_result,
  api_reject_result,
  api_apply_all_results,
  api_create_task_plan,
  api_execute_task_async,
  api_get_task_progress,
  api_cancel_running_task,
  api_get_llm_providers,
  api_get_analysis_task,
  type TaskProgress,
  type TaskExecutionPlan,
  type LLMProvider,
} from '@lib/api/analysis'
import type { AnalysisTask, AnalysisResult, CreateTaskRequest } from '@lib/data/analysis'

interface TaskPanelProps {
  editionId: number
}

const TASK_TYPES = [
  { id: 'outline_extraction', name: '大纲提取', description: '从章节中提取情节大纲' },
  { id: 'character_detection', name: '人物识别', description: '识别章节中的人物及其特征' },
  { id: 'setting_extraction', name: '设定提取', description: '提取世界观设定元素' },
]

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-500',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-yellow-500',
}

const STATUS_LABELS: Record<string, string> = {
  pending: '等待执行',
  running: '执行中',
  completed: '已完成',
  failed: '执行失败',
  cancelled: '已取消',
}

export default function TaskPanel({ editionId }: TaskPanelProps) {
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTask, setSelectedTask] = useState<AnalysisTask | null>(null)
  const [taskResults, setTaskResults] = useState<AnalysisResult[]>([])
  const [activeTab, setActiveTab] = useState('list')
  
  // 创建任务对话框状态
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [newTaskType, setNewTaskType] = useState('outline_extraction')
  const [creating, setCreating] = useState(false)
  
  // 执行任务状态
  const [showExecuteDialog, setShowExecuteDialog] = useState(false)
  const [executionPlan, setExecutionPlan] = useState<TaskExecutionPlan | null>(null)
  const [executing, setExecuting] = useState(false)
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null)
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  
  // 加载任务列表
  const loadTasks = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api_get_tasks_by_edition(editionId)
      setTasks(data)
    } catch (err) {
      console.error('Failed to load tasks:', err)
    } finally {
      setLoading(false)
    }
  }, [editionId])
  
  // 加载 LLM 提供商
  const loadProviders = useCallback(async () => {
    try {
      const data = await api_get_llm_providers()
      if (data.success) {
        setProviders(data.providers)
        // 设置默认 Provider
        if (data.default_provider && !selectedProvider) {
          setSelectedProvider(data.default_provider)
        }
      }
    } catch (err) {
      console.error('Failed to load providers:', err)
    }
  }, [selectedProvider])
  
  useEffect(() => {
    loadTasks()
    loadProviders()
  }, [loadTasks, loadProviders])
  
  // 创建任务
  const handleCreateTask = async () => {
    try {
      setCreating(true)
      const request: CreateTaskRequest = {
        edition_id: editionId,
        task_type: newTaskType,
        target_scope: 'full',
        target_node_ids: [],
        parameters: {},
      }
      const task = await api_create_analysis_task(request)
      setTasks([task, ...tasks])
      setShowCreateDialog(false)
      setSelectedTask(task)
      setActiveTab('execute')
    } catch (err) {
      console.error('Failed to create task:', err)
    } finally {
      setCreating(false)
    }
  }
  
  // 生成执行计划
  const handleCreatePlan = async (task: AnalysisTask) => {
    try {
      setSelectedTask(task)
      setShowExecuteDialog(true)
      const result = await api_create_task_plan(task.id, 'llm_direct')
      if (result.success && result.plan) {
        setExecutionPlan(result.plan)
      }
    } catch (err) {
      console.error('Failed to create plan:', err)
    }
  }
  
  // 执行任务（异步 + 轮询进度）
  const handleExecuteTask = async () => {
    if (!selectedTask) return
    
    try {
      setExecuting(true)
      setTaskProgress({
        task_id: selectedTask.id,
        status: 'running',
        current_step: 'starting',
        total_chunks: executionPlan?.chunks.length || 0,
        completed_chunks: 0,
      })
      
      // 使用异步执行 API 启动任务
      const startResult = await api_execute_task_async(selectedTask.id, {
        mode: 'llm_direct',
        llm_provider: selectedProvider,
        temperature: 0.3,
      })
      
      if (!startResult.success) {
        setTaskProgress(prev => prev ? { 
          ...prev, 
          status: 'failed', 
          error: startResult.error || 'Failed to start task' 
        } : null)
        setExecuting(false)
        return
      }
      
      // 开始轮询进度
      pollProgressUntilComplete(selectedTask.id)
      
    } catch (err) {
      console.error('Failed to execute task:', err)
      setTaskProgress(prev => prev ? { ...prev, status: 'failed', error: String(err) } : null)
      setExecuting(false)
    }
  }
  
  // 轮询进度直到任务完成
  const pollProgressUntilComplete = async (taskId: number) => {
    const poll = async () => {
      try {
        const result = await api_get_task_progress(taskId)
        if (result.success && result.progress) {
          setTaskProgress(result.progress)
          
          if (result.progress.status === 'running' || result.progress.status === 'pending') {
            // 继续轮询
            setTimeout(poll, 1000)
          } else if (result.progress.status === 'completed') {
            // 任务完成
            setExecuting(false)
            await loadTasks()
            // 更新选中的任务状态
            setSelectedTask(prev => prev ? { ...prev, status: 'completed' } : null)
          } else if (['failed', 'cancelled'].includes(result.progress.status)) {
            // 任务失败或取消
            setExecuting(false)
            await loadTasks()
          }
        } else {
          // 无法获取进度，继续轮询（可能任务还没初始化）
          setTimeout(poll, 1000)
        }
      } catch (err) {
        console.error('Failed to poll progress:', err)
        // 出错后继续轮询，最多重试一定次数
        setTimeout(poll, 2000)
      }
    }
    
    // 开始轮询
    poll()
  }
  
  // 加载任务结果
  const loadTaskResults = async (task: AnalysisTask) => {
    try {
      const results = await api_get_task_results(task.id)
      setTaskResults(results)
      setSelectedTask(task)
      setActiveTab('review')
    } catch (err) {
      console.error('Failed to load results:', err)
    }
  }
  
  // 审核结果
  const handleApproveResult = async (resultId: number) => {
    try {
      await api_approve_result(resultId)
      setTaskResults(prev => prev.map(r => 
        r.id === resultId ? { ...r, review_status: 'approved' } : r
      ))
    } catch (err) {
      console.error('Failed to approve result:', err)
    }
  }
  
  const handleRejectResult = async (resultId: number) => {
    try {
      await api_reject_result(resultId)
      setTaskResults(prev => prev.map(r => 
        r.id === resultId ? { ...r, review_status: 'rejected' } : r
      ))
    } catch (err) {
      console.error('Failed to reject result:', err)
    }
  }
  
  // 应用所有已批准的结果
  const handleApplyAll = async () => {
    if (!selectedTask) return
    try {
      const result = await api_apply_all_results(selectedTask.id)
      alert(`已应用 ${result.applied} 条结果，失败 ${result.failed} 条`)
      await loadTaskResults(selectedTask)
    } catch (err) {
      console.error('Failed to apply results:', err)
    }
  }
  
  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">分析任务管理</h3>
        <Button onClick={() => setShowCreateDialog(true)}>
          创建任务
        </Button>
      </div>
      
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="list">任务列表</TabsTrigger>
          <TabsTrigger value="execute" disabled={!selectedTask}>执行任务</TabsTrigger>
          <TabsTrigger value="review" disabled={!selectedTask || selectedTask.status !== 'completed'}>
            审核结果
          </TabsTrigger>
        </TabsList>
        
        {/* 任务列表 */}
        <TabsContent value="list" className="mt-4">
          {tasks.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                暂无分析任务，点击"创建任务"开始分析
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {tasks.map(task => (
                <Card key={task.id} className="hover:shadow-md transition-shadow">
                  <CardHeader className="py-3 px-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-base">
                          {TASK_TYPES.find(t => t.id === task.task_type)?.name || task.task_type}
                        </CardTitle>
                        <CardDescription className="text-sm">
                          任务 #{task.id} · 创建于 {new Date(task.created_at!).toLocaleString()}
                        </CardDescription>
                      </div>
                      <Badge className={STATUS_COLORS[task.status] || 'bg-gray-500'}>
                        {STATUS_LABELS[task.status] || task.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="py-2 px-4">
                    <div className="flex gap-2">
                      {task.status === 'pending' && (
                        <Button size="sm" onClick={() => handleCreatePlan(task)}>
                          执行任务
                        </Button>
                      )}
                      {task.status === 'completed' && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => loadTaskResults(task)}>
                            查看结果 ({task.result_count || 0})
                          </Button>
                        </>
                      )}
                      {task.status === 'failed' && (
                        <Button size="sm" variant="outline" onClick={() => handleCreatePlan(task)}>
                          重试
                        </Button>
                      )}
                    </div>
                    {task.error_message && (
                      <p className="text-sm text-red-500 mt-2">{task.error_message}</p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
        
        {/* 执行任务 */}
        <TabsContent value="execute" className="mt-4">
          {selectedTask && (
            <Card>
              <CardHeader>
                <CardTitle>
                  执行任务 #{selectedTask.id}: {TASK_TYPES.find(t => t.id === selectedTask.task_type)?.name}
                </CardTitle>
                <CardDescription>
                  配置执行参数并开始分析
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* LLM 提供商选择 */}
                <div>
                  <label className="text-sm font-medium mb-2 block">LLM 提供商</label>
                  <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                    <SelectTrigger className="w-64">
                      <SelectValue placeholder="选择 LLM 提供商" />
                    </SelectTrigger>
                    <SelectContent>
                      {providers.map(p => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name}
                          {p.description && (
                            <span className="text-muted-foreground ml-2 text-xs">
                              ({p.description})
                            </span>
                          )}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {!selectedProvider && (
                    <p className="text-sm text-muted-foreground mt-1">
                      请选择 LLM 提供商
                    </p>
                  )}
                </div>
                
                {/* 执行计划预览 */}
                {executionPlan && (
                  <div className="border rounded-lg p-4 bg-muted/50">
                    <h4 className="font-medium mb-2">执行计划</h4>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">分块数量：</span>
                        <span className="font-medium">{executionPlan.chunks.length}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">预估 Token：</span>
                        <span className="font-medium">{executionPlan.total_estimated_tokens.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">预估成本：</span>
                        <span className="font-medium">${executionPlan.estimated_cost_usd.toFixed(4)}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">模板：</span>
                        <span className="font-medium">{executionPlan.prompt_template_id}</span>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* 进度显示 */}
                {taskProgress && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>
                        {taskProgress.current_step === 'processing_chunk' 
                          ? `处理中: ${taskProgress.current_chunk_info || ''}`
                          : taskProgress.current_step}
                      </span>
                      <span>{taskProgress.completed_chunks} / {taskProgress.total_chunks}</span>
                    </div>
                    <Progress 
                      value={taskProgress.total_chunks > 0 
                        ? (taskProgress.completed_chunks / taskProgress.total_chunks) * 100 
                        : 0} 
                    />
                    {taskProgress.error && (
                      <p className="text-sm text-red-500">{taskProgress.error}</p>
                    )}
                    {taskProgress.status === 'completed' && (
                      <p className="text-sm text-green-600">任务执行完成！</p>
                    )}
                  </div>
                )}
                
                {/* 操作按钮 */}
                <div className="flex gap-2">
                  <Button 
                    onClick={handleExecuteTask}
                    disabled={executing || !executionPlan}
                  >
                    {executing ? '执行中...' : '开始执行'}
                  </Button>
                  {taskProgress?.status === 'completed' && (
                    <Button variant="outline" onClick={() => loadTaskResults(selectedTask)}>
                      查看结果
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => setActiveTab('list')}>
                    返回列表
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        
        {/* 审核结果 */}
        <TabsContent value="review" className="mt-4">
          {selectedTask && (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle>审核结果 - 任务 #{selectedTask.id}</CardTitle>
                    <CardDescription>
                      共 {taskResults.length} 条结果，
                      {taskResults.filter(r => r.review_status === 'pending').length} 条待审核
                    </CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Button 
                      size="sm"
                      onClick={handleApplyAll}
                      disabled={taskResults.filter(r => r.review_status === 'approved').length === 0}
                    >
                      应用所有已批准
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setActiveTab('list')}>
                      返回
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[500px]">
                  <div className="space-y-3">
                    {taskResults.map(result => (
                      <Card key={result.id} className="border">
                        <CardHeader className="py-2 px-4">
                          <div className="flex justify-between items-center">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-sm">
                                {result.result_type}
                              </span>
                              <Badge variant={
                                result.review_status === 'approved' ? 'default' :
                                result.review_status === 'rejected' ? 'destructive' :
                                'secondary'
                              }>
                                {result.review_status === 'approved' ? '已批准' :
                                 result.review_status === 'rejected' ? '已拒绝' :
                                 '待审核'}
                              </Badge>
                              {result.confidence && (
                                <span className="text-xs text-muted-foreground">
                                  置信度: {(result.confidence * 100).toFixed(0)}%
                                </span>
                              )}
                            </div>
                            {result.review_status === 'pending' && (
                              <div className="flex gap-1">
                                <Button 
                                  size="sm" 
                                  variant="outline"
                                  onClick={() => handleApproveResult(result.id)}
                                >
                                  批准
                                </Button>
                                <Button 
                                  size="sm" 
                                  variant="ghost"
                                  onClick={() => handleRejectResult(result.id)}
                                >
                                  拒绝
                                </Button>
                              </div>
                            )}
                          </div>
                        </CardHeader>
                        <CardContent className="py-2 px-4">
                          <pre className="text-xs bg-muted p-2 rounded overflow-x-auto max-h-40">
                            {JSON.stringify(result.result_data, null, 2)}
                          </pre>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
      
      {/* 创建任务对话框 */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建分析任务</DialogTitle>
            <DialogDescription>
              选择要执行的分析类型
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <label className="text-sm font-medium mb-2 block">任务类型</label>
            <Select value={newTaskType} onValueChange={setNewTaskType}>
              <SelectTrigger>
                <SelectValue placeholder="选择任务类型" />
              </SelectTrigger>
              <SelectContent>
                {TASK_TYPES.map(type => (
                  <SelectItem key={type.id} value={type.id}>
                    <div>
                      <div className="font-medium">{type.name}</div>
                      <div className="text-xs text-muted-foreground">{type.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowCreateDialog(false)}>
              取消
            </Button>
            <Button onClick={handleCreateTask} disabled={creating}>
              {creating ? '创建中...' : '创建任务'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      
      {/* 执行确认对话框 */}
      <Dialog open={showExecuteDialog} onOpenChange={setShowExecuteDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>确认执行任务</DialogTitle>
            <DialogDescription>
              请确认执行计划并选择 LLM 提供商
            </DialogDescription>
          </DialogHeader>
          
          {executionPlan ? (
            <div className="py-4 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-muted p-3 rounded">
                  <div className="text-muted-foreground">分块数量</div>
                  <div className="font-semibold text-lg">{executionPlan.chunks.length}</div>
                </div>
                <div className="bg-muted p-3 rounded">
                  <div className="text-muted-foreground">预估 Token</div>
                  <div className="font-semibold text-lg">{executionPlan.total_estimated_tokens.toLocaleString()}</div>
                </div>
              </div>
              
              <div>
                <label className="text-sm font-medium mb-2 block">选择 LLM</label>
                <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择 LLM 提供商" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map(p => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : (
            <div className="py-8 text-center">
              <Skeleton className="h-20 w-full" />
            </div>
          )}
          
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowExecuteDialog(false)}>
              取消
            </Button>
            <Button 
              onClick={() => {
                setShowExecuteDialog(false)
                setActiveTab('execute')
              }}
              disabled={!executionPlan}
            >
              确认并执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
