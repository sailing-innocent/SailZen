/**
 * @file evidence_expansion.tsx
 * @brief Evidence Expansion Component with Lazy Loading
 * @author sailing-innocent
 * @date 2026-03-08
 */

import { useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ChevronDown, ChevronUp, FileText, AlertCircle } from 'lucide-react'
import { useNodeEvidence } from '@hooks/useOutlinePagination'
import type { NodeEvidence } from '@lib/data/analysis'

export interface EvidenceExpansionProps {
  /** Node ID for lazy loading */
  nodeId: string
  /** Preview text to show initially */
  previewText?: string
  /** Whether full evidence is available */
  hasFullEvidence?: boolean
  /** Initial expanded state */
  defaultExpanded?: boolean
  /** Callback when expansion state changes */
  onExpandedChange?: (expanded: boolean) => void
  /** Sibling node IDs for preloading */
  siblingNodeIds?: string[]
  /** Callback to preload evidence for specific nodes */
  onPreloadEvidence?: (nodeIds: string[]) => void
}

/**
 * Evidence expansion component with lazy loading and preloading support
 * 
 * Shows a preview of evidence with the ability to expand
 * and load full evidence text on demand. Supports preloading
 * sibling nodes for better UX.
 */
export function EvidenceExpansion({
  nodeId,
  previewText,
  hasFullEvidence = true,
  defaultExpanded = false,
  onExpandedChange,
  siblingNodeIds,
  onPreloadEvidence,
}: EvidenceExpansionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const { evidence, isLoading, error, loadEvidence, preloadEvidence } = useNodeEvidence({
    nodeId,
    preload: defaultExpanded,
    preloadSiblings: siblingNodeIds,
  })

  const handleToggle = useCallback(async () => {
    const newExpanded = !isExpanded
    setIsExpanded(newExpanded)
    onExpandedChange?.(newExpanded)

    if (newExpanded && evidence.length === 0 && !isLoading) {
      await loadEvidence()
      // Preload siblings when expanding
      if (siblingNodeIds && siblingNodeIds.length > 0) {
        preloadEvidence(siblingNodeIds.filter(id => id !== nodeId))
        onPreloadEvidence?.(siblingNodeIds.filter(id => id !== nodeId))
      }
    }
  }, [isExpanded, evidence.length, isLoading, loadEvidence, siblingNodeIds, nodeId, onExpandedChange, onPreloadEvidence, preloadEvidence])

  const renderEvidenceContent = () => {
    if (isLoading) {
      return (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-[90%]" />
          <Skeleton className="h-4 w-[80%]" />
        </div>
      )
    }

    if (error) {
      return (
        <div className="flex items-center gap-2 text-red-600 text-sm">
          <AlertCircle className="w-4 h-4" />
          <span>加载失败: {error.message}</span>
          <Button variant="ghost" size="sm" onClick={loadEvidence}>
            重试
          </Button>
        </div>
      )
    }

    if (evidence.length === 0) {
      return (
        <p className="text-sm text-muted-foreground italic">
          暂无证据文本
        </p>
      )
    }

    return (
      <div className="space-y-4">
        {evidence.map((item, index) => (
          <EvidenceItem key={index} evidence={item} index={index} />
        ))}
      </div>
    )
  }

  return (
    <div className="w-full">
      {/* Preview Section */}
      {!isExpanded && previewText && (
        <div className="text-sm bg-muted/50 p-3 rounded-md border-l-2 border-primary">
          <div className="flex items-start gap-2">
            <FileText className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <p className="text-muted-foreground line-clamp-2">
              {previewText}
            </p>
          </div>
        </div>
      )}

      {/* Expansion Button */}
      {hasFullEvidence && (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleToggle}
          className="mt-2 h-auto py-1 px-2 text-xs"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="w-3 h-3 mr-1" />
              收起证据
            </>
          ) : (
            <>
              <ChevronDown className="w-3 h-3 mr-1" />
              显示完整证据
            </>
          )}
        </Button>
      )}

      {/* Expanded Content */}
      {isExpanded && (
        <Card className="mt-3 border-l-4 border-l-primary">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">完整证据</span>
              {evidence.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  ({evidence.length} 条)
                </span>
              )}
            </div>
            {renderEvidenceContent()}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

interface EvidenceItemProps {
  evidence: NodeEvidence
  index: number
}

function EvidenceItem({ evidence, index }: EvidenceItemProps) {
  return (
    <div className="border-l-2 border-muted pl-3 py-1">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-medium text-muted-foreground">
          证据 {index + 1}
        </span>
        {evidence.chapter_title && (
          <span className="text-xs text-muted-foreground">
            · {evidence.chapter_title}
          </span>
        )}
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap">
        {evidence.text}
      </p>
      {(evidence.start_fragment || evidence.end_fragment) && (
        <p className="text-xs text-muted-foreground mt-2">
          位置: {evidence.start_fragment || '...'} 
          {evidence.end_fragment ? ` → ${evidence.end_fragment}` : '...'}
        </p>
      )}
    </div>
  )
}

export default EvidenceExpansion
