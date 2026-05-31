import { useState } from 'react'
import { Play, X, Database, Zap, CheckSquare } from 'lucide-react'
import type { PipelineInfo } from '@lib/data/dag_pipeline'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'
import { cn } from '@lib/utils'

interface Props {
  pipeline: PipelineInfo
  workspaceId: string
  onClose: () => void
}

export default function RunConfigPanel({ pipeline, workspaceId, onClose }: Props) {
  const { triggerRun } = useDAGPipelineStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const initialParams = Object.fromEntries(
    pipeline.params.map((p) => [p.key, p.default])
  )
  const nodeDefinitions = pipeline.nodes || []
  // Pre-fill workspace_id from the selected workspace
  initialParams['workspace_id'] = workspaceId
  initialParams['mock_task_types'] = nodeDefinitions
    .filter((node) => node.default_mock)
    .map((node) => node.type)
  const [params, setParams] = useState<Record<string, unknown>>(initialParams)

  const toggleNodeMock = (nodeType: string, checked: boolean) => {
    setParams((prev) => {
      const current = Array.isArray(prev['mock_task_types'])
        ? [...(prev['mock_task_types'] as string[])]
        : []
      const next = checked
        ? Array.from(new Set([...current, nodeType]))
        : current.filter((item) => item !== nodeType)
      return { ...prev, mock_task_types: next }
    })
  }

  const setAllNodeMocks = (checked: boolean) => {
    setParams((prev) => ({
      ...prev,
      mock_task_types: checked ? nodeDefinitions.map((node) => node.type) : [],
    }))
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      await triggerRun(pipeline.id, params)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const isInitPipeline = pipeline.id === 'globalbatch_init'
  const supportsNodeMock = isInitPipeline && (pipeline.options?.node_mock ?? true)
  const mockTaskTypes = Array.isArray(params['mock_task_types']) ? params['mock_task_types'] as string[] : []
  const mockedNodeCount = mockTaskTypes.length
  const initWorkspaceMocked = mockTaskTypes.includes('init_workspace')

  return (
    <div className={cn(
      'border rounded-xl p-5 w-full max-w-md shadow-2xl',
      isInitPipeline
        ? 'bg-gradient-to-br from-amber-950/80 to-slate-800 border-amber-600/50'
        : 'bg-slate-800 border-slate-600',
    )}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            {isInitPipeline && <Zap size={18} className="text-amber-400" />}
            <h3 className="font-bold text-slate-100">{pipeline.name}</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{pipeline.description}</p>
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-slate-700 text-slate-400">
          <X size={18} />
        </button>
      </div>

      {/* Init pipeline info banner */}
      {isInitPipeline && (
        <div className="mb-4 p-2.5 rounded-lg bg-amber-900/30 border border-amber-700/50">
          <div className="text-xs text-amber-300 font-medium mb-1">📋 GlobalBatch 流程</div>
          <div className="text-xs text-amber-200/70 space-y-0.5">
            <div>1. DAG 会先创建入口节点 Init Workspace，再进入 pick_a</div>
            <div>2. 默认 Init Workspace 执行真实环境准备：clone / fetch / worktree / start_globalbatch</div>
            <div>3. 勾选 Init Workspace 的 mock 即表示跳过初始化，后续节点仍按同一 DAG 推进</div>
            <div>4. 其他被勾选为 mock 的节点会自动成功，用于保持主流程通畅</div>
          </div>
        </div>
      )}

      {/* Workspace info (read-only) */}
      <div className="mb-4 p-2 rounded bg-slate-900 border border-slate-700 flex items-center gap-2">
        <Database size={14} className="text-blue-400" />
        <span className="text-xs text-slate-400">Workspace:</span>
        <span className="text-xs text-slate-200 font-mono">{workspaceId.slice(0, 16)}...</span>
      </div>

      <div className="space-y-3 mb-5">
        {pipeline.params.filter(p => p.key !== 'workspace_id').map((p) => (
          <div key={p.key}>
            <label className="text-xs text-slate-400 block mb-1">{p.label}</label>
            {p.type === 'string' && (
              <input
                type="text"
                value={String(params[p.key] ?? '')}
                onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                className="w-full bg-slate-900 border border-slate-600 rounded px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
            )}
            {p.type === 'select' && (
              <select
                value={String(params[p.key] ?? '')}
                onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                className={cn(
                  'w-full bg-slate-900 border rounded px-3 py-1.5 text-sm focus:outline-none',
                  p.key === 'fail_pattern' && String(params[p.key] ?? 'none') !== 'none'
                    ? 'border-red-500/60 text-red-300 focus:border-red-400'
                    : 'border-slate-600 text-slate-200 focus:border-blue-500',
                )}
              >
                {p.options?.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            )}
            {p.type === 'boolean' && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={Boolean(params[p.key])}
                  onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.checked }))}
                  className="accent-blue-500 w-4 h-4"
                />
                <span className="text-sm text-slate-300">Enabled</span>
              </label>
            )}
          </div>
        ))}
      </div>

      {supportsNodeMock && nodeDefinitions.length ? (
        <div className="mb-4 p-3 rounded-lg bg-slate-900/70 border border-slate-700">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-1.5">
              <CheckSquare size={14} className="text-cyan-300" />
              <span className="text-xs text-slate-200 font-semibold">Node Mock 配置</span>
            </div>
            <div className="flex items-center gap-2 text-[11px]">
              <button
                type="button"
                onClick={() => setAllNodeMocks(false)}
                className="text-slate-400 hover:text-slate-200"
              >
                全部真实
              </button>
              <span className="text-slate-600">|</span>
              <button
                type="button"
                onClick={() => setAllNodeMocks(true)}
                className="text-cyan-300 hover:text-cyan-200"
              >
                全部 mock
              </button>
            </div>
          </div>
          <div className="text-[11px] text-slate-500 mb-2">
            默认全部非 mock。勾选 Init Workspace 即表示跳过初始化；勾选其他节点会让对应类型任务自动成功。
          </div>
          <div className="grid grid-cols-2 gap-2">
            {nodeDefinitions.map((node) => {
              const checked = mockTaskTypes.includes(node.type)
              return (
                <label
                  key={node.type}
                  className={cn(
                    'flex items-center gap-2 rounded border px-2 py-1.5 cursor-pointer transition-colors',
                    checked
                      ? 'bg-cyan-950/50 border-cyan-600/60 text-cyan-100'
                      : 'bg-slate-950/40 border-slate-700 text-slate-300 hover:border-slate-500',
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => toggleNodeMock(node.type, e.target.checked)}
                    className="accent-cyan-500 w-3.5 h-3.5"
                  />
                  <span className="text-xs truncate" title={`${node.label} (${node.type})`}>
                    {node.label}
                  </span>
                </label>
              )
            })}
          </div>
          <div className="text-[11px] text-slate-500 mt-2">
            本次将 mock: <span className="text-cyan-300">{mockedNodeCount ? mockTaskTypes.join(', ') : '无'}</span>
          </div>
        </div>
      ) : null}

      {/* Init preview for globalbatch_init */}
      {isInitPipeline && (
        <div className="mb-4 p-2 rounded bg-slate-900/50 border border-slate-700">
          <div className="text-xs text-slate-500 mb-1">预览分配</div>
          <div className="text-xs text-slate-300 font-mono">
            {Array.from({ length: Number(params['subbatch_count'] || 4) }, (_, i) => {
              const suffix = String.fromCharCode(97 + i)
              const size = Number(params['subbatch_size'] || 10)
              const start = i * size + 1
              const end = (i + 1) * size
              return (
                <div key={i} className="flex items-center gap-1">
                  <span>_{suffix}: commit #{start}..#{end}</span>
                  <span className="text-slate-500">({size} commits)</span>
                  <span className="text-slate-600">
                    base={i === 0
                      ? String(params['predecessor_branch'] || '<required>')
                      : `netease/globalbatch/MM/DD_${String.fromCharCode(96 + i)}`}
                  </span>
                </div>
              )
            })}
            <div className="text-slate-500 mt-1">
              Batch predecessor: <span className="text-amber-300">{String(params['predecessor_branch'] || '<required>')}</span>
            </div>
            <div className="text-slate-500 mt-1">
              Init Workspace: <span className={initWorkspaceMocked ? 'text-cyan-300' : 'text-amber-300'}>
                {initWorkspaceMocked ? 'mock（跳过真实初始化）' : 'real（执行真实初始化）'}
              </span>
            </div>
            <div className="text-slate-500 mt-1">
              预计: {Number(params['subbatch_count'] || 4) * Number(params['subbatch_size'] || 10)} commits,{' '}
              {Number(params['subbatch_count'] || 4) * 6 + 3} tasks
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/50 bg-red-950/50 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <button
        onClick={handleRun}
        disabled={loading}
        className={cn(
          'w-full flex items-center justify-center gap-2 py-2 rounded-lg font-semibold text-sm transition-all',
          loading
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : isInitPipeline
              ? 'bg-amber-600 hover:bg-amber-500 text-white'
              : 'bg-blue-600 hover:bg-blue-500 text-white'
        )}
      >
        {isInitPipeline ? <Zap size={15} /> : <Play size={15} />}
        {loading
          ? 'Starting...'
          : isInitPipeline
            ? `${initWorkspaceMocked ? '⚡ 启动 GlobalBatch（Init Workspace mock）' : '⚡ 初始化 GlobalBatch'}${mockedNodeCount ? `（${mockedNodeCount} 类节点 mock）` : ''}`
            : '🚀 开始 Pick'}
      </button>
    </div>
  )
}
