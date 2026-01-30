/**
 * @file chapter_reader.tsx
 * @brief Chapter Reader/Editor Component
 * @author sailing-innocent
 * @date 2025-01-29
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  api_get_chapter_list,
  api_get_chapter_content,
  api_update_node,
  api_get_edition,
} from '@lib/api/text'
import type { Work, Edition, ChapterListItem, DocumentNode, ChapterInsertResponse } from '@lib/data/text'
import { formatCharCount } from '@lib/data/text'
import ChapterInsertDialog from './chapter_insert_dialog'

interface ChapterReaderProps {
  work: Work
  onBack?: () => void
}

export default function ChapterReader({ work, onBack }: ChapterReaderProps) {
  const [edition, setEdition] = useState<Edition | null>(null)
  const [chapters, setChapters] = useState<ChapterListItem[]>([])
  const [currentChapter, setCurrentChapter] = useState<DocumentNode | null>(null)
  const [currentIndex, setCurrentIndex] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [contentLoading, setContentLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [isMobileTocOpen, setIsMobileTocOpen] = useState(false)

  // 加载版本和章节列表
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        // 获取第一个版本
        const { api_get_editions_by_work } = await import('@lib/api/text')
        const editions = await api_get_editions_by_work(work.id)
        if (editions.length === 0) {
          setError('该作品没有可用版本')
          return
        }

        const ed = editions[0]
        setEdition(ed)

        // 获取章节列表
        const chapterList = await api_get_chapter_list(ed.id)
        setChapters(chapterList)
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [work.id])

  // 加载章节内容
  const loadChapter = async (index: number) => {
    if (!edition) return

    setContentLoading(true)
    setError(null)
    setIsEditing(false)
    try {
      const chapter = await api_get_chapter_content(edition.id, index)
      setCurrentChapter(chapter)
      setCurrentIndex(index)
      setEditTitle(chapter.title || '')
      setEditContent(chapter.raw_text || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载章节失败')
    } finally {
      setContentLoading(false)
    }
  }

  // 保存编辑
  const handleSave = async () => {
    if (!currentChapter) return

    try {
      const updated = await api_update_node(currentChapter.id, {
        title: editTitle,
        raw_text: editContent,
      })
      setCurrentChapter(updated)
      setIsEditing(false)

      // 更新章节列表中的标题
      setChapters(
        chapters.map((ch) =>
          ch.id === currentChapter.id ? { ...ch, title: editTitle, char_count: editContent.length } : ch
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  // 导航
  const goToPrev = () => {
    if (currentIndex !== null && currentIndex > 0) {
      loadChapter(currentIndex - 1)
    }
  }

  const goToNext = () => {
    if (currentIndex !== null && currentIndex < chapters.length - 1) {
      loadChapter(currentIndex + 1)
    }
  }

  // 插入章节成功后刷新列表
  const handleInsertSuccess = async (response: ChapterInsertResponse) => {
    if (!edition) return

    try {
      // 重新加载章节列表
      const chapterList = await api_get_chapter_list(edition.id)
      setChapters(chapterList)

      // 如果当前有选中的章节，需要更新索引
      if (currentIndex !== null && response.chapter.sort_index <= currentIndex) {
        setCurrentIndex(currentIndex + 1)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '刷新章节列表失败')
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  // 移动端目录选择处理
  const handleMobileChapterSelect = (index: number) => {
    loadChapter(index)
    setIsMobileTocOpen(false)
  }

  // 目录列表组件（复用）
  const ChapterList = ({ onSelect }: { onSelect?: (idx: number) => void }) => (
    <ul className="divide-y">
      {chapters.map((chapter, idx) => (
        <li
          key={chapter.id}
          className={`px-4 py-2 cursor-pointer hover:bg-muted transition-colors ${
            currentIndex === idx ? 'bg-muted font-medium' : ''
          }`}
          onClick={() => (onSelect ? onSelect(idx) : loadChapter(idx))}
        >
          <div className="text-sm truncate">
            {chapter.label}
            {chapter.title && ` ${chapter.title}`}
          </div>
          {chapter.char_count && (
            <div className="text-xs text-muted-foreground">{formatCharCount(chapter.char_count)}</div>
          )}
        </li>
      ))}
    </ul>
  )

  return (
    <div className="space-y-4">
      {/* 顶部导航 */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 md:gap-4">
          <Button variant="outline" size="sm" onClick={onBack}>
            返回
          </Button>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg md:text-xl font-bold truncate">{work.title}</h2>
            {work.author && (
              <p className="text-xs md:text-sm text-muted-foreground truncate">作者：{work.author}</p>
            )}
          </div>
        </div>
        <div className="flex items-center justify-between md:justify-end gap-2">
          {edition && (
            <div className="text-xs md:text-sm text-muted-foreground">
              {chapters.length} 章 · {formatCharCount(edition.char_count || 0)}
            </div>
          )}
          {/* 移动端目录按钮 */}
          <Sheet open={isMobileTocOpen} onOpenChange={setIsMobileTocOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm" className="md:hidden">
                目录
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[280px] p-0">
              <SheetHeader className="p-4 border-b">
                <SheetTitle className="flex items-center justify-between">
                  <span>目录</span>
                  {edition && (
                    <ChapterInsertDialog
                      editionId={edition.id}
                      chapters={chapters}
                      onInsertSuccess={handleInsertSuccess}
                    />
                  )}
                </SheetTitle>
              </SheetHeader>
              <div className="overflow-y-auto max-h-[calc(100vh-80px)]">
                <ChapterList onSelect={handleMobileChapterSelect} />
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 章节目录 - 仅桌面端显示 */}
        <Card className="hidden md:block md:col-span-1 max-h-[70vh] overflow-y-auto">
          <CardHeader className="py-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">目录</CardTitle>
              {edition && (
                <ChapterInsertDialog
                  editionId={edition.id}
                  chapters={chapters}
                  onInsertSuccess={handleInsertSuccess}
                />
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <ChapterList />
          </CardContent>
        </Card>

        {/* 章节内容 */}
        <Card className="md:col-span-3">
          <CardHeader className="py-2 md:py-3">
            {/* 移动端章节快速选择 */}
            {chapters.length > 0 && (
              <div className="md:hidden mb-2">
                <Select
                  value={currentIndex?.toString() ?? ''}
                  onValueChange={(val) => loadChapter(parseInt(val))}
                >
                  <SelectTrigger className="w-full text-sm">
                    <SelectValue placeholder="选择章节..." />
                  </SelectTrigger>
                  <SelectContent>
                    {chapters.map((chapter, idx) => (
                      <SelectItem key={chapter.id} value={idx.toString()}>
                        {chapter.label}
                        {chapter.title && ` ${chapter.title}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* 章节标题 */}
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <CardTitle className="text-sm md:text-base flex-1 min-w-0">
                {currentChapter ? (
                  isEditing ? (
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full md:w-64"
                      placeholder="章节标题"
                    />
                  ) : (
                    <span className="truncate block">
                      {currentChapter.label}
                      {currentChapter.title && ` ${currentChapter.title}`}
                    </span>
                  )
                ) : (
                  <span className="hidden md:inline">请选择章节</span>
                )}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="px-3 md:px-6">
            {contentLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : currentChapter ? (
              <>
                {isEditing ? (
                  <textarea
                    className="w-full min-h-[50vh] md:min-h-[400px] p-3 md:p-4 border rounded-md font-mono text-sm"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                ) : (
                  <div className="prose prose-sm max-w-none max-h-[60vh] overflow-y-auto">
                    <div className="whitespace-pre-wrap leading-relaxed text-sm md:text-base">
                      {currentChapter.raw_text}
                    </div>
                  </div>
                )}

                {/* 底部操作栏 */}
                <div className="flex justify-between items-center mt-4 pt-4 border-t">
                  {isEditing ? (
                    <>
                      <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
                        取消
                      </Button>
                      <span className="text-xs md:text-sm text-muted-foreground">
                        {editContent.length.toLocaleString()} 字符
                      </span>
                      <Button size="sm" onClick={handleSave}>
                        保存
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" onClick={goToPrev} disabled={currentIndex === 0}>
                        上一章
                      </Button>
                      <div className="flex items-center gap-2">
                        <span className="text-xs md:text-sm text-muted-foreground">
                          {currentIndex !== null ? `${currentIndex + 1} / ${chapters.length}` : ''}
                        </span>
                        <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                          编辑
                        </Button>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={goToNext}
                        disabled={currentIndex === chapters.length - 1}
                      >
                        下一章
                      </Button>
                    </>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-8 md:py-16 text-muted-foreground text-sm">
                <span className="hidden md:inline">点击左侧目录选择章节开始阅读</span>
                <span className="md:hidden">点击上方目录或下拉选择章节</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
