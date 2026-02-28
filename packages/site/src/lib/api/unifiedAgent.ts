/**
 * @file unifiedAgent.ts
 * @brief Unified Agent API Client
 * @author sailing-innocent
 * @date 2026-02-28
 * @version 1.0
 *
 * 统一 Agent API 客户端
 * 对接后端新的统一 Agent 系统 (/api/v1/agent-unified)
 */

import { get_url } from './config'

// ============================================================================
// Enums & Types
// ============================================================================

export type TaskType = 'novel_analysis' | 'code' | 'writing' | 'general'

export type TaskSubType =
  // novel_analysis subtypes
  | 'outline_extraction'
  | 'character_detection'
  | 'setting_extraction'
  | 'relation_analysis'
  | 'attribute_extraction'
  // code subtypes
  | 'code_review'
  | 'code_generation'
  | 'code_refactor'
  | 'bug_fix'
  // writing subtypes
  | 'text_completion'
  | 'text_polish'
  | 'translation'
  | 'summarization'
  // general subtypes
  | 'chat'
  | 'qa'
  | 'brainstorm'

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type AgentEventType =
  | 'task_created'
  | 'task_started'
  | 'task_progress'
  | 'task_step'
  | 'task_completed'
  | 'task_failed'
  | 'task_cancelled'
  | 'cost_update'

// ============================================================================
// Data Interfaces
// ============================================================================

export interface UnifiedTask {
  id: number
  taskType: TaskType
  subType?: TaskSubType | string
  status: TaskStatus
  progress: number
  currentPhase?: string
  priority: number
  estimatedTokens?: number
  actualTokens: number
  estimatedCost?: number
  actualCost: number
  createdAt: string
  startedAt?: string
  completedAt?: string
  cancelledAt?: string
  errorMessage?: string
  resultData?: Record<string, unknown>
}

export interface TaskProgress {
  taskId: number
  status: TaskStatus
  progress: number
  currentPhase?: string
  currentStep?: number
  totalSteps?: number
  estimatedRemainingSeconds?: number
  errorMessage?: string
  actualTokens: number
  actualCost: number
}

export interface TaskStep {
  id: number
  taskId: number
  stepType: 'llm_call' | 'data_processing' | 'verification' | 'error'
  stepName: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  llmProvider?: string
  llmModel?: string
  promptTokens: number
  completionTokens: number
  totalTokens: number
  cost: number
  startedAt?: string
  completedAt?: string
}

export interface AgentEvent {
  eventType: AgentEventType
  taskId: number
  timestamp: string
  data: Record<string, unknown>
}

export interface AgentInfo {
  agentType: string
  name: string
  description: string
  supportedTaskTypes: TaskType[]
  supportedSubTypes: string[]
  capabilities: string[]
  defaultConfig: Record<string, unknown>
}

export interface CostEstimate {
  estimatedTokens: number
  estimatedCost: number
  estimatedTimeSeconds: number
  confidence: number // 0-1
  breakdown: {
    promptTokens: number
    completionTokens: number
    llmCost: number
    processingCost: number
  }
}

export interface SchedulerStatus {
  isRunning: boolean
  stats: {
    totalTasks: number
    pendingTasks: number
    runningTasks: number
    completedTasks: number
    failedTasks: number
    cancelledTasks: number
    totalTokensConsumed: number
    totalCost: number
  }
}

export interface LLMProviderInfo {
  name: string
  displayName: string
  defaultModel: string
  availableModels: string[]
  description: string
}

export interface LLMConfig {
  providers: LLMProviderInfo[]
  defaultProvider: string
  recommendations: Record<string, {
    provider: string
    model: string
    description: string
  }>
}

// ============================================================================
// Request Interfaces
// ============================================================================

export interface CreateTaskRequest {
  taskType: TaskType
  subType?: TaskSubType | string
  editionId?: number
  targetNodeIds?: number[]
  targetScope?: string
  llmProvider?: string
  llmModel?: string
  promptTemplateId?: string
  priority?: number
  config?: Record<string, unknown>
}

export interface TaskFilter {
  status?: TaskStatus
  taskType?: TaskType
  subType?: string
  editionId?: number
  skip?: number
  limit?: number
}

// ============================================================================
// WebSocket Types
// ============================================================================

export type WebSocketMessageType =
  | 'subscribe'
  | 'unsubscribe'
  | 'subscribe_task'
  | 'unsubscribe_task'
  | 'ping'
  | 'pong'

export interface WebSocketMessage {
  type: WebSocketMessageType
  taskId?: number
  timestamp?: string
}

// ============================================================================
// Unified Agent API Client
// ============================================================================

const API_BASE = '/api/v1/agent-unified'

export class UnifiedAgentAPI {
  private baseUrl: string

  constructor() {
    this.baseUrl = (get_url() || '') + API_BASE
  }

  // --------------------------------------------------------------------------
  // Task Management APIs
  // --------------------------------------------------------------------------

  /**
   * 创建新任务
   */
  async createTask(request: CreateTaskRequest): Promise<UnifiedTask> {
    const res = await fetch(`${this.baseUrl}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_type: request.taskType,
        sub_type: request.subType,
        edition_id: request.editionId,
        target_node_ids: request.targetNodeIds,
        target_scope: request.targetScope,
        llm_provider: request.llmProvider,
        llm_model: request.llmModel,
        prompt_template_id: request.promptTemplateId,
        priority: request.priority ?? 5,
        config: request.config ?? {},
      }),
    })
    if (!res.ok) throw new Error(`Failed to create task: ${res.statusText}`)
    const data = await res.json()
    return this._transformTaskResponse(data)
  }

  /**
   * 获取任务列表
   */
  async listTasks(filter: TaskFilter = {}): Promise<UnifiedTask[]> {
    const query = new URLSearchParams()
    if (filter.status) query.append('status', filter.status)
    if (filter.taskType) query.append('task_type', filter.taskType)
    if (filter.subType) query.append('sub_type', filter.subType)
    if (filter.editionId !== undefined) query.append('edition_id', String(filter.editionId))
    if (filter.skip !== undefined) query.append('skip', String(filter.skip))
    if (filter.limit !== undefined) query.append('limit', String(filter.limit))

    const res = await fetch(`${this.baseUrl}/tasks?${query}`)
    if (!res.ok) throw new Error(`Failed to list tasks: ${res.statusText}`)
    const data = await res.json()
    return Array.isArray(data) ? data.map((t) => this._transformTaskResponse(t)) : []
  }

  /**
   * 获取任务详情
   */
  async getTask(taskId: number): Promise<UnifiedTask> {
    const res = await fetch(`${this.baseUrl}/tasks/${taskId}`)
    if (!res.ok) throw new Error(`Failed to get task: ${res.statusText}`)
    const data = await res.json()
    return this._transformTaskResponse(data)
  }

  /**
   * 获取任务进度
   */
  async getTaskProgress(taskId: number): Promise<TaskProgress> {
    const res = await fetch(`${this.baseUrl}/tasks/${taskId}/progress`)
    if (!res.ok) throw new Error(`Failed to get task progress: ${res.statusText}`)
    const data = await res.json()
    return this._transformProgressResponse(data)
  }

  /**
   * 取消任务
   */
  async cancelTask(taskId: number): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/tasks/${taskId}/cancel`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed to cancel task: ${res.statusText}`)
    const data = await res.json()
    return data.success === true
  }

  /**
   * 删除任务
   */
  async deleteTask(taskId: number): Promise<boolean> {
    const res = await fetch(`${this.baseUrl}/tasks/${taskId}`, { method: 'DELETE' })
    if (!res.ok) throw new Error(`Failed to delete task: ${res.statusText}`)
    const data = await res.json()
    return data.success === true
  }

  // --------------------------------------------------------------------------
  // Agent Info APIs
  // --------------------------------------------------------------------------

  /**
   * 获取所有可用的 Agent 列表
   */
  async listAgents(): Promise<AgentInfo[]> {
    const res = await fetch(`${this.baseUrl}/agents`)
    if (!res.ok) throw new Error(`Failed to list agents: ${res.statusText}`)
    const data = await res.json()
    return Array.isArray(data) ? data.map((a) => this._transformAgentInfo(a)) : []
  }

  /**
   * 获取 Agent 详细信息
   */
  async getAgentInfo(agentType: string): Promise<AgentInfo> {
    const res = await fetch(`${this.baseUrl}/agents/${agentType}`)
    if (!res.ok) throw new Error(`Failed to get agent info: ${res.statusText}`)
    const data = await res.json()
    return this._transformAgentInfo(data)
  }

  /**
   * 预估任务成本
   */
  async estimateTaskCost(agentType: string, request: CreateTaskRequest): Promise<CostEstimate> {
    const res = await fetch(`${this.baseUrl}/agents/${agentType}/estimate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_type: request.taskType,
        sub_type: request.subType,
        edition_id: request.editionId,
        target_node_ids: request.targetNodeIds,
        llm_provider: request.llmProvider,
        llm_model: request.llmModel,
        config: request.config ?? {},
      }),
    })
    if (!res.ok) throw new Error(`Failed to estimate cost: ${res.statusText}`)
    const data = await res.json()
    return this._transformCostEstimate(data)
  }

  /**
   * 获取 LLM 配置信息
   */
  async getLLMConfig(): Promise<LLMConfig> {
    const res = await fetch(`${this.baseUrl}/agents/config/llm`)
    if (!res.ok) throw new Error(`Failed to get LLM config: ${res.statusText}`)
    return await res.json()
  }

  // --------------------------------------------------------------------------
  // Scheduler APIs
  // --------------------------------------------------------------------------

  /**
   * 获取调度器状态
   */
  async getSchedulerStatus(): Promise<SchedulerStatus> {
    const res = await fetch(`${this.baseUrl}/scheduler/status`)
    if (!res.ok) throw new Error(`Failed to get scheduler status: ${res.statusText}`)
    const data = await res.json()
    return this._transformSchedulerStatus(data)
  }

  /**
   * 启动调度器
   */
  async startScheduler(): Promise<SchedulerStatus> {
    const res = await fetch(`${this.baseUrl}/scheduler/start`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed to start scheduler: ${res.statusText}`)
    const data = await res.json()
    // 成功后获取最新状态
    return this.getSchedulerStatus()
  }

  /**
   * 停止调度器
   */
  async stopScheduler(): Promise<SchedulerStatus> {
    const res = await fetch(`${this.baseUrl}/scheduler/stop`, { method: 'POST' })
    if (!res.ok) throw new Error(`Failed to stop scheduler: ${res.statusText}`)
    const data = await res.json()
    // 成功后获取最新状态
    return this.getSchedulerStatus()
  }

  // --------------------------------------------------------------------------
  // WebSocket
  // --------------------------------------------------------------------------

  /**
   * 连接 WebSocket 实时流
   * @param onEvent 事件回调
   * @param onError 错误回调
   * @param onOpen 连接成功回调
   * @param onClose 连接关闭回调
   * @returns WebSocket 实例
   */
  connectRealtimeStream(
    onEvent: (event: AgentEvent) => void,
    onError?: (error: Event) => void,
    onOpen?: () => void,
    onClose?: () => void
  ): WebSocket {
    // Build WebSocket URL
    let wsUrl: string
    if (this.baseUrl.startsWith('http')) {
      wsUrl = this.baseUrl.replace(/^http/, 'ws') + '/ws/tasks'
    } else {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      wsUrl = `${protocol}//${host}${this.baseUrl}/ws/tasks`
    }

    console.log('[UnifiedAgentAPI] Connecting to WebSocket:', wsUrl)
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[UnifiedAgentAPI] WebSocket connected')
      // 发送订阅消息订阅所有任务事件
      const subscribeMsg: WebSocketMessage = {
        type: 'subscribe',
        timestamp: new Date().toISOString(),
      }
      ws.send(JSON.stringify(subscribeMsg))
      onOpen?.()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const agentEvent = this._transformAgentEvent(data)
        onEvent(agentEvent)
      } catch (e) {
        console.error('[UnifiedAgentAPI] Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      if (ws.readyState !== WebSocket.CLOSED && ws.readyState !== WebSocket.CLOSING) {
        console.error('[UnifiedAgentAPI] WebSocket error:', error)
        onError?.(error)
      }
    }

    ws.onclose = () => {
      console.log('[UnifiedAgentAPI] WebSocket connection closed')
      onClose?.()
    }

    return ws
  }

  /**
   * 订阅特定任务的事件
   */
  subscribeToTask(ws: WebSocket, taskId: number): void {
    if (ws.readyState === WebSocket.OPEN) {
      const msg: WebSocketMessage = {
        type: 'subscribe_task',
        taskId,
        timestamp: new Date().toISOString(),
      }
      ws.send(JSON.stringify(msg))
    }
  }

  /**
   * 取消订阅特定任务的事件
   */
  unsubscribeFromTask(ws: WebSocket, taskId: number): void {
    if (ws.readyState === WebSocket.OPEN) {
      const msg: WebSocketMessage = {
        type: 'unsubscribe_task',
        taskId,
        timestamp: new Date().toISOString(),
      }
      ws.send(JSON.stringify(msg))
    }
  }

  // --------------------------------------------------------------------------
  // Private Transform Methods
  // --------------------------------------------------------------------------

  private _transformTaskResponse(data: Record<string, unknown>): UnifiedTask {
    return {
      id: data.id as number,
      taskType: data.task_type as TaskType,
      subType: data.sub_type as TaskSubType | undefined,
      status: data.status as TaskStatus,
      progress: data.progress as number,
      currentPhase: data.current_phase as string | undefined,
      priority: data.priority as number,
      estimatedTokens: data.estimated_tokens as number | undefined,
      actualTokens: data.actual_tokens as number,
      estimatedCost: data.estimated_cost as number | undefined,
      actualCost: data.actual_cost as number,
      createdAt: data.created_at as string,
      startedAt: data.started_at as string | undefined,
      completedAt: data.completed_at as string | undefined,
      cancelledAt: data.cancelled_at as string | undefined,
      errorMessage: data.error_message as string | undefined,
      resultData: data.result_data as Record<string, unknown> | undefined,
    }
  }

  private _transformProgressResponse(data: Record<string, unknown>): TaskProgress {
    return {
      taskId: data.task_id as number,
      status: data.status as TaskStatus,
      progress: data.progress as number,
      currentPhase: data.current_phase as string | undefined,
      currentStep: data.current_step as number | undefined,
      totalSteps: data.total_steps as number | undefined,
      estimatedRemainingSeconds: data.estimated_remaining_seconds as number | undefined,
      errorMessage: data.error_message as string | undefined,
      actualTokens: data.actual_tokens as number,
      actualCost: data.actual_cost as number,
    }
  }

  private _transformAgentInfo(data: Record<string, unknown>): AgentInfo {
    return {
      agentType: data.agent_type as string,
      name: data.name as string,
      description: data.description as string,
      supportedTaskTypes: data.supported_task_types as TaskType[],
      supportedSubTypes: data.supported_sub_types as string[],
      capabilities: data.capabilities as string[],
      defaultConfig: data.default_config as Record<string, unknown>,
    }
  }

  private _transformCostEstimate(data: Record<string, unknown>): CostEstimate {
    return {
      estimatedTokens: data.estimated_tokens as number,
      estimatedCost: data.estimated_cost as number,
      estimatedTimeSeconds: data.estimated_time_seconds as number,
      confidence: data.confidence as number,
      breakdown: data.breakdown as {
        promptTokens: number
        completionTokens: number
        llmCost: number
        processingCost: number
      },
    }
  }

  private _transformSchedulerStatus(data: Record<string, unknown>): SchedulerStatus {
    return {
      isRunning: data.is_running as boolean,
      stats: {
        totalTasks: data.stats?.total_tasks as number,
        pendingTasks: data.stats?.pending_tasks as number,
        runningTasks: data.stats?.running_tasks as number,
        completedTasks: data.stats?.completed_tasks as number,
        failedTasks: data.stats?.failed_tasks as number,
        cancelledTasks: data.stats?.cancelled_tasks as number,
        totalTokensConsumed: data.stats?.total_tokens_consumed as number,
        totalCost: data.stats?.total_cost as number,
      },
    }
  }

  private _transformAgentEvent(data: Record<string, unknown>): AgentEvent {
    return {
      eventType: data.event_type as AgentEventType,
      taskId: data.task_id as number,
      timestamp: data.timestamp as string,
      data: (data.data as Record<string, unknown>) ?? {},
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

export const unifiedAgentAPI = new UnifiedAgentAPI()

// ============================================================================
// Backward Compatibility Helpers
// ============================================================================

/**
 * 将旧的 AnalysisTask 状态映射到新的 TaskStatus
 */
export function mapAnalysisStatusToUnified(status: string): TaskStatus {
  const statusMap: Record<string, TaskStatus> = {
    pending: 'pending',
    running: 'running',
    completed: 'completed',
    failed: 'failed',
    cancelled: 'cancelled',
  }
  return statusMap[status] ?? 'pending'
}

/**
 * 将旧的 AnalysisTaskType 映射到新的 TaskSubType
 */
export function mapAnalysisTypeToUnified(taskType: string): TaskSubType {
  const typeMap: Record<string, TaskSubType> = {
    outline_extraction: 'outline_extraction',
    character_detection: 'character_detection',
    setting_extraction: 'setting_extraction',
    relation_analysis: 'relation_analysis',
    attribute_extraction: 'attribute_extraction',
  }
  return typeMap[taskType] ?? 'chat'
}

/**
 * 创建小说分析任务的便捷方法
 */
export function createNovelAnalysisTask(
  editionId: number,
  subType: TaskSubType,
  targetNodeIds?: number[],
  options?: Partial<Omit<CreateTaskRequest, 'taskType' | 'editionId' | 'subType' | 'targetNodeIds'>>
): CreateTaskRequest {
  return {
    taskType: 'novel_analysis',
    subType,
    editionId,
    targetNodeIds,
    ...options,
  }
}

/**
 * 创建代码辅助任务的便捷方法
 */
export function createCodeTask(
  subType: Extract<TaskSubType, 'code_review' | 'code_generation' | 'code_refactor' | 'bug_fix'>,
  config?: Record<string, unknown>,
  options?: Partial<Omit<CreateTaskRequest, 'taskType' | 'subType' | 'config'>>
): CreateTaskRequest {
  return {
    taskType: 'code',
    subType,
    config,
    ...options,
  }
}

/**
 * 创建写作辅助任务的便捷方法
 */
export function createWritingTask(
  subType: Extract<TaskSubType, 'text_completion' | 'text_polish' | 'translation' | 'summarization'>,
  config?: Record<string, unknown>,
  options?: Partial<Omit<CreateTaskRequest, 'taskType' | 'subType' | 'config'>>
): CreateTaskRequest {
  return {
    taskType: 'writing',
    subType,
    config,
    ...options,
  }
}

/**
 * 创建通用对话任务的便捷方法
 */
export function createGeneralTask(
  content: string,
  options?: Partial<Omit<CreateTaskRequest, 'taskType' | 'config'>>
): CreateTaskRequest {
  return {
    taskType: 'general',
    subType: 'chat',
    config: { content },
    ...options,
  }
}
