/**
 * @file pems.ts
 * @brief Personal Energy Management System API (mapped to Rhythm API)
 * @author sailing-innocent
 * @date 2026-03-01
 *
 * PEMS 已合并进 Rhythm 模块。本文件保留站点 view model 的前端封装，
 * 底层调用 /api/v1/rhythm/* 系列接口。
 */

import { SERVER_URL, API_BASE } from './config'
import type {
  DayViewData,
  TimeSpanViewData,
  EnergyBudgetData,
  InsightData,
  HealthQuickLogProps,
  TimeSpanReviewProps,
  RhythmDayViewData,
  HealthCheckinRequestData,
  EnergyProfileData,
  ReviewData,
} from '@lib/data/pems'
import {
  transformRhythmDayView,
  transformReviewToInsights,
} from '@lib/data/pems'

const RHYTHM_API_BASE = API_BASE + '/rhythm'

const formatDate = (date: Date | string): string => {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toISOString().split('T')[0]
}

const buildUrl = (path: string, query?: Record<string, string>): string => {
  const url = new URL(`${SERVER_URL}/${RHYTHM_API_BASE}${path}`)
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, v)
      }
    })
  }
  return url.toString()
}

const checkOk = async (response: Response, action: string): Promise<void> => {
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`Error ${action}: ${response.status} ${response.statusText}${text ? ` - ${text.slice(0, 200)}` : ''}`)
  }
}

const fetchDayViewRaw = async (date: Date | string): Promise<RhythmDayViewData> => {
  const response = await fetch(buildUrl('/timeline/day-view', { date: formatDate(date) }))
  await checkOk(response, 'fetching day view')
  return response.json()
}

export const api_get_day_view = async (date: Date | string): Promise<DayViewData> => {
  const raw = await fetchDayViewRaw(date)
  return transformRhythmDayView(raw)
}

export const api_plan_day = async (
  date: Date | string
): Promise<DayViewData> => {
  const response = await fetch(buildUrl('/plan/day'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date: formatDate(date), preserve_done: true }),
  })
  await checkOk(response, 'planning day')
  return api_get_day_view(date)
}

export const api_log_health_on_day = async (
  date: Date | string,
  log: HealthQuickLogProps
): Promise<DayViewData> => {
  const dateStr = formatDate(date)
  const note = log.note || ''
  const requests: HealthCheckinRequestData[] = []

  if (log.sleep_hours !== undefined || log.sleep_quality !== undefined) {
    requests.push({
      collection_type: 'sleep',
      log_date: dateStr,
      payload: {
        hours: log.sleep_hours ?? 7,
        quality: log.sleep_quality ?? 3,
      },
      note,
    })
  }

  if (log.energy_level !== undefined) {
    requests.push({
      collection_type: 'energy',
      log_date: dateStr,
      payload: { score: log.energy_level },
      note,
    })
  }

  if (log.mood !== undefined) {
    requests.push({
      collection_type: 'mood',
      log_date: dateStr,
      payload: { score: log.mood },
      note,
    })
  }

  if (requests.length === 0) {
    return api_get_day_view(date)
  }

  await Promise.all(
    requests.map((body) =>
      fetch(buildUrl('/checkin/health'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then((r) => checkOk(r, 'logging health'))
    )
  )

  return api_get_day_view(date)
}

export const api_get_timespan_view = async (spanId: number): Promise<TimeSpanViewData> => {
  const response = await fetch(buildUrl(`/review/timespan/${spanId}`))
  await checkOk(response, 'fetching timespan view')
  const data = (await response.json()) as Record<string, unknown>
  return {
    id: (data.timespan_id as number) || spanId,
    class_: (data.scope as string) || '',
    name: (data.period_key as string) || '',
    start_date: '',
    end_date: '',
    theme: null,
    energy_capacity: 0,
    energy_consumed: 0,
    venture_ids: [],
    health_goals: {},
    review_note: (data.ai_summary as string) || null,
    focus_areas: [],
    day_count: 0,
  }
}

export const api_review_timespan = async (
  spanId: number,
  review: TimeSpanReviewProps
): Promise<TimeSpanViewData> => {
  const viewResp = await fetch(buildUrl(`/review/timespan/${spanId}`))
  await checkOk(viewResp, 'fetching timespan view')
  const view = (await viewResp.json()) as Record<string, unknown>
  const scope = String(view.scope || 'timespan')
  const periodKey = String(view.period_key || spanId)

  const response = await fetch(buildUrl(`/review/${scope}/${periodKey}/summary`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ai_summary: review.review_note,
      theme: review.theme,
      focus_areas: review.focus_areas,
    }),
  })
  await checkOk(response, 'reviewing timespan')
  return api_get_timespan_view(spanId)
}

export const api_get_energy_budget = async (
  date: Date | string
): Promise<EnergyBudgetData> => {
  const response = await fetch(buildUrl('/energy/profile'))
  await checkOk(response, 'fetching energy profile')
  const profile = (await response.json()) as EnergyProfileData
  const dayView = await api_get_day_view(date)
  return {
    ...dayView.energy_budget,
    base_energy: profile.daily_energy_budget,
    energy_budget: profile.daily_energy_budget,
  }
}

export const api_get_daily_insights = async (
  date: Date | string
): Promise<InsightData[]> => {
  const response = await fetch(buildUrl('/review/day', { date: formatDate(date) }))
  await checkOk(response, 'fetching daily insights')
  const review = (await response.json()) as ReviewData
  return transformReviewToInsights(review)
}

export const api_get_weekly_insights = async (
  date: Date | string
): Promise<InsightData[]> => {
  const d = typeof date === 'string' ? new Date(date) : date
  const iso = d.toISOString().split('T')[0]
  const response = await fetch(buildUrl('/review/week', { span: iso }))
  await checkOk(response, 'fetching weekly insights')
  const review = (await response.json()) as ReviewData
  return transformReviewToInsights(review)
}
