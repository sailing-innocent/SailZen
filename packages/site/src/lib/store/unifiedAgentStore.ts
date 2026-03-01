/**
 * @file unifiedAgentStore.ts
 * @brief Unified Agent Store
 * @author sailing-innocent
 * @date 2026-02-28
 * @version 1.0
 *
 * 统一 Agent Store - 使用 Zustand 管理统一 Agent 状态
 */

import React from 'react'
import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import {
  unifiedAgentAPI,
  type UnifiedTask,
  type TaskProgress,
  type TaskStep,
  type AgentEvent,
  type AgentInfo,
  type SchedulerStatus,
  type CreateTaskRequest,
  type TaskFilter,
  type CostEstimate,
  type TaskType,
  type TaskSubType,
} from '@/lib/api/unifiedAgent'

// ============================================================================
// Types
// ============================================================================

interface UnifiedAgentState {
  // Data
  tasks: UnifiedTask[]
  currentTask: UnifiedTask | null
  currentTaskProgress: TaskProgress | null
  currentTaskSteps: TaskStep[]
  agents: AgentInfo[]
  schedulerStatus: SchedulerStatus | null

  // UI State
  isLoading: boolean
  isCreatingTask: boolean
  error: string | null
  wsConnection: WebSocket | null
  wsConnected: boolean

  // Feature Flags
  useUnifiedAPI: boolean // 控制是否使用新的统一 API

  // Filters
  taskFilter: TaskFilter

  // Actions - Tasks
  createTask: (request: CreateTaskRequest) => Promise<UnifiedTask | null>
  loadTasks: (filter?: TaskFilter) => Promise<void>
  loadTask: (taskId: number) => Promise<void>
  loadTaskProgress: (taskId: number) => Promise<void>
  cancelTask: (taskId: number) => Promise<boolean>
  deleteTask: (taskId: number) => Promise<boolean>
  clearCurrentTask: () => void

  // Actions - Agents
  loadAgents: () => Promise<void>
  estimateTaskCost: (agentType: string, request: CreateTaskRequest) => Promise<CostEstimate | null>

  // Actions - Scheduler
  loadSchedulerStatus: () => Promise<void>
  startScheduler: () => Promise<void>
  stopScheduler: () => Promise<void>

  // Actions - WebSocket
  connectRealtimeUpdates: () => void
  disconnectRealtimeUpdates: () => void
  subscribeToTask: (taskId: number) => void
  unsubscribeFromTask: (taskId: number) => void

  // Actions - Event Handling
  handleAgentEvent: (event: AgentEvent) => void

  // Actions - Filters
  setTaskFilter: (filter: Partial<TaskFilter>) => void
  clearTaskFilter: () => void

  // Actions - Feature Flags
  setUseUnifiedAPI: (enabled: boolean) => void

  // Actions - Utils
  clearError: () => void
  reset: () => void
}

// ============================================================================
// Initial State
// ============================================================================

const initialState = {
  tasks: [],
  currentTask: null,
  currentTaskProgress: null,
  currentTaskSteps: [],
  agents: [],
  schedulerStatus: null,
  isLoading: false,
  isCreatingTask: false,
  error: null,
  wsConnection: null,
  wsConnected: false,
  useUnifiedAPI: true,
  taskFilter: {
    status: undefined,
    taskType: undefined,
    subType: undefined,
    editionId: undefined,
    skip: 0,
    limit: 20,
  },
}

// ============================================================================
// Store
// ============================================================================

export const useUnifiedAgentStore = create<UnifiedAgentState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        // --------------------------------------------------------------------------
        // Task Actions
        // --------------------------------------------------------------------------

        createTask: async (request) => {
          set({ isCreatingTask: true, error: null })
          try {
            const task = await unifiedAgentAPI.createTask(request)
            set((state) => ({
              tasks: [task, ...state.tasks],
              currentTask: task,
              isCreatingTask: false,
            }))
            return task
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to create task',
              isCreatingTask: false,
            })
            return null
          }
        },

        loadTasks: async (filter) => {
          set({ isLoading: true, error: null })
          try {
            const currentFilter = filter ?? get().taskFilter
            const tasks = await unifiedAgentAPI.listTasks(currentFilter)
            set({ tasks, isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to load tasks',
              isLoading: false,
            })
          }
        },

        loadTask: async (taskId) => {
          set({ isLoading: true, error: null })
          try {
            const task = await unifiedAgentAPI.getTask(taskId)
            set({ currentTask: task, isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to load task',
              isLoading: false,
            })
          }
        },

        loadTaskProgress: async (taskId) => {
          try {
            const progress = await unifiedAgentAPI.getTaskProgress(taskId)
            set({ currentTaskProgress: progress })
          } catch (error) {
            console.error('Failed to load task progress:', error)
          }
        },

        cancelTask: async (taskId) => {
          set({ isLoading: true, error: null })
          try {
            const success = await unifiedAgentAPI.cancelTask(taskId)
            if (success) {
              set((state) => ({
                tasks: state.tasks.map((t) =>
                  t.id === taskId ? { ...t, status: 'cancelled' as const } : t
                ),
                currentTask:
                  state.currentTask?.id === taskId
                    ? { ...state.currentTask, status: 'cancelled' as const }
                    : state.currentTask,
                isLoading: false,
              }))
            }
            return success
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to cancel task',
              isLoading: false,
            })
            return false
          }
        },

        deleteTask: async (taskId) => {
          set({ isLoading: true, error: null })
          try {
            const success = await unifiedAgentAPI.deleteTask(taskId)
            if (success) {
              set((state) => ({
                tasks: state.tasks.filter((t) => t.id !== taskId),
                currentTask: state.currentTask?.id === taskId ? null : state.currentTask,
                isLoading: false,
              }))
            }
            return success
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to delete task',
              isLoading: false,
            })
            return false
          }
        },

        clearCurrentTask: () => {
          set({ currentTask: null, currentTaskProgress: null, currentTaskSteps: [] })
        },

        // --------------------------------------------------------------------------
        // Agent Actions
        // --------------------------------------------------------------------------

        loadAgents: async () => {
          try {
            const agents = await unifiedAgentAPI.listAgents()
            set({ agents })
          } catch (error) {
            console.error('Failed to load agents:', error)
          }
        },

        estimateTaskCost: async (agentType, request) => {
          try {
            const estimate = await unifiedAgentAPI.estimateTaskCost(agentType, request)
            return estimate
          } catch (error) {
            console.error('Failed to estimate task cost:', error)
            return null
          }
        },

        // --------------------------------------------------------------------------
        // Scheduler Actions
        // --------------------------------------------------------------------------

        loadSchedulerStatus: async () => {
          try {
            const schedulerStatus = await unifiedAgentAPI.getSchedulerStatus()
            set({ schedulerStatus })
          } catch (error) {
            console.error('Failed to load scheduler status:', error)
          }
        },

        startScheduler: async () => {
          set({ isLoading: true, error: null })
          try {
            const schedulerStatus = await unifiedAgentAPI.startScheduler()
            set({ schedulerStatus, isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to start scheduler',
              isLoading: false,
            })
          }
        },

        stopScheduler: async () => {
          set({ isLoading: true, error: null })
          try {
            const schedulerStatus = await unifiedAgentAPI.stopScheduler()
            set({ schedulerStatus, isLoading: false })
          } catch (error) {
            set({
              error: error instanceof Error ? error.message : 'Failed to stop scheduler',
              isLoading: false,
            })
          }
        },

        // --------------------------------------------------------------------------
        // WebSocket Actions
        // --------------------------------------------------------------------------

        connectRealtimeUpdates: () => {
          const { wsConnection, handleAgentEvent, loadTasks, loadSchedulerStatus } = get()

          // Close existing connection
          if (wsConnection) {
            try {
              wsConnection.close()
            } catch (e) {
              // Ignore errors when closing
            }
          }

          const ws = unifiedAgentAPI.connectRealtimeStream(
            (event) => {
              handleAgentEvent(event)
            },
            (error) => {
              console.log('[UnifiedAgentStore] WebSocket error, will retry...')
            },
            () => {
              // onOpen
              set({ wsConnected: true })
            },
            () => {
              // onClose
              set({ wsConnection: null, wsConnected: false })
              // Try to reconnect after a delay
              setTimeout(() => {
                const current = get()
                if (!current.wsConnection && current.useUnifiedAPI) {
                  get().connectRealtimeUpdates()
                }
              }, 3000)
            }
          )

          set({ wsConnection: ws })

          // Initial load
          loadTasks()
          loadSchedulerStatus()
        },

        disconnectRealtimeUpdates: () => {
          const { wsConnection } = get()
          if (wsConnection) {
            wsConnection.onclose = null
            try {
              wsConnection.close()
            } catch (e) {
              // Ignore errors when closing
            }
            set({ wsConnection: null, wsConnected: false })
          }
        },

        subscribeToTask: (taskId) => {
          const { wsConnection } = get()
          if (wsConnection) {
            unifiedAgentAPI.subscribeToTask(wsConnection, taskId)
          }
        },

        unsubscribeFromTask: (taskId) => {
          const { wsConnection } = get()
          if (wsConnection) {
            unifiedAgentAPI.unsubscribeFromTask(wsConnection, taskId)
          }
        },

        // --------------------------------------------------------------------------
        // Event Handling
        // --------------------------------------------------------------------------

        handleAgentEvent: (event) => {
          const { currentTask, loadTask, loadSchedulerStatus, loadTaskProgress } = get()

          switch (event.eventType) {
            case 'task_created':
            case 'task_started':
              // Refresh task list to show new/updated task
              get().loadTasks()
              loadSchedulerStatus()
              break

            case 'task_progress':
              // Update task progress
              set((state) => ({
                tasks: state.tasks.map((t) =>
                  t.id === event.taskId
                    ? {
                      ...t,
                      progress: (event.data.progress as number) ?? t.progress,
                      status: (event.data.status as UnifiedTask['status']) ?? t.status,
                    }
                    : t
                ),
                currentTask:
                  state.currentTask?.id === event.taskId
                    ? {
                      ...state.currentTask,
                      progress: (event.data.progress as number) ?? state.currentTask.progress,
                      status:
                        (event.data.status as UnifiedTask['status']) ??
                        state.currentTask.status,
                    }
                    : state.currentTask,
              }))
              break

            case 'task_step':
              // Add new step to current task
              if (currentTask?.id === event.taskId) {
                const newStep = event.data.step as TaskStep
                if (newStep) {
                  set((state) => ({
                    currentTaskSteps: [...state.currentTaskSteps, newStep],
                  }))
                }
              }
              break

            case 'task_completed':
            case 'task_failed':
            case 'task_cancelled':
              // Refresh task and scheduler state
              get().loadTasks()
              loadSchedulerStatus()

              // If viewing the task, refresh detail
              if (currentTask?.id === event.taskId) {
                loadTask(event.taskId)
                loadTaskProgress(event.taskId)
              }
              break

            case 'cost_update':
              // Update cost information
              set((state) => ({
                tasks: state.tasks.map((t) =>
                  t.id === event.taskId
                    ? {
                      ...t,
                      actualTokens: (event.data.actual_tokens as number) ?? t.actualTokens,
                      actualCost: (event.data.actual_cost as number) ?? t.actualCost,
                    }
                    : t
                ),
                currentTask:
                  state.currentTask?.id === event.taskId
                    ? {
                      ...state.currentTask,
                      actualTokens:
                        (event.data.actual_tokens as number) ??
                        state.currentTask.actualTokens,
                      actualCost:
                        (event.data.actual_cost as number) ?? state.currentTask.actualCost,
                    }
                    : state.currentTask,
              }))
              break
          }
        },

        // --------------------------------------------------------------------------
        // Filter Actions
        // --------------------------------------------------------------------------

        setTaskFilter: (filter) => {
          set((state) => ({
            taskFilter: { ...state.taskFilter, ...filter },
          }))
        },

        clearTaskFilter: () => {
          set({
            taskFilter: {
              status: undefined,
              taskType: undefined,
              subType: undefined,
              editionId: undefined,
              skip: 0,
              limit: 20,
            },
          })
        },

        // --------------------------------------------------------------------------
        // Feature Flag Actions
        // --------------------------------------------------------------------------

        setUseUnifiedAPI: (enabled) => {
          set({ useUnifiedAPI: enabled })
          if (enabled) {
            // Connect to new WebSocket
            get().connectRealtimeUpdates()
          } else {
            // Disconnect from new WebSocket
            get().disconnectRealtimeUpdates()
          }
        },

        // --------------------------------------------------------------------------
        // Utils
        // --------------------------------------------------------------------------

        clearError: () => set({ error: null }),

        reset: () => {
          get().disconnectRealtimeUpdates()
          set(initialState)
        },
      }),
      {
        name: 'unified-agent-store',
        partialize: (state) => ({
          useUnifiedAPI: state.useUnifiedAPI,
          taskFilter: state.taskFilter,
        }),
      }
    )
  )
)

// ============================================================================
// Selectors
// ============================================================================

/**
 * 获取按状态分组的任务
 */
export function selectTasksByStatus(state: UnifiedAgentState) {
  const grouped: Record<string, UnifiedTask[]> = {
    pending: [],
    running: [],
    completed: [],
    failed: [],
    cancelled: [],
  }
  state.tasks.forEach((task) => {
    grouped[task.status].push(task)
  })
  return grouped
}

/**
 * 获取运行中的任务
 */
export function selectRunningTasks(state: UnifiedAgentState): UnifiedTask[] {
  return state.tasks.filter((t) => t.status === 'running')
}

/**
 * 获取待处理的任务
 */
export function selectPendingTasks(state: UnifiedAgentState): UnifiedTask[] {
  return state.tasks.filter((t) => t.status === 'pending')
}

/**
 * 获取已完成的任务
 */
export function selectCompletedTasks(state: UnifiedAgentState): UnifiedTask[] {
  return state.tasks.filter((t) => t.status === 'completed')
}

/**
 * 获取指定类型的 Agent
 */
export function selectAgentByType(state: UnifiedAgentState, taskType: TaskType): AgentInfo | undefined {
  return state.agents.find((a) => a.supportedTaskTypes.includes(taskType))
}

/**
 * 获取指定类型的任务
 */
export function selectTasksByType(state: UnifiedAgentState, taskType: TaskType): UnifiedTask[] {
  return state.tasks.filter((t) => t.taskType === taskType)
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to get tasks filtered by status
 */
export function useTasksByStatus(status: TaskStatus | 'all' = 'all') {
  return useUnifiedAgentStore((state) =>
    status === 'all' ? state.tasks : state.tasks.filter((t) => t.status === status)
  )
}

/**
 * Hook to get tasks filtered by type
 */
export function useTasksByType(taskType: TaskType | 'all' = 'all') {
  return useUnifiedAgentStore((state) =>
    taskType === 'all' ? state.tasks : state.tasks.filter((t) => t.taskType === taskType)
  )
}

/**
 * Hook to check if any task is running
 */
export function useHasRunningTasks(): boolean {
  return useUnifiedAgentStore((state) => state.tasks.some((t) => t.status === 'running'))
}

/**
 * Hook to get total cost of all tasks
 */
export function useTotalTaskCost(): number {
  return useUnifiedAgentStore((state) =>
    state.tasks.reduce((sum, t) => sum + (t.actualCost || 0), 0)
  )
}

/**
 * Hook to get task statistics
 * Uses shallow comparison to prevent infinite re-renders
 */
export function useTaskStats() {
  const tasks = useUnifiedAgentStore((state) => state.tasks)

  // Use useMemo to cache the result
  return React.useMemo(() => {
    return {
      total: tasks.length,
      pending: tasks.filter((t) => t.status === 'pending').length,
      running: tasks.filter((t) => t.status === 'running').length,
      completed: tasks.filter((t) => t.status === 'completed').length,
      failed: tasks.filter((t) => t.status === 'failed').length,
      cancelled: tasks.filter((t) => t.status === 'cancelled').length,
      totalCost: tasks.reduce((sum, t) => sum + (t.actualCost || 0), 0),
      totalTokens: tasks.reduce((sum, t) => sum + (t.actualTokens || 0), 0),
    }
  }, [tasks])
}
