/**
 * @file file_storage.tsx
 * @brief File Storage Page
 * @author sailing-innocent
 * @date 2026-03-14
 */

import { useState, useRef, useCallback } from 'react'
import PageLayout from '@components/page_layout'
import { Button } from '@components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Alert, AlertDescription } from '@components/ui/alert'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@components/ui/table'
import { Upload, Download, Trash2, FileText, RefreshCw, Eye } from 'lucide-react'
import type { FileInfo } from '@lib/data/file_storage'
import {
  api_upload_file,
  api_list_files,
  api_delete_file,
  api_download_file,
  api_get_file_content,
} from '@lib/api/file_storage'

const MAX_FILE_SIZE = 10485760 // 10MB

export default function FileStoragePage() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<FileInfo | null>(null)
  const [previewContent, setPreviewContent] = useState<string>('')
  const [isPreviewOpen, setIsPreviewOpen] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 加载文件列表
  const loadFiles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api_list_files()
      setFiles(response.files)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // 处理文件上传
  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      setError(`文件大小超过限制，最大允许 ${MAX_FILE_SIZE} 字节`)
      return
    }

    setLoading(true)
    setError(null)

    try {
      await api_upload_file(file)
      await loadFiles()
      // 重置文件输入
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理文件删除
  const handleDelete = async (filename: string, originalName: string) => {
    if (!confirm(`确定要删除文件 "${originalName}" 吗？`)) {
      return
    }

    setLoading(true)
    setError(null)

    try {
      await api_delete_file(filename)
      await loadFiles()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理文件下载
  const handleDownload = (filename: string) => {
    api_download_file(filename)
  }

  // 预览文件
  const handlePreview = async (file: FileInfo) => {
    setSelectedFile(file)
    setLoading(true)
    try {
      const response = await api_get_file_content(file.filename)
      setPreviewContent(response.content)
      setIsPreviewOpen(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '预览失败')
    } finally {
      setLoading(false)
    }
  }

  // 格式化文件大小
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(2)} KB`
  }

  // 格式化日期
  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('zh-CN')
  }

  return (
    <PageLayout>
      <div className="container mx-auto p-4 space-y-6">
        {/* 标题和上传按钮 */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">文件存储</h1>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadFiles}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
            >
              <Upload className="w-4 h-4 mr-2" />
              上传文件
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,text/plain"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
        </div>

        {/* 说明 */}
        <Alert>
          <AlertDescription>
            支持上传文本文件（.txt），单个文件大小限制为 {MAX_FILE_SIZE} 字节（10MB）。上传后可以在此页面预览、下载或删除文件。
          </AlertDescription>
        </Alert>

        {/* 错误提示 */}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* 文件列表 */}
        <Card>
          <CardHeader>
            <CardTitle>文件列表 ({files.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {files.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>暂无文件，请点击"上传文件"按钮添加</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>文件名</TableHead>
                    <TableHead>大小</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {files.map((file) => (
                    <TableRow key={file.filename}>
                      <TableCell>
                        <div className="font-medium">{file.original_name}</div>
                        <div className="text-xs text-gray-500 font-mono">{file.filename}</div>
                      </TableCell>
                      <TableCell>{formatSize(file.size)}</TableCell>
                      <TableCell>{formatDate(file.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handlePreview(file)}
                            disabled={loading}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownload(file.filename)}
                          >
                            <Download className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(file.filename, file.original_name)}
                            disabled={loading}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 预览对话框 */}
      <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>
              文件预览: {selectedFile?.original_name}
            </DialogTitle>
            <div className="text-xs text-gray-500 font-mono">
              {selectedFile?.filename}
            </div>
          </DialogHeader>
          <div className="mt-4">
            <div className="bg-gray-50 p-4 rounded-md overflow-auto max-h-[60vh]">
              <pre className="text-sm whitespace-pre-wrap font-mono">
                {previewContent || '(空文件)'}
              </pre>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setIsPreviewOpen(false)}
              >
                关闭
              </Button>
              {selectedFile && (
                <Button
                  onClick={() => {
                    handleDownload(selectedFile.filename)
                    setIsPreviewOpen(false)
                  }}
                >
                  <Download className="w-4 h-4 mr-2" />
                  下载
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  )
}
