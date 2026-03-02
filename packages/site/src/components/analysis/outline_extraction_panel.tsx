/**
 * @file outline_extraction_panel.tsx
 * @brief Outline Extraction Panel with Unified Agent Integration
 * @author sailing-innocent
 * @date 2026-03-01
 * @version 2.0
 *
 * 集成 Unified Agent 系统的大纲提取面板
 * 支持数据库持久化、检查点恢复、WebSocket 实时进度
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sparkles,
  Play,
  Pause,
  RotateCcw,
  Save,
  X,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Layers,
  Clock,
  Database,
} from 'lucide-react'

import { OutlineExtractionConfigPanel } from '@components/outline_extraction_config'
import { OutlineReviewPanel } from '@components/outline_review_panel'
import { useAnalysisStore } from '@lib/store/analysisStore'

import {
  api_create_unified_outline_task,
  api_get_unified_outline_task,
  api_get_unified_outline_progress,
  api_resume_unified_outline_task,
  api_cancel_unified_outline_task,
  api_delete_unified_outline_task,
  api_save_outline_result,
  checkRecoverableTasks,
  autoRecoverLatestTask,
  connectOutlineExtractionWebSocket,
  subscribeToOutlineTask,
  saveOutlineTaskToStorage,
  getOutlineTaskFromStorage,
  clearOutlineTaskFromStorage,
  type UnifiedOutlineExtractionTask,
  type TaskRecoveryInfo,
  type OutlineExtractionCheckpointInfo,
} from '@lib/api/outlineExtraction'
import { api_get_llm_providers } from '@lib/api/analysis'

import type {
  OutlineExtractionConfig,
  OutlineExtractionResult,
  OutlineExtractionProgress,
  LLMProvider,
  TextRangeSelection,
} from '@lib/data/analysis'
import type { ChapterListItem } from '@lib/data/text'

interface OutlineExtractionPanelProps {
  editionId: number
  workTitle?: string
  chapters?: ChapterListItem[]
  onComplete?: (result: OutlineExtractionResult) => void
  onSave?: () => void
  onClose?: () => void
}

// ============================================================================
// Main Component
// ============================================================================

export default function OutlineExtractionPanel({ editionId, workTitle, chapters = [], onComplete, onSave, onClose }: OutlineExtractionPanelProps) {
  // ==========================================================================
  // State
  // ==========================================================================
  
  // UI State
  const [isOpen, setIsOpen] = useState(false)
  const [showRecoveryDialog, setShowRecoveryDialog] = useState(false)
  const [recoverableTasks, setRecoverableTasks] = useState<TaskRecoveryInfo[]>([])
  
  // Config State
  const [config, setConfig] = useState<OutlineExtractionConfig>({
    granularity: 'scene',
    outline_type: 'main',
    extract_turning_points: true,
    extract_characters: true,
    max_nodes: 50,
    temperature: 0.3,
    prompt_template_id: 'outline_extraction_v2',
  })
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [defaultProvider, setDefaultProvider] = useState<string>('')
  
  // Task State
  const [currentTask, setCurrentTask] = useState<UnifiedOutlineExtractionTask | null>(null)
  const [taskId, setTaskId] = useState<number | null>(null)
  const [progress, setProgress] = useState<OutlineExtractionProgress | null>(null)
  const [checkpoint, setCheckpoint] = useState<OutlineExtractionCheckpointInfo | null>(null)
  const [result, setResult] = useState<OutlineExtractionResult | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // WebSocket Ref
  const wsRef = useRef<WebSocket | null>(null)
  
  // Global Store
  const { rangeSelection, loadStats } = useAnalysisStore()

  // ==========================================================================
  // Effects
  // ==========================================================================
  
  // Load providers on mount
  useEffect(() => {
    loadProviders()
  }, [])
  
  // Ensure default provider is set to moonshot if available
  useEffect(() => {
    if (providers.length > 0 && !config.llm_provider) {
      // Prefer moonshot as default
      const moonshotProvider = providers.find(p => p.id === 'moonshot')
      const defaultProv = moonshotProvider || providers[0]
      if (defaultProv) {
        setConfig(prev => ({ ...prev, llm_provider: defaultProv.id }))
      }
    }
  }, [providers])
  
  // Check for recoverable tasks when opening
  useEffect(() => {
    if (isOpen) {
      checkForRecoverableTasks()
    }
  }, [isOpen, editionId])
  
  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])

  // ==========================================================================
  // Data Loading
  // ==========================================================================
  
  const loadProviders = async () => {
    try {
      const data = await api_get_llm_providers()
      if (data.success) {
        setProviders(data.providers)
        if (data.default_provider) {
          setDefaultProvider(data.default_provider)
        }
      }
    } catch (err) {
      console.error('Failed to load providers:', err)
    }
  }
  
  const checkForRecoverableTasks = async () => {
    try {
      // 1. Check localStorage first
      const storedTaskId = getOutlineTaskFromStorage(editionId)
      
      if (storedTaskId) {
        // Verify task status
        const task = await api_get_unified_outline_task(storedTaskId)
        if (task && ['pending', 'running', 'paused', 'completed'].includes(task.status)) {
          setTaskId(storedTaskId)
          setCurrentTask(task)
          setProgress({
            task_id: String(storedTaskId),
            current_step: task.currentPhase || 'processing',
            progress_percent: task.progress,
            message: '',
          })
          
          // If running, reconnect WebSocket and open panel
          if (task.status === 'running') {
            setIsProcessing(true)
            setIsOpen(true)  // Open the panel to show progress
            connectWebSocket(storedTaskId)
          }
          
          // If completed, load result directly
          if (task.status === 'completed') {
            setIsProcessing(false)
            setIsOpen(true)  // Open the panel to show results
            if (task.resultData?.extraction_result) {
              setResult(task.resultData.extraction_result)
            }
          }
          
          return
        } else {
          // Task not recoverable, clear storage
          clearOutlineTaskFromStorage(editionId)
        }
      }
      
      // 2. Check for other recoverable tasks
      const tasks = await checkRecoverableTasks(editionId)
      if (tasks.length > 0) {
        setRecoverableTasks(tasks)
        setShowRecoveryDialog(true)
      }
    } catch (err) {
      console.error('Failed to check recoverable tasks:', err)
    }
  }

  // ==========================================================================
  // WebSocket
  // ==========================================================================
  
  const connectWebSocket = useCallback((targetTaskId: number) => {
    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close()
    }
    
    // Create new connection
    const ws = connectOutlineExtractionWebSocket(
      (taskId, progressData) => {
        if (taskId === targetTaskId) {
          setProgress(progressData)
        }
      },
      (taskId, resultData) => {
        if (taskId === targetTaskId) {
          setResult(resultData)
          setIsProcessing(false)
          clearOutlineTaskFromStorage(editionId)
          loadStats(editionId)
          // 调用 onComplete 回调通知父组件
          onComplete?.(resultData)
        }
      },
      (taskId, errorMsg) => {
        if (taskId === targetTaskId) {
          setError(errorMsg)
          setIsProcessing(false)
        }
      },
      (taskId, checkpointData) => {
        if (taskId === targetTaskId) {
          setCheckpoint(checkpointData)
        }
      }
    )
    
    wsRef.current = ws
    
    // Subscribe to task after connection opens
    ws.onopen = () => {
      subscribeToOutlineTask(ws, targetTaskId)
    }
  }, [editionId, loadStats, onComplete])

  // ==========================================================================
  // Task Actions
  // ==========================================================================
  
  const handleStartExtraction = async () => {
    if (!rangeSelection) {
      setError('请先选择文本范围')
      return
    }
    
    setError(null)
    setIsProcessing(true)
    setResult(null)
    
    try {
      const task = await api_create_unified_outline_task(
        editionId,
        rangeSelection,
        config,
        workTitle,
        undefined // knownCharacters
      )
      
      setTaskId(task.id)
      setCurrentTask(task)
      setProgress({
        task_id: String(task.id),
        current_step: 'initializing',
        progress_percent: 0,
        message: '任务初始化中...',
      })
      
      // Save to localStorage
      saveOutlineTaskToStorage(editionId, task.id)
      
      // Connect WebSocket for real-time updates
      connectWebSocket(task.id)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败')
      setIsProcessing(false)
    }
  }
  
  const handleResumeTask = async (recoveryInfo: TaskRecoveryInfo) => {
    setShowRecoveryDialog(false)
    setTaskId(recoveryInfo.taskId)
    setError(null)
    
    try {
      // Load current task state
      const task = await api_get_unified_outline_task(recoveryInfo.taskId)
      setCurrentTask(task)
      
      // If task is completed, load result directly
      if (task.status === 'completed') {
        setIsProcessing(false)
        setIsOpen(true)  // Open the panel to show results
        if (task.resultData?.extraction_result) {
          setResult(task.resultData.extraction_result)
          setProgress({
            task_id: String(recoveryInfo.taskId),
            current_step: 'completed',
            progress_percent: 100,
            message: '任务已完成',
          })
        }
        // Save to localStorage for reference
        saveOutlineTaskToStorage(editionId, recoveryInfo.taskId)
        return
      }
      
      // For pending/running/paused/failed tasks
      setIsProcessing(true)
      setIsOpen(true)  // Open the panel
      
      // If task is paused or failed, resume it
      if (task.status === 'paused' || task.status === 'failed') {
        await api_resume_unified_outline_task(recoveryInfo.taskId)
      }
      
      // Save to localStorage
      saveOutlineTaskToStorage(editionId, recoveryInfo.taskId)
      
      // Connect WebSocket for real-time updates
      connectWebSocket(recoveryInfo.taskId)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '恢复任务失败')
      setIsProcessing(false)
    }
  }
  
  const handleCancelTask = async () => {
    if (!taskId) return
    
    try {
      await api_cancel_unified_outline_task(taskId)
      setIsProcessing(false)
      clearOutlineTaskFromStorage(editionId)
    } catch (err) {
      console.error('Failed to cancel task:', err)
    }
  }
  
  const handleDismissTask = async () => {
    if (!taskId) {
      setIsOpen(false)
      return
    }
    
    if (confirm('确定要关闭此任务吗？未保存的结果将被丢弃。')) {
      try {
        await api_delete_unified_outline_task(taskId)
        clearOutlineTaskFromStorage(editionId)
        
        // Reset state
        setTaskId(null)
        setCurrentTask(null)
        setProgress(null)
        setCheckpoint(null)
        setResult(null)
        setIsProcessing(false)
        setIsOpen(false)
      } catch (err) {
        console.error('Failed to dismiss task:', err)
      }
    }
  }
  
  const handleSaveResult = async () => {
    if (!result || !taskId) return
    
    // 过滤出已批准的节点
    const approvedNodes = result.nodes.filter(n => n.review_status === 'approved')
    const rejectedCount = result.nodes.filter(n => n.review_status === 'rejected').length
    
    if (approvedNodes.length === 0) {
      alert('没有已批准的节点可保存。请先批准至少一个节点。')
      return
    }
    
    // 确认保存
    if (rejectedCount > 0) {
      const confirmed = confirm(`您拒绝了 ${rejectedCount} 个节点，批准了 ${approvedNodes.length} 个节点。确定只保存批准的节点吗？`)
      if (!confirmed) return
    }
    
    try {
      // 调用 API 保存批准的节点
      const saveResult = await api_save_outline_result(
        taskId, 
        approvedNodes.map(n => n.id)
      )
      
      if (saveResult.success) {
        alert(`保存成功！创建了 ${saveResult.nodes_created} 个节点${saveResult.events_created ? `，${saveResult.events_created} 个事件` : ''}。`)
      } else {
        alert(`保存失败：${saveResult.message}`)
        return
      }
      
      // 刷新统计
      loadStats(editionId)
      
      // Clear storage
      clearOutlineTaskFromStorage(editionId)
      
      // 调用 onSave 回调通知父组件
      onSave?.()
      
      // Reset and close
      setTaskId(null)
      setCurrentTask(null)
      setProgress(null)
      setCheckpoint(null)
      setResult(null)
      setIsOpen(false)
      
      // 调用 onClose 回调
      onClose?.()
    } catch (err) {
      console.error('Failed to save result:', err)
      alert(`保存失败：${err instanceof Error ? err.message : '未知错误'}`)
    }
  }

  // 批准选中的节点
  const handleApproveNodes = (nodeIds: string[]) => {
    if (!result) return
    
    // 更新节点的批准状态
    const updatedNodes = result.nodes.map(node => 
      nodeIds.includes(node.id) 
        ? { ...node, review_status: 'approved' as const }
        : node
    )
    
    setResult({
      ...result,
      nodes: updatedNodes
    })
  }

  // 拒绝选中的节点
  const handleRejectNodes = (nodeIds: string[]) => {
    if (!result) return
    
    // 更新节点的拒绝状态
    const updatedNodes = result.nodes.map(node => 
      nodeIds.includes(node.id) 
        ? { ...node, review_status: 'rejected' as const }
        : node
    )
    
    setResult({
      ...result,
      nodes: updatedNodes
    })
  }

  // ==========================================================================
  // Render Helpers
  // ==========================================================================

  /**
   * 根据 rangeSelection 和 chapters 计算范围显示文本
   * 直接使用本地 chapters 数据，不依赖后端返回的 selected_chapters
   */
  const getRangeDisplayText = (selection: TextRangeSelection | null): string => {
    if (!selection) return ''

    const getChapterDisplay = (chapter: ChapterListItem | undefined): string => {
      if (!chapter) return ''
      const parts: string[] = []
      if (chapter.label) parts.push(chapter.label)
      if (chapter.title) parts.push(chapter.title)
      return parts.join(' ') || `第 ${chapter.sort_index + 1} 章`
    }

    switch (selection.mode) {
      case 'full_edition':
        return '整部作品'

      case 'single_chapter': {
        if (selection.chapter_index === undefined) return '单章选择'
        const chapter = chapters.find(ch => ch.sort_index === selection.chapter_index)
        return getChapterDisplay(chapter) || `第 ${selection.chapter_index + 1} 章`
      }

      case 'chapter_range': {
        if (selection.start_index === undefined || selection.end_index === undefined) {
          return '章节范围选择'
        }
        const startChapter = chapters.find(ch => ch.sort_index === selection.start_index)
        const endChapter = chapters.find(ch => ch.sort_index === selection.end_index)
        const startText = getChapterDisplay(startChapter) || `第 ${selection.start_index + 1} 章`
        const endText = getChapterDisplay(endChapter) || `第 ${selection.end_index + 1} 章`
        return `${startText} 到 ${endText}`
      }

      case 'multi_chapter': {
        const count = selection.chapter_indices?.length || 0
        return `${count} 个章节`
      }

      case 'current_to_end': {
        if (selection.start_index === undefined) return '从当前到结尾'
        const startChapter = chapters.find(ch => ch.sort_index === selection.start_index)
        const startText = getChapterDisplay(startChapter) || `第 ${selection.start_index + 1} 章`
        return `从 ${startText} 到结尾`
      }

      case 'custom_range':
        return '自定义范围'

      default:
        return ''
    }
  }

  const getStatusBadge = (status?: string) => {
    const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: React.ReactNode }> = {
      pending: { label: '等待中', variant: 'secondary', icon: <Clock className="w-3 h-3" /> },
      running: { label: '运行中', variant: 'default', icon: <Loader2 className="w-3 h-3 animate-spin" /> },
      paused: { label: '已暂停', variant: 'secondary', icon: <Pause className="w-3 h-3" /> },
      completed: { label: '已完成', variant: 'default', icon: <CheckCircle2 className="w-3 h-3" /> },
      failed: { label: '失败', variant: 'destructive', icon: <AlertCircle className="w-3 h-3" /> },
      cancelled: { label: '已取消', variant: 'outline', icon: <X className="w-3 h-3" /> },
    }
    
    const config = statusConfig[status || 'pending']
    
    if (!config) {
      return <Badge variant="outline">{status || 'unknown'}</Badge>
    }
    
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        {config.icon}
        {config.label}
      </Badge>
    )
  }

  // ==========================================================================
  // Render
  // ==========================================================================
  
  if (!isOpen) {
    return (
      <Button variant="outline" onClick={() => setIsOpen(true)}>
        <Sparkles className="w-4 h-4 mr-2" />
        AI 大纲提取
      </Button>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-primary" />
          <h3 className="text-lg font-semibold">AI 大纲提取</h3>
          {currentTask && getStatusBadge(currentTask.status)}
        </div>
        <div className="flex items-center gap-2">
          {taskId && !isProcessing && (
            <Button 
              variant="ghost" 
              size="sm"
              className="text-red-500 hover:text-red-700"
              onClick={handleDismissTask}
            >
              <X className="w-4 h-4 mr-1" />
              关闭任务
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setIsOpen(false)}>
            返回
          </Button>
        </div>
      </div>

      {/* Range Selection Info */}
      <Alert variant={rangeSelection ? "default" : "destructive"}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {rangeSelection ? (
            <span>
              当前选择: <strong>{getRangeDisplayText(rangeSelection)}</strong>
              {' '}(请在左侧"任务"标签页中更改范围选择)
            </span>
          ) : (
            <span>未选择文本范围，请先切换到"任务"标签页选择范围</span>
          )}
        </AlertDescription>
      </Alert>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left Panel: Config */}
        <OutlineExtractionConfigPanel
          config={config}
          onConfigChange={setConfig}
          onStart={handleStartExtraction}
          isProcessing={isProcessing}
          providers={providers}
          defaultProvider={defaultProvider}
          disabled={!!taskId}
        />

        {/* Right Panel: Progress/Result */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Database className="w-4 h-4" />
              提取进度
            </CardTitle>
            <CardDescription>
              {isProcessing 
                ? '正在分析文本，请稍候...' 
                : result 
                  ? '提取完成，请查看结果' 
                  : '准备开始提取'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Progress Display */}
            {progress && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">{progress.current_step}</span>
                  <span className="font-medium">{progress.progress_percent}%</span>
                </div>
                <Progress value={progress.progress_percent} />
              </div>
            )}

            {/* Checkpoint Info */}
            {checkpoint && (
              <div className="bg-muted rounded-lg p-3 space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Layers className="w-4 h-4 text-muted-foreground" />
                  <span className="text-muted-foreground">批次进度:</span>
                  <span className="font-medium">
                    {checkpoint.completedBatches.length} / {checkpoint.totalBatches}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-muted-foreground" />
                  <span className="text-muted-foreground">已提取节点:</span>
                  <span className="font-medium">{checkpoint.totalNodes}</span>
                </div>
                {checkpoint.failedBatches.length > 0 && (
                  <div className="flex items-center gap-2 text-sm text-yellow-600">
                    <AlertCircle className="w-4 h-4" />
                    <span>失败批次: {checkpoint.failedBatches.length}</span>
                  </div>
                )}
              </div>
            )}

            {/* Result Preview */}
            {result && (
              <div className="space-y-2">
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    共提取 {result.nodes.length} 个节点
                    {result.turning_points && `, ${result.turning_points.length} 个转折点`}
                  </span>
                  <Button size="sm" onClick={handleSaveResult}>
                    <Save className="w-4 h-4 mr-1" />
                    保存结果
                  </Button>
                </div>
              </div>
            )}

            {/* Cancel Button */}
            {isProcessing && (
              <Button 
                variant="outline" 
                className="w-full"
                onClick={handleCancelTask}
              >
                <X className="w-4 h-4 mr-1" />
                取消任务
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Result Review Panel */}
      {result && (
        <OutlineReviewPanel
          result={result}
          progress={progress}
          isProcessing={isProcessing}
          selectedNodeIds={result.nodes.filter(n => n.review_status !== 'rejected').map(n => n.id)}
          onSelectionChange={() => {}}
          onApprove={handleApproveNodes}
          onReject={handleRejectNodes}
          onSave={handleSaveResult}
          onRetry={() => {
            setResult(null)
            setProgress(null)
            setCheckpoint(null)
            setTaskId(null)
            setCurrentTask(null)
          }}
        />
      )}

      {/* Recovery Dialog */}
      <Dialog open={showRecoveryDialog} onOpenChange={setShowRecoveryDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>发现可恢复的任务</DialogTitle>
            <DialogDescription>
              检测到该版本有以下历史提取任务，您可以选择恢复或开始新任务
            </DialogDescription>
          </DialogHeader>
          
          <ScrollArea className="max-h-[300px]">
            <div className="space-y-3 py-4">
              {recoverableTasks.map((task) => (
                <div 
                  key={task.taskId} 
                  className={`border rounded-lg p-4 ${
                    task.status === 'running' ? 'bg-blue-50 border-blue-200' :
                    task.status === 'completed' ? 'bg-green-50 border-green-200' :
                    'bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {getStatusBadge(task.status)}
                        <span className="text-sm font-medium">任务 #{task.taskId}</span>
                      </div>
                      <p className="text-xs text-muted-foreground">{task.message}</p>
                      {task.checkpoint && (
                        <p className="text-xs text-muted-foreground">
                          进度: {task.checkpoint.progressPercent}% | 
                          批次: {task.checkpoint.completedBatches.length}/{task.checkpoint.totalBatches}
                        </p>
                      )}
                    </div>
                    <Button 
                      size="sm" 
                      onClick={() => handleResumeTask(task)}
                      variant={task.status === 'completed' ? 'outline' : 'default'}
                    >
                      {task.status === 'completed' ? '查看结果' : '恢复'}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRecoveryDialog(false)}>
              <Play className="w-4 h-4 mr-1" />
              开始新任务
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
