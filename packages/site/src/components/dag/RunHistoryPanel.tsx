import { cn } from '@lib/utils'
import { STATUS_DOT, formatDatetime } from './dag_utils'
import type { PipelineRun } from '@lib/data/dag_pipeline'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'

interface Props {
  runs: PipelineRun[]
}

export default function RunHistoryPanel({ runs }: Props) {
  const { setActiveRun, activeRun } = useDAGPipelineStore()

  if (runs.length === 0) {
    return <p className="text-xs text-slate-500 px-2 py-4 text-center">No runs yet</p>
  }

  return (
    <div className="space-y-1">
      {runs.map((run) => (
        <button
          key={run.id}
          onClick={() => setActiveRun(activeRun?.id === run.id ? null : run)}
          className={cn(
            'w-full text-left px-3 py-2 rounded-lg transition-colors text-sm',
            activeRun?.id === run.id
              ? 'bg-blue-900/40 border border-blue-700'
              : 'hover:bg-slate-800 border border-transparent'
          )}
        >
          <div className="flex items-center gap-2">
            <span className={cn('w-2 h-2 rounded-full flex-shrink-0', STATUS_DOT[run.status])} />
            <span className="font-medium text-slate-200 truncate flex-1">{run.pipeline_name}</span>
            <span className="text-xs text-slate-500">#{run.id}</span>
          </div>
          <div className="text-xs text-slate-500 mt-0.5 pl-4">{formatDatetime(run.created_at)}</div>
        </button>
      ))}
    </div>
  )
}
