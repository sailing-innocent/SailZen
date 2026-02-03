import React, { useState } from 'react'
import { Label } from '@components/ui/label'
import { Input } from '@components/ui/input'
import { Button } from '@components/ui/button'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@components/ui/select'
import DatePicker from '@components/date_picker'
import { useIsMobile } from '@/hooks/use-mobile'

import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

import { type TransactionCreateProps, type TransactionData, type AccountOption } from '@lib/data'

interface TransactionAddCardProps {
  accounts: AccountOption[]
  onAddTransaction: (transaction: TransactionCreateProps) => Promise<TransactionData>
  onClose?: () => void
}

type DialogState =
  | { type: 'idle' }
  | { type: 'success'; data: TransactionData }
  | { type: 'error'; error: Error }

const TransactionAddCard: React.FC<TransactionAddCardProps> = (props: TransactionAddCardProps) => {
  const [fromAccId, setFromAccId] = useState<number>(-1)
  const [toAccId, setToAccId] = useState<number>(-1)
  const [value, setValue] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [htime, setHtime] = useState<number>(Math.floor(Date.now() / 1000))
  const [dialogState, setDialogState] = useState<DialogState>({ type: 'idle' })
  const isMobile = useIsMobile()

  const { accounts, onAddTransaction, onClose } = props

  const resetForm = () => {
    setFromAccId(-1)
    setToAccId(-1)
    setValue('')
    setDescription('')
    setHtime(Math.floor(Date.now() / 1000))
  }

  const handleAddTransaction = async () => {
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
    const new_transaction_props: TransactionCreateProps = {
      from_acc_id: fromAccId,
      to_acc_id: toAccId,
      value: value,
      description: description,
      tags: '',
      htime: htime,
    }
    try {
      const new_transaction = await onAddTransaction(new_transaction_props)
      console.log('Transaction added:', new_transaction)
      setDialogState({ type: 'success', data: new_transaction })
    } catch (error) {
      console.error('Error adding transaction:', error)
      setDialogState({ type: 'error', error: error instanceof Error ? error : new Error('未知错误') })
    }
  }

  const handleContinueAdd = () => {
    setDialogState({ type: 'idle' })
    resetForm()
  }

  const handleClose = () => {
    setDialogState({ type: 'idle' })
    onClose?.()
  }

  return (
    <>
      <Card className="w-full border-0 shadow-none">
        <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
          <CardTitle className={`${isMobile ? 'text-lg' : ''}`}>添加交易记录</CardTitle>
          <CardDescription className={`${isMobile ? 'text-sm' : ''}`}>请输入要添加的交易记录详情</CardDescription>
        </CardHeader>
        <CardContent className={`space-y-4 ${isMobile ? 'px-4' : ''}`}>
          {/* 账户选择区域 */}
          <div className={`grid gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-2'}`}>
            <div className="flex flex-col space-y-2">
              <Label htmlFor="from-account" className={`${isMobile ? 'text-sm' : ''}`}>
                转出账户
              </Label>
              <Select onValueChange={(value) => setFromAccId(parseInt(value))} defaultValue="-1">
                <SelectTrigger className={`w-full ${isMobile ? 'h-10' : ''}`}>
                  <SelectValue placeholder="选择账户" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>转出账户</SelectLabel>
                    {accounts.map((account) => (
                      <SelectItem key={account.id} value={account.id.toString()}>
                        {account.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col space-y-2">
              <Label htmlFor="to-account" className={`${isMobile ? 'text-sm' : ''}`}>
                转入账户
              </Label>
              <Select onValueChange={(value) => setToAccId(parseInt(value))} defaultValue="-1">
                <SelectTrigger className={`w-full ${isMobile ? 'h-10' : ''}`}>
                  <SelectValue placeholder="选择账户" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>转入账户</SelectLabel>
                    {accounts.map((account) => (
                      <SelectItem key={account.id} value={account.id.toString()}>
                        {account.name}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 金额和描述 */}
          <div className="space-y-4">
            <div className="flex flex-col space-y-2">
              <Label htmlFor="value" className={`${isMobile ? 'text-sm' : ''}`}>
                金额
              </Label>
              <Input
                id="value"
                type="text"
                placeholder="请输入金额"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                className={`${isMobile ? 'h-10' : ''}`}
              />
            </div>
            <div className="flex flex-col space-y-2">
              <Label htmlFor="description" className={`${isMobile ? 'text-sm' : ''}`}>
                描述
              </Label>
              <Input
                id="description"
                type="text"
                placeholder="请输入交易描述"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className={`${isMobile ? 'h-10' : ''}`}
              />
            </div>
            <div className="flex flex-col space-y-2">
              <Label htmlFor="htime" className={`${isMobile ? 'text-sm' : ''}`}>
                日期
              </Label>
              <DatePicker
                label=""
                placeholder="选择日期"
                onChange={(date: Date) => {
                  setHtime(Math.floor(date.getTime() / 1000))
                }}
              />
            </div>
          </div>
        </CardContent>
        <CardFooter className={`${isMobile ? 'px-4 py-3' : ''}`}>
          <CardAction>
            <Button variant="outline" onClick={handleAddTransaction} className={`w-full ${isMobile ? 'h-10' : ''}`}>
              添加交易记录
            </Button>
          </CardAction>
        </CardFooter>
      </Card>

      {/* 成功弹窗 */}
      <AlertDialog open={dialogState.type === 'success'} onOpenChange={(open) => !open && setDialogState({ type: 'idle' })}>
        <AlertDialogContent className={isMobile ? 'max-w-[90vw]' : ''}>
          <AlertDialogHeader>
            <AlertDialogTitle>添加成功</AlertDialogTitle>
            <AlertDialogDescription>
              交易记录已成功添加。
              <br />
              金额: {dialogState.type === 'success' ? dialogState.data.value : ''}
              <br />
              描述: {dialogState.type === 'success' ? dialogState.data.description : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleClose}>返回列表</AlertDialogCancel>
            <AlertDialogAction onClick={handleContinueAdd}>继续添加</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 失败弹窗 */}
      <AlertDialog open={dialogState.type === 'error'} onOpenChange={(open) => !open && setDialogState({ type: 'idle' })}>
        <AlertDialogContent className={isMobile ? 'max-w-[90vw]' : ''}>
          <AlertDialogHeader>
            <AlertDialogTitle>添加失败</AlertDialogTitle>
            <AlertDialogDescription>
              交易记录添加失败，请检查输入数据后重试。
              <br />
              错误信息: {dialogState.type === 'error' ? dialogState.error.message : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleClose}>返回列表</AlertDialogCancel>
            <AlertDialogAction onClick={() => setDialogState({ type: 'idle' })}>修改</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default TransactionAddCard
