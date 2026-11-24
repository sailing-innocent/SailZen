/**
 * @file user.ts
 * @brief Unified UserProfile & Multi-Device REST API (/api/v1/user/*)
 * @author sailing-innocent
 * @date 2026-11-24
 */

import { API_BASE, ApiError, SERVER_URL, authHeaders, parseErrorDetail } from './config'

const USER_API_BASE = `${SERVER_URL}/${API_BASE}/user`

export interface QuietHoursConfig {
  enabled?: boolean
  start: string
  end: string
}

export interface UserProfile {
  id: number
  slug: string
  display_name: string
  avatar_url: string
  role: string
  status: string
  is_default: boolean
  timezone: string
  locale: string
  quiet_hours: QuietHoursConfig
  notification_prefs: Record<string, unknown>
  health_profile: Record<string, unknown>
  preferences: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface UserProfileUpdatePayload {
  display_name?: string
  avatar_url?: string
  timezone?: string
  locale?: string
  quiet_hours?: Partial<QuietHoursConfig>
  notification_prefs?: Record<string, unknown>
  health_profile?: Record<string, unknown>
  preferences?: Record<string, unknown>
}

export interface UserDevice {
  id: number
  user_id: number
  device_id: string
  device_name: string
  platform: string
  client_type: string
  app_version: string
  capabilities: Record<string, unknown>
  is_active: boolean
  is_online: boolean
  last_sync_seq: number
  last_seen_at?: string | null
}

export interface UserBootstrapResponse {
  auth_mode: string
  requires_login: boolean
  user: UserProfile
  unread_inbox_count: number
  active_inbox_count: number
  latest_sync_seq: number
  online_device_count: number
  devices: UserDevice[]
}

async function handleJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new ApiError(resp.status, resp.statusText, parseErrorDetail(text))
  }
  return (await resp.json()) as T
}

export async function api_user_bootstrap(): Promise<UserBootstrapResponse> {
  const resp = await fetch(`${USER_API_BASE}/bootstrap`, {
    headers: authHeaders(),
  })
  return handleJson<UserBootstrapResponse>(resp)
}

export async function api_get_user_profile(): Promise<UserProfile> {
  const resp = await fetch(`${USER_API_BASE}/profile`, {
    headers: authHeaders(),
  })
  return handleJson<UserProfile>(resp)
}

export async function api_update_user_profile(
  payload: UserProfileUpdatePayload,
): Promise<UserProfile> {
  const resp = await fetch(`${USER_API_BASE}/profile`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  return handleJson<UserProfile>(resp)
}

export async function api_register_web_device(deviceId: string): Promise<UserDevice> {
  const ua = typeof navigator !== 'undefined' ? navigator.userAgent : 'Web'
  const browserName = ua.includes('Edg/')
    ? 'Edge Web'
    : ua.includes('Chrome/')
      ? 'Chrome Web'
      : ua.includes('Firefox/')
        ? 'Firefox Web'
        : 'Browser Web'
  const resp = await fetch(`${USER_API_BASE}/devices/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      device_id: deviceId,
      device_name: browserName,
      platform: 'web',
      client_type: 'web',
      app_version: 'site',
      capabilities: { push_ws: true, system_notification: false },
    }),
  })
  return handleJson<UserDevice>(resp)
}

export async function api_list_user_devices(): Promise<UserDevice[]> {
  const resp = await fetch(`${USER_API_BASE}/devices`, {
    headers: authHeaders(),
  })
  return handleJson<UserDevice[]>(resp)
}
