import React from 'react'
import { type BudgetData, type TransactionData, BudgetDirection, BudgetDirectionLabels } from '@lib/data/money'
import { Money } from '@lib/utils/money'
import { useAccountsStore, type AccountsState } from '@lib/store'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { useIsMobile } from '@/hooks/use-mobile'
import { Calendar, Tag, FileText, DollarSign, Percent, CreditCard } from 'lucide-react'

interface BudgetDetailDialogProps {
  budget: BudgetData | null
  usedAmount?: string
  remainingAmount?: string
  transactions?: TransactionData[]
  open: boolean
  onOpenChange: (open: boolean) => void
  onEdit?: () => void
}

const BudgetDetailDialog: React.FC<BudgetDetailDialogProps> = ({
  budget,
  usedAmount,
  remainingAmount,
  transactions,
  open,
  onOpenChange,
  onEdit,
}) => {
  const accounts = useAccountsStore((state: AccountsState) => state.accounts)
  const isMobile = useIsMobile()

  if (!budget) return null

  const budgetAmount = budget.total_amount ? new Money(budget.total_amount) : new Money('0')
  const used = usedAmount && usedAmount !== '0.0' ? new Money(usedAmount) : new Money('0')
  const remaining = remainingAmount && remainingAmount !== '0.0' ? new Money(remainingAmount) : budgetAmount
  const usagePercentage = budgetAmount.value > 0 
    ? (used.value / budgetAmount.value) * 100 
    : 0

  const getAccountName = (accountId: number): string => {
    if (accountId === -1) return '外部'
    const account = accounts.find((a) => a.id === accountId)
    return account?.name || `账户${accountId}`
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={isMobile ? 'max-w-[95vw] max-h-[90vh] overflow-y-auto' : 'max-w-2xl max-h-[85vh] overflow-y-auto'}>
        <DialogHeader>
          <div className="flex items-center justify-between">
            <div>
              <DialogTitle className="flex items-center gap-2">
                <DollarSign className={`h-5 w-5 ${budget.direction === BudgetDirection.INCOME ? 'text-green-500' : 'text-red-500'}`} />
                {budget.name}
                <Badge 
                  variant="outline" 
                  className={`text-xs ${
                    budget.direction === BudgetDirection.INCOME
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-red-50 text-red-700 border-red-200'
                  }`}
                >
                  {BudgetDirectionLabels[budget.direction ?? BudgetDirection.EXPENSE]}
                </Badge>
              </DialogTitle>
              <DialogDescription>
                预算ID: {budget.id} | 创建于 {new Date(budget.htime * 1000).toLocaleDateString('zh-CN')}
              </DialogDescription>
            </div>
            {onEdit && (
              <Button variant="outline" size="sm" onClick={onEdit}>
                编辑
              </Button>
            )}
          </div>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {/* Budget Overview Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">预算金额</div>
              <div className="text-lg font-semibold">{budgetAmount.format()}</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">已使用</div>
              <div className="text-lg font-semibold text-orange-600">{used.format()}</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-xs text-muted-foreground mb-1">剩余</div>
              <div className={`text-lg font-semibold ${remaining.value < budgetAmount.value * 0.2 ? 'text-red-600' : 'text-green-600'}`}>
                {remaining.format()}
              </div>
            </div>
          </div>

          {/* Usage Progress */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <Label className="flex items-center gap-1">
                <Percent className="h-4 w-4" />
                使用率
              </Label>
              <span className={`text-sm font-semibold ${usagePercentage >= 100 ? 'text-red-600' : usagePercentage >= 80 ? 'text-orange-600' : ''}`}>
                {usagePercentage.toFixed(1)}%
              </span>
            </div>
            <Progress 
              value={Math.min(usagePercentage, 100)} 
              className="h-3"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>0%</span>
              <span>50%</span>
              <span>100%</span>
            </div>
          </div>

          {/* Budget Details */}
          <div className="space-y-4 border-t pt-4">
            <h4 className="text-sm font-semibold">预算详情</h4>
            
            <div className="grid gap-3">
              {budget.description && (
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground mt-0.5" />
                  <div>
                    <div className="text-xs text-muted-foreground">描述</div>
                    <div className="text-sm">{budget.description}</div>
                  </div>
                </div>
              )}
              
              {budget.tags && (
                <div className="flex items-start gap-2">
                  <Tag className="h-4 w-4 text-muted-foreground mt-0.5" />
                  <div>
                    <div className="text-xs text-muted-foreground">标签</div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {budget.tags.split(',').map((tag) => tag.trim()).filter(Boolean).map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              
              <div className="flex items-start gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <div className="text-xs text-muted-foreground">生效时间</div>
                  <div className="text-sm">
                    {new Date(budget.htime * 1000).toLocaleString('zh-CN', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Related Transactions */}
          {transactions && transactions.length > 0 && (
            <div className="space-y-4 border-t pt-4">
              <h4 className="text-sm font-semibold flex items-center gap-1">
                <CreditCard className="h-4 w-4" />
                关联交易 ({transactions.length}笔)
              </h4>
              
              <div className="border rounded-md overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-3 py-2 text-left text-xs font-medium">日期</th>
                        <th className="px-3 py-2 text-left text-xs font-medium">描述</th>
                        <th className="px-3 py-2 text-right text-xs font-medium">金额</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transactions.slice(0, 10).map((transaction) => (
                        <tr key={transaction.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-3 py-2 text-xs whitespace-nowrap">
                            {new Date(transaction.htime * 1000).toLocaleDateString('zh-CN')}
                          </td>
                          <td className="px-3 py-2 text-xs max-w-[200px] truncate">
                            {transaction.description || '-'}
                          </td>
                          <td className="px-3 py-2 text-xs text-right font-medium">
                            {new Money(transaction.value).format()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {transactions.length > 10 && (
                  <div className="px-3 py-2 text-xs text-muted-foreground text-center border-t">
                    还有 {transactions.length - 10} 笔交易...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            关闭
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default BudgetDetailDialog
