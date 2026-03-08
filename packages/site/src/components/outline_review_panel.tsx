/**
 * @file outline_review_panel.tsx
 * @brief Outline Review Panel Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Progress } from '@/components/ui/progress'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  Check,
  X,
  Save,
  RefreshCw,
  AlertCircle,
  BookOpen,
  Target,
  Sparkles,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Clock,
} from 'lucide-react'
import type { ExtractedOutlineNode, OutlineExtractionResult, OutlineExtractionProgress } from '@lib/data/analysis'
import { getExtractedNodeEvidencePreview, hasExtractedNodeFullEvidence } from '@lib/data/analysis'

export interface OutlineReviewPanelProps {
  /** 提取结果 */
  result: OutlineExtractionResult | null
  /** 任务进度 */
  progress?: OutlineExtractionProgress | null
  /** 是否正在处理 */
  isProcessing?: boolean
  /** 选中的节点ID列表 */
  selectedNodeIds?: string[]
  /** 节点选择变更回调 */
  onSelectionChange?: (nodeIds: string[]) => void
  /** 批准所有选中节点回调 */
  onApprove?: (nodeIds: string[]) => void
  /** 拒绝节点回调 */
  onReject?: (nodeIds: string[]) => void
  /** 修改节点回调 */
  onModify?: (nodeId: string, data: Partial<ExtractedOutlineNode>) => void
  /** 保存到数据库回调 */
  onSave?: () => void
  /** 重新提取回调 */
  onRetry?: () => void
}

const NODE_TYPE_ICONS: Record<string, React.ReactNode> = {
  act: <BookOpen className="w-4 h-4" />,
  arc: <Target className="w-4 h-4" />,
  scene: <Sparkles className="w-4 h-4" />,
  beat: <ChevronRight className="w-4 h-4" />,
  turning_point: <AlertCircle className="w-4 h-4" />,
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
 * 大纲提取结果审核面板
 * 
 * 用于审核 AI 提取的大纲结果：
 * - 显示提取进度
 * - 展示提取的节点列表
 * - 批量选择/批准/拒绝
 * - 查看节点详情和证据
 * - 保存到数据库
 */
export function OutlineReviewPanel({
  result,
  progress,
  isProcessing = false,
  selectedNodeIds = [],
  onSelectionChange,
  onApprove,
  onReject,
  onModify,
  onSave,
  onRetry,
}: OutlineReviewPanelProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null)

  const nodes = result?.nodes || []
  const totalNodes = nodes.length
  const selectedCount = selectedNodeIds.length

  // 构建节点树结构
  const buildNodeTree = (nodes: ExtractedOutlineNode[]): ExtractedOutlineNode[] => {
    const nodeMap = new Map<string, ExtractedOutlineNode & { children?: ExtractedOutlineNode[] }>()
    const rootNodes: ExtractedOutlineNode[] = []

    // 首先创建所有节点的映射
    nodes.forEach((node) => {
      nodeMap.set(node.id, { ...node, children: [] })
    })

    // 然后构建父子关系
    nodes.forEach((node) => {
      const nodeWithChildren = nodeMap.get(node.id)!
      if (node.parent_id && nodeMap.has(node.parent_id)) {
        const parent = nodeMap.get(node.parent_id)!
        if (!parent.children) parent.children = []
        parent.children.push(nodeWithChildren)
      } else {
        rootNodes.push(nodeWithChildren)
      }
    })

    return rootNodes
  }

  const treeNodes = buildNodeTree(nodes)

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onSelectionChange?.(nodes.map((n) => n.id))
    } else {
      onSelectionChange?.([])
    }
  }

  const handleSelectNode = (nodeId: string, checked: boolean) => {
    if (checked) {
      onSelectionChange?.([...selectedNodeIds, nodeId])
    } else {
      onSelectionChange?.(selectedNodeIds.filter((id) => id !== nodeId))
    }
  }

  const handleApproveSelected = () => {
    onApprove?.(selectedNodeIds)
  }

  const handleRejectSelected = () => {
    onReject?.(selectedNodeIds)
  }

  // 渲染进度状态
  const renderProgress = () => {
    if (!progress && isProcessing) {
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <RefreshCw className="w-4 h-4 animate-spin" />
            正在处理...
          </div>
          <Progress value={0} className="h-2" />
        </div>
      )
    }

    if (!progress) return null

    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            {progress.progress_percent < 100 ? (
              <RefreshCw className="w-4 h-4 animate-spin text-primary" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-green-500" />
            )}
            <span>{progress.message}</span>
          </div>
          <span className="text-muted-foreground">{progress.progress_percent}%</span>
        </div>
        <Progress value={progress.progress_percent} className="h-2" />
        {progress.total_chunks && progress.total_chunks > 1 && (
          <p className="text-xs text-muted-foreground">
            处理分块 {progress.chunk_index || 0 + 1} / {progress.total_chunks}
          </p>
        )}
      </div>
    )
  }

  // 递归渲染节点
  const renderNode = (node: ExtractedOutlineNode & { children?: ExtractedOutlineNode[] }, level: number = 0) => {
    const isSelected = selectedNodeIds.includes(node.id)
    const isExpanded = expandedNodes.has(node.id)
    const hasChildren = node.children && node.children.length > 0
    const reviewStatus = node.review_status || 'pending'

    // 根据审核状态设置样式
    const getReviewStatusStyle = () => {
      switch (reviewStatus) {
        case 'approved':
          return 'bg-green-50 border-green-200'
        case 'rejected':
          return 'bg-red-50 border-red-200 opacity-50'
        default:
          return ''
      }
    }

    return (
      <div key={node.id} className="border-l-2 border-muted ml-3">
        <div
          className={`
            flex items-start gap-2 py-2 px-3 rounded-md border
            ${isSelected ? 'bg-primary/5' : 'hover:bg-muted/50'}
            ${getReviewStatusStyle()}
          `}
          style={{ marginLeft: `${level * 16}px` }}
        >
          <Checkbox
            checked={isSelected}
            onCheckedChange={(checked) => handleSelectNode(node.id, checked as boolean)}
          />

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              {/* 展开/折叠按钮 */}
              {hasChildren && (
                <button
                  onClick={() => {
                    const newSet = new Set(expandedNodes)
                    if (newSet.has(node.id)) {
                      newSet.delete(node.id)
                    } else {
                      newSet.add(node.id)
                    }
                    setExpandedNodes(newSet)
                  }}
                  className="p-0.5 hover:bg-muted rounded"
                >
                  {isExpanded ? (
                    <ChevronRight className="w-4 h-4 rotate-90 transition-transform" />
                  ) : (
                    <ChevronRight className="w-4 h-4 transition-transform" />
                  )}
                </button>
              )}

              {/* 节点类型图标 */}
              <span className="text-muted-foreground">
                {NODE_TYPE_ICONS[node.node_type] || <Sparkles className="w-4 h-4" />}
              </span>

              {/* 标题 */}
              <span className="font-medium text-sm truncate">{node.title}</span>

              {/* 重要性徽章 */}
              <Badge
                variant="outline"
                className={`text-xs ${SIGNIFICANCE_COLORS[node.significance]}`}
              >
                {SIGNIFICANCE_LABELS[node.significance]}
              </Badge>

              {/* 审核状态徽章 */}
              {reviewStatus !== 'pending' && (
                <Badge
                  variant={reviewStatus === 'approved' ? 'default' : 'destructive'}
                  className="text-xs"
                >
                  {reviewStatus === 'approved' ? '已批准' : '已拒绝'}
                </Badge>
              )}
            </div>

            {/* 摘要 */}
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
              {node.summary}
            </p>

            {/* 证据预览 (支持新数据流) */}
            {(node.evidence || node.evidence_preview || node.evidence_list) && (
              <div className="mt-2 text-xs bg-muted p-2 rounded border-l-2 border-primary">
                <span className="font-medium">证据：</span>
                {node.evidence_preview || getExtractedNodeEvidencePreview(node, 100) || '...'}
                {hasExtractedNodeFullEvidence(node) && !node.evidence_preview?.endsWith('...') && '...'}
                
                {/* 完整证据提示 */}
                {(node.evidence_full_available || hasExtractedNodeFullEvidence(node)) && (
                  <span className="text-primary ml-1 cursor-pointer hover:underline">
                    (查看更多)
                  </span>
                )}
              </div>
            )}

            {/* 涉及人物 */}
            {node.characters && node.characters.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {node.characters.map((char) => (
                  <Badge key={char} variant="secondary" className="text-xs">
                    {char}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 子节点 */}
        {hasChildren && isExpanded && (
          <div className="mt-1">
            {node.children!.map((child) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">提取结果审核</CardTitle>
            <CardDescription>
              {isProcessing
                ? '正在提取大纲，请稍候...'
                : result
                ? `共提取 ${totalNodes} 个节点，已选择 ${selectedCount} 个`
                : '等待提取结果'}
            </CardDescription>
          </div>
          {result && !isProcessing && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCw className="w-4 h-4 mr-1" />
                重新提取
              </Button>
              <Button size="sm" onClick={onSave} disabled={selectedCount === 0}>
                <Save className="w-4 h-4 mr-1" />
                保存选中
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 进度显示 */}
        {(isProcessing || progress) && renderProgress()}

        {/* 结果列表 */}
        {result && !isProcessing && (
          <>
            <Separator />

            {/* 批量操作栏 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={selectedCount === totalNodes && totalNodes > 0}
                  onCheckedChange={handleSelectAll}
                />
                <span className="text-sm text-muted-foreground">
                  全选 ({selectedCount}/{totalNodes})
                </span>
              </div>
              {selectedCount > 0 && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleApproveSelected}
                  >
                    <Check className="w-4 h-4 mr-1" />
                    批准
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRejectSelected}
                  >
                    <X className="w-4 h-4 mr-1" />
                    拒绝
                  </Button>
                </div>
              )}
            </div>

            {/* 节点列表 */}
            <ScrollArea className="max-h-[50vh]">
              <div className="space-y-1">
                {treeNodes.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>未提取到任何节点</p>
                    <p className="text-sm">请尝试调整配置或选择其他文本范围</p>
                  </div>
                ) : (
                  treeNodes.map((node) => renderNode(node))
                )}
              </div>
            </ScrollArea>

            {/* 元数据 */}
            {result.metadata && (
              <>
                <Separator />
                <div className="text-xs text-muted-foreground space-y-1">
                  {result.metadata.analysis_confidence && (
                    <p>
                      分析置信度:{' '}
                      {Math.round((result.metadata.analysis_confidence as number) * 100)}%
                    </p>
                  )}
                  {result.metadata.chapter_coverage && (
                    <p>覆盖章节: {result.metadata.chapter_coverage as string}</p>
                  )}
                  {result.metadata.max_depth && (
                    <p>最大深度: {result.metadata.max_depth as number} 层</p>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default OutlineReviewPanel
