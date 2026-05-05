import React, { useEffect, useState, useMemo } from 'react'
import { type HistoryEventsState, useHistoryEventsStore } from '@lib/store/history'
import { useServerStore } from '@lib/store'
import { type HistoryEventData } from '@lib/data/history'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { useIsMobile } from '@/hooks/use-mobile'
import { DataTable } from '@components/data_table'
import { type ColumnDef, type PaginationState } from '@tanstack/react-table'
import EditHistoryEventDialog from './history_event_edit_dialog'
import { Badge } from '@components/ui/badge'

const HistoryEventsDataTable: React.FC = () => {
  const events = useHistoryEventsStore((state: HistoryEventsState) => state.events)
  const isLoading = useHistoryEventsStore((state: HistoryEventsState) => state.isLoading)
  const fetchEvents = useHistoryEventsStore((state: HistoryEventsState) => state.fetchEvents)
  const searchEvents = useHistoryEventsStore((state: HistoryEventsState) => state.searchEvents)
  const deleteEvent = useHistoryEventsStore((state: HistoryEventsState) => state.deleteEvent)
  
  const serverHealth = useServerStore((state) => state.serverHealth)
  const isMobile = useIsMobile()
  
  const [searchKeyword, setSearchKeyword] = useState<string>('')
  const [dataUpdated, setDataUpdated] = useState(false)
  const [editingEvent, setEditingEvent] = useState<HistoryEventData | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  
  const [pagination, setPagination] = useState<PaginationState>(() => ({
    pageIndex: 0,
    pageSize: isMobile ? 5 : 10,
  }))

  useEffect(() => {
    setPagination(prev => ({
      ...prev,
      pageSize: isMobile ? 5 : 10,
    }))
  }, [isMobile])

  useEffect(() => {
    if (!serverHealth) {
      return
    }
    if (dataUpdated) {
      return
    }
    setDataUpdated(true)
    fetchEvents(0, 100)
  }, [fetchEvents, serverHealth, dataUpdated])

  const handleRefresh = () => {
    setDataUpdated(false)
    setSearchKeyword('')
  }

  const handleSearch = async () => {
    if (!searchKeyword.trim()) {
      setDataUpdated(false)
      return
    }
    try {
      await searchEvents(searchKeyword.trim())
    } catch (error) {
      console.error('Search failed:', error)
    }
  }

  const handleEdit = (event: HistoryEventData) => {
    setEditingEvent(event)
    setEditDialogOpen(true)
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定要删除这个事件吗？')) {
      return
    }
    try {
      await deleteEvent(id)
    } catch (error) {
      console.error('Delete failed:', error)
      alert('删除失败，请稍后重试')
    }
  }

  const formatDateTime = (dateString?: string): string => {
    if (!dateString) return '-'
    try {
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN')
    } catch {
      return dateString
    }
  }

  const columns: ColumnDef<HistoryEventData>[] = useMemo(() => [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ row }) => <div className="w-12">{row.original.id}</div>,
    },
    {
      accessorKey: 'title',
      header: '标题',
      cell: ({ row }) => (
        <div className="max-w-xs">
          <div className="font-medium truncate" title={row.original.title}>
            {row.original.title}
          </div>
        </div>
      ),
    },
    {
      accessorKey: 'description',
      header: '描述',
      cell: ({ row }) => (
        <div className="max-w-md">
          <div className="truncate text-sm text-muted-foreground" title={row.original.description}>
            {row.original.description}
          </div>
        </div>
      ),
    },
    {
      accessorKey: 'rar_tags',
      header: '标签',
      cell: ({ row }) => (
        <div className="flex gap-1 flex-wrap max-w-xs">
          {row.original.rar_tags?.map((tag, idx) => (
            <Badge key={idx} variant="secondary" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
      ),
    },
    {
      accessorKey: 'start_time',
      header: '开始时间',
      cell: ({ row }) => (
        <div className="text-sm whitespace-nowrap">
          {formatDateTime(row.original.start_time)}
        </div>
      ),
    },
    {
      accessorKey: 'parent_event',
      header: '父事件',
      cell: ({ row }) => (
        <div className="text-sm">
          {row.original.parent_event || '-'}
        </div>
      ),
    },
    {
      id: 'actions',
      header: '操作',
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleEdit(row.original)}
          >
            编辑
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => handleDelete(row.original.id)}
          >
            删除
          </Button>
        </div>
      ),
    },
  ], [])

  return (
    <Card className="w-full">
      <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
        <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>历史事件列表</CardTitle>
      </CardHeader>
      <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
        {/* Search bar */}
        <div className={`flex gap-2 mb-4 ${isMobile ? 'flex-col' : 'flex-row'}`}>
          <Input
            placeholder="搜索事件标题或描述..."
            value={searchKeyword}
            onChange={(e) => setSearchKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSearch()
              }
            }}
            className={`${isMobile ? 'w-full' : 'flex-1'}`}
          />
          <Button onClick={handleSearch} className={`${isMobile ? 'w-full' : ''}`}>
            搜索
          </Button>
          <Button onClick={handleRefresh} variant="outline" className={`${isMobile ? 'w-full' : ''}`}>
            刷新
          </Button>
        </div>

        {/* Results summary */}
        <div className={`mb-4 text-gray-600 ${isMobile ? 'text-sm' : 'text-sm'}`}>
          显示 {events.length} 条历史事件
        </div>

        {/* Data table */}
        {isLoading ? (
          <div className={`w-full space-y-3 ${isMobile ? 'text-sm' : ''}`}>正在加载历史事件...</div>
        ) : events.length > 0 ? (
          <DataTable 
            columns={columns} 
            data={events} 
            pagination={pagination} 
            setPagination={setPagination} 
            keepPaginationOnDataChange={true}
          />
        ) : (
          <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>暂无历史事件</div>
        )}
      </CardContent>

      {/* Edit dialog */}
      {editingEvent && (
        <EditHistoryEventDialog
          event={editingEvent}
          open={editDialogOpen}
          onOpenChange={(open) => {
            setEditDialogOpen(open)
            if (!open) {
              setEditingEvent(null)
            }
          }}
        />
      )}
    </Card>
  )
}

export default HistoryEventsDataTable

