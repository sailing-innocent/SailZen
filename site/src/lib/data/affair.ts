/**
 * @file affair.ts
 * @brief Rhythm Affair data types and helpers
 * @description
 *   统一事务模型 `rhythm_affairs` 的数据类型、状态常量与工具函数。
 * 统一事务模型 `rhythm_affairs` 的数据类型、状态常量与工具函数。
 * 作为 site 端任务看板、待办列表、打卡挑战的唯一数据源。

 */

// ============================================================================
// Affair 域与种类常量
// ============================================================================

export const AffairDomain = {
  LIFE: 'life',
  WORK: 'work',
  CAREER: 'career',
} as const
export type AffairDomainValue = typeof AffairDomain[keyof typeof AffairDomain]

export const AffairKind = {
  BASE_RHYTHM: 'base_rhythm',
  PRECEPT: 'precept',
  HABIT: 'habit',
  FIXED_PLAN: 'fixed_plan',
  TASK_ONEOFF: 'task_oneoff',
  TASK_MAINTENANCE: 'task_maintenance',
  VENTURE: 'venture',
  ASYNC_CALLBACK: 'async_callback',
  BUFFER: 'buffer',
  GENERIC: 'generic',
} as const
export type AffairKindValue = typeof AffairKind[keyof typeof AffairKind]

// ============================================================================
// Affair 状态常量
// ============================================================================

export const AffairState = {
  INBOX: 'INBOX',
  PLANNED: 'PLANNED',
  SCHEDULED: 'SCHEDULED',
  DOING: 'DOING',
  DONE: 'DONE',
  DEFERRED: 'DEFERRED',
  CANCELED: 'CANCELED',
  ACTIVE: 'ACTIVE',
  PAUSED: 'PAUSED',
  ARCHIVED: 'ARCHIVED',
  KICKOFF: 'KICKOFF',
  DELEGATED: 'DELEGATED',
  REVIEWING: 'REVIEWING',
  COMPLETED: 'COMPLETED',
} as const
export type AffairStateValue = typeof AffairState[keyof typeof AffairState]

export const AffairStateLabels: Record<AffairStateValue, string> = {
  [AffairState.INBOX]: '待处理',
  [AffairState.PLANNED]: '已规划',
  [AffairState.SCHEDULED]: '已排期',
  [AffairState.DOING]: '进行中',
  [AffairState.DONE]: '已完成',
  [AffairState.DEFERRED]: '已延期',
  [AffairState.CANCELED]: '已取消',
  [AffairState.ACTIVE]: '进行中',
  [AffairState.PAUSED]: '已暂停',
  [AffairState.ARCHIVED]: '已归档',
  [AffairState.KICKOFF]: '启动中',
  [AffairState.DELEGATED]: '委托中',
  [AffairState.REVIEWING]: '审阅中',
  [AffairState.COMPLETED]: '已完成',
}

export const AffairStateColors: Record<AffairStateValue, string> = {
  [AffairState.INBOX]: 'bg-gray-500',
  [AffairState.PLANNED]: 'bg-blue-500',
  [AffairState.SCHEDULED]: 'bg-indigo-500',
  [AffairState.DOING]: 'bg-yellow-500',
  [AffairState.DONE]: 'bg-green-500',
  [AffairState.DEFERRED]: 'bg-purple-500',
  [AffairState.CANCELED]: 'bg-red-500',
  [AffairState.ACTIVE]: 'bg-blue-500',
  [AffairState.PAUSED]: 'bg-orange-500',
  [AffairState.ARCHIVED]: 'bg-gray-400',
  [AffairState.KICKOFF]: 'bg-blue-500',
  [AffairState.DELEGATED]: 'bg-purple-500',
  [AffairState.REVIEWING]: 'bg-yellow-500',
  [AffairState.COMPLETED]: 'bg-green-500',
}

/** 一次性任务终态（用于任务看板等 UI） */
export const TerminalAffairStates: readonly AffairStateValue[] = [
  AffairState.DONE,
  AffairState.CANCELED,
]

/** 长期事务终态 */
export const LongTermTerminalStates: readonly AffairStateValue[] = [
  AffairState.ARCHIVED,
  AffairState.DONE,
]

// ============================================================================
// 数据类型
// ============================================================================

export interface AffairCreateProps {
  title: string
  description?: string
  domain?: AffairDomainValue
  kind?: AffairKindValue
  kind_meta?: Record<string, unknown>
  state?: AffairStateValue
  importance?: number
  urgency_ddl?: string | number | Date | null
  energy_cost?: number
  money_cost?: number
  budget_id?: number | null
  est_minutes?: number
  window_start?: string | Date | null
  window_end?: string | Date | null
  splittable?: boolean
  min_chunk_minutes?: number
  fallback_plan?: string
  recurrence_rule_id?: number | null
  day_id?: number | null
  timespan_id?: number | null
  parent_id?: number | null
  info_collection_type?: string | null
  ref?: Record<string, unknown>
}

export interface AffairUpdateProps extends Partial<AffairCreateProps> {
  ai_hint?: Record<string, unknown>
}

export interface AffairData extends AffairCreateProps {
  id: number
  title: string
  description: string
  kind: AffairKindValue
  domain: AffairDomainValue
  state: AffairStateValue
  kind_meta: Record<string, unknown>
  importance: number
  urgency_ddl: string | number | null | undefined
  energy_cost: number
  money_cost: number
  budget_id: number | null
  est_minutes: number
  splittable: boolean
  min_chunk_minutes: number
  fallback_plan: string
  recurrence_rule_id: number | null
  day_id: number | null
  timespan_id: number | null
  parent_id: number | null
  info_collection_type: string | null
  ai_hint: Record<string, unknown>
  score: number
  ref: Record<string, unknown>
  ctime?: string | number
  mtime?: string | number
}

// ============================================================================
// DDL / 截止日期工具函数
// ============================================================================

function isValidDate(d: Date): boolean {
  return !isNaN(d.getTime())
}

export const parseDdl = (ddl: string | number | Date | null | undefined): Date | null => {
  if (ddl === undefined || ddl === null || ddl === '') return null
  if (ddl instanceof Date) return isValidDate(ddl) ? ddl : null
  if (typeof ddl === 'string') {
    const date = new Date(ddl)
    return isValidDate(date) ? date : null
  }
  if (typeof ddl === 'number') {
    const date = ddl < 946684800000 ? new Date(ddl * 1000) : new Date(ddl)
    return isValidDate(date) ? date : null
  }
  return null
}

export const getDdlTimestamp = (ddl: string | number | Date | null | undefined): number | null => {
  const date = parseDdl(ddl)
  if (!date) return null
  return Math.floor(date.getTime() / 1000)
}

export const isAffairOverdue = (ddl: string | number | Date | null | undefined, state?: AffairStateValue): boolean => {
  if (!state || TerminalAffairStates.includes(state)) return false
  // DEFERRED 已明确延期，不再按旧 deadline 显示逾期
  if (state === AffairState.DEFERRED) return false
  const ddlTimestamp = getDdlTimestamp(ddl)
  if (ddlTimestamp === null) return false
  const now = Math.floor(Date.now() / 1000)
  return ddlTimestamp < now
}

export const getHoursUntilDeadline = (ddl: string | number | Date | null | undefined): number => {
  const ddlTimestamp = getDdlTimestamp(ddl)
  if (ddlTimestamp === null) return Infinity
  const now = Math.floor(Date.now() / 1000)
  return (ddlTimestamp - now) / 3600
}

export const formatDeadline = (ddl: string | number | Date | null | undefined): string => {
  const date = parseDdl(ddl)
  if (!date) return '无截止日期'
  const now = new Date()
  const diffHours = (date.getTime() - now.getTime()) / (1000 * 60 * 60)

  if (diffHours < 0) {
    const overdueDays = Math.floor(Math.abs(diffHours) / 24)
    if (overdueDays > 0) {
      return `已逾期 ${overdueDays} 天`
    }
    return `已逾期 ${Math.floor(Math.abs(diffHours))} 小时`
  } else if (diffHours < 1) {
    return `${Math.floor(diffHours * 60)} 分钟后`
  } else if (diffHours < 24) {
    return `${Math.floor(diffHours)} 小时后`
  } else if (diffHours < 72) {
    return `${Math.floor(diffHours / 24)} 天后`
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
  }
}

// ============================================================================
// 状态与优先级判断
// ============================================================================

export const isAffairActive = (state: AffairStateValue | undefined): boolean => {
  if (!state) return true
  return !TerminalAffairStates.includes(state) && state !== AffairState.ARCHIVED
}

/**
 * 获取事务用于展示和判断逾期的有效截止时间。
 * DEFERRED 状态优先使用 window_start（延期后的新窗口）。
 */
export const getAffairDeadline = (
  affair: AffairData
): string | number | Date | null | undefined => {
  if (affair.state === AffairState.DEFERRED && affair.window_start) {
    return affair.window_start
  }
  return affair.urgency_ddl
}

// ============================================================================
// kind_meta 分类型强类型辅助
// ============================================================================

export interface PreceptMeta {
  rule_text: string
  cycle: 'daily' | 'weekly'
  weekday_mask: number[]
  check_time: string
  severity: 'hard' | 'soft'
  block_minutes: number
}

export interface HabitMeta {
  freq_per_week: number
  min_session_minutes: number
  preferred_slots: string[]
  streak: number
  best_streak: number
  last_done_date?: string | null
}

export interface MaintenanceMeta {
  interval_days: number
  last_done_at?: string | number | null
  session_minutes: number
}

export interface VentureMeta {
  target_date?: string | null
  weekly_budget_hours: number
  spare_time_only: boolean
  total_est_hours: number
}

export interface FixedPlanMeta {
  immovable: boolean
  fixed_start?: string | number | null
  fixed_end?: string | number | null
  legs: number[]
}

export interface AsyncCallbackPhase {
  name: string
  est_minutes: number
  energy_cost: number
}

export interface AsyncCallbackMeta {
  phases: AsyncCallbackPhase[]
  current_phase: string
  round: number
  max_rounds: number
  work_hours_only: boolean
  delegate_to: string
  est_wait_hours: number
  last_handoff_at?: string | null
  last_return_at?: string | null
  next_review_at?: string | null
  revision_history?: unknown[]
}

export type KindMetaMap = {
  base_rhythm: Record<string, unknown>
  precept: PreceptMeta
  habit: HabitMeta
  fixed_plan: FixedPlanMeta
  task_oneoff: Record<string, unknown>
  task_maintenance: MaintenanceMeta
  venture: VentureMeta
  async_callback: AsyncCallbackMeta
  buffer: Record<string, unknown>
  generic: Record<string, unknown>
}

export function getKindMeta<T extends AffairKindValue>(
  affair: AffairData,
  kind: T
): KindMetaMap[T] | undefined {
  if (affair.kind !== kind) return undefined
  return (affair.kind_meta ?? {}) as KindMetaMap[T]
}

export const defaultPreceptMeta = (): PreceptMeta => ({
  rule_text: '',
  cycle: 'daily',
  weekday_mask: [1, 1, 1, 1, 1, 1, 1],
  check_time: '22:30',
  severity: 'soft',
  block_minutes: 0,
})

export const defaultHabitMeta = (): HabitMeta => ({
  freq_per_week: 3,
  min_session_minutes: 30,
  preferred_slots: [],
  streak: 0,
  best_streak: 0,
  last_done_date: null,
})

export const defaultVentureMeta = (): VentureMeta => ({
  target_date: null,
  weekly_budget_hours: 6,
  spare_time_only: true,
  total_est_hours: 0,
})

export const defaultMaintenanceMeta = (): MaintenanceMeta => ({
  interval_days: 7,
  last_done_at: null,
  session_minutes: 60,
})

export const defaultFixedPlanMeta = (): FixedPlanMeta => ({
  immovable: true,
  fixed_start: null,
  fixed_end: null,
  legs: [],
})

export const defaultAsyncCallbackMeta = (): AsyncCallbackMeta => ({
  phases: [
    { name: 'kickoff', est_minutes: 30, energy_cost: 25 },
    { name: 'delegated', est_minutes: 0, energy_cost: 0 },
    { name: 'review', est_minutes: 20, energy_cost: 15 },
  ],
  current_phase: 'kickoff',
  round: 1,
  max_rounds: 3,
  work_hours_only: false,
  delegate_to: 'ai',
  est_wait_hours: 24,
  last_handoff_at: null,
  last_return_at: null,
  next_review_at: null,
  revision_history: [],
})

export function getDefaultKindMeta(kind: AffairKindValue): Record<string, unknown> {
  switch (kind) {
    case AffairKind.PRECEPT:
      return defaultPreceptMeta() as unknown as Record<string, unknown>
    case AffairKind.HABIT:
      return defaultHabitMeta() as unknown as Record<string, unknown>
    case AffairKind.VENTURE:
      return defaultVentureMeta() as unknown as Record<string, unknown>
    case AffairKind.TASK_MAINTENANCE:
      return defaultMaintenanceMeta() as unknown as Record<string, unknown>
    case AffairKind.FIXED_PLAN:
      return defaultFixedPlanMeta() as unknown as Record<string, unknown>
    case AffairKind.ASYNC_CALLBACK:
      return defaultAsyncCallbackMeta() as unknown as Record<string, unknown>
    default:
      return {}
  }
}

export type AffairPriority = 'urgent' | 'high' | 'normal' | 'low'

export const getAffairPriority = (
  ddl: string | number | Date | null | undefined,
  state?: AffairStateValue
): AffairPriority => {
  if (!state || !isAffairActive(state)) return 'low'
  if (isAffairOverdue(ddl, state)) return 'urgent'
  const hours = getHoursUntilDeadline(ddl)
  if (hours <= 2) return 'urgent'
  if (hours <= 24) return 'high'
  if (hours <= 72) return 'normal'
  return 'low'
}

// ============================================================================
// 日期 / target_date 工具
// ============================================================================

export const formatTargetDate = (targetDate: string | Date | null | undefined): string => {
  if (!targetDate) return ''
  const date = typeof targetDate === 'string' ? new Date(targetDate) : targetDate
  if (!isValidDate(date)) return ''
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
}

/** 将任意日期格式化为 ISO 日期字符串（用于 kind_meta.target_date） */
export const toISODate = (date: Date | string | number): string => {
  const d = date instanceof Date ? date : new Date(date)
  if (!isValidDate(d)) return ''
  return d.toISOString().split('T')[0]
}

/** 将 DDL 转换为后端可接受的 ISO datetime 字符串 */
export const toIsoDdl = (ddl: Date | string | number | null | undefined): string | null => {
  if (!ddl) return null
  const date = ddl instanceof Date ? ddl : parseDdl(ddl)
  if (!date) return null
  return date.toISOString()
}

