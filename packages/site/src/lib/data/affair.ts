/**
 * @file affair.ts
 * @brief Rhythm Affair data types and helpers
 * @description
 *   统一事务模型 `rhythm_affairs` 的数据类型、状态常量与工具函数。
 *   本文件取代旧的 `project.ts` 中 Project/Mission 类型，作为 site 端
 *   任务看板、待办列表、打卡挑战的唯一数据源。
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
  mission_id?: number | null
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
  mission_id: number | null
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
// 状态映射（旧 Project/Mission → Affair）
// ============================================================================

/** projects.state（旧数字枚举） → AffairState */
export function projectStateToAffairState(state: number | undefined): AffairStateValue {
  switch (state) {
    case 3: return AffairState.ACTIVE
    case 4: return AffairState.PAUSED
    case 5: return AffairState.DONE
    case 0:
    case 6:
      return AffairState.ARCHIVED
    case 1:
    case 2:
    default:
      return AffairState.INBOX
  }
}

/** missions.state（旧数字枚举） → AffairState */
export function missionStateToAffairState(state: number | undefined): AffairStateValue {
  switch (state) {
    case 1: return AffairState.PLANNED
    case 2: return AffairState.DOING
    case 3: return AffairState.DONE
    case 4: return AffairState.CANCELED
    case 0:
    default:
      return AffairState.INBOX
  }
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
    // 秒级时间戳（兼容旧 missions.ddl）
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

// ============================================================================
// 兼容性类型别名（供部分旧组件名平滑过渡，不新增运行时依赖）
// ============================================================================

/** 旧组件中 mission/project 的 `name` 语义等价于 Affair `title` */
export type VentureData = AffairData
export type TaskData = AffairData
