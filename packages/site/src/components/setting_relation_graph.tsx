/**
 * @file setting_relation_graph.tsx
 * @brief Setting Relation Graph Component
 * @author sailing-innocent
 * @date 2025-03-01
 */

import { useEffect, useRef, useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Badge } from '@components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@components/ui/select'
import { ZoomIn, ZoomOut, Maximize, RotateCcw, Network } from 'lucide-react'

interface GraphNode {
  id: string
  name: string
  type: string
  importance: string
  category?: string
  x?: number
  y?: number
}

interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  description?: string
}

interface SettingRelationGraphProps {
  nodes: GraphNode[]
  edges: GraphEdge[]
  isLoading?: boolean
  onNodeClick?: (node: GraphNode) => void
}

const typeColors: Record<string, string> = {
  item: '#3b82f6',
  location: '#22c55e',
  organization: '#a855f7',
  concept: '#eab308',
  magic_system: '#f97316',
  creature: '#ec4899',
  event_type: '#06b6d4',
}

const importanceSizes: Record<string, number> = {
  critical: 24,
  major: 18,
  minor: 14,
  background: 10,
}

export function SettingRelationGraph({
  nodes,
  edges,
  isLoading = false,
  onNodeClick,
}: SettingRelationGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')

  // 计算节点位置（简单的力导向布局）
  const positionedNodes = useMemo(() => {
    const nodeMap = new Map<string, GraphNode>()
    
    // 初始化位置
    nodes.forEach((node, index) => {
      const angle = (index / nodes.length) * Math.PI * 2
      const radius = 150
      nodeMap.set(node.id, {
        ...node,
        x: 300 + Math.cos(angle) * radius,
        y: 250 + Math.sin(angle) * radius,
      })
    })

    // 简单的力导向迭代
    for (let i = 0; i < 50; i++) {
      // 斥力
      nodes.forEach((node1) => {
        nodes.forEach((node2) => {
          if (node1.id === node2.id) return
          const n1 = nodeMap.get(node1.id)!
          const n2 = nodeMap.get(node2.id)!
          const dx = n2.x! - n1.x!
          const dy = n2.y! - n1.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 1000 / (dist * dist)
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          n1.x! -= fx
          n1.y! -= fy
          n2.x! += fx
          n2.y! += fy
        })
      })

      // 引力（边）
      edges.forEach((edge) => {
        const source = nodeMap.get(edge.source)
        const target = nodeMap.get(edge.target)
        if (source && target) {
          const dx = target.x! - source.x!
          const dy = target.y! - source.y!
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = (dist - 100) * 0.01
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          source.x! += fx
          source.y! += fy
          target.x! -= fx
          target.y! -= fy
        }
      })
    }

    return Array.from(nodeMap.values())
  }, [nodes, edges])

  // 过滤节点
  const visibleNodes = useMemo(() => {
    if (filterType === 'all') return positionedNodes
    return positionedNodes.filter((n) => n.type === filterType)
  }, [positionedNodes, filterType])

  const visibleNodeIds = useMemo(() => 
    new Set(visibleNodes.map((n) => n.id)),
    [visibleNodes]
  )

  const visibleEdges = useMemo(() => 
    edges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target)),
    [edges, visibleNodeIds]
  )

  // 绘制画布
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // 设置画布大小
    canvas.width = canvas.offsetWidth * 2
    canvas.height = canvas.offsetHeight * 2
    ctx.scale(2, 2)

    // 清空画布
    ctx.clearRect(0, 0, canvas.offsetWidth, canvas.offsetHeight)

    // 保存上下文
    ctx.save()

    // 应用变换
    ctx.translate(offset.x, offset.y)
    ctx.scale(scale, scale)

    // 绘制边
    visibleEdges.forEach((edge) => {
      const source = positionedNodes.find((n) => n.id === edge.source)
      const target = positionedNodes.find((n) => n.id === edge.target)
      if (!source || !target || !source.x || !source.y || !target.x || !target.y) return

      ctx.beginPath()
      ctx.moveTo(source.x, source.y)
      ctx.lineTo(target.x, target.y)
      ctx.strokeStyle = '#94a3b8'
      ctx.lineWidth = 1
      ctx.stroke()

      // 绘制箭头
      const angle = Math.atan2(target.y - source.y, target.x - source.x)
      const arrowLength = 10
      const arrowAngle = Math.PI / 6
      const targetRadius = importanceSizes[target.importance] || 14

      ctx.beginPath()
      ctx.moveTo(
        target.x - targetRadius * Math.cos(angle),
        target.y - targetRadius * Math.sin(angle)
      )
      ctx.lineTo(
        target.x - targetRadius * Math.cos(angle) - arrowLength * Math.cos(angle - arrowAngle),
        target.y - targetRadius * Math.sin(angle) - arrowLength * Math.sin(angle - arrowAngle)
      )
      ctx.moveTo(
        target.x - targetRadius * Math.cos(angle),
        target.y - targetRadius * Math.sin(angle)
      )
      ctx.lineTo(
        target.x - targetRadius * Math.cos(angle) - arrowLength * Math.cos(angle + arrowAngle),
        target.y - targetRadius * Math.sin(angle) - arrowLength * Math.sin(angle + arrowAngle)
      )
      ctx.stroke()
    })

    // 绘制节点
    visibleNodes.forEach((node) => {
      if (!node.x || !node.y) return

      const size = importanceSizes[node.importance] || 14
      const isSelected = node.id === selectedNode

      // 绘制节点圆形
      ctx.beginPath()
      ctx.arc(node.x, node.y, size, 0, Math.PI * 2)
      ctx.fillStyle = typeColors[node.type] || '#64748b'
      ctx.fill()

      // 选中效果
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, size + 4, 0, Math.PI * 2)
        ctx.strokeStyle = '#f59e0b'
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // 绘制节点名称
      ctx.fillStyle = '#1e293b'
      ctx.font = '12px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.name, node.x, node.y + size + 15)
    })

    // 恢复上下文
    ctx.restore()
  }, [positionedNodes, visibleEdges, visibleNodes, scale, offset, selectedNode])

  // 处理鼠标事件
  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return

    const x = (e.clientX - rect.left - offset.x) / scale
    const y = (e.clientY - rect.top - offset.y) / scale

    // 检查是否点击了节点
    const clickedNode = positionedNodes.find((node) => {
      if (!node.x || !node.y) return false
      const size = importanceSizes[node.importance] || 14
      const dx = node.x - x
      const dy = node.y - y
      return Math.sqrt(dx * dx + dy * dy) <= size
    })

    if (clickedNode) {
      setSelectedNode(clickedNode.id)
      onNodeClick?.(clickedNode)
    } else {
      setIsDragging(true)
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y })
    }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return
    setOffset({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    })
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleZoomIn = () => setScale((s) => Math.min(s * 1.2, 3))
  const handleZoomOut = () => setScale((s) => Math.max(s / 1.2, 0.3))
  const handleReset = () => {
    setScale(1)
    setOffset({ x: 0, y: 0 })
  }

  if (isLoading) {
    return (
      <Card className="w-full h-full">
        <CardContent className="flex items-center justify-center h-96">
          <div className="w-8 h-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Network className="w-5 h-5" />
            设定关系图
            <Badge variant="secondary">{nodes.length} 节点 / {edges.length} 关系</Badge>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder="过滤类型" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类型</SelectItem>
                <SelectItem value="item">物品</SelectItem>
                <SelectItem value="location">地点</SelectItem>
                <SelectItem value="organization">组织</SelectItem>
                <SelectItem value="concept">概念</SelectItem>
                <SelectItem value="magic_system">能力体系</SelectItem>
                <SelectItem value="creature">生物</SelectItem>
                <SelectItem value="event_type">事件类型</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <canvas
            ref={canvasRef}
            className="w-full h-96 border rounded-lg cursor-move"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          />
          
          {/* 控制按钮 */}
          <div className="absolute bottom-4 right-4 flex gap-2">
            <Button variant="secondary" size="icon" onClick={handleZoomIn}>
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="icon" onClick={handleZoomOut}>
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button variant="secondary" size="icon" onClick={handleReset}>
              <RotateCcw className="w-4 h-4" />
            </Button>
          </div>

          {/* 图例 */}
          <div className="absolute top-4 left-4 bg-background/90 p-3 rounded-lg border text-xs space-y-2">
            <p className="font-medium">图例</p>
            {Object.entries(typeColors).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                <span>
                  {type === 'item' && '物品'}
                  {type === 'location' && '地点'}
                  {type === 'organization' && '组织'}
                  {type === 'concept' && '概念'}
                  {type === 'magic_system' && '能力体系'}
                  {type === 'creature' && '生物'}
                  {type === 'event_type' && '事件类型'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
