/**
 * @file analysis.tsx
 * @brief Novel Analysis Page - Entry point for outline, character, and setting analysis
 * @author sailing-innocent
 * @date 2025-02-01
 */

import { useState, useEffect } from 'react'
import PageLayout from '@components/page_layout'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { api_get_works } from '@lib/api/text'
import { api_get_analysis_stats } from '@lib/api/analysis'
import type { Work, Edition } from '@lib/data/text'
import type { AnalysisStats } from '@lib/data/analysis'
import { api_get_editions_by_work } from '@lib/api/text'

// Sub-components
import CharacterPanel from '@components/analysis/character_panel'
import SettingPanel from '@components/analysis/setting_panel'
import OutlinePanel from '@components/analysis/outline_panel'
import TaskPanel from '@components/analysis/task_panel'

export default function AnalysisPage() {
  const [works, setWorks] = useState<Work[]>([])
  const [selectedWork, setSelectedWork] = useState<Work | null>(null)
  const [editions, setEditions] = useState<Edition[]>([])
  const [selectedEdition, setSelectedEdition] = useState<Edition | null>(null)
  const [stats, setStats] = useState<AnalysisStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('tasks')

  // Load works on mount
  useEffect(() => {
    const fetchWorks = async () => {
      try {
        const data = await api_get_works()
        setWorks(data)
        if (data.length > 0) {
          setSelectedWork(data[0])
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
    if (!selectedWork) {
      setEditions([])
      setSelectedEdition(null)
      return
    }

    const fetchEditions = async () => {
      try {
        const data = await api_get_editions_by_work(selectedWork.id)
        setEditions(data)
        if (data.length > 0) {
          setSelectedEdition(data[0])
        }
      } catch (err) {
        console.error('Failed to load editions:', err)
      }
    }
    fetchEditions()
  }, [selectedWork])

  // Load stats when edition changes
  useEffect(() => {
    if (!selectedEdition) {
      setStats(null)
      return
    }

    const fetchStats = async () => {
      try {
        const data = await api_get_analysis_stats(selectedEdition.id)
        setStats(data)
      } catch (err) {
        console.error('Failed to load stats:', err)
      }
    }
    fetchStats()
  }, [selectedEdition])

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
          <div className="text-xl md:text-2xl font-bold">作品分析</div>
          
          {/* Work and Edition Selector */}
          <div className="flex flex-wrap gap-2">
            <Select
              value={selectedWork?.id.toString()}
              onValueChange={(value) => {
                const work = works.find(w => w.id.toString() === value)
                setSelectedWork(work || null)
              }}
            >
              <SelectTrigger className="w-48">
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
                value={selectedEdition?.id.toString()}
                onValueChange={(value) => {
                  const edition = editions.find(e => e.id.toString() === value)
                  setSelectedEdition(edition || null)
                }}
              >
                <SelectTrigger className="w-40">
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
                <CardDescription>人物</CardDescription>
                <CardTitle className="text-2xl">{stats.evidence?.character || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <CardDescription>设定</CardDescription>
                <CardTitle className="text-2xl">{stats.evidence?.setting || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <CardDescription>大纲节点</CardDescription>
                <CardTitle className="text-2xl">{stats.evidence?.outline_node || 0}</CardTitle>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader className="py-3 px-4">
                <CardDescription>分析任务</CardDescription>
                <CardTitle className="text-2xl">
                  {Object.values(stats.tasks || {}).reduce((a, b) => a + b, 0)}
                </CardTitle>
              </CardHeader>
            </Card>
          </div>
        )}

        {/* Main Tabs */}
        {selectedEdition && (
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
        )}
      </div>
    </PageLayout>
  )
}
