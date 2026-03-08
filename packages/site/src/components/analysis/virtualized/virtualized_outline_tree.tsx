/**
 * @file virtualized_outline_tree.tsx
 * @brief Virtualized Outline Tree Component
 * @author sailing-innocent
 * @date 2026-03-07
 */

import React, { useState, useCallback, useMemo, useRef } from 'react'
import { Virtuoso, type VirtuosoHandle } from 'react-virtuoso'
import type { OutlineNodeListItem, NodeEvidence } from '@lib/data/analysis'
import { ChevronRight, ChevronDown, Loader2, FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

interface VirtualizedOutlineTreeProps {
  nodes: OutlineNodeListItem[]
  isLoading: boolean
  isLoadingMore: boolean
  hasMore: boolean
  onLoadMore: () => void
  onNodeExpand: (nodeId: string) => void
  onNodeCollapse: (nodeId: string) => void
  expandedNodes: Set<string>
  selectedNodeId?: string
  onNodeSelect?: (nodeId: string) => void
  loadEvidence: (nodeId: string) => Promise<NodeEvidence[]>
}

interface TreeItemData {
  node: OutlineNodeListItem
  depth: number
  isExpanded: boolean
  hasChildren: boolean
}

// Flatten tree structure for virtualization
function flattenTree(
  nodes: OutlineNodeListItem[],
  expandedNodes: Set<string>,
  parentDepth: number = 0
): TreeItemData[] {
  const result: TreeItemData[] = []

  for (const node of nodes) {
    result.push({
      node,
      depth: parentDepth,
      isExpanded: expandedNodes.has(node.id),
      hasChildren: node.has_children,
    })

    // If expanded and has children, recursively add them
    if (expandedNodes.has(node.id) && node.has_children) {
      // Children would need to be loaded separately or included in nodes
      // For now, we assume children are managed separately
    }
  }

  return result
}

// Calculate indentation based on depth
function getIndentationStyle(depth: number): React.CSSProperties {
  return {
    paddingLeft: `${depth * 20 + 12}px`,
  }
}

interface TreeNodeItemProps {
  item: TreeItemData
  isSelected: boolean
  onToggle: () => void
  onSelect: () => void
  evidence?: NodeEvidence[]
  isLoadingEvidence: boolean
  onLoadEvidence: () => void
}

const TreeNodeItem = React.memo(function TreeNodeItem({
  item,
  isSelected,
  onToggle,
  onSelect,
  evidence,
  isLoadingEvidence,
  onLoadEvidence,
}: TreeNodeItemProps) {
  const { node, depth, isExpanded, hasChildren } = item
  const [showEvidence, setShowEvidence] = useState(false)

  const handleToggle = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onToggle()
    },
    [onToggle]
  )

  const handleSelect = useCallback(() => {
    onSelect()
  }, [onSelect])

  const handleShowEvidence = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation()
      if (!evidence && !isLoadingEvidence) {
        await onLoadEvidence()
      }
      setShowEvidence((prev) => !prev)
    },
    [evidence, isLoadingEvidence, onLoadEvidence]
  )

  return (
    <div
      className={cn(
        'group flex flex-col border-b border-border/50 transition-colors',
        isSelected && 'bg-accent',
        'hover:bg-accent/50'
      )}
      style={getIndentationStyle(depth)}
      role="treeitem"
      aria-expanded={hasChildren ? isExpanded : undefined}
      aria-selected={isSelected}
      aria-label={`${node.title}${node.significance && node.significance !== 'normal' ? ` (${node.significance})` : ''}`}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          if (hasChildren) {
            onToggle()
          } else {
            onSelect()
          }
        }
      }}
    >
      <div
        className="flex items-center gap-2 py-2 pr-4 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        onClick={handleSelect}
      >
        {/* Expand/Collapse button */}
        {hasChildren ? (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0"
            onClick={handleToggle}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? `收起 ${node.title}` : `展开 ${node.title}`}
            title={isExpanded ? '收起' : '展开'}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        ) : (
          <div className="w-6 shrink-0" />
        )}

        {/* Node title and summary */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium truncate">{node.title}</span>
            {node.significance && node.significance !== 'normal' && (
              <span
                className={cn(
                  'text-xs px-1.5 py-0.5 rounded',
                  node.significance === 'critical' && 'bg-red-100 text-red-700',
                  node.significance === 'major' && 'bg-orange-100 text-orange-700',
                  node.significance === 'minor' && 'bg-blue-100 text-blue-700'
                )}
              >
                {node.significance}
              </span>
            )}
          </div>
          {node.summary && (
            <p className="text-sm text-muted-foreground truncate">
              {node.summary}
            </p>
          )}
        </div>

        {/* Evidence indicator */}
        {node.evidence_full_available && (
          <Button
            variant="ghost"
            size="sm"
            className="shrink-0 h-7"
            onClick={handleShowEvidence}
            aria-expanded={showEvidence}
            aria-controls={`evidence-${node.id}`}
            aria-label={showEvidence ? `收起 ${node.title} 的证据` : `查看 ${node.title} 的完整证据`}
            title={showEvidence ? '收起证据' : '查看完整证据'}
          >
            <FileText className="h-3.5 w-3.5 mr-1" aria-hidden="true" />
            {isLoadingEvidence ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" aria-hidden="true" />
                <span className="sr-only">加载中</span>
              </>
            ) : (
              '证据'
            )}
          </Button>
        )}

        {/* Events count */}
        {node.events_count > 0 && (
          <span className="text-xs text-muted-foreground shrink-0">
            {node.events_count} 事件
          </span>
        )}
      </div>

      {/* Evidence display */}
      {showEvidence && evidence && (
        <div className="pl-8 pr-4 pb-2" role="region" aria-label={`${node.title} 的完整证据`}>
          <div className="bg-muted rounded-md p-3 text-sm border border-border/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-muted-foreground">
                完整证据 ({evidence.length} 条)
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-xs"
                onClick={handleShowEvidence}
                aria-label="收起证据"
              >
                收起
              </Button>
            </div>
            {evidence.length === 0 ? (
              <p className="text-muted-foreground">暂无证据</p>
            ) : (
              <div className="space-y-3">
                {evidence.map((ev, idx) => (
                  <div key={idx} className="border-b border-border/30 last:border-0 pb-2 last:pb-0">
                    {ev.chapter_title && (
                      <p className="text-xs text-muted-foreground mb-1 flex items-center gap-1">
                        <span className="font-medium">章节:</span> {ev.chapter_title}
                      </p>
                    )}
                    <p className="text-foreground leading-relaxed">{ev.text}</p>
                    {(ev.start_fragment || ev.end_fragment) && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {ev.start_fragment && <span>开始: {ev.start_fragment}</span>}
                        {ev.start_fragment && ev.end_fragment && <span className="mx-2">|</span>}
                        {ev.end_fragment && <span>结束: {ev.end_fragment}</span>}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Evidence preview */}
      {!showEvidence && node.evidence_preview && (
        <div className="pl-8 pr-4 pb-2">
          <div className="group/preview flex items-start gap-2">
            <p className="text-xs text-muted-foreground line-clamp-2 flex-1">
              <span className="font-medium">预览:</span> {node.evidence_preview}
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs opacity-0 group-hover/preview:opacity-100 transition-opacity shrink-0"
              onClick={handleShowEvidence}
              aria-label="显示完整证据"
            >
              显示全部
            </Button>
          </div>
        </div>
      )}
    </div>
  )
})

export function VirtualizedOutlineTree({
  nodes,
  isLoading,
  isLoadingMore,
  hasMore,
  onLoadMore,
  onNodeExpand,
  onNodeCollapse,
  expandedNodes,
  selectedNodeId,
  onNodeSelect,
  loadEvidence,
}: VirtualizedOutlineTreeProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null)
  const [evidenceCache, setEvidenceCache] = useState<Map<string, NodeEvidence[]>>(
    new Map()
  )
  const [loadingEvidenceNodes, setLoadingEvidenceNodes] = useState<Set<string>>(
    new Set()
  )

  // Flatten tree for virtualization
  const flatItems = useMemo(() => {
    return flattenTree(nodes, expandedNodes)
  }, [nodes, expandedNodes])

  // Handle evidence loading
  const handleLoadEvidence = useCallback(
    async (nodeId: string) => {
      if (evidenceCache.has(nodeId) || loadingEvidenceNodes.has(nodeId)) {
        return evidenceCache.get(nodeId) || []
      }

      setLoadingEvidenceNodes((prev) => new Set(prev).add(nodeId))

      try {
        const evidence = await loadEvidence(nodeId)
        setEvidenceCache((prev) => new Map(prev).set(nodeId, evidence))
        return evidence
      } finally {
        setLoadingEvidenceNodes((prev) => {
          const next = new Set(prev)
          next.delete(nodeId)
          return next
        })
      }
    },
    [evidenceCache, loadingEvidenceNodes, loadEvidence]
  )

  // Toggle node expansion
  const handleToggle = useCallback(
    (nodeId: string) => {
      if (expandedNodes.has(nodeId)) {
        onNodeCollapse(nodeId)
      } else {
        onNodeExpand(nodeId)
      }
    },
    [expandedNodes, onNodeExpand, onNodeCollapse]
  )

  // Render item
  const renderItem = useCallback(
    (index: number, item: TreeItemData) => {
      const nodeId = item.node.id
      const isSelected = selectedNodeId === nodeId

      return (
        <TreeNodeItem
          item={item}
          isSelected={isSelected}
          onToggle={() => handleToggle(nodeId)}
          onSelect={() => onNodeSelect?.(nodeId)}
          evidence={evidenceCache.get(nodeId)}
          isLoadingEvidence={loadingEvidenceNodes.has(nodeId)}
          onLoadEvidence={() => handleLoadEvidence(nodeId)}
        />
      )
    },
    [
      selectedNodeId,
      evidenceCache,
      loadingEvidenceNodes,
      handleToggle,
      onNodeSelect,
      handleLoadEvidence,
    ]
  )

  // Footer component for loading more
  const Footer = useCallback(() => {
    if (!hasMore && !isLoadingMore) return null

    return (
      <div className="py-4 text-center" role="status" aria-live="polite">
        {isLoadingMore ? (
          <div className="flex items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            <span>加载更多节点...</span>
          </div>
        ) : hasMore ? (
          <Button variant="ghost" size="sm" onClick={onLoadMore} aria-label="加载更多大纲节点">
            加载更多
          </Button>
        ) : (
          <span className="text-sm text-muted-foreground">已加载全部节点</span>
        )}
      </div>
    )
  }, [hasMore, isLoadingMore, onLoadMore])

  if (isLoading && nodes.length === 0) {
    return (
      <div 
        className="space-y-2 p-4" 
        role="status" 
        aria-label="加载大纲节点中"
        aria-busy="true"
      >
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" aria-hidden="true" />
        ))}
        <span className="sr-only">正在加载大纲节点...</span>
      </div>
    )
  }

  if (nodes.length === 0) {
    return (
      <div 
        className="flex flex-col items-center justify-center h-64 text-muted-foreground"
        role="status"
        aria-label="暂无大纲节点"
      >
        <p>暂无大纲节点</p>
      </div>
    )
  }

  return (
    <div 
      className="h-full" 
      role="tree" 
      aria-label="大纲树"
      aria-busy={isLoadingMore ? 'true' : 'false'}
    >
      <Virtuoso
        ref={virtuosoRef}
        data={flatItems}
        itemContent={renderItem}
        components={{
          Footer,
        }}
        overscan={200}
        increaseViewportBy={{ top: 100, bottom: 100 }}
      />
    </div>
  )
}

export default VirtualizedOutlineTree
