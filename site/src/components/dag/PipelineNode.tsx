import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@lib/utils'
import { STATUS_COLOR, STATUS_DOT, NODE_TYPE_ICON, formatDuration } from './dag_utils'
import type { NodeStatus } from '@lib/data/dag_pipeline'

export interface PipelineNodeData {
  nodeId: string
  label: string
  nodeType: string
  status: NodeStatus
  duration: number | null
  isDynamic: boolean
  canSpawn: boolean
  selected: boolean
  onClick: () => void
}

function PipelineNode({ data }: NodeProps) {
  const d = data as unknown as PipelineNodeData
  const icon = NODE_TYPE_ICON[d.nodeType] ?? '\u25C6'

  return (
    <div
      onClick={d.onClick}
      className={cn(
        'relative cursor-pointer rounded-lg border-2 px-3 py-2 w-[210px] transition-all duration-200 select-none',
        STATUS_COLOR[d.status],
        d.selected ? 'ring-2 ring-white/60 scale-105' : 'hover:scale-102 hover:brightness-110'
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-400 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg leading-none">{icon}</span>
        <span className="font-semibold text-sm truncate flex-1">{d.label}</span>
        {d.isDynamic && (
          <span className="text-[10px] bg-purple-700/60 text-purple-200 px-1 rounded">DYN</span>
        )}
        {d.canSpawn && (
          <span className="text-[10px] bg-orange-700/60 text-orange-200 px-1 rounded">+</span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span className={cn('w-2 h-2 rounded-full flex-shrink-0', STATUS_DOT[d.status])} />
        <span className="text-xs capitalize opacity-80">{d.status}</span>
        <span className="ml-auto text-xs opacity-60">{formatDuration(d.duration)}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-slate-400 !w-2 !h-2" />
    </div>
  )
}

export default memo(PipelineNode)
