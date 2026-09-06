import { create } from 'zustand'
import type { PipelineInfo, PipelineRun } from '@lib/data/dag_pipeline'
import { fetchPipelines, fetchRuns, startRun, cancelRun, createSSEStream, resumeRunFromNode, manualBlockNode, manualSuccessNode } from '@lib/api/dag_pipeline'

interface DAGPipelineState {
  pipelines: PipelineInfo[]
  runs: PipelineRun[]
  activeRun: PipelineRun | null
  selectedNodeId: string | null
  sseSource: EventSource | null

  loadPipelines: () => Promise<void>
  loadRuns: () => Promise<void>
  triggerRun: (pipelineId: string, params: Record<string, unknown>) => Promise<void>
  cancelActiveRun: () => Promise<void>
  resumeFromNode: (runId: string, nodeId: string) => Promise<void>
  blockNode: (runId: string, nodeId: string, reason?: string) => Promise<void>
  successNode: (runId: string, nodeId: string, reason?: string) => Promise<void>
  selectNode: (nodeId: string | null) => void
  setActiveRun: (run: PipelineRun | null) => void
}

export const useDAGPipelineStore = create<DAGPipelineState>((set, get) => ({
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
      if (updated.status === 'success' || updated.status === 'failed' || updated.status === 'skipped' || updated.status === 'blocked') {
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

  resumeFromNode: async (runId, nodeId) => {
    const { sseSource } = get()
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }

    const run = await resumeRunFromNode(runId, nodeId)
    set({ activeRun: run, selectedNodeId: nodeId })

    const es = createSSEStream(run.id, (updated) => {
      set({ activeRun: updated })
      if (updated.status === 'success' || updated.status === 'failed' || updated.status === 'skipped' || updated.status === 'blocked') {
        es.close()
        set({ sseSource: null })
        get().loadRuns()
      }
    })
    set({ sseSource: es })
    await get().loadRuns()
  },

  blockNode: async (runId, nodeId, reason) => {
    const { sseSource } = get()
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }

    const run = await manualBlockNode(runId, nodeId, reason)
    set({ activeRun: run, selectedNodeId: nodeId })
    await get().loadRuns()
  },

  successNode: async (runId, nodeId, reason) => {
    const { sseSource } = get()
    if (sseSource) {
      sseSource.close()
      set({ sseSource: null })
    }

    const run = await manualSuccessNode(runId, nodeId, reason)
    set({ activeRun: run, selectedNodeId: nodeId })
    await get().loadRuns()
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
    const es = createSSEStream(run.id, (updated) => {
      set({ activeRun: updated })
      if (updated.status === 'success' || updated.status === 'failed' || updated.status === 'skipped' || updated.status === 'blocked') {
        es.close()
        set({ sseSource: null })
      }
    })
    set({ sseSource: es })
  },
}))
