import { SERVER_URL, API_BASE } from './config'
import type { PipelineInfo, PipelineRun, TaskDetail } from '@lib/data/dag_pipeline'

// API_BASE 已经是 "/api/v1"，所以拼接后 PIPELINE_BASE = "/api/v1/pipeline" 或 "http://host/api/v1/pipeline"
const PIPELINE_BASE = `${SERVER_URL}${API_BASE}/pipeline`

export async function fetchPipelines(): Promise<PipelineInfo[]> {
  const r = await fetch(`${PIPELINE_BASE}/definition`)
  if (!r.ok) throw new Error('Failed to fetch pipelines')
  return r.json()
}

export async function fetchRuns(): Promise<PipelineRun[]> {
  const r = await fetch(`${PIPELINE_BASE}/run`)
  if (!r.ok) throw new Error('Failed to fetch runs')
  return r.json()
}

export async function fetchRun(id: string): Promise<PipelineRun> {
  const r = await fetch(`${PIPELINE_BASE}/run/${id}`)
  if (!r.ok) throw new Error('Failed to fetch run')
  return r.json()
}

export async function startRun(pipeline_id: string, params: Record<string, unknown>): Promise<PipelineRun> {
  const r = await fetch(`${PIPELINE_BASE}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pipeline_id, params }),
  })
  if (!r.ok) {
    let message = 'Failed to start run'
    try {
      const body = await r.json()
      message = String(body.error || body.text || message)
    } catch {
      message = await r.text() || message
    }
    throw new Error(message)
  }
  return r.json()
}

export async function resumeRunFromNode(runId: string, nodeId: string): Promise<PipelineRun> {
  const r = await fetch(`${PIPELINE_BASE}/run/${runId}/resume-from/${nodeId}`, { method: 'POST' })
  if (!r.ok) {
    let message = 'Failed to resume run from node'
    try {
      const body = await r.json()
      message = String(body.error || body.text || message)
    } catch {
      message = await r.text() || message
    }
    throw new Error(message)
  }
  return r.json()
}

export async function manualBlockNode(runId: string, nodeId: string, reason?: string): Promise<PipelineRun> {
  const r = await fetch(`${PIPELINE_BASE}/run/${runId}/block-node/${nodeId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!r.ok) {
    let message = 'Failed to manually block node'
    try {
      const body = await r.json()
      message = String(body.error || body.text || message)
    } catch {
      message = await r.text() || message
    }
    throw new Error(message)
  }
  return r.json()
}

export async function manualSuccessNode(runId: string, nodeId: string, reason?: string): Promise<PipelineRun> {
  const r = await fetch(`${PIPELINE_BASE}/run/${runId}/success-node/${nodeId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  })
  if (!r.ok) {
    let message = 'Failed to manually mark node as success'
    try {
      const body = await r.json()
      message = String(body.error || body.text || message)
    } catch {
      message = await r.text() || message
    }
    throw new Error(message)
  }
  return r.json()
}

export async function cancelRun(id: string): Promise<void> {
  await fetch(`${PIPELINE_BASE}/run/${id}`, { method: 'DELETE' })
}

export async function fetchTaskDetail(taskId: string): Promise<TaskDetail> {
  const r = await fetch(`${SERVER_URL}${API_BASE}/tasks/${taskId}/detail`)
  if (!r.ok) {
    let message = 'Failed to fetch task detail'
    try {
      const body = await r.json()
      message = String(body.error || body.text || message)
    } catch {
      message = await r.text() || message
    }
    throw new Error(message)
  }
  return r.json()
}

export function createSSEStream(runId: string, onData: (run: PipelineRun) => void): EventSource {
  const url = `${PIPELINE_BASE}/sse/run/${runId}`
  console.log('[SSE] Connecting to:', url)  // debug
  const es = new EventSource(url)
  es.onmessage = (e) => {
    try {
      onData(JSON.parse(e.data))
    } catch { /* ignore parse errors */ }
  }
  es.onerror = (e) => {
    console.warn('[SSE] Error:', e)
  }
  return es
}
