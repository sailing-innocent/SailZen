/**
 * @file rhythm.ts
 * @brief Rhythm Dashboard API client
 * @description
 *   封装 `/api/v1/rhythm/*` 的 REST 调用，覆盖 Timeline/Plan/Review/Template/
 *   Energy/Policy/Checkin/Admin/Stats 等 Dashboard 所需端点。
 */

import { SERVER_URL, API_BASE } from './config'
import type {
  DayTimelineData,
  DayTemplateData,
  PlanDayData,
  ReviewData,
  EnergyProfileData,
  EnergyProfileUpdateProps,
  PolicyData,
  PolicyCreateProps,
  PolicyUpdateProps,
  CheckinTodayData,
  CheckinLogData,
  ConflictReportData,
  EncroachmentData,
  RhythmDashboardData,
  HabitHeatmapData,
  DomainTrendData,
  VentureBurndownData,
  HealthCheckinData,
  PlanOptions,
  DayTemplateCreateProps,
  BlockStatusValue,
  CheckinResultValue,
  TimeBlockData,
} from '@lib/data/rhythm'
import { toIsoDdl } from '@lib/data/affair'

const RHYTHM_API_BASE = API_BASE + '/rhythm'

const buildUrl = (path: string, query?: Record<string, unknown>): string => {
  const url = new URL(`${SERVER_URL}/${RHYTHM_API_BASE}${path}`)
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v === undefined || v === null) return
      if (Array.isArray(v)) {
        v.forEach((item) => {
          if (item !== undefined && item !== null && item !== '') {
            url.searchParams.append(k, String(item))
          }
        })
      } else if (v !== '') {
        url.searchParams.set(k, String(v))
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

const toISODate = (d: Date | string): string => {
  if (typeof d === 'string') return d.split('T')[0]
  return d.toISOString().split('T')[0]
}

const requestInit = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body !== undefined ? JSON.stringify(body) : undefined,
})

// ============================================================================
// Dashboard
// ============================================================================

export const api_get_dashboard = async (date: Date | string): Promise<RhythmDashboardData> => {
  const response = await fetch(buildUrl('/dashboard', { date: toISODate(date) }))
  await checkOk(response, 'fetching dashboard')
  return response.json()
}

// ============================================================================
// Timeline
// ============================================================================

export const api_get_day_timeline = async (date: Date | string): Promise<DayTimelineData> => {
  const response = await fetch(buildUrl('/timeline/day', { date: toISODate(date) }))
  await checkOk(response, 'fetching day timeline')
  return response.json()
}

export const api_get_day_view = async (date: Date | string): Promise<unknown> => {
  const response = await fetch(buildUrl('/timeline/day-view', { date: toISODate(date) }))
  await checkOk(response, 'fetching day view')
  return response.json()
}

export const api_create_time_block = async (data: Record<string, unknown>): Promise<TimeBlockData> => {
  const response = await fetch(buildUrl('/timeline/block'), requestInit('POST', data))
  await checkOk(response, 'creating time block')
  return response.json()
}

export const api_set_block_status = async (id: number, status: BlockStatusValue): Promise<TimeBlockData> => {
  const response = await fetch(buildUrl(`/timeline/block/${id}/status`), requestInit('POST', { status }))
  await checkOk(response, `setting block ${id} status`)
  return response.json()
}

export const api_move_block = async (
  id: number,
  start_time: Date | string | number,
  end_time: Date | string | number
): Promise<TimeBlockData> => {
  const response = await fetch(
    buildUrl(`/timeline/block/${id}/move`),
    requestInit('POST', { start_time: toIsoDdl(start_time), end_time: toIsoDdl(end_time) })
  )
  await checkOk(response, `moving block ${id}`)
  return response.json()
}

// ============================================================================
// Plan
// ============================================================================

export const api_plan_day = async (
  date: Date | string,
  options: PlanOptions = {}
): Promise<PlanDayData> => {
  const response = await fetch(
    buildUrl('/plan/day'),
    requestInit('POST', { date: toISODate(date), preserve_done: options.preserve_done ?? true, force: options.force ?? false })
  )
  await checkOk(response, 'planning day')
  return response.json()
}

export const api_rebalance_day = async (
  date: Date | string,
  trigger = 'manual'
): Promise<PlanDayData> => {
  const response = await fetch(
    buildUrl('/plan/rebalance'),
    requestInit('POST', { date: toISODate(date), trigger })
  )
  await checkOk(response, 'rebalancing day')
  return response.json()
}

export const api_get_conflicts = async (date: Date | string): Promise<ConflictReportData> => {
  const response = await fetch(buildUrl('/plan/conflicts', { date: toISODate(date) }))
  await checkOk(response, 'fetching conflicts')
  return response.json()
}

// ============================================================================
// Review
// ============================================================================

export const api_get_day_review = async (date: Date | string): Promise<ReviewData> => {
  const response = await fetch(buildUrl('/review/day', { date: toISODate(date) }))
  await checkOk(response, 'fetching day review')
  return response.json()
}

export const api_get_week_review = async (span?: string): Promise<ReviewData> => {
  const response = await fetch(buildUrl('/review/week', span ? { span } : undefined))
  await checkOk(response, 'fetching week review')
  return response.json()
}

export const api_update_review_summary = async (
  scope: 'day' | 'week',
  period_key: string,
  ai_summary: string
): Promise<ReviewData> => {
  const response = await fetch(
    buildUrl(`/review/${scope}/${period_key}/summary`),
    requestInit('PUT', { ai_summary })
  )
  await checkOk(response, 'updating review summary')
  return response.json()
}

export const api_get_encroachments = async (
  start?: Date | string,
  end?: Date | string
): Promise<EncroachmentData[]> => {
  const response = await fetch(
    buildUrl('/review/encroachments', {
      start_date: start ? toISODate(start) : undefined,
      end_date: end ? toISODate(end) : undefined,
    })
  )
  await checkOk(response, 'fetching encroachments')
  return response.json()
}

export const api_get_domain_trend = async (
  start: Date | string,
  end: Date | string
): Promise<DomainTrendData> => {
  const response = await fetch(
    buildUrl('/review/domain-trend', { start_date: toISODate(start), end_date: toISODate(end) })
  )
  await checkOk(response, 'fetching domain trend')
  return response.json()
}

// ============================================================================
// Template
// ============================================================================

export const api_list_templates = async (enabled_only = false): Promise<{ templates: DayTemplateData[]; total: number }> => {
  const response = await fetch(buildUrl('/template/', { enabled_only }))
  await checkOk(response, 'listing templates')
  return response.json()
}

export const api_get_active_template = async (date: Date | string): Promise<DayTemplateData> => {
  const response = await fetch(buildUrl('/template/active', { date: toISODate(date) }))
  await checkOk(response, 'fetching active template')
  return response.json()
}

export const api_upsert_template = async (data: DayTemplateCreateProps): Promise<DayTemplateData> => {
  const response = await fetch(buildUrl('/template/'), requestInit('POST', data))
  await checkOk(response, 'upserting template')
  return response.json()
}

export const api_update_template = async (id: number, data: DayTemplateCreateProps): Promise<DayTemplateData> => {
  const response = await fetch(buildUrl(`/template/${id}`), requestInit('PUT', data))
  await checkOk(response, `updating template ${id}`)
  return response.json()
}

export const api_delete_template = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(buildUrl(`/template/${id}`), { method: 'DELETE' })
  await checkOk(response, `deleting template ${id}`)
  return response.json()
}

// ============================================================================
// Energy
// ============================================================================

export const api_get_energy_profile = async (): Promise<EnergyProfileData> => {
  const response = await fetch(buildUrl('/energy/profile'))
  await checkOk(response, 'fetching energy profile')
  return response.json()
}

export const api_upsert_energy_profile = async (data: EnergyProfileUpdateProps): Promise<EnergyProfileData> => {
  const response = await fetch(buildUrl('/energy/profile'), requestInit('PUT', data))
  await checkOk(response, 'upserting energy profile')
  return response.json()
}

// ============================================================================
// Policy
// ============================================================================

export const api_list_policies = async (enabled_only = false): Promise<{ policies: PolicyData[]; total: number }> => {
  const response = await fetch(buildUrl('/policy/', { enabled_only }))
  await checkOk(response, 'listing policies')
  return response.json()
}

export const api_create_policy = async (data: PolicyCreateProps): Promise<PolicyData> => {
  const response = await fetch(buildUrl('/policy/'), requestInit('POST', data))
  await checkOk(response, 'creating policy')
  return response.json()
}

export const api_update_policy = async (id: number, data: PolicyUpdateProps): Promise<PolicyData> => {
  const response = await fetch(buildUrl(`/policy/${id}`), requestInit('PUT', data))
  await checkOk(response, `updating policy ${id}`)
  return response.json()
}

export const api_delete_policy = async (id: number): Promise<{ id: number; status: string }> => {
  const response = await fetch(buildUrl(`/policy/${id}`), { method: 'DELETE' })
  await checkOk(response, `deleting policy ${id}`)
  return response.json()
}

// ============================================================================
// Checkin
// ============================================================================

export interface CheckinCreateProps {
  affair_id: number
  result: CheckinResultValue
  log_date?: Date | string
  note?: string
  source?: string
}

export const api_checkin = async (data: CheckinCreateProps): Promise<CheckinLogData> => {
  const body: Record<string, unknown> = {
    affair_id: data.affair_id,
    result: data.result,
    note: data.note ?? '',
    source: data.source ?? 'manual',
  }
  if (data.log_date !== undefined) body.log_date = toISODate(data.log_date)
  const response = await fetch(buildUrl('/checkin/'), requestInit('POST', body))
  await checkOk(response, 'checking in')
  return response.json()
}

export const api_list_checkins = async (filters?: {
  affair_id?: number
  start_date?: Date | string
  end_date?: Date | string
  cycle_key?: string
  skip?: number
  limit?: number
}): Promise<{ logs: CheckinLogData[]; total: number }> => {
  const response = await fetch(
    buildUrl('/checkin/', {
      affair_id: filters?.affair_id,
      start_date: filters?.start_date ? toISODate(filters.start_date) : undefined,
      end_date: filters?.end_date ? toISODate(filters.end_date) : undefined,
      cycle_key: filters?.cycle_key,
      skip: filters?.skip,
      limit: filters?.limit,
    })
  )
  await checkOk(response, 'listing checkins')
  return response.json()
}

export const api_get_today_checkins = async (date?: Date | string): Promise<CheckinTodayData> => {
  const response = await fetch(buildUrl('/checkin/today', date ? { date: toISODate(date) } : undefined))
  await checkOk(response, 'fetching today checkins')
  return response.json()
}

export const api_health_checkin = async (data: Record<string, unknown>): Promise<HealthCheckinData> => {
  const response = await fetch(buildUrl('/checkin/health'), requestInit('POST', data))
  await checkOk(response, 'health checkin')
  return response.json()
}

export const api_get_habit_heatmap = async (
  affair_id: number,
  start: Date | string,
  end: Date | string
): Promise<HabitHeatmapData> => {
  const response = await fetch(
    buildUrl('/checkin/heatmap', { affair_id, start_date: toISODate(start), end_date: toISODate(end) })
  )
  await checkOk(response, 'fetching habit heatmap')
  return response.json()
}

// ============================================================================
// Venture stats
// ============================================================================

export const api_get_venture_burndown = async (id: number): Promise<VentureBurndownData> => {
  const response = await fetch(buildUrl(`/venture/${id}/burndown`))
  await checkOk(response, `fetching venture ${id} burndown`)
  return response.json()
}

// ============================================================================
// Admin
// ============================================================================

export const api_recalibrate_profile = async (data: EnergyProfileUpdateProps): Promise<EnergyProfileData> => {
  const response = await fetch(buildUrl('/admin/recalibrate-profile'), requestInit('POST', data))
  await checkOk(response, 'recalibrating energy profile')
  return response.json()
}

export const api_ensure_default_templates = async (): Promise<{
  created: number
  updated: number
  templates: DayTemplateData[]
}> => {
  const response = await fetch(buildUrl('/admin/ensure-default-templates'), requestInit('POST'))
  await checkOk(response, 'ensuring default templates')
  return response.json()
}


