import { Link } from 'react-router-dom'
import { X, Clock, Hash, Zap, FileText, RotateCcw, ExternalLink, Ban, CheckCheck, FileSearch } from 'lucide-react'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'
import { cn } from '@lib/utils'
import { STATUS_COLOR, STATUS_DOT, NODE_TYPE_ICON, formatDuration, formatDatetime } from './dag_utils'
import type { NodeRun } from '@lib/data/dag_pipeline'

interface Props {
  nodeRun: NodeRun
  runId: string
}

export default function NodeDetailPanel({ nodeRun, runId }: Props) {
  const selectNode = useDAGPipelineStore((s) => s.selectNode)
  const resumeFromNode = useDAGPipelineStore((s) => s.resumeFromNode)
  const blockNode = useDAGPipelineStore((s) => s.blockNode)
  const successNode = useDAGPipelineStore((s) => s.successNode)
  const icon = NODE_TYPE_ICON[nodeRun.node_type] ?? '\u25C6'
  const payload = nodeRun.payload ?? {}
  const branchName = typeof payload.branch_name === 'string' ? payload.branch_name : ''
  const subbatchBaseBranch = typeof payload.subbatch_base_branch === 'string'
    ? payload.subbatch_base_branch
    : ''
  const batchPredecessorBranch = typeof payload.batch_predecessor_branch === 'string'
    ? payload.batch_predecessor_branch
    : ''
  const worktreePath = typeof payload.worktree_path === 'string' ? payload.worktree_path : ''
  // For pick nodes: sub_batch_id and batch_id from pick_handler extra_result
  const subBatchId = typeof payload.sub_batch_id === 'string' ? payload.sub_batch_id : ''
  const batchId = typeof payload.batch_id === 'string' ? payload.batch_id : ''
  const isPickNode = nodeRun.node_type === 'pick'

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
        <Link
          to={`/tasks/${nodeRun.node_id}`}
          className="w-full flex items-center justify-center gap-2 text-xs text-blue-200 bg-blue-900/30 hover:bg-blue-800/40 border border-blue-700 hover:border-blue-500 px-3 py-2 rounded transition-colors"
          title="Open full task transcript and subagent review page"
        >
          <ExternalLink size={13} /> 查看任务详情
        </Link>

        {isPickNode && subBatchId && (
          <Link
            to={`/batches/${batchId || 'unknown'}/sub-batches/${subBatchId}/review`}
            className="w-full flex items-center justify-center gap-2 text-xs text-emerald-200 bg-emerald-900/30 hover:bg-emerald-800/40 border border-emerald-700 hover:border-emerald-500 px-3 py-2 rounded transition-colors"
            title="查看 commit map、冲突 evidence、审查结论"
          >
            <FileSearch size={13} /> 审阅 Commit Map
          </Link>
        )}

        <button
          onClick={() => {
            if (!window.confirm(`Resume pipeline from ${nodeRun.node_name}? This will reset this node and downstream nodes.`)) return
            resumeFromNode(runId, nodeRun.node_id).catch((err) => {
              window.alert(err instanceof Error ? err.message : String(err))
            })
          }}
          className="w-full flex items-center justify-center gap-2 text-xs text-amber-200 bg-amber-900/30 hover:bg-amber-800/40 border border-amber-700 hover:border-amber-500 px-3 py-2 rounded transition-colors"
          title="Reset this node and downstream nodes, then restart runner"
        >
          <RotateCcw size={13} /> Resume from this node
        </button>

        <button
          onClick={() => {
            if (!window.confirm(`强制 block 节点 ${nodeRun.node_name}? 这会停止 pipeline，并强杀可能仍在运行的 CodeMaker runner，方便人工接管清理。`)) return
            blockNode(runId, nodeRun.node_id, 'Dashboard manual block: human takeover after LLM misbehavior').catch((err) => {
              window.alert(err instanceof Error ? err.message : String(err))
            })
          }}
          className="w-full flex items-center justify-center gap-2 text-xs text-red-200 bg-red-950/40 hover:bg-red-900/50 border border-red-800 hover:border-red-500 px-3 py-2 rounded transition-colors"
          title="Force this node to BLOCKED, stop pipeline, and kill possible CodeMaker runner"
        >
          <Ban size={13} /> 手动 Block / Kill Runner
        </button>

        <button
          onClick={() => {
            const nodeStatus = nodeRun.status
            const isBlocker = nodeStatus === 'failed' || nodeStatus === 'blocked' || nodeStatus === 'running' || nodeStatus === 'waiting'
            const confirmMsg = isBlocker
              ? `标记 ${nodeRun.node_name} 为 SUCCESS（人类专家接管完成）? 这将直接从 SUCCESS 状态推进 pipeline 后续节点。`
              : `节点 ${nodeRun.node_name} 当前状态为 ${nodeStatus}。强制标记为 SUCCESS 意味着人类专家已接管完成该任务，将推进 pipeline。`
            if (!window.confirm(confirmMsg)) return
            successNode(runId, nodeRun.node_id, 'Dashboard manual success: human expert takeover complete').catch((err) => {
              window.alert(err instanceof Error ? err.message : String(err))
            })
          }}
          className="w-full flex items-center justify-center gap-2 text-xs text-emerald-200 bg-emerald-950/40 hover:bg-emerald-900/50 border border-emerald-800 hover:border-emerald-500 px-3 py-2 rounded transition-colors"
          title="Mark this node as SUCCESS — human expert has taken over and completed the task"
        >
          <CheckCheck size={13} /> 人类接管（标记为 SUCCESS）
        </button>

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

        {(branchName || subbatchBaseBranch || batchPredecessorBranch || worktreePath) && (
          <div className="bg-slate-800 rounded p-2 text-xs space-y-1">
            <div className="text-slate-500 font-medium">Branch Context</div>
            {batchPredecessorBranch && (
              <div>
                <span className="text-slate-500">Batch predecessor: </span>
                <span className="text-amber-300 font-mono break-all">{batchPredecessorBranch}</span>
              </div>
            )}
            {subbatchBaseBranch && (
              <div>
                <span className="text-slate-500">SubBatch base: </span>
                <span className="text-blue-300 font-mono break-all">{subbatchBaseBranch}</span>
              </div>
            )}
            {branchName && (
              <div>
                <span className="text-slate-500">SubBatch branch: </span>
                <span className="text-slate-300 font-mono break-all">{branchName}</span>
              </div>
            )}
            {worktreePath && (
              <div>
                <span className="text-slate-500">Worktree: </span>
                <span className="text-slate-300 font-mono break-all">{worktreePath}</span>
              </div>
            )}
          </div>
        )}

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
