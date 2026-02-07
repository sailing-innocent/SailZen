import React, { useState, useEffect } from 'react'
import { useBudgetsStore, type BudgetsState } from '@lib/store'
import { type BudgetData, type BudgetCreateProps } from '@lib/data/money'
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
import DatePicker from '@components/date_picker'
import { useIsMobile } from '@/hooks/use-mobile'

interface BudgetEditDialogProps {
  budget: BudgetData | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

const BudgetEditDialog: React.FC<BudgetEditDialogProps> = ({
  budget,
  open,
  onOpenChange,
  onSuccess,
}) => {
  const updateBudget = useBudgetsStore((state: BudgetsState) => state.updateBudget)
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const [htime, setHtime] = useState<number>(Math.floor(Date.now() / 1000))
  const [loading, setLoading] = useState(false)
  const isMobile = useIsMobile()

  // Initialize form when budget changes
  useEffect(() => {
    if (budget) {
      setName(budget.name)
      setAmount(budget.total_amount)
      setDescription(budget.description || '')
      setTags(budget.tags || '')
      setHtime(budget.htime)
    }
  }, [budget])

  const handleSubmit = async () => {
    if (!budget) return
    
    if (!name.trim()) {
      alert('请输入预算名称')
      return
    }
    if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
      alert('请输入有效的预算金额')
      return
    }

    setLoading(true)
    try {
      const budgetData: BudgetCreateProps = {
        name: name.trim(),
        amount: amount,
        description: description.trim() || undefined,
        tags: tags.trim() || undefined,
        htime: htime > 0 ? htime : undefined,
      }
      await updateBudget(budget.id, budgetData)
      onOpenChange(false)
      if (onSuccess) {
        onSuccess()
      }
    } catch (error) {
      console.error('Error updating budget:', error)
      alert('更新预算失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  if (!budget) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[85vh] overflow-y-auto' : ''}>
        <DialogHeader>
          <DialogTitle>编辑预算</DialogTitle>
          <DialogDescription>修改预算详情（预算ID: {budget.id}）</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="edit-name">预算名称 *</Label>
            <Input
              id="edit-name"
              placeholder="请输入预算名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-amount">预算金额 *</Label>
            <Input
              id="edit-amount"
              type="text"
              placeholder="请输入预算金额"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              提示：修改预算金额不会影响已核销的交易记录
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-description">描述</Label>
            <Input
              id="edit-description"
              placeholder="请输入预算描述（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-tags">标签</Label>
            <Input
              id="edit-tags"
              placeholder="请输入标签，多个标签用逗号分隔（可选）"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="edit-htime">生效时间</Label>
            <DatePicker
              label=""
              placeholder="选择生效时间"
              onChange={(date: Date) => {
                setHtime(Math.floor(date.getTime() / 1000))
              }}
            />
            <p className="text-xs text-muted-foreground">
              当前生效时间: {new Date(htime * 1000).toLocaleDateString('zh-CN')}
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '保存中...' : '保存修改'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetEditDialog
