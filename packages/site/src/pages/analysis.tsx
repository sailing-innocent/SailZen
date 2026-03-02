/**
 * @file analysis.tsx
 * @brief Novel Analysis Page - Entry point for outline, character, and setting analysis
 * @author sailing-innocent
 * @date 2025-02-28
 * 
 * 布局说明:
 * - 顶部: 标题栏 + 作品/版本选择器 + 紧凑统计概览
 * - 范围选择区: 共享的章节范围选择器 (所有tab可见)
 * - 主体区域: 标签页内容区
 *   - 任务管理: 任务创建/监控
 *   - 人物管理: 人物列表和分析
 *   - 设定管理: 设定列表和分析
 *   - 大纲分析: 大纲列表、AI提取、树形编辑器
 */

import { useState, useEffect, useMemo } from 'react'
import PageLayout from '@components/page_layout'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { 
  FileText, 
  Users, 
  Settings, 
  BookOpen,
  Layers,
  Target,
  Sparkles,
  Activity,
  AlertCircle,
} from 'lucide-react'

import { api_get_works } from '@lib/api/text'
import { api_get_editions_by_work } from '@lib/api/text'
import { api_get_chapter_list } from '@lib/api/text'
import { useAnalysisStore } from '@lib/store/analysisStore'

import type { Work, Edition, ChapterListItem } from '@lib/data/text'
import type { TextRangeSelection } from '@lib/data/analysis'

// Components
import TextRangeSelector from '@components/text_range_selector'

// Sub-components
import CharacterPanel from '@components/analysis/character_panel'
import SettingPanel from '@components/analysis/setting_panel'
import OutlinePanel from '@components/analysis/outline_panel'
import TaskPanel from '@components/analysis/task_panel'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * 根据 rangeSelection 和 chapters 计算范围显示文本
 */
function getRangeDisplayText(selection: TextRangeSelection | null, chapters: ChapterListItem[]): string {
  if (!selection) return '未选择'

  const getChapterDisplay = (chapter: ChapterListItem | undefined): string => {
    if (!chapter) return ''
    const parts: string[] = []
    if (chapter.label) parts.push(chapter.label)
    if (chapter.title) parts.push(chapter.title)
    return parts.join(' ') || `第 ${chapter.sort_index + 1} 章`
  }

  switch (selection.mode) {
    case 'full_edition':
      return '整部作品'

    case 'single_chapter': {
      if (selection.chapter_index === undefined) return '单章选择'
      const chapter = chapters.find(ch => ch.sort_index === selection.chapter_index)
      return getChapterDisplay(chapter) || `第 ${selection.chapter_index + 1} 章`
    }

    case 'chapter_range': {
      if (selection.start_index === undefined || selection.end_index === undefined) {
        return '章节范围选择'
      }
      const startChapter = chapters.find(ch => ch.sort_index === selection.start_index)
      const endChapter = chapters.find(ch => ch.sort_index === selection.end_index)
      const startText = getChapterDisplay(startChapter) || `第 ${selection.start_index + 1} 章`
      const endText = getChapterDisplay(endChapter) || `第 ${selection.end_index + 1} 章`
      return `${startText} 到 ${endText}`
    }

    case 'multi_chapter': {
      const count = selection.chapter_indices?.length || 0
      return `${count} 个章节`
    }

    case 'current_to_end': {
      if (selection.start_index === undefined) return '从当前到结尾'
      const startChapter = chapters.find(ch => ch.sort_index === selection.start_index)
      const startText = getChapterDisplay(startChapter) || `第 ${selection.start_index + 1} 章`
      return `从 ${startText} 到结尾`
    }

    case 'custom_range':
      return '自定义范围'

    default:
      return ''
  }
}

/**
 * 计算选择范围的统计信息
 */
function calculateRangeStats(selection: TextRangeSelection | null, chapters: ChapterListItem[]) {
  if (!selection || chapters.length === 0) {
    return { chapterCount: 0, totalChars: 0, estimatedTokens: 0 }
  }

  let selectedChapters: ChapterListItem[] = []

  switch (selection.mode) {
    case 'full_edition':
      selectedChapters = chapters
      break
    case 'single_chapter':
      if (selection.chapter_index !== undefined) {
        selectedChapters = chapters.filter(ch => ch.sort_index === selection.chapter_index)
      }
      break
    case 'chapter_range':
      if (selection.start_index !== undefined && selection.end_index !== undefined) {
        selectedChapters = chapters.filter(
          ch => ch.sort_index >= selection.start_index! && ch.sort_index <= selection.end_index!
        )
      }
      break
    case 'multi_chapter':
      if (selection.chapter_indices) {
        selectedChapters = chapters.filter(ch => selection.chapter_indices!.includes(ch.sort_index))
      }
      break
    case 'current_to_end':
      if (selection.start_index !== undefined) {
        selectedChapters = chapters.filter(ch => ch.sort_index >= selection.start_index)
      }
      break
  }

  const chapterCount = selectedChapters.length
  const totalChars = selectedChapters.reduce((sum, ch) => sum + (ch.char_count || 0), 0)
  // 简单估算：中文约 1.5 字符/token
  const estimatedTokens = Math.round(totalChars / 1.5)

  return { chapterCount, totalChars, estimatedTokens }
}

// ============================================================================
// Main Component
// ============================================================================

export default function AnalysisPage() {
  // Local state
  const [works, setWorks] = useState<Work[]>([])
  const [editions, setEditions] = useState<Edition[]>([])
  const [chapters, setChapters] = useState<ChapterListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('tasks')
  const [showRangeSelector, setShowRangeSelector] = useState(false)

  // Global store state
  const {
    selectedWorkId,
    selectedEditionId,
    stats,
    rangeSelection,
    setSelectedWork,
    setSelectedEdition,
    setRangeSelection,
    loadStats,
  } = useAnalysisStore()

  // Load works on mount
  useEffect(() => {
    const fetchWorks = async () => {
      try {
        const data = await api_get_works()
        setWorks(data)
        if (data.length > 0 && !selectedWorkId) {
          setSelectedWork(data[0].id)
        }
      } catch (err) {
        console.error('Failed to load works:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchWorks()
  }, [])

  // Load editions when work changes
  useEffect(() => {
    if (!selectedWorkId) {
      setEditions([])
      setSelectedEdition(null)
      return
    }

    const fetchEditions = async () => {
      try {
        const data = await api_get_editions_by_work(selectedWorkId)
        setEditions(data)
        if (data.length > 0 && !selectedEditionId) {
          setSelectedEdition(data[0].id)
        }
      } catch (err) {
        console.error('Failed to load editions:', err)
      }
    }
    fetchEditions()
  }, [selectedWorkId])

  // Load stats when edition changes
  useEffect(() => {
    if (selectedEditionId) {
      loadStats(selectedEditionId)
    }
  }, [selectedEditionId])

  // Load chapters when edition changes
  useEffect(() => {
    if (!selectedEditionId) {
      setChapters([])
      return
    }

    const fetchChapters = async () => {
      try {
        const data = await api_get_chapter_list(selectedEditionId)
        setChapters(data)
      } catch (err) {
        console.error('Failed to load chapters:', err)
      }
    }
    fetchChapters()
  }, [selectedEditionId])

  // Get selected work and edition
  const selectedWork = works.find(w => w.id === selectedWorkId)
  const selectedEdition = editions.find(e => e.id === selectedEditionId)

  // Calculate range stats
  const rangeStats = useMemo(
    () => calculateRangeStats(rangeSelection, chapters),
    [rangeSelection, chapters]
  )

  // Get selected chapters info for TextRangeSelector
  const selectedChaptersInfo = useMemo(() => {
    if (!rangeSelection) return []
    
    let selectedChapters: ChapterListItem[] = []
    
    switch (rangeSelection.mode) {
      case 'full_edition':
        selectedChapters = chapters
        break
      case 'single_chapter':
        if (rangeSelection.chapter_index !== undefined) {
          selectedChapters = chapters.filter(ch => ch.sort_index === rangeSelection.chapter_index)
        }
        break
      case 'chapter_range':
        if (rangeSelection.start_index !== undefined && rangeSelection.end_index !== undefined) {
          selectedChapters = chapters.filter(
            ch => ch.sort_index >= rangeSelection.start_index! && ch.sort_index <= rangeSelection.end_index!
          )
        }
        break
      case 'multi_chapter':
        if (rangeSelection.chapter_indices) {
          selectedChapters = chapters.filter(ch => rangeSelection.chapter_indices!.includes(ch.sort_index))
        }
        break
      case 'current_to_end':
        if (rangeSelection.start_index !== undefined) {
          selectedChapters = chapters.filter(ch => ch.sort_index >= rangeSelection.start_index)
        }
        break
    }
    
    return selectedChapters.map(ch => ({
      id: ch.id,
      sort_index: ch.sort_index,
      label: ch.label,
      title: ch.title,
      char_count: ch.char_count,
    }))
  }, [rangeSelection, chapters])

  if (loading) {
    return (
      <PageLayout>
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageLayout>
    )
  }

  if (works.length === 0) {
    return (
      <PageLayout>
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <h2 className="text-xl font-semibold mb-2">暂无作品</h2>
          <p className="text-muted-foreground mb-4">请先在「文本管理」中导入作品</p>
          <Button variant="outline" onClick={() => window.location.href = '/text'}>
            前往导入
          </Button>
        </div>
      </PageLayout>
    )
  }

  return (
    <PageLayout>
      <div className="space-y-4 px-2 md:px-0">
        {/* Header: Title + Selectors + Compact Stats */}
        <div className="flex flex-col gap-4">
          {/* Top Row: Title and Selectors */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Target className="w-6 h-6" />
              <h1 className="text-xl md:text-2xl font-bold">作品分析工作台</h1>
            </div>
            
            {/* Work and Edition Selector */}
            <div className="flex flex-wrap gap-2">
              <Select
                value={selectedWorkId?.toString()}
                onValueChange={(value) => setSelectedWork(parseInt(value))}
              >
                <SelectTrigger className="w-48">
                  <BookOpen className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="选择作品" />
                </SelectTrigger>
                <SelectContent>
                  {works.map((work) => (
                    <SelectItem key={work.id} value={work.id.toString()}>
                      {work.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              {editions.length > 0 && (
                <Select
                  value={selectedEditionId?.toString()}
                  onValueChange={(value) => setSelectedEdition(parseInt(value))}
                >
                  <SelectTrigger className="w-40">
                    <FileText className="w-4 h-4 mr-2" />
                    <SelectValue placeholder="选择版本" />
                  </SelectTrigger>
                  <SelectContent>
                    {editions.map((edition) => (
                      <SelectItem key={edition.id} value={edition.id.toString()}>
                        {edition.edition_name || `版本 ${edition.ingest_version}`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>

          {/* Compact Stats Bar */}
          {stats && (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">当前版本统计:</span>
              <Badge variant="secondary" className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                人物 {stats.evidence?.character || 0}
              </Badge>
              <Badge variant="secondary" className="flex items-center gap-1">
                <Settings className="w-3 h-3" />
                设定 {stats.evidence?.setting || 0}
              </Badge>
              <Badge variant="secondary" className="flex items-center gap-1">
                <Layers className="w-3 h-3" />
                大纲节点 {stats.evidence?.outline_node || 0}
              </Badge>
              <Badge variant="secondary" className="flex items-center gap-1">
                <Activity className="w-3 h-3" />
                任务 {Object.values(stats.tasks || {}).reduce((a, b) => a + b, 0)}
              </Badge>
            </div>
          )}
        </div>

        <Separator />

        {/* Main Content */}
        {selectedEdition && (
          <div className="space-y-4">
            {/* Shared Range Selection Summary */}
            <Card className="bg-muted/50">
              <CardContent className="py-3 px-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-muted-foreground" />
                    <div>
                      <span className="text-sm text-muted-foreground">当前分析范围: </span>
                      <span className="text-sm font-medium">
                        {getRangeDisplayText(rangeSelection, chapters)}
                      </span>
                      {rangeStats.chapterCount > 0 && (
                        <span className="text-xs text-muted-foreground ml-2">
                          ({rangeStats.chapterCount} 章, {rangeStats.totalChars.toLocaleString()} 字, 约 {rangeStats.estimatedTokens.toLocaleString()} tokens)
                        </span>
                      )}
                    </div>
                  </div>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setShowRangeSelector(!showRangeSelector)}
                  >
                    {showRangeSelector ? '收起选择器' : '更改范围'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Range Selector (Collapsible) */}
            {showRangeSelector && (
              <TextRangeSelector
                editionId={selectedEdition.id}
                chapters={chapters}
                selectedMode={rangeSelection?.mode || 'full_edition'}
                onModeChange={(mode) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode,
                    })
                  }
                }}
                selectedChapterIndex={rangeSelection?.chapter_index}
                onSelectedChapterChange={(index) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode: 'single_chapter',
                      chapter_index: index,
                    })
                  }
                }}
                selectedIndices={rangeSelection?.chapter_indices || []}
                onSelectedIndicesChange={(indices) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode: 'multi_chapter',
                      chapter_indices: indices,
                    })
                  }
                }}
                startIndex={rangeSelection?.start_index}
                onStartIndexChange={(index) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode: rangeSelection?.mode === 'chapter_range' ? 'chapter_range' : 'current_to_end',
                      start_index: index,
                      end_index: rangeSelection?.end_index,
                    })
                  }
                }}
                endIndex={rangeSelection?.end_index}
                onEndIndexChange={(index) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode: 'chapter_range',
                      start_index: rangeSelection?.start_index,
                      end_index: index,
                    })
                  }
                }}
                chapterCount={rangeStats.chapterCount}
                totalChars={rangeStats.totalChars}
                estimatedTokens={rangeStats.estimatedTokens}
                selectedChapters={selectedChaptersInfo}
                warnings={[]}
              />
            )}

            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="tasks" className="flex items-center gap-1">
                  <Target className="w-4 h-4" />
                  <span className="hidden sm:inline">分析任务</span>
                  <span className="sm:hidden">任务</span>
                </TabsTrigger>
                <TabsTrigger value="characters" className="flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  <span className="hidden sm:inline">人物管理</span>
                  <span className="sm:hidden">人物</span>
                </TabsTrigger>
                <TabsTrigger value="settings" className="flex items-center gap-1">
                  <Settings className="w-4 h-4" />
                  <span className="hidden sm:inline">设定管理</span>
                  <span className="sm:hidden">设定</span>
                </TabsTrigger>
                <TabsTrigger value="outline" className="flex items-center gap-1">
                  <Sparkles className="w-4 h-4" />
                  <span className="hidden sm:inline">大纲分析</span>
                  <span className="sm:hidden">大纲</span>
                </TabsTrigger>
              </TabsList>
              
              {/* Tasks Tab */}
              <TabsContent value="tasks" className="mt-4">
                <TaskPanel editionId={selectedEdition.id} />
              </TabsContent>
              
              {/* Characters Tab */}
              <TabsContent value="characters" className="mt-4">
                <CharacterPanel 
                  editionId={selectedEdition.id} 
                  workTitle={selectedWork?.title || ''}
                  rangeSelection={rangeSelection || undefined}
                  chapters={chapters}
                />
              </TabsContent>
              
              {/* Settings Tab */}
              <TabsContent value="settings" className="mt-4">
                <SettingPanel 
                  editionId={selectedEdition.id}
                  rangeSelection={rangeSelection || undefined}
                  chapters={chapters}
                />
              </TabsContent>
              
              {/* Outline Tab */}
              <TabsContent value="outline" className="mt-4">
                <OutlinePanel 
                  editionId={selectedEdition.id} 
                  chapters={chapters}
                  rangeSelection={rangeSelection || undefined}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
