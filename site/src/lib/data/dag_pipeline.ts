export type NodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'waiting' | 'skipped' | 'blocked'

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
  payload?: Record<string, unknown>
  result?: unknown
  error?: unknown
}

export interface PipelineRun {
  id: string
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

export interface PipelineNodeInfo {
  type: string
  label: string
  default_mock?: boolean
}

export interface PipelineInfo {
  id: string
  name: string
  description: string
  params: PipelineParam[]
  nodes?: PipelineNodeInfo[]
  options?: {
    node_mock?: boolean
  }
}

export interface TaskSession {
  id: string
  task_id: string
  agent_id: string
  session_key: string
  skill: string
  working_dir: string
  status: string
  context?: Record<string, unknown>
  result?: unknown
  started_at: string
  completed_at: string | null
  last_activity_at: string | null
}

export interface TaskEventLog {
  id: number
  event_type: string
  entity_type: string
  entity_id: string
  old_state?: unknown
  new_state?: unknown
  metadata?: unknown
  actor: string
  created_at: string
}

export interface TranscriptPart {
  type: string
  text?: string
  tool?: string
  callID?: string
  state?: {
    status?: string
    input?: unknown
    output?: unknown
    title?: string
    metadata?: Record<string, unknown>
    time?: { start?: number; end?: number }
  }
  time?: { start?: number; end?: number }
  [key: string]: unknown
}

export interface TranscriptMessage {
  info?: {
    id?: string
    role?: string
    agent?: string
    mode?: string
    sessionID?: string
    parentID?: string
    cost?: number
    tokens?: Record<string, unknown>
    time?: { created?: number; completed?: number }
    [key: string]: unknown
  }
  parts?: TranscriptPart[]
  [key: string]: unknown
}

export interface TranscriptNode {
  session_id: string
  parent_id?: string | null
  depth: number
  messages: TranscriptMessage[]
  children: TranscriptNode[]
  errors?: string[]
  session?: Record<string, unknown>
}

export interface TaskTranscriptArchive {
  task_label?: string
  task_id?: string
  task_type?: string
  session_id?: string
  archived_at?: string
  summary?: Record<string, unknown>
  messages?: TranscriptMessage[]
  children?: TranscriptNode[]
  session_tree?: TranscriptNode
}

export interface TaskRun {
  id: string
  task_id: string
  attempt: number
  status: string
  runner: string
  agent_id?: string | null
  session_id?: string | null
  session_key?: string | null
  prompt?: string | null
  context?: Record<string, unknown>
  result?: unknown
  error?: unknown
  transcript_path?: string | null
  transcript_found?: boolean
  transcript_candidates?: Array<Record<string, unknown>>
  transcript?: TaskTranscriptArchive | null
  started_at: string
  completed_at: string | null
  last_activity_at: string | null
}

export interface TaskDetail {
  task: Record<string, unknown>
  runs: TaskRun[]
  sessions: TaskSession[]
  events: TaskEventLog[]
  transcript_path: string | null
  transcript_found: boolean
  transcript_candidates: Array<Record<string, unknown>>
  transcript: TaskTranscriptArchive | null
}
