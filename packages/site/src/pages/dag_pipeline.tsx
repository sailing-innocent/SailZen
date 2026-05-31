import { useEffect, useState } from 'react'
import { GitBranch, Play, History, Square, RefreshCw, Database, Zap } from 'lucide-react'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'
import { useWorkspaceStore } from '@lib/store'
import DAGCanvas from '@components/dag/DAGCanvas'
import NodeDetailPanel from '@components/dag/NodeDetailPanel'
import RunConfigPanel from '@components/dag/RunConfigPanel'
import RunHistoryPanel from '@components/dag/RunHistoryPanel'
import AppShell from '@components/app_shell'
import { cn } from '@lib/utils'
import { STATUS_DOT } from '@components/dag/dag_utils'
import type { PipelineInfo } from '@lib/data/dag_pipeline'

const DAGPipelinePage = () => {
  const {
    pipelines, runs, activeRun, selectedNodeId,
    loadPipelines, loadRuns, cancelActiveRun,
  } = useDAGPipelineStore()

  const { workspaces, selectedWorkspaceId, selectWorkspace } = useWorkspaceStore()

  const [selectedPipeline, setSelectedPipeline] = useState<PipelineInfo | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [tab, setTab] = useState<'pipelines' | 'history'>('pipelines')

  useEffect(() => {
    loadPipelines()
    loadRuns()
  }, [])

  const selectedNode = activeRun?.node_runs.find((n) => n.node_id === selectedNodeId) ?? null

  const runningCount = activeRun?.node_runs.filter((n) => n.status === 'running').length ?? 0
  const doneCount = activeRun?.node_runs.filter(
    (n) => n.status === 'success' || n.status === 'failed' || n.status === 'skipped'
  ).length ?? 0
  const totalCount = activeRun?.node_runs.length ?? 0

  const selectedWs = workspaces.find((ws) => ws.id === selectedWorkspaceId)

  return (
    <AppShell>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Header bar */}
        <header className="flex items-center gap-3 px-5 py-3 border-b border-slate-800 bg-slate-900 flex-shrink-0">
          <GitBranch size={20} className="text-blue-400" />
          <h1 className="font-bold text-lg tracking-tight">DAG Pipeline</h1>

          {/* Workspace indicator */}
          {selectedWs && (
            <div className="flex items-center gap-1.5 ml-2 px-2 py-1 rounded bg-slate-800 border border-slate-700">
              <Database size={12} className="text-slate-500" />
              <span className="text-xs text-slate-400">{selectedWs.name}</span>
            </div>
          )}

          {activeRun && (
            <div className="flex items-center gap-3 ml-4 flex-1">
              <span className={cn('w-2.5 h-2.5 rounded-full', STATUS_DOT[activeRun.status])} />
              <span className="text-sm font-medium text-slate-300">{activeRun.pipeline_name}</span>
              <span className="text-xs text-slate-500">
                {doneCount}/{totalCount} nodes · {runningCount} running
              </span>
              {(activeRun.status === 'running' || activeRun.status === 'pending') && (
                <button
                  onClick={cancelActiveRun}
                  className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 border border-red-800 hover:border-red-600 px-2 py-1 rounded transition-colors"
                >
                  <Square size={11} /> Cancel
                </button>
              )}
            </div>
          )}

          <button
            onClick={() => { loadPipelines(); loadRuns() }}
            className="ml-auto p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={15} />
          </button>
        </header>

        <div className="flex flex-1 min-h-0">
          {/* Left sidebar */}
          <aside className="w-64 flex-shrink-0 border-r border-slate-800 bg-slate-900 flex flex-col min-h-0 overflow-hidden">
            {/* Workspace selector */}
            {!selectedWorkspaceId && workspaces.length > 0 && (
              <div className="p-2 border-b border-slate-800">
                <div className="text-xs text-amber-400 mb-1.5">⚠️ 请先选择工作空间</div>
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => selectWorkspace(ws.id)}
                    className="w-full text-left px-2 py-1.5 rounded text-xs text-slate-300 hover:bg-slate-800 border border-slate-700 mb-1"
                  >
                    {ws.name}
                  </button>
                ))}
              </div>
            )}

            <div className="flex border-b border-slate-800">
              <button
                onClick={() => setTab('pipelines')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                  tab === 'pipelines' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-500 hover:text-slate-300'
                )}
              >
                <Play size={12} /> Pipelines
              </button>
              <button
                onClick={() => setTab('history')}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                  tab === 'history' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-500 hover:text-slate-300'
                )}
              >
                <History size={12} /> History ({runs.length})
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {tab === 'pipelines' && (
                <div className="space-y-2">
                  {pipelines.map((p) => {
                    const isInit = p.id === 'globalbatch_init'
                    return (
                      <button
                        key={p.id}
                        onClick={() => {
                          if (!selectedWorkspaceId) return
                          setSelectedPipeline(p)
                          setShowConfig(true)
                        }}
                        disabled={!selectedWorkspaceId}
                        className={cn(
                          'w-full text-left p-3 rounded-lg border transition-all',
                          !selectedWorkspaceId
                            ? 'border-slate-800 bg-slate-800/30 opacity-50 cursor-not-allowed'
                            : selectedPipeline?.id === p.id && showConfig
                              ? isInit ? 'border-amber-500 bg-amber-900/30' : 'border-blue-600 bg-blue-900/30'
                              : isInit
                                ? 'border-amber-700/50 hover:border-amber-500 hover:bg-amber-900/20 bg-amber-950/20'
                                : 'border-slate-700 hover:border-slate-500 hover:bg-slate-800'
                        )}
                      >
                        <div className="font-medium text-sm text-slate-200">{p.name}</div>
                        <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">{p.description}</div>
                        <div className="flex items-center gap-1 mt-2">
                          {isInit ? (
                            <>
                              <Zap size={10} className="text-amber-400" />
                              <span className="text-xs text-amber-400">
                                {selectedWorkspaceId ? 'Quick Test Init' : '需要先选择工作空间'}
                              </span>
                            </>
                          ) : (
                            <>
                              <Play size={10} className="text-blue-400" />
                              <span className="text-xs text-blue-400">
                                {selectedWorkspaceId ? 'Configure & Run' : '需要先选择工作空间'}
                              </span>
                            </>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
              {tab === 'history' && <RunHistoryPanel runs={runs} />}
            </div>
          </aside>

          {/* Main area */}
          <main className="flex-1 flex flex-col min-h-0 relative">
            {showConfig && selectedPipeline && selectedWorkspaceId && (
              <div
                className="absolute inset-0 bg-black/60 z-10 flex items-center justify-center p-6"
                onClick={() => setShowConfig(false)}
              >
                <div onClick={(e) => e.stopPropagation()}>
                  <RunConfigPanel
                    pipeline={selectedPipeline}
                    workspaceId={selectedWorkspaceId}
                    onClose={() => setShowConfig(false)}
                  />
                </div>
              </div>
            )}

            {activeRun ? (
              <div className="flex flex-1 min-h-0 overflow-hidden">
                <div className="relative flex-1 min-w-0" style={{ minHeight: 0, height: '100%' }}>
                  <DAGCanvas run={activeRun} />
                </div>
                {selectedNode && activeRun && <NodeDetailPanel nodeRun={selectedNode} runId={activeRun.id} />}
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-600">
                <GitBranch size={48} className="mb-4 opacity-30" />
                <p className="text-lg font-medium">No active run</p>
                <p className="text-sm mt-1">
                  {selectedWorkspaceId
                    ? 'Select a pipeline from the left panel to get started'
                    : 'Please select a workspace first, then choose a pipeline'}
                </p>
              </div>
            )}
          </main>
        </div>
      </div>
    </AppShell>
  )
}

export default DAGPipelinePage
