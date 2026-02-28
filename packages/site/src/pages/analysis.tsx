/**
 * @file analysis.tsx
 * @brief Novel Analysis Page - Entry point for outline, character, and setting analysis
 * @author sailing-innocent
 * @date 2025-02-28
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
  Share2, 
  Activity,
  BarChart3,
  BookOpen,
} from 'lucide-react'

import { api_get_works } from '@lib/api/text'
import { api_get_editions_by_work } from '@lib/api/text'
import { useAnalysisStore } from '@lib/store/analysisStore'

import type { Work, Edition } from '@lib/data/text'

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
                  <FileText className="w-4 h-4 text-muted-foreground" />
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

        {/* Main Content */}
        {selectedEdition && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left Sidebar - Range Selector */}
            <div className="lg:col-span-1 space-y-4">
              <TextRangeSelector
                editionId={selectedEdition.id}
                chapters={[]} // TODO: Load chapters
                selectedMode={rangeSelection?.mode || 'full_edition'}
                onModeChange={(mode) => {
                  if (selectedEditionId) {
                    setRangeSelection({
                      edition_id: selectedEditionId,
                      mode,
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
                chapterCount={rangePreview?.chapterCount || 0}
                totalChars={rangePreview?.totalChars || 0}
                estimatedTokens={rangePreview?.estimatedTokens || 0}
                selectedChapters={rangePreview?.selectedChapters || []}
                warnings={rangePreview?.warnings || []}
                isLoading={isPreviewLoading}
              />

              {/* Task Queue */}
              <AnalysisTaskQueue
                tasks={tasks}
                onSelect={(task) => console.log('Selected task:', task)}
              />
            </div>

            {/* Right Content - Tabs */}
            <div className="lg:col-span-2">
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
                  <CharacterPanel editionId={selectedEdition.id} />
                </TabsContent>
                
                <TabsContent value="settings" className="mt-4">
                  <SettingPanel editionId={selectedEdition.id} />
                </TabsContent>
                
                <TabsContent value="outline" className="mt-4">
                  <OutlinePanel editionId={selectedEdition.id} />
                </TabsContent>
              </Tabs>

              {/* Analysis Results Panel */}
              <div className="mt-4">
                <AnalysisResultPanel
                  results={[]}
                  onApprove={(id) => console.log('Approve:', id)}
                  onReject={(id) => console.log('Reject:', id)}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}
