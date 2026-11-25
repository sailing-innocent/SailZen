/**
 * @file rhythm.ts
 * @brief Rhythm v2 DTO types (极简可视化日程画布 + 重要项目倒排 + 占用 + 轻量打卡)
 */

import type { AffairData, AffairDomainValue, AffairKindValue } from './affair'

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
  OCCUPIED: 'occupied',
} as const
export type BlockTypeValue = (typeof BlockType)[keyof typeof BlockType]

export const BlockStatus = {
  PLANNED: 'PLANNED',
  DOING: 'DOING',
  DONE: 'DONE',
  SKIPPED: 'SKIPPED',
  MOVED: 'MOVED',
} as const
export type BlockStatusValue = (typeof BlockStatus)[keyof typeof BlockStatus]

export const CheckinResult = {
  KEPT: 'kept',
  VIOLATED: 'violated',
  DONE: 'done',
  MISSED: 'missed',
  EXEMPT: 'exempt',
} as const
export type CheckinResultValue = (typeof CheckinResult)[keyof typeof CheckinResult]

export type OccupancyTypeValue = 'leave' | 'meeting' | 'appointment' | 'travel' | 'other'

export interface TimeBlockData {
  id: number
  day_id: number
  affair_id: number | null
  affair_title?: string | null
  affair_kind?: AffairKindValue | null
  affair_domain?: AffairDomainValue | null
  block_type: BlockTypeValue
  start_time: string
  end_time: string
  status: BlockStatusValue
  pinned: boolean
  plan_version: number
  ref: Record<string, unknown>
}

export interface DomainMinutesData {
  life: number
  work: number
  career: number
}

export interface CheckinTodayItemData {
  affair: AffairData
  done_today: boolean
  last_result: CheckinResultValue | null
  week_done_count: number
  week_target?: number | null
}

export interface CheckinTodayData {
  date: string
  precepts: CheckinTodayItemData[]
  habits: CheckinTodayItemData[]
}

export interface CheckinLogData {
  id: number
  affair_id: number
  log_date: string
  cycle_key: string
  result: CheckinResultValue
  note: string
  source: string
  created_at?: string | null
}

export interface DayTimelineData {
  date: string
  day_id: number
  plan_version: number
  ai_rationale: string
  ai_updated_at?: string | null
  blocks: TimeBlockData[]
  completed_minutes: number
  planned_minutes: number
  domain_minutes: DomainMinutesData
  checkins?: CheckinTodayData | null
}

export interface VentureProgressData {
  affair_id: number
  title: string
  description: string
  state: string
  target_date?: string | null
  days_left?: number | null
  weeks_left?: number | null
  weekly_budget_hours: number
  week_consumed_hours: number
  recent_14d_hours: number
  total_done_hours: number
  total_est_hours: number
  milestones: AffairData[]
  completion_ratio: number
}

export interface OccupancyData {
  id: number
  date: string
  start?: string | null
  end?: string | null
  whole_day: boolean
  occupancy_type: OccupancyTypeValue
  label: string
  note: string
}

export interface RhythmDashboardData {
  date: string
  timeline: DayTimelineData
  projects: VentureProgressData[]
  focus_affairs: AffairData[]
  overdue_affairs: AffairData[]
  inbox_affairs: AffairData[]
  occupancies: OccupancyData[]
  today_checkins: CheckinTodayData
  degraded: string[]
}
