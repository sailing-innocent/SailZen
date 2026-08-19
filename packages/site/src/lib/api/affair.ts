/**
 * @file affair.ts
 * @brief Rhythm Affair API client
 * @description
 *   封装 `/api/v1/rhythm/*` 的 REST 调用，取代旧的 `/api/v1/project/*`。
 *   提供事务 CRUD、状态转移、事业里程碑与进度查询。
 */

import { SERVER_URL, API_BASE } from './config'
import type {
  AffairData,
  AffairCreateProps,
  AffairUpdateProps,
  AffairKindValue,
  AffairDomainValue,
  AffairStateValue,
} from '@lib/data/affair'
import { toIsoDdl } from '@lib/data/affair'

const RHYTHM_API_BASE = API_BASE + '/rhythm'

type QueryValue = string | number | undefined | (string | number)[]

const buildUrl = (path: string, query?: Record<string, QueryValue>): string => {
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

// Normalize creation props before sending to backend
const normalizeCreateProps = (props: AffairCreateProps): Record<string, unknown> => {
  const body: Record<string, unknown> = {
    title: props.title,
    description: props.description ?? '',
    domain: props.domain ?? 'work',
    kind: props.kind ?? 'task_oneoff',
    kind_meta: props.kind_meta ?? {},
    importance: props.importance ?? 3,
    energy_cost: props.energy_cost ?? 10,
    money_cost: props.money_cost ?? 0,
    est_minutes: props.est_minutes ?? 30,
    splittable: props.splittable ?? false,
    min_chunk_minutes: props.min_chunk_minutes ?? 30,
    fallback_plan: props.fallback_plan ?? '',
    ref: props.ref ?? {},
  }
  if (props.state) body.state = props.state
  if (props.parent_id !== undefined) body.parent_id = props.parent_id
  if (props.urgency_ddl !== undefined) body.urgency_ddl = toIsoDdl(props.urgency_ddl)
  if (props.budget_id !== undefined) body.budget_id = props.budget_id
  if (props.mission_id !== undefined) body.mission_id = props.mission_id
  if (props.day_id !== undefined) body.day_id = props.day_id
  if (props.timespan_id !== undefined) body.timespan_id = props.timespan_id
  if (props.info_collection_type !== undefined) body.info_collection_type = props.info_collection_type
  if (props.window_start !== undefined) body.window_start = toIsoDdl(props.window_start)
  if (props.window_end !== undefined) body.window_end = toIsoDdl(props.window_end)
  if (props.recurrence_rule_id !== undefined) body.recurrence_rule_id = props.recurrence_rule_id
  return body
}

const normalizeUpdateProps = (props: AffairUpdateProps): Record<string, unknown> => {
  const body: Record<string, unknown> = {}
  if (props.title !== undefined) body.title = props.title
  if (props.description !== undefined) body.description = props.description
  if (props.domain !== undefined) body.domain = props.domain
  if (props.kind !== undefined) body.kind = props.kind
  if (props.kind_meta !== undefined) body.kind_meta = props.kind_meta
  if (props.state !== undefined) body.state = props.state
  if (props.importance !== undefined) body.importance = props.importance
  if (props.energy_cost !== undefined) body.energy_cost = props.energy_cost
  if (props.money_cost !== undefined) body.money_cost = props.money_cost
  if (props.est_minutes !== undefined) body.est_minutes = props.est_minutes
  if (props.splittable !== undefined) body.splittable = props.splittable
  if (props.min_chunk_minutes !== undefined) body.min_chunk_minutes = props.min_chunk_minutes
  if (props.fallback_plan !== undefined) body.fallback_plan = props.fallback_plan
  if (props.parent_id !== undefined) body.parent_id = props.parent_id
  if (props.urgency_ddl !== undefined) body.urgency_ddl = toIsoDdl(props.urgency_ddl)
  if (props.budget_id !== undefined) body.budget_id = props.budget_id
  if (props.mission_id !== undefined) body.mission_id = props.mission_id
  if (props.day_id !== undefined) body.day_id = props.day_id
  if (props.timespan_id !== undefined) body.timespan_id = props.timespan_id
  if (props.info_collection_type !== undefined) body.info_collection_type = props.info_collection_type
  if (props.ref !== undefined) body.ref = props.ref
  if (props.ai_hint !== undefined) body.ai_hint = props.ai_hint
  if (props.window_start !== undefined) body.window_start = toIsoDdl(props.window_start)
  if (props.window_end !== undefined) body.window_end = toIsoDdl(props.window_end)
  return body
}

// ---------------------------------------------------------------------------
// Affair CRUD
// ---------------------------------------------------------------------------

const fetchAffairsSingle = async (
  filters: Record<string, QueryValue>
): Promise<AffairData[]> => {
  const response = await fetch(buildUrl('/affair/', filters))
  await checkOk(response, 'fetching affairs')
  const data = (await response.json()) as { affairs: AffairData[]; total: number }
  return data.affairs ?? []
}

const uniqueById = (items: AffairData[]): AffairData[] => {
  const seen = new Set<number>()
  return items.filter((item) => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
}

export const api_get_affairs = async (filters?: {
  state?: string | string[]
  domain?: string | string[]
  kind?: string | string[]
  day_id?: number
  parent_id?: number | null
  urgency_ddl_before?: string | Date | number
  urgency_ddl_after?: string | Date | number
  skip?: number
  limit?: number
}): Promise<AffairData[]> => {
  const base: Record<string, QueryValue> = {}
  if (filters) {
    // 后端 list_affairs_impl 的 kind 支持 List[str]，用重复 query param 传递
    if (filters.kind !== undefined && filters.kind !== '') {
      base.kind = Array.isArray(filters.kind) ? filters.kind : [filters.kind]
    }
    if (filters.day_id !== undefined) base.day_id = filters.day_id
    if (filters.parent_id !== undefined && filters.parent_id !== null) base.parent_id = filters.parent_id
    if (filters.urgency_ddl_before !== undefined) {
      base.urgency_ddl_before = toIsoDdl(filters.urgency_ddl_before) ?? undefined
    }
    if (filters.urgency_ddl_after !== undefined) {
      base.urgency_ddl_after = toIsoDdl(filters.urgency_ddl_after) ?? undefined
    }
    if (filters.skip !== undefined) base.skip = filters.skip
    if (filters.limit !== undefined) base.limit = filters.limit
  }

  const states = filters?.state ? (Array.isArray(filters.state) ? filters.state : [filters.state]) : [undefined]
  const domains = filters?.domain ? (Array.isArray(filters.domain) ? filters.domain : [filters.domain]) : [undefined]

  const all: AffairData[] = []
  for (const state of states) {
    for (const domain of domains) {
      const query: Record<string, QueryValue> = { ...base }
      if (state) query.state = state
      if (domain) query.domain = domain
      const affairs = await fetchAffairsSingle(query)
      all.push(...affairs)
    }
  }

  return uniqueById(all)
}

export const api_get_affair = async (id: number): Promise<AffairData> => {
  const response = await fetch(buildUrl(`/affair/${id}`))
  await checkOk(response, `fetching affair ${id}`)
  return response.json()
}

export const api_create_affair = async (props: AffairCreateProps): Promise<AffairData> => {
  const response = await fetch(buildUrl('/affair/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(normalizeCreateProps(props)),
  })
  await checkOk(response, 'creating affair')
  return response.json()
}

export const api_update_affair = async (id: number, props: AffairUpdateProps): Promise<AffairData> => {
  const response = await fetch(buildUrl(`/affair/${id}`), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(normalizeUpdateProps(props)),
  })
  await checkOk(response, `updating affair ${id}`)
  return response.json()
}

export const api_delete_affair = async (id: number): Promise<{ id: number; status: string; message?: string }> => {
  const response = await fetch(buildUrl(`/affair/${id}`), {
    method: 'DELETE',
  })
  await checkOk(response, `deleting affair ${id}`)
  return response.json()
}

// ---------------------------------------------------------------------------
// State transitions
// ---------------------------------------------------------------------------

export type AffairAction =
  | 'confirm'
  | 'defer'
  | 'replan'
  | 'cancel'
  | 'dismiss'
  | 'start'
  | 'finish'
  | 'pause'
  | 'resume'
  | 'archive'
  | 'graduate'

export interface TransitAffairOptions {
  defer_to?: string | Date | number
  defer_end?: string | Date | number
  force?: boolean
}

export const api_transit_affair_state = async (
  id: number,
  action: AffairAction,
  options: TransitAffairOptions = {}
): Promise<AffairData> => {
  const body: Record<string, unknown> = { action }
  if (options.defer_to !== undefined) body.defer_to = toIsoDdl(options.defer_to)
  if (options.defer_end !== undefined) body.defer_end = toIsoDdl(options.defer_end)
  if (options.force !== undefined) body.force = options.force

  const response = await fetch(buildUrl(`/affair/${id}/state`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  await checkOk(response, `transiting affair ${id} state`)
  return response.json()
}

// ---------------------------------------------------------------------------
// Venture helpers
// ---------------------------------------------------------------------------

export const api_add_milestone = async (
  ventureId: number,
  props: {
    title: string
    timespan_id?: number
    urgency_ddl?: string | Date | number
    est_minutes?: number
    description?: string
  }
): Promise<AffairData> => {
  const response = await fetch(buildUrl(`/venture/${ventureId}/milestone`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: props.title,
      description: props.description ?? '',
      timespan_id: props.timespan_id,
      urgency_ddl: toIsoDdl(props.urgency_ddl),
      est_minutes: props.est_minutes ?? 30,
    }),
  })
  await checkOk(response, `adding milestone to venture ${ventureId}`)
  return response.json()
}

export const api_done_milestone = async (milestoneId: number): Promise<AffairData> => {
  const response = await fetch(buildUrl(`/venture/milestone/${milestoneId}/done`), {
    method: 'POST',
  })
  await checkOk(response, `completing milestone ${milestoneId}`)
  return response.json()
}

export const api_get_venture_progress = async (id: number): Promise<Record<string, unknown>> => {
  const response = await fetch(buildUrl(`/venture/${id}/progress`))
  await checkOk(response, `fetching venture progress ${id}`)
  return response.json()
}

// ---------------------------------------------------------------------------
// Convenience: scoped venture / task helpers used by stores
// ---------------------------------------------------------------------------

export const api_get_ventures = async (): Promise<AffairData[]> => {
  return api_get_affairs({ kind: 'venture', state: ['INBOX', 'ACTIVE', 'PAUSED'] })
}

export const api_get_tasks = async (parentId?: number | null): Promise<AffairData[]> => {
  const filters: Parameters<typeof api_get_affairs>[0] = {
    kind: 'task_oneoff',
    domain: ['work', 'career'],
  }
  if (parentId !== undefined) filters.parent_id = parentId
  return api_get_affairs(filters)
}
