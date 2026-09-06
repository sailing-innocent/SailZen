/**
 * @file rhythm.ts
 * @brief Rhythm Dashboard Zustand store
 * @description
 * 统一 Rhythm Dashboard 状态管理：聚合数据、时间线、事务、配置、复盘统计。
 * 错误分片：dashboard/timeline/affairs/ventures/checkins/review/config 七个分片
 * 各自维护 {loading, error}，任何分片失败不污染全局，可 retrySection 单分片重试。
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  AffairKind,
  AffairState,
  type AffairData,
  type AffairCreateProps,
  type AffairUpdateProps,
  type AffairKindValue,
  type AffairDomainValue,
  type AffairStateValue,
} from '@lib/data/affair'
import type { AffairAction } from '@lib/api/affair'
import {
  api_get_dashboard,
  api_get_day_timeline,
  api_plan_day,
  api_rebalance_day,
  api_get_conflicts,
  api_get_day_review,
  api_get_week_review,
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
  api_get_affairs,
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
  PriorityAffairItemData,
} from '@lib/data/rhythm'

// ============================================================================
// 错误分片
// ============================================================================

/** 状态分片键：每个分片独立维护 loading/error */
export type RhythmSection =
  | 'dashboard'
  | 'timeline'
  | 'affairs'
  | 'ventures'
  | 'checkins'
  | 'review'
  | 'config'

export interface SectionStatus {
  loading: boolean
  error: string | null
}

const EMPTY_SECTION: SectionStatus = { loading: false, error: null }

const initialSections = (): Record<RhythmSection, SectionStatus> => ({
  dashboard: { ...EMPTY_SECTION },
  timeline: { ...EMPTY_SECTION },
  affairs: { ...EMPTY_SECTION },
  ventures: { ...EMPTY_SECTION },
  checkins: { ...EMPTY_SECTION },
  review: { ...EMPTY_SECTION },
  config: { ...EMPTY_SECTION },
})

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

// ============================================================================
// 事务过滤器（事务中心工具栏）
// ============================================================================

export interface AffairFilterState {
  search: string
  states: AffairStateValue[]
  domains: AffairDomainValue[]
  kinds: AffairKindValue[]
}

const initialAffairFilters = (): AffairFilterState => ({
  search: '',
  states: [],
  domains: [],
  kinds: [],
})

/** fetchAffairsByKind 拉取的非终态集合（DONE/CANCELED/ARCHIVED/COMPLETED 不进看板） */
const BOARD_STATES: AffairStateValue[] = [
  AffairState.INBOX,
  AffairState.PLANNED,
  AffairState.SCHEDULED,
  AffairState.DOING,
  AffairState.DEFERRED,
  AffairState.ACTIVE,
  AffairState.PAUSED,
  AffairState.KICKOFF,
  AffairState.DELEGATED,
  AffairState.REVIEWING,
]

const BOARD_KINDS: AffairKindValue[] = [
  AffairKind.BASE_RHYTHM,
  AffairKind.PRECEPT,
  AffairKind.HABIT,
  AffairKind.FIXED_PLAN,
  AffairKind.TASK_ONEOFF,
  AffairKind.TASK_MAINTENANCE,
  AffairKind.VENTURE,
  AffairKind.ASYNC_CALLBACK,
  AffairKind.GENERIC,
]

const filterByKind = (list: AffairData[], kind: AffairKindValue): AffairData[] =>
  list.filter((a) => a.kind === kind)

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

  // Dashboard 摘要（优先级事务）
  inboxSummary: PriorityAffairItemData[]
  overdueSummary: PriorityAffairItemData[]
  todayDueSummary: PriorityAffairItemData[]
  /** dashboard 装配失败的子模块名（后端 degraded 字段） */
  degraded: string[]

  // 事务
  inbox: AffairData[]
  activeAffairs: AffairData[]
  allAffairs: AffairData[]
  ventures: AffairData[]
  habits: AffairData[]
  precepts: AffairData[]
  maintenanceTasks: AffairData[]
  asyncCallbacks: AffairData[]

  // 事务中心过滤器
  affairFilters: AffairFilterState

  // 分片状态
  sections: Record<RhythmSection, SectionStatus>

  // 加载态（legacy：任意分片 loading 的聚合，新代码请用 sections[section].loading）
  isLoading: boolean
  // 全局错误（legacy：仅 dashboard 致命失败写入，分片错误请用 sections[section].error）
  error: string | null

  // actions
  setSelectedDate: (date: string | Date) => void
  sectionStatus: (section: RhythmSection) => SectionStatus
  retrySection: (section: RhythmSection) => Promise<void>
  fetchDashboard: (date?: string | Date) => Promise<void>
  fetchDayTimeline: (date?: string | Date) => Promise<void>
  fetchConflicts: (date?: string | Date) => Promise<void>
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
  setAffairFilters: (patch: Partial<AffairFilterState>) => void
  resetAffairFilters: () => void
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

/**
 * fetchDashboard 在途请求表（按日期键合并）。
 * React StrictMode 会双调用 mount effect；若无合并，一次进入概览页会发出 2 次相同请求、
 * 触发 2 次 dashboard 全量替换（三域时间等图表动画重复播放），后端日志表现为成对请求。
 * 同一日期的并发调用共享同一 Promise；不同日期或前序请求已结束则正常发起新请求。
 */
let dashboardInflight: { date: string; promise: Promise<void> } | null = null

export const useRhythmStore: UseBoundStore<StoreApi<RhythmState>> = create<RhythmState>((set, get) => {
  /** 更新单个分片状态 */
  const setSection = (section: RhythmSection, patch: Partial<SectionStatus>): void => {
    set((state) => ({
      sections: {
        ...state.sections,
        [section]: { ...state.sections[section], ...patch },
      },
    }))
  }

  /** 最佳努力刷新：失败静默（调用方已处理主错误，级联刷新不再抛出） */
  const refreshBestEffort = async (fn: () => Promise<unknown>): Promise<void> => {
    try {
      await fn()
    } catch {
      // 级联刷新失败静默：分片状态已由被调 action 记录
    }
  }

  return {
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
    inboxSummary: [],
    overdueSummary: [],
    todayDueSummary: [],
    degraded: [],
    inbox: [],
    activeAffairs: [],
    allAffairs: [],
    ventures: [],
    habits: [],
    precepts: [],
    maintenanceTasks: [],
    asyncCallbacks: [],
    affairFilters: initialAffairFilters(),
    sections: initialSections(),
    isLoading: false,
    error: null,

    setSelectedDate: (date: string | Date) => {
      set({ selectedDate: toISODate(date) })
    },

    sectionStatus: (section: RhythmSection) => get().sections[section],

    retrySection: async (section: RhythmSection) => {
      const g = get()
      switch (section) {
        case 'dashboard':
          return g.fetchDashboard()
        case 'timeline':
          return g.fetchDayTimeline()
        case 'affairs':
        case 'ventures':
          return g.fetchAffairsByKind()
        case 'checkins':
          return g.fetchTodayCheckins()
        case 'review':
          return g.fetchReview('day').then(() => undefined)
        case 'config':
          return g.fetchEnergyProfile().then(() => undefined)
      }
    },

    fetchDashboard: async (date?: string | Date) => {
      const d = toISODate(date ?? get().selectedDate)
      // 在途合并：同日期并发调用（StrictMode 双调用 effect / 并发级联刷新）共享一次请求
      const inflight = dashboardInflight
      if (inflight && inflight.date === d) return inflight.promise

      const promise = (async () => {
        set({ isLoading: true, error: null })
        setSection('dashboard', { loading: true, error: null })
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
            inboxSummary: dashboard.inbox_summary,
            overdueSummary: dashboard.overdue_summary,
            todayDueSummary: dashboard.today_due_summary,
            degraded: dashboard.degraded ?? [],
            isLoading: false,
          })
          setSection('dashboard', { loading: false, error: null })
        } catch (error) {
          set({ isLoading: false, error: errorMessage(error) })
          setSection('dashboard', { loading: false, error: errorMessage(error) })
          throw error
        }
      })()

      dashboardInflight = { date: d, promise }
      try {
        await promise
      } finally {
        // 仅清理仍指向本次请求的表项（期间可能已有新日期请求取代）
        if (dashboardInflight?.promise === promise) dashboardInflight = null
      }
    },

    fetchDayTimeline: async (date?: string | Date) => {
      const d = toISODate(date ?? get().selectedDate)
      setSection('timeline', { loading: true, error: null })
      try {
        const timeline = await api_get_day_timeline(d)
        set({ dayTimeline: timeline })
        setSection('timeline', { loading: false, error: null })
      } catch (error) {
        setSection('timeline', { loading: false, error: errorMessage(error) })
        throw error
      }
    },

    fetchConflicts: async (date?: string | Date) => {
      const d = toISODate(date ?? get().selectedDate)
      try {
        const conflicts = await api_get_conflicts(d)
        set({ conflicts })
      } catch (error) {
        setSection('dashboard', { error: errorMessage(error) })
        throw error
      }
    },

    planDay: async (date?: string | Date, options?: PlanOptions) => {
      const d = toISODate(date ?? get().selectedDate)
      const result = await api_plan_day(d, options)
      // 级联：timeline + dashboard（含 conflicts/摘要）同步刷新
      await refreshBestEffort(async () => {
        await Promise.all([get().fetchDayTimeline(d), get().fetchDashboard(d)])
      })
      return result
    },

    rebalanceDay: async (date?: string | Date, trigger = 'manual') => {
      const d = toISODate(date ?? get().selectedDate)
      const result = await api_rebalance_day(d, trigger)
      await refreshBestEffort(async () => {
        await Promise.all([get().fetchDayTimeline(d), get().fetchDashboard(d)])
      })
      return result
    },

    fetchReview: async (scope: 'day' | 'week', dateOrSpan?: string) => {
      const d = dateOrSpan ?? (scope === 'day' ? get().selectedDate : undefined)
      setSection('review', { loading: true, error: null })
      try {
        const review =
          scope === 'day' ? await api_get_day_review(d!) : await api_get_week_review(d)
        set(scope === 'day' ? { dayReview: review } : { weekReview: review })
        setSection('review', { loading: false, error: null })
        return review
      } catch (error) {
        setSection('review', { loading: false, error: errorMessage(error) })
        throw error
      }
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
      setSection('checkins', { loading: true, error: null })
      try {
        const checkins = await api_get_today_checkins(date)
        set({ todayCheckins: checkins })
        setSection('checkins', { loading: false, error: null })
      } catch (error) {
        setSection('checkins', { loading: false, error: errorMessage(error) })
        throw error
      }
    },

    checkin: async (affairId: number, result: CheckinResultValue, note?: string, date?: Date) => {
      const log = await api_checkin({ affair_id: affairId, result, note, log_date: date })
      // 级联：今日打卡 + 日评分 + dashboard 同步刷新
      await refreshBestEffort(async () => {
        await get().fetchTodayCheckins(date)
      })
      await refreshBestEffort(async () => {
        await get().fetchReview('day')
      })
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
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
      setSection('config', { loading: true, error: null })
      try {
        const profile = await api_get_energy_profile()
        set({ energyProfile: profile })
        setSection('config', { loading: false, error: null })
      } catch (error) {
        setSection('config', { loading: false, error: errorMessage(error) })
        throw error
      }
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
      setSection('affairs', { loading: true, error: null })
      setSection('ventures', { loading: true, error: null })
      try {
        // 单请求拉全量非终态事务（state/kind 均支持多值数组），再按 kind 分片
        const all = await api_get_affairs({ kind: BOARD_KINDS, state: BOARD_STATES })
        set({
          allAffairs: all,
          activeAffairs: all,
          ventures: filterByKind(all, AffairKind.VENTURE),
          habits: filterByKind(all, AffairKind.HABIT),
          precepts: filterByKind(all, AffairKind.PRECEPT),
          maintenanceTasks: filterByKind(all, AffairKind.TASK_MAINTENANCE),
          asyncCallbacks: filterByKind(all, AffairKind.ASYNC_CALLBACK),
        })
        setSection('affairs', { loading: false, error: null })
        setSection('ventures', { loading: false, error: null })
      } catch (error) {
        const message = errorMessage(error)
        setSection('affairs', { loading: false, error: message })
        setSection('ventures', { loading: false, error: message })
        throw error
      }
    },

    setAffairFilters: (patch: Partial<AffairFilterState>) => {
      set((state) => ({ affairFilters: { ...state.affairFilters, ...patch } }))
    },

    resetAffairFilters: () => {
      set({ affairFilters: initialAffairFilters() })
    },

    createAffair: async (props: AffairCreateProps) => {
      const affair = await api_create_affair(props)
      set((state) => ({
        allAffairs: [...state.allAffairs, affair],
        inbox: affair.state === 'INBOX' ? [...state.inbox, affair] : state.inbox,
      }))
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
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
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
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
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
      return affair
    },

    deleteAffair: async (id: number) => {
      await api_delete_affair(id)
      set((state) => removeAffairFromLists(state, id))
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
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
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
      return affair
    },

    splitAffair: async (id: number, children: Record<string, unknown>[]) => {
      // 调用方以宽松 Record 构造子事务字段，由后端 DTO 校验兜底
      const res = await api_split_affair(id, {
        children: children as unknown as Parameters<typeof api_split_affair>[1]['children'],
      })
      set((state) => ({
        allAffairs: [...state.allAffairs, ...res.affairs],
        inbox: [...state.inbox, ...res.affairs.filter((a) => a.state === 'INBOX')],
      }))
      await refreshBestEffort(async () => {
        await get().fetchDashboard()
      })
      return res.affairs
    },

    setBlockStatus: async (blockId: number, status: BlockStatusValue) => {
      await api_set_block_status(blockId, status)
      // 级联：时间线 + 日评分同步刷新
      await refreshBestEffort(async () => {
        await get().fetchDayTimeline()
      })
      await refreshBestEffort(async () => {
        await get().fetchReview('day')
      })
    },

    moveBlock: async (blockId: number, start: Date, end: Date) => {
      await api_move_block(blockId, start, end)
      await refreshBestEffort(async () => {
        await get().fetchDayTimeline()
      })
      await refreshBestEffort(async () => {
        await get().fetchReview('day')
      })
    },

    createBlock: async (data: Record<string, unknown>) => {
      await api_create_time_block(data)
      await refreshBestEffort(async () => {
        await get().fetchDayTimeline()
      })
      await refreshBestEffort(async () => {
        await get().fetchReview('day')
      })
    },

    recalibrateProfile: async () => {
      // 校准：把当前画像数据提交给 recalibrate 端点；
      // 后端强制写 default 画像并清除 is_default 标记（响应带回最新值）。
      const current = get().energyProfile
      const profile = await api_recalibrate_profile({
        daily_energy_budget: current?.daily_energy_budget,
        curve_template: current?.curve_template,
        sleep_start: current?.sleep_start,
        sleep_end: current?.sleep_end,
        work_hours_cap: current?.work_hours_cap,
        spare_time_windows: current?.spare_time_windows,
        min_buffer_ratio: current?.min_buffer_ratio,
        life_weight: current?.life_weight,
        work_weight: current?.work_weight,
        career_weight: current?.career_weight,
        score_weights: current?.score_weights,
      })
      set({ energyProfile: profile })
      return profile
    },

    ensureDefaultTemplates: async () => {
      return api_ensure_default_templates()
    },

    clearError: () => set({ error: null, sections: initialSections() }),
  }
})
