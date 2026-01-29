/**
 * @file text_import_dialog.tsx
 * @brief Text Import Dialog Component
 * @author sailing-innocent
 * @date 2025-01-29
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api_import_text } from '@lib/api/text'
import type { TextImportRequest, ImportResponse } from '@lib/data/text'

interface TextImportDialogProps {
  onImportSuccess?: (response: ImportResponse) => void
}

export default function TextImportDialog({ onImportSuccess }: TextImportDialogProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [synopsis, setSynopsis] = useState('')
  const [language, setLanguage] = useState('zh')
  const [content, setContent] = useState('')

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      setContent(text)

      // 尝试从文件名提取标题
      if (!title) {
        const fileName = file.name.replace(/\.[^/.]+$/, '') // 移除扩展名
        setTitle(fileName)
      }
    } catch (err) {
      setError('读取文件失败')
    }
  }

  const handleSubmit = async () => {
    if (!title.trim()) {
      setError('请输入作品标题')
      return
    }
    if (!content.trim()) {
      setError('请输入或上传文本内容')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const request: TextImportRequest = {
        work_title: title.trim(),
        content: content,
        work_author: author.trim() || undefined,
        work_synopsis: synopsis.trim() || undefined,
        language: language,
      }

      const response = await api_import_text(request)
      onImportSuccess?.(response)
      setOpen(false)
      resetForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : '导入失败')
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setTitle('')
    setAuthor('')
    setSynopsis('')
    setLanguage('zh')
    setContent('')
    setError(null)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>导入文本</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>导入文本</DialogTitle>
          <DialogDescription>上传或粘贴小说文本，系统将自动识别章节结构</DialogDescription>
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

          {/* 语言 */}
          <div className="grid gap-2">
            <Label htmlFor="language">语言</Label>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="zh">中文</SelectItem>
                <SelectItem value="en">English</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 简介 */}
          <div className="grid gap-2">
            <Label htmlFor="synopsis">作品简介</Label>
            <textarea
              id="synopsis"
              className="min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="请输入作品简介（可选）"
              value={synopsis}
              onChange={(e) => setSynopsis(e.target.value)}
            />
          </div>

          {/* 文件上传 */}
          <div className="grid gap-2">
            <Label htmlFor="file">上传文件</Label>
            <Input id="file" type="file" accept=".txt,.md" onChange={handleFileUpload} />
            <p className="text-xs text-muted-foreground">支持 .txt, .md 格式文件</p>
          </div>

          {/* 文本内容 */}
          <div className="grid gap-2">
            <Label htmlFor="content">文本内容</Label>
            <textarea
              id="content"
              className="min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              placeholder="在此粘贴或输入文本内容...&#10;&#10;系统支持以下章节格式识别：&#10;- 第一章 章节标题&#10;- Chapter 1 Title&#10;- 1. 标题"
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
            {loading ? '导入中...' : '开始导入'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
