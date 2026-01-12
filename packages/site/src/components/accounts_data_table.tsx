import React, { useEffect } from 'react'
import { type AccountsState, useAccountsStore, useServerStore } from '@lib/store'
import { type AccountData } from '@lib/data/money'
import { AccountColumns } from './account_column'
import { DataTable } from '@components/data_table'
import AccountFixDialog from './account_fix_dialog'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import {
  type PaginationState,
} from '@tanstack/react-table'

const AccountDataTable: React.FC = () => {
  const accounts = useAccountsStore((state: AccountsState) => state.accounts)
  const isLoading = useAccountsStore((state: AccountsState) => state.isLoading)
  const fetchAccounts = useAccountsStore((state: AccountsState) => state.fetchAccounts)
  const fixAccount = useAccountsStore((state: AccountsState) => state.fixAccount)
  const isMobile = useIsMobile()
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: isMobile ? 5 : 10,
  })

  const serverHealth = useServerStore((state) => state.serverHealth)
  useEffect(() => {
    if (!serverHealth) {
      return
    }
    fetchAccounts()
  }, [fetchAccounts, serverHealth])

  return (
    <Card className="w-full">
      <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
        <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>账户管理</CardTitle>
      </CardHeader>
      <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
        {/* 操作按钮区域 */}
        <div
          className={`
          flex gap-4 mb-4
          ${isMobile ? 'flex-col' : 'flex-row'}
        `}
        >
          <div
            className={`
            ${isMobile ? 'w-full' : 'flex-1'}
          `}
          >
            添加交易
          </div>
          <div
            className={`
            ${isMobile ? 'w-full' : 'flex-1'}
          `}
          >
            <AccountFixDialog
              accounts={accounts}
              handleFixAccount={React.useCallback(async (id, newBalance) => {
                console.log('修正账户:', id, '新余额:', newBalance)
                await fixAccount(id, newBalance)
              }, [fixAccount])}
            />
          </div>
        </div>

        {/* 数据表格区域 */}
        {isLoading ? (
          <div className={`w-full space-y-3 ${isMobile ? 'text-sm' : ''}`}>正在加载...</div>
        ) : accounts.length > 0 ? (
          <DataTable columns={AccountColumns} data={accounts.filter((a: AccountData) => {
            return a.state == 0;
          })} pagination={pagination} setPagination={setPagination} />
        ) : (
          <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>暂无账户数据</div>
        )}
      </CardContent>
    </Card>
  )
}

export default AccountDataTable
