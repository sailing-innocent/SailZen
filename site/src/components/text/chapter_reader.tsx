/**
 * @file chapter_reader.tsx
 * @brief Content 2.0 Volume-Aware Cloud-Synced Reader (Collapsible Volumes, Cloud Progress, Auto-Volume, PDF Side-View)
 * @author sailing-innocent
 * @date 2026-11-26
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  FolderTree,
  Wand2,
} from 'lucide-react'
import {
  api_auto_volume_edition,
  api_get_chapter_content,
  api_get_chapter_list,
  api_get_edition_toc,
  api_get_editions_by_work,
  api_get_reading_progress,
  api_list_assets,
  api_record_reading_session,
  api_update_node,
  api_upsert_reading_progress,
  getAssetFileUrl,
} from '@lib/api/text'
import { formatCharCount, getPillarLabel } from '@lib/data/text'
import type {
  ChapterListItem,
  ContentAsset,
  DocumentNode,
  Edition,
  EditionToc,
  TocChapterItem,
  Work,
} from '@lib/data/text'

interface ChapterReaderProps {
  work: Work
  onBack?: () => void
}

export default function ChapterReader({ work, onBack }: ChapterReaderProps) {
  const [edition, setEdition] = useState<Edition | null>(null)
  const [chapters, setChapters] = useState<ChapterListItem[]>([])
  const [toc, setToc] = useState<EditionToc | null>(null)
  const [expandedVols, setExpandedVols] = useState<Record<number, boolean>>({})
  const [assets, setAssets] = useState<ContentAsset[]>([])
  const [showPdfPreview, setShowPdfPreview] = useState(false)

  const [currentChapter, setCurrentChapter] = useState<DocumentNode | null>(null)
  const [currentIndex, setCurrentIndex] = useState<number | null>(null)
  const [progressPct, setProgressPct] = useState<number>(work.progress?.progress_pct ?? 0)
  const [loading, setLoading] = useState(true)
  const [contentLoading, setContentLoading] = useState(false)
  const [autoVolBusy, setAutoVolBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [isEditing, setIsEditing] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [isMobileTocOpen, setIsMobileTocOpen] = useState(false)

  const sessionStartRef = useRef<number>(Date.now())
  const startNodeIdRef = useRef<number | undefined>(undefined)
  const latestNodeIdRef = useRef<number | undefined>(undefined)
  const editionIdRef = useRef<number | undefined>(undefined)

  const pdfAsset = assets.find((a) => a.asset_kind === 'pdf_source' || a.mime_type === 'application/pdf')

  const loadChapter = useCallback(
    async (
      edId: number,
      chapterList: ChapterListItem[],
      arrayIndex: number,
      syncToCloud = true
    ) => {
      const chapterItem = chapterList[arrayIndex]
      if (!chapterItem) return
      setContentLoading(true)
      setError(null)
      setIsEditing(false)
      try {
        const chapter = await api_get_chapter_content(edId, chapterItem.sort_index)
        setCurrentChapter(chapter)
        setCurrentIndex(arrayIndex)
        setEditTitle(chapter.title || '')
        setEditContent(chapter.raw_text || '')
        if (!startNodeIdRef.current) startNodeIdRef.current = chapter.id
        latestNodeIdRef.current = chapter.id

        if (chapterItem.parent_id) {
          setExpandedVols((prev) => ({ ...prev, [chapterItem.parent_id!]: true }))
        }
        if (syncToCloud) {
          const saved = await api_upsert_reading_progress(work.id, {
            edition_id: edId,
            node_id: chapter.id,
            sort_index: chapterItem.sort_index,
            client_device: 'web',
          }).catch(() => null)
          if (saved) setProgressPct(saved.progress_pct)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载章节失败')
      } finally {
        setContentLoading(false)
      }
    },
    [work.id]
  )

  // 初始化加载版本、分卷目录、附件及云端续读进度
  useEffect(() => {
    let active = true
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      sessionStartRef.current = Date.now()
      try {
        const [editions, assetList, cloudProgress] = await Promise.all([
          api_get_editions_by_work(work.id),
          api_list_assets({ work_id: work.id }).catch(() => []),
          api_get_reading_progress(work.id).catch(() => null),
        ])
        if (!active) return
        setAssets(assetList)
        if (editions.length === 0) {
          setError('该作品没有可用版本')
          return
        }
        const ed =
          (cloudProgress && editions.find((e) => e.id === cloudProgress.edition_id)) ||
          editions[0]
        setEdition(ed)
        editionIdRef.current = ed.id

        const [chapterList, tocData] = await Promise.all([
          api_get_chapter_list(ed.id),
          api_get_edition_toc(ed.id).catch(() => null),
        ])
        if (!active) return
        setChapters(chapterList)
        setToc(tocData)

        // 默认展开第一卷或进度所在卷
        if (tocData && tocData.volumes.length > 0) {
          const initExpanded: Record<number, boolean> = {}
          initExpanded[tocData.volumes[0].id] = true
          setExpandedVols(initExpanded)
        }

        if (chapterList.length > 0) {
          let targetIdx = 0
          if (cloudProgress) {
            setProgressPct(cloudProgress.progress_pct)
            const foundIdx = chapterList.findIndex(
              (c) =>
                (cloudProgress.node_id && c.id === cloudProgress.node_id) ||
                c.sort_index === cloudProgress.sort_index
            )
            if (foundIdx >= 0) targetIdx = foundIdx
          }
          await loadChapter(ed.id, chapterList, targetIdx, false)
        }
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : '加载失败')
      } finally {
        if (active) setLoading(false)
      }
    }

    fetchData()
    return () => {
      active = false
      const elapsedSec = Math.floor((Date.now() - sessionStartRef.current) / 1000)
      if (elapsedSec >= 15 && editionIdRef.current) {
        api_record_reading_session({
          work_id: work.id,
          edition_id: editionIdRef.current,
          start_node_id: startNodeIdRef.current,
          end_node_id: latestNodeIdRef.current,
          duration_sec: elapsedSec,
          source_client: 'web',
        }).catch(() => {})
      }
    }
  }, [work.id, loadChapter])

  const handleSave = async () => {
    if (!currentChapter) return
    try {
      const updated = await api_update_node(currentChapter.id, {
        title: editTitle,
        raw_text: editContent,
      })
      setCurrentChapter(updated)
      setIsEditing(false)
      setChapters((prev) =>
        prev.map((ch) =>
          ch.id === currentChapter.id
            ? { ...ch, title: editTitle, char_count: editContent.length }
            : ch
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败')
    }
  }

  const handleAutoVolume = async () => {
    if (!edition) return
    setAutoVolBusy(true)
    setError(null)
    try {
      const preview = await api_auto_volume_edition(edition.id, true)
      if (preview.volumes.length === 0) {
        alert('未检测到可分卷章节。')
        return
      }
      const summary = preview.volumes
        .slice(0, 8)
        .map((v) => `• ${v.label} ${v.title} (${v.chapter_count} 章)`)
        .join('\n')
      const ok = confirm(
        `自动分卷预览（策略: ${preview.strategy}，共 ${preview.volumes.length} 卷）：\n\n${summary}${
          preview.volumes.length > 8 ? `\n... 等共 ${preview.volumes.length} 卷` : ''
        }\n\n确认应用该分卷结构吗？（不删除任何正文）`
      )
      if (!ok) return
      await api_auto_volume_edition(edition.id, false)
      const [nextChapters, nextToc] = await Promise.all([
        api_get_chapter_list(edition.id),
        api_get_edition_toc(edition.id),
      ])
      setChapters(nextChapters)
      setToc(nextToc)
      if (nextToc.volumes.length > 0) {
        setExpandedVols({ [nextToc.volumes[0].id]: true })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '自动分卷失败')
    } finally {
      setAutoVolBusy(false)
    }
  }

  const selectChapterById = (ch: TocChapterItem | ChapterListItem, closeMobile = false) => {
    if (!edition) return
    const idx = chapters.findIndex((c) => c.id === ch.id)
    if (idx >= 0) {
      loadChapter(edition.id, chapters, idx, true)
      if (closeMobile) setIsMobileTocOpen(false)
    }
  }

  const goToPrev = () => {
    if (edition && currentIndex !== null && currentIndex > 0) {
      loadChapter(edition.id, chapters, currentIndex - 1, true)
    }
  }

  const goToNext = () => {
    if (edition && currentIndex !== null && currentIndex < chapters.length - 1) {
      loadChapter(edition.id, chapters, currentIndex + 1, true)
    }
  }

  const renderTocTree = (closeMobile = false) => {
    const hasVolumes = toc && toc.volumes.length > 0
    if (!hasVolumes) {
      return (
        <ul className="divide-y">
          {chapters.map((chapter, arrayIdx) => (
            <li
              key={chapter.id}
              className={`px-3 py-2 cursor-pointer hover:bg-muted transition-colors ${
                currentIndex === arrayIdx ? 'bg-muted font-medium' : ''
              }`}
              onClick={() => selectChapterById(chapter, closeMobile)}
            >
              <div className="text-xs md:text-sm truncate">
                {chapter.label}
                {chapter.title && ` ${chapter.title}`}
              </div>
              {chapter.char_count ? (
                <div className="text-[11px] text-muted-foreground">
                  {formatCharCount(chapter.char_count)}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )
    }

    return (
      <div className="divide-y">
        {toc.volumes.map((vol) => {
          const isOpen = !!expandedVols[vol.id]
          return (
            <div key={vol.id}>
              <button
                type="button"
                className="w-full px-3 py-2 flex items-center justify-between text-left bg-muted/40 hover:bg-muted transition-colors"
                onClick={() =>
                  setExpandedVols((prev) => ({ ...prev, [vol.id]: !prev[vol.id] }))
                }
              >
                <div className="min-w-0 pr-2">
                  <div className="text-xs font-semibold truncate">
                    {vol.label ? `${vol.label} ` : ''}
                    {vol.title}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {vol.chapter_count} 章 · {formatCharCount(vol.total_chars)}
                  </div>
                </div>
                {isOpen ? (
                  <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground" />
                )}
              </button>
              {isOpen && (
                <ul className="divide-y border-t">
                  {vol.chapters.map((ch) => {
                    const isCurrent = currentChapter?.id === ch.id
                    return (
                      <li
                        key={ch.id}
                        className={`pl-5 pr-3 py-1.5 cursor-pointer hover:bg-muted transition-colors ${
                          isCurrent ? 'bg-primary/10 font-medium text-primary' : ''
                        }`}
                        onClick={() => selectChapterById(ch, closeMobile)}
                      >
                        <div className="text-xs truncate">
                          {ch.label}
                          {ch.title && ` ${ch.title}`}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )
        })}

        {toc.ungrouped_chapters.length > 0 && (
          <div>
            <div className="px-3 py-1.5 text-[11px] font-medium text-muted-foreground bg-muted/20">
              未分卷章节 ({toc.ungrouped_chapters.length})
            </div>
            <ul className="divide-y">
              {toc.ungrouped_chapters.map((ch) => (
                <li
                  key={ch.id}
                  className={`px-3 py-1.5 cursor-pointer hover:bg-muted text-xs truncate ${
                    currentChapter?.id === ch.id ? 'bg-primary/10 font-medium' : ''
                  }`}
                  onClick={() => selectChapterById(ch, closeMobile)}
                >
                  {ch.label} {ch.title}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 顶部导航与动作栏 */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <Button variant="outline" size="sm" onClick={onBack}>
            返回书架
          </Button>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-base md:text-xl font-bold truncate">{work.title}</h2>
              <Badge variant="outline" className="text-[11px] shrink-0">
                {getPillarLabel(work.pillar || 'fiction')}
              </Badge>
              <Badge variant="secondary" className="text-[11px] shrink-0">
                {Math.round(progressPct)}%
              </Badge>
            </div>
            {work.author && (
              <p className="text-xs text-muted-foreground truncate">作者：{work.author}</p>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {edition && chapters.length >= 2 && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleAutoVolume}
              disabled={autoVolBusy}
              title="识别卷名或按章数自动整理分卷树"
            >
              <Wand2 className="w-3.5 h-3.5 mr-1" />
              {autoVolBusy ? '分卷中...' : '自动分卷'}
            </Button>
          )}
          {pdfAsset && (
            <>
              <Button
                variant={showPdfPreview ? 'default' : 'outline'}
                size="sm"
                onClick={() => setShowPdfPreview((v) => !v)}
              >
                <FileText className="w-3.5 h-3.5 mr-1" />
                {showPdfPreview ? '收起原 PDF' : '对照原 PDF'}
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <a href={getAssetFileUrl(pdfAsset)} target="_blank" rel="noreferrer">
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </Button>
            </>
          )}

          {/* 移动端目录抽屉 */}
          <Sheet open={isMobileTocOpen} onOpenChange={setIsMobileTocOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm" className="md:hidden">
                <FolderTree className="w-4 h-4 mr-1" />
                目录
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[290px] p-0">
              <SheetHeader className="p-4 border-b">
                <SheetTitle>
                  目录（{toc && toc.volume_count > 0 ? `${toc.volume_count} 卷 / ` : ''}
                  {chapters.length} 章）
                </SheetTitle>
              </SheetHeader>
              <div className="overflow-y-auto max-h-[calc(100vh-80px)]">{renderTocTree(true)}</div>
            </SheetContent>
          </Sheet>
        </div>
      </div>

      {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

      <div className={`grid grid-cols-1 gap-4 ${showPdfPreview && pdfAsset ? 'md:grid-cols-12' : 'md:grid-cols-4'}`}>
        {/* 分卷目录树（桌面端） */}
        <Card
          className={`hidden md:block max-h-[74vh] overflow-y-auto ${
            showPdfPreview && pdfAsset ? 'md:col-span-3' : 'md:col-span-1'
          }`}
        >
          <CardHeader className="py-2.5 px-3 border-b">
            <CardTitle className="text-sm flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <FolderTree className="w-4 h-4" /> 目录
              </span>
              <span className="text-xs font-normal text-muted-foreground">
                {toc && toc.volume_count > 0 ? `${toc.volume_count}卷 · ` : ''}
                {chapters.length}章
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">{loading ? <Skeleton className="h-40 m-3" /> : renderTocTree(false)}</CardContent>
        </Card>

        {/* 正文阅读区 */}
        <Card className={showPdfPreview && pdfAsset ? 'md:col-span-5' : 'md:col-span-3'}>
          <CardHeader className="py-2.5 border-b">
            {chapters.length > 0 && (
              <div className="md:hidden mb-2">
                <Select
                  value={currentIndex?.toString() ?? ''}
                  onValueChange={(val) => edition && loadChapter(edition.id, chapters, parseInt(val), true)}
                >
                  <SelectTrigger className="w-full text-sm">
                    <SelectValue placeholder="选择章节..." />
                  </SelectTrigger>
                  <SelectContent>
                    {chapters.map((chapter, idx) => (
                      <SelectItem key={chapter.id} value={idx.toString()}>
                        {chapter.volume_title ? `[${chapter.volume_title}] ` : ''}
                        {chapter.label} {chapter.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-sm md:text-base flex-1 min-w-0">
                {currentChapter ? (
                  isEditing ? (
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full"
                    />
                  ) : (
                    <span className="truncate block">
                      {currentChapter.label}
                      {currentChapter.title && ` ${currentChapter.title}`}
                    </span>
                  )
                ) : (
                  <span>请选择章节</span>
                )}
              </CardTitle>
              {edition && (
                <span className="text-xs text-muted-foreground shrink-0">
                  {currentIndex !== null ? `${currentIndex + 1} / ${chapters.length}` : ''}
                </span>
              )}
            </div>
          </CardHeader>

          <CardContent className="px-3 md:px-6 pt-4">
            {contentLoading || loading ? (
              <div className="space-y-2 py-4">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : currentChapter ? (
              <>
                {isEditing ? (
                  <textarea
                    className="w-full min-h-[55vh] p-3 border rounded-md font-mono text-sm"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                ) : (
                  <div className="max-h-[62vh] overflow-y-auto pr-1">
                    <div className="chapter-content-text whitespace-pre-wrap leading-relaxed text-sm md:text-base">
                      {currentChapter.raw_text}
                    </div>
                  </div>
                )}

                <div className="flex justify-between items-center mt-4 pt-3 border-t">
                  {isEditing ? (
                    <>
                      <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
                        取消
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        {editContent.length.toLocaleString()} 字符
                      </span>
                      <Button size="sm" onClick={handleSave}>保存</Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" onClick={goToPrev} disabled={currentIndex === 0}>
                        <ChevronLeft className="w-4 h-4 mr-1" /> 上一章
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                        编辑正文
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={goToNext}
                        disabled={currentIndex === chapters.length - 1}
                      >
                        下一章 <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    </>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground text-sm">
                请选择章节开始阅读
              </div>
            )}
          </CardContent>
        </Card>

        {/* PDF 原件侧栏对照（适用于论文/公式/插图） */}
        {showPdfPreview && pdfAsset && (
          <Card className="md:col-span-4 overflow-hidden flex flex-col max-h-[74vh]">
            <CardHeader className="py-2 px-3 border-b flex-row items-center justify-between">
              <CardTitle className="text-xs truncate">{pdfAsset.original_name}</CardTitle>
              <a
                href={getAssetFileUrl(pdfAsset)}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-primary hover:underline shrink-0"
              >
                新标签打开
              </a>
            </CardHeader>
            <iframe
              title={pdfAsset.original_name}
              src={getAssetFileUrl(pdfAsset)}
              className="w-full flex-1 min-h-[65vh] border-0"
            />
          </Card>
        )}
      </div>
    </div>
  )
}
