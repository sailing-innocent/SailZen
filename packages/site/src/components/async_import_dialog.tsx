/**
 * @file async_import_dialog.tsx
 * @brief Async Import Dialog Component with WebSocket Progress
 * @author sailing-innocent
 * @date 2026-03-08
 */

import { useState, useCallback } from 'react'
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
import { Switch } from '@/components/ui/switch'
import { Progress } from '@/components/ui/progress'
import { uploadFile, createImportTask } from '@lib/api/asyncImport'
import type { ImportTaskProgress } from '@lib/data/text'

interface AsyncImportDialogProps {
  onImportSuccess?: (workId: number) => void
}

export default function AsyncImportDialog({ onImportSuccess }: AsyncImportDialogProps) {
  const [open, setOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [enableAi, setEnableAi] = useState(true)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [fileId, setFileId] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<number | null>(null)
  const [importProgress, setImportProgress] = useState<ImportTaskProgress | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (!selectedFile) return

    // 验证文件大小 (500MB)
    if (selectedFile.size > 500 * 1024 * 1024) {
      setError('文件太大，最大支持 500MB')
      return
    }

    // 验证文件类型
    const ext = selectedFile.name.split('.').pop()?.toLowerCase()
    if (!['txt', 'md', 'text'].includes(ext || '')) {
      setError('仅支持 .txt, .md, .text 文件')
      return
    }

    setFile(selectedFile)
    setError(null)

    // 自动提取标题
    if (!title) {
      const fileName = selectedFile.name.replace(/\.[^/.]+$/, '')
      setTitle(fileName)
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('请选择文件')
      return
    }

    setUploading(true)
    setError(null)
    setUploadProgress(0)

    try {
      const response = await uploadFile(file, (progress) => {
        setUploadProgress(progress)
      })

      setFileId(response.file_id)
      setSuccess('文件上传成功，准备创建导入任务...')
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  const handleCreateTask = async () => {
    if (!fileId) {
      setError('请先上传文件')
      return
    }

    if (!title.trim()) {
      setError('请输入作品标题')
      return
    }

    setCreating(true)
    setError(null)

    try {
      const response = await createImportTask({
        file_id: fileId,
        work_title: title.trim(),
        work_author: author.trim() || undefined,
        enable_ai_parsing: enableAi,
        priority: 5,
      })

      setTaskId(response.task_id)
      setSuccess(`导入任务已创建 (ID: ${response.task_id})`)
      
      // 关闭对话框并通知父组件
      setTimeout(() => {
        setOpen(false)
        resetForm()
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败')
    } finally {
      setCreating(false)
    }
  }

  const resetForm = () => {
    setTitle('')
    setAuthor('')
    setFile(null)
    setEnableAi(true)
    setUploadProgress(0)
    setFileId(null)
    setTaskId(null)
    setImportProgress(null)
    setError(null)
    setSuccess(null)
  }

  const getStageLabel = (stage: string) => {
    const labels: Record<string, string> = {
      upload: '文件上传',
      preprocess: '文本预处理',
      parse: '章节解析',
      store: '数据存储',
    }
    return labels[stage] || stage
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">导入文本 (异步)</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>异步导入文本</DialogTitle>
          <DialogDescription>
            支持大文件和AI智能章节解析，导入过程在后台进行
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* 文件选择 */}
          <div className="grid gap-2">
            <Label htmlFor="file">选择文件</Label>
            <Input
              id="file"
              type="file"
              accept=".txt,.md,.text"
              onChange={handleFileChange}
              disabled={uploading || creating}
            />
            {file && (
              <p className="text-sm text-muted-foreground">
                已选择: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          {/* 上传进度 */}
          {uploading && (
            <div className="grid gap-2">
              <Label>上传进度</Label>
              <Progress value={uploadProgress} />
              <p className="text-sm text-muted-foreground">{uploadProgress}%</p>
            </div>
          )}

          {/* 作品信息 */}
          {fileId && (
            <>
              <div className="grid gap-2">
                <Label htmlFor="title">作品标题 *</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="输入作品标题"
                  disabled={creating}
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="author">作者</Label>
                <Input
                  id="author"
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  placeholder="输入作者名（可选）"
                  disabled={creating}
                />
              </div>

              {/* AI 解析开关 */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="ai-parse">AI 智能章节解析</Label>
                  <p className="text-xs text-muted-foreground">
                    自动识别楔子、番外等特殊章节
                  </p>
                </div>
                <Switch
                  id="ai-parse"
                  checked={enableAi}
                  onCheckedChange={setEnableAi}
                  disabled={creating}
                />
              </div>
            </>
          )}

          {/* 导入进度 */}
          {importProgress && (
            <div className="grid gap-2">
              <Label>导入进度</Label>
              <Progress value={importProgress.overall_progress} />
              <div className="text-sm text-muted-foreground">
                <p>阶段: {getStageLabel(importProgress.stage)}</p>
                <p>{importProgress.message}</p>
                {importProgress.chapters_found > 0 && (
                  <p>
                    章节: {importProgress.chapters_processed} / {importProgress.chapters_found}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* 错误/成功消息 */}
          {error && (
            <div className="text-sm text-red-500">{error}</div>
          )}
          {success && (
            <div className="text-sm text-green-500">{success}</div>
          )}
        </div>

        <DialogFooter>
          {!fileId ? (
            <Button
              onClick={handleUpload}
              disabled={!file || uploading}
            >
              {uploading ? '上传中...' : '上传文件'}
            </Button>
          ) : (
            <Button
              onClick={handleCreateTask}
              disabled={creating}
            >
              {creating ? '创建任务...' : '创建导入任务'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
