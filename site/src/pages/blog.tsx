/**
 * @file blog.tsx
 * @brief Blog Review Page - Markdown report list & GitHub-flavored rendering
 * @author sailing-innocent
 * @date 2026-05-05
 *
 * 使用场景：agent 在开发机/服务器上产出 Markdown 报告后通过 API 上传，
 * 用户在手机/桌面浏览器打开预览地址（/blog?content=<filename>）审阅，
 * 可下载留档或直接删除不保留。
 */

import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageLayout from '@components/page_layout'
import { Button } from '@components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Alert, AlertDescription } from '@components/ui/alert'
import { useIsMobile } from '@/hooks/use-mobile'
import {
  Upload,
  Download,
  Trash2,
  RefreshCw,
  ArrowLeft,
  FileText,
  BookOpen,
} from 'lucide-react'
import type { BlogArticleInfo } from '@lib/data/blog'
import {
  api_upload_article,
  api_list_articles,
  api_delete_article,
  api_download_article,
  api_get_article_content,
} from '@lib/api/blog'
import { renderMarkdown } from '@lib/utils/markdown'
import './blog.css'

const MAX_FILE_SIZE = 10485760 // 10MB

interface SelectedArticle {
  info: BlogArticleInfo
  content: string
}

export default function BlogPage() {
  const isMobile = useIsMobile()
  const [searchParams, setSearchParams] = useSearchParams()

  const [articles, setArticles] = useState<BlogArticleInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<SelectedArticle | null>(null)
  const [contentLoading, setContentLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 加载文章列表
  const loadArticles = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api_list_articles()
      setArticles(response.articles)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  // 选中并加载单篇文章
  const selectArticle = useCallback(
    async (info: BlogArticleInfo, updateUrl = true) => {
      setContentLoading(true)
      setError(null)
      try {
        const response = await api_get_article_content(info.filename)
        setSelected({ info, content: response.content })
        if (updateUrl) {
          setSearchParams({ content: info.filename }, { replace: true })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载文章失败')
        setSelected(null)
      } finally {
        setContentLoading(false)
      }
    },
    [setSearchParams]
  )

  // 返回列表（清除选中与 URL 参数）
  const clearSelection = useCallback(() => {
    setSelected(null)
    setSearchParams({}, { replace: true })
  }, [setSearchParams])

  // 初始加载 + 处理 /blog?content=<filename> 预览地址
  useEffect(() => {
    loadArticles()
  }, [loadArticles])

  useEffect(() => {
    const contentParam = searchParams.get('content')
    if (!contentParam || articles.length === 0) return
    const target = articles.find((a) => a.filename === contentParam)
    if (target && selected?.info.filename !== target.filename) {
      selectArticle(target, false)
    }
  }, [searchParams, articles, selected, selectArticle])

  // 上传
  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (file.size > MAX_FILE_SIZE) {
      setError(`文件大小超过限制，最大允许 ${MAX_FILE_SIZE} 字节`)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const uploaded = await api_upload_article(file)
      await loadArticles()
      // 上传后直接打开新文章
      const info: BlogArticleInfo = {
        filename: uploaded.filename,
        original_name: uploaded.original_name,
        title: uploaded.title,
        size: uploaded.size,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      await selectArticle(info)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
    } finally {
      setLoading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // 删除
  const handleDelete = async (info: BlogArticleInfo) => {
    if (!confirm(`确定要删除文章 "${info.title}" 吗？删除后不可恢复。`)) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      await api_delete_article(info.filename)
      if (selected?.info.filename === info.filename) {
        setSelected(null)
        setSearchParams({}, { replace: true })
      }
      await loadArticles()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setLoading(false)
    }
  }

  // 下载
  const handleDownload = (filename: string) => {
    api_download_article(filename)
  }

  // 渲染后的 HTML（memo，避免每次 render 重新渲染 Markdown）
  const renderedHtml = useMemo(
    () => (selected ? renderMarkdown(selected.content) : ''),
    [selected]
  )

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(2)} KB`
  }

  const formatDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleString('zh-CN')
    } catch {
      return isoString
    }
  }

  // ---------------- 文章列表 ----------------
  const articleList = (
    <Card className="h-fit">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-lg">
          <span className="flex items-center gap-2">
            <BookOpen className="w-5 h-5" />
            文章列表 ({articles.length})
          </span>
          <Button variant="outline" size="sm" onClick={loadArticles} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {articles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>暂无文章，请点击上传按钮添加</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {articles.map((article) => {
              const isActive = selected?.info.filename === article.filename
              return (
                <li key={article.filename}>
                  <button
                    type="button"
                    onClick={() => selectArticle(article)}
                    className={`w-full text-left px-3 py-2 rounded-md border transition-colors ${
                      isActive
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-transparent hover:bg-gray-100'
                    }`}
                  >
                    <div className="font-medium truncate">{article.title}</div>
                    <div className="text-xs text-gray-500 truncate">
                      {article.original_name} · {formatSize(article.size)}
                    </div>
                    <div className="text-xs text-gray-400">
                      {formatDate(article.created_at)}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )

  // ---------------- 文章详情 ----------------
  const articleDetail = selected ? (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-xl break-words">{selected.info.title}</CardTitle>
            <div className="text-xs text-gray-500 mt-1">
              {selected.info.original_name} · {formatSize(selected.info.size)} ·{' '}
              {formatDate(selected.info.created_at)}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDownload(selected.info.filename)}
              title="下载 Markdown"
            >
              <Download className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDelete(selected.info)}
              disabled={loading}
              title="删除文章"
              className="text-red-600 hover:text-red-700"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {contentLoading ? (
          <div className="py-12 text-center text-gray-500">加载中...</div>
        ) : (
          <article
            className="markdown-body p-4 sm:p-6 rounded-md border border-gray-200"
            dangerouslySetInnerHTML={{ __html: renderedHtml }}
          />
        )}
      </CardContent>
    </Card>
  ) : (
    <Card className="h-full min-h-[300px]">
      <CardContent>
        <div className="py-16 text-center text-gray-400">
          <BookOpen className="w-16 h-16 mx-auto mb-4 opacity-40" />
          <p>从左侧选择一篇文章开始审阅</p>
        </div>
      </CardContent>
    </Card>
  )

  // ---------------- 页面 ----------------
  return (
    <PageLayout>
      <div className="container mx-auto p-4 space-y-4">
        {/* 标题栏 */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">博客审阅</h1>
          <div className="flex items-center gap-2">
            {isMobile && selected && (
              <Button variant="outline" size="sm" onClick={clearSelection}>
                <ArrowLeft className="w-4 h-4 mr-1" />
                列表
              </Button>
            )}
            <Button onClick={() => fileInputRef.current?.click()} disabled={loading}>
              <Upload className="w-4 h-4 mr-2" />
              上传 Markdown
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>
        </div>

        {/* 说明 */}
        <Alert>
          <AlertDescription>
            上传 Markdown 报告后可直接审阅渲染结果；支持下载留档，审阅完毕可一键删除不保留。
            Agent 可通过 API 上传并获取预览地址。
          </AlertDescription>
        </Alert>

        {/* 错误提示 */}
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* 内容区：移动端列表/详情切换，桌面端并排 */}
        {isMobile ? (
          selected ? (
            articleDetail
          ) : (
            articleList
          )
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
            <div className="lg:col-span-1">{articleList}</div>
            <div className="lg:col-span-2">{articleDetail}</div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
