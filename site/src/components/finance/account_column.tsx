import { type ColumnDef } from '@tanstack/react-table'
import { type AccountData } from '@lib/data'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAccountsStore } from '@lib/store'
import { Archive, ArchiveRestore, Loader2, Wallet } from 'lucide-react'
import React, { useState } from 'react'

interface AccountActionsProps {
  account: AccountData
  onStateChanged?: () => void
}

// 处理单个账户行的重算、刷新、封存/解封操作
const AccountActions: React.FC<AccountActionsProps> = ({ account, onStateChanged }) => {
  const updateAccount = useAccountsStore((state) => state.updateAccount)
  const setAccountState = useAccountsStore((state) => state.setAccountState)
  const [busyAction, setBusyAction] = useState<'recalc' | 'update' | 'archive' | null>(null)

  const isArchived = account.state !== 0

  const handleRecalc = React.useCallback(async () => {
    setBusyAction('recalc')
    try {
      await updateAccount(account.id, true)
    } finally {
      setBusyAction(null)
    }
  }, [updateAccount, account.id])

  const handleUpdate = React.useCallback(async () => {
    setBusyAction('update')
    try {
      await updateAccount(account.id, false)
    } finally {
      setBusyAction(null)
    }
  }, [updateAccount, account.id])

  const handleToggleArchive = React.useCallback(async () => {
    setBusyAction('archive')
    try {
      await setAccountState(account.id, isArchived ? 0 : 1)
      onStateChanged?.()
    } catch (err) {
      console.error('Failed to toggle account archive state:', err)
    } finally {
      setBusyAction(null)
    }
  }, [setAccountState, account.id, isArchived, onStateChanged])

  return (
    <div className="flex flex-row items-center gap-1">
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2 text-xs"
        disabled={busyAction !== null}
        onClick={() => void handleRecalc()}
        title="从全部流水重算余额"
      >
        {busyAction === 'recalc' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Recalc'}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2 text-xs"
        disabled={busyAction !== null}
        onClick={() => void handleUpdate()}
        title="按未结算流水增量更新余额"
      >
        {busyAction === 'update' ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Update'}
      </Button>
      <Button
        size="sm"
        variant={isArchived ? 'outline' : 'ghost'}
        className={`h-7 px-2 text-xs ${isArchived ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'}`}
        disabled={busyAction !== null}
        onClick={() => void handleToggleArchive()}
        title={isArchived ? '解封账户，恢复为活跃状态' : '封存归档账户（靠后灰显，不触发活跃提醒）'}
      >
        {busyAction === 'archive' ? (
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
        ) : isArchived ? (
          <ArchiveRestore className="h-3.5 w-3.5 mr-1" />
        ) : (
          <Archive className="h-3.5 w-3.5 mr-1" />
        )}
        {isArchived ? '解封' : '封存'}
      </Button>
    </div>
  )
}

export const createAccountColumns = (onStateChanged?: () => void): ColumnDef<AccountData>[] => [
  {
    accessorKey: 'name',
    header: '账户',
    cell: ({ row }) => {
      const acc = row.original
      const isArchived = acc.state !== 0
      const desc = (acc.description ?? '').trim()
      return (
        <div className="flex flex-col gap-0.5 min-w-[110px]">
          <div className="flex items-center gap-1.5">
            {isArchived ? (
              <Archive
                className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70"
                aria-label="已封存账户"
              />
            ) : (
              <Wallet
                className="h-3.5 w-3.5 shrink-0 text-primary/80"
                aria-label="活跃账户"
              />
            )}
            <span className={isArchived ? 'text-muted-foreground' : 'font-medium text-foreground'}>
              {acc.name}
            </span>
            {isArchived && (
              <Badge
                variant="secondary"
                className="text-[10px] leading-tight px-1.5 py-0 font-normal text-muted-foreground shrink-0"
              >
                已封存
              </Badge>
            )}
          </div>
          {desc && (
            <span className="text-[11px] text-muted-foreground pl-5 truncate max-w-[160px]" title={desc}>
              {desc}
            </span>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: 'balance',
    header: '余额',
    cell: ({ row }) => {
      const isArchived = row.original.state !== 0
      return (
        <span className={`font-mono tabular-nums ${isArchived ? 'text-muted-foreground' : 'font-medium'}`}>
          {row.original.balance}
        </span>
      )
    },
  },
  {
    id: 'actions',
    header: '操作',
    cell: ({ row }) => <AccountActions account={row.original} onStateChanged={onStateChanged} />,
  },
]

export const AccountColumns: ColumnDef<AccountData>[] = createAccountColumns()
