/**
 * @file inbox.ts
 * @brief Unified UserInbox REST API (/api/v1/inbox/*)
 * @author sailing-innocent
 * @date 2026-11-24
 */

import { API_BASE, ApiError, SERVER_URL, authHeaders, parseErrorDetail } from './config'

const INBOX_API_BASE = `${SERVER_URL}/${API_BASE}/inbox`

export type InboxItemStatus =
  | 'pending'
  | 'delivered'
  | 'snoozed'
  | 'opened'
  | 'answered'
  | 'resolved'
  | 'dismissed'
  | 'expired'
  | 'canceled'

export const INBOX_ACTIVE_STATUSES: ReadonlySet<string> = new Set([
  'pending',
  'delivered',
  'snoozed',
  'opened',
])

export interface InboxItem {
  id: number
  user_id: number
  sync_seq: number
  source_domain: string
  target_domain?: string
  persona?: string
  target_clients?: string[]
  item_kind: string
  topic: string
  dedup_key: string
  ref_type: string
  ref_id: number | null
  reminder_id: number | null
  ticket_id: number | null
  title: string
  body: string
  priority: 'low' | 'normal' | 'high' | 'urgent'
  status: InboxItemStatus
  is_read: boolean
  read_at: string | null
  action_schema: Record<string, unknown>
  reply_text: string | null
  resolution_source: string
  resolution_summary: string
  resolution_ref: Record<string, unknown>
  trigger_at: string | null
  snooze_until: string | null
  expires_at: string | null
  delivered_at: string | null
  resolved_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface InboxSyncResponse {
  latest_seq: number
  unread_count: number
  active_count: number
  active_ids: number[]
  changes: InboxItem[]
}

export interface InboxSummary {
  date: string
  active: number
  unread: number
  answered: number
  resolved: number
  dismissed: number
  expired: number
  by_domain: Record<string, number>
}

async function handleJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new ApiError(resp.status, resp.statusText, parseErrorDetail(text))
  }
  return (await resp.json()) as T
}

export async function api_sync_inbox(sinceSeq = 0, limit = 200): Promise<InboxSyncResponse> {
  const qs = new URLSearchParams({
    since_seq: String(sinceSeq),
    limit: String(limit),
  })
  const resp = await fetch(`${INBOX_API_BASE}/sync?${qs.toString()}`, {
    headers: authHeaders(),
  })
  return handleJson<InboxSyncResponse>(resp)
}

export async function api_list_inbox(
  tab: 'active' | 'history' | 'all' = 'active',
  limit = 100,
  domain?: string,
): Promise<InboxItem[]> {
  const qs = new URLSearchParams({ tab, limit: String(limit) })
  if (domain && domain !== 'all') qs.set('domain', domain)
  const resp = await fetch(`${INBOX_API_BASE}/?${qs.toString()}`, {
    headers: authHeaders(),
  })
  return handleJson<InboxItem[]>(resp)
}

export async function api_inbox_summary(): Promise<InboxSummary> {
  const resp = await fetch(`${INBOX_API_BASE}/summary`, {
    headers: authHeaders(),
  })
  return handleJson<InboxSummary>(resp)
}

export async function api_inbox_reply(
  itemId: number,
  reply: string,
  source = 'web:inbox',
): Promise<InboxItem> {
  const resp = await fetch(`${INBOX_API_BASE}/${itemId}/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ reply, source }),
  })
  return handleJson<InboxItem>(resp)
}

export async function api_inbox_resolve(
  itemId: number,
  resolutionSummary = '',
  resolutionSource = 'web:inbox',
): Promise<InboxItem> {
  const resp = await fetch(`${INBOX_API_BASE}/${itemId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      resolution_summary: resolutionSummary,
      resolution_source: resolutionSource,
    }),
  })
  return handleJson<InboxItem>(resp)
}

export async function api_inbox_snooze(
  itemId: number,
  option: '15m' | '1h' | 'tonight' | 'tomorrow' | '24h' = '24h',
): Promise<InboxItem> {
  const resp = await fetch(`${INBOX_API_BASE}/${itemId}/snooze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ option }),
  })
  return handleJson<InboxItem>(resp)
}

export async function api_inbox_dismiss(itemId: number, reason = ''): Promise<InboxItem> {
  const resp = await fetch(`${INBOX_API_BASE}/${itemId}/dismiss`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ reason }),
  })
  return handleJson<InboxItem>(resp)
}

export async function api_inbox_mark_read(itemId: number): Promise<InboxItem> {
  const resp = await fetch(`${INBOX_API_BASE}/${itemId}/read`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return handleJson<InboxItem>(resp)
}

export async function api_inbox_read_all(): Promise<{ ok: boolean; marked_read: number }> {
  const resp = await fetch(`${INBOX_API_BASE}/read-all`, {
    method: 'POST',
    headers: authHeaders(),
  })
  return handleJson<{ ok: boolean; marked_read: number }>(resp)
}
