/**
 * @file content_import_dialog.tsx
 * @brief Multi-format Content Import Dialog (EPUB / PDF / arXiv)
 * @author sailing-innocent
 * @date 2026-11-26
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Upload, FileText, BookOpen, Globe } from 'lucide-react'
import { api_import_arxiv, api_import_epub, api_import_pdf } from '@lib/api/text'
import type { MultiFormatImportResponse } from '@lib/data/text'

interface ContentImportDialogProps {
  defaultTopicId?: number
  defaultPillar?: string
  onImported?: (result: MultiFormatImportResponse) => void
  trigger?: React.ReactNode
}

type ImportMode = 'epub' | 'pdf' | 'arxiv'

export default function ContentImportDialog({
  defaultTopicId,
  defaultPillar,
  onImported,
  trigger,
}: ContentImportDialogProps) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<ImportMode>('pdf')
  const [file, setFile] = useState<File | null>(null)
  const [arxivInput, setArxivInput] = useState('')
  const [titleOverride, setTitleOverride] = useState('')
  const [authorOverride, setAuthorOverride] = useState('')
  const [pillar, setPillar] = useState(defaultPillar || 'tech')
  const [readingTrack, setReadingTrack] = useState(defaultTopicId ? 'project' : 'mainline')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleModeSwitch = (next: ImportMode) => {
    setMode(next)
    setError(null)
    if (next === 'epub') {
      setPillar(defaultPillar || 'history')
      setReadingTrack(defaultTopicId ? 'project' : 'mainline')
    } else {
      setPillar(defaultPillar || 'tech')
      setReadingTrack('project')
    }
  }

  const handleSubmit = async () => {
    setError(null)
    setLoading(true)
    try {
      let res: MultiFormatImportResponse
      if (mode === 'epub') {
        if (!file) throw new Error('请选择 .epub 文件')
        res = await api_import_epub(file, {
          pillar,
          reading_track: readingTrack,
          work_type: 'book',
          topic_id: defaultTopicId,
          title: titleOverride.trim() || undefined,
          author: authorOverride.trim() || undefined,
        })
      } else if (mode === 'pdf') {
        if (!file) throw new Error('请选择 .pdf 文件')
        res = await api_import_pdf(file, {
          pillar,
          reading_track: readingTrack,
          work_type: 'paper',
          topic_id: defaultTopicId,
          title: titleOverride.trim() || undefined,
          author: authorOverride.trim() || undefined,
        })
      } else {
        if (!arxivInput.trim()) throw new Error('请输入 arXiv ID 或链接（如 2405.12345）')
        res = await api_import_arxiv({
          arxiv_id_or_url: arxivInput.trim(),
          pillar,
          reading_track: readingTrack,
          topic_id: defaultTopicId,
          download_pdf: true,
        })
      }
      onImported?.(res)
      setOpen(false)
      setFile(null)
      setArxivInput('')
      setTitleOverride('')
      setAuthorOverride('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button size="sm">
            <Upload className="w-4 h-4 mr-1.5" />
            导入论文 / 书籍
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>多格式内容导入</DialogTitle>
          <DialogDescription>
            支持 EPUB 电子书（自动分卷）、PDF 论文/书籍（正文分节 + 原 PDF 对照）与 arXiv 论文直连拉取
          </DialogDescription>
        </DialogHeader>

        {/* 导入方式切换 */}
        <div className="grid grid-cols-3 gap-2 pt-1">
          <Button
            type="button"
            variant={mode === 'pdf' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleModeSwitch('pdf')}
          >
            <FileText className="w-4 h-4 mr-1" />
            PDF 论文/书
          </Button>
          <Button
            type="button"
            variant={mode === 'arxiv' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleModeSwitch('arxiv')}
          >
            <Globe className="w-4 h-4 mr-1" />
            arXiv 直拉
          </Button>
          <Button
            type="button"
            variant={mode === 'epub' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleModeSwitch('epub')}
          >
            <BookOpen className="w-4 h-4 mr-1" />
            EPUB 电子书
          </Button>
        </div>

        <div className="grid gap-3 py-2">
          {mode === 'arxiv' ? (
            <div className="grid gap-1.5">
              <Label>arXiv ID 或 URL *</Label>
              <Input
                placeholder="例如：2308.04079 或 https://arxiv.org/abs/2308.04079"
                value={arxivInput}
                onChange={(e) => setArxivInput(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                自动抓取论文元数据、结构化 HTML 分节正文并留存原 PDF 附件供公式/插图对照。
              </p>
            </div>
          ) : (
            <>
              <div className="grid gap-1.5">
                <Label>选择 {mode.toUpperCase()} 文件 *</Label>
                <Input
                  type="file"
                  accept={mode === 'epub' ? '.epub' : '.pdf'}
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <Label>自定义标题（可选）</Label>
                  <Input
                    placeholder="留空则自动识别"
                    value={titleOverride}
                    onChange={(e) => setTitleOverride(e.target.value)}
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label>作者（可选）</Label>
                  <Input
                    placeholder="留空则自动识别"
                    value={authorOverride}
                    onChange={(e) => setAuthorOverride(e.target.value)}
                  />
                </div>
              </div>
            </>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label>素养归属</Label>
              <Select value={pillar} onValueChange={setPillar}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="tech">技术素养</SelectItem>
                  <SelectItem value="history">历史素养</SelectItem>
                  <SelectItem value="aesthetics">审美素养</SelectItem>
                  <SelectItem value="fiction">小说 / 文学</SelectItem>
                  <SelectItem value="general">综合</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>阅读轨道</Label>
              <Select value={readingTrack} onValueChange={setReadingTrack}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="mainline">主线精读</SelectItem>
                  <SelectItem value="project">项目驱动</SelectItem>
                  <SelectItem value="leisure">日常消遣</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {error && <div className="text-sm text-red-500 bg-red-50 p-2 rounded">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={loading}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '正在解析并入库...' : '开始导入'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
