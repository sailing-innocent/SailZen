export type NodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'waiting' | 'skipped'

export interface NodeRun {
  id: number
  node_id: string
  node_name: string
  node_type: string
  description: string
  depends_on: string[]
  status: NodeStatus
  logs: string[]
  started_at: string | null
  finished_at: string | null
  duration: number | null
  is_dynamic: boolean
  can_spawn: boolean
}

export interface PipelineRun {
  id: number
  pipeline_id: string
  pipeline_name: string
  params: Record<string, unknown>
  status: NodeStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  node_runs: NodeRun[]
}

export interface PipelineParam {
  key: string
  label: string
  type: 'string' | 'select' | 'boolean'
  default: string | boolean
  options?: string[]
}

export interface PipelineInfo {
  id: string
  name: string
  description: string
  params: PipelineParam[]
}

// ================== Agent Types ==================

export type AgentStatus = 'online' | 'offline' | 'busy' | 'maintenance'
export type AgentRole = 'manager' | 'worker'
export type Platform = 'windows' | 'macos' | 'linux'
export type TaskStatus = 'pending' | 'assigned' | 'running' | 'success' | 'failed'
export type SessionStatus = 'starting' | 'running' | 'completed' | 'failed' | 'timeout'

export interface Agent {
  id: string
  name: string
  host: string
  port: number
  platform: Platform
  role: AgentRole
  capabilities: string[]
  status: AgentStatus
  current_task_id: string | null
  opencode_port: number | null
  working_dir: string | null
  heartbeat_at: string | null
  registered_at: string
}

export interface AgentTask {
  id: string
  agent_id: string
  task_type: string
  status: TaskStatus
  priority: number
  payload: Record<string, unknown>
  result: Record<string, unknown> | null
  error: string | null
  retry_count: number
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface OpenCodeSession {
  id: string
  agent_id: string
  task_id: string
  session_key: string
  skill: string
  working_dir: string
  status: SessionStatus
  context: Record<string, unknown> | null
  result: Record<string, unknown> | null
  logs: string[]
  started_at: string
  completed_at: string | null
  last_activity_at: string | null
}

export interface DashboardStats {
  total_agents: number
  online_agents: number
  busy_agents: number
  total_tasks: number
  pending_tasks: number
  running_tasks: number
  completed_tasks: number
  failed_tasks: number
}

export interface AgentWithTasks {
  agent: Agent
  current_task: AgentTask | null
  recent_tasks: AgentTask[]
  active_sessions: OpenCodeSession[]
}

export interface Skill {
  name: string
  description: string
}

// ================== Workflow Types ==================

export interface WorkflowStep {
  step_id: string
  step_name: string
  task_type: string
  agent_id: string | null
  status: string
  depends_on: string[]
  started_at: string | null
  completed_at: string | null
}

export interface Workflow {
  id: string
  name: string
  description: string
  workflow_type: string
  status: string
  params: Record<string, unknown>
  steps: WorkflowStep[]
  created_at: string
  started_at: string | null
  completed_at: string | null
}
