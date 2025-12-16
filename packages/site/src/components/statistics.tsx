import React, { useState, useEffect } from 'react'
import { useTransactionsStore } from '@lib/store'
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from '@/components/ui/chart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LineChart, Line, XAxis, YAxis } from 'recharts'
import { useIsMobile } from '@/hooks/use-mobile'
import { api_get_transactions_stats } from '@lib/api'
import type { TransactionDataStatsRequest } from '@lib/data/money'
import { Money } from '@lib/utils/money'
type TimeRange = 'monthly' | 'quarterly' | 'yearly'

interface TagStatistic {
  tag: string
  amount: Money
  count: number
  color: string
}

interface TimeSeriesData {
  period: string
  [key: string]: string | number
}

// Helper function to get start and end timestamps for a period
const getPeriodRange = (year: number, month?: number, quarter?: number): { from: number; to: number } => {
  let startDate: Date
  let endDate: Date

  if (month !== undefined) {
    // Monthly range
    startDate = new Date(year, month - 1, 1)
    endDate = new Date(year, month, 0, 23, 59, 59, 999)
  } else if (quarter !== undefined) {
    // Quarterly range
    const startMonth = (quarter - 1) * 3
    startDate = new Date(year, startMonth, 1)
    endDate = new Date(year, startMonth + 3, 0, 23, 59, 59, 999)
  } else {
    // Yearly range
    startDate = new Date(year, 0, 1)
    endDate = new Date(year, 11, 31, 23, 59, 59, 999)
  }

  return {
    from: Math.floor(startDate.getTime() / 1000),
    to: Math.floor(endDate.getTime() / 1000),
  }
}

// Generate periods based on time range
const generatePeriods = (timeRange: TimeRange, numPeriods: number = 12): Array<{ key: string; from: number; to: number }> => {
  const now = new Date()
  const currentYear = now.getFullYear()
  const currentMonth = now.getMonth() + 1
  const periods: Array<{ key: string; from: number; to: number }> = []

  switch (timeRange) {
    case 'monthly':
      for (let i = numPeriods - 1; i >= 0; i--) {
        const date = new Date(currentYear, currentMonth - 1 - i, 1)
        const year = date.getFullYear()
        const month = date.getMonth() + 1
        const key = `${year}-${String(month).padStart(2, '0')}`
        periods.push({ key, ...getPeriodRange(year, month) })
      }
      break
    case 'quarterly':
      for (let i = 7; i >= 0; i--) {
        const currentQuarter = Math.ceil(currentMonth / 3)
        const quarterOffset = currentQuarter - 1 - i
        const year = currentYear + Math.floor(quarterOffset / 4)
        const quarter = ((currentQuarter - 1 - i) % 4 + 4) % 4 + 1
        const key = `${year}-Q${quarter}`
        periods.push({ key, ...getPeriodRange(year, undefined, quarter) })
      }
      break
    case 'yearly':
      for (let i = 4; i >= 0; i--) {
        const year = currentYear - i
        const key = `${year}`
        periods.push({ key, ...getPeriodRange(year) })
      }
      break
  }

  return periods
}

const Statistics: React.FC = () => {
  const getSupportedTags = useTransactionsStore((state) => state.getSupportedTags)
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>('monthly')
  const [loading, setLoading] = useState(false)
  const [tagStats, setTagStats] = useState<TagStatistic[]>([])
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData[]>([])
  const isMobile = useIsMobile()

  const supportedTags = getSupportedTags()
  const regularTags = supportedTags.filter((tag) => tag !== '大宗收支')

  // Color mapping for tags
  const tagColors: Record<string, string> = {
    零食: '#8884d8',
    交通: '#82ca9d',
    日用消耗: '#ffc658',
    大宗电器: '#ff7300',
    娱乐休闲: '#00ff00',
    人际交往: '#ff00ff',
    医药健康: '#00ffff',
    衣物: '#ff0080',
    大宗收支: '#8000ff',
  }

  // Fetch statistics data from backend
  useEffect(() => {
    const fetchStatistics = async () => {
      setLoading(true)
      try {
        const periods = generatePeriods(selectedTimeRange)
        const timeSeriesResults: TimeSeriesData[] = []

        // Fetch data for each period for each tag
        for (const period of periods) {
          const periodData: TimeSeriesData = { period: period.key }

          // Fetch stats for each regular tag in this period
          for (const tag of regularTags) {
            const request: TransactionDataStatsRequest = {
              tags: [tag],
              tag_op: 'or',
              return_list: false,
              from_time: period.from,
              to_time: period.to,
            }
            const stats = await api_get_transactions_stats(request)
            periodData[tag] = new Money(stats.expense_total).value
          }

          timeSeriesResults.push(periodData)
        }

        setTimeSeriesData(timeSeriesResults)

        // Calculate total stats for each tag across all periods
        const tagStatsMap = new Map<string, { amount: Money; count: number }>()
        
        for (const tag of regularTags) {
          const request: TransactionDataStatsRequest = {
            tags: [tag],
            tag_op: 'or',
            return_list: false,
            from_time: periods[0].from,
            to_time: periods[periods.length - 1].to,
          }
          // console.log(request)
          const stats = await api_get_transactions_stats(request)
          // console.log(stats)
          tagStatsMap.set(tag, {
            amount: new Money(stats.expense_total),
            count: stats.expense_count,
          })
        }

        // Convert to tag statistics
        const tagStatsArray: TagStatistic[] = regularTags
          .map((tag) => {
            const stats = tagStatsMap.get(tag) || { amount: new Money(0), count: 0 }
            return {
              tag,
              amount: stats.amount,
              count: stats.count,
              color: tagColors[tag] || '#888888',
            }
          })
          .filter((stat) => stat.amount.value > 0)
          .sort((a, b) => b.amount.compare(a.amount))

        setTagStats(tagStatsArray)
      } catch (error) {
        console.error('Failed to fetch statistics:', error)
      } finally {
        setLoading(false)
      }
    }

    if (supportedTags.length > 0) {
      fetchStatistics()
    }
  }, [selectedTimeRange, supportedTags.join(',')])

  const chartConfig = supportedTags.reduce(
    (config, tag) => {
      config[tag] = {
        label: tag,
        color: tagColors[tag] || '#888888',
      }
      return config
    },
    {} as Record<string, { label: string; color: string }>
  )

  const regularTagStats = tagStats

  if (loading) {
    return (
      <div className={`flex flex-col gap-4 ${isMobile ? 'px-2' : ''}`}>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">加载统计数据中...</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-4 ${isMobile ? 'px-2' : ''}`}>
      <Card>
        <CardHeader className={`${isMobile ? 'px-4 py-3' : ''}`}>
          <CardTitle className={`${isMobile ? 'text-lg' : ''}`}>消费统计</CardTitle>
          <CardDescription className={`${isMobile ? 'text-sm' : ''}`}>按标签统计各时期的消费情况</CardDescription>
          <div className="flex gap-2">
            <Select value={selectedTimeRange} onValueChange={(value: TimeRange) => setSelectedTimeRange(value)}>
              <SelectTrigger className={`${isMobile ? 'w-[100px] h-8 text-sm' : 'w-[120px]'}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">按月</SelectItem>
                <SelectItem value="quarterly">按季度</SelectItem>
                <SelectItem value="yearly">按年</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
      </Card>

      {tagStats.length > 0 ? (
        <>
          <div className="flex flex-row justify-center">
            <Card>
              <CardHeader>
                <CardTitle>日常消费趋势线</CardTitle>
                <CardDescription>主要日常消费标签的变化趋势（不含大宗收支）</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer config={chartConfig} className="h-[300px]">
                  <LineChart data={timeSeriesData}>
                    <XAxis dataKey="period" />
                    <YAxis tickFormatter={(value) => new Money(value).toFormattedString()} />

                    {regularTagStats.slice(0, 5).map(({ tag }) => (
                      <Line key={tag} type="monotone" dataKey={tag} stroke={tagColors[tag]} strokeWidth={2} dot={{ r: 4 }} />
                    ))}

                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(_value, _name) => {
                            const value = _value as number
                            const money = new Money(value)
                            return (
                              <div>
                                <div>
                                  {_name}:{money.toFormattedString()}
                                </div>
                              </div>
                            )
                          }}
                        />
                      }
                    />
                    <ChartLegend content={<ChartLegendContent />} />
                  </LineChart>
                </ChartContainer>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>日常消费详情</CardTitle>
              <CardDescription>日常消费各标签详细统计（不含大宗收支）</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {regularTagStats.slice(0, 6).map((stat) => (
                  <div key={stat.tag} className="flex flex-col items-center p-3 border rounded-lg">
                    <div className="w-4 h-4 rounded-full mb-2" style={{ backgroundColor: stat.color }} />
                    <div className="text-sm font-medium">{stat.tag}</div>
                    <div className="text-lg font-bold">{stat.amount.toFormattedString()}</div>
                    <div className="text-xs text-muted-foreground">{stat.count} 笔交易</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground">暂无消费数据</div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default Statistics
