/**
 * @file works_list.tsx
 * @brief Content 2.0 Reading Library Shelf (Pillar Overview, Multi-filter, Progress Bars, Multi-format Import)
 * @author sailing-innocent
 * @date 2026-11-26
 */

import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { BookOpen, Compass, FileText, Clock, Sparkles } from 'lucide-react'
import {
  api_get_works,
  api_search_works,
  api_delete_work,
  api_get_reading_overview,
} from '@lib/api/text'
import type { ReadingOverview, Work } from '@lib/data/text'
import {
  formatCharCount,
  formatDurationMinutes,
  getPillarLabel,
  getReadingStatusLabel,
  getReadingTrackLabel,
  getWorkTypeLabel,
} from '@lib/data/text'
import WorkEditDialog from './work_edit_dialog'
import ContentImportDialog from './content_import_dialog'

interface WorksListProps {
  onSelectWork?: (work: Work) => void
  refreshTrigger?: number
  onDeleteSuccess?: () => void
}

const PILLAR_TABS = [
  { key: 'all', label: '全部素养' },
  { key: 'tech', label: '技术' },
  { key: 'history', label: '历史' },
  { key: 'aesthetics', label: '审美' },
  { key: 'fiction', label: '小说' },
]

export default function WorksList({
  onSelectWork,
  refreshTrigger,
  onDeleteSuccess,
}: WorksListProps) {
  const [works, setWorks] = useState<Work[]>([])
  const [overview, setOverview] = useState<ReadingOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [pillarFilter, setPillarFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [workList, ov] = await Promise.all([
        searchKeyword.trim()
          ? api_search_works(searchKeyword.trim())
          : api_get_works({
              pillar: pillarFilter === 'all' ? undefined : pillarFilter,
              reading_status: statusFilter === 'all' ? undefined : statusFilter,
              work_type: typeFilter === 'all' ? undefined : typeFilter,
            }),
        api_get_reading_overview().catch(() => null),
      ])
      setWorks(workList)
      if (ov) setOverview(ov)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [searchKeyword, pillarFilter, statusFilter, typeFilter])

  useEffect(() => {
    fetchAll()
  }, [fetchAll, refreshTrigger])

  const handleDelete = async (work: Work, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`确定要删除《${work.title}》吗？此操作不可恢复。`)) {
      return
    }
    setDeletingId(work.id)
    try {
      await api_delete_work(work.id)
      setWorks((prev) => prev.filter((w) => w.id !== work.id))
      onDeleteSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除失败')
    } finally {
      setDeletingId(null)
    }
  }

  const handleWorkUpdate = (updatedWork: Work) => {
    setWorks((prev) => prev.map((w) => (w.id === updatedWork.id ? updatedWork : w)))
  }

  return (
    <div className="space-y-4">
      {/* 顶栏标题 + 专题入口 + 多格式导入 */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
            <BookOpen className="w-6 h-6" />
            阅读库
          </h1>
          <p className="text-xs md:text-sm text-muted-foreground">
            分卷小说、技术书籍、SIGGRAPH/arXiv 论文与三大素养进度统一中枢
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link to="/topics">
              <Compass className="w-4 h-4 mr-1.5" />
              专题工作台
              {overview && overview.active_topic_count > 0 && (
                <Badge variant="secondary" className="ml-1.5 px-1.5 py-0 text-[10px]">
                  {overview.active_topic_count}
                </Badge>
              )}
            </Link>
          </Button>
          <ContentImportDialog
            onImported={(res) => {
              fetchAll()
              if (res.work) {
                onSelectWork?.(res.work)
              }
            }}
          />
        </div>
      </div>

      {/* 素养与主线进度概览条 */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
          <Card className="p-3">
            <div className="text-xs text-muted-foreground">藏书 / 在读</div>
            <div className="text-lg font-semibold mt-0.5">
              {overview.total_works}
              <span className="text-xs font-normal text-muted-foreground ml-1.5">
                在读 {overview.reading_count}
              </span>
            </div>
          </Card>
          <Card className="p-3">
            <div className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" /> 近 7 天投入
            </div>
            <div className="text-lg font-semibold mt-0.5">
              {formatDurationMinutes(overview.total_read_seconds_7d)}
              <span className="text-xs font-normal text-muted-foreground ml-1.5">
                30天 {formatDurationMinutes(overview.total_read_seconds_30d)}
              </span>
            </div>
          </Card>
          {overview.pillar_stats.slice(0, 3).map((ps) => (
            <Card
              key={ps.pillar}
              className="p-3 cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => setPillarFilter(pillarFilter === ps.pillar ? 'all' : ps.pillar)}
            >
              <div className="text-xs text-muted-foreground flex items-center justify-between">
                <span>{getPillarLabel(ps.pillar)}素养</span>
                <span className="text-[11px]">{formatDurationMinutes(ps.read_seconds_7d)}/7d</span>
              </div>
              <div className="text-base font-semibold mt-0.5">
                {ps.work_count} 本
                <span className="text-xs font-normal text-muted-foreground ml-1.5">
                  在读 {ps.reading_count}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* 主线在读快捷条 */}
      {overview && overview.mainline_reading.length > 0 && (
        <Card className="p-3 bg-muted/30">
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground mb-2">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            主线 / 项目阅读队列
          </div>
          <div className="flex flex-wrap gap-2">
            {overview.mainline_reading.slice(0, 5).map((w) => (
              <Button
                key={w.id}
                variant="outline"
                size="sm"
                className="h-auto py-1 px-2.5 text-xs bg-background"
                onClick={() => onSelectWork?.(w)}
              >
                <span className="max-w-[180px] truncate">{w.title}</span>
                <Badge variant="secondary" className="ml-1.5 text-[10px] px-1 py-0">
                  {Math.round(w.progress?.progress_pct ?? 0)}%
                </Badge>
              </Button>
            ))}
          </div>
        </Card>
      )}

      {/* 筛选 + 搜索栏 */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="flex flex-wrap gap-1">
          {PILLAR_TABS.map((tab) => (
            <Button
              key={tab.key}
              variant={pillarFilter === tab.key ? 'default' : 'outline'}
              size="sm"
              className="h-8 text-xs"
              onClick={() => setPillarFilter(tab.key)}
            >
              {tab.label}
            </Button>
          ))}
        </div>
        <div className="flex flex-1 gap-2">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[105px] h-8 text-xs">
              <SelectValue placeholder="阅读态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="reading">正在读</SelectItem>
              <SelectItem value="queued">待读</SelectItem>
              <SelectItem value="paused">搁置</SelectItem>
              <SelectItem value="finished">已读完</SelectItem>
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-[98px] h-8 text-xs">
              <SelectValue placeholder="类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              <SelectItem value="paper">论文</SelectItem>
              <SelectItem value="book">书籍</SelectItem>
              <SelectItem value="web_novel">网文</SelectItem>
              <SelectItem value="article">长文</SelectItem>
            </SelectContent>
          </Select>
          <Input
            placeholder="搜索标题 / 作者..."
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchAll()}
            className="flex-1 h-8 text-sm"
          />
        </div>
      </div>

      {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

      {/* 作品列表 */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader><Skeleton className="h-5 w-48" /></CardHeader>
              <CardContent><Skeleton className="h-4 w-full" /></CardContent>
            </Card>
          ))}
        </div>
      ) : works.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground border rounded-lg">
          {searchKeyword ? '没有找到匹配的作品' : '当前筛选下暂无作品，点击右上角「导入论文 / 书籍」开始'}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {works.map((work) => {
            const pct = Math.round(work.progress?.progress_pct ?? 0)
            return (
              <Card
                key={work.id}
                className="cursor-pointer hover:shadow-md hover:border-primary/40 transition-all"
                onClick={() => onSelectWork?.(work)}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <CardTitle className="text-base truncate">{work.title}</CardTitle>
                      {work.author && (
                        <CardDescription className="mt-0.5 text-xs truncate">
                          {work.author}
                        </CardDescription>
                      )}
                    </div>
                    <div className="flex flex-wrap justify-end items-center gap-1 shrink-0">
                      <Badge variant="outline" className="text-[11px]">
                        {getPillarLabel(work.pillar || 'fiction')}
                      </Badge>
                      <Badge variant="secondary" className="text-[11px]">
                        {getWorkTypeLabel(work.work_type)}
                      </Badge>
                      {work.reading_track !== 'leisure' && (
                        <Badge variant="default" className="text-[11px]">
                          {getReadingTrackLabel(work.reading_track)}
                        </Badge>
                      )}
                      {work.asset_count > 0 && (
                        <Badge variant="outline" className="text-[11px] gap-0.5">
                          <FileText className="w-3 h-3" /> PDF/源
                        </Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  {work.synopsis && (
                    <p className="text-xs text-muted-foreground line-clamp-2">{work.synopsis}</p>
                  )}

                  {/* 云端阅读进度条 */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {getReadingStatusLabel(work.reading_status || 'queued')}
                        {work.progress && work.progress.total_read_seconds > 0
                          ? ` · 已读 ${formatDurationMinutes(work.progress.total_read_seconds)}`
                          : ''}
                      </span>
                      <span className="font-medium text-foreground">{pct}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs pt-1">
                    <div className="flex gap-3 text-muted-foreground">
                      <span>{work.chapter_count} 章/节</span>
                      <span>{formatCharCount(work.total_chars)}</span>
                      {work.topic_ids?.length > 0 && (
                        <span>{work.topic_ids.length} 专题</span>
                      )}
                    </div>
                    <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
                      <WorkEditDialog work={work} onUpdateSuccess={handleWorkUpdate} />
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs text-red-500 hover:text-red-700 hover:bg-red-50"
                        onClick={(e) => handleDelete(work, e)}
                        disabled={deletingId === work.id}
                      >
                        {deletingId === work.id ? '删除中...' : '删除'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
