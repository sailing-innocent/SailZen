/**
 * @file evidence_highlighter.tsx
 * @brief Text Evidence Highlighter Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useMemo, useCallback } from 'react'
import type { TextEvidence } from '@lib/data/analysis'

export interface HighlightRange {
  /** 证据ID */
  evidenceId: string
  /** 起始偏移 */
  start: number
  /** 结束偏移 */
  end: number
  /** 证据类型 */
  evidenceType: string
  /** 高亮颜色类 */
  colorClass?: string
}

export interface EvidenceHighlighterProps {
  /** 原文内容 */
  content: string
  /** 证据列表 */
  evidences: TextEvidence[]
  /** 当前高亮的证据ID */
  activeEvidenceId?: string | null
  /** 点击高亮区域回调 */
  onHighlightClick?: (evidence: TextEvidence) => void
  /** 自定义高亮颜色映射 */
  colorMap?: Record<string, string>
  /** 是否显示高亮 */
  showHighlights?: boolean
  /** 内容样式类 */
  contentClassName?: string
  /** 高亮样式类 */
  highlightClassName?: string
}

const DEFAULT_COLOR_MAP: Record<string, string> = {
  character: 'bg-blue-200/60 hover:bg-blue-300/80 border-b-2 border-blue-400',
  setting: 'bg-green-200/60 hover:bg-green-300/80 border-b-2 border-green-400',
  outline: 'bg-purple-200/60 hover:bg-purple-300/80 border-b-2 border-purple-400',
  relation: 'bg-orange-200/60 hover:bg-orange-300/80 border-b-2 border-orange-400',
  custom: 'bg-gray-200/60 hover:bg-gray-300/80 border-b-2 border-gray-400',
}

const ACTIVE_HIGHLIGHT_CLASS = 'ring-2 ring-primary ring-offset-1'

/**
 * 将证据列表转换为高亮范围
 */
function convertEvidencesToRanges(
  evidences: TextEvidence[],
  colorMap: Record<string, string>
): HighlightRange[] {
  return evidences
    .filter((ev) => ev.start_offset >= 0 && ev.end_offset > ev.start_offset)
    .map((ev) => ({
      evidenceId: ev.id,
      start: ev.start_offset,
      end: ev.end_offset,
      evidenceType: ev.evidence_type,
      colorClass: colorMap[ev.evidence_type] || colorMap.custom,
    }))
    .sort((a, b) => a.start - b.start)
}

/**
 * 合并重叠的高亮范围
 */
function mergeOverlappingRanges(ranges: HighlightRange[]): HighlightRange[][] {
  if (ranges.length === 0) return []

  const groups: HighlightRange[][] = []
  let currentGroup: HighlightRange[] = [ranges[0]]
  let currentEnd = ranges[0].end

  for (let i = 1; i < ranges.length; i++) {
    const range = ranges[i]
    if (range.start < currentEnd) {
      // 有重叠，加入当前组
      currentGroup.push(range)
      currentEnd = Math.max(currentEnd, range.end)
    } else {
      // 无重叠，开始新组
      groups.push(currentGroup)
      currentGroup = [range]
      currentEnd = range.end
    }
  }
  groups.push(currentGroup)

  return groups
}

/**
 * 文本证据高亮组件
 * 
 * 在章节内容中高亮显示证据标注，支持：
 * - 多种证据类型的不同颜色高亮
 * - 点击高亮区域触发回调
 * - 活跃证据的特殊样式
 * - 处理重叠的高亮范围
 * 
 * @example
 * ```tsx
 * <EvidenceHighlighter
 *   content={chapterContent}
 *   evidences={chapterEvidences}
 *   activeEvidenceId={selectedEvidenceId}
 *   onHighlightClick={(evidence) => console.log('Clicked:', evidence)}
 * />
 * ```
 */
export function EvidenceHighlighter({
  content,
  evidences,
  activeEvidenceId,
  onHighlightClick,
  colorMap = DEFAULT_COLOR_MAP,
  showHighlights = true,
  contentClassName = 'whitespace-pre-wrap leading-relaxed',
  highlightClassName = 'cursor-pointer transition-colors duration-200 rounded px-0.5',
}: EvidenceHighlighterProps) {
  // 转换证据为高亮范围
  const highlightRanges = useMemo(
    () => convertEvidencesToRanges(evidences, colorMap),
    [evidences, colorMap]
  )

  // 合并重叠范围
  const mergedGroups = useMemo(
    () => mergeOverlappingRanges(highlightRanges),
    [highlightRanges]
  )

  // 构建证据ID到证据对象的映射
  const evidenceMap = useMemo(() => {
    const map = new Map<string, TextEvidence>()
    evidences.forEach((ev) => map.set(ev.id, ev))
    return map
  }, [evidences])

  // 处理高亮点击
  const handleHighlightClick = useCallback(
    (evidenceId: string) => {
      const evidence = evidenceMap.get(evidenceId)
      if (evidence && onHighlightClick) {
        onHighlightClick(evidence)
      }
    },
    [evidenceMap, onHighlightClick]
  )

  // 如果没有高亮或不需要显示，直接返回纯文本
  if (!showHighlights || highlightRanges.length === 0) {
    return <div className={contentClassName}>{content}</div>
  }

  // 构建渲染内容
  const renderContent = () => {
    const elements: React.ReactNode[] = []
    let lastEnd = 0

    mergedGroups.forEach((group, groupIndex) => {
      const groupStart = group[0].start
      const groupEnd = Math.max(...group.map((r) => r.end))

      // 添加高亮前的普通文本
      if (groupStart > lastEnd) {
        elements.push(
          <span key={`text-${groupIndex}-before`}>
            {content.slice(lastEnd, groupStart)}
          </span>
        )
      }

      // 处理重叠的高亮
      if (group.length === 1) {
        // 单个高亮
        const range = group[0]
        const isActive = range.evidenceId === activeEvidenceId
        const evidence = evidenceMap.get(range.evidenceId)

        elements.push(
          <mark
            key={`highlight-${range.evidenceId}`}
            className={`
              ${range.colorClass}
              ${highlightClassName}
              ${isActive ? ACTIVE_HIGHLIGHT_CLASS : ''}
            `}
            onClick={() => handleHighlightClick(range.evidenceId)}
            title={evidence?.content}
            data-evidence-id={range.evidenceId}
          >
            {content.slice(range.start, range.end)}
          </mark>
        )
      } else {
        // 多个重叠的高亮，使用嵌套或并排显示
        const baseRange = group[0]
        const isActive = baseRange.evidenceId === activeEvidenceId
        const evidence = evidenceMap.get(baseRange.evidenceId)

        // 创建一个包含所有重叠证据的容器
        elements.push(
          <span
            key={`highlight-group-${groupIndex}`}
            className="relative inline"
          >
            <mark
              className={`
                ${baseRange.colorClass}
                ${highlightClassName}
                ${isActive ? ACTIVE_HIGHLIGHT_CLASS : ''}
              `}
              onClick={() => handleHighlightClick(baseRange.evidenceId)}
              title={evidence?.content}
              data-evidence-id={baseRange.evidenceId}
            >
              {content.slice(groupStart, groupEnd)}
            </mark>
            {/* 显示重叠指示器 */}
            {group.length > 1 && (
              <span className="absolute -top-1 -right-1 flex -space-x-1">
                {group.slice(1).map((range, idx) => (
                  <span
                    key={`overlap-${range.evidenceId}`}
                    className={`
                      w-2 h-2 rounded-full border border-white
                      ${range.colorClass?.split(' ')[0] || 'bg-gray-400'}
                    `}
                    title={`重叠证据: ${evidenceMap.get(range.evidenceId)?.content || ''}`}
                  />
                ))}
              </span>
            )}
          </span>
        )
      }

      lastEnd = groupEnd
    })

    // 添加最后一段普通文本
    if (lastEnd < content.length) {
      elements.push(
        <span key="text-final">{content.slice(lastEnd)}</span>
      )
    }

    return elements
  }

  return <div className={contentClassName}>{renderContent()}</div>
}

/**
 * 简单的高亮文本组件
 * 用于显示带有单个高亮范围的文本片段
 */
export interface SimpleHighlightProps {
  text: string
  highlights: Array<{
    start: number
    end: number
    className?: string
  }>
  className?: string
}

export function SimpleHighlight({
  text,
  highlights,
  className = '',
}: SimpleHighlightProps) {
  if (highlights.length === 0) {
    return <span className={className}>{text}</span>
  }

  // 排序并合并重叠
  const sorted = [...highlights].sort((a, b) => a.start - b.start)
  const elements: React.ReactNode[] = []
  let lastEnd = 0

  sorted.forEach((hl, index) => {
    // 添加高亮前的文本
    if (hl.start > lastEnd) {
      elements.push(
        <span key={`before-${index}`}>{text.slice(lastEnd, hl.start)}</span>
      )
    }

    // 添加高亮文本
    elements.push(
      <mark
        key={`hl-${index}`}
        className={hl.className || 'bg-yellow-200 px-0.5 rounded'}
      >
        {text.slice(Math.max(hl.start, lastEnd), hl.end)}
      </mark>
    )

    lastEnd = Math.max(lastEnd, hl.end)
  })

  // 添加剩余文本
  if (lastEnd < text.length) {
    elements.push(<span key="final">{text.slice(lastEnd)}</span>)
  }

  return <span className={className}>{elements}</span>
}

export default EvidenceHighlighter
