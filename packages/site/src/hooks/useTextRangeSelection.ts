/**
 * @file useTextRangeSelection.ts
 * @brief Text Range Selection Hook
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  TextRangeSelection,
  TextRangePreview,
  TextRangeContent,
  RangeSelectionMode,
  SelectedChapterInfo,
} from '@lib/data/analysis'
import {
  api_preview_range,
  api_get_range_content,
} from '@lib/api/analysis'

export interface UseTextRangeSelectionOptions {
  editionId: number
  initialMode?: RangeSelectionMode
  initialChapterIndex?: number
  autoPreview?: boolean
  debounceMs?: number
}

export interface UseTextRangeSelectionReturn {
  // 选择状态
  selection: TextRangeSelection
  setSelection: (selection: TextRangeSelection) => void
  
  // 模式切换
  mode: RangeSelectionMode
  setMode: (mode: RangeSelectionMode) => void
  
  // 单章选择
  selectedChapterIndex: number | undefined
  setSelectedChapterIndex: (index: number | undefined) => void
  
  // 范围选择
  startIndex: number | undefined
  setStartIndex: (index: number | undefined) => void
  endIndex: number | undefined
  setEndIndex: (index: number | undefined) => void
  
  // 多章选择
  selectedIndices: number[]
  toggleChapterSelection: (index: number) => void
  selectChapters: (indices: number[]) => void
  clearChapterSelection: () => void
  selectAllChapters: (totalChapters: number) => void
  
  // 预览状态
  preview: TextRangePreview | null
  isPreviewLoading: boolean
  previewError: string | null
  refreshPreview: () => Promise<void>
  
  // 内容获取
  content: TextRangeContent | null
  isContentLoading: boolean
  contentError: string | null
  fetchContent: () => Promise<void>
  
  // 统计信息
  chapterCount: number
  totalChars: number
  totalWords: number
  estimatedTokens: number
  selectedChapters: SelectedChapterInfo[]
  warnings: string[]
  
  // 重置
  reset: () => void
}

/**
 * 文本范围选择 Hook
 * 
 * 提供完整的文本范围选择状态管理和预览功能
 * 
 * @example
 * ```tsx
 * const {
 *   selection,
 *   mode,
 *   setMode,
 *   selectedIndices,
 *   toggleChapterSelection,
 *   preview,
 *   isPreviewLoading,
 * } = useTextRangeSelection({ editionId: 1 })
 * ```
 */
export function useTextRangeSelection(
  options: UseTextRangeSelectionOptions
): UseTextRangeSelectionReturn {
  const { editionId, initialMode = 'full_edition', initialChapterIndex, autoPreview = true, debounceMs = 300 } = options

  // 模式状态
  const [mode, setModeState] = useState<RangeSelectionMode>(initialMode)
  
  // 单章选择
  const [selectedChapterIndex, setSelectedChapterIndex] = useState<number | undefined>(initialChapterIndex)
  
  // 范围选择
  const [startIndex, setStartIndex] = useState<number | undefined>(undefined)
  const [endIndex, setEndIndex] = useState<number | undefined>(undefined)
  
  // 多章选择
  const [selectedIndices, setSelectedIndices] = useState<number[]>([])
  
  // 预览状态
  const [preview, setPreview] = useState<TextRangePreview | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState<string | null>(null)
  
  // 内容状态
  const [content, setContent] = useState<TextRangeContent | null>(null)
  const [isContentLoading, setIsContentLoading] = useState(false)
  const [contentError, setContentError] = useState<string | null>(null)
  
  // Debounce timer
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null)

  // 构建选择对象
  const buildSelection = useCallback((): TextRangeSelection => {
    const baseSelection: TextRangeSelection = {
      edition_id: editionId,
      mode,
    }

    switch (mode) {
      case 'single_chapter':
        return {
          ...baseSelection,
          chapter_index: selectedChapterIndex,
        }
      case 'chapter_range':
        return {
          ...baseSelection,
          start_index: startIndex,
          end_index: endIndex,
        }
      case 'multi_chapter':
        return {
          ...baseSelection,
          chapter_indices: selectedIndices,
        }
      case 'current_to_end':
        return {
          ...baseSelection,
          start_index: startIndex,
        }
      case 'custom_range':
        return {
          ...baseSelection,
          node_ids: [], // 暂时不支持
        }
      case 'full_edition':
      default:
        return baseSelection
    }
  }, [editionId, mode, selectedChapterIndex, startIndex, endIndex, selectedIndices])

  // 当前选择
  const [selection, setSelection] = useState<TextRangeSelection>(buildSelection())

  // 更新选择对象
  useEffect(() => {
    setSelection(buildSelection())
  }, [buildSelection])

  // 设置模式（同时重置相关状态）
  const setMode = useCallback((newMode: RangeSelectionMode) => {
    setModeState(newMode)
    
    // 重置其他模式的状态
    if (newMode !== 'single_chapter') {
      setSelectedChapterIndex(undefined)
    }
    if (newMode !== 'chapter_range') {
      setStartIndex(undefined)
      setEndIndex(undefined)
    }
    if (newMode !== 'multi_chapter') {
      setSelectedIndices([])
    }
    if (newMode !== 'current_to_end') {
      if (newMode !== 'chapter_range') {
        setStartIndex(undefined)
      }
    }
  }, [])

  // 多章选择操作
  const toggleChapterSelection = useCallback((index: number) => {
    setSelectedIndices(prev => {
      if (prev.includes(index)) {
        return prev.filter(i => i !== index)
      }
      return [...prev, index].sort((a, b) => a - b)
    })
  }, [])

  const selectChapters = useCallback((indices: number[]) => {
    setSelectedIndices(indices.sort((a, b) => a - b))
  }, [])

  const clearChapterSelection = useCallback(() => {
    setSelectedIndices([])
  }, [])

  const selectAllChapters = useCallback((totalChapters: number) => {
    setSelectedIndices(Array.from({ length: totalChapters }, (_, i) => i))
  }, [])

  // 刷新预览
  const refreshPreview = useCallback(async () => {
    setIsPreviewLoading(true)
    setPreviewError(null)
    
    try {
      const currentSelection = buildSelection()
      const result = await api_preview_range(currentSelection)
      setPreview(result)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : '预览失败')
      setPreview(null)
    } finally {
      setIsPreviewLoading(false)
    }
  }, [buildSelection])

  // 获取内容
  const fetchContent = useCallback(async () => {
    setIsContentLoading(true)
    setContentError(null)
    
    try {
      const currentSelection = buildSelection()
      const result = await api_get_range_content(currentSelection)
      setContent(result)
    } catch (err) {
      setContentError(err instanceof Error ? err.message : '获取内容失败')
      setContent(null)
    } finally {
      setIsContentLoading(false)
    }
  }, [buildSelection])

  // Auto preview with debounce
  useEffect(() => {
    if (!autoPreview) return

    // Clear previous timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    // Set new timer
    debounceTimerRef.current = setTimeout(() => {
      refreshPreview()
    }, debounceMs)

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [selection, autoPreview, debounceMs, refreshPreview])

  // 重置
  const reset = useCallback(() => {
    setModeState(initialMode)
    setSelectedChapterIndex(initialChapterIndex)
    setStartIndex(undefined)
    setEndIndex(undefined)
    setSelectedIndices([])
    setPreview(null)
    setContent(null)
    setPreviewError(null)
    setContentError(null)
  }, [initialMode, initialChapterIndex])

  // 导出统计信息
  const chapterCount = preview?.chapter_count ?? 0
  const totalChars = preview?.total_chars ?? 0
  const totalWords = preview?.total_words ?? 0
  const estimatedTokens = preview?.estimated_tokens ?? 0
  const selectedChapters = preview?.selected_chapters ?? []
  const warnings = preview?.warnings ?? []

  return {
    // 选择状态
    selection,
    setSelection,
    
    // 模式切换
    mode,
    setMode,
    
    // 单章选择
    selectedChapterIndex,
    setSelectedChapterIndex,
    
    // 范围选择
    startIndex,
    setStartIndex,
    endIndex,
    setEndIndex,
    
    // 多章选择
    selectedIndices,
    toggleChapterSelection,
    selectChapters,
    clearChapterSelection,
    selectAllChapters,
    
    // 预览状态
    preview,
    isPreviewLoading,
    previewError,
    refreshPreview,
    
    // 内容获取
    content,
    isContentLoading,
    contentError,
    fetchContent,
    
    // 统计信息
    chapterCount,
    totalChars,
    totalWords,
    estimatedTokens,
    selectedChapters,
    warnings,
    
    // 重置
    reset,
  }
}

export default useTextRangeSelection
