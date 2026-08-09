/**
 * @file pems.ts
 * @brief Personal Energy Management System API
 * @author sailing-innocent
 * @date 2026-03-01
 */

import { SERVER_URL, API_BASE } from './config'
import type {
  DayViewData,
  TimeSpanViewData,
  ProjectTimelineData,
  EnergyBudgetData,
  InsightData,
  HealthQuickLogProps,
  PlanMissionProps,
  TimeSpanReviewProps,
} from '@lib/data/pems'

const PEMS_API_BASE = API_BASE + '/pems'

const formatDate = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toISOString().split('T')[0]
}

export const api_get_day_view = async (date: Date | string): Promise<DayViewData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/day/${formatDate(date)}`)
  if (!response.ok) {
    throw new Error(`Error fetching day view: ${response.statusText}`)
  }
  return response.json()
}

export const api_plan_mission_on_day = async (
  date: Date | string,
  plan: PlanMissionProps
): Promise<DayViewData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/day/${formatDate(date)}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(plan),
  })
  if (!response.ok) {
    throw new Error(`Error planning mission: ${response.statusText}`)
  }
  return response.json()
}

export const api_log_health_on_day = async (
  date: Date | string,
  log: HealthQuickLogProps
): Promise<DayViewData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/day/${formatDate(date)}/health`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(log),
  })
  if (!response.ok) {
    throw new Error(`Error logging health: ${response.statusText}`)
  }
  return response.json()
}

export const api_get_timespan_view = async (spanId: number): Promise<TimeSpanViewData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/timespan/${spanId}`)
  if (!response.ok) {
    throw new Error(`Error fetching timespan view: ${response.statusText}`)
  }
  return response.json()
}

export const api_review_timespan = async (
  spanId: number,
  review: TimeSpanReviewProps
): Promise<TimeSpanViewData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/timespan/${spanId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(review),
  })
  if (!response.ok) {
    throw new Error(`Error reviewing timespan: ${response.statusText}`)
  }
  return response.json()
}

export const api_get_project_timeline = async (
  projectId: number
): Promise<ProjectTimelineData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/project/${projectId}/timeline`)
  if (!response.ok) {
    throw new Error(`Error fetching project timeline: ${response.statusText}`)
  }
  return response.json()
}

export const api_get_energy_budget = async (
  date: Date | string
): Promise<EnergyBudgetData> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/energy/budget?query_date=${formatDate(date)}`)
  if (!response.ok) {
    throw new Error(`Error fetching energy budget: ${response.statusText}`)
  }
  return response.json()
}

export const api_get_daily_insights = async (
  date: Date | string
): Promise<InsightData[]> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/insight/daily?query_date=${formatDate(date)}`)
  if (!response.ok) {
    throw new Error(`Error fetching daily insights: ${response.statusText}`)
  }
  return response.json()
}

export const api_get_weekly_insights = async (
  date: Date | string
): Promise<InsightData[]> => {
  const response = await fetch(`${SERVER_URL}/${PEMS_API_BASE}/insight/weekly?query_date=${formatDate(date)}`)
  if (!response.ok) {
    throw new Error(`Error fetching weekly insights: ${response.statusText}`)
  }
  return response.json()
}
