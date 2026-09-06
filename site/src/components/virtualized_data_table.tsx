/**
 * @file virtualized_data_table.tsx
 * @brief Virtualized DataTable component for large datasets
 * @description Uses @tanstack/react-virtual for efficient rendering of large lists
 */

import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useRef, useState, useMemo, useCallback } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIsMobile } from '@/hooks/use-mobile'
import { Skeleton } from '@/components/ui/skeleton'

interface VirtualizedDataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  /** Height of each row in pixels */
  rowHeight?: number
  /** Height of the table container */
  containerHeight?: number | string
  /** Whether data is loading */
  isLoading?: boolean
  /** Overscan count for virtualization */
  overscan?: number
  /** Called when a row is clicked */
  onRowClick?: (row: TData) => void
}

// 性能优化：将 row model 获取函数移到组件外部
const coreRowModel = getCoreRowModel()
const sortedRowModel = getSortedRowModel()

export function VirtualizedDataTable<TData, TValue>({
  columns,
  data,
  rowHeight = 48,
  containerHeight = 600,
  isLoading = false,
  overscan = 5,
  onRowClick,
}: VirtualizedDataTableProps<TData, TValue>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const isMobile = useIsMobile()
  const tableContainerRef = useRef<HTMLDivElement>(null)

  // 性能优化：分离静态配置
  const staticConfig = useMemo(() => ({
    getCoreRowModel: coreRowModel,
    getSortedRowModel: sortedRowModel,
    enableRowSelection: false,
  }), [])

  const table = useReactTable({
    data,
    columns,
    ...staticConfig,
    state: {
      sorting,
    },
    onSortingChange: setSorting,
  })

  const { rows } = table.getRowModel()

  // 设置虚拟化
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => rowHeight,
    overscan,
  })

  const virtualRows = virtualizer.getVirtualItems()
  const totalSize = virtualizer.getTotalSize()

  // 计算 padding 以正确定位虚拟行
  const paddingTop = virtualRows.length > 0 ? virtualRows[0]?.start ?? 0 : 0
  const paddingBottom =
    virtualRows.length > 0
      ? totalSize - (virtualRows[virtualRows.length - 1]?.end ?? 0)
      : 0

  // 处理行点击
  const handleRowClick = useCallback((row: TData) => {
    if (onRowClick) {
      onRowClick(row)
    }
  }, [onRowClick])

  // 计算容器高度
  const containerStyle = useMemo(() => ({
    height: typeof containerHeight === 'number' ? `${containerHeight}px` : containerHeight,
    overflow: 'auto' as const,
  }), [containerHeight])

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 border rounded-md">
        <span className="text-muted-foreground">暂无数据</span>
      </div>
    )
  }

  return (
    <div className="w-full">
      <div
        ref={tableContainerRef}
        className="rounded-md border"
        style={containerStyle}
      >
        <Table>
          <TableHeader className="sticky top-0 bg-background z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={isMobile ? 'text-xs px-2 py-3' : ''}
                    style={{ width: header.getSize() }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {/* Top padding row */}
            {paddingTop > 0 && (
              <tr>
                <td style={{ height: `${paddingTop}px` }} colSpan={columns.length} />
              </tr>
            )}
            
            {/* Virtualized rows */}
            {virtualRows.map((virtualRow) => {
              const row = rows[virtualRow.index]
              return (
                <TableRow
                  key={row.id}
                  data-index={virtualRow.index}
                  data-state={row.getIsSelected() && 'selected'}
                  onClick={() => handleRowClick(row.original)}
                  className={onRowClick ? 'cursor-pointer hover:bg-muted/50' : ''}
                  style={{
                    height: `${virtualRow.size}px`,
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={isMobile ? 'text-xs px-2 py-3' : ''}
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              )
            })}
            
            {/* Bottom padding row */}
            {paddingBottom > 0 && (
              <tr>
                <td style={{ height: `${paddingBottom}px` }} colSpan={columns.length} />
              </tr>
            )}
          </TableBody>
        </Table>
      </div>
      
      {/* Info bar */}
      <div className="flex items-center justify-between mt-2 text-sm text-muted-foreground">
        <span>共 {data.length} 条记录</span>
        <span>当前显示 {virtualRows.length} 行</span>
      </div>
    </div>
  )
}

export default VirtualizedDataTable
