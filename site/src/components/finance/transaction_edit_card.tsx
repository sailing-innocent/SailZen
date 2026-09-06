import React, { useEffect, useState } from 'react'
import { useTransactionsStore, useAccountsStore } from '@lib/store'

import { Card, CardAction, CardContent, CardFooter } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import DatePicker from '@components/date_picker'

import type { TransactionCreateProps } from '@lib/data'

interface TransactionEditCardProps {
  transactionId: number
}

const TransactionEditCard: React.FC<TransactionEditCardProps> = (props: TransactionEditCardProps) => {
  const { transactionId } = props

  const [fromAccId, setFromAccId] = useState<number>(-1)
  const [toAccId, setToAccId] = useState<number>(-1)

  const [value, setValue] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [htime, setHtime] = useState<number>(Math.floor(Date.now() / 1000))
  const [tags, setTags] = useState<string[]>([])

  const getSupportedTags = useTransactionsStore((state) => state.getSupportedTags)

  const updateTransaction = useTransactionsStore((state) => state.updateTransaction)
  const deleteTransaction = useTransactionsStore((state) => state.deleteTransaction)
  const default_data = useTransactionsStore((state) => {
    const transactions = state.transactions
    return transactions.find((t) => t.id === transactionId)
  })
  // set default values if transaction exists
  const getOptions = useAccountsStore((state) => state.getOptions)
  const accounts = getOptions()

  useEffect(() => {
    if (!default_data) return
    setFromAccId(default_data.from_acc_id)
    setToAccId(default_data.to_acc_id)
    setValue(default_data.value.toString())
    setDescription(default_data.description)
    setHtime(default_data.htime)
    setTags(default_data.tags ? default_data.tags.split(',') : [])
  }, [default_data])

  if (!default_data) {
    return <div>Transaction not found</div>
  }

  const default_date = new Date(default_data.htime * 1000)

  const handleUpdateTransaction = async () => {
    // check value
    if (isNaN(parseFloat(value))) {
      console.error('Invalid value')
      return
    }
    // check htime
    if (isNaN(htime) || htime <= 0) {
      console.error('Invalid htime')
      return
    }
    const updated_transaction_props: TransactionCreateProps = {
      from_acc_id: fromAccId,
      to_acc_id: toAccId,
      value: value,
      description: description,
      tags: tags.join(','),
      htime: htime,
    }
    try {
      const updated_transaction = await updateTransaction(transactionId, updated_transaction_props)
      console.log('Transaction updated:', updated_transaction)
    } catch (error) {
      console.error('Error updating transaction:', error)
    }
  }

  return (
    <Card className="w-full max-w-md">
      {/* <CardHeader>
        <CardTitle>Update Transaction</CardTitle>
        <CardDescription></CardDescription>
      </CardHeader> */}
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col">
            <Label htmlFor="from-account">From Account</Label>
            <Select onValueChange={(value) => setFromAccId(parseInt(value))} value={fromAccId.toString()}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select from account" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>From Account</SelectLabel>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id.toString()}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col">
            <Label htmlFor="to-account">To Account</Label>
            <Select onValueChange={(value) => setToAccId(parseInt(value))} value={toAccId.toString()}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select to account" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>To Account</SelectLabel>
                  {accounts.map((account) => (
                    <SelectItem key={account.id} value={account.id.toString()}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col">
            <Label htmlFor="value">Value</Label>
            <Input id="value" type="text" placeholder="Enter value" value={value} onChange={(e) => setValue(e.target.value)} />
          </div>
          <div className="flex flex-col">
            <Label htmlFor="description">Description</Label>
            <Input
              id="description"
              type="text"
              placeholder="Enter description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex flex-col">
            <Label htmlFor="htime">Time</Label>
            <DatePicker
              label=""
              placeholder="Select date"
              value={default_date}
              onChange={(date: Date) => {
                setHtime(Math.floor(date.getTime() / 1000))
              }}
            />
          </div>
          <div className="flex flex-col space-y-3">
            <Label htmlFor="tags">Tags</Label>
            <div className="flex flex-wrap gap-2">
              {getSupportedTags().map((tag) => (
                <div 
                  key={tag} 
                  className="flex items-center cursor-pointer select-none hover:bg-gray-100 rounded-md p-1 transition-colors"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setTags((prev) => {
                      if (prev.includes(tag)) {
                        return prev.filter((t) => t !== tag)
                      } else {
                        return [...prev, tag]
                      }
                    })
                  }}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  onDragStart={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                  }}
                  style={{ 
                    userSelect: 'none', 
                    WebkitUserSelect: 'none', 
                    MozUserSelect: 'none', 
                    msUserSelect: 'none',
                    WebkitTouchCallout: 'none',
                    WebkitTapHighlightColor: 'transparent'
                  }}
                >
                  <Checkbox
                    id={`tag-${tag}`}
                    checked={tags.includes(tag)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setTags((prev) => [...prev, tag])
                      } else {
                        setTags((prev) => prev.filter((t) => t !== tag))
                      }
                    }}
                    className="mr-2 pointer-events-none"
                  />
                  <Label 
                    htmlFor={`tag-${tag}`} 
                    className="text-sm cursor-pointer select-none hover:text-blue-600 transition-colors pointer-events-none"
                  >
                    {tag}
                  </Label>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
      <CardFooter>
        <CardAction>
          <Button variant="outline" onClick={handleUpdateTransaction} className="w-full">
            Update Transaction
          </Button>
        </CardAction>
        {/* Delete Transaction: double check */}
        <CardAction>
          <Button
            variant="destructive"
            onClick={async () => {
              if (window.confirm('Are you sure you want to delete this transaction?')) {
                try {
                  await deleteTransaction(transactionId)
                  console.log('Transaction deleted:', transactionId)
                } catch (error) {
                  console.error('Error deleting transaction:', error)
                }
              }
            }}
            className="w-full"
          >
            Delete Transaction
          </Button>
        </CardAction>
      </CardFooter>
    </Card>
  )
}

export default TransactionEditCard
