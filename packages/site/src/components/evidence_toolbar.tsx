/**
 * @file evidence_toolbar.tsx
 * @brief Evidence Annotation Toolbar Component
 * @author sailing-innocent
 * @date 2025-02-28
 */

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Highlighter, X, Check, MessageSquare, Tag } from 'lucide-react'
import type { TextSelection } from '@hooks/useTextSelection'

export type EvidenceType = 'character' | 'setting' | 'outline' | 'relation' | 'custom'

export interface EvidenceToolbarProps {
  /** 当前选区 */
  selection: TextSelection | null
  /** 选区矩形位置（用于定位工具栏） */
  selectionRect: DOMRect | null
  /** 容器元素（用于计算相对位置） */
  containerElement?: HTMLElement | null
  /** 创建证据回调 */
  onCreateEvidence: (data: {
    evidenceType: EvidenceType
    content: string
    targetType?: string
    targetId?: string
    context?: string
  }) => void
  /** 取消回调 */
  onCancel: () => void
  /** 是否显示 */
  visible: boolean
  /** 可选的证据类型列表 */
  evidenceTypes?: { value: EvidenceType; label: string }[]
}

const DEFAULT_EVIDENCE_TYPES: { value: EvidenceType; label: string }[] = [
  { value: 'character', label: '人物' },
  { value: 'setting', label: '设定' },
  { value: 'outline', label: '大纲' },
  { value: 'relation', label: '关系' },
  { value: 'custom', label: '自定义' },
]

/**
 * 证据标注工具栏
 * 
 * 在文本选择后显示的工具栏，允许用户：
 * - 选择证据类型
 * - 输入证据内容
 * - 关联到目标（人物/设定等）
 * - 添加上下文说明
 * 
 * 工具栏会智能定位到选区附近。
 */
export function EvidenceToolbar({
  selection,
  selectionRect,
  containerElement,
  onCreateEvidence,
  onCancel,
  visible,
  evidenceTypes = DEFAULT_EVIDENCE_TYPES,
}: EvidenceToolbarProps) {
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('character')
  const [content, setContent] = useState('')
  const [targetType, setTargetType] = useState('')
  const [targetId, setTargetId] = useState('')
  const [context, setContext] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const toolbarRef = useRef<HTMLDivElement>(null)

  // 当选择变化时，重置表单
  useEffect(() => {
    if (selection) {
      // 使用选中的文本作为默认内容
      setContent(selection.text)
      setIsOpen(true)
    } else {
      setIsOpen(false)
    }
  }, [selection?.text])

  // 计算工具栏位置
  const getToolbarPosition = () => {
    if (!selectionRect || !containerElement) {
      return { top: 0, left: 0 }
    }

    const containerRect = containerElement.getBoundingClientRect()
    const toolbarHeight = 200 // 预估高度
    const toolbarWidth = 320

    // 计算相对于容器的位置
    let top = selectionRect.bottom - containerRect.top + 8
    let left = selectionRect.left - containerRect.left + (selectionRect.width / 2) - (toolbarWidth / 2)

    // 边界检查：确保不超出容器右边界
    if (left + toolbarWidth > containerRect.width) {
      left = containerRect.width - toolbarWidth - 16
    }
    // 边界检查：确保不超出容器左边界
    if (left < 0) {
      left = 16
    }
    // 边界检查：如果下方空间不足，显示在选区上方
    if (top + toolbarHeight > containerRect.height) {
      top = selectionRect.top - containerRect.top - toolbarHeight - 8
    }

    return { top, left }
  }

  const handleSubmit = () => {
    if (!content.trim()) return

    onCreateEvidence({
      evidenceType,
      content: content.trim(),
      targetType: targetType || undefined,
      targetId: targetId || undefined,
      context: context || undefined,
    })

    // 重置表单
    setContent('')
    setTargetType('')
    setTargetId('')
    setContext('')
    setIsOpen(false)
  }

  const handleCancel = () => {
    setContent('')
    setTargetType('')
    setTargetId('')
    setContext('')
    setIsOpen(false)
    onCancel()
  }

  if (!visible || !selection) {
    return null
  }

  const position = getToolbarPosition()

  return (
    <div
      ref={toolbarRef}
      className="absolute z-50 animate-in fade-in zoom-in-95 duration-200"
      style={{
        top: position.top,
        left: position.left,
      }}
    >
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="secondary"
            size="sm"
            className="shadow-lg border"
            onClick={() => setIsOpen(true)}
          >
            <Highlighter className="w-4 h-4 mr-1" />
            添加证据
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className="w-80 p-4"
          align="start"
          side="bottom"
          onInteractOutside={(e) => {
            // 防止点击工具栏外部时关闭
            e.preventDefault()
          }}
        >
          <div className="space-y-4">
            {/* 头部 */}
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-sm">添加证据标注</h4>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCancel}>
                <X className="w-4 h-4" />
              </Button>
            </div>

            {/* 选中的文本预览 */}
            <div className="bg-muted p-2 rounded text-xs text-muted-foreground line-clamp-3">
              <span className="font-medium">选中内容：</span>
              {selection.text}
            </div>

            {/* 证据类型选择 */}
            <div className="space-y-2">
              <label className="text-xs font-medium">证据类型</label>
              <Select value={evidenceType} onValueChange={(v) => setEvidenceType(v as EvidenceType)}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {evidenceTypes.map((type) => (
                    <SelectItem key={type.value} value={type.value} className="text-xs">
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 证据内容 */}
            <div className="space-y-2">
              <label className="text-xs font-medium">证据说明</label>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="描述这个证据的内容..."
                className="min-h-[60px] text-xs resize-none"
              />
            </div>

            {/* 目标关联（可选） */}
            <div className="space-y-2">
              <label className="text-xs font-medium flex items-center gap-1">
                <Tag className="w-3 h-3" />
                关联目标（可选）
              </label>
              <div className="flex gap-2">
                <Input
                  placeholder="目标类型"
                  value={targetType}
                  onChange={(e) => setTargetType(e.target.value)}
                  className="h-8 text-xs flex-1"
                />
                <Input
                  placeholder="目标ID"
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  className="h-8 text-xs flex-1"
                />
              </div>
            </div>

            {/* 上下文（可选） */}
            <div className="space-y-2">
              <label className="text-xs font-medium flex items-center gap-1">
                <MessageSquare className="w-3 h-3" />
                上下文说明（可选）
              </label>
              <Input
                placeholder="添加额外的上下文信息..."
                value={context}
                onChange={(e) => setContext(e.target.value)}
                className="h-8 text-xs"
              />
            </div>

            {/* 操作按钮 */}
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleCancel}>
                取消
              </Button>
              <Button
                size="sm"
                className="h-7 text-xs"
                onClick={handleSubmit}
                disabled={!content.trim()}
              >
                <Check className="w-3 h-3 mr-1" />
                确认
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}

export default EvidenceToolbar
