import { type ColumnDef } from '@tanstack/react-table'
import { type AccountData } from '@lib/data'
import { Button } from '@/components/ui/button'
import { useAccountsStore } from '@lib/store'
import React from 'react'

// 创建一个组件来处理按钮点击，避免在列定义中直接使用store
const AccountActions = ({ accountId }: { accountId: number }) => {
  const updateAccount = useAccountsStore((state) => state.updateAccount)

  const handleRecalc = React.useCallback(async () => {
    await updateAccount(accountId, true)
  }, [updateAccount, accountId])

  const handleUpdate = React.useCallback(async () => {
    await updateAccount(accountId, false)
  }, [updateAccount, accountId])

  return (
    <div className="flex flex-row">
      <Button variant="outline" onClick={handleRecalc}>
        Recalc
      </Button>
      <Button variant="outline" onClick={handleUpdate}>
        Update
      </Button>
    </div>
  )
}

export const AccountColumns: ColumnDef<AccountData>[] = [
  {
    accessorKey: 'name',
    header: 'Name',
  },
  {
    accessorKey: 'description',
    header: 'Description',
  },
  {
    accessorKey: 'balance',
    header: 'Balance',
  },
  {
    id: 'update',
    header: 'Update',
    cell: ({ row }) => {
      return <AccountActions accountId={row.original.id} />
    },
  },
]
