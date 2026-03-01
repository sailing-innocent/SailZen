/**
 * @file outlineExtraction.ts
 * @brief Outline Extraction API with Unified Agent Integration
 * @author sailing-innocent
 * @date 2026-03-01
 * @version 2.0
 *
 * 大纲提取 API - 集成 Unified Agent 系统
 * 支持数据库持久化、检查点恢复、WebSocket 实时进度
 */

import { get_url } from './config'
import { unifiedAgentAPI, type CreateTaskRequest, type TaskStatus } from './unifiedAgent'
import type {
  OutlineExtractionConfig,
  OutlineExtractionResult,
  OutlineExtractionProgress,
  OutlineExtractionDetailedStatus,
  ResumeTaskResponse,
  OutlineExtractionTaskSummary,
  RecoverTaskViewResponse,
  TextRangeSelection,
} from '@lib/data/analysis'

// ============================================================================
// Types
// ============================================================================

/** 大纲提取任务（Unified Agent 版本） */
export interface UnifiedOutlineExtractionTask {
  id: number
  status: TaskStatus
  progress: number
  currentPhase?: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  errorMessage?: string
  resultData?: {
    extraction_result?: OutlineExtractionResult
    checkpoint?: OutlineExtractionCheckpointInfo
  }
  config?: {
    extraction_config?: OutlineExtractionConfig
    range_selection?: TextRangeSelection
    work_title?: string
    known_characters?: string[]
  }
}

/** 检查点信息 */
export interface OutlineExtractionCheckpointInfo {
  phase: string
  progressPercent: number
  totalBatches: number
  completedBatches: number[]
  failedBatches: number[]
  currentBatch: number
  totalNodes: number
  totalTurningPoints: number
  lastError?: string
  isRecoverable: boolean
}

/** 任务恢复信息 */
export interface TaskRecoveryInfo {
  canRecover: boolean
  taskId: number
  status: TaskStatus
  progress: number
  checkpoint?: OutlineExtractionCheckpointInfo
  message: string
}

// ============================================================================
// Unified Agent Based API
// ============================================================================

const API_BASE = '/api/v1/agent-unified'

/**
 * 创建大纲提取任务（使用 Unified Agent 系统）
 */
export async function api_create_unified_outline_task(
  editionId: number,
  rangeSelection: TextRangeSelection,
  config: OutlineExtractionConfig,
  workTitle?: string,
  knownCharacters?: string[]
): Promise<UnifiedOutlineExtractionTask> {
  const request: CreateTaskRequest = {
    taskType: 'novel_analysis',
    subType: 'outline_extraction',
    editionId,
    config: {
      extraction_config: config,
      range_selection: rangeSelection,
      work_title: workTitle,
      known_characters: knownCharacters,
      checkpoint_enabled: true,
      checkpoint_interval_batches: 1,
    },
    priority: 5,
  }

  const task = await unifiedAgentAPI.createTask(request)
  
  return {
    id: task.id,
    status: task.status,
    progress: task.progress,
    currentPhase: task.currentPhase,
    createdAt: task.createdAt,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    errorMessage: task.errorMessage,
    config: {
      extraction_config: config,
      range_selection: rangeSelection,
      work_title: workTitle,
      known_characters: knownCharacters,
    },
  }
}

/**
 * 获取任务详情（包含检查点信息）
 */
export async function api_get_unified_outline_task(
  taskId: number
): Promise<UnifiedOutlineExtractionTask> {
  const task = await unifiedAgentAPI.getTask(taskId)
  
  return {
    id: task.id,
    status: task.status,
    progress: task.progress,
    currentPhase: task.currentPhase,
    createdAt: task.createdAt,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    errorMessage: task.errorMessage,
    resultData: task.resultData as UnifiedOutlineExtractionTask['resultData'],
  }
}

/**
 * 获取任务进度（包含检查点详情）
 */
export async function api_get_unified_outline_progress(
  taskId: number
): Promise<OutlineExtractionProgress & { checkpoint?: OutlineExtractionCheckpointInfo }> {
  const progress = await unifiedAgentAPI.getTaskProgress(taskId)
  
  // 从 resultData 中提取检查点信息
  const checkpoint = progress.checkpoint || 
    (progress as unknown as { checkpoint?: OutlineExtractionCheckpointInfo }).checkpoint
  
  return {
    task_id: String(taskId),
    current_step: progress.currentPhase || 'processing',
    progress_percent: progress.progress,
    message: progress.errorMessage || '',
    total_batches: progress.totalSteps,
    completed_chunks: progress.currentStep,
    checkpoint,
  } as OutlineExtractionProgress & { checkpoint?: OutlineExtractionCheckpointInfo }
}

/**
 * 获取版本的所有大纲提取任务
 */
export async function api_get_unified_outline_tasks(
  editionId: number,
  status?: TaskStatus
): Promise<UnifiedOutlineExtractionTask[]> {
  const tasks = await unifiedAgentAPI.listTasks({
    taskType: 'novel_analysis',
    subType: 'outline_extraction',
    editionId,
    status,
  })

  return tasks.map(task => ({
    id: task.id,
    status: task.status,
    progress: task.progress,
    currentPhase: task.currentPhase,
    createdAt: task.createdAt,
    startedAt: task.startedAt,
    completedAt: task.completedAt,
    errorMessage: task.errorMessage,
    resultData: task.resultData as UnifiedOutlineExtractionTask['resultData'],
  }))
}

/**
 * 恢复暂停/失败的任务
 */
export async function api_resume_unified_outline_task(
  taskId: number
): Promise<ResumeTaskResponse> {
  const baseUrl = (get_url() || '') + API_BASE
  
  const response = await fetch(`${baseUrl}/tasks/${taskId}/resume`, {
    method: 'POST',
  })
  
  if (!response.ok) {
    throw new Error(`Failed to resume task: ${response.statusText}`)
  }
  
  const data = await response.json()
  return {
    success: data.success,
    task_id: String(taskId),
    message: data.message,
    resumed_from_batch: data.resumed_from_batch || 0,
    total_batches: data.total_batches || 0,
  }
}

/**
 * 取消任务
 */
export async function api_cancel_unified_outline_task(taskId: number): Promise<boolean> {
  return await unifiedAgentAPI.cancelTask(taskId)
}

/**
 * 删除任务
 */
export async function api_delete_unified_outline_task(taskId: number): Promise<boolean> {
  return await unifiedAgentAPI.deleteTask(taskId)
}

// ============================================================================
// Legacy API Compatibility Layer
// ============================================================================

/**
 * 兼容层：创建大纲提取任务（返回旧版格式）
 * 用于平滑迁移
 */
export async function api_create_outline_extraction_task_compat(
  editionId: number,
  rangeSelection: TextRangeSelection,
  config: OutlineExtractionConfig,
  workTitle?: string,
  knownCharacters?: string[]
): Promise<{ task_id: string; status: string; message: string; created_at: string }> {
  const task = await api_create_unified_outline_task(
    editionId,
    rangeSelection,
    config,
    workTitle,
    knownCharacters
  )
  
  return {
    task_id: String(task.id),
    status: task.status,
    message: '大纲提取任务已创建',
    created_at: task.createdAt,
  }
}

/**
 * 兼容层：获取任务进度
 */
export async function api_get_outline_extraction_progress_compat(
  taskId: string
): Promise<OutlineExtractionProgress> {
  const progress = await api_get_unified_outline_progress(parseInt(taskId))
  return {
    task_id: taskId,
    current_step: progress.current_step,
    progress_percent: progress.progress_percent,
    message: progress.message,
    batch_index: progress.checkpoint?.currentBatch,
    total_batches: progress.checkpoint?.totalBatches,
    is_retrying: false,
    retry_attempt: 0,
  }
}

/**
 * 兼容层：恢复任务查看
 */
export async function api_recover_outline_task_compat(
  taskId: string
): Promise<RecoverTaskViewResponse> {
  const task = await api_get_unified_outline_task(parseInt(taskId))
  
  return {
    success: true,
    task_id: taskId,
    result: task.resultData?.extraction_result,
    message: task.resultData?.extraction_result 
      ? '任务结果已恢复' 
      : '任务正在进行中',
  }
}

// ============================================================================
// Task Recovery Utilities
// ============================================================================

/**
 * 检查是否有可恢复的任务
 */
export async function checkRecoverableTasks(
  editionId: number
): Promise<TaskRecoveryInfo[]> {
  // 获取所有非 completed/failed 状态的任务
  const tasks = await api_get_unified_outline_tasks(editionId)
  
  const recoverableStatuses: TaskStatus[] = ['pending', 'running', 'paused']
  
  return tasks
    .filter(task => recoverableStatuses.includes(task.status) || 
      (task.status === 'completed' && task.resultData?.extraction_result))
    .map(task => {
      const checkpoint = task.resultData?.checkpoint
      const isRecoverable = task.status === 'paused' || 
        task.status === 'running' ||
        (task.status === 'completed' && !!task.resultData?.extraction_result)
      
      return {
        canRecover: isRecoverable,
        taskId: task.id,
        status: task.status,
        progress: task.progress,
        checkpoint,
        message: getRecoveryMessage(task.status, checkpoint),
      }
    })
}

function getRecoveryMessage(
  status: TaskStatus, 
  checkpoint?: OutlineExtractionCheckpointInfo
): string {
  switch (status) {
    case 'running':
      return `任务正在运行中${checkpoint ? `，进度 ${checkpoint.progressPercent}%` : ''}`
    case 'paused':
      return `任务已暂停${checkpoint ? `，可从批次 ${checkpoint.currentBatch}/${checkpoint.totalBatches} 恢复` : ''}`
    case 'completed':
      return '任务已完成，可查看结果'
    default:
      return '任务可恢复'
  }
}

/**
 * 自动恢复最近的一个任务
 */
export async function autoRecoverLatestTask(
  editionId: number
): Promise<TaskRecoveryInfo | null> {
  const recoverable = await checkRecoverableTasks(editionId)
  
  if (recoverable.length === 0) return null
  
  // 按进度排序，优先恢复进行中的任务
  const sorted = recoverable.sort((a, b) => {
    // running 状态优先
    if (a.status === 'running' && b.status !== 'running') return -1
    if (b.status === 'running' && a.status !== 'running') return -1
    // 然后按进度排序
    return b.progress - a.progress
  })
  
  return sorted[0]
}

// ============================================================================
// WebSocket Integration
// ============================================================================

/**
 * 连接 WebSocket 并订阅大纲提取任务事件
 */
export function connectOutlineExtractionWebSocket(
  onProgress: (taskId: number, progress: OutlineExtractionProgress) => void,
  onComplete: (taskId: number, result: OutlineExtractionResult) => void,
  onError: (taskId: number, error: string) => void,
  onCheckpoint?: (taskId: number, checkpoint: OutlineExtractionCheckpointInfo) => void
): WebSocket {
  const ws = unifiedAgentAPI.connectRealtimeStream(
    (event) => {
      const taskId = event.taskId
      
      switch (event.eventType) {
        case 'task_progress':
          const progressData = event.data as { progress?: number; current_phase?: string }
          onProgress(taskId, {
            task_id: String(taskId),
            current_step: progressData.current_phase || 'processing',
            progress_percent: progressData.progress || 0,
            message: '',
          })
          break
          
        case 'task_completed':
          const resultData = (event.data as { result_data?: { extraction_result?: OutlineExtractionResult } })?.result_data
          if (resultData?.extraction_result) {
            onComplete(taskId, resultData.extraction_result)
          }
          break
          
        case 'task_failed':
          const errorMsg = (event.data as { error_message?: string })?.error_message || '任务失败'
          onError(taskId, errorMsg)
          break
          
        case 'task_step':
          // 检查点更新
          const stepData = event.data as { step_type?: string; meta_data?: { checkpoint?: OutlineExtractionCheckpointInfo } }
          if (stepData.step_type === 'checkpoint_saved' && stepData.meta_data?.checkpoint && onCheckpoint) {
            onCheckpoint(taskId, stepData.meta_data.checkpoint)
          }
          break
      }
    },
    (error) => {
      console.error('[OutlineExtraction] WebSocket error:', error)
    }
  )
  
  return ws
}

/**
 * 订阅特定任务的进度
 */
export function subscribeToOutlineTask(ws: WebSocket, taskId: number): void {
  unifiedAgentAPI.subscribeToTask(ws, taskId)
}

// ============================================================================
// LocalStorage Persistence
// ============================================================================

const STORAGE_KEY_PREFIX = 'outline_extraction_task_v2_'

/**
 * 保存任务 ID 到 localStorage
 */
export function saveOutlineTaskToStorage(editionId: number, taskId: number): void {
  const data = {
    taskId,
    editionId,
    savedAt: new Date().toISOString(),
  }
  localStorage.setItem(`${STORAGE_KEY_PREFIX}${editionId}`, JSON.stringify(data))
}

/**
 * 从 localStorage 获取任务 ID
 */
export function getOutlineTaskFromStorage(editionId: number): number | null {
  const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${editionId}`)
  if (!stored) return null
  
  try {
    const data = JSON.parse(stored) as { taskId: number; editionId: number; savedAt: string }
    // 检查是否过期（7天）
    const savedAt = new Date(data.savedAt)
    const now = new Date()
    const daysDiff = (now.getTime() - savedAt.getTime()) / (1000 * 60 * 60 * 24)
    
    if (daysDiff > 7) {
      localStorage.removeItem(`${STORAGE_KEY_PREFIX}${editionId}`)
      return null
    }
    
    return data.taskId
  } catch {
    return null
  }
}

/**
 * 清除 localStorage 中的任务记录
 */
export function clearOutlineTaskFromStorage(editionId: number): void {
  localStorage.removeItem(`${STORAGE_KEY_PREFIX}${editionId}`)
}

// ============================================================================
// Export
// ============================================================================

export {
  unifiedAgentAPI,
}
