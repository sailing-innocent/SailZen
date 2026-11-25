/**
 * @file rhythm.ts
 * @brief Rhythm v2 极简 Zustand store（可视化日程画布 + 项目倒排 + 待办 + 占用）
 */

import { create } from 'zustand'
import { AffairDomain, AffairKind } from '@lib/data/affair'
import {
  api_create_affair,
  api_delete_affair,
  api_transit_affair_state,
} from '@lib/api/affair'
import {
  api_add_venture_milestone,
  api_checkin,
  api_create_occupancy,
  api_create_time_block,
  api_delete_occupancy,
  api_delete_time_block,
  api_get_dashboard,
  api_mark_milestone_done,
  api_move_block,
  api_set_block_status,
  toISODate,
} from '@lib/api/rhythm'
import type {
  BlockStatusValue,
  CheckinResultValue,
  OccupancyTypeValue,
  RhythmDashboardData,
} from '@lib/data/rhythm'

interface RhythmStoreState {
  selectedDate: string
  dashboard: RhythmDashboardData | null
  loading: boolean
  error: string | null

  setSelectedDate: (d: Date | string) => void
  fetchDashboard: (date?: Date | string) => Promise<void>
  setBlockStatus: (blockId: number, status: BlockStatusValue) => Promise<void>
  moveBlock: (blockId: number, start: Date | string, end: Date | string) => Promise<void>
  deleteBlock: (blockId: number) => Promise<void>
  createBlock: (payload: {
    title: string
    start: string
    end: string
    block_type?: string
    affair_id?: number | null
    pinned?: boolean
  }) => Promise<void>
  createOccupancy: (payload: {
    occupancy_type: OccupancyTypeValue
    start?: string
    end?: string
    whole_day?: boolean
    label: string
    note?: string
  }) => Promise<void>
  deleteOccupancy: (blockId: number) => Promise<void>
  quickAddProject: (title: string, targetDate?: string, description?: string) => Promise<void>
  addMilestone: (ventureId: number, title: string) => Promise<void>
  markMilestoneDone: (milestoneId: number) => Promise<void>
  quickAddTask: (title: string, ddl?: string) => Promise<void>
  finishAffair: (affairId: number) => Promise<void>
  deleteAffair: (affairId: number) => Promise<void>
  checkin: (affairId: number, result: CheckinResultValue) => Promise<void>
}

export const useRhythmStore = create<RhythmStoreState>((set, get) => ({
  selectedDate: toISODate(new Date()),
  dashboard: null,
  loading: false,
  error: null,

  setSelectedDate: (d) => {
    const next = toISODate(d)
    set({ selectedDate: next })
  },

  fetchDashboard: async (date) => {
    const target = date ? toISODate(date) : get().selectedDate
    set({ loading: true, error: null })
    try {
      const data = await api_get_dashboard(target)
      set({ dashboard: data, loading: false })
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : String(e),
      })
    }
  },

  setBlockStatus: async (blockId, status) => {
    await api_set_block_status(blockId, status)
    await get().fetchDashboard()
  },

  moveBlock: async (blockId, start, end) => {
    await api_move_block(blockId, start, end)
    await get().fetchDashboard()
  },

  deleteBlock: async (blockId) => {
    await api_delete_time_block(blockId)
    await get().fetchDashboard()
  },

  createBlock: async ({ title, start, end, block_type = 'focus', affair_id = null, pinned = false }) => {
    const d = get().selectedDate
    await api_create_time_block({
      date: d,
      affair_id,
      block_type,
      start_time: start.includes('T') ? start : `${d}T${start}:00`,
      end_time: end.includes('T') ? end : `${d}T${end}:00`,
      pinned,
      ref: { label: title, source: 'manual' },
    })
    await get().fetchDashboard()
  },

  createOccupancy: async (payload) => {
    await api_create_occupancy({ ...payload, date: get().selectedDate })
    await get().fetchDashboard()
  },

  deleteOccupancy: async (blockId) => {
    await api_delete_occupancy(blockId)
    await get().fetchDashboard()
  },

  quickAddProject: async (title, targetDate, description = '') => {
    await api_create_affair({
      title: title.trim(),
      description,
      kind: AffairKind.VENTURE,
      domain: AffairDomain.CAREER,
      kind_meta: targetDate ? { target_date: targetDate } : {},
      urgency_ddl: targetDate ? `${targetDate}T00:00:00` : undefined,
      est_minutes: 60,
    })
    await get().fetchDashboard()
  },

  addMilestone: async (ventureId, title) => {
    await api_add_venture_milestone(ventureId, { title: title.trim(), est_minutes: 60 })
    await get().fetchDashboard()
  },

  markMilestoneDone: async (milestoneId) => {
    await api_mark_milestone_done(milestoneId)
    await get().fetchDashboard()
  },

  quickAddTask: async (title, ddl) => {
    await api_create_affair({
      title: title.trim(),
      kind: AffairKind.TASK_ONEOFF,
      domain: AffairDomain.WORK,
      urgency_ddl: ddl ? `${ddl}T18:00:00` : undefined,
      est_minutes: 30,
    })
    await get().fetchDashboard()
  },

  finishAffair: async (affairId) => {
    await api_transit_affair_state(affairId, 'finish')
    await get().fetchDashboard()
  },

  deleteAffair: async (affairId) => {
    await api_delete_affair(affairId)
    await get().fetchDashboard()
  },

  checkin: async (affairId, result) => {
    await api_checkin(affairId, result, get().selectedDate)
    await get().fetchDashboard()
  },
}))
