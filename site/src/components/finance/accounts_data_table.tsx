import React, { useEffect } from 'react'
import { type AccountsState, sortAccountsForDisplay, useAccountsStore, useServerStore } from '@lib/store'
import { type AccountData } from '@lib/data/money'
import { createAccountColumns } from './account_column'
import { DataTable } from '@components/data_table'
import AccountFixDialog from './account_fix_dialog'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

import {
  type PaginationState,
} from '@tanstack/react-table'

export interface AccountDataTableProps {
  onAccountStateChanged?: () => void
}

const AccountDataTable: React.FC<AccountDataTableProps> = ({ onAccountStateChanged }) => {
  const accounts = useAccountsStore((state: AccountsState) => state.accounts)
  const isLoading = useAccountsStore((state: AccountsState) => state.isLoading)
  const fetchAccounts = useAccountsStore((state: AccountsState) => state.fetchAccounts)
  const fixAccount = useAccountsStore((state: AccountsState) => state.fixAccount)
  const isMobile = useIsMobile()
  const [pagination, setPagination] = React.useState<PaginationState>({
    pageIndex: 0,
    pageSize: isMobile ? 10 : 20,
  })

  const serverHealth = useServerStore((state) => state.serverHealth)
  useEffect(() => {
    if (!serverHealth) {
      return
    }
    fetchAccounts()
  }, [fetchAccounts, serverHealth])

  // 展示全部账户：活跃账户在前、已封存账户靠后并灰显
  const sortedAccounts = React.useMemo(
    () => sortAccountsForDisplay(accounts),
    [accounts]
  )

  const activeCount = React.useMemo(
    () => sortedAccounts.filter((a: AccountData) => a.state === 0).length,
    [sortedAccounts]
  )
  const archivedCount = sortedAccounts.length - activeCount

  const columns = React.useMemo(
    () => createAccountColumns(onAccountStateChanged),
    [onAccountStateChanged]
  )

  const handleFixAccount = React.useCallback(
    async (id: number, newBalance: string) => {
      console.log('修正账户:', id, '新余额:', newBalance)
      await fixAccount(id, newBalance)
    },
    [fixAccount]
  )

  const getRowClassName = React.useCallback(
    (acc: AccountData) =>
      acc.state !== 0 ? 'bg-muted/30 text-muted-foreground hover:bg-muted/45' : '',
    []
  )

  return (
    <Card className="w-full">
      <CardHeader className={`${isMobile ? 'px-4 py-3' : 'pb-3'}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>账户管理</CardTitle>
            {sortedAccounts.length > 0 && (
              <div className="flex items-center gap-1">
                <Badge variant="outline" className="text-[11px] font-normal">
                  活跃 {activeCount}
                </Badge>
                {archivedCount > 0 && (
                  <Badge variant="secondary" className="text-[11px] font-normal text-muted-foreground">
                    已封存 {archivedCount}
                  </Badge>
                )}
              </div>
            )}
          </div>
          <AccountFixDialog
            accounts={sortedAccounts}
            handleFixAccount={handleFixAccount}
          />
        </div>
      </CardHeader>
      <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
        {/* 数据表格区域 */}
        {isLoading ? (
          <div className={`w-full space-y-3 ${isMobile ? 'text-sm' : ''}`}>正在加载...</div>
        ) : sortedAccounts.length > 0 ? (
          <DataTable
            columns={columns}
            data={sortedAccounts}
            pagination={pagination}
            setPagination={setPagination}
            keepPaginationOnDataChange
            getRowClassName={getRowClassName}
          />
        ) : (
          <div className={`text-center py-8 ${isMobile ? 'text-sm' : ''}`}>暂无账户数据</div>
        )}
      </CardContent>
    </Card>
  )
}

export default AccountDataTable
