/**
 * @file analysis.tsx
 * @brief Novel Analysis Page - Entry point for outline, character, and setting analysis
 * @author sailing-innocent
 * @date 2025-02-28
 * 
 * 布局说明:
 * - 顶部: 标题栏 + 作品/版本选择器
 * - 统计概览: 4个统计卡片
 * - 主体区域: 左右两栏布局
 *   - 左侧 (2/3): 文本范围选择器 (宽版)
 *   - 右侧 (1/3): 任务队列 + 分析结果
 * - 下方: 标签页内容区 (任务/人物/设定/大纲管理)
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  FileText, 
  Users, 
  Settings, 
  Activity,
  BarChart3,
  BookOpen,
  Layers,
  Target,
} from 'lucide-react'

import { api_get_works } from '@lib/api/text'
import { api_get_editions_by_work } from '@lib/api/text'
import { api_get_chapter_list } from '@lib/api/text'
import { useAnalysisStore } from '@lib/store/analysisStore'

import type { Work, Edition, ChapterListItem } from '@lib/data/text'

// Components
import TextRangeSelector from '@components/text_range_selector'
import AnalysisResultPanel from '@components/analysis_result_panel'
import AnalysisTaskQueue from '@components/analysis_task_queue'

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
    tasks,
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
      <div className="space-y-6 px-2 md:px-0">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-6 h-6" />
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

        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-muted-foreground" />
                  <CardDescription>人物</CardDescription>
                </div>
                <CardTitle className="text-2xl">{stats.evidence?.character || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center gap-2">
                  <Settings className="w-4 h-4 text-muted-foreground" />
                  <CardDescription>设定</CardDescription>
                </div>
                <CardTitle className="text-2xl">{stats.evidence?.setting || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-muted-foreground" />
                  <CardDescription>大纲节点</CardDescription>
                </div>
                <CardTitle className="text-2xl">{stats.evidence?.outline_node || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-muted-foreground" />
                  <CardDescription>分析任务</CardDescription>
                </div>
                <CardTitle className="text-2xl">
                  {Object.values(stats.tasks || {}).reduce((a, b) => a + b, 0)}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>
        )}

        {/* Main Content - Wide Layout */}
        {selectedEdition && (
          <>
            {/* Section 1: Range Selector (Wide) + Task Queue */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left: Text Range Selector (2/3 width) */}
              <div className="lg:col-span-2">
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
              </div>

              {/* Right: Task Queue (1/3 width) */}
              <div className="lg:col-span-1">
                <AnalysisTaskQueue
                  tasks={tasks}
                  onSelect={(task) => console.log('Selected task:', task)}
                />
              </div>
            </div>

            {/* Section 2: Analysis Results */}
            <AnalysisResultPanel
              results={[]}
              onApprove={(id) => console.log('Approve:', id)}
              onReject={(id) => console.log('Reject:', id)}
            />

            {/* Section 3: Management Tabs */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Target className="w-5 h-5" />
                  分析管理
                </CardTitle>
                <CardDescription>
                  管理人物、设定、大纲和分析任务
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                  <TabsList className="grid w-full grid-cols-4">
                    <TabsTrigger value="tasks">任务管理</TabsTrigger>
                    <TabsTrigger value="characters">人物管理</TabsTrigger>
                    <TabsTrigger value="settings">设定管理</TabsTrigger>
                    <TabsTrigger value="outline">大纲分析</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="tasks" className="mt-4">
                    <TaskPanel editionId={selectedEdition.id} />
                  </TabsContent>
                  
                  <TabsContent value="characters" className="mt-4">
                    <CharacterPanel 
                      editionId={selectedEdition.id} 
                      workTitle={selectedWork?.title || ''}
                      rangeSelection={rangeSelection || undefined}
                    />
                  </TabsContent>
                  
                  <TabsContent value="settings" className="mt-4">
                    <SettingPanel editionId={selectedEdition.id} />
                  </TabsContent>
                  
                  <TabsContent value="outline" className="mt-4">
                    <OutlinePanel editionId={selectedEdition.id} />
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </PageLayout>
  )
}
