import React, { useEffect, useMemo } from 'react'
import { type TransactionsState, useTransactionsStore, useServerStore, useAccountsStore } from '@lib/store'
import { TransactionColumns, type TransactionDisplayProps } from './transaction_column'
import { DataTable } from '@components/data_table'
import { Button } from '@components/ui/button'
import TransactionFiltersComponent, { type TransactionFilters } from './transaction_filters'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { Dialog, DialogClose, DialogContent, DialogTrigger } from '@/components/ui/dialog'
import TransactionAddCard from './transaction_add_card'


import {
  type PaginationState,
} from '@tanstack/react-table'

const TransactionsDataTable: React.FC = () => {
  const [dataUpdated, setDataUpdated] = React.useState(false)
  const maxTransactions = 2048
  const [filters, setFilters] = React.useState<TransactionFilters>({
    dateRange: {},
    tags: [],
    amountRange: {},
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

  const transactions = useTransactionsStore((state: TransactionsState) => state.transactions)
  const isLoading = useTransactionsStore((state: TransactionsState) => state.isLoading)

  const fetchTransactions = useTransactionsStore((state: TransactionsState) => state.fetchTransactions)
  const createTransaction = useTransactionsStore((state: TransactionsState) => state.createTransaction)

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

  const getOptions = useAccountsStore((state) => state.getOptions)
  const accountsData = useAccountsStore((state) => state.accounts)
  const accounts = useMemo(() => getOptions(), [getOptions, accountsData])

  // Filter transactions based on current filters
  const filteredTransactions = useMemo(() => {
    return transactions.filter((transaction) => {
      // Date range filter
      if (filters.dateRange.start || filters.dateRange.end) {
        const transactionDate = new Date(transaction.htime * 1000)
        if (filters.dateRange.start && transactionDate < filters.dateRange.start) {
          return false
        }
        if (filters.dateRange.end && transactionDate >= filters.dateRange.end) {
          return false
        }
      }

      // Tags filter
      if (filters.tags.length > 0) {
        const transactionTags = transaction.tags
          .split(',')
          .map((tag) => tag.trim())
          .filter((tag) => tag.length > 0)

        const hasMatchingTag = filters.tags.some((filterTag) =>
          transactionTags.some((transactionTag) => transactionTag.toLowerCase().includes(filterTag.toLowerCase()))
        )

        if (!hasMatchingTag) {
          return false
        }
      }

      // Amount range filter
      const transactionValue = parseFloat(transaction.value)
      if (filters.amountRange.min !== undefined && transactionValue < filters.amountRange.min) {
        return false
      }
      if (filters.amountRange.max !== undefined && transactionValue > filters.amountRange.max) {
        return false
      }

      return true
    })
  }, [transactions, filters])

  const resetFilters = () => {
    setFilters({
      dateRange: {},
      tags: [],
      amountRange: {},
    })
  }

  const handleAddTransaction = React.useCallback(async (transaction: any) => {
    console.log('Adding transaction:', transaction)
    const res = await createTransaction(transaction)
    setDataUpdated(false)
    return res
  }, [createTransaction])


  const transactionsDisplay: TransactionDisplayProps[] = useMemo(() => {
    return filteredTransactions.map((transaction) => {
      const fromAccount = accounts.find((acc) => acc.id === transaction.from_acc_id)
      const toAccount = accounts.find((acc) => acc.id === transaction.to_acc_id)
      
      // 调试信息
      if (!fromAccount) {
        console.log('From account not found:', {
          transactionId: transaction.id,
          from_acc_id: transaction.from_acc_id,
          availableAccounts: accounts.map(acc => ({ id: acc.id, name: acc.name }))
        })
      }
      if (!toAccount) {
        console.log('To account not found:', {
          transactionId: transaction.id,
          to_acc_id: transaction.to_acc_id,
          availableAccounts: accounts.map(acc => ({ id: acc.id, name: acc.name }))
        })
      }
      
      return {
        ...transaction,
        from_acc_name: fromAccount?.name || 'Unknown',
        to_acc_name: toAccount?.name || 'Unknown',
      }
    })
  }, [filteredTransactions, accounts])

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
          <TransactionFiltersComponent filters={filters} onFiltersChange={setFilters} onReset={resetFilters} />
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
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">Add Transaction</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogClose asChild>
                <TransactionAddCard
                  onAddTransaction={handleAddTransaction}
                  accounts={accounts}
                />
              </DialogClose>
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
