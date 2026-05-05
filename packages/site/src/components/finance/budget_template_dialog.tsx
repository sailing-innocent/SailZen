/**
 * @file budget_template_dialog.tsx
 * @brief Budget Template Dialog - Configuration-driven budget creation
 * @author sailing-innocent
 * @date 2026-02-01
 * 
 * 设计理念：
 * - 模板只是前端的"预设配置"，不需要后端专用 API
 * - 所有预算创建都使用统一的 create_budget_with_items 接口
 * - 用户可以基于预设模板修改，也可以完全自定义
 */

import React, { useState, useMemo } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Trash2, Plus } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { api_create_budget_with_items } from '@lib/api/money'
import { Money } from '@lib/utils/money'
import {
  BUDGET_PRESETS,
  BudgetDirection,
  BudgetDirectionLabels,
  ItemType,
  ItemTypeLabels,
  type BudgetPresetType,
  type BudgetItemCreateProps,
} from '@lib/data/money'

interface BudgetTemplateDialogProps {
  onSuccess?: () => void
}

interface ItemFormData extends BudgetItemCreateProps {
  key: string  // For React list key
}

const BudgetTemplateDialog: React.FC<BudgetTemplateDialogProps> = ({ onSuccess }) => {
  const [open, setOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Preset selection
  const [selectedPreset, setSelectedPreset] = useState<BudgetPresetType>('rent')
  
  // Budget form state
  const [budgetName, setBudgetName] = useState('')
  const [budgetDescription, setBudgetDescription] = useState('')
  const [budgetTags, setBudgetTags] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  
  // Items state
  const [items, setItems] = useState<ItemFormData[]>([])

  // Load preset items when preset changes
  const handlePresetChange = (preset: BudgetPresetType) => {
    setSelectedPreset(preset)
    const presetConfig = BUDGET_PRESETS[preset]
    setBudgetTags(presetConfig.defaultTags)
    setBudgetDescription(presetConfig.description)
    
    // Convert preset items to form data
    const newItems: ItemFormData[] = presetConfig.itemPresets.map((item, index) => ({
      ...item,
      key: `preset-${index}-${Date.now()}`,
    }))
    setItems(newItems)
  }

  // Initialize with rent preset when dialog opens
  const handleOpenChange = (isOpen: boolean) => {
    setOpen(isOpen)
    if (isOpen && items.length === 0) {
      handlePresetChange('rent')
    }
  }

  // Add new item
  const addItem = () => {
    const newItem: ItemFormData = {
      key: `new-${Date.now()}`,
      name: '',
      description: '',
      direction: BudgetDirection.EXPENSE,
      item_type: ItemType.FIXED,
      amount: '0',
      period_count: 1,
      is_refundable: 0,
    }
    setItems([...items, newItem])
  }

  // Update item
  const updateItem = (key: string, updates: Partial<ItemFormData>) => {
    setItems(items.map(item => 
      item.key === key ? { ...item, ...updates } : item
    ))
  }

  // Remove item
  const removeItem = (key: string) => {
    setItems(items.filter(item => item.key !== key))
  }

  // Calculate total
  const totalAmount = useMemo(() => {
    let total = new Money('0')
    for (const item of items) {
      const amount = new Money(item.amount || '0')
      if (item.item_type === ItemType.PERIODIC) {
        total = total.add(amount.multiply(item.period_count || 1))
      } else {
        total = total.add(amount)
      }
    }
    return total
  }, [items])

  // Calculate by direction
  const { expenseTotal, incomeTotal } = useMemo(() => {
    let expense = new Money('0')
    let income = new Money('0')
    
    for (const item of items) {
      const amount = new Money(item.amount || '0')
      const itemTotal = item.item_type === ItemType.PERIODIC 
        ? amount.multiply(item.period_count || 1) 
        : amount
      
      if (item.direction === BudgetDirection.INCOME) {
        income = income.add(itemTotal)
      } else {
        expense = expense.add(itemTotal)
      }
    }
    
    return { expenseTotal: expense, incomeTotal: income }
  }, [items])

  // Reset form
  const resetForm = () => {
    setBudgetName('')
    setBudgetDescription('')
    setBudgetTags('')
    setStartDate('')
    setEndDate('')
    setItems([])
    setSelectedPreset('rent')
  }

  // Submit
  const handleSubmit = async () => {
    if (!budgetName.trim()) {
      alert('请输入预算名称')
      return
    }
    if (items.length === 0) {
      alert('请至少添加一个预算项')
      return
    }
    if (items.some(item => !item.name.trim())) {
      alert('请填写所有预算项的名称')
      return
    }

    setIsSubmitting(true)
    try {
      // Prepare items for API
      const apiItems: BudgetItemCreateProps[] = items.map(({ key, ...item }) => item)
      
      await api_create_budget_with_items(
        {
          name: budgetName.trim(),
          description: budgetDescription,
          tags: budgetTags,
          start_date: startDate ? new Date(startDate).getTime() / 1000 : undefined,
          end_date: endDate ? new Date(endDate).getTime() / 1000 : undefined,
        },
        apiItems
      )
      
      resetForm()
      setOpen(false)
      onSuccess?.()
    } catch (error) {
      console.error('Failed to create budget:', error)
      alert('创建失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">预算模板</Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>创建预算</DialogTitle>
          <DialogDescription>
            选择预设模板快速创建，或自定义预算项
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Preset Selection */}
          <div className="flex gap-2 flex-wrap">
            {Object.entries(BUDGET_PRESETS).map(([key, preset]) => (
              <Button
                key={key}
                variant={selectedPreset === key ? 'default' : 'outline'}
                size="sm"
                onClick={() => handlePresetChange(key as BudgetPresetType)}
              >
                {preset.name}
              </Button>
            ))}
          </div>

          {/* Budget Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">预算信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label>预算名称 *</Label>
                <Input
                  value={budgetName}
                  onChange={(e) => setBudgetName(e.target.value)}
                  placeholder="如：2026年租房预算"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label>开始日期</Label>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>结束日期</Label>
                  <Input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label>标签</Label>
                <Input
                  value={budgetTags}
                  onChange={(e) => setBudgetTags(e.target.value)}
                  placeholder="逗号分隔，如：rent,housing"
                />
              </div>
              <div className="grid gap-2">
                <Label>描述</Label>
                <Input
                  value={budgetDescription}
                  onChange={(e) => setBudgetDescription(e.target.value)}
                  placeholder="预算描述..."
                />
              </div>
            </CardContent>
          </Card>

          {/* Budget Items */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="text-base">预算项</CardTitle>
                  <CardDescription>添加预算的组成项目</CardDescription>
                </div>
                <Button size="sm" variant="outline" onClick={addItem}>
                  <Plus className="h-4 w-4 mr-1" />
                  添加项目
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {items.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground">
                  暂无预算项，点击"添加项目"开始
                </div>
              ) : (
                items.map((item, index) => (
                  <div key={item.key} className="border rounded-lg p-4 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">预算项 #{index + 1}</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => removeItem(item.key)}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="col-span-2 grid gap-1">
                        <Label className="text-xs">名称 *</Label>
                        <Input
                          size={1}
                          value={item.name}
                          onChange={(e) => updateItem(item.key, { name: e.target.value })}
                          placeholder="如：月租金"
                        />
                      </div>
                      <div className="grid gap-1">
                        <Label className="text-xs">方向</Label>
                        <Select
                          value={String(item.direction)}
                          onValueChange={(v) => updateItem(item.key, { direction: parseInt(v) })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(BudgetDirectionLabels).map(([value, label]) => (
                              <SelectItem key={value} value={value}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-1">
                        <Label className="text-xs">类型</Label>
                        <Select
                          value={String(item.item_type)}
                          onValueChange={(v) => updateItem(item.key, { item_type: parseInt(v) })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(ItemTypeLabels).map(([value, label]) => (
                              <SelectItem key={value} value={value}>{label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="grid gap-1">
                        <Label className="text-xs">
                          {item.item_type === ItemType.PERIODIC ? '单期金额' : '金额'}
                        </Label>
                        <Input
                          type="number"
                          value={item.amount}
                          onChange={(e) => updateItem(item.key, { amount: e.target.value })}
                          placeholder="0"
                        />
                      </div>
                      {item.item_type === ItemType.PERIODIC && (
                        <div className="grid gap-1">
                          <Label className="text-xs">期数</Label>
                          <Input
                            type="number"
                            value={item.period_count}
                            onChange={(e) => updateItem(item.key, { period_count: parseInt(e.target.value) || 1 })}
                            placeholder="12"
                          />
                        </div>
                      )}
                      <div className="grid gap-1">
                        <Label className="text-xs">可退还</Label>
                        <Select
                          value={String(item.is_refundable)}
                          onValueChange={(v) => updateItem(item.key, { is_refundable: parseInt(v) })}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="0">否</SelectItem>
                            <SelectItem value="1">是</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-1">
                        <Label className="text-xs">小计</Label>
                        <div className="h-9 flex items-center px-3 bg-muted rounded-md text-sm font-medium">
                          {item.item_type === ItemType.PERIODIC
                            ? new Money(item.amount || '0').multiply(item.period_count || 1).format()
                            : new Money(item.amount || '0').format()}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex gap-2 flex-wrap">
                      {item.direction === BudgetDirection.INCOME && (
                        <Badge variant="secondary">收入</Badge>
                      )}
                      {item.is_refundable === 1 && (
                        <Badge variant="outline">可退还</Badge>
                      )}
                      {item.item_type === ItemType.PERIODIC && (
                        <Badge variant="outline">{item.period_count}期</Badge>
                      )}
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          {/* Summary */}
          {items.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">预算汇总</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-sm text-muted-foreground">支出预算</div>
                    <div className="text-lg font-semibold text-red-600">
                      {expenseTotal.format()}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">收入预算</div>
                    <div className="text-lg font-semibold text-green-600">
                      {incomeTotal.format()}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-muted-foreground">总预算</div>
                    <div className="text-lg font-bold">
                      {totalAmount.format()}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? '创建中...' : '创建预算'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetTemplateDialog
