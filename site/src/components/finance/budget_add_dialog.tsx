import React, { useState } from 'react'
import { useBudgetsStore, type BudgetsState } from '@lib/store'
import { type BudgetCreateProps } from '@lib/data/money'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import DatePicker from '@components/date_picker'
import { useIsMobile } from '@/hooks/use-mobile'

interface BudgetAddDialogProps {
  onSuccess?: () => void
}

const BudgetAddDialog: React.FC<BudgetAddDialogProps> = ({ onSuccess }) => {
  const createBudget = useBudgetsStore((state: BudgetsState) => state.createBudget)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const [htime, setHtime] = useState<number>(Math.floor(Date.now() / 1000))
  const [loading, setLoading] = useState(false)
  const isMobile = useIsMobile()

  const handleSubmit = async () => {
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
      const budget: BudgetCreateProps = {
        name: name.trim(),
        total_amount: amount,
        description: description.trim() || undefined,
        tags: tags.trim() || undefined,
        htime: htime > 0 ? htime : undefined,
      }
      await createBudget(budget)
      // Reset form
      setName('')
      setAmount('')
      setDescription('')
      setTags('')
      setHtime(Math.floor(Date.now() / 1000))
      if (onSuccess) {
        onSuccess()
      }
      setOpen(false)
    } catch (error) {
      console.error('Error creating budget:', error)
      alert('创建预算失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="default" size="sm">
          创建预算
        </Button>
      </DialogTrigger>
      <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[85vh] overflow-y-auto' : ''}>
        <DialogHeader>
          <DialogTitle>创建预算</DialogTitle>
          <DialogDescription>创建一个新的预算计划</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="name">预算名称 *</Label>
            <Input
              id="name"
              placeholder="请输入预算名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="amount">预算金额 *</Label>
            <Input
              id="amount"
              type="text"
              placeholder="请输入预算金额"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">描述</Label>
            <Input
              id="description"
              placeholder="请输入预算描述（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="tags">标签</Label>
            <Input
              id="tags"
              placeholder="请输入标签，多个标签用逗号分隔（可选）"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="htime">生效时间</Label>
            <DatePicker
              label=""
              placeholder="选择生效时间"
              onChange={(date: Date) => {
                setHtime(Math.floor(date.getTime() / 1000))
              }}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={loading}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? '创建中...' : '创建'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetAddDialog
