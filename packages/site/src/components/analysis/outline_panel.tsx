/**
 * @file outline_panel.tsx
 * @brief Outline Management Panel
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect, useCallback } from 'react'
import { useAnalysisStore } from '@lib/store/analysisStore'
import { Sparkles, ChevronRight, ChevronDown, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
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
  api_get_outline_nodes_paginated,
  api_get_node_evidence,
} from '@lib/api/analysis'
import type { Outline, OutlineTree, OutlineTreeNode, OutlineType, OutlineNodeType, TextRangeSelection, OutlineNodeListItem, NodeEvidence } from '@lib/data/analysis'
import type { ChapterListItem } from '@lib/data/text'
import { VirtualizedOutlineTree } from './virtualized'

// Outline Extraction imports - Unified Agent Version
import OutlineExtractionPanel from './outline_extraction_panel'

interface OutlinePanelProps {
  editionId: number
  workTitle?: string
  chapters?: ChapterListItem[]
  rangeSelection?: TextRangeSelection
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

export default function OutlinePanel({ editionId, workTitle, chapters = [], rangeSelection }: OutlinePanelProps) {
  const [outlines, setOutlines] = useState<Outline[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedOutline, setSelectedOutline] = useState<Outline | null>(null)

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
  }

  const handleRefreshOutline = () => {
    fetchOutlines()
  }

  const handleCreateOutline = async () => {
    if (!newOutline.title.trim()) return

    try {
      const created = await api_create_outline(editionId, {
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
        // setOutlineTree(null)
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

  // Show outline tree editor with virtualization
  if (selectedOutline) {
    return (
      <OutlineTreeEditor
        outline={selectedOutline}
        onBack={() => {
          setSelectedOutline(null)
        }}
        onUpdate={handleRefreshOutline}
      />
    )
  }

  // Show extraction interface - Unified Agent Version
  if (showExtraction) {
    return (
      <OutlineExtractionPanel
        editionId={editionId}
        workTitle={workTitle}
        chapters={chapters}
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

// Outline Tree Editor Component with Virtualization
interface OutlineTreeEditorProps {
  outline: Outline
  onBack: () => void
  onUpdate: () => void
}

function OutlineTreeEditor({ outline, onBack, onUpdate }: OutlineTreeEditorProps) {
  const [addNodeOpen, setAddNodeOpen] = useState(false)
  const [parentNodeId, setParentNodeId] = useState<string | null>(null)
  const [newNode, setNewNode] = useState({
    node_type: 'act' as OutlineNodeType,
    title: '',
    summary: '',
    significance: 'normal',
  })

  // Pagination state
  const [nodes, setNodes] = useState<OutlineNodeListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [nextCursor, setNextCursor] = useState<string | undefined>(undefined)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>(undefined)
  const [totalCount, setTotalCount] = useState<number | undefined>(undefined)

  // Load initial nodes
  useEffect(() => {
    loadNodes()
  }, [outline.id])

  const loadNodes = async (cursor?: string) => {
    const isInitial = !cursor
    if (isInitial) {
      setIsLoading(true)
    } else {
      setIsLoadingMore(true)
    }

    try {
      const response = await api_get_outline_nodes_paginated(
        outline.id,
        50,
        cursor,
        undefined // parent_id - load root level
      )

      if (isInitial) {
        setNodes(response.nodes)
      } else {
        setNodes(prev => [...prev, ...response.nodes])
      }

      setHasMore(response.has_more)
      setNextCursor(response.next_cursor)
      setTotalCount(response.total_count)
    } catch (err) {
      console.error('Failed to load nodes:', err)
    } finally {
      setIsLoading(false)
      setIsLoadingMore(false)
    }
  }

  const handleLoadMore = useCallback(() => {
    if (!isLoadingMore && hasMore && nextCursor) {
      loadNodes(nextCursor)
    }
  }, [isLoadingMore, hasMore, nextCursor])

  const handleNodeExpand = useCallback((nodeId: string) => {
    setExpandedNodes(prev => new Set(prev).add(nodeId))
  }, [])

  const handleNodeCollapse = useCallback((nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev)
      next.delete(nodeId)
      return next
    })
  }, [])

  const handleLoadEvidence = useCallback(async (nodeId: string): Promise<NodeEvidence[]> => {
    const response = await api_get_node_evidence(nodeId)
    return response.evidence_list
  }, [])

  const handleAddNode = async () => {
    if (!newNode.title.trim()) return
    try {
      await api_add_outline_node(outline.id, {
        node_type: newNode.node_type,
        title: newNode.title,
        parent_id: parentNodeId || undefined,
        summary: newNode.summary || undefined,
        significance: newNode.significance,
      })
      setAddNodeOpen(false)
      setNewNode({ node_type: 'act', title: '', summary: '', significance: 'normal' })
      setParentNodeId(null)
      // Refresh nodes
      setNodes([])
      setNextCursor(undefined)
      loadNodes()
      onUpdate()
    } catch (err) {
      console.error('Failed to add node:', err)
    }
  }

  const handleDeleteNode = async (nodeId: string) => {
    if (!confirm('确定要删除这个节点及其子节点吗？')) return
    try {
      await api_delete_outline_node(nodeId)
      // Refresh nodes
      setNodes([])
      setNextCursor(undefined)
      loadNodes()
      onUpdate()
    } catch (err) {
      console.error('Failed to delete node:', err)
    }
  }

  const openAddNodeDialog = (parentId: string | null = null) => {
    setParentNodeId(parentId)
    setAddNodeOpen(true)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" onClick={onBack}>← 返回</Button>
          <h2 className="text-xl font-bold">{outline.title}</h2>
          <Badge variant="outline">{OUTLINE_TYPE_LABELS[outline.outline_type]}</Badge>
        </div>
        <div className="flex items-center gap-2">
          {totalCount !== undefined && (
            <span className="text-sm text-muted-foreground">
              {nodes.length} / {totalCount} 节点
            </span>
          )}
          <Button onClick={() => openAddNodeDialog(null)}>添加根节点</Button>
        </div>
      </div>

      {/* Description */}
      {outline.description && (
        <Card>
          <CardContent className="pt-4">
            <p className="text-muted-foreground">{outline.description}</p>
          </CardContent>
        </Card>
      )}

      {/* Tree View with Virtualization */}
      <Card className="h-[600px] flex flex-col">
        <CardHeader className="pb-2 shrink-0">
          <CardTitle className="text-base">大纲结构</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 min-h-0 p-0">
          <VirtualizedOutlineTree
            nodes={nodes}
            isLoading={isLoading}
            isLoadingMore={isLoadingMore}
            hasMore={hasMore}
            onLoadMore={handleLoadMore}
            onNodeExpand={handleNodeExpand}
            onNodeCollapse={handleNodeCollapse}
            expandedNodes={expandedNodes}
            selectedNodeId={selectedNodeId}
            onNodeSelect={setSelectedNodeId}
            loadEvidence={handleLoadEvidence}
          />
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
