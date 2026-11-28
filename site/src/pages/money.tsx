import { useCallback, useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'

import AccountsDataTable from '@components/finance/accounts_data_table'
import TransactionsDataTable from '@components/finance/transactions_data_table'
import Statistics from '@components/finance/statistics'
import BudgetsDataTable from '@components/finance/budgets_data_table'
import { SailTickSecretaryPanel } from '@components/finance/sailtick_secretary_panel'
import { useAccountsStore, useFinanceTagsStore, useTransactionsStore } from '@lib/store'

const MoneyPage = () => {
  const isMobile = useIsMobile()
  const fetchTags = useFinanceTagsStore((state) => state.fetchTags)
  const isTagsLoaded = useFinanceTagsStore((state) => state.isLoaded)
  const fetchAccounts = useAccountsStore((state) => state.fetchAccounts)
  const fetchTransactionsPaginated = useTransactionsStore((state) => state.fetchTransactionsPaginated)
  const [secretaryRefreshKey, setSecretaryRefreshKey] = useState(0)

  // 在页面加载时获取标签（只加载一次）
  useEffect(() => {
    if (!isTagsLoaded) {
      fetchTags().catch((err) => console.error('Failed to load finance tags:', err))
    }
  }, [fetchTags, isTagsLoaded])

  const handleSecretaryDataChanged = useCallback(() => {
    try {
      fetchAccounts()
      void fetchTransactionsPaginated({ page: 1, page_size: 20, sort_by: 'htime', sort_order: 'desc' })
    } catch (err) {
      console.error('Failed to refresh finance tables:', err)
    }
  }, [fetchAccounts, fetchTransactionsPaginated])

  const handleAccountStateChanged = useCallback(() => {
    setSecretaryRefreshKey((k) => k + 1)
  }, [])

  return (
    <>
      <PageLayout>
        <div className="text-xl md:text-2xl font-bold px-2 md:px-0 mb-2">财务管理</div>

        {/* SailTick 日常开销秘书顶部工作台（即时记账/对账 + 小票识图 + 分级自治清理队列） */}
        <SailTickSecretaryPanel
          onDataChanged={handleSecretaryDataChanged}
          refreshSignal={secretaryRefreshKey}
        />

        {/* 移动端使用垂直布局，桌面端使用水平布局 */}
        <div
          className={`
          flex gap-4 
          ${isMobile ? 'flex-col' : 'flex-row'}
        `}
        >
          {/* 账户表格 */}
          <div
            className={`
            ${isMobile ? 'w-full order-2' : 'w-[36%] min-w-[380px]'}
          `}
          >
            <AccountsDataTable onAccountStateChanged={handleAccountStateChanged} />
          </div>

          {/* 交易表格 */}
          <div
            className={`
            ${isMobile ? 'w-full order-1' : 'w-[64%]'}
          `}
          >
            <TransactionsDataTable />
          </div>
        </div>

        {/* 预算管理 */}
        <div className="w-full mt-4 md:mt-6">
          <BudgetsDataTable />
        </div>

        {/* 统计图表 */}
        <div className="w-full mt-4 md:mt-6">
          <Statistics />
        </div>
      </PageLayout>
    </>
  )
}

export default MoneyPage
