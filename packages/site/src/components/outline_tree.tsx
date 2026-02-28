/**
 * @file outline_tree.tsx
 * @brief Outline Tree Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from '@/components/ui/context-menu'
import {
  ChevronRight,
  ChevronDown,
  Plus,
  Trash2,
  Edit2,
  GripVertical,
  BookOpen,
  Target,
  Sparkles,
  Save,
  X,
} from 'lucide-react'
import type { OutlineTreeNode, OutlineNodeType } from '@lib/data/analysis'

export interface OutlineTreeProps {
  /** 大纲节点列表 */
  nodes: OutlineTreeNode[]
  /** 选中的节点ID */
  selectedNodeId?: string | null
  /** 节点点击回调 */
  onNodeClick?: (node: OutlineTreeNode) => void
  /** 节点展开/折叠回调 */
  onNodeToggle?: (nodeId: string, expanded: boolean) => void
  /** 添加子节点回调 */
  onAddChild?: (parentId: string) => void
  /** 删除节点回调 */
  onDeleteNode?: (nodeId: string) => void
  /** 更新节点回调 */
  onUpdateNode?: (nodeId: string, data: Partial<OutlineTreeNode>) => void
  /** 移动节点回调 */
  onMoveNode?: (nodeId: string, newParentId: string | null, newIndex: number) => void
  /** 是否可编辑 */
  editable?: boolean
  /** 是否显示添加根节点按钮 */
  showAddRoot?: boolean
  /** 添加根节点回调 */
  onAddRoot?: () => void
}

const NODE_TYPE_ICONS: Record<OutlineNodeType, React.ReactNode> = {
  act: <BookOpen className="w-4 h-4" />,
  arc: <Target className="w-4 h-4" />,
  scene: <Sparkles className="w-4 h-4" />,
  beat: <ChevronRight className="w-4 h-4" />,
  event: <Sparkles className="w-4 h-4" />,
}

const NODE_TYPE_LABELS: Record<OutlineNodeType, string> = {
  act: '幕',
  arc: '弧',
  scene: '场景',
  beat: '节拍',
  event: '事件',
}

const SIGNIFICANCE_COLORS = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  major: 'bg-orange-100 text-orange-800 border-orange-200',
  normal: 'bg-blue-100 text-blue-800 border-blue-200',
  minor: 'bg-gray-100 text-gray-800 border-gray-200',
}

const SIGNIFICANCE_LABELS = {
  critical: '关键',
  major: '主要',
  normal: '普通',
  minor: '次要',
}

/**
 * 大纲树节点组件（递归）
 */
interface TreeNodeItemProps {
  node: OutlineTreeNode
  level: number
  selectedNodeId?: string | null
  expandedNodes: Set<string>
  editingNodeId: string | null
  editForm: Partial<OutlineTreeNode>
  onNodeClick: (node: OutlineTreeNode) => void
  onNodeToggle: (nodeId: string) => void
  onAddChild: (parentId: string) => void
  onDeleteNode: (nodeId: string) => void
  onStartEdit: (node: OutlineTreeNode) => void
  onSaveEdit: () => void
  onCancelEdit: () => void
  onEditFormChange: (data: Partial<OutlineTreeNode>) => void
  editable: boolean
}

function TreeNodeItem({
  node,
  level,
  selectedNodeId,
  expandedNodes,
  editingNodeId,
  editForm,
  onNodeClick,
  onNodeToggle,
  onAddChild,
  onDeleteNode,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onEditFormChange,
  editable,
}: TreeNodeItemProps) {
  const isExpanded = expandedNodes.has(node.id)
  const isSelected = selectedNodeId === node.id
  const isEditing = editingNodeId === node.id
  const hasChildren = node.children && node.children.length > 0

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    onNodeToggle(node.id)
  }

  const handleClick = () => {
    onNodeClick(node)
  }

  if (isEditing) {
    return (
      <div className="py-2 px-3 bg-muted rounded-md space-y-2">
        <div className="flex gap-2">
          <Input
            value={editForm.title || ''}
            onChange={(e) => onEditFormChange({ title: e.target.value })}
            placeholder="节点标题"
            className="flex-1 h-8 text-sm"
          />
          <Select
            value={editForm.node_type || 'scene'}
            onValueChange={(v) => onEditFormChange({ node_type: v as OutlineNodeType })}
          >
            <SelectTrigger className="w-24 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(NODE_TYPE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value} className="text-xs">
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Textarea
          value={editForm.content || ''}
          onChange={(e) => onEditFormChange({ content: e.target.value })}
          placeholder="节点内容描述..."
          className="min-h-[60px] text-xs resize-none"
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onCancelEdit}>
            <X className="w-3 h-3 mr-1" />
            取消
          </Button>
          <Button size="sm" className="h-7 text-xs" onClick={onSaveEdit}>
            <Save className="w-3 h-3 mr-1" />
            保存
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <ContextMenu>
        <ContextMenuTrigger>
          <div
            className={`
              flex items-center gap-1 py-1.5 px-2 rounded-md cursor-pointer
              transition-colors duration-200
              ${isSelected ? 'bg-primary/10 ring-1 ring-primary' : 'hover:bg-muted'}
            `}
            style={{ paddingLeft: `${level * 16 + 8}px` }}
            onClick={handleClick}
          >
            {/* 展开/折叠按钮 */}
            {hasChildren ? (
              <button
                onClick={handleToggle}
                className="p-0.5 hover:bg-muted-foreground/20 rounded"
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                )}
              </button>
            ) : (
              <span className="w-5" />
            )}

            {/* 节点类型图标 */}
            <span className="text-muted-foreground">
              {NODE_TYPE_ICONS[node.node_type]}
            </span>

            {/* 节点标题 */}
            <span className="flex-1 text-sm truncate">{node.title}</span>

            {/* 重要性徽章 */}
            <Badge
              variant="outline"
              className={`text-xs ${SIGNIFICANCE_COLORS[node.significance || 'normal']}`}
            >
              {SIGNIFICANCE_LABELS[node.significance || 'normal']}
            </Badge>

            {/* 编辑按钮 */}
            {editable && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation()
                  onStartEdit(node)
                }}
              >
                <Edit2 className="w-3 h-3" />
              </Button>
            )}
          </div>
        </ContextMenuTrigger>

        {editable && (
          <ContextMenuContent>
            <ContextMenuItem onClick={() => onAddChild(node.id)}>
              <Plus className="w-4 h-4 mr-2" />
              添加子节点
            </ContextMenuItem>
            <ContextMenuItem onClick={() => onStartEdit(node)}>
              <Edit2 className="w-4 h-4 mr-2" />
              编辑节点
            </ContextMenuItem>
            <ContextMenuSeparator />
            <ContextMenuItem
              className="text-destructive"
              onClick={() => onDeleteNode(node.id)}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              删除节点
            </ContextMenuItem>
          </ContextMenuContent>
        )}
      </ContextMenu>

      {/* 子节点 */}
      {hasChildren && isExpanded && (
        <div className="mt-0.5">
          {node.children!.map((child) => (
            <TreeNodeItem
              key={child.id}
              node={child}
              level={level + 1}
              selectedNodeId={selectedNodeId}
              expandedNodes={expandedNodes}
              editingNodeId={editingNodeId}
              editForm={editForm}
              onNodeClick={onNodeClick}
              onNodeToggle={onNodeToggle}
              onAddChild={onAddChild}
              onDeleteNode={onDeleteNode}
              onStartEdit={onStartEdit}
              onSaveEdit={onSaveEdit}
              onCancelEdit={onCancelEdit}
              onEditFormChange={onEditFormChange}
              editable={editable}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * 大纲树组件
 * 
 * 显示层级化的大纲结构，支持：
 * - 展开/折叠节点
 * - 选择节点
 * - 添加/删除/编辑节点
 * - 右键菜单操作
 */
export function OutlineTree({
  nodes,
  selectedNodeId,
  onNodeClick,
  onNodeToggle,
  onAddChild,
  onDeleteNode,
  onUpdateNode,
  onMoveNode,
  editable = true,
  showAddRoot = true,
  onAddRoot,
}: OutlineTreeProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<OutlineTreeNode>>({})

  const handleNodeToggle = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId)
      } else {
        newSet.add(nodeId)
      }
      return newSet
    })
    onNodeToggle?.(nodeId, !expandedNodes.has(nodeId))
  }, [expandedNodes, onNodeToggle])

  const handleStartEdit = useCallback((node: OutlineTreeNode) => {
    setEditingNodeId(node.id)
    setEditForm({
      title: node.title,
      content: node.content,
      node_type: node.node_type,
    })
  }, [])

  const handleSaveEdit = useCallback(() => {
    if (editingNodeId) {
      onUpdateNode?.(editingNodeId, editForm)
      setEditingNodeId(null)
      setEditForm({})
    }
  }, [editingNodeId, editForm, onUpdateNode])

  const handleCancelEdit = useCallback(() => {
    setEditingNodeId(null)
    setEditForm({})
  }, [])

  return (
    <Card className="w-full">
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">大纲结构</CardTitle>
          {editable && showAddRoot && (
            <Button variant="outline" size="sm" onClick={onAddRoot}>
              <Plus className="w-4 h-4 mr-1" />
              添加根节点
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        <div className="max-h-[60vh] overflow-y-auto py-2">
          {nodes.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              暂无大纲节点
            </div>
          ) : (
            <div className="space-y-0.5">
              {nodes.map((node) => (
                <TreeNodeItem
                  key={node.id}
                  node={node}
                  level={0}
                  selectedNodeId={selectedNodeId}
                  expandedNodes={expandedNodes}
                  editingNodeId={editingNodeId}
                  editForm={editForm}
                  onNodeClick={onNodeClick || (() => {})}
                  onNodeToggle={handleNodeToggle}
                  onAddChild={onAddChild || (() => {})}
                  onDeleteNode={onDeleteNode || (() => {})}
                  onStartEdit={handleStartEdit}
                  onSaveEdit={handleSaveEdit}
                  onCancelEdit={handleCancelEdit}
                  onEditFormChange={setEditForm}
                  editable={editable}
                />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default OutlineTree
