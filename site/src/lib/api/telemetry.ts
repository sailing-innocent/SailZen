/**
 * @file telemetry.ts
 * @brief SailZen Telemetry, AI Trace & System Profile API Client
 * @author sailing-innocent
 * @date 2026-11-23
 */
import { SERVER_URL, API_BASE, authHeaders, ApiError, parseErrorDetail } from './config'

const TELEMETRY_API_BASE = `${API_BASE}/telemetry`

export interface AITraceSpan {
  span_id: string
  parent_span_id: string | null
  seq: number
  stage: string
  name: string
  status: 'ok' | 'error' | 'degraded' | 'skipped' | string
  started_at: string | null
  ended_at: string | null
  duration_ms: number
  input_summary: string
  output_summary: string
  payload: Record<string, unknown>
  error: string | null
}

export interface AITraceSummary {
  id: number
  trace_id: string
  service: string
  tick_id: string
  slot: string
  tick_date: string
  trigger_source: string
  mode: string
  status: string
  plan_source: string
  started_at: string | null
  ended_at: string | null
  duration_ms: number
  llm_calls_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  tickets_created: number
  tickets_throttled: number
  actions_executed: number
  actions_failed: number
  summary: string
  error: string | null
  meta: Record<string, unknown>
  span_count: number
}

export interface AITraceDetail extends AITraceSummary {
  spans: AITraceSpan[]
}

export interface AITraceSlotStats {
  slot: string
  total: number
  completed: number
  failed: number
  llm_plans: number
  fallback_plans: number
  avg_duration_ms: number
  total_tokens: number
  total_cost_usd: number
}

export interface AITraceDailyTrendPoint {
  date: string
  total: number
  completed: number
  failed: number
  fallback: number
  tokens: number
  cost_usd: number
}

export interface AITraceStats {
  window_days: number
  service: string
  total_traces: number
  completed_count: number
  failed_count: number
  paused_count: number
  skipped_count: number
  success_rate: number
  llm_plan_count: number
  fallback_plan_count: number
  fallback_error_count: number
  fallback_rate: number
  avg_duration_ms: number
  avg_llm_latency_ms: number
  total_tokens: number
  total_prompt_tokens: number
  total_completion_tokens: number
  total_cost_usd: number
  total_tickets_created: number
  total_tickets_throttled: number
  total_actions_executed: number
  total_actions_failed: number
  by_slot: AITraceSlotStats[]
  daily_trend: AITraceDailyTrendPoint[]
}

export interface ModuleApiMetric {
  module: string
  req_count: number
  err_4xx: number
  err_5xx: number
  error_rate: number
  avg_ms: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  max_ms: number
  bytes_out: number
}

export interface EndpointApiMetric {
  module: string
  method: string
  endpoint: string
  req_count: number
  err_4xx: number
  err_5xx: number
  error_rate: number
  avg_ms: number
  p95_ms: number
  max_ms: number
  bytes_out: number
}

export interface NotableEventItem {
  id: number | null
  category: string
  module: string
  name: string
  client_source: string
  duration_ms: number | null
  status_code: number | null
  value: number | null
  detail: Record<string, unknown>
  created_at: string
}

export interface ApiProfile {
  window_hours: number
  total_requests: number
  total_4xx: number
  total_5xx: number
  error_rate: number
  avg_ms: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
  max_ms: number
  total_bytes_out: number
  slow_threshold_ms: number
  slow_requests_count: number
  by_module: ModuleApiMetric[]
  by_client: Record<string, number>
  top_slow_endpoints: EndpointApiMetric[]
  top_called_endpoints: EndpointApiMetric[]
  top_error_endpoints?: EndpointApiMetric[]
  recent_notable: NotableEventItem[]
}

export interface ModuleProfileCard {
  key: string
  label: string
  status: 'healthy' | 'warning' | 'idle' | string
  summary: string
  metrics: Record<string, unknown>
  api_requests_window: number
  api_p95_ms: number
  api_error_rate: number
}

export interface PageUsageItem {
  path: string
  views: number
  avg_dwell_sec: number
  total_dwell_sec: number
}

export interface ModulesProfile {
  generated_at: string
  window_days: number
  modules: ModuleProfileCard[]
  page_usage: PageUsageItem[]
  recent_client_errors: NotableEventItem[]
}

export interface SystemRuntimeProfile {
  generated_at: string
  started_at: string
  uptime_seconds: number
  python_version: string
  db_backend: string
  memory_rss_mb: number | null
  data_dir: string
  data_dir_size_mb: number
  online_ws_devices: string[]
  total_requests_since_boot: number
  total_errors_since_boot: number
  unflushed_buckets: number
  last_flush_at: string | null
  table_counts: Record<string, number>
}

export interface SailTickLiveStatus {
  reachable: boolean
  api_base: string
  error?: string
  health?: {
    status?: string
    version?: string
    time?: string
    daily_tokens?: number
    current_tick?: Record<string, unknown> | null
    canary?: {
      mode: string
      circuit_breaker_open: boolean
      consecutive_failures: number
      last_downgrade_reason?: string
      policy?: Record<string, unknown>
    }
    deps?: Record<string, { status?: string; detail?: string }>
    db_stats?: Record<string, number>
  }
  monitor?: {
    overall_health?: string
    metrics?: Record<string, number>
    alerts?: Array<{ level: string; code: string; message: string }>
  } | null
  schedules?: Array<{
    id?: string
    name?: string
    slot?: string
    next_run_time?: string | null
  }>
}

export interface ClientTelemetryEventPayload {
  category: 'page_view' | 'web_vital' | 'client_error' | 'system'
  module?: string
  name: string
  client_source?: string
  duration_ms?: number
  status_code?: number
  value?: number
  detail?: Record<string, unknown>
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${SERVER_URL}/${TELEMETRY_API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-SailZen-Client': 'web',
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText, parseErrorDetail(await response.text()))
  }
  return response.json() as Promise<T>
}

export const api_list_ai_traces = (params?: {
  service?: string
  slot?: string
  status?: string
  plan_source?: string
  days?: number
  limit?: number
}): Promise<AITraceSummary[]> => {
  const search = new URLSearchParams()
  if (params?.service) search.set('service', params.service)
  if (params?.slot) search.set('slot', params.slot)
  if (params?.status) search.set('status', params.status)
  if (params?.plan_source) search.set('plan_source', params.plan_source)
  if (params?.days !== undefined) search.set('days', String(params.days))
  if (params?.limit !== undefined) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<AITraceSummary[]>(`/ai-traces${qs ? `?${qs}` : ''}`)
}

export const api_get_ai_trace_detail = (traceId: string): Promise<AITraceDetail> =>
  request<AITraceDetail>(`/ai-traces/${encodeURIComponent(traceId)}`)

export const api_get_ai_trace_stats = (params?: {
  service?: string
  days?: number
}): Promise<AITraceStats> => {
  const search = new URLSearchParams()
  if (params?.service) search.set('service', params.service)
  if (params?.days !== undefined) search.set('days', String(params.days))
  const qs = search.toString()
  return request<AITraceStats>(`/ai-traces/stats${qs ? `?${qs}` : ''}`)
}

export const api_get_api_profile = (hours = 24, includeSelf = false): Promise<ApiProfile> =>
  request<ApiProfile>(`/profile/api?hours=${hours}&include_self=${includeSelf}`)

export const api_get_modules_profile = (days = 7): Promise<ModulesProfile> =>
  request<ModulesProfile>(`/profile/modules?days=${days}`)

export const api_get_runtime_profile = (): Promise<SystemRuntimeProfile> =>
  request<SystemRuntimeProfile>('/profile/runtime')

export const api_get_sailtick_live = (): Promise<SailTickLiveStatus> =>
  request<SailTickLiveStatus>('/sailtick/live')

export const api_trigger_sailtick_slot = (
  slot: string,
  idempotencySuffix?: string,
): Promise<{ reachable: boolean; status_code?: number; result?: Record<string, unknown>; error?: string }> =>
  request('/sailtick/trigger', {
    method: 'POST',
    body: JSON.stringify({
      slot,
      idempotency_suffix: idempotencySuffix,
      params: { trigger_source: 'debug_ui' },
    }),
  })

export const api_post_client_events = (events: ClientTelemetryEventPayload[]): Promise<{ accepted: number }> =>
  request<{ accepted: number }>('/events', {
    method: 'POST',
    body: JSON.stringify({ events }),
  })
