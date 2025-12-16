import PageLayout from '@components/page_layout'
import { useIsMobile } from '@/hooks/use-mobile'

import AccountsDataTable from '@components/accounts_data_table'
import TransactionsDataTable from '@components/transactions_data_table'
import Statistics from '@components/statistics'

const MoneyPage = () => {
  const isMobile = useIsMobile()

  return (
    <>
      <PageLayout>
        <div className="text-xl md:text-2xl font-bold px-2 md:px-0">财务管理</div>

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
            ${isMobile ? 'w-full order-2' : 'w-[30%] min-w-[300px]'}
          `}
          >
            <AccountsDataTable />
          </div>

          {/* 交易表格 */}
          <div
            className={`
            ${isMobile ? 'w-full order-1' : 'w-[70%]'}
          `}
          >
            <TransactionsDataTable />
          </div>
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
