/**
 * @file rhythm.ts
 * @brief Rhythm Dashboard Zustand store
 * @description
 *   统一 Rhythm Dashboard 状态管理：聚合数据、时间线、事务、配置、复盘统计。
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type { AffairData, AffairCreateProps, AffairUpdateProps } from '@lib/data/affair'
import type { AffairAction } from '@lib/api/affair'
import {
  api_get_dashboard,
  api_get_day_timeline,
  api_plan_day,
  api_rebalance_day,
  api_get_conflicts,
  api_get_day_review,
  api_get_week_review,
  api_update_review_summary,
  api_get_encroachments,
  api_get_domain_trend,
  api_get_today_checkins,
  api_checkin,
  api_list_checkins,
  api_get_energy_profile,
  api_upsert_energy_profile,
  api_list_policies,
  api_create_policy,
  api_update_policy,
  api_delete_policy,
  api_list_templates,
  api_upsert_template,
  api_delete_template,
  api_get_habit_heatmap,
  api_get_venture_burndown,
  api_set_block_status,
  api_move_block,
  api_create_time_block,
  api_recalibrate_profile,
  api_ensure_default_templates,
} from '@lib/api/rhythm'
import {
  api_create_affair,
  api_update_affair,
  api_delete_affair,
  api_transit_affair_state,
  api_confirm_hint,
  api_split_affair,
  api_get_affairs_by_kind,
} from '@lib/api/affair'
import type {
  RhythmDashboardData,
  DayTimelineData,
  ReviewData,
  ConflictReportData,
  CheckinTodayData,
  EnergyProfileData,
  EnergyProfileUpdateProps,
  PolicyData,
  PolicyCreateProps,
  PolicyUpdateProps,
  DayTemplateData,
  DayTemplateCreateProps,
  EncroachmentData,
  DomainTrendData,
  HabitHeatmapData,
  VentureBurndownData,
  CheckinLogData,
  PlanDayData,
  PlanOptions,
  BlockStatusValue,
  CheckinResultValue,
} from '@lib/data/rhythm'

export interface RhythmState {
  // 全局配置
  energyProfile: EnergyProfileData | null
  policies: PolicyData[]
  templates: DayTemplateData[]

  // 当前视图日期
  selectedDate: string

  // Dashboard 聚合数据
  dashboard: RhythmDashboardData | null
  dayTimeline: DayTimelineData | null
  dayReview: ReviewData | null
  weekReview: ReviewData | null
  todayCheckins: CheckinTodayData | null
  conflicts: ConflictReportData | null
  encroachments: EncroachmentData[]
  domainTrend: DomainTrendData | null

  // 事务
  inbox: AffairData[]
  activeAffairs: AffairData[]
  allAffairs: AffairData[]
  ventures: AffairData[]
  habits: AffairData[]
  precepts: AffairData[]
  maintenanceTasks: AffairData[]
  asyncCallbacks: AffairData[]

  // 加载态
  isLoading: boolean
  error: string | null

  // actions
  setSelectedDate: (date: string | Date) => void
  fetchDashboard: (date?: string | Date) => Promise<void>
  fetchDayTimeline: (date?: string | Date) => Promise<void>
  planDay: (date?: string | Date, options?: PlanOptions) => Promise<PlanDayData>
  rebalanceDay: (date?: string | Date, trigger?: string) => Promise<PlanDayData>
  fetchReview: (scope: 'day' | 'week', dateOrSpan?: string) => Promise<ReviewData>
  fetchEncroachments: (start?: Date, end?: Date) => Promise<void>
  fetchDomainTrend: (start: Date, end: Date) => Promise<void>
  fetchTodayCheckins: (date?: Date) => Promise<void>
  checkin: (
    affairId: number,
    result: CheckinResultValue,
    note?: string,
    date?: Date
  ) => Promise<CheckinLogData>
  listCheckins: (filters?: {
    affair_id?: number
    start_date?: Date
    end_date?: Date
  }) => Promise<CheckinLogData[]>
  fetchHabitHeatmap: (affairId: number, start: Date, end: Date) => Promise<HabitHeatmapData>
  fetchVentureBurndown: (ventureId: number) => Promise<VentureBurndownData>
  fetchEnergyProfile: () => Promise<void>
  saveEnergyProfile: (data: EnergyProfileUpdateProps) => Promise<EnergyProfileData>
  fetchPolicies: () => Promise<void>
  savePolicy: (data: PolicyCreateProps) => Promise<PolicyData>
  updatePolicy: (id: number, data: PolicyUpdateProps) => Promise<PolicyData>
  deletePolicy: (id: number) => Promise<void>
  fetchTemplates: () => Promise<void>
  saveTemplate: (data: DayTemplateCreateProps) => Promise<DayTemplateData>
  deleteTemplate: (id: number) => Promise<void>
  fetchAllAffairs: (filters?: Record<string, unknown>) => Promise<void>
  fetchAffairsByKind: () => Promise<void>
  createAffair: (props: AffairCreateProps) => Promise<AffairData>
  updateAffair: (id: number, props: AffairUpdateProps) => Promise<AffairData>
  transitAffair: (id: number, action: AffairAction, options?: Record<string, unknown>) => Promise<AffairData>
  deleteAffair: (id: number) => Promise<void>
  confirmHint: (id: number, accept: boolean, overrides?: Record<string, unknown>) => Promise<AffairData>
  splitAffair: (id: number, children: Record<string, unknown>[]) => Promise<AffairData[]>
  setBlockStatus: (blockId: number, status: BlockStatusValue) => Promise<void>
  moveBlock: (blockId: number, start: Date, end: Date) => Promise<void>
  createBlock: (data: Record<string, unknown>) => Promise<void>
  recalibrateProfile: () => Promise<EnergyProfileData>
  ensureDefaultTemplates: () => Promise<{ created: number; updated: number; templates: DayTemplateData[] }>
  clearError: () => void
}

const toISODate = (d: string | Date): string => {
  if (typeof d === 'string') return d.split('T')[0]
  // 转成当地日期字符串，避免 toISOString() 返回 UTC 日期导致东八区等地区日期回退一天
  const localMs = d.getTime() - d.getTimezoneOffset() * 60 * 1000
  return new Date(localMs).toISOString().split('T')[0]
}

const updateAffairInList = (list: AffairData[], updated: AffairData): AffairData[] => {
  const index = list.findIndex((a) => a.id === updated.id)
  if (index === -1) return [...list, updated]
  const next = [...list]
  next[index] = updated
  return next
}

const removeAffairFromLists = (state: RhythmState, id: number): Partial<RhythmState> => ({
  inbox: state.inbox.filter((a) => a.id !== id),
  activeAffairs: state.activeAffairs.filter((a) => a.id !== id),
  allAffairs: state.allAffairs.filter((a) => a.id !== id),
  ventures: state.ventures.filter((a) => a.id !== id),
  habits: state.habits.filter((a) => a.id !== id),
  precepts: state.precepts.filter((a) => a.id !== id),
  maintenanceTasks: state.maintenanceTasks.filter((a) => a.id !== id),
  asyncCallbacks: state.asyncCallbacks.filter((a) => a.id !== id),
})

export const useRhythmStore: UseBoundStore<StoreApi<RhythmState>> = create<RhythmState>((set, get) => ({
  energyProfile: null,
  policies: [],
  templates: [],
  selectedDate: toISODate(new Date()),
  dashboard: null,
  dayTimeline: null,
  dayReview: null,
  weekReview: null,
  todayCheckins: null,
  conflicts: null,
  encroachments: [],
  domainTrend: null,
  inbox: [],
  activeAffairs: [],
  allAffairs: [],
  ventures: [],
  habits: [],
  precepts: [],
  maintenanceTasks: [],
  asyncCallbacks: [],
  isLoading: false,
  error: null,

  setSelectedDate: (date: string | Date) => {
    set({ selectedDate: toISODate(date) })
  },

  fetchDashboard: async (date?: string | Date) => {
    const d = toISODate(date ?? get().selectedDate)
    set({ isLoading: true, error: null })
    try {
      const dashboard = await api_get_dashboard(d)
      set({
        dashboard,
        dayTimeline: dashboard.timeline,
        dayReview: dashboard.day_review,
        weekReview: dashboard.week_review,
        todayCheckins: dashboard.today_checkins,
        conflicts: dashboard.conflicts,
        energyProfile: dashboard.energy_profile,
        policies: dashboard.policies,
        inbox: dashboard.inbox_summary.map((i) => i.affair),
        activeAffairs: dashboard.inbox_summary.map((i) => i.affair),
        isLoading: false,
      })
    } catch (error) {
      set({ isLoading: false, error: String(error) })
      throw error
    }
  },

  fetchDayTimeline: async (date?: string | Date) => {
    const d = toISODate(date ?? get().selectedDate)
    try {
      const timeline = await api_get_day_timeline(d)
      set({ dayTimeline: timeline })
    } catch (error) {
      set({ error: String(error) })
      throw error
    }
  },

  planDay: async (date?: string | Date, options?: PlanOptions) => {
    const d = toISODate(date ?? get().selectedDate)
    const result = await api_plan_day(d, options)
    await get().fetchDayTimeline(d)
    return result
  },

  rebalanceDay: async (date?: string | Date, trigger = 'manual') => {
    const d = toISODate(date ?? get().selectedDate)
    const result = await api_rebalance_day(d, trigger)
    await get().fetchDayTimeline(d)
    return result
  },

  fetchReview: async (scope: 'day' | 'week', dateOrSpan?: string) => {
    const d = dateOrSpan ?? (scope === 'day' ? get().selectedDate : undefined)
    const review =
      scope === 'day' ? await api_get_day_review(d!) : await api_get_week_review(d)
    set(scope === 'day' ? { dayReview: review } : { weekReview: review })
    return review
  },

  fetchEncroachments: async (start?: Date, end?: Date) => {
    const items = await api_get_encroachments(start, end)
    set({ encroachments: items })
  },

  fetchDomainTrend: async (start: Date, end: Date) => {
    const trend = await api_get_domain_trend(start, end)
    set({ domainTrend: trend })
  },

  fetchTodayCheckins: async (date?: Date) => {
    const checkins = await api_get_today_checkins(date)
    set({ todayCheckins: checkins })
  },

  checkin: async (affairId: number, result: CheckinResultValue, note?: string, date?: Date) => {
    const log = await api_checkin({ affair_id: affairId, result, note, log_date: date })
    await get().fetchTodayCheckins(date)
    return log
  },

  listCheckins: async (filters) => {
    const res = await api_list_checkins(filters)
    return res.logs
  },

  fetchHabitHeatmap: async (affairId: number, start: Date, end: Date) => {
    return api_get_habit_heatmap(affairId, start, end)
  },

  fetchVentureBurndown: async (ventureId: number) => {
    return api_get_venture_burndown(ventureId)
  },

  fetchEnergyProfile: async () => {
    const profile = await api_get_energy_profile()
    set({ energyProfile: profile })
  },

  saveEnergyProfile: async (data: EnergyProfileUpdateProps) => {
    const profile = await api_upsert_energy_profile(data)
    set({ energyProfile: profile })
    return profile
  },

  fetchPolicies: async () => {
    const res = await api_list_policies()
    set({ policies: res.policies })
  },

  savePolicy: async (data: PolicyCreateProps) => {
    const policy = await api_create_policy(data)
    set((state) => ({ policies: [...state.policies, policy] }))
    return policy
  },

  updatePolicy: async (id: number, data: PolicyUpdateProps) => {
    const policy = await api_update_policy(id, data)
    set((state) => ({
      policies: state.policies.map((p) => (p.id === id ? policy : p)),
    }))
    return policy
  },

  deletePolicy: async (id: number) => {
    await api_delete_policy(id)
    set((state) => ({ policies: state.policies.filter((p) => p.id !== id) }))
  },

  fetchTemplates: async () => {
    const res = await api_list_templates()
    set({ templates: res.templates })
  },

  saveTemplate: async (data: DayTemplateCreateProps) => {
    const template = await api_upsert_template(data)
    set((state) => {
      const exists = state.templates.some((t) => t.id === template.id)
      if (exists) {
        return { templates: state.templates.map((t) => (t.id === template.id ? template : t)) }
      }
      return { templates: [...state.templates, template] }
    })
    return template
  },

  deleteTemplate: async (id: number) => {
    await api_delete_template(id)
    set((state) => ({ templates: state.templates.filter((t) => t.id !== id) }))
  },

  fetchAllAffairs: async () => {
    // 由 affair store 负责细粒度拉取，rhythm store 只刷新聚合摘要
    await get().fetchAffairsByKind()
  },

  fetchAffairsByKind: async () => {
    const [ventures, habits, precepts, maintenance, asyncs] = await Promise.all([
      api_get_affairs_by_kind('venture', ['INBOX', 'ACTIVE', 'PAUSED']),
      api_get_affairs_by_kind('habit', ['INBOX', 'ACTIVE', 'PAUSED']),
      api_get_affairs_by_kind('precept', ['INBOX', 'ACTIVE', 'PAUSED']),
      api_get_affairs_by_kind('task_maintenance', ['INBOX', 'ACTIVE', 'PAUSED']),
      api_get_affairs_by_kind('async_callback', [
        'INBOX',
        'ACTIVE',
        'PAUSED',
        'KICKOFF',
        'DELEGATED',
        'REVIEWING',
      ]),
    ])
    set({
      ventures,
      habits,
      precepts,
      maintenanceTasks: maintenance,
      asyncCallbacks: asyncs,
      allAffairs: [...ventures, ...habits, ...precepts, ...maintenance, ...asyncs],
    })
  },

  createAffair: async (props: AffairCreateProps) => {
    const affair = await api_create_affair(props)
    set((state) => ({
      allAffairs: [...state.allAffairs, affair],
      inbox: affair.state === 'INBOX' ? [...state.inbox, affair] : state.inbox,
    }))
    return affair
  },

  updateAffair: async (id: number, props: AffairUpdateProps) => {
    const affair = await api_update_affair(id, props)
    set((state) => {
      const patch: Partial<RhythmState> = {
        allAffairs: updateAffairInList(state.allAffairs, affair),
      }
      if (affair.kind === 'venture') patch.ventures = updateAffairInList(state.ventures, affair)
      if (affair.kind === 'habit') patch.habits = updateAffairInList(state.habits, affair)
      if (affair.kind === 'precept') patch.precepts = updateAffairInList(state.precepts, affair)
      if (affair.kind === 'task_maintenance') patch.maintenanceTasks = updateAffairInList(state.maintenanceTasks, affair)
      if (affair.kind === 'async_callback') patch.asyncCallbacks = updateAffairInList(state.asyncCallbacks, affair)
      if (affair.state === 'INBOX') patch.inbox = updateAffairInList(state.inbox, affair)
      return patch
    })
    return affair
  },

  transitAffair: async (id: number, action: AffairAction, options?: Record<string, unknown>) => {
    const affair = await api_transit_affair_state(id, action, options ?? {})
    set((state) => {
      const patch: Partial<RhythmState> = {
        allAffairs: updateAffairInList(state.allAffairs, affair),
      }
      if (affair.kind === 'venture') patch.ventures = updateAffairInList(state.ventures, affair)
      if (affair.kind === 'habit') patch.habits = updateAffairInList(state.habits, affair)
      if (affair.kind === 'precept') patch.precepts = updateAffairInList(state.precepts, affair)
      if (affair.kind === 'task_maintenance') patch.maintenanceTasks = updateAffairInList(state.maintenanceTasks, affair)
      if (affair.kind === 'async_callback') patch.asyncCallbacks = updateAffairInList(state.asyncCallbacks, affair)
      patch.inbox = state.inbox.filter((a) => a.id !== id)
      return patch
    })
    return affair
  },

  deleteAffair: async (id: number) => {
    await api_delete_affair(id)
    set((state) => removeAffairFromLists(state, id))
  },

  confirmHint: async (id: number, accept: boolean, overrides?: Record<string, unknown>) => {
    const affair = await api_confirm_hint(id, { accept, overrides })
    set((state) => {
      const patch: Partial<RhythmState> = {
        allAffairs: updateAffairInList(state.allAffairs, affair),
      }
      if (affair.kind === 'venture') patch.ventures = updateAffairInList(state.ventures, affair)
      if (affair.kind === 'habit') patch.habits = updateAffairInList(state.habits, affair)
      if (affair.kind === 'precept') patch.precepts = updateAffairInList(state.precepts, affair)
      if (affair.kind === 'task_maintenance') patch.maintenanceTasks = updateAffairInList(state.maintenanceTasks, affair)
      if (affair.kind === 'async_callback') patch.asyncCallbacks = updateAffairInList(state.asyncCallbacks, affair)
      patch.inbox = updateAffairInList(state.inbox, affair)
      return patch
    })
    return affair
  },

  splitAffair: async (id: number, children: Record<string, unknown>[]) => {
    const res = await api_split_affair(id, { children })
    set((state) => ({
      allAffairs: [...state.allAffairs, ...res.affairs],
      inbox: [...state.inbox, ...res.affairs.filter((a) => a.state === 'INBOX')],
    }))
    return res.affairs
  },

  setBlockStatus: async (blockId: number, status: BlockStatusValue) => {
    await api_set_block_status(blockId, status)
    await get().fetchDayTimeline()
  },

  moveBlock: async (blockId: number, start: Date, end: Date) => {
    await api_move_block(blockId, start, end)
    await get().fetchDayTimeline()
  },

  createBlock: async (data: Record<string, unknown>) => {
    await api_create_time_block(data)
    await get().fetchDayTimeline()
  },

  recalibrateProfile: async () => {
    // 默认校准：保持当前值但重命名 default_imported（后端实际会 upsert default）
    const profile = await api_recalibrate_profile({
      ...(get().energyProfile ?? {}),
      name: 'default',
    } as EnergyProfileUpdateProps)
    set({ energyProfile: profile })
    return profile
  },

  ensureDefaultTemplates: async () => {
    return api_ensure_default_templates()
  },

  clearError: () => set({ error: null }),
}))
