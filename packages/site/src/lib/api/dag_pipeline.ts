import { SERVER_URL, API_BASE } from './config'
import type { PipelineInfo, PipelineRun } from '@lib/data/dag_pipeline'

const PIPELINE_BASE = `${SERVER_URL}/${API_BASE}/pipeline`

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

export async function fetchRun(id: number): Promise<PipelineRun> {
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
  if (!r.ok) throw new Error('Failed to start run')
  return r.json()
}

export async function cancelRun(id: number): Promise<void> {
  await fetch(`${PIPELINE_BASE}/run/${id}`, { method: 'DELETE' })
}

export function createSSEStream(runId: number, onData: (run: PipelineRun) => void): EventSource {
  const es = new EventSource(`${PIPELINE_BASE}/sse/run/${runId}`)
  es.onmessage = (e) => {
    try {
      onData(JSON.parse(e.data))
    } catch {}
  }
  return es
}
