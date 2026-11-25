/**
 * @file tick.ts
 * @brief SailTick Ticket API Client (异步 AI 教练票据)
 * @author sailing-innocent
 * @date 2026-10-27
 */
import { SERVER_URL, API_BASE, AUTH_TOKEN, authHeaders, ApiError, parseErrorDetail } from './config'

const TICK_API_BASE = `${API_BASE}/tick`

export type TicketType = 'question' | 'task' | 'approval' | 'info'
export type TicketStatus = 'pending' | 'replied' | 'resolved' | 'expired' | 'snoozed'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface TickTicket {
  id: number
  tick_id: string
  type: TicketType
  topic?: string
  title: string
  body: string
  meta?: Record<string, unknown>
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

export type TickMessageCategory = 'diet' | 'weight' | 'daily_info' | 'mood' | 'exercise' | 'general'

export interface TickMessage {
  id: number
  direction: 'user_to_agent' | 'agent_to_user'
  category: TickMessageCategory
  content: string
  meta: Record<string, unknown>
  source_channel: string
  status: 'unread' | 'ingested' | 'archived'
  ingested_by_tick_id: string | null
  created_at: string
  ingested_at: string | null
}

export interface DailyReport {
  id: number
  report_date: string
  tick_id: string
  title: string
  summary: string
  body_markdown: string
  weight_snapshot: Record<string, unknown>
  diet_summary: Record<string, unknown>
  plan_update: Record<string, unknown>
  tomorrow_focus: string[]
  pushed: boolean
  created_at: string
  updated_at: string
}

export type IntakeScene =
  | 'diet'
  | 'canteen_menu'
  | 'sleep'
  | 'exercise'
  | 'weight'
  | 'selfie_status'
  | 'general'

export type IntakeEntryKind =
  | 'diet'
  | 'canteen_menu'
  | 'sleep'
  | 'exercise'
  | 'weight'
  | 'mood'
  | 'daily_info'

export interface IntakeEntry {
  selected: boolean
  kind: IntakeEntryKind
  title: string
  confidence: number
  data: Record<string, unknown>
}

export interface CommittedRef {
  kind: string
  id: number
  label: string
}

export interface ImageIntakeDraft {
  id: number
  status: 'pending_confirm' | 'committed' | 'discarded'
  source_channel: string
  ticket_id: number | null
  media_key: string
  media_url: string
  media_mime: string
  media_size: number
  original_filename: string
  user_note: string
  scene: IntakeScene
  summary: string
  coach_advice: string
  ocr_text: string
  entries: IntakeEntry[]
  committed_refs: CommittedRef[]
  model_used: string
  usage: Record<string, unknown>
  created_at: string
  updated_at: string
  committed_at: string | null
}

export interface ImageIntakeCommitPayload {
  entries: IntakeEntry[]
  summary?: string
  user_note?: string
  ticket_id?: number | null
  reply_text?: string
}

export interface ImageIntakeCommitResponse {
  draft: ImageIntakeDraft
  committed_refs: CommittedRef[]
  message_id: number | null
  replied_ticket_id: number | null
}

export interface HealthCoachSummary {
  active_plan: Record<string, unknown> | null
  plan_progress: Record<string, unknown> | null
  latest_report: DailyReport | null
  pending_tickets: TickTicket[]
  pending_ticket_count: number
  today_messages: TickMessage[]
  pending_intake_drafts?: ImageIntakeDraft[]
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

// ── 用户主动静默上报餐饮/日常消息 ─────────────────────────────────────────

export const api_send_coach_message = (payload: {
  content: string
  category?: TickMessageCategory
  meta?: Record<string, unknown>
  source_channel?: string
  auto_log_diet?: boolean
}): Promise<TickMessage> =>
  request<TickMessage>('/messages', {
    method: 'POST',
    body: JSON.stringify({
      direction: 'user_to_agent',
      category: payload.category ?? 'diet',
      content: payload.content,
      meta: payload.meta ?? {},
      source_channel: payload.source_channel ?? 'web',
      auto_log_diet: payload.auto_log_diet ?? true,
    }),
  })

export const api_list_coach_messages = (params?: {
  status?: string
  category?: string
  direction?: string
  limit?: number
}): Promise<TickMessage[]> => {
  const search = new URLSearchParams()
  if (params?.status) search.set('status', params.status)
  if (params?.category) search.set('category', params.category)
  if (params?.direction) search.set('direction', params.direction)
  if (params?.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<TickMessage[]>(`/messages${qs ? `?${qs}` : ''}`)
}

// ── 每日睡前体重与健康日报 ────────────────────────────────────────────────

export const api_list_daily_reports = (limit = 14): Promise<DailyReport[]> =>
  request<DailyReport[]>(`/reports?limit=${limit}`)

export const api_get_latest_daily_report = (): Promise<DailyReport | null> =>
  request<DailyReport | null>('/reports/latest')

export const api_get_health_coach_summary = (): Promise<HealthCoachSummary> =>
  request<HealthCoachSummary>('/health-summary')

// ── 通用图片识图与二段式确认落库 ──────────────────────────────────────────

/** 构造可供 <img> 直接访问的媒体 URL（带可选 token 参数）。 */
export const tickMediaUrl = (mediaUrl: string): string => {
  if (!mediaUrl) return ''
  const base = mediaUrl.startsWith('http')
    ? mediaUrl
    : `${SERVER_URL}${mediaUrl.startsWith('/') ? '' : '/'}${mediaUrl}`
  if (!AUTH_TOKEN) return base
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}token=${encodeURIComponent(AUTH_TOKEN)}`
}

/** 上传图片并由 DeepSeek Vision/OCR 解析为待确认草稿 */
export const api_analyze_image_intake = async (
  file: File,
  options?: {
    note?: string
    ticketId?: number | null
    sourceChannel?: string
    useOcrAssist?: 'auto' | 'true' | 'false'
  },
): Promise<ImageIntakeDraft> => {
  const form = new FormData()
  form.append('file', file, file.name || 'capture.jpg')
  if (options?.note?.trim()) form.append('note', options.note.trim())
  form.append('source_channel', options?.sourceChannel ?? 'web')
  if (options?.ticketId != null) form.append('ticket_id', String(options.ticketId))
  if (options?.useOcrAssist) form.append('use_ocr_assist', options.useOcrAssist)

  const response = await fetch(`${SERVER_URL}/${TICK_API_BASE}/intake/analyze`, {
    method: 'POST',
    headers: { ...authHeaders() },
    body: form,
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText, parseErrorDetail(await response.text()))
  }
  return response.json() as Promise<ImageIntakeDraft>
}

export const api_list_intake_drafts = (params?: {
  status?: 'pending_confirm' | 'committed' | 'discarded'
  limit?: number
}): Promise<ImageIntakeDraft[]> => {
  const search = new URLSearchParams()
  if (params?.status) search.set('status', params.status)
  if (params?.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<ImageIntakeDraft[]>(`/intake/drafts${qs ? `?${qs}` : ''}`)
}

export const api_commit_image_intake = (
  draftId: number,
  payload: ImageIntakeCommitPayload,
): Promise<ImageIntakeCommitResponse> =>
  request<ImageIntakeCommitResponse>(`/intake/${draftId}/commit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const api_discard_image_intake = (draftId: number): Promise<ImageIntakeDraft> =>
  request<ImageIntakeDraft>(`/intake/${draftId}/discard`, {
    method: 'POST',
  })

// ── 健康模块：快速记体重 ──────────────────────────────────────────────

const HEALTH_API_BASE = `${API_BASE}/health`

/** 快速记体重（body_data metric=weight） */
export const api_quick_log_weight = async (weight: number): Promise<void> => {
  const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/body-data`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ data: { weight } }),
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText, parseErrorDetail(await response.text()))
  }
}

// ── 白天快反对话 & 专家简报（直连 SailTick daemon :9070） ──────────────────

export interface QuickChatResponse {
  reply: string
  actions: Array<Record<string, unknown>>
  reminders_created: Array<Record<string, unknown>>
  rhythm_updated?: boolean
  expert_brief_date?: string | null
  source: string
  session_id?: string
  latency_ms?: number
}

export const api_quick_chat = (
  text: string,
  options?: { channel?: string; session_id?: string },
): Promise<QuickChatResponse> =>
  request<QuickChatResponse>('/quick-chat', {
    method: 'POST',
    body: JSON.stringify({
      text,
      channel: options?.channel ?? 'web',
      session_id: options?.session_id ?? 'web:owner',
    }),
  })

export const api_get_expert_brief = (): Promise<Record<string, unknown>> =>
  request<Record<string, unknown>>('/expert-brief')
