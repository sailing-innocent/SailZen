import { useMemo, useState, useCallback, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  applyNodeChanges,
  type Node,
  type Edge,
  type NodeChange,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { PipelineRun } from '@lib/data/dag_pipeline'
import { layoutNodes, STATUS_COLOR } from './dag_utils'
import PipelineNode, { type PipelineNodeData } from './PipelineNode'
import { useDAGPipelineStore } from '@lib/store/dag_pipeline'

const nodeTypes = { pipelineNode: PipelineNode }

interface Props {
  run: PipelineRun
}

export default function DAGCanvas({ run }: Props) {
  const { selectedNodeId, selectNode } = useDAGPipelineStore()

  const nodeIdKey = run.node_runs.map((n) => n.node_id).join(',')

  const positions = useMemo(
    () => layoutNodes(run.node_runs.map((n) => ({ node_id: n.node_id, depends_on: n.depends_on }))),
    [nodeIdKey]
  )

  const canonicalNodes: Node[] = useMemo(() => {
    return run.node_runs.map((nr) => {
      const pos = positions[nr.node_id] ?? { x: 0, y: 0 }
      const nodeData: PipelineNodeData = {
        nodeId: nr.node_id,
        label: nr.node_name,
        nodeType: nr.node_type,
        status: nr.status,
        duration: nr.duration,
        isDynamic: nr.is_dynamic,
        canSpawn: nr.can_spawn,
        selected: selectedNodeId === nr.node_id,
        onClick: () => selectNode(selectedNodeId === nr.node_id ? null : nr.node_id),
      }
      return {
        id: nr.node_id,
        type: 'pipelineNode',
        position: pos,
        data: nodeData as unknown as Record<string, unknown>,
      }
    })
  }, [run.node_runs, selectedNodeId, positions])

  const [nodes, setNodes] = useState<Node[]>(canonicalNodes)
  const [currentRunId, setCurrentRunId] = useState(run.id)

  useEffect(() => {
    if (run.id !== currentRunId) {
      setCurrentRunId(run.id)
      setNodes(canonicalNodes)
      return
    }
    setNodes((prev) => {
      const prevMap = new Map(prev.map((n) => [n.id, n]))
      return canonicalNodes.map((canonical) => {
        const existing = prevMap.get(canonical.id)
        if (existing) {
          return { ...existing, data: canonical.data }
        }
        return canonical
      })
    })
  }, [run.id, canonicalNodes, currentRunId])

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setNodes((nds) => applyNodeChanges(changes, nds))
  }, [])

  const edges: Edge[] = useMemo(() => {
    const result: Edge[] = []
    for (const nr of run.node_runs) {
      for (const dep of nr.depends_on) {
        if (!run.node_runs.find((n) => n.node_id === dep)) continue
        result.push({
          id: `${dep}->${nr.node_id}`,
          source: dep,
          target: nr.node_id,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: nr.is_dynamic ? '#a855f7' : '#64748b',
          },
          style: {
            stroke: nr.is_dynamic ? '#a855f7' : '#475569',
            strokeWidth: nr.is_dynamic ? 2 : 1.5,
            strokeDasharray: nr.is_dynamic ? '6 3' : undefined,
          },
          animated: nr.status === 'running',
        })
      }
    }
    return result
  }, [run.node_runs])

  return (
    <div style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} className="bg-slate-950">
      <ReactFlow
        style={{ width: '100%', height: '100%' }}
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        colorMode="dark"
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={20} />
        <Controls className="!bg-slate-800 !border-slate-600 !text-slate-200" />
        <MiniMap
          nodeColor={(n) => {
            const status = (n.data as unknown as PipelineNodeData).status
            const cls = STATUS_COLOR[status] ?? ''
            if (cls.includes('emerald')) return '#10b981'
            if (cls.includes('red')) return '#ef4444'
            if (cls.includes('blue')) return '#3b82f6'
            if (cls.includes('amber')) return '#f59e0b'
            return '#475569'
          }}
          className="!bg-slate-900 !border-slate-700"
        />
      </ReactFlow>
    </div>
  )
}
