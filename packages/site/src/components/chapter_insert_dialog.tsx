/**
 * @file chapter_insert_dialog.tsx
 * @brief Chapter Insert Dialog Component
 * @author sailing-innocent
 * @date 2025-01-30
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api_insert_chapter } from '@lib/api/text'
import type { ChapterInsertResponse, ChapterListItem } from '@lib/data/text'

interface ChapterInsertDialogProps {
  editionId: number
  chapters: ChapterListItem[]
  onInsertSuccess?: (response: ChapterInsertResponse) => void
}

export default function ChapterInsertDialog({
  editionId,
  chapters,
  onInsertSuccess,
}: ChapterInsertDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [sortIndex, setSortIndex] = useState(0)
  const [label, setLabel] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const handleSubmit = async () => {
    if (!content.trim()) {
      setError('请输入章节内容')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await api_insert_chapter(editionId, {
        sort_index: sortIndex,
        label: label.trim() || undefined,
        title: title.trim() || undefined,
        content: content,
      })
      onInsertSuccess?.(response)
      setOpen(false)
      resetForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : '插入失败')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setSortIndex(chapters.length)
    setLabel('')
    setTitle('')
    setContent('')
    setError(null)
  }

  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen)
    if (isOpen) {
      // 默认插入到末尾
      setSortIndex(chapters.length)
      setError(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          插入章节
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>插入新章节</DialogTitle>
          <DialogDescription>
            添加新章节到指定位置，该位置及之后的章节会自动后移
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* 插入位置 */}
          <div className="grid gap-2">
            <Label htmlFor="sort_index">插入位置</Label>
            <div className="flex items-center gap-2">
              <Input
                id="sort_index"
                type="number"
                min={0}
                max={chapters.length}
                value={sortIndex}
                onChange={(e) => setSortIndex(parseInt(e.target.value) || 0)}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">
                {sortIndex === 0
                  ? '（插入到最前面）'
                  : sortIndex >= chapters.length
                    ? '（插入到最后）'
                    : `（在"${chapters[sortIndex - 1]?.label || ''}${chapters[sortIndex - 1]?.title ? ' ' + chapters[sortIndex - 1]?.title : ''}"之后）`}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              当前共 {chapters.length} 章，可输入 0 到 {chapters.length}
            </p>
          </div>

          {/* 章节标签 */}
          <div className="grid gap-2">
            <Label htmlFor="label">章节标签</Label>
            <Input
              id="label"
              placeholder="如：第一章、Chapter 1"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>

          {/* 章节标题 */}
          <div className="grid gap-2">
            <Label htmlFor="title">章节标题</Label>
            <Input
              id="title"
              placeholder="如：风起云涌"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* 章节内容 */}
          <div className="grid gap-2">
            <Label htmlFor="content">章节内容 *</Label>
            <textarea
              id="content"
              className="min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              placeholder="在此输入章节正文内容..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              已输入 {content.length.toLocaleString()} 字符
            </p>
          </div>

          {/* 错误提示 */}
          {error && <div className="text-sm text-red-500">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '插入中...' : '确认插入'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
