import React, { useEffect, useState } from 'react'
import { useBudgetsStore, type BudgetsState } from '@lib/store'
import { type BudgetData, type BudgetAnalysis } from '@lib/data/money'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useIsMobile } from '@/hooks/use-mobile'
import { Money } from '@lib/utils/money'
import { Progress } from '@components/ui/progress'

interface BudgetAnalysisCardProps {
  budgetId: number
}

const BudgetAnalysisCard: React.FC<BudgetAnalysisCardProps> = ({ budgetId }) => {
  const getBudgetAnalysis = useBudgetsStore((state: BudgetsState) => state.getBudgetAnalysis)
  const [analysis, setAnalysis] = useState<BudgetAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const isMobile = useIsMobile()

  useEffect(() => {
    const fetchAnalysis = async () => {
      setLoading(true)
      try {
        const result = await getBudgetAnalysis(budgetId)
        setAnalysis(result)
      } catch (error) {
        console.error('Error fetching budget analysis:', error)
      } finally {
        setLoading(false)
      }
    }
    if (budgetId > 0) {
      fetchAnalysis()
    }
  }, [budgetId, getBudgetAnalysis])

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent className="p-6">
          <div className="text-center">正在加载分析数据...</div>
        </CardContent>
      </Card>
    )
  }

  if (!analysis) {
    return (
      <Card className="w-full">
        <CardContent className="p-6">
          <div className="text-center text-muted-foreground">暂无分析数据</div>
        </CardContent>
      </Card>
    )
  }

  const usedAmount = new Money(analysis.used_amount)
  const budgetAmount = new Money(analysis.budget.amount)
  const remainingAmount = new Money(analysis.remaining_amount)
  const usagePercentage = analysis.usage_percentage

  return (
    <Card className="w-full">
      <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
        <CardTitle className={`${isMobile ? 'text-lg' : 'text-xl'}`}>
          预算分析: {analysis.budget.name}
        </CardTitle>
        <CardDescription>预算执行情况详细分析</CardDescription>
      </CardHeader>
      <CardContent className={`${isMobile ? 'px-4 py-3' : ''}`}>
        <div className="space-y-4">
          {/* 预算概览 */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">预算金额</div>
              <div className="text-lg font-semibold">{budgetAmount.format()}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">已使用</div>
              <div className="text-lg font-semibold">{usedAmount.format()}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">剩余</div>
              <div className="text-lg font-semibold">{remainingAmount.format()}</div>
            </div>
          </div>

          {/* 使用率进度条 */}
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span>使用率</span>
              <span>{usagePercentage.toFixed(1)}%</span>
            </div>
            <Progress value={usagePercentage} className="h-2" />
          </div>

          {/* 按标签统计 */}
          {Object.keys(analysis.by_tag).length > 0 && (
            <div>
              <div className="text-sm font-semibold mb-2">按标签统计</div>
              <div className="space-y-2">
                {Object.entries(analysis.by_tag).map(([tag, stats]) => (
                  <div key={tag} className="flex justify-between items-center">
                    <span className="text-sm">{tag}</span>
                    <div className="text-sm">
                      <span className="font-semibold">{new Money(stats.amount).format()}</span>
                      <span className="text-muted-foreground ml-2">({stats.count}笔)</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 交易记录 */}
          {analysis.transactions.length > 0 && (
            <div>
              <div className="text-sm font-semibold mb-2">
                关联交易 ({analysis.transactions.length}笔)
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {analysis.transactions.slice(0, 10).map((transaction) => (
                  <div key={transaction.id} className="flex justify-between items-center text-sm">
                    <div className="flex-1">
                      <div>{transaction.description || '-'}</div>
                      <div className="text-muted-foreground text-xs">
                        {new Date(transaction.htime * 1000).toLocaleDateString('zh-CN')}
                      </div>
                    </div>
                    <div className="font-semibold">{new Money(transaction.value).format()}</div>
                  </div>
                ))}
                {analysis.transactions.length > 10 && (
                  <div className="text-xs text-muted-foreground text-center">
                    还有 {analysis.transactions.length - 10} 笔交易...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default BudgetAnalysisCard
