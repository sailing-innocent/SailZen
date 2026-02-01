import React, { useEffect, useMemo, useState } from 'react'
import { type BudgetsState, useBudgetsStore, useServerStore, useAccountsStore, type AccountsState } from '@lib/store'
import { type BudgetData, type TransactionData } from '@lib/data/money'
import { DataTable } from '@components/data_table'
import BudgetAddDialog from './budget_add_dialog'
import BudgetConsumeDialog from './budget_consume_dialog'
import BudgetTemplateDialog from './budget_template_dialog'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { type ColumnDef } from '@tanstack/react-table'
import { Money } from '@lib/utils/money'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  type PaginationState,
} from '@tanstack/react-table'
import { Badge } from '@/components/ui/badge'

interface BudgetWithStats extends BudgetData {
  used_amount?: string
  remaining_amount?: string
  transaction_count?: number
  transactions?: TransactionData[]
}

const BudgetColumns: ColumnDef<BudgetWithStats>[] = [
  {
    accessorKey: 'name',
    header: '预算名称',
    cell: ({ row }) => {
      return <div className="font-medium">{row.getValue('name')}</div>
    },
  },
  {
    accessorKey: 'total_amount',
    header: '预算金额',
    cell: ({ row }) => {
      const amount = new Money(row.getValue('total_amount') as string)
      return <div className="text-right font-semibold">{amount.format()}</div>
    },
  },
  {
    id: 'used_amount',
    header: '已使用',
    cell: ({ row }) => {
      const used = row.original.used_amount
      if (!used) return <div className="text-right">-</div>
      const amount = new Money(used)
      return <div className="text-right text-muted-foreground">{amount.format()}</div>
    },
  },
  {
    id: 'remaining_amount',
    header: '剩余',
    cell: ({ row }) => {
      const remaining = row.original.remaining_amount || row.original.total_amount
      const amount = new Money(remaining)
      const used = row.original.used_amount
      const usedAmount = used ? new Money(used).value : 0
      const budgetAmount = new Money(row.original.total_amount).value
      const isLow = budgetAmount > 0 && (budgetAmount - usedAmount) / budgetAmount < 0.2
      return (
        <div className={`text-right font-semibold ${isLow ? 'text-red-600' : ''}`}>
          {amount.format()}
        </div>
      )
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
  const getBudgetAnalysis = useBudgetsStore((state: BudgetsState) => state.getBudgetAnalysis)
  const unlinkTransaction = useBudgetsStore((state: BudgetsState) => state.unlinkTransaction)
  const accounts = useAccountsStore((state: AccountsState) => state.accounts)
  const isMobile = useIsMobile()
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: isMobile ? 5 : 10,
  })
  const [dataUpdated, setDataUpdated] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState<BudgetData | null>(null)
  const [consumeDialogOpen, setConsumeDialogOpen] = useState(false)
  const [budgetsWithStats, setBudgetsWithStats] = useState<BudgetWithStats[]>([])
  const [expandedBudgets, setExpandedBudgets] = useState<Set<number>>(new Set())
  const [loadingTransactions, setLoadingTransactions] = useState<Set<number>>(new Set())

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

  // Fetch stats for budgets
  useEffect(() => {
    if (budgets.length === 0) {
      setBudgetsWithStats([])
      return
    }
    const fetchStats = async () => {
      try {
        const stats = await getBudgetStats({ return_list: true })
        const budgetMap = new Map(
          stats.budgets?.map((b) => [b.budget.id, b]) || []
        )
        const budgetsWithStatsData = budgets.map((budget) => {
          const stat = budgetMap.get(budget.id)
          return {
            ...budget,
            used_amount: stat?.used_amount,
            remaining_amount: stat?.remaining_amount,
            transaction_count: stat?.transaction_count,
            transactions: undefined, // Will be loaded on expand
          }
        })
        setBudgetsWithStats(budgetsWithStatsData)
      } catch (error) {
        console.error('Error fetching budget stats:', error)
        setBudgetsWithStats(budgets.map((b) => ({ ...b, transactions: undefined })))
      }
    }
    fetchStats()
  }, [budgets, getBudgetStats])

  // Fetch transactions when budget is expanded
  const handleBudgetExpand = React.useCallback(async (budgetId: number) => {
    // Check if transactions are already loaded
    setBudgetsWithStats((prev) => {
      const currentBudget = prev.find((b) => b.id === budgetId)
      if (currentBudget?.transactions !== undefined) {
        return prev // Already loaded
      }
      return prev
    })

    // Double check with current state
    const currentBudget = budgetsWithStats.find((b) => b.id === budgetId)
    if (currentBudget?.transactions !== undefined) {
      return // Already loaded
    }

    setLoadingTransactions((prev) => new Set(prev).add(budgetId))
    try {
      const analysis = await getBudgetAnalysis(budgetId)
      setBudgetsWithStats((prev) =>
        prev.map((b) =>
          b.id === budgetId
            ? { ...b, transactions: analysis.transactions || [] }
            : b
        )
      )
    } catch (error) {
      console.error('Error fetching budget transactions:', error)
      setBudgetsWithStats((prev) =>
        prev.map((b) =>
          b.id === budgetId ? { ...b, transactions: [] } : b
        )
      )
    } finally {
      setLoadingTransactions((prev) => {
        const next = new Set(prev)
        next.delete(budgetId)
        return next
      })
    }
  }, [budgetsWithStats, getBudgetAnalysis])

  // Handle accordion value change
  const handleAccordionChange = React.useCallback((values: string[]) => {
    const expandedIds = new Set(values.map((v) => parseInt(v.replace('budget-', ''))))
    
    // Find newly expanded budgets and load their transactions
    expandedIds.forEach((budgetId) => {
      if (!expandedBudgets.has(budgetId)) {
        // Newly expanded - check if transactions need to be loaded
        const budget = budgetsWithStats.find((b) => b.id === budgetId)
        if (budget?.transactions === undefined) {
          // Load transactions asynchronously
          handleBudgetExpand(budgetId)
        }
      }
    })
    
    setExpandedBudgets(expandedIds)
  }, [expandedBudgets, budgetsWithStats, handleBudgetExpand])

  // Get account name helper
  const getAccountName = (accountId: number): string => {
    if (accountId === -1) return '外部'
    const account = accounts.find((a) => a.id === accountId)
    return account?.name || `账户${accountId}`
  }

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


  const columnsWithActions: ColumnDef<BudgetWithStats>[] = [
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
              <BudgetTemplateDialog
                onSuccess={() => {
                  setDataUpdated(false)
                }}
              />
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
          ) : budgetsWithStats.length > 0 ? (
            <div className="space-y-2">
              <Accordion
                type="multiple"
                className="w-full"
                value={Array.from(expandedBudgets).map((id) => `budget-${id}`)}
                onValueChange={handleAccordionChange}
              >
                {budgetsWithStats.map((budget) => (
                  <AccordionItem key={budget.id} value={`budget-${budget.id}`}>
                    <div className="flex items-center gap-2">
                      <AccordionTrigger className="hover:no-underline flex-1">
                        <div className="flex-1 grid grid-cols-2 md:grid-cols-7 gap-2 md:gap-4 text-left">
                          <div className="font-medium">{budget.name}</div>
                          <div className="text-right font-semibold">
                            {new Money(budget.total_amount).format()}
                          </div>
                          <div className="text-right text-muted-foreground">
                            {budget.used_amount ? new Money(budget.used_amount).format() : '-'}
                          </div>
                          <div
                            className={`text-right font-semibold ${
                              budget.remaining_amount &&
                              new Money(budget.remaining_amount).value <
                                new Money(budget.total_amount).value * 0.2
                                ? 'text-red-600'
                                : ''
                            }`}
                          >
                            {budget.remaining_amount
                              ? new Money(budget.remaining_amount).format()
                              : new Money(budget.total_amount).format()}
                          </div>
                          <div className="hidden md:block max-w-[200px] truncate text-sm">
                            {budget.description || '-'}
                          </div>
                          <div className="hidden md:block max-w-[200px] truncate text-sm">
                            {budget.tags || '-'}
                          </div>
                          <div className="hidden md:block text-sm">
                            {budget.htime
                              ? new Date(budget.htime * 1000).toLocaleDateString('zh-CN')
                              : '-'}
                          </div>
                        </div>
                      </AccordionTrigger>
                      <div className="flex gap-2 pr-4">
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
                    </div>
                    <AccordionContent>
                      <div className="pt-4">
                        {loadingTransactions.has(budget.id) ? (
                          <div className="text-center py-4 text-muted-foreground">
                            正在加载交易记录...
                          </div>
                        ) : budget.transactions && budget.transactions.length > 0 ? (
                          <div className="space-y-2">
                            <div className="text-sm font-semibold mb-2">
                              关联交易 ({budget.transactions.length}笔)
                            </div>
                            <div className="border rounded-md">
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="border-b bg-muted/50">
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'text-xs' : ''}`}>
                                        ID
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'text-xs' : ''}`}>
                                        日期
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'hidden' : ''}`}>
                                        支出账户
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'hidden' : ''}`}>
                                        收入账户
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'text-xs' : ''}`}>
                                        描述
                                      </th>
                                      <th className={`px-2 py-2 text-right ${isMobile ? 'text-xs' : ''}`}>
                                        金额
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'hidden' : ''}`}>
                                        标签
                                      </th>
                                      <th className={`px-2 py-2 text-left ${isMobile ? 'text-xs' : ''}`}>
                                        操作
                                      </th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {budget.transactions.map((transaction) => (
                                      <tr
                                        key={transaction.id}
                                        className="border-b hover:bg-muted/50"
                                      >
                                        <td className={`px-2 py-2 font-mono ${isMobile ? 'text-xs' : 'text-xs'}`}>
                                          {transaction.id}
                                        </td>
                                        <td className={`px-2 py-2 ${isMobile ? 'text-xs' : ''}`}>
                                          {new Date(transaction.htime * 1000).toLocaleDateString(
                                            'zh-CN'
                                          )}
                                        </td>
                                        <td className={`px-2 py-2 ${isMobile ? 'hidden' : ''}`}>
                                          {getAccountName(transaction.from_acc_id)}
                                        </td>
                                        <td className={`px-2 py-2 ${isMobile ? 'hidden' : ''}`}>
                                          {getAccountName(transaction.to_acc_id)}
                                        </td>
                                        <td className={`px-2 py-2 max-w-[150px] truncate ${isMobile ? 'text-xs' : ''}`}>
                                          {transaction.description || '-'}
                                        </td>
                                        <td className={`px-2 py-2 text-right font-semibold ${isMobile ? 'text-xs' : ''}`}>
                                          {new Money(transaction.value).format()}
                                        </td>
                                        <td className={`px-2 py-2 ${isMobile ? 'hidden' : ''}`}>
                                          <div className="flex flex-wrap gap-1">
                                            {transaction.tags
                                              ?.split(',')
                                              .map((tag) => tag.trim())
                                              .filter((tag) => tag.length > 0)
                                              .slice(0, 3)
                                              .map((tag) => (
                                                <Badge key={tag} variant="outline" className="text-xs">
                                                  {tag}
                                                </Badge>
                                              ))}
                                            {transaction.tags
                                              ?.split(',')
                                              .filter((tag) => tag.trim().length > 0).length > 3 && (
                                              <Badge variant="outline" className="text-xs">
                                                +{transaction.tags.split(',').filter((tag) => tag.trim().length > 0).length - 3}
                                              </Badge>
                                            )}
                                          </div>
                                        </td>
                                        <td className={`px-2 py-2 ${isMobile ? 'text-xs' : ''}`}>
                                          {transaction.budget_id === budget.id && (
                                            <Button
                                              variant="ghost"
                                              size={isMobile ? 'sm' : 'sm'}
                                              className={isMobile ? 'h-7 text-xs px-2' : ''}
                                              onClick={async (e) => {
                                                e.stopPropagation()
                                                if (
                                                  window.confirm(
                                                    '确定要取消链接此交易记录吗？'
                                                  )
                                                ) {
                                                  try {
                                                    await unlinkTransaction(transaction.id)
                                                    // Refresh transactions for this budget
                                                    const analysis = await getBudgetAnalysis(budget.id)
                                                    setBudgetsWithStats((prev) =>
                                                      prev.map((b) =>
                                                        b.id === budget.id
                                                          ? {
                                                              ...b,
                                                              transactions:
                                                                analysis.transactions || [],
                                                            }
                                                          : b
                                                      )
                                                    )
                                                    // Refresh stats
                                                    setDataUpdated(false)
                                                  } catch (error) {
                                                    console.error('Error unlinking transaction:', error)
                                                    alert('取消链接失败，请稍后重试')
                                                  }
                                                }
                                              }}
                                            >
                                              {isMobile ? '取消' : '取消链接'}
                                            </Button>
                                          )}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center py-4 text-muted-foreground">
                            暂无关联的交易记录
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          ) : budgets.length > 0 ? (
            <DataTable
              columns={columnsWithActions}
              data={budgets.map((b) => ({ ...b }))}
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
