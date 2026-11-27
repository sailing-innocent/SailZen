/**
 * @file work_edit_dialog.tsx
 * @brief Work Edit Dialog Component (Content 2.0: Pillar / Reading Status / Track / Vault)
 * @author sailing-innocent
 * @date 2026-11-26
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
import type { Work, WorkUpdate } from '@lib/data/text'

interface WorkEditDialogProps {
  work: Work
  onUpdateSuccess?: (updatedWork: Work) => void
  trigger?: React.ReactNode
}

const WORK_TYPES = [
  { value: 'web_novel', label: '网文' },
  { value: 'book', label: '书籍' },
  { value: 'paper', label: '学术论文' },
  { value: 'article', label: '深度长文' },
  { value: 'script', label: '剧本/游戏叙事' },
  { value: 'reference', label: '工具资料' },
  { value: 'novel', label: '小说' },
]

const PILLARS = [
  { value: 'tech', label: '技术素养' },
  { value: 'history', label: '历史素养' },
  { value: 'aesthetics', label: '审美素养' },
  { value: 'fiction', label: '长篇小说 / 文学' },
  { value: 'general', label: '综合' },
]

const READING_STATUSES = [
  { value: 'inbox', label: '收件箱' },
  { value: 'queued', label: '待读队列' },
  { value: 'reading', label: '正在读' },
  { value: 'paused', label: '搁置' },
  { value: 'finished', label: '已读完' },
  { value: 'dropped', label: '弃坑' },
]

const READING_TRACKS = [
  { value: 'mainline', label: '主线精读' },
  { value: 'project', label: '项目驱动 (Rhythm)' },
  { value: 'leisure', label: '日常消遣' },
]

export default function WorkEditDialog({
  work,
  onUpdateSuccess,
  trigger,
}: WorkEditDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState(work.title)
  const [author, setAuthor] = useState(work.author || '')
  const [synopsis, setSynopsis] = useState(work.synopsis || '')
  const [workType, setWorkType] = useState(work.work_type || 'web_novel')
  const [pillar, setPillar] = useState(work.pillar || 'fiction')
  const [readingStatus, setReadingStatus] = useState(work.reading_status || 'queued')
  const [readingTrack, setReadingTrack] = useState(work.reading_track || 'leisure')
  const [sourceUrl, setSourceUrl] = useState(work.source_url || '')
  const [vaultSlug, setVaultSlug] = useState(work.vault_slug || '')

  useEffect(() => {
    if (open) {
      setTitle(work.title)
      setAuthor(work.author || '')
      setSynopsis(work.synopsis || '')
      setWorkType(work.work_type || 'web_novel')
      setPillar(work.pillar || 'fiction')
      setReadingStatus(work.reading_status || 'queued')
      setReadingTrack(work.reading_track || 'leisure')
      setSourceUrl(work.source_url || '')
      setVaultSlug(work.vault_slug || '')
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
      const data: WorkUpdate = {
        title: title.trim(),
        author: author.trim() || undefined,
        synopsis: synopsis.trim() || undefined,
        work_type: workType,
        pillar,
        reading_status: readingStatus,
        reading_track: readingTrack,
        source_url: sourceUrl.trim() || undefined,
        vault_slug: vaultSlug.trim() || undefined,
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
      <DialogContent className="sm:max-w-[540px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑作品元数据</DialogTitle>
          <DialogDescription>
            配置作品的素养归属、阅读轨道、阅读状态与 Vault 笔记映射
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 py-3">
          <div className="grid gap-1.5">
            <Label htmlFor="work-title">标题 *</Label>
            <Input id="work-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="work-author">作者</Label>
              <Input id="work-author" value={author} onChange={(e) => setAuthor(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label>作品类型</Label>
              <Select value={workType} onValueChange={setWorkType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {WORK_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="grid gap-1.5">
              <Label>素养归属</Label>
              <Select value={pillar} onValueChange={setPillar}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PILLARS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>阅读轨道</Label>
              <Select value={readingTrack} onValueChange={setReadingTrack}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {READING_TRACKS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>阅读状态</Label>
              <Select value={readingStatus} onValueChange={setReadingStatus}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {READING_STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="work-vault">Vault 笔记标识</Label>
              <Input
                id="work-vault"
                placeholder="read.my-book"
                value={vaultSlug}
                onChange={(e) => setVaultSlug(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="work-url">原文链接 / arXiv</Label>
              <Input
                id="work-url"
                placeholder="https://arxiv.org/abs/..."
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="work-synopsis">简介 / 摘要</Label>
            <textarea
              id="work-synopsis"
              className="min-h-[84px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={synopsis}
              onChange={(e) => setSynopsis(e.target.value)}
            />
          </div>

          {error && <div className="text-sm text-red-500">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>取消</Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '保存中...' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
