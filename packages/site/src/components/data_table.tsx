import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  type ColumnFiltersState,
  type SortingState,
  type PaginationState,
  useReactTable,
  type OnChangeFn,
} from '@tanstack/react-table'

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { Button } from '@components/ui/button'
import { useIsMobile } from '@/hooks/use-mobile'
import React from 'react'

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[],
  pagination: PaginationState,
  setPagination: OnChangeFn<PaginationState>,
  keepPaginationOnDataChange?: boolean
}

export function DataTable<TData, TValue>({ columns, data, pagination, setPagination, keepPaginationOnDataChange = false }: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const isMobile = useIsMobile()

  // 稳定化表格配置，避免不必要的重新创建
  const tableConfig = React.useMemo(() => ({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    autoResetPageIndex: !keepPaginationOnDataChange,
    state: {
      sorting,
      columnFilters,
      pagination,
    },
    onPaginationChange: setPagination,
    // 确保分页状态正确保持
    enableRowSelection: false,
    enableMultiRowSelection: false,
  }), [data, columns, sorting, columnFilters, pagination, setPagination, keepPaginationOnDataChange])

  const table = useReactTable(tableConfig)

  return (
    <div className="w-full">
      {/* 表格容器 - 移动端可横向滚动 */}
      <div
        className={`
        rounded-md border
        ${isMobile ? 'overflow-x-auto max-w-[calc(100vw-2rem)]' : 'overflow-hidden'}
      `}
      >
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id} className={isMobile ? 'text-xs px-2 py-3' : ''}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} data-state={row.getIsSelected() && 'selected'}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className={isMobile ? 'text-xs px-2 py-3' : ''}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className={`h-24 text-center ${isMobile ? 'text-sm' : ''}`}>
                  暂无数据
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* 分页控制 - 移动端优化 */}
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
          <p className={`font-medium ${isMobile ? 'text-sm' : 'text-sm'}`}>每页显示</p>
          <Select
            value={`${table.getState().pagination.pageSize}`}
            onValueChange={(value) => {
              table.setPageSize(Number(value))
            }}
          >
            <SelectTrigger className="h-8 w-[70px]">
              <SelectValue placeholder={table.getState().pagination.pageSize} />
            </SelectTrigger>
            <SelectContent side="top">
              {(isMobile ? [5, 10, 20] : [10, 20, 25, 30, 40, 50]).map((pageSize) => (
                <SelectItem key={pageSize} value={`${pageSize}`}>
                  {pageSize}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className={`font-medium ${isMobile ? 'text-sm' : 'text-sm'}`}>条</span>
        </div>

        {/* 页面信息 */}
        <div
          className={`
          text-sm font-medium
          ${isMobile ? 'order-1' : 'flex w-[100px] items-center justify-center'}
        `}
        >
          第 {table.getState().pagination.pageIndex + 1} 页，共 {table.getPageCount()} 页
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
            onClick={() => table.setPageIndex(0)}
            disabled={!table.getCanPreviousPage()}
          >
            <span className="sr-only">跳转到第一页</span>
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="size-8"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <span className="sr-only">上一页</span>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" className="size-8" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()}>
            <span className="sr-only">下一页</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className={`size-8 ${isMobile ? 'flex' : 'hidden lg:flex'}`}
            onClick={() => table.setPageIndex(table.getPageCount() - 1)}
            disabled={!table.getCanNextPage()}
          >
            <span className="sr-only">跳转到最后一页</span>
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
