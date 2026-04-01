import { create } from 'zustand'
import type { 
  Agent, AgentTask, OpenCodeSession, DashboardStats, Skill, AgentWithTasks 
} from '../types'
import { 
  fetchAgents, fetchTasks, fetchSessions, fetchDashboardStats, 
  fetchSkills, createTask, createSession, fetchAgentDetail
} from '../api'

interface AgentState {
  agents: Agent[]
  tasks: AgentTask[]
  sessions: OpenCodeSession[]
  stats: DashboardStats | null
  skills: Skill[]
  selectedAgentId: string | null
  selectedAgentDetail: AgentWithTasks | null
  isLoading: boolean
  error: string | null
  pollInterval: number | null

  // Actions
  loadAgents: () => Promise<void>
  loadTasks: () => Promise<void>
  loadSessions: () => Promise<void>
  loadStats: () => Promise<void>
  loadSkills: () => Promise<void>
  loadAll: () => Promise<void>
  selectAgent: (agentId: string | null) => void
  loadAgentDetail: (agentId: string) => Promise<void>
  dispatchTask: (taskType: string, agentId?: string, payload?: Record<string, unknown>) => Promise<AgentTask>
  startSession: (agentId: string, taskId: string, skill: string, workingDir: string, context?: Record<string, unknown>) => Promise<OpenCodeSession>
  startPolling: (intervalMs?: number) => void
  stopPolling: () => void
}

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  tasks: [],
  sessions: [],
  stats: null,
  skills: [],
  selectedAgentId: null,
  selectedAgentDetail: null,
  isLoading: false,
  error: null,
  pollInterval: null,

  loadAgents: async () => {
    try {
      const agents = await fetchAgents()
      set({ agents })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  loadTasks: async () => {
    try {
      const tasks = await fetchTasks(50)
      set({ tasks })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  loadSessions: async () => {
    try {
      const sessions = await fetchSessions()
      set({ sessions })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  loadStats: async () => {
    try {
      const stats = await fetchDashboardStats()
      set({ stats })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  loadSkills: async () => {
    try {
      const skills = await fetchSkills()
      set({ skills })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  loadAll: async () => {
    set({ isLoading: true, error: null })
    try {
      await Promise.all([
        get().loadAgents(),
        get().loadTasks(),
        get().loadSessions(),
        get().loadStats(),
        get().loadSkills(),
      ])
    } finally {
      set({ isLoading: false })
    }
  },

  selectAgent: (agentId) => {
    set({ selectedAgentId: agentId, selectedAgentDetail: null })
    if (agentId) {
      get().loadAgentDetail(agentId)
    }
  },

  loadAgentDetail: async (agentId) => {
    try {
      const detail = await fetchAgentDetail(agentId)
      set({ selectedAgentDetail: detail })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  dispatchTask: async (taskType, agentId, payload) => {
    const task = await createTask({
      task_type: taskType,
      agent_id: agentId,
      payload: payload || {},
    })
    await get().loadTasks()
    return task
  },

  startSession: async (agentId, taskId, skill, workingDir, context) => {
    const session = await createSession({
      agent_id: agentId,
      task_id: taskId,
      skill,
      working_dir: workingDir,
      context: context || {},
    })
    await get().loadSessions()
    return session
  },

  startPolling: (intervalMs = 3000) => {
    const { pollInterval } = get()
    if (pollInterval) return

    const interval = window.setInterval(async () => {
      await get().loadAll()
      const { selectedAgentId } = get()
      if (selectedAgentId) {
        await get().loadAgentDetail(selectedAgentId)
      }
    }, intervalMs)
    
    set({ pollInterval: interval })
  },

  stopPolling: () => {
    const { pollInterval } = get()
    if (pollInterval) {
      clearInterval(pollInterval)
      set({ pollInterval: null })
    }
  },
}))
