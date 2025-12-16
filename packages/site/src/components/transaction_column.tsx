import { type ColumnDef } from '@tanstack/react-table'
import { type TransactionData } from '@lib/data'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import TransactionEditCard from './transaction_edit_card'

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

export interface TransactionDisplayProps extends TransactionData {
  from_acc_name: string
  to_acc_name: string
}

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
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'CNY',
      }).format(value)
    },
  },
  {
    accessorKey: 'tags',
    header: 'Tags',
    cell: ({ row }) => {
      const tags: string = row.getValue('tags')
      const tagList = tags
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0)
      return (
        <>
          {tagList.map((tag) => (
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
    header: 'Edit',
    cell: ({ row }) => {
      return (
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Edit</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Transaction</DialogTitle>
              <DialogDescription>Modify the details of the transaction.</DialogDescription>
            </DialogHeader>
            <DialogClose asChild>
              <TransactionEditCard transactionId={row.original.id} />
            </DialogClose>
          </DialogContent>
        </Dialog>
      )
    },
  },
]
