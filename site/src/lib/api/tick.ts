/**
 * @file tick.ts
 * @brief SailTick Ticket API Client (异步 AI 教练票据)
 * @author sailing-innocent
 * @date 2026-10-27
 */
import { SERVER_URL, API_BASE, authHeaders, ApiError, parseErrorDetail } from './config'

const TICK_API_BASE = `${API_BASE}/tick`

export type TicketType = 'question' | 'task' | 'approval' | 'info'
export type TicketStatus = 'pending' | 'replied' | 'resolved' | 'expired' | 'snoozed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface TickTicket {
  id: number
  tick_id: string
  type: TicketType
  title: string
  body: string
  status: TicketStatus
  expected_reply_by: string | null
  replied_at: string | null
  reply: string | null
  resolved_at: string | null
  resolution: string | null
  fallback_assumption: string
  priority: TicketPriority
  channel: string
  created_at: string
  updated_at: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${SERVER_URL}/${TICK_API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText, parseErrorDetail(await response.text()))
  }
  return response.json() as Promise<T>
}

/** 待回票据列表（默认按期待回复时间升序） */
export const api_list_tickets = (params?: {
  status?: TicketStatus
  channel?: string
  type?: TicketType
  limit?: number
}): Promise<TickTicket[]> => {
  const search = new URLSearchParams()
  if (params?.status) search.set('status', params.status)
  if (params?.channel) search.set('channel', params.channel)
  if (params?.type) search.set('type', params.type)
  if (params?.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<TickTicket[]>(`/tickets${qs ? `?${qs}` : ''}`)
}

export const api_get_ticket = (id: number): Promise<TickTicket> =>
  request<TickTicket>(`/tickets/${id}`)

/** 用户回复票据 */
export const api_reply_ticket = (id: number, reply: string): Promise<TickTicket> =>
  request<TickTicket>(`/tickets/${id}/reply`, {
    method: 'POST',
    body: JSON.stringify({ reply }),
  })

/** 关闭票据 */
export const api_resolve_ticket = (id: number, resolution = ''): Promise<TickTicket> =>
  request<TickTicket>(`/tickets/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ resolution }),
  })

/** 暂缓票据 N 小时 */
export const api_snooze_ticket = (id: number, hours = 24): Promise<TickTicket> =>
  request<TickTicket>(`/tickets/${id}/snooze`, {
    method: 'POST',
    body: JSON.stringify({ hours }),
  })

/** 增量拉取已回复/关闭票据（agent SCAN 用，页面历史也可复用） */
export const api_list_replies = (since?: string): Promise<TickTicket[]> => {
  const qs = since ? `?since=${encodeURIComponent(since)}` : ''
  return request<TickTicket[]>(`/replies${qs}`)
}

// ── 健康模块：快速记体重 ──────────────────────────────────────────────

const HEALTH_API_BASE = `${API_BASE}/health`

/** 快速记体重（body_data metric=weight） */
export const api_quick_log_weight = async (weight: number): Promise<void> => {
  const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/body_data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ data: { weight } }),
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText, parseErrorDetail(await response.text()))
  }
}
