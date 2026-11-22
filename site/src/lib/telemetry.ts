/**
 * @file telemetry.ts
 * @brief Lightweight client-side telemetry tracker (page views, dwell time, JS errors)
 * @author sailing-innocent
 * @date 2026-11-23
 */
import { api_post_client_events, type ClientTelemetryEventPayload } from '@lib/api/telemetry'

const FLUSH_INTERVAL_MS = 10_000
const MAX_QUEUE = 30

let queue: ClientTelemetryEventPayload[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null
let errorListenersInstalled = false

function flushQueue(): void {
  if (flushTimer) {
    clearTimeout(flushTimer)
    flushTimer = null
  }
  if (queue.length === 0) return
  const batch = queue.splice(0, MAX_QUEUE)
  api_post_client_events(batch).catch(() => {
    // 埋点上报永不阻塞业务，静默丢弃
  })
}

export function trackClientEvent(event: ClientTelemetryEventPayload): void {
  if (queue.length >= MAX_QUEUE) {
    queue.shift()
  }
  queue.push({
    client_source: 'web',
    ...event,
  })
  if (queue.length >= 10) {
    flushQueue()
    return
  }
  if (!flushTimer) {
    flushTimer = setTimeout(flushQueue, FLUSH_INTERVAL_MS)
  }
}

export function flushClientEvents(): void {
  flushQueue()
}

export function installGlobalErrorTelemetry(): () => void {
  if (errorListenersInstalled || typeof window === 'undefined') {
    return () => {}
  }
  errorListenersInstalled = true

  const onError = (ev: ErrorEvent) => {
    trackClientEvent({
      category: 'client_error',
      module: 'web',
      name: (ev.message || 'Uncaught Error').slice(0, 200),
      detail: {
        path: window.location.pathname,
        filename: ev.filename,
        lineno: ev.lineno,
        colno: ev.colno,
      },
    })
  }

  const onRejection = (ev: PromiseRejectionEvent) => {
    const msg =
      ev.reason instanceof Error
        ? `${ev.reason.name}: ${ev.reason.message}`
        : String(ev.reason ?? 'Unhandled Rejection')
    trackClientEvent({
      category: 'client_error',
      module: 'web',
      name: msg.slice(0, 200),
      detail: {
        path: window.location.pathname,
        type: 'unhandledrejection',
      },
    })
  }

  const onVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      flushQueue()
    }
  }

  window.addEventListener('error', onError)
  window.addEventListener('unhandledrejection', onRejection)
  document.addEventListener('visibilitychange', onVisibilityChange)

  return () => {
    window.removeEventListener('error', onError)
    window.removeEventListener('unhandledrejection', onRejection)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    errorListenersInstalled = false
  }
}
