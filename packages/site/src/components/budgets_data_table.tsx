import React, { useEffect, useMemo, useState } from 'react'
import { type BudgetsState, useBudgetsStore, useServerStore } from '@lib/store'
import { type BudgetData } from '@lib/data/money'
import { DataTable } from '@components/data_table'
import BudgetAddDialog from './budget_add_dialog'
import BudgetConsumeDialog from './budget_consume_dialog'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { type ColumnDef } from '@tanstack/react-table'
import { Money } from '@lib/utils/money'
import {
  type PaginationState,
} from '@tanstack/react-table'

const BudgetColumns: ColumnDef<BudgetData>[] = [
  {
    accessorKey: 'name',
    header: '预算名称',
    cell: ({ row }) => {
      return <div className="font-medium">{row.getValue('name')}</div>
    },
  },
  {
    accessorKey: 'amount',
    header: '预算金额',
    cell: ({ row }) => {
      const amount = new Money(row.getValue('amount'))
      return <div className="text-right">{amount.format()}</div>
    },
  },
  {
    accessorKey: 'description',
    header: '描述',
    cell: ({ row }) => {
      const desc = row.getValue('description') as string
      return <div className="max-w-[200px] truncate">{desc || '-'}</div>
    },
  },
  {
    accessorKey: 'tags',
    header: '标签',
    cell: ({ row }) => {
      const tags = row.getValue('tags') as string
      return <div className="max-w-[200px] truncate">{tags || '-'}</div>
    },
  },
  {
    accessorKey: 'htime',
    header: '生效时间',
    cell: ({ row }) => {
      const htime = row.getValue('htime') as number
      if (!htime) return '-'
      const date = new Date(htime * 1000)
      return <div>{date.toLocaleDateString('zh-CN')}</div>
    },
  },
]

const BudgetsDataTable: React.FC = () => {
  const budgets = useBudgetsStore((state: BudgetsState) => state.budgets)
  const isLoading = useBudgetsStore((state: BudgetsState) => state.isLoading)
  const fetchBudgets = useBudgetsStore((state: BudgetsState) => state.fetchBudgets)
  const deleteBudget = useBudgetsStore((state: BudgetsState) => state.deleteBudget)
  const getBudgetStats = useBudgetsStore((state: BudgetsState) => state.getBudgetStats)
  const isMobile = useIsMobile()
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: isMobile ? 5 : 10,
  })
  const [dataUpdated, setDataUpdated] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState<BudgetData | null>(null)
  const [consumeDialogOpen, setConsumeDialogOpen] = useState(false)

  const serverHealth = useServerStore((state) => state.serverHealth)
  
  useEffect(() => {
    if (!serverHealth) {
      return
    }
    if (dataUpdated) {
      return
    }
    setDataUpdated(true)
    fetchBudgets()
  }, [fetchBudgets, serverHealth, dataUpdated])

  const handleRefresh = () => {
    setDataUpdated(false)
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定要删除这个预算吗？')) {
      return
    }
    try {
      await deleteBudget(id)
      setDataUpdated(false)
    } catch (error) {
      console.error('Delete failed:', error)
      alert('删除失败，请稍后重试')
    }
  }

  const handleConsume = (budget: BudgetData) => {
    setSelectedBudget(budget)
    setConsumeDialogOpen(true)
  }


  const columnsWithActions: ColumnDef<BudgetData>[] = [
    ...BudgetColumns,
    {
      id: 'actions',
      header: '操作',
      cell: ({ row }) => {
        const budget = row.original
        return (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleConsume(budget)}
            >
              核销
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleDelete(budget.id)}
            >
              删除
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <>
      <Card className="w-full">
        <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
          <div className="flex justify-between items-center">
            <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>预算管理</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleRefresh}>
                刷新
              </Button>
              <BudgetAddDialog
                onSuccess={() => {
                  setDataUpdated(false)
                }}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
          {isLoading ? (
            <div className={`w-full space-y-3 ${isMobile ? 'text-sm' : ''}`}>正在加载...</div>
          ) : budgets.length > 0 ? (
            <DataTable
              columns={columnsWithActions}
              data={budgets}
              pagination={pagination}
              setPagination={setPagination}
            />
          ) : (
            <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>暂无预算数据</div>
          )}
        </CardContent>
      </Card>

      {selectedBudget && (
        <BudgetConsumeDialog
          budget={selectedBudget}
          open={consumeDialogOpen}
          onOpenChange={setConsumeDialogOpen}
          onSuccess={() => {
            setDataUpdated(false)
            setConsumeDialogOpen(false)
            setSelectedBudget(null)
          }}
        />
      )}
    </>
  )
}

export default BudgetsDataTable
