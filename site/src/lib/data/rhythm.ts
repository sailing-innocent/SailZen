/**
 * @file rhythm.ts
 * @brief Rhythm Dashboard DTO types
 * @description
 *   映射后端 `/api/v1/rhythm/*` 的响应字段，供 Dashboard、时间线、复盘统计使用。
 *   字段名与后端 DTO 保持一致，便于双端契约维护。
 */

import type { AffairData, AffairKindValue, AffairDomainValue, AffairStateValue } from './affair'

// ============================================================================
// Enums / value types
// ============================================================================

export const BlockType = {
  SLEEP: 'sleep',
  COMMUTE: 'commute',
  WORK_WINDOW: 'work_window',
  MICRO_REST: 'micro_rest',
  MEAL: 'meal',
  PRECEPT: 'precept',
  HABIT: 'habit',
  FIXED: 'fixed',
  FOCUS: 'focus',
  LIGHT: 'light',
  CAREER: 'career',
  REST: 'rest',
  BUFFER: 'buffer',
  ASYNC_KICKOFF: 'async_kickoff',
  ASYNC_REVIEW: 'async_review',
  ASYNC_WAIT: 'async_wait',
} as const
export type BlockTypeValue = typeof BlockType[keyof typeof BlockType]

export const BlockStatus = {
  PLANNED: 'PLANNED',
  DOING: 'DOING',
  DONE: 'DONE',
  SKIPPED: 'SKIPPED',
  MOVED: 'MOVED',
} as const
export type BlockStatusValue = typeof BlockStatus[keyof typeof BlockStatus]

export const PolicyRuleType = {
  PROTECT_WINDOW: 'protect_window',
  DOMAIN_CAP: 'domain_cap',
  KIND_MIN_FREQ: 'kind_min_freq',
  MAX_CONSECUTIVE_FOCUS: 'max_consecutive_focus',
  SPARE_TIME_GUARD: 'spare_time_guard',
} as const
export type PolicyRuleTypeValue = typeof PolicyRuleType[keyof typeof PolicyRuleType]

export const CheckinResult = {
  KEPT: 'kept',
  VIOLATED: 'violated',
  DONE: 'done',
  MISSED: 'missed',
  EXEMPT: 'exempt',
} as const
export type CheckinResultValue = typeof CheckinResult[keyof typeof CheckinResult]

// ============================================================================
// TimeBlock / Timeline
// ============================================================================

export interface TimeBlockData {
  id: number
  day_id: number
  affair_id: number | null
  block_type: BlockTypeValue
  start_time: string
  end_time: string
  status: BlockStatusValue
  pinned: boolean
  plan_version: number
  ref: Record<string, unknown>
  affair_title?: string | null
  affair_kind?: AffairKindValue | null
  energy_cost: number
  ctime?: string
  mtime?: string
}

export interface DomainMinutesData {
  life: number
  work: number
  career: number
}

export interface DayTimelineData {
  date: string
  day_id: number
  plan_version: number
  blocks: TimeBlockData[]
  domain_minutes: DomainMinutesData
  energy_consumed: number
  energy_budget: number
  buffer_total_minutes: number
  buffer_free_minutes: number
  checkins?: CheckinTodayData
  warnings: string[]
  unplaced?: UnplacedItemData[]
}

// ============================================================================
// Plan
// ============================================================================

export interface PlanWarningData {
  code: string
  message: string
  affair_id?: number | null
}

export interface UnplacedItemData {
  affair_id: number
  title: string
  reason: string
}

export interface PlanDayData {
  date: string
  day_id: number
  plan_version: number
  blocks: TimeBlockData[]
  warnings: PlanWarningData[]
  unplaced: UnplacedItemData[]
}

export interface PlanOptions {
  preserve_done?: boolean
  force?: boolean
}

// ============================================================================
// Checkin
// ============================================================================

export interface CheckinLogData {
  id: number
  affair_id: number
  log_date: string
  cycle_key: string
  result: CheckinResultValue
  note: string
  source: string
  created_at?: string
}

export interface CheckinTodayItemData {
  affair: AffairData
  done_today: boolean
  last_result?: CheckinResultValue | null
  week_done_count?: number
  week_target?: number
}

export interface CheckinTodayData {
  date: string
  precepts: CheckinTodayItemData[]
  habits: CheckinTodayItemData[]
}

export interface HabitHeatmapItemData {
  date: string
  cycle_key: string
  result?: CheckinResultValue | null
  done: boolean
}

export interface HabitHeatmapData {
  affair_id: number
  start_date: string
  end_date: string
  days: HabitHeatmapItemData[]
}

// ============================================================================
// Energy / Policy / Template
// ============================================================================

export interface EnergyProfileData {
  id: number
  name: string
  is_default: boolean
  daily_energy_budget: number
  curve_template: Record<string, unknown>
  sleep_start: string
  sleep_end: string
  work_hours_cap: number
  spare_time_windows: Record<string, unknown>
  min_buffer_ratio: number
  life_weight: number
  work_weight: number
  career_weight: number
  score_weights: Record<string, unknown>
  updated_at?: string
}

export interface EnergyProfileUpdateProps {
  name?: string
  daily_energy_budget?: number
  curve_template?: Record<string, unknown>
  sleep_start?: string
  sleep_end?: string
  work_hours_cap?: number
  spare_time_windows?: Record<string, unknown>
  min_buffer_ratio?: number
  life_weight?: number
  work_weight?: number
  career_weight?: number
  score_weights?: Record<string, unknown>
}

export interface PolicyData {
  id: number
  name: string
  enabled: boolean
  rule_type: PolicyRuleTypeValue
  params: Record<string, unknown>
  scope: string
  ctime?: string
  mtime?: string
}

export interface PolicyCreateProps {
  name: string
  rule_type: PolicyRuleTypeValue | string
  params?: Record<string, unknown>
  scope?: string
  enabled?: boolean
}

export interface PolicyUpdateProps {
  name?: string
  rule_type?: PolicyRuleTypeValue | string
  params?: Record<string, unknown>
  scope?: string
  enabled?: boolean
}

export interface TemplateSlotData {
  label: string
  start: string
  end: string
  block_type: BlockTypeValue
  micro_cycle?: Record<string, number> | null
}

export interface DayTemplateData {
  id: number
  name: string
  description: string
  weekday_mask: number[]
  slots: Record<string, unknown>[]
  enabled: boolean
  priority: number
  ctime?: string
  mtime?: string
}

export interface DayTemplateCreateProps {
  name: string
  description?: string
  weekday_mask?: number[]
  slots?: Record<string, unknown>[]
  enabled?: boolean
  priority?: number
}

// ============================================================================
// Review / Conflict
// ============================================================================

export interface EncroachmentData {
  type: string
  message: string
  block_id?: number | null
  affair_id?: number | null
  date?: string | null
}

export interface ConflictReportData {
  date: string
  encroachments: EncroachmentData[]
}

export interface ReviewData {
  id?: number | null
  scope: string
  period_key: string
  rhythm_score: number
  domain_minutes: Record<string, number>
  precept_compliance_rate: number
  habit_consistency: number
  sleep_window_keeping: number
  venture_budget_fulfillment: number
  buffer_consumed: number
  encroachments: EncroachmentData[]
  ai_summary: string
  created_at?: string
}

export interface DomainTrendItemData {
  date: string
  life: number
  work: number
  career: number
}

export interface DomainTrendData {
  start_date: string
  end_date: string
  days: DomainTrendItemData[]
}

// ============================================================================
// Dashboard aggregate
// ============================================================================

export interface PriorityAffairItemData {
  affair: AffairData
  reason: string
  suggested_slot?: string | null
}

export interface RhythmDashboardData {
  date: string
  timeline: DayTimelineData
  day_review: ReviewData
  week_review: ReviewData
  today_checkins: CheckinTodayData
  energy_profile: EnergyProfileData
  policies: PolicyData[]
  conflicts: ConflictReportData
  inbox_summary: PriorityAffairItemData[]
  overdue_summary: PriorityAffairItemData[]
  today_due_summary: PriorityAffairItemData[]
}

// ============================================================================
// Venture
// ============================================================================

export interface VentureProgressData {
  affair_id: number
  title: string
  target_date?: string | null
  weeks_left?: number | null
  weekly_budget_hours: number
  week_consumed_hours: number
  total_done_hours: number
  total_est_hours: number
  countdown_pressure?: number | null
  milestones: AffairData[]
  completion_ratio: number
}

export interface VentureBurndownData {
  affair_id: number
  title: string
  weeks: string[]
  planned: number[]
  actual: number[]
  milestones_done: number[]
}

// ============================================================================
// Health checkin
// ============================================================================

export interface HealthCheckinData {
  id: number
  collection_type: string
  log_date: string
  ref_id?: number | null
  affair_id?: number | null
  note: string
  created_at?: string
}
