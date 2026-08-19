/**
 * @file affair.ts
 * @brief Rhythm Affair Zustand store
 * @description
 *   取代 `useProjectsStore` / `useMissionsStore`，统一提供：
 *   - ventures（kind=venture 长期事业）
 *   - tasks（kind=task_oneoff 一次性任务）
 *   - 状态转移、待办/逾期查询
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type { AffairData, AffairCreateProps, AffairUpdateProps } from '@lib/data/affair'
import type { AffairAction } from '@lib/api/affair'
import {
  api_get_affairs,
  api_get_affair,
  api_create_affair,
  api_update_affair,
  api_delete_affair,
  api_transit_affair_state,
} from '@lib/api/affair'

export interface AffairsState {
  // 数据
  ventures: AffairData[]
  tasks: AffairData[]
  upcomingTasks: AffairData[]
  overdueTasks: AffairData[]
  isLoading: boolean

  // CRUD
  fetchVentures: () => Promise<void>
  fetchTasks: (parentId?: number | null) => Promise<void>
  fetchAffair: (id: number) => Promise<AffairData>
  createVenture: (venture: AffairCreateProps) => Promise<AffairData>
  createTask: (task: AffairCreateProps) => Promise<AffairData>
  updateAffair: (id: number, affair: AffairUpdateProps) => Promise<AffairData>
  deleteAffair: (id: number) => Promise<boolean>

  // State transitions
  _transit: (id: number, action: AffairAction, options?: { defer_to?: Date | string | number }) => Promise<AffairData>
  confirmTask: (id: number) => Promise<AffairData>
  startTask: (id: number) => Promise<AffairData>
  finishTask: (id: number) => Promise<AffairData>
  cancelTask: (id: number) => Promise<AffairData>
  deferTask: (id: number, deferTo: Date | string | number) => Promise<AffairData>
  replanTask: (id: number) => Promise<AffairData>
  reopenTask: (id: number) => Promise<AffairData | null>

  // Reminder-like queries
  fetchUpcomingTasks: (hours?: number) => Promise<void>
  fetchOverdueTasks: () => Promise<void>
}

const updateAffairInList = (list: AffairData[], updated: AffairData): AffairData[] => {
  const index = list.findIndex((a) => a.id === updated.id)
  if (index === -1) return [...list, updated]
  const next = [...list]
  next[index] = updated
  return next
}

export const useAffairsStore: UseBoundStore<StoreApi<AffairsState>> = create<AffairsState>((set, get) => ({
  ventures: [],
  tasks: [],
  upcomingTasks: [],
  overdueTasks: [],
  isLoading: false,

  // -------------------------------------------------------------------------
  // Queries
  // -------------------------------------------------------------------------

  fetchVentures: async (): Promise<void> => {
    set({ isLoading: true })
    try {
      const ventures = await api_get_affairs({ kind: 'venture', state: ['INBOX', 'ACTIVE', 'PAUSED'] })
      set({ ventures, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  fetchTasks: async (parentId?: number | null): Promise<void> => {
    set({ isLoading: true })
    try {
      const tasks = await api_get_affairs({
        kind: 'task_oneoff',
        domain: ['work', 'career'],
        parent_id: parentId,
      })
      set({ tasks, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  fetchAffair: async (id: number): Promise<AffairData> => {
    const affair = await api_get_affair(id)
    set((state) => {
      const next: Partial<AffairsState> = {}
      if (affair.kind === 'venture') {
        next.ventures = updateAffairInList(state.ventures, affair)
      } else if (affair.kind === 'task_oneoff') {
        next.tasks = updateAffairInList(state.tasks, affair)
      }
      return next
    })
    return affair
  },

  // -------------------------------------------------------------------------
  // CRUD
  // -------------------------------------------------------------------------

  createVenture: async (venture: AffairCreateProps): Promise<AffairData> => {
    const newVenture = await api_create_affair({
      ...venture,
      kind: 'venture',
      domain: 'career',
    })
    set((state) => ({
      ventures: [...state.ventures, newVenture],
    }))
    return newVenture
  },

  createTask: async (task: AffairCreateProps): Promise<AffairData> => {
    const newTask = await api_create_affair({
      ...task,
      kind: 'task_oneoff',
      domain: 'work',
    })
    set((state) => ({
      tasks: [...state.tasks, newTask],
    }))
    return newTask
  },

  updateAffair: async (id: number, affair: AffairUpdateProps): Promise<AffairData> => {
    const updated = await api_update_affair(id, affair)
    set((state) => {
      const next: Partial<AffairsState> = {}
      if (updated.kind === 'venture') {
        next.ventures = updateAffairInList(state.ventures, updated)
      } else if (updated.kind === 'task_oneoff') {
        next.tasks = updateAffairInList(state.tasks, updated)
      }
      return next
    })
    return updated
  },

  deleteAffair: async (id: number): Promise<boolean> => {
    const response = await api_delete_affair(id)
    const success = response.status === 'success'
    if (success) {
      set((state) => ({
        ventures: state.ventures.filter((v) => v.id !== id),
        tasks: state.tasks.filter((t) => t.id !== id),
        upcomingTasks: state.upcomingTasks.filter((t) => t.id !== id),
        overdueTasks: state.overdueTasks.filter((t) => t.id !== id),
      }))
    }
    return success
  },

  // -------------------------------------------------------------------------
  // State transitions
  // -------------------------------------------------------------------------

  _transit: async (id: number, action: AffairAction, options?: { defer_to?: Date | string | number }): Promise<AffairData> => {
    const updated = await api_transit_affair_state(id, action, options ?? {})
    set((state) => ({
      tasks: updateAffairInList(state.tasks, updated),
      ventures: updateAffairInList(state.ventures, updated),
      upcomingTasks: updateAffairInList(state.upcomingTasks, updated),
      overdueTasks: updateAffairInList(state.overdueTasks, updated),
    }))
    return updated
  },

  confirmTask: async (id: number): Promise<AffairData> => {
    return get()._transit(id, 'confirm')
  },

  startTask: async (id: number): Promise<AffairData> => {
    return get()._transit(id, 'start')
  },

  finishTask: async (id: number): Promise<AffairData> => {
    return get()._transit(id, 'finish')
  },

  cancelTask: async (id: number): Promise<AffairData> => {
    return get()._transit(id, 'cancel')
  },

  deferTask: async (id: number, deferTo: Date | string | number): Promise<AffairData> => {
    return get()._transit(id, 'defer', { defer_to: deferTo })
  },

  replanTask: async (id: number): Promise<AffairData> => {
    return get()._transit(id, 'replan')
  },

  reopenTask: async (id: number): Promise<AffairData | null> => {
    // Affair 的 CANCELED/DONE 是终态，不能回退。
    // 业务上采用"复制为新建"：创建同名 INBOX 任务。
    const original = get().tasks.find((t) => t.id === id) ?? get().ventures.find((v) => v.id === id)
    if (!original) return null
    try {
      const created = await api_create_affair({
        title: `${original.title} [reopened]`,
        description: original.description,
        kind: original.kind,
        domain: original.domain,
        parent_id: original.parent_id,
        urgency_ddl: original.urgency_ddl,
        est_minutes: original.est_minutes,
        energy_cost: original.energy_cost,
        state: 'INBOX',
      })
      set((state) => ({
        tasks: [...state.tasks, created],
      }))
      return created
    } catch (error) {
      console.error('Failed to reopen affair:', error)
      return null
    }
  },

  // -------------------------------------------------------------------------
  // Reminder-like queries
  // -------------------------------------------------------------------------

  fetchUpcomingTasks: async (hours: number = 24): Promise<void> => {
    const before = new Date(Date.now() + hours * 60 * 60 * 1000)
    try {
      const tasks = await api_get_affairs({
        kind: 'task_oneoff',
        domain: ['work', 'career'],
        state: ['INBOX', 'PLANNED', 'DOING'],
        urgency_ddl_before: before,
      })
      set({ upcomingTasks: tasks })
    } catch (error) {
      console.error('Failed to fetch upcoming tasks:', error)
    }
  },

  fetchOverdueTasks: async (): Promise<void> => {
    const now = new Date()
    try {
      const tasks = await api_get_affairs({
        kind: 'task_oneoff',
        domain: ['work', 'career'],
        state: ['INBOX', 'PLANNED', 'DOING'],
        urgency_ddl_before: now,
      })
      set({ overdueTasks: tasks })
    } catch (error) {
      console.error('Failed to fetch overdue tasks:', error)
    }
  },
}))

// Expose a typed helper for internal use; not part of public state API
export type { AffairAction }
