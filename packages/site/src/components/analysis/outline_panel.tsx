/**
 * @file outline_panel.tsx
 * @brief Outline Management Panel
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect } from 'react'
import { useAnalysisStore } from '@lib/store/analysisStore'
import { Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  api_get_outlines_by_edition,
  api_create_outline,
  api_delete_outline,
  api_get_outline_tree,
  api_add_outline_node,
  api_delete_outline_node,
  api_add_outline_event,
} from '@lib/api/analysis'
import type { Outline, OutlineTree, OutlineTreeNode, OutlineType, OutlineNodeType } from '@lib/data/analysis'

// Outline Extraction imports - Unified Agent Version
import OutlineExtractionPanel from './outline_extraction_panel'

interface OutlinePanelProps {
  editionId: number
  workTitle?: string
}

const OUTLINE_TYPE_LABELS: Record<OutlineType, string> = {
  main: '主线大纲',
  subplot: '支线大纲',
  character_arc: '人物弧线',
}

const NODE_TYPE_LABELS: Record<OutlineNodeType, string> = {
  act: '幕',
  arc: '弧',
  beat: '节拍',
  scene: '场景',
  turning_point: '转折点',
}

const SIGNIFICANCE_LABELS: Record<string, string> = {
  critical: '关键',
  major: '主要',
  normal: '普通',
  minor: '次要',
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  plot: '情节',
  conflict: '冲突',
  revelation: '揭示',
  resolution: '解决',
  climax: '高潮',
}

export default function OutlinePanel({ editionId, workTitle }: OutlinePanelProps) {
  const [outlines, setOutlines] = useState<Outline[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedOutline, setSelectedOutline] = useState<Outline | null>(null)
  const [outlineTree, setOutlineTree] = useState<OutlineTree | null>(null)

  // Create dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newOutline, setNewOutline] = useState({
    title: '',
    outline_type: 'main' as OutlineType,
    description: '',
  })

  // Extraction state - Unified Agent Integration
  const [showExtraction, setShowExtraction] = useState(false)

  const fetchOutlines = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api_get_outlines_by_edition(editionId)
      setOutlines(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOutlines()
  }, [editionId])

  const handleSelectOutline = async (outline: Outline) => {
    setSelectedOutline(outline)
    try {
      const tree = await api_get_outline_tree(outline.id)
      setOutlineTree(tree)
    } catch (err) {
      console.error('Failed to load tree:', err)
    }
  }

  const handleCreateOutline = async () => {
    if (!newOutline.title.trim()) return

    try {
      const created = await api_create_outline({
        edition_id: editionId,
        title: newOutline.title,
        outline_type: newOutline.outline_type,
        description: newOutline.description || undefined,
      })
      setOutlines([created, ...outlines])
      setCreateDialogOpen(false)
      setNewOutline({ title: '', outline_type: 'main', description: '' })
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建失败')
    }
  }

  const handleDeleteOutline = async (outline: Outline) => {
    if (!confirm(`确定要删除「${outline.title}」吗？`)) return

    try {
      await api_delete_outline(outline.id)
      setOutlines(outlines.filter(o => o.id !== outline.id))
      if (selectedOutline?.id === outline.id) {
        setSelectedOutline(null)
        setOutlineTree(null)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    }
  }

  // Access global store for refreshing stats
  const { loadStats } = useAnalysisStore()

  // Handle extraction complete
  const handleExtractionComplete = () => {
    fetchOutlines()
    loadStats(editionId)
    setShowExtraction(false)
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2].map(i => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    )
  }

  // Show outline tree editor
  if (selectedOutline && outlineTree) {
    return (
      <OutlineTreeEditor
        tree={outlineTree}
        onBack={() => {
          setSelectedOutline(null)
          setOutlineTree(null)
        }}
        onUpdate={() => handleSelectOutline(selectedOutline)}
      />
    )
  }

  // Show extraction interface - Unified Agent Version
  if (showExtraction) {
    return (
      <OutlineExtractionPanel
        editionId={editionId}
        workTitle={workTitle}
        onSave={handleExtractionComplete}
        onClose={() => setShowExtraction(false)}
      />
    )
  }



  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex justify-between">
        <h3 className="text-lg font-semibold">大纲列表</h3>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowExtraction(true)}>
            <Sparkles className="w-4 h-4 mr-2" />
            AI 提取
          </Button>

          {/* Create Dialog */}
          <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
            <DialogTrigger asChild>
              <Button>新建大纲</Button>
            </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建大纲</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>大纲标题</Label>
                <Input
                  value={newOutline.title}
                  onChange={(e) => setNewOutline({ ...newOutline, title: e.target.value })}
                  placeholder="输入大纲标题"
                />
              </div>
              <div className="space-y-2">
                <Label>大纲类型</Label>
                <Select
                  value={newOutline.outline_type}
                  onValueChange={(v) => setNewOutline({ ...newOutline, outline_type: v as OutlineType })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(OUTLINE_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>描述</Label>
                <Textarea
                  value={newOutline.description}
                  onChange={(e) => setNewOutline({ ...newOutline, description: e.target.value })}
                  placeholder="大纲描述（可选）"
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>取消</Button>
              <Button onClick={handleCreateOutline}>创建</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>
      )}

      {/* Outline List */}
      {outlines.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          暂无大纲，点击「新建大纲」开始创建
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {outlines.map((outline) => (
            <Card
              key={outline.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => handleSelectOutline(outline)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base">{outline.title}</CardTitle>
                  <Badge variant="outline">{OUTLINE_TYPE_LABELS[outline.outline_type]}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                {outline.description && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                    {outline.description}
                  </p>
                )}
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{outline.node_count} 节点</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-500 hover:text-red-700 h-6 px-2"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteOutline(outline)
                    }}
                  >
                    删除
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// Outline Tree Editor Component
interface OutlineTreeEditorProps {
  tree: OutlineTree
  onBack: () => void
  onUpdate: () => void
}

function OutlineTreeEditor({ tree, onBack, onUpdate }: OutlineTreeEditorProps) {
  const [addNodeOpen, setAddNodeOpen] = useState(false)
  const [parentNodeId, setParentNodeId] = useState<number | null>(null)
  const [newNode, setNewNode] = useState({
    node_type: 'act' as OutlineNodeType,
    title: '',
    summary: '',
    significance: 'normal',
  })

  const handleAddNode = async () => {
    if (!newNode.title.trim()) return
    try {
      await api_add_outline_node(tree.outline.id, {
        node_type: newNode.node_type,
        title: newNode.title,
        parent_id: parentNodeId || undefined,
        summary: newNode.summary || undefined,
        significance: newNode.significance,
      })
      setAddNodeOpen(false)
      setNewNode({ node_type: 'act', title: '', summary: '', significance: 'normal' })
      setParentNodeId(null)
      onUpdate()
    } catch (err) {
      console.error('Failed to add node:', err)
    }
  }

  const handleDeleteNode = async (nodeId: number) => {
    if (!confirm('确定要删除这个节点及其子节点吗？')) return
    try {
      await api_delete_outline_node(nodeId)
      onUpdate()
    } catch (err) {
      console.error('Failed to delete node:', err)
    }
  }

  const openAddNodeDialog = (parentId: number | null = null) => {
    setParentNodeId(parentId)
    setAddNodeOpen(true)
  }

  // Recursive node renderer
  const renderNode = (node: OutlineTreeNode, level: number = 0) => {
    const indent = level * 16

    return (
      <div key={node.id} style={{ marginLeft: indent }}>
        <div className="flex items-center justify-between py-2 px-3 rounded hover:bg-muted/50 group">
          <div className="flex items-center gap-2 flex-1">
            <Badge variant="outline" className="text-xs">
              {NODE_TYPE_LABELS[node.node_type as OutlineNodeType] || node.node_type}
            </Badge>
            <span className="font-medium">{node.title}</span>
            <Badge variant="secondary" className="text-xs">
              {SIGNIFICANCE_LABELS[node.significance] || node.significance}
            </Badge>
          </div>
          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2"
              onClick={() => openAddNodeDialog(node.id)}
            >
              + 子节点
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-red-500 hover:text-red-700"
              onClick={() => handleDeleteNode(node.id)}
            >
              删除
            </Button>
          </div>
        </div>

        {node.summary && (
          <p className="text-sm text-muted-foreground ml-3 mb-1" style={{ marginLeft: indent + 12 }}>
            {node.summary}
          </p>
        )}

        {/* Events */}
        {node.events.length > 0 && (
          <div className="ml-6 mb-2" style={{ marginLeft: indent + 24 }}>
            {node.events.map((event) => (
              <div key={event.id} className="flex items-center gap-2 text-sm py-1">
                <Badge variant="secondary" className="text-xs">
                  {EVENT_TYPE_LABELS[event.event_type] || event.event_type}
                </Badge>
                <span>{event.title}</span>
              </div>
            ))}
          </div>
        )}

        {/* Children */}
        {node.children.length > 0 && (
          <div className="border-l ml-4">
            {node.children.map((child) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>← 返回</Button>
          <h2 className="text-xl font-bold">{tree.outline.title}</h2>
          <Badge variant="outline">{OUTLINE_TYPE_LABELS[tree.outline.outline_type]}</Badge>
        </div>
        <Button onClick={() => openAddNodeDialog(null)}>添加根节点</Button>
      </div>

      {/* Description */}
      {tree.outline.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-muted-foreground">{tree.outline.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Tree View */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">大纲结构</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[500px]">
            {tree.nodes.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                暂无节点，点击「添加根节点」开始构建大纲
              </p>
            ) : (
              <div className="space-y-1">
                {tree.nodes.map((node) => renderNode(node))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Add Node Dialog */}
      <Dialog open={addNodeOpen} onOpenChange={setAddNodeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {parentNodeId ? '添加子节点' : '添加根节点'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>节点类型</Label>
              <Select
                value={newNode.node_type}
                onValueChange={(v) => setNewNode({ ...newNode, node_type: v as OutlineNodeType })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(NODE_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>标题</Label>
              <Input
                value={newNode.title}
                onChange={(e) => setNewNode({ ...newNode, title: e.target.value })}
                placeholder="节点标题"
              />
            </div>
            <div className="space-y-2">
              <Label>重要程度</Label>
              <Select
                value={newNode.significance}
                onValueChange={(v) => setNewNode({ ...newNode, significance: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SIGNIFICANCE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>摘要</Label>
              <Textarea
                value={newNode.summary}
                onChange={(e) => setNewNode({ ...newNode, summary: e.target.value })}
                placeholder="节点摘要（可选）"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddNodeOpen(false)}>取消</Button>
            <Button onClick={handleAddNode}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
