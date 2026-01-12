import React, { useState, useEffect } from 'react'
import { useBudgetsStore, type BudgetsState, useAccountsStore, type AccountsState } from '@lib/store'
import { type BudgetData, type BudgetConsumeProps } from '@lib/data/money'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import DatePicker from '@components/date_picker'
import { useIsMobile } from '@/hooks/use-mobile'
import { Money } from '@lib/utils/money'

interface BudgetConsumeDialogProps {
  budget: BudgetData
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

const BudgetConsumeDialog: React.FC<BudgetConsumeDialogProps> = ({
  budget,
  open,
  onOpenChange,
  onSuccess,
}) => {
  const consumeBudget = useBudgetsStore((state: BudgetsState) => state.consumeBudget)
  const getBudgetStats = useBudgetsStore((state: BudgetsState) => state.getBudgetStats)
  const accounts = useAccountsStore((state: AccountsState) => state.accounts)
  const [fromAccId, setFromAccId] = useState<number>(-1)
  const [toAccId, setToAccId] = useState<number>(-1)
  const [value, setValue] = useState<string>('')
  const [description, setDescription] = useState<string>('')
  const [htime, setHtime] = useState<number>(Math.floor(Date.now() / 1000))
  const [loading, setLoading] = useState(false)
  const [remainingAmount, setRemainingAmount] = useState<string>('0.0')
  const isMobile = useIsMobile()

  // Get account options
  const accountOptions = React.useMemo(() => {
    const options = accounts.map((account) => ({
      id: account.id,
      name: account.name,
    }))
    options.unshift({ id: -1, name: '外部' })
    return options
  }, [accounts])

  // Fetch remaining amount
  useEffect(() => {
    if (open && budget.id) {
      const fetchRemaining = async () => {
        try {
          const stats = await getBudgetStats({
            tags: budget.tags,
            return_list: true,
          })
          const budgetDetail = stats.budgets?.find((b) => b.budget.id === budget.id)
          if (budgetDetail) {
            setRemainingAmount(budgetDetail.remaining_amount)
          } else {
            setRemainingAmount(budget.amount)
          }
        } catch (error) {
          console.error('Error fetching remaining amount:', error)
          setRemainingAmount(budget.amount)
        }
      }
      fetchRemaining()
    }
  }, [open, budget, getBudgetStats])

  const handleSubmit = async () => {
    if (!value || isNaN(parseFloat(value)) || parseFloat(value) <= 0) {
      alert('请输入有效的核销金额')
      return
    }

    const consumeAmount = new Money(value)
    const remaining = new Money(remainingAmount)
    if (consumeAmount.value > remaining.value) {
      alert(`核销金额不能超过剩余预算 ${remaining.format()}`)
      return
    }

    if (fromAccId === -1 && toAccId === -1) {
      alert('请至少选择一个账户')
      return
    }

    setLoading(true)
    try {
      const consume: BudgetConsumeProps = {
        from_acc_id: fromAccId,
        to_acc_id: toAccId,
        value: value,
        description: description.trim() || undefined,
        htime: htime > 0 ? htime : undefined,
      }
      await consumeBudget(budget.id, consume)
      // Reset form
      setValue('')
      setDescription('')
      setHtime(Math.floor(Date.now() / 1000))
      setFromAccId(-1)
      setToAccId(-1)
      onOpenChange(false)
      if (onSuccess) {
        onSuccess()
      }
    } catch (error: any) {
      console.error('Error consuming budget:', error)
      alert(error.message || '核销预算失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={isMobile ? 'max-w-[95vw]' : ''}>
        <DialogHeader>
          <DialogTitle>预算核销</DialogTitle>
          <DialogDescription>
            从预算 "{budget.name}" 创建交易记录
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label>预算信息</Label>
            <div className="text-sm text-muted-foreground">
              <div>预算金额: {new Money(budget.amount).format()}</div>
              <div>剩余预算: {new Money(remainingAmount).format()}</div>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="from_acc">支出账户 *</Label>
            <Select
              value={fromAccId.toString()}
              onValueChange={(value) => setFromAccId(parseInt(value))}
            >
              <SelectTrigger id="from_acc">
                <SelectValue placeholder="选择支出账户" />
              </SelectTrigger>
              <SelectContent>
                {accountOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id.toString()}>
                    {option.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="to_acc">收入账户 *</Label>
            <Select
              value={toAccId.toString()}
              onValueChange={(value) => setToAccId(parseInt(value))}
            >
              <SelectTrigger id="to_acc">
                <SelectValue placeholder="选择收入账户" />
              </SelectTrigger>
              <SelectContent>
                {accountOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id.toString()}>
                    {option.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="value">核销金额 *</Label>
            <Input
              id="value"
              type="text"
              placeholder="请输入核销金额"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">描述</Label>
            <Input
              id="description"
              placeholder="请输入交易描述（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="htime">交易时间</Label>
            <DatePicker
              label=""
              placeholder="选择交易时间"
              onChange={(date: Date) => {
                setHtime(Math.floor(date.getTime() / 1000))
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '核销中...' : '核销'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetConsumeDialog
