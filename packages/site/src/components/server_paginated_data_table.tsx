/**
 * @file server_paginated_data_table.tsx
 * @brief Server-side paginated DataTable component
 * @description DataTable that fetches data from server with pagination
 */

import React, { useCallback, useEffect, useMemo } from 'react'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Loader2 } from 'lucide-react'
import { useIsMobile } from '@/hooks/use-mobile'
import { Skeleton } from '@/components/ui/skeleton'
import type { PaginationMeta } from '@lib/store/money'

interface ServerPaginatedDataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  pagination: PaginationMeta
  isLoading: boolean
  onPageChange: (page: number) => void
  onPageSizeChange: (pageSize: number) => void
  onSortChange?: (sortBy: string, sortOrder: 'asc' | 'desc') => void
}

// 性能优化：将 row model 获取函数移到组件外部
const coreRowModel = getCoreRowModel()
const sortedRowModel = getSortedRowModel()

export function ServerPaginatedDataTable<TData, TValue>({
  columns,
  data,
  pagination,
  isLoading,
  onPageChange,
  onPageSizeChange,
  onSortChange,
}: ServerPaginatedDataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const isMobile = useIsMobile()

  // 性能优化：分离静态配置
  const staticConfig = useMemo(() => ({
    getCoreRowModel: coreRowModel,
    getSortedRowModel: sortedRowModel,
    enableRowSelection: false,
    manualPagination: true, // Server-side pagination
    manualSorting: !!onSortChange, // Server-side sorting if handler provided
  }), [onSortChange])

  const table = useReactTable({
    data,
    columns,
    ...staticConfig,
    state: {
      sorting,
    },
    onSortingChange: (updater) => {
      const newSorting = typeof updater === 'function' ? updater(sorting) : updater
      setSorting(newSorting)
      
      // Notify parent of sort change
      if (onSortChange && newSorting.length > 0) {
        const sort = newSorting[0]
        onSortChange(sort.id, sort.desc ? 'desc' : 'asc')
      }
    },
  })

  // 页码导航
  const goToPage = useCallback((page: number) => {
    if (page >= 1 && page <= pagination.totalPages) {
      onPageChange(page)
    }
  }, [pagination.totalPages, onPageChange])

  // 页面大小选项
  const pageSizeOptions = useMemo(() => 
    isMobile ? [5, 10, 20] : [10, 20, 30, 50, 100],
    [isMobile]
  )

  if (isLoading && data.length === 0) {
    return (
      <div className="space-y-2">
        {Array.from({ length: pagination.pageSize }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  return (
    <div className="w-full">
      {/* 表格容器 */}
      <div
        className={`
          rounded-md border relative
          ${isMobile ? 'overflow-x-auto max-w-[calc(100vw-2rem)]' : 'overflow-hidden'}
        `}
      >
        {/* Loading overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-20">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}
        
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={isMobile ? 'text-xs px-2 py-3' : ''}
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
            {data.length > 0 ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} data-state={row.getIsSelected() && 'selected'}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={isMobile ? 'text-xs px-2 py-3' : ''}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className={`h-24 text-center ${isMobile ? 'text-sm' : ''}`}
                >
                  暂无数据
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* 分页控制 */}
      <div
        className={`
          flex items-center justify-between mt-4
          ${isMobile ? 'flex-col gap-4' : 'flex-row space-x-6 lg:space-x-8'}
        `}
      >
        {/* 每页显示行数选择 */}
        <div
          className={`
            flex items-center space-x-2
            ${isMobile ? 'order-2 w-full justify-center' : ''}
          `}
        >
          <p className="text-sm font-medium">每页显示</p>
          <Select
            value={`${pagination.pageSize}`}
            onValueChange={(value) => onPageSizeChange(Number(value))}
          >
            <SelectTrigger className="h-8 w-[70px]">
              <SelectValue placeholder={pagination.pageSize} />
            </SelectTrigger>
            <SelectContent side="top">
              {pageSizeOptions.map((pageSize) => (
                <SelectItem key={pageSize} value={`${pageSize}`}>
                  {pageSize}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-sm font-medium">条</span>
        </div>

        {/* 页面信息 */}
        <div
          className={`
            text-sm font-medium
            ${isMobile ? 'order-1' : 'flex items-center justify-center'}
          `}
        >
          <span>第 {pagination.page} 页，共 {pagination.totalPages} 页</span>
          <span className="ml-2 text-muted-foreground">
            (共 {pagination.total} 条)
          </span>
        </div>

        {/* 分页按钮 */}
        <div
          className={`
            flex items-center space-x-2
            ${isMobile ? 'order-3 w-full justify-center' : ''}
          `}
        >
          <Button
            variant="outline"
            size="icon"
            className={`size-8 ${isMobile ? 'flex' : 'hidden lg:flex'}`}
            onClick={() => goToPage(1)}
            disabled={!pagination.hasPrev || isLoading}
          >
            <span className="sr-only">跳转到第一页</span>
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            onClick={() => goToPage(pagination.page - 1)}
            disabled={!pagination.hasPrev || isLoading}
          >
            <span className="sr-only">上一页</span>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            onClick={() => goToPage(pagination.page + 1)}
            disabled={!pagination.hasNext || isLoading}
          >
            <span className="sr-only">下一页</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className={`size-8 ${isMobile ? 'flex' : 'hidden lg:flex'}`}
            onClick={() => goToPage(pagination.totalPages)}
            disabled={!pagination.hasNext || isLoading}
          >
            <span className="sr-only">跳转到最后一页</span>
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ServerPaginatedDataTable
