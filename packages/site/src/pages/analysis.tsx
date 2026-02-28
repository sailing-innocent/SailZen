/**
 * @file analysis.tsx
 * @brief Novel Analysis Page - Entry point for outline, character, and setting analysis
 * @author sailing-innocent
 * @date 2025-02-28
 * 
 * 布局说明:
 * - 顶部: 标题栏 + 作品/版本选择器 + 紧凑统计概览
 * - 主体区域: 标签页内容区
 *   - 任务管理: 文本范围选择器 + 任务创建/监控
 *   - 人物管理: 人物列表和分析
 *   - 设定管理: 设定列表和分析
 *   - 大纲分析: 大纲列表、AI提取、树形编辑器
 */

import { useState, useEffect } from 'react'
import PageLayout from '@components/page_layout'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { 
  FileText, 
  Users, 
  Settings, 
  BookOpen,
  Layers,
  Target,
  Sparkles,
  Activity,
} from 'lucide-react'

import { api_get_works } from '@lib/api/text'
import { api_get_editions_by_work } from '@lib/api/text'
import { api_get_chapter_list } from '@lib/api/text'
import { useAnalysisStore } from '@lib/store/analysisStore'

import type { Work, Edition, ChapterListItem } from '@lib/data/text'

// Components
import TextRangeSelector from '@components/text_range_selector'

// Sub-components
import CharacterPanel from '@components/analysis/character_panel'
import SettingPanel from '@components/analysis/setting_panel'
import OutlinePanel from '@components/analysis/outline_panel'
import TaskPanel from '@components/analysis/task_panel'

export default function AnalysisPage() {
  // Local state
  const [works, setWorks] = useState<Work[]>([])
  const [editions, setEditions] = useState<Edition[]>([])
  const [chapters, setChapters] = useState<ChapterListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('tasks')

  // Global store state
  const {
    selectedWorkId,
    selectedEditionId,
    stats,
    rangeSelection,
    rangePreview,
    isPreviewLoading,
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

        {/* Main Content: Tabs */}
        {selectedEdition && (
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
            
            {/* Tasks Tab: Range Selector + Task Management */}
            <TabsContent value="tasks" className="mt-4 space-y-4">
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
                chapterCount={rangePreview?.chapterCount || 0}
                totalChars={rangePreview?.totalChars || 0}
                estimatedTokens={rangePreview?.estimatedTokens || 0}
                selectedChapters={rangePreview?.selectedChapters || []}
                warnings={rangePreview?.warnings || []}
                isLoading={isPreviewLoading}
              />
              <TaskPanel editionId={selectedEdition.id} />
            </TabsContent>
            
            {/* Characters Tab */}
            <TabsContent value="characters" className="mt-4">
              <CharacterPanel 
                editionId={selectedEdition.id} 
                workTitle={selectedWork?.title || ''}
                rangeSelection={rangeSelection || undefined}
              />
            </TabsContent>
            
            {/* Settings Tab */}
            <TabsContent value="settings" className="mt-4">
              <SettingPanel editionId={selectedEdition.id} />
            </TabsContent>
            
            {/* Outline Tab */}
            <TabsContent value="outline" className="mt-4">
              <OutlinePanel editionId={selectedEdition.id} />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </PageLayout>
  )
}
