import React, { useEffect, useMemo } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { type TransactionsState, useTransactionsStore, useServerStore, useAccountsStore } from '@lib/store'
import { TransactionColumns, type TransactionDisplayProps } from './transaction_column'
import { DataTable } from '@components/data_table'
import { Button } from '@components/ui/button'
import TransactionFiltersComponent, { type TransactionFilters, type TransactionTypeFilter } from './transaction_filters'
import { useIsMobile } from '@/hooks/use-mobile'
import { useDebouncedValue } from '@/hooks/use-debounce'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog'
import TransactionAddCard from './transaction_add_card'


import {
  type PaginationState,
} from '@tanstack/react-table'

const TransactionsDataTable: React.FC = () => {
  const [dataUpdated, setDataUpdated] = React.useState(false)
  const [isAddDialogOpen, setIsAddDialogOpen] = React.useState(false)
  const maxTransactions = 2048
  const [filters, setFilters] = React.useState<TransactionFilters>({
    dateRange: {},
    tags: [],
    amountRange: {},
    transactionType: 'all',
    fromAccountId: undefined,
    toAccountId: undefined,
  })
  const isMobile = useIsMobile()
  const [pagination, setPagination] = React.useState<PaginationState>(() => ({
    pageIndex: 0,
    pageSize: isMobile ? 5 : 10,
  }))

  // 保存当前分页状态，用于数据更新时恢复
  const savedPaginationRef = React.useRef<PaginationState>(pagination)
  
  // 当分页状态变化时，更新保存的状态
  React.useEffect(() => {
    savedPaginationRef.current = pagination
  }, [pagination])

  // 稳定化setPagination函数，防止数据更新时重置分页
  const stableSetPagination = React.useCallback((updater: any) => {
      setPagination(updater)
  }, [])

  // 只在isMobile变化时更新pageSize，但保持pageIndex不变
  React.useEffect(() => {
    setPagination(prev => ({
      ...prev,
      pageSize: isMobile ? 5 : 10,
    }))
  }, [isMobile])

  // 性能优化：使用 useShallow 合并多个选择器，减少不必要的重渲染
  const { transactions, isLoading, fetchTransactions, createTransaction } = useTransactionsStore(
    useShallow((state: TransactionsState) => ({
      transactions: state.transactions,
      isLoading: state.isLoading,
      fetchTransactions: state.fetchTransactions,
      createTransaction: state.createTransaction,
    }))
  )

  const serverHealth = useServerStore((state) => state.serverHealth)
  const accountsLoading = useAccountsStore((state) => state.isLoading)

  useEffect(() => {
    if (!serverHealth || accountsLoading) {
      return
    }
    if (dataUpdated) {
      return
    }
    setDataUpdated(true)
    fetchTransactions(maxTransactions)
  }, [fetchTransactions, serverHealth, accountsLoading, dataUpdated, maxTransactions])

  // 性能优化：合并账户相关的选择器
  const { getOptions, accounts: accountsData } = useAccountsStore(
    useShallow((state) => ({
      getOptions: state.getOptions,
      accounts: state.accounts,
    }))
  )
  const accounts = useMemo(() => {
    const options = getOptions()
    // 按照state排序，state小的在前，大的在后
    return options.sort((a, b) => {
      const stateA = a.state ?? 0
      const stateB = b.state ?? 0
      return stateA - stateB
    })
  }, [getOptions, accountsData])

  // 性能优化：使用 Map 进行 O(1) 账户查找，替代 O(n) 的 find()
  const accountsMap = useMemo(() => {
    return new Map(accounts.map(acc => [acc.id, acc]))
  }, [accounts])

  // 性能优化：对过滤条件进行防抖处理，避免频繁输入时的重复计算
  // 300ms 的延迟在用户体验和性能之间取得平衡
  const debouncedFilters = useDebouncedValue(filters, 300)

  // Filter transactions based on debounced filters
  const filteredTransactions = useMemo(() => {
    return transactions.filter((transaction) => {
      // Date range filter
      if (debouncedFilters.dateRange.start || debouncedFilters.dateRange.end) {
        const transactionDate = new Date(transaction.htime * 1000)
        if (debouncedFilters.dateRange.start && transactionDate < debouncedFilters.dateRange.start) {
          return false
        }
        if (debouncedFilters.dateRange.end && transactionDate >= debouncedFilters.dateRange.end) {
          return false
        }
      }

      // Tags filter
      if (debouncedFilters.tags.length > 0) {
        const transactionTags = transaction.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter((tag) => tag.length > 0)

        const hasMatchingTag = debouncedFilters.tags.some((filterTag) =>
          transactionTags.some((transactionTag) => transactionTag.toLowerCase().includes(filterTag.toLowerCase()))
        )

        if (!hasMatchingTag) {
          return false
        }
      }

      // Amount range filter
      const transactionValue = parseFloat(transaction.value)
      if (debouncedFilters.amountRange.min !== undefined && transactionValue < debouncedFilters.amountRange.min) {
        return false
      }
      if (debouncedFilters.amountRange.max !== undefined && transactionValue > debouncedFilters.amountRange.max) {
        return false
      }

      // Transaction type filter
      const transactionType: TransactionTypeFilter = debouncedFilters.transactionType || 'all'
      if (transactionType !== 'all') {
        const fromAccId = transaction.from_acc_id
        const toAccId = transaction.to_acc_id
        
        // Determine transaction type
        // income: from_acc_id == -1 (money from external to account)
        // expense: to_acc_id == -1 (money from account to external)
        // transfer: both from_acc_id and to_acc_id are valid accounts
        const isIncome = fromAccId === -1
        const isExpense = toAccId === -1
        const isTransfer = !isIncome && !isExpense

        if (transactionType === 'income' && !isIncome) {
          return false
        }
        if (transactionType === 'expense' && !isExpense) {
          return false
        }
        if (transactionType === 'transfer' && !isTransfer) {
          return false
        }
      }

      // Account filters
      if (debouncedFilters.fromAccountId !== undefined) {
        if (transaction.from_acc_id !== debouncedFilters.fromAccountId) {
          return false
        }
      }
      if (debouncedFilters.toAccountId !== undefined) {
        if (transaction.to_acc_id !== debouncedFilters.toAccountId) {
          return false
        }
      }

      return true
    })
  }, [transactions, debouncedFilters])

  const resetFilters = () => {
    setFilters({
      dateRange: {},
      tags: [],
      amountRange: {},
      transactionType: 'all',
      fromAccountId: undefined,
      toAccountId: undefined,
    })
  }

  const handleAddTransaction = React.useCallback(async (transaction: any) => {
    console.log('Adding transaction:', transaction)
    const res = await createTransaction(transaction)
    setDataUpdated(false)
    return res
  }, [createTransaction])

  const handleCloseAddDialog = React.useCallback(() => {
    setIsAddDialogOpen(false)
  }, [])


  // 性能优化：使用 Map 进行 O(1) 查找，预解析标签避免重复 split()
  const transactionsDisplay: TransactionDisplayProps[] = useMemo(() => {
    return filteredTransactions.map((transaction) => {
      // 使用 Map 的 O(1) 查找替代 find() 的 O(n) 查找
      const fromAccount = accountsMap.get(transaction.from_acc_id)
      const toAccount = accountsMap.get(transaction.to_acc_id)
      
      // 预解析标签，避免在渲染时重复解析
      const parsedTags = transaction.tags
        .split(',')
        .map(tag => tag.trim())
        .filter(tag => tag.length > 0)
      
      return {
        ...transaction,
        from_acc_name: fromAccount?.name || 'Unknown',
        to_acc_name: toAccount?.name || 'Unknown',
        parsedTags,
      }
    })
  }, [filteredTransactions, accountsMap])

  // 稳定化数据引用，避免不必要的重新渲染
  const stableTransactionsDisplay = useMemo(() => transactionsDisplay, [transactionsDisplay])

  return (
    <Card className="w-full">
      <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
        <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>交易记录</CardTitle>
      </CardHeader>
      <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
        {/* 筛选器组件 */}
        <div className="mb-4">
          <TransactionFiltersComponent filters={filters} onFiltersChange={setFilters} onReset={resetFilters} accounts={accounts} />
        </div>

        {/* 操作按钮区域 */}
        <div
          className={`
          flex gap-4 mb-4
          ${isMobile ? 'flex-col' : 'flex-row'}
        `}
        >
          <Button
            onClick={() => {
              setDataUpdated(false)
            }}
            className={`${isMobile ? 'w-full' : ''}`}
          >
            刷新交易记录
          </Button>
          <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className={`${isMobile ? 'w-full' : ''}`}>
                添加交易
              </Button>
            </DialogTrigger>
            <DialogContent className={`${isMobile ? 'max-h-[85vh] overflow-y-auto p-4' : ''}`}>
              <TransactionAddCard
                onAddTransaction={handleAddTransaction}
                accounts={accounts}
                onClose={handleCloseAddDialog}
              />
            </DialogContent>
          </Dialog>
        </div>

        {/* 结果摘要 */}
        <div className={`mb-4 text-gray-600 ${isMobile ? 'text-sm' : 'text-sm'}`}>
          显示 {transactionsDisplay.length} / {transactions.length} 条交易记录
        </div>

        {/* 数据表格 */}
        {isLoading || accountsLoading ? (
          <div className={`w-full space-y-3 ${isMobile ? 'text-sm' : ''}`}>
            {isLoading ? '正在加载交易记录...' : '正在加载账户数据...'}
          </div>
        ) : stableTransactionsDisplay.length > 0 ? (
          <DataTable columns={TransactionColumns} data={stableTransactionsDisplay} pagination={pagination} setPagination={stableSetPagination} keepPaginationOnDataChange={true} />
        ) : transactions.length > 0 ? (
          <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>没有符合当前筛选条件的交易记录</div>
        ) : (
          <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>暂无交易记录</div>
        )}
      </CardContent>
    </Card>
  )
}

export default TransactionsDataTable
