/**
 * @file pems.ts
 * @brief Personal Energy Management System data types (mapped to Rhythm API)
 * @author sailing-innocent
 * @date 2026-03-01
 */

export interface EnergyBudgetData {
  date: string
  day_id: number
  rhythm: string
  base_energy: number
  health_multiplier: number
  energy_budget: number
  energy_planned: number
  energy_actual: number
  warning_messages: string[]
}

export interface HealthSignalSummaryData {
  sleep_hours: number | null
  sleep_quality: number | null
  energy_level: number | null
  mood: number | null
  weight_value: number | null
  exercise_count: number
}

export interface PemsMissionBriefData {
  id: number
  name: string
  project_id: number | null
  project_name: string | null
  state: number
  energy_cost: number
  planned_minutes: number
  health_constraint: string
}

export interface InsightData {
  type: string
  severity: 'info' | 'warning' | 'danger'
  title: string
  message: string
}

export interface DayViewData {
  date: string
  day_id: number
  rhythm: string
  energy_budget: EnergyBudgetData
  health_signals: HealthSignalSummaryData
  planned_missions: PemsMissionBriefData[]
  completed_missions: PemsMissionBriefData[]
  challenge_checkins: Record<string, string>
  insights: InsightData[]
  note: string | null
}

export interface TimeSpanViewData {
  id: number
  class_: string
  name: string
  start_date: string
  end_date: string
  theme: string | null
  energy_capacity: number
  energy_consumed: number
  project_ids: number[]
  health_goals: Record<string, unknown>
  review_note: string | null
  focus_areas: string[]
  day_count: number
}

export interface ProjectTimelineData {
  project_id: number
  project_name: string
  timespan_id: number | null
  energy_budget: number
  milestones: Array<{
    id: number
    name: string
    date: string | null
    state: number
    energy_weight: number
  }>
  missions: PemsMissionBriefData[]
  timelogs: Array<{
    id: number
    mission_id: number
    day_id: number
    duration_minutes: number
    energy_cost: number
    description: string
  }>
}

export interface HealthQuickLogProps {
  sleep_hours?: number
  sleep_quality?: number
  energy_level?: number
  mood?: number
  note?: string
}

export interface PlanMissionProps {
  mission_id: number
}

export interface TimeSpanReviewProps {
  review_note: string
  theme?: string
  focus_areas?: string[]
}

export const RhythmLabels: Record<string, string> = {
  workday: '工作日',
  restday: '休息日',
  holiday: '假期',
  sick: '病休',
  travel: '出行',
  focus: '专注日',
}

export const RhythmColors: Record<string, string> = {
  workday: 'bg-blue-100 text-blue-700',
  restday: 'bg-green-100 text-green-700',
  holiday: 'bg-yellow-100 text-yellow-700',
  sick: 'bg-red-100 text-red-700',
  travel: 'bg-purple-100 text-purple-700',
  focus: 'bg-indigo-100 text-indigo-700',
}

// ============================================================================
// Raw Rhythm API types (PEMS has been merged into Rhythm)
// ============================================================================

export interface TimeBlockData {
  id: number
  day_id: number
  affair_id: number | null
  block_type: string
  start_time: string
  end_time: string
  status: string
  pinned: boolean
  plan_version: number
  ref: Record<string, unknown>
  affair_title: string | null
  affair_kind: string | null
  energy_cost: number
  ctime?: string
  mtime?: string
}

export interface DomainMinutesData {
  life: number
  work: number
  career: number
}

export interface HealthSignalItemData {
  signal_type: string
  ref_id: number
  value_json: Record<string, unknown>
  htime: string | null
}

export interface CheckinTodayItemData {
  affair: Record<string, unknown>
  done_today: boolean
  last_result: string | null
  week_done_count?: number
  week_target?: number
}

export interface CheckinTodayData {
  date: string
  precepts: CheckinTodayItemData[]
  habits: CheckinTodayItemData[]
}

export interface RhythmDayViewData {
  date: string
  day_id: number
  plan_version: number
  blocks: TimeBlockData[]
  domain_minutes: DomainMinutesData
  energy_consumed: number
  energy_budget: number
  energy_available: number
  buffer_total_minutes: number
  buffer_free_minutes: number
  checkins: CheckinTodayData | null
  health_signals: HealthSignalItemData[]
  insights: string[]
  warnings: string[]
  note: string | null
}

export interface HealthCheckinRequestData {
  collection_type: 'weight' | 'meal' | 'exercise' | 'medication' | 'sleep' | 'mood' | 'energy'
  log_date?: string
  payload: Record<string, unknown>
  note?: string
}

export interface HealthCheckinResponseData {
  id: number
  collection_type: string
  log_date: string
  ref_id: number | null
  affair_id: number | null
  note: string
  created_at?: string
}

export interface EnergyProfileData {
  id: number
  name: string
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
  ctime?: string
  mtime?: string
}

export interface ReviewData {
  id?: number
  scope: string
  period_key: string
  rhythm_score: number
  domain_minutes: Record<string, number>
  precept_compliance_rate: number
  habit_consistency: number
  sleep_window_keeping: number
  venture_budget_fulfillment: number
  buffer_consumed: number
  encroachments: unknown[]
  ai_summary: string
}

// ============================================================================
// Transformers: Rhythm DTO -> legacy PEMS view model (used by site UI)
// ============================================================================

function blockStatusToState(status: string): number {
  if (status === 'done') return 2
  if (status === 'skipped' || status === 'cancelled') return 3
  return 1
}

function deriveRhythm(date: string): string {
  const d = new Date(date)
  const day = d.getDay()
  return day === 0 || day === 6 ? 'restday' : 'workday'
}

export function transformRhythmDayView(raw: RhythmDayViewData): DayViewData {
  const planned_missions: PemsMissionBriefData[] = []
  const completed_missions: PemsMissionBriefData[] = []

  for (const b of raw.blocks) {
    if (!b.affair_id) continue
    const mission: PemsMissionBriefData = {
      id: b.id,
      name: b.affair_title || '未命名',
      project_id: null,
      project_name: null,
      state: blockStatusToState(b.status),
      energy_cost: b.energy_cost,
      planned_minutes: 0,
      health_constraint: '',
    }
    if (b.status === 'done' || b.status === 'skipped') {
      completed_missions.push(mission)
    } else {
      planned_missions.push(mission)
    }
  }

  const health: HealthSignalSummaryData = {
    sleep_hours: null,
    sleep_quality: null,
    energy_level: null,
    mood: null,
    weight_value: null,
    exercise_count: 0,
  }
  for (const s of raw.health_signals) {
    const v = s.value_json
    if (s.signal_type === 'sleep') {
      health.sleep_hours = typeof v.hours === 'number' ? v.hours : null
      health.sleep_quality = typeof v.quality === 'number' ? v.quality : null
    } else if (s.signal_type === 'mood') {
      health.mood = typeof v.score === 'number' ? v.score : null
    } else if (s.signal_type === 'energy') {
      health.energy_level = typeof v.score === 'number' ? v.score : null
    } else if (s.signal_type === 'weight') {
      health.weight_value = typeof v.value_kg === 'number' ? v.value_kg : null
    } else if (s.signal_type === 'exercise') {
      health.exercise_count += 1
    }
  }

  const insights: InsightData[] = raw.insights.map((text) => ({
    type: 'info',
    severity: 'info',
    title: text,
    message: '',
  }))
  raw.warnings.forEach((text) =>
    insights.push({
      type: 'warning',
      severity: 'warning',
      title: text,
      message: '',
    })
  )

  const rhythm = deriveRhythm(raw.date)
  const energyBudget: EnergyBudgetData = {
    date: raw.date,
    day_id: raw.day_id,
    rhythm,
    base_energy: raw.energy_budget,
    health_multiplier: 100,
    energy_budget: raw.energy_budget,
    energy_planned: raw.energy_budget - raw.energy_available,
    energy_actual: raw.energy_consumed,
    warning_messages: raw.warnings,
  }

  return {
    date: raw.date,
    day_id: raw.day_id,
    rhythm,
    energy_budget: energyBudget,
    health_signals: health,
    planned_missions,
    completed_missions,
    challenge_checkins: {},
    insights,
    note: raw.note,
  }
}

export function transformReviewToInsights(review: ReviewData): InsightData[] {
  const insights: InsightData[] = []
  if (review.ai_summary) {
    insights.push({
      type: 'info',
      severity: 'info',
      title: 'AI 复盘',
      message: review.ai_summary,
    })
  }
  if (review.rhythm_score < 60) {
    insights.push({
      type: 'warning',
      severity: 'warning',
      title: '节奏评分偏低',
      message: `当前节奏评分 ${review.rhythm_score.toFixed(0)}，建议回顾今日安排。`,
    })
  }
  if (review.buffer_consumed > 80) {
    insights.push({
      type: 'danger',
      severity: 'danger',
      title: '缓冲过度消耗',
      message: '今日缓冲时间已消耗超过 80%，请保留恢复空间。',
    })
  }
  return insights
}
