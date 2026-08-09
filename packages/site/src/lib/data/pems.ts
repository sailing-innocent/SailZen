/**
 * @file pems.ts
 * @brief Personal Energy Management System data types
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
