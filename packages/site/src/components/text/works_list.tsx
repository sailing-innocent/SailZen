/**
 * @file works_list.tsx
 * @brief Works List Component
 * @author sailing-innocent
 * @date 2025-01-29
 */

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api_get_works, api_search_works, api_delete_work } from '@lib/api/text'
import type { Work } from '@lib/data/text'
import { formatCharCount, getWorkStatusLabel, getWorkTypeLabel } from '@lib/data/text'
import WorkEditDialog from './work_edit_dialog'

interface WorksListProps {
  onSelectWork?: (work: Work) => void
  refreshTrigger?: number
  onDeleteSuccess?: () => void
}

export default function WorksList({ onSelectWork, refreshTrigger, onDeleteSuccess }: WorksListProps) {
  const [works, setWorks] = useState<Work[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchKeyword, setSearchKeyword] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const fetchWorks = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = searchKeyword ? await api_search_works(searchKeyword) : await api_get_works()
      setWorks(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWorks()
  }, [refreshTrigger])

  const handleSearch = () => {
    fetchWorks()
  }

  const handleDelete = async (work: Work, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`确定要删除《${work.title}》吗？此操作不可恢复。`)) {
      return
    }

    setDeletingId(work.id)
    try {
      await api_delete_work(work.id)
      // 使用函数式更新避免闭包陷阱，先立即从列表移除
      setWorks((prev) => prev.filter((w) => w.id !== work.id))
      // 通知父组件触发刷新，确保与服务端数据一致
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

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-4 w-32" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-4 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 搜索栏 */}
      <div className="flex gap-2">
        <Input
          placeholder="搜索作品..."
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1"
        />
        <Button onClick={handleSearch} variant="outline">
          搜索
        </Button>
      </div>

      {/* 错误提示 */}
      {error && <div className="text-sm text-red-500 p-2 bg-red-50 rounded">{error}</div>}

      {/* 作品列表 */}
      {works.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          {searchKeyword ? '没有找到匹配的作品' : '暂无作品，点击"导入文本"开始'}
        </div>
      ) : (
        <div className="space-y-3">
          {works.map((work) => (
            <Card
              key={work.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => onSelectWork?.(work)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{work.title}</CardTitle>
                    {work.author && (
                      <CardDescription className="mt-1">作者：{work.author}</CardDescription>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{getWorkTypeLabel(work.work_type)}</Badge>
                    <Badge
                      variant={work.status === 'completed' ? 'default' : 'secondary'}
                    >
                      {getWorkStatusLabel(work.status)}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {work.synopsis && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{work.synopsis}</p>
                )}
                <div className="flex items-center justify-between text-sm">
                  <div className="flex gap-4 text-muted-foreground">
                    <span>{work.chapter_count} 章</span>
                    <span>{formatCharCount(work.total_chars)}</span>
                    <span>{work.edition_count} 个版本</span>
                  </div>
                  <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                    <WorkEditDialog
                      work={work}
                      onUpdateSuccess={handleWorkUpdate}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      onClick={(e) => handleDelete(work, e)}
                      disabled={deletingId === work.id}
                    >
                      {deletingId === work.id ? '删除中...' : '删除'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
