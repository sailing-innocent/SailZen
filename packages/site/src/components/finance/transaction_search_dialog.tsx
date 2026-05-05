import React, { useState, useEffect, useMemo } from 'react'
import { useTransactionsStore, type TransactionsState } from '@lib/store'
import { type TransactionData } from '@lib/data/money'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useIsMobile } from '@/hooks/use-mobile'
import { Money } from '@lib/utils/money'
import { DataTable } from '@components/data_table'
import { type ColumnDef } from '@tanstack/react-table'

interface TransactionSearchDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (transaction: TransactionData) => void
  excludeBudgetId?: number | null
  excludeTransactionIds?: number[]
}

const TransactionSearchDialog: React.FC<TransactionSearchDialogProps> = ({
  open,
  onOpenChange,
  onSelect,
  excludeBudgetId,
  excludeTransactionIds = [],
}) => {
  const fetchTransactions = useTransactionsStore((state: TransactionsState) => state.fetchTransactions)
  const [transactions, setTransactions] = useState<TransactionData[]>([])
  const [searchKeyword, setSearchKeyword] = useState('')
  const [loading, setLoading] = useState(false)
  const isMobile = useIsMobile()

  useEffect(() => {
    if (open) {
      loadTransactions()
    }
  }, [open])

  const loadTransactions = async () => {
    setLoading(true)
    try {
      const data = await fetchTransactions(100) // Load first 100 transactions
      // Filter out already linked transactions and excluded ones
      const filtered = data.filter((t) => {
        // Only show expense transactions (from_acc_id > 0, to_acc_id === -1)
        if (!(t.from_acc_id > 0 && t.to_acc_id === -1)) {
          return false
        }
        // Exclude transactions already linked to a budget (unless it's the same budget)
        if (t.budget_id !== null && t.budget_id !== undefined) {
          if (excludeBudgetId === null || t.budget_id !== excludeBudgetId) {
            return false
          }
        }
        // Exclude specific transaction IDs
        if (excludeTransactionIds.includes(t.id)) {
          return false
        }
        return true
      })
      setTransactions(filtered)
    } catch (error) {
      console.error('Error loading transactions:', error)
    } finally {
      setLoading(false)
    }
  }

  const filteredTransactions = useMemo(() => {
    if (!searchKeyword.trim()) {
      return transactions
    }
    const keyword = searchKeyword.toLowerCase()
    return transactions.filter((t) => {
      return (
        t.description?.toLowerCase().includes(keyword) ||
        t.tags?.toLowerCase().includes(keyword) ||
        t.value.includes(keyword) ||
        t.id.toString().includes(keyword)
      )
    })
  }, [transactions, searchKeyword])

  const columns: ColumnDef<TransactionData>[] = useMemo(
    () => [
      {
        accessorKey: 'id',
        header: 'ID',
        cell: ({ row }) => <div className="font-mono text-sm">{row.getValue('id')}</div>,
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
        accessorKey: 'value',
        header: '金额',
        cell: ({ row }) => {
          const value = new Money(row.getValue('value') as string)
          return <div className="text-right font-semibold">{value.format()}</div>
        },
      },
      {
        accessorKey: 'htime',
        header: '时间',
        cell: ({ row }) => {
          const htime = row.getValue('htime') as number
          if (!htime) return '-'
          const date = new Date(htime * 1000)
          return <div className="text-sm">{date.toLocaleDateString('zh-CN')}</div>
        },
      },
      {
        id: 'actions',
        header: '操作',
        cell: ({ row }) => {
          const transaction = row.original
          return (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                onSelect(transaction)
                onOpenChange(false)
              }}
            >
              选择
            </Button>
          )
        },
      },
    ],
    [onSelect, onOpenChange]
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={isMobile ? 'max-w-[95vw] h-[90vh]' : 'max-w-4xl h-[80vh]'}>
        <DialogHeader>
          <DialogTitle>搜索交易记录</DialogTitle>
          <DialogDescription>选择要链接到预算的交易记录</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4 flex-1 overflow-hidden">
          <div className="grid gap-2">
            <Label htmlFor="search">搜索</Label>
            <Input
              id="search"
              placeholder="搜索描述、标签、金额或ID..."
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
            />
          </div>
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="text-center py-8">正在加载...</div>
            ) : filteredTransactions.length > 0 ? (
              <DataTable
                columns={columns}
                data={filteredTransactions}
                pagination={{ pageIndex: 0, pageSize: 10 }}
                setPagination={() => {}}
              />
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                {searchKeyword ? '未找到匹配的交易记录' : '暂无可用的交易记录'}
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default TransactionSearchDialog
