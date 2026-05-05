import { type ColumnDef } from '@tanstack/react-table'
import { type TransactionData } from '@lib/data'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import TransactionEditCard from './transaction_edit_card'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export interface TransactionDisplayProps extends TransactionData {
  from_acc_name: string
  to_acc_name: string
  parsedTags: string[]  // 预解析的标签数组，避免渲染时重复解析
}

// 性能优化：缓存 Intl.NumberFormat 实例，避免每次渲染都创建新实例
const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'CNY',
})

export const TransactionColumns: ColumnDef<TransactionDisplayProps>[] = [
  {
    accessorKey: 'id',
    header: 'ID',
  },
  {
    accessorKey: 'htime',
    header: 'Date',
    cell: ({ row }) => {
      const htime: number = row.getValue('htime')
      const date = new Date(htime * 1000)
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      })
    },
  },
  {
    accessorKey: 'from_acc_name',
    header: 'From Account',
  },
  {
    accessorKey: 'to_acc_name',
    header: 'To Account',
  },
  {
    accessorKey: 'description',
    header: 'Description',
  },
  {
    accessorKey: 'value',
    header: 'Value',
    cell: ({ row }) => {
      const value: number = parseFloat(row.getValue('value'))
      // 使用缓存的 formatter 实例
      return currencyFormatter.format(value)
    },
  },
  {
    accessorKey: 'tags',
    header: 'Tags',
    cell: ({ row }) => {
      // 使用预解析的标签数组，避免每次渲染都重新解析
      const parsedTags = row.original.parsedTags
      return (
        <>
          {parsedTags.map((tag) => (
            <Badge key={tag} className="mr-1">
              {tag}
            </Badge>
          ))}
        </>
      )
    },
  },
  {
    id: 'edit',
    header: '编辑',
    cell: ({ row }) => {
      return (
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm">编辑</Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>编辑交易</DialogTitle>
              <DialogDescription>修改交易记录的详细信息</DialogDescription>
            </DialogHeader>
            <TransactionEditCard transactionId={row.original.id} />
          </DialogContent>
        </Dialog>
      )
    },
  },
]
