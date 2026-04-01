import { create } from 'zustand'
import type { PipelineInfo, PipelineRun } from '../types'
import { fetchPipelines, fetchRuns, startRun, cancelRun, createSSEStream } from '../api'

interface AppState {
  pipelines: PipelineInfo[]
  runs: PipelineRun[]
  activeRun: PipelineRun | null
  selectedNodeId: string | null
  sseSource: EventSource | null

  loadPipelines: () => Promise<void>
  loadRuns: () => Promise<void>
  triggerRun: (pipelineId: string, params: Record<string, unknown>) => Promise<void>
  cancelActiveRun: () => Promise<void>
  selectNode: (nodeId: string | null) => void
  setActiveRun: (run: PipelineRun | null) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  pipelines: [],
  runs: [],
  activeRun: null,
  selectedNodeId: null,
  sseSource: null,

  loadPipelines: async () => {
    const pipelines = await fetchPipelines()
    set({ pipelines })
  },

  loadRuns: async () => {
    const runs = await fetchRuns()
    set({ runs })
  },

  triggerRun: async (pipelineId, params) => {
    const { sseSource } = get()
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }

    const run = await startRun(pipelineId, params)
    set({ activeRun: run, selectedNodeId: null })

    const es = createSSEStream(run.id, (updated) => {
      set({ activeRun: updated })
      if (updated.status === 'success' || updated.status === 'failed') {
        es.close()
        set({ sseSource: null })
        get().loadRuns()
      }
    })
    set({ sseSource: es })
    await get().loadRuns()
  },

  cancelActiveRun: async () => {
    const { activeRun, sseSource } = get()
    if (!activeRun) return
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }
    await cancelRun(activeRun.id)
    set({ activeRun: null })
  },

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  setActiveRun: (run) => {
    const { sseSource } = get()
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }
    if (!run) {
      set({ activeRun: null, selectedNodeId: null })
      return
    }
    set({ activeRun: run, selectedNodeId: null })
    if (run.status === 'running' || run.status === 'pending') {
      const es = createSSEStream(run.id, (updated) => {
        set({ activeRun: updated })
        if (updated.status === 'success' || updated.status === 'failed') {
          es.close()
          set({ sseSource: null })
        }
      })
      set({ sseSource: es })
    }
  },
}))
