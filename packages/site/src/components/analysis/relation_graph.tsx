/**
 * @file relation_graph.tsx
 * @brief Character Relation Graph Component using simple SVG
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import type { RelationGraphData, RelationGraphNode, RelationGraphEdge } from '@lib/data/analysis'

interface RelationGraphProps {
  data: RelationGraphData
  onNodeClick?: (nodeId: number) => void
}

const ROLE_COLORS: Record<string, string> = {
  protagonist: '#3b82f6', // blue
  antagonist: '#ef4444', // red
  deuteragonist: '#8b5cf6', // purple
  supporting: '#22c55e', // green
  minor: '#94a3b8', // gray
  mentioned: '#cbd5e1', // light gray
}

const RELATION_COLORS: Record<string, string> = {
  family: '#f59e0b', // amber
  romance: '#ec4899', // pink
  friendship: '#22c55e', // green
  rivalry: '#f97316', // orange
  mentor: '#6366f1', // indigo
  alliance: '#14b8a6', // teal
  enemy: '#ef4444', // red
}

export default function RelationGraph({ data, onNodeClick }: RelationGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 })
  const [nodePositions, setNodePositions] = useState<Map<number, { x: number; y: number }>>(new Map())
  const [hoveredNode, setHoveredNode] = useState<number | null>(null)

  // Calculate responsive dimensions
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { clientWidth } = containerRef.current
        setDimensions({
          width: Math.max(clientWidth - 32, 400),
          height: Math.min(Math.max(clientWidth * 0.6, 400), 600),
        })
      }
    }
    updateDimensions()
    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [])

  // Simple force-directed layout simulation
  useEffect(() => {
    if (data.nodes.length === 0) return

    const positions = new Map<number, { x: number; y: number }>()
    const centerX = dimensions.width / 2
    const centerY = dimensions.height / 2
    const radius = Math.min(dimensions.width, dimensions.height) * 0.35

    // Initial positions in a circle
    data.nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / data.nodes.length
      positions.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      })
    })

    // Simple force simulation (just a few iterations for basic layout)
    const repulsionStrength = 2000
    const attractionStrength = 0.05

    for (let iter = 0; iter < 50; iter++) {
      // Repulsion between nodes
      data.nodes.forEach((nodeA) => {
        data.nodes.forEach((nodeB) => {
          if (nodeA.id === nodeB.id) return
          const posA = positions.get(nodeA.id)!
          const posB = positions.get(nodeB.id)!
          const dx = posA.x - posB.x
          const dy = posA.y - posB.y
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1)
          const force = repulsionStrength / (dist * dist)
          posA.x += (dx / dist) * force * 0.01
          posA.y += (dy / dist) * force * 0.01
        })
      })

      // Attraction along edges
      data.edges.forEach((edge) => {
        const posSource = positions.get(edge.source)
        const posTarget = positions.get(edge.target)
        if (!posSource || !posTarget) return
        const dx = posTarget.x - posSource.x
        const dy = posTarget.y - posSource.y
        posSource.x += dx * attractionStrength
        posSource.y += dy * attractionStrength
        posTarget.x -= dx * attractionStrength
        posTarget.y -= dy * attractionStrength
      })

      // Center gravity
      data.nodes.forEach((node) => {
        const pos = positions.get(node.id)!
        pos.x += (centerX - pos.x) * 0.01
        pos.y += (centerY - pos.y) * 0.01
      })
    }

    // Clamp to bounds
    const padding = 60
    data.nodes.forEach((node) => {
      const pos = positions.get(node.id)!
      pos.x = Math.max(padding, Math.min(dimensions.width - padding, pos.x))
      pos.y = Math.max(padding, Math.min(dimensions.height - padding, pos.y))
    })

    setNodePositions(positions)
  }, [data, dimensions])

  if (data.nodes.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64 text-muted-foreground">
          暂无人物数据
        </CardContent>
      </Card>
    )
  }

  // Get connected edges for hovered node
  const getConnectedEdges = (nodeId: number) => {
    return data.edges.filter(e => e.source === nodeId || e.target === nodeId)
  }

  return (
    <Card ref={containerRef}>
      <CardContent className="p-4">
        <svg
          width={dimensions.width}
          height={dimensions.height}
          className="bg-muted/20 rounded-lg"
        >
          {/* Edges */}
          {data.edges.map((edge, index) => {
            const sourcePos = nodePositions.get(edge.source)
            const targetPos = nodePositions.get(edge.target)
            if (!sourcePos || !targetPos) return null

            const isHighlighted = hoveredNode === edge.source || hoveredNode === edge.target
            const color = RELATION_COLORS[edge.relation_type] || '#94a3b8'

            return (
              <g key={`edge-${index}`}>
                <line
                  x1={sourcePos.x}
                  y1={sourcePos.y}
                  x2={targetPos.x}
                  y2={targetPos.y}
                  stroke={color}
                  strokeWidth={isHighlighted ? 2 : 1}
                  strokeOpacity={hoveredNode && !isHighlighted ? 0.2 : 0.6}
                />
                {/* Edge label (only when highlighted) */}
                {isHighlighted && (
                  <text
                    x={(sourcePos.x + targetPos.x) / 2}
                    y={(sourcePos.y + targetPos.y) / 2 - 5}
                    textAnchor="middle"
                    className="text-xs fill-current"
                    style={{ fontSize: 10 }}
                  >
                    {edge.relation_type}
                  </text>
                )}
              </g>
            )
          })}

          {/* Nodes */}
          {data.nodes.map((node) => {
            const pos = nodePositions.get(node.id)
            if (!pos) return null

            const color = ROLE_COLORS[node.role_type] || '#94a3b8'
            const nodeRadius = 20 + (node.importance_score || 0.5) * 10
            const isHighlighted = hoveredNode === node.id
            const isConnected = hoveredNode ? getConnectedEdges(hoveredNode).some(e => e.source === node.id || e.target === node.id) : false

            return (
              <g
                key={node.id}
                transform={`translate(${pos.x}, ${pos.y})`}
                className="cursor-pointer"
                onClick={() => onNodeClick?.(node.id)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                opacity={hoveredNode && !isHighlighted && !isConnected ? 0.3 : 1}
              >
                {/* Node circle */}
                <circle
                  r={nodeRadius}
                  fill={color}
                  stroke={isHighlighted ? '#000' : '#fff'}
                  strokeWidth={isHighlighted ? 3 : 2}
                />
                {/* Node label */}
                <text
                  y={nodeRadius + 14}
                  textAnchor="middle"
                  className="fill-current"
                  style={{ fontSize: 12, fontWeight: 500 }}
                >
                  {node.name}
                </text>
              </g>
            )
          })}
        </svg>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <div className="font-medium">角色类型：</div>
          {Object.entries(ROLE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-muted-foreground">{type}</span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-sm">
          <div className="font-medium">关系类型：</div>
          {Object.entries(RELATION_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1">
              <div className="w-6 h-0.5" style={{ backgroundColor: color }} />
              <span className="text-muted-foreground">{type}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
