import { X, Clock, Hash, Zap, FileText } from 'lucide-react'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'
import { cn } from '@lib/utils'
import { STATUS_COLOR, STATUS_DOT, NODE_TYPE_ICON, formatDuration, formatDatetime } from './dag_utils'
import type { NodeRun } from '@lib/data/dag_pipeline'

interface Props {
  nodeRun: NodeRun
}

export default function NodeDetailPanel({ nodeRun }: Props) {
  const selectNode = useDAGPipelineStore((s) => s.selectNode)
  const icon = NODE_TYPE_ICON[nodeRun.node_type] ?? '\u25C6'

  return (
    <div className="h-full flex flex-col bg-slate-900 border-l border-slate-700 w-80 flex-shrink-0">
      <div className={cn('flex items-center gap-2 px-4 py-3 border-b border-slate-700', STATUS_COLOR[nodeRun.status])}>
        <span className="text-xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm truncate">{nodeRun.node_name}</div>
          <div className="text-xs opacity-70 capitalize">{nodeRun.node_type}</div>
        </div>
        <button
          onClick={() => selectNode(null)}
          className="p-1 rounded hover:bg-white/10 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex items-center gap-2">
          <span className={cn('w-3 h-3 rounded-full flex-shrink-0', STATUS_DOT[nodeRun.status])} />
          <span className="text-sm font-medium capitalize text-slate-200">{nodeRun.status}</span>
          {nodeRun.is_dynamic && (
            <span className="text-xs bg-purple-700/60 text-purple-200 px-2 py-0.5 rounded-full">Dynamic</span>
          )}
          {nodeRun.can_spawn && (
            <span className="text-xs bg-orange-700/60 text-orange-200 px-2 py-0.5 rounded-full">Spawner</span>
          )}
        </div>

        <p className="text-xs text-slate-400 leading-relaxed">{nodeRun.description || '\u2014'}</p>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-800 rounded p-2">
            <div className="flex items-center gap-1 text-slate-500 mb-1">
              <Clock size={11} /> Started
            </div>
            <div className="text-slate-300">{formatDatetime(nodeRun.started_at)}</div>
          </div>
          <div className="bg-slate-800 rounded p-2">
            <div className="flex items-center gap-1 text-slate-500 mb-1">
              <Clock size={11} /> Finished
            </div>
            <div className="text-slate-300">{formatDatetime(nodeRun.finished_at)}</div>
          </div>
          <div className="bg-slate-800 rounded p-2">
            <div className="flex items-center gap-1 text-slate-500 mb-1">
              <Zap size={11} /> Duration
            </div>
            <div className="text-slate-300">{formatDuration(nodeRun.duration)}</div>
          </div>
          <div className="bg-slate-800 rounded p-2">
            <div className="flex items-center gap-1 text-slate-500 mb-1">
              <Hash size={11} /> Node ID
            </div>
            <div className="text-slate-300 font-mono truncate">{nodeRun.node_id}</div>
          </div>
        </div>

        {nodeRun.depends_on.length > 0 && (
          <div>
            <div className="text-xs text-slate-500 mb-1">Depends on</div>
            <div className="flex flex-wrap gap-1">
              {nodeRun.depends_on.map((d) => (
                <span key={d} className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded font-mono">
                  {d}
                </span>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center gap-1 text-xs text-slate-500 mb-2">
            <FileText size={11} /> Logs
          </div>
          <div className="bg-slate-950 rounded p-2 font-mono text-xs text-slate-300 space-y-1 max-h-48 overflow-y-auto">
            {nodeRun.logs.length === 0 ? (
              <span className="text-slate-600 italic">No output yet</span>
            ) : (
              nodeRun.logs.map((line, i) => (
                <div key={i} className={cn('leading-relaxed', line.startsWith('[ERROR]') ? 'text-red-400' : '')}>
                  <span className="text-slate-600 mr-2 select-none">{String(i + 1).padStart(2, '0')}</span>
                  {line}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
