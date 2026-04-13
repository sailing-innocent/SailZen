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
