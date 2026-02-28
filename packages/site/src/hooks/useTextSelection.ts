/**
 * @file useTextSelection.ts
 * @brief Hook for text selection in chapter reader
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useCallback, useEffect, useRef } from 'react'

export interface TextSelection {
  /** 选中的文本 */
  text: string
  /** 起始偏移量（相对于章节内容） */
  startOffset: number
  /** 结束偏移量 */
  endOffset: number
  /** 选中文本所在的节点ID */
  nodeId?: number
  /** 选区矩形位置信息 */
  rect?: DOMRect
}

export interface UseTextSelectionOptions {
  /** 是否启用文本选择 */
  enabled?: boolean
  /** 容器元素选择器 */
  containerSelector?: string
  /** 选择完成回调 */
  onSelectionChange?: (selection: TextSelection | null) => void
  /** 最小选择长度 */
  minLength?: number
  /** 最大选择长度 */
  maxLength?: number
}

export interface UseTextSelectionReturn {
  /** 当前选区 */
  selection: TextSelection | null
  /** 是否正在选择 */
  isSelecting: boolean
  /** 清除选区 */
  clearSelection: () => void
  /** 手动设置选区 */
  setSelection: (selection: TextSelection | null) => void
  /** 获取选区在容器中的相对位置 */
  getSelectionRect: () => DOMRect | null
}

/**
 * 计算文本在元素中的偏移量
 */
function calculateOffset(container: Node, targetNode: Node, targetOffset: number): number {
  let offset = 0
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT,
    null,
    false
  )
  
  let node: Node | null
  while ((node = walker.nextNode())) {
    if (node === targetNode) {
      return offset + targetOffset
    }
    offset += node.textContent?.length || 0
  }
  
  return offset
}

/**
 * 文本选择 Hook
 * 
 * 用于在阅读器中捕获用户的文本选择，支持：
 * - 获取选中的文本内容和位置
 * - 计算相对于章节内容的偏移量
 * - 获取选区的矩形位置（用于显示工具栏）
 * - 支持最小/最大长度限制
 * 
 * @example
 * ```tsx
 * const { selection, clearSelection } = useTextSelection({
 *   enabled: true,
 *   containerSelector: '.chapter-content',
 *   onSelectionChange: (sel) => console.log('Selected:', sel?.text),
 *   minLength: 2,
 *   maxLength: 500,
 * })
 * ```
 */
export function useTextSelection(
  options: UseTextSelectionOptions = {}
): UseTextSelectionReturn {
  const {
    enabled = true,
    containerSelector,
    onSelectionChange,
    minLength = 1,
    maxLength = 10000,
  } = options

  const [selection, setSelectionState] = useState<TextSelection | null>(null)
  const [isSelecting, setIsSelecting] = useState(false)
  const containerRef = useRef<HTMLElement | null>(null)
  const mouseDownRef = useRef(false)

  // 获取容器元素
  useEffect(() => {
    if (containerSelector) {
      containerRef.current = document.querySelector(containerSelector)
    }
  }, [containerSelector])

  // 处理选区变化
  const handleSelectionChange = useCallback(() => {
    if (!enabled) return

    const domSelection = window.getSelection()
    if (!domSelection || domSelection.isCollapsed) {
      if (selection !== null) {
        setSelectionState(null)
        onSelectionChange?.(null)
      }
      return
    }

    const range = domSelection.getRangeAt(0)
    const text = range.toString().trim()

    // 检查长度限制
    if (text.length < minLength || text.length > maxLength) {
      return
    }

    // 计算偏移量
    const container = containerRef.current || document.body
    const startOffset = calculateOffset(container, range.startContainer, range.startOffset)
    const endOffset = calculateOffset(container, range.endContainer, range.endOffset)

    // 获取选区矩形
    const rect = range.getBoundingClientRect()

    const newSelection: TextSelection = {
      text,
      startOffset,
      endOffset,
      rect,
    }

    setSelectionState(newSelection)
    onSelectionChange?.(newSelection)
  }, [enabled, minLength, maxLength, onSelectionChange, selection])

  // 监听鼠标事件
  useEffect(() => {
    if (!enabled) return

    const handleMouseDown = () => {
      mouseDownRef.current = true
      setIsSelecting(true)
    }

    const handleMouseUp = () => {
      mouseDownRef.current = false
      setIsSelecting(false)
      // 延迟处理，确保选区已更新
      setTimeout(handleSelectionChange, 0)
    }

    const handleMouseMove = () => {
      if (mouseDownRef.current) {
        setIsSelecting(true)
      }
    }

    // 监听选区变化事件
    document.addEventListener('selectionchange', handleSelectionChange)
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousemove', handleMouseMove)

    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange)
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }, [enabled, handleSelectionChange])

  // 清除选区
  const clearSelection = useCallback(() => {
    const domSelection = window.getSelection()
    if (domSelection) {
      domSelection.removeAllRanges()
    }
    setSelectionState(null)
    onSelectionChange?.(null)
  }, [onSelectionChange])

  // 手动设置选区
  const setSelection = useCallback((newSelection: TextSelection | null) => {
    setSelectionState(newSelection)
    onSelectionChange?.(newSelection)
  }, [onSelectionChange])

  // 获取选区矩形
  const getSelectionRect = useCallback((): DOMRect | null => {
    const domSelection = window.getSelection()
    if (!domSelection || domSelection.isCollapsed) {
      return null
    }
    return domSelection.getRangeAt(0).getBoundingClientRect()
  }, [])

  return {
    selection,
    isSelecting,
    clearSelection,
    setSelection,
    getSelectionRect,
  }
}

export default useTextSelection
