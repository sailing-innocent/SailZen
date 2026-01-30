/**
 * @file work_edit_dialog.tsx
 * @brief Work Edit Dialog Component
 * @author sailing-innocent
 * @date 2025-01-30
 */

import { useState, useEffect } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api_update_work } from '@lib/api/text'
import type { Work, WorkCreate } from '@lib/data/text'

interface WorkEditDialogProps {
  work: Work
  onUpdateSuccess?: (updatedWork: Work) => void
  trigger?: React.ReactNode
}

const WORK_TYPES = [
  { value: 'web_novel', label: '网络小说' },
  { value: 'novel', label: '小说' },
  { value: 'essay', label: '散文' },
]

const WORK_STATUSES = [
  { value: 'ongoing', label: '连载中' },
  { value: 'completed', label: '已完结' },
  { value: 'hiatus', label: '暂停' },
]

const LANGUAGES = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
]

export default function WorkEditDialog({
  work,
  onUpdateSuccess,
  trigger,
}: WorkEditDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form fields
  const [title, setTitle] = useState(work.title)
  const [originalTitle, setOriginalTitle] = useState(work.original_title || '')
  const [author, setAuthor] = useState(work.author || '')
  const [synopsis, setSynopsis] = useState(work.synopsis || '')
  const [workType, setWorkType] = useState(work.work_type)
  const [status, setStatus] = useState(work.status)
  const [languagePrimary, setLanguagePrimary] = useState(work.language_primary)

  // Reset form when work changes or dialog opens
  useEffect(() => {
    if (open) {
      setTitle(work.title)
      setOriginalTitle(work.original_title || '')
      setAuthor(work.author || '')
      setSynopsis(work.synopsis || '')
      setWorkType(work.work_type)
      setStatus(work.status)
      setLanguagePrimary(work.language_primary)
      setError(null)
    }
  }, [open, work])

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError('作品标题不能为空')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const data: WorkCreate = {
        title: title.trim(),
        original_title: originalTitle.trim() || undefined,
        author: author.trim() || undefined,
        synopsis: synopsis.trim() || undefined,
        work_type: workType,
        status: status,
        language_primary: languagePrimary,
      }

      const updatedWork = await api_update_work(work.id, data)
      onUpdateSuccess?.(updatedWork)
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button size="sm" variant="outline">
            编辑
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑作品信息</DialogTitle>
          <DialogDescription>
            修改作品的基本信息，包括标题、作者、简介等
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* 作品标题 */}
          <div className="grid gap-2">
            <Label htmlFor="title">作品标题 *</Label>
            <Input
              id="title"
              placeholder="请输入作品标题"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* 原标题 */}
          <div className="grid gap-2">
            <Label htmlFor="original_title">原标题</Label>
            <Input
              id="original_title"
              placeholder="如有外文原标题，请输入"
              value={originalTitle}
              onChange={(e) => setOriginalTitle(e.target.value)}
            />
          </div>

          {/* 作者 */}
          <div className="grid gap-2">
            <Label htmlFor="author">作者</Label>
            <Input
              id="author"
              placeholder="请输入作者名"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
            />
          </div>

          {/* 作品简介 */}
          <div className="grid gap-2">
            <Label htmlFor="synopsis">作品简介</Label>
            <textarea
              id="synopsis"
              className="min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="请输入作品简介..."
              value={synopsis}
              onChange={(e) => setSynopsis(e.target.value)}
            />
          </div>

          {/* 作品类型 */}
          <div className="grid gap-2">
            <Label htmlFor="work_type">作品类型</Label>
            <Select value={workType} onValueChange={setWorkType}>
              <SelectTrigger>
                <SelectValue placeholder="选择作品类型" />
              </SelectTrigger>
              <SelectContent>
                {WORK_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 作品状态 */}
          <div className="grid gap-2">
            <Label htmlFor="status">作品状态</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue placeholder="选择作品状态" />
              </SelectTrigger>
              <SelectContent>
                {WORK_STATUSES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 主要语言 */}
          <div className="grid gap-2">
            <Label htmlFor="language">主要语言</Label>
            <Select value={languagePrimary} onValueChange={setLanguagePrimary}>
              <SelectTrigger>
                <SelectValue placeholder="选择主要语言" />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGES.map((lang) => (
                  <SelectItem key={lang.value} value={lang.value}>
                    {lang.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 错误提示 */}
          {error && <div className="text-sm text-red-500">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
