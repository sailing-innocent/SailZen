/**
 * @file rhythm.ts
 * @brief Rhythm v2 API Client (极简可视化日程画布 + 重要项目倒排 + 占用 + 轻量打卡)
 */

import { SERVER_URL, API_BASE, authHeaders, ApiError, parseErrorDetail } from './config'
import type {
  BlockStatusValue,
  CheckinLogData,
  CheckinResultValue,
  CheckinTodayData,
  DayTimelineData,
  OccupancyData,
  OccupancyTypeValue,
  RhythmDashboardData,
  TimeBlockData,
  VentureProgressData,
} from '@lib/data/rhythm'
import { toIsoDdl } from '@lib/data/affair'

const RHYTHM_API_BASE = API_BASE + '/rhythm'

const buildUrl = (path: string, query?: Record<string, unknown>): string => {
  const base =
    SERVER_URL || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost')
  const url = new URL(`${SERVER_URL}/${RHYTHM_API_BASE}${path}`, base)
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return
      url.searchParams.set(k, String(v))
    })
  }
  return url.toString()
}

const checkOk = async (response: Response, action: string): Promise<void> => {
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new ApiError(response.status, `${action}: ${response.statusText}`, parseErrorDetail(text))
  }
}

export const toISODate = (d: Date | string): string => {
  if (typeof d === 'string') return d.split('T')[0]
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const requestInit = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json', ...authHeaders() },
  body: body !== undefined ? JSON.stringify(body) : undefined,
})

const getInit = (): RequestInit => ({ headers: authHeaders() })

export const api_get_dashboard = async (date: Date | string): Promise<RhythmDashboardData> => {
  const response = await fetch(buildUrl('/dashboard', { date: toISODate(date) }), getInit())
  await checkOk(response, 'fetching dashboard')
  return response.json()
}

export const api_get_day_timeline = async (date: Date | string): Promise<DayTimelineData> => {
  const response = await fetch(buildUrl('/timeline/day', { date: toISODate(date) }), getInit())
  await checkOk(response, 'fetching day timeline')
  return response.json()
}

export const api_create_time_block = async (
  data: Record<string, unknown>,
): Promise<TimeBlockData> => {
  const response = await fetch(buildUrl('/timeline/block'), requestInit('POST', data))
  await checkOk(response, 'creating time block')
  return response.json()
}

export const api_delete_time_block = async (id: number): Promise<void> => {
  const response = await fetch(buildUrl(`/timeline/block/${id}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await checkOk(response, `deleting block ${id}`)
}

export const api_set_block_status = async (
  id: number,
  status: BlockStatusValue,
): Promise<TimeBlockData> => {
  const response = await fetch(
    buildUrl(`/timeline/block/${id}/status`),
    requestInit('POST', { status }),
  )
  await checkOk(response, `setting block ${id} status`)
  return response.json()
}

export const api_move_block = async (
  id: number,
  start_time: Date | string | number,
  end_time: Date | string | number,
): Promise<TimeBlockData> => {
  const response = await fetch(
    buildUrl(`/timeline/block/${id}/move`),
    requestInit('POST', { start_time: toIsoDdl(start_time), end_time: toIsoDdl(end_time) }),
  )
  await checkOk(response, `moving block ${id}`)
  return response.json()
}

export const api_list_projects = async (): Promise<VentureProgressData[]> => {
  const response = await fetch(buildUrl('/venture/projects'), getInit())
  await checkOk(response, 'fetching projects')
  return response.json()
}

export const api_add_venture_milestone = async (
  ventureId: number,
  data: { title: string; description?: string; est_minutes?: number; urgency_ddl?: string },
): Promise<unknown> => {
  const response = await fetch(
    buildUrl(`/venture/${ventureId}/milestone`),
    requestInit('POST', data),
  )
  await checkOk(response, `adding milestone to venture ${ventureId}`)
  return response.json()
}

export const api_mark_milestone_done = async (milestoneId: number): Promise<unknown> => {
  const response = await fetch(
    buildUrl(`/venture/milestone/${milestoneId}/done`),
    requestInit('POST'),
  )
  await checkOk(response, `marking milestone ${milestoneId} done`)
  return response.json()
}

export const api_create_occupancy = async (data: {
  date: Date | string
  occupancy_type: OccupancyTypeValue
  start?: string
  end?: string
  whole_day?: boolean
  label?: string
  note?: string
}): Promise<OccupancyData> => {
  const response = await fetch(
    buildUrl('/occupancy/'),
    requestInit('POST', { ...data, date: toISODate(data.date) }),
  )
  await checkOk(response, 'creating occupancy')
  return response.json()
}

export const api_delete_occupancy = async (blockId: number): Promise<void> => {
  const response = await fetch(buildUrl(`/occupancy/${blockId}`), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await checkOk(response, `deleting occupancy ${blockId}`)
}

export const api_get_today_checkins = async (date?: Date | string): Promise<CheckinTodayData> => {
  const response = await fetch(
    buildUrl('/checkin/today', date ? { date: toISODate(date) } : undefined),
    getInit(),
  )
  await checkOk(response, 'fetching today checkins')
  return response.json()
}

export const api_checkin = async (
  affair_id: number,
  result: CheckinResultValue,
  log_date?: Date | string,
  note = '',
): Promise<CheckinLogData> => {
  const response = await fetch(
    buildUrl('/checkin/'),
    requestInit('POST', {
      affair_id,
      result,
      log_date: log_date ? toISODate(log_date) : undefined,
      note,
    }),
  )
  await checkOk(response, 'checking in')
  return response.json()
}
