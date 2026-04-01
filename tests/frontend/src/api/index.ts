import type { 
  PipelineInfo, PipelineRun, 
  Agent, AgentTask, OpenCodeSession, DashboardStats, Skill, AgentWithTasks 
} from '../types'

const BASE = '/runs'
const AGENTS_BASE = '/agents'

// ================== Pipeline APIs ==================

export async function fetchPipelines(): Promise<PipelineInfo[]> {
  const r = await fetch('/pipelines')
  if (!r.ok) throw new Error('Failed to fetch pipelines')
  return r.json()
}

export async function fetchRuns(): Promise<PipelineRun[]> {
  const r = await fetch(BASE)
  if (!r.ok) throw new Error('Failed to fetch runs')
  return r.json()
}

export async function fetchRun(id: number): Promise<PipelineRun> {
  const r = await fetch(`${BASE}/${id}`)
  if (!r.ok) throw new Error('Failed to fetch run')
  return r.json()
}

export async function startRun(pipeline_id: string, params: Record<string, unknown>): Promise<PipelineRun> {
  const r = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pipeline_id, params }),
  })
  if (!r.ok) throw new Error('Failed to start run')
  return r.json()
}

export async function cancelRun(id: number): Promise<void> {
  await fetch(`${BASE}/${id}`, { method: 'DELETE' })
}

export function createSSEStream(runId: number, onData: (run: PipelineRun) => void): EventSource {
  const es = new EventSource(`/sse/runs/${runId}`)
  es.onmessage = (e) => {
    try {
      onData(JSON.parse(e.data))
    } catch {}
  }
  return es
}

// ================== Agent APIs ==================

export async function fetchAgents(): Promise<Agent[]> {
  const r = await fetch(AGENTS_BASE)
  if (!r.ok) throw new Error('Failed to fetch agents')
  return r.json()
}

export async function fetchOnlineAgents(): Promise<Agent[]> {
  const r = await fetch(`${AGENTS_BASE}/online`)
  if (!r.ok) throw new Error('Failed to fetch online agents')
  return r.json()
}

export async function fetchAgent(agentId: string): Promise<Agent> {
  const r = await fetch(`${AGENTS_BASE}/${agentId}`)
  if (!r.ok) throw new Error('Failed to fetch agent')
  return r.json()
}

export async function fetchAgentDetail(agentId: string): Promise<AgentWithTasks> {
  const r = await fetch(`${AGENTS_BASE}/${agentId}/detail`)
  if (!r.ok) throw new Error('Failed to fetch agent detail')
  return r.json()
}

export async function registerAgent(data: {
  id: string
  name: string
  host: string
  port?: number
  platform: string
  role?: string
  capabilities?: string[]
  opencode_port?: number
  working_dir?: string
}): Promise<{ agent_id: string; heartbeat_interval: number }> {
  const r = await fetch(`${AGENTS_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('Failed to register agent')
  return r.json()
}

// ================== Task APIs ==================

export async function fetchTasks(limit = 50): Promise<AgentTask[]> {
  const r = await fetch(`${AGENTS_BASE}/tasks?limit=${limit}`)
  if (!r.ok) throw new Error('Failed to fetch tasks')
  return r.json()
}

export async function fetchTask(taskId: string): Promise<AgentTask> {
  const r = await fetch(`${AGENTS_BASE}/tasks/${taskId}`)
  if (!r.ok) throw new Error('Failed to fetch task')
  return r.json()
}

export async function createTask(data: {
  task_type: string
  agent_id?: string
  priority?: number
  payload?: Record<string, unknown>
}): Promise<AgentTask> {
  const r = await fetch(`${AGENTS_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('Failed to create task')
  return r.json()
}

// ================== Session APIs ==================

export async function fetchSessions(): Promise<OpenCodeSession[]> {
  const r = await fetch(`${AGENTS_BASE}/sessions`)
  if (!r.ok) throw new Error('Failed to fetch sessions')
  return r.json()
}

export async function fetchSession(sessionId: string): Promise<OpenCodeSession> {
  const r = await fetch(`${AGENTS_BASE}/sessions/${sessionId}`)
  if (!r.ok) throw new Error('Failed to fetch session')
  return r.json()
}

export async function createSession(data: {
  agent_id: string
  task_id: string
  skill: string
  working_dir: string
  context?: Record<string, unknown>
}): Promise<OpenCodeSession> {
  const r = await fetch(`${AGENTS_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('Failed to create session')
  return r.json()
}

// ================== Dashboard APIs ==================

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const r = await fetch(`${AGENTS_BASE}/dashboard/stats`)
  if (!r.ok) throw new Error('Failed to fetch dashboard stats')
  return r.json()
}

export async function fetchSkills(): Promise<Skill[]> {
  const r = await fetch(`${AGENTS_BASE}/skills`)
  if (!r.ok) throw new Error('Failed to fetch skills')
  return r.json()
}
