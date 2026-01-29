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
  api_get_chapter_list,
  api_get_chapter_content,
  api_update_node,
  api_get_edition,
} from '@lib/api/text'
import type { Work, Edition, ChapterListItem, DocumentNode } from '@lib/data/text'
import { formatCharCount } from '@lib/data/text'

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

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 顶部导航 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={onBack}>
            返回列表
          </Button>
          <div>
            <h2 className="text-xl font-bold">{work.title}</h2>
            {work.author && <p className="text-sm text-muted-foreground">作者：{work.author}</p>}
          </div>
        </div>
        {edition && (
          <div className="text-sm text-muted-foreground">
            {chapters.length} 章 · {formatCharCount(edition.char_count || 0)}
          </div>
        )}
      </div>

      {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* 章节目录 */}
        <Card className="md:col-span-1 max-h-[70vh] overflow-y-auto">
          <CardHeader className="py-3">
            <CardTitle className="text-base">目录</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ul className="divide-y">
              {chapters.map((chapter, idx) => (
                <li
                  key={chapter.id}
                  className={`px-4 py-2 cursor-pointer hover:bg-muted transition-colors ${
                    currentIndex === idx ? 'bg-muted font-medium' : ''
                  }`}
                  onClick={() => loadChapter(idx)}
                >
                  <div className="text-sm truncate">
                    {chapter.label}
                    {chapter.title && ` ${chapter.title}`}
                  </div>
                  {chapter.char_count && (
                    <div className="text-xs text-muted-foreground">
                      {formatCharCount(chapter.char_count)}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* 章节内容 */}
        <Card className="md:col-span-3">
          <CardHeader className="py-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">
                {currentChapter ? (
                  isEditing ? (
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-64"
                      placeholder="章节标题"
                    />
                  ) : (
                    <>
                      {currentChapter.label}
                      {currentChapter.title && ` ${currentChapter.title}`}
                    </>
                  )
                ) : (
                  '请选择章节'
                )}
              </CardTitle>
              {currentChapter && (
                <div className="flex gap-2">
                  {isEditing ? (
                    <>
                      <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>
                        取消
                      </Button>
                      <Button size="sm" onClick={handleSave}>
                        保存
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                      编辑
                    </Button>
                  )}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
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
                    className="w-full min-h-[400px] p-4 border rounded-md font-mono text-sm"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                ) : (
                  <div className="prose prose-sm max-w-none max-h-[60vh] overflow-y-auto">
                    <div className="whitespace-pre-wrap leading-relaxed">
                      {currentChapter.raw_text}
                    </div>
                  </div>
                )}

                {/* 底部导航 */}
                <div className="flex justify-between mt-4 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={goToPrev}
                    disabled={currentIndex === 0}
                  >
                    上一章
                  </Button>
                  <span className="text-sm text-muted-foreground self-center">
                    {currentIndex !== null ? `${currentIndex + 1} / ${chapters.length}` : ''}
                  </span>
                  <Button
                    variant="outline"
                    onClick={goToNext}
                    disabled={currentIndex === chapters.length - 1}
                  >
                    下一章
                  </Button>
                </div>
              </>
            ) : (
              <div className="text-center py-16 text-muted-foreground">
                点击左侧目录选择章节开始阅读
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
