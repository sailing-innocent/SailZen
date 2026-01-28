import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useTransactionsStore } from '@lib/store'
import { ChartContainer, ChartTooltip, ChartTooltipContent, ChartLegend, ChartLegendContent } from '@/components/ui/chart'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { LineChart, Line, XAxis, YAxis } from 'recharts'
import { useIsMobile } from '@/hooks/use-mobile'
import { LazyChart } from '@/components/lazy_chart'
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

// 性能优化：将静态配置移到组件外部，避免每次渲染都创建新对象
const TAG_COLORS: Record<string, string> = {
  零食: '#8884d8',
  交通: '#82ca9d',
  日用消耗: '#ffc658',
  大宗电器: '#ff7300',
  娱乐休闲: '#00ff00',
  人际交往: '#ff00ff',
  医药健康: '#00ffff',
  衣物: '#ff0080',
  大宗收支: '#8000ff',
  总支出: '#ff0000',
}

const Statistics: React.FC = () => {
  const getSupportedTags = useTransactionsStore((state) => state.getSupportedTags)
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>('monthly')
  const [loading, setLoading] = useState(false)
  const [tagStats, setTagStats] = useState<TagStatistic[]>([])
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData[]>([])
  const [majorTagStats, setMajorTagStats] = useState<TagStatistic[]>([])
  const [overallExpenseData, setOverallExpenseData] = useState<TimeSeriesData[]>([])
  const isMobile = useIsMobile()

  // 性能优化：缓存 tooltip formatter，避免每次渲染都创建新函数
  const moneyTooltipFormatter = useCallback((_value: any, _name: any) => {
    const value = _value as number
    const money = new Money(value)
    return (
      <div>
        <div>
          {_name}:{money.toFormattedString()}
        </div>
      </div>
    )
  }, [])

  // 性能优化：缓存 Y 轴格式化函数
  const yAxisFormatter = useCallback((value: number) => new Money(value).toFormattedString(), [])

  // Fetch statistics data from backend
  useEffect(() => {
    const fetchStatistics = async () => {
      // Recalculate tags inside effect to ensure they're up to date
      const currentSupportedTags = getSupportedTags()
      const currentRegularTags = currentSupportedTags.filter((tag) => tag !== '大宗收支')
      const currentMajorTags = ['大宗收支', '大宗电器'].filter((tag) => currentSupportedTags.includes(tag))

      if (currentSupportedTags.length === 0) {
        return
      }

      setLoading(true)
      try {
        const periods = generatePeriods(selectedTimeRange)
        const overallFromTime = periods[0].from
        const overallToTime = periods[periods.length - 1].to

        // Prepare all requests upfront for concurrent execution
        const allRequests: Array<{
          key: string
          periodKey?: string
          request: TransactionDataStatsRequest
        }> = []

        // Add requests for time series data (each period for each tag)
        for (const period of periods) {
          // Regular tags for this period
          for (const tag of currentRegularTags) {
            allRequests.push({
              key: `regular-${period.key}-${tag}`,
              periodKey: period.key,
              request: {
                tags: [tag],
                tag_op: 'or',
                return_list: false,
                from_time: period.from,
                to_time: period.to,
              },
            })
          }

          // Total expense for this period
          allRequests.push({
            key: `total-${period.key}`,
            periodKey: period.key,
            request: {
              return_list: false,
              from_time: period.from,
              to_time: period.to,
            },
          })

          // Major tags for this period
          for (const tag of currentMajorTags) {
            allRequests.push({
              key: `major-${period.key}-${tag}`,
              periodKey: period.key,
              request: {
                tags: [tag],
                tag_op: 'or',
                return_list: false,
                from_time: period.from,
                to_time: period.to,
              },
            })
          }

          // Daily expense (日用消耗 excluding 大宗收支) for this period
          if (currentRegularTags.includes('日用消耗')) {
            allRequests.push({
              key: `daily-${period.key}`,
              periodKey: period.key,
              request: {
                tags: ['日用消耗'],
                tag_op: 'or',
                return_list: false,
                from_time: period.from,
                to_time: period.to,
              },
            })
          }
        }

        // Add requests for overall stats (across all periods)
        for (const tag of currentRegularTags) {
          allRequests.push({
            key: `overall-regular-${tag}`,
            request: {
              tags: [tag],
              tag_op: 'or',
              return_list: false,
              from_time: overallFromTime,
              to_time: overallToTime,
            },
          })
        }

        for (const tag of currentMajorTags) {
          allRequests.push({
            key: `overall-major-${tag}`,
            request: {
              tags: [tag],
              tag_op: 'or',
              return_list: false,
              from_time: overallFromTime,
              to_time: overallToTime,
            },
          })
        }

        // Execute all requests concurrently
        const results = await Promise.all(
          allRequests.map(async ({ key, request }) => {
            try {
              const stats = await api_get_transactions_stats(request)
              return { key, stats }
            } catch (error) {
              console.error(`Failed to fetch stats for ${key}:`, error)
              return { key, stats: null }
            }
          })
        )

        // Process results into data structures
        const resultsMap = new Map<string, any>()
        results.forEach(({ key, stats }) => {
          if (stats) {
            resultsMap.set(key, stats)
          }
        })

        // Build time series data
        const timeSeriesResults: TimeSeriesData[] = periods.map((period) => {
          const periodData: TimeSeriesData = { period: period.key }
          for (const tag of currentRegularTags) {
            const key = `regular-${period.key}-${tag}`
            const stats = resultsMap.get(key)
            periodData[tag] = stats ? new Money(stats.expense_total).value : 0
          }
          return periodData
        })

        // Build combined expense data (支出总体 + 日常零碎支出 + 大宗收支 + 大宗电器)
        const combinedExpenseResults: TimeSeriesData[] = periods.map((period) => {
          const combinedData: TimeSeriesData = { period: period.key }

          // 支出总体 (总支出)
          const totalKey = `total-${period.key}`
          const totalStats = resultsMap.get(totalKey)
          combinedData['支出总体'] = totalStats ? new Money(totalStats.expense_total).value : 0

          // 日常零碎支出 (日用消耗 excluding 大宗收支)
          if (currentRegularTags.includes('日用消耗')) {
            const dailyKey = `daily-${period.key}`
            const dailyStats = resultsMap.get(dailyKey)
            combinedData['日常零碎支出'] = dailyStats ? new Money(dailyStats.expense_total).value : 0
          } else {
            combinedData['日常零碎支出'] = 0
          }

          // 大宗收支
          const majorIncomeKey = `major-${period.key}-大宗收支`
          const majorIncomeStats = resultsMap.get(majorIncomeKey)
          combinedData['大宗收支'] = majorIncomeStats ? new Money(majorIncomeStats.expense_total).value : 0

          // 大宗电器
          const majorApplianceKey = `major-${period.key}-大宗电器`
          const majorApplianceStats = resultsMap.get(majorApplianceKey)
          combinedData['大宗电器'] = majorApplianceStats ? new Money(majorApplianceStats.expense_total).value : 0

          return combinedData
        })

        setTimeSeriesData(timeSeriesResults)
        setOverallExpenseData(combinedExpenseResults)

        // Build tag statistics
        const tagStatsArray: TagStatistic[] = currentRegularTags
          .map((tag) => {
            const key = `overall-regular-${tag}`
            const stats = resultsMap.get(key)
            if (!stats) {
              return null
            }
            return {
              tag,
              amount: new Money(stats.expense_total),
              count: stats.expense_count,
              color: TAG_COLORS[tag] || '#888888',
            }
          })
          .filter((stat): stat is TagStatistic => stat !== null && stat.amount.value > 0)
          .sort((a, b) => b.amount.compare(a.amount))

        const majorTagStatsArray: TagStatistic[] = currentMajorTags
          .map((tag) => {
            const key = `overall-major-${tag}`
            const stats = resultsMap.get(key)
            if (!stats) {
              return null
            }
            return {
              tag,
              amount: new Money(stats.expense_total),
              count: stats.expense_count,
              color: TAG_COLORS[tag] || '#888888',
            }
          })
          .filter((stat): stat is TagStatistic => stat !== null && stat.amount.value > 0)
          .sort((a, b) => b.amount.compare(a.amount))

        setTagStats(tagStatsArray)
        setMajorTagStats(majorTagStatsArray)
      } catch (error) {
        console.error('Failed to fetch statistics:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchStatistics()
  }, [selectedTimeRange, getSupportedTags])

  // Build chart config dynamically based on available tags
  const chartConfig = React.useMemo(() => {
    const supportedTags = getSupportedTags()
    const config: Record<string, { label: string; color: string }> = {}
    
    supportedTags.forEach((tag) => {
      config[tag] = {
        label: tag,
        color: TAG_COLORS[tag] || '#888888',
      }
    })
    
    // Add total expense to chart config
    config['总支出'] = {
      label: '总支出',
      color: TAG_COLORS['总支出'] || '#ff0000',
    }
    
    // Add overall expense and daily expense to chart config
    config['支出总体'] = {
      label: '支出总体',
      color: '#ff0000',
    }
    
    config['日常零碎支出'] = {
      label: '日常零碎支出',
      color: '#ffc658',
    }
    
    // Add major tags to chart config
    config['大宗收支'] = {
      label: '大宗收支',
      color: TAG_COLORS['大宗收支'] || '#8000ff',
    }
    
    config['大宗电器'] = {
      label: '大宗电器',
      color: TAG_COLORS['大宗电器'] || '#ff7300',
    }
    
    return config
  }, [getSupportedTags])

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

      {overallExpenseData.length > 0 || tagStats.length > 0 ? (
        <>
          {/* Combined Expense Chart and Regular Tags Chart - Side by Side */}
          <div className={`flex ${isMobile ? 'flex-col' : 'flex-row'} gap-4 justify-center`}>
            {/* Combined Expense Chart (支出总体 + 日常零碎支出 + 大宗收支 + 大宗电器) */}
            {overallExpenseData.length > 0 && (
              <Card className={isMobile ? 'w-full' : 'flex-1'}>
                <CardHeader>
                  <CardTitle>支出总体趋势</CardTitle>
                  <CardDescription>支出总体、日常零碎支出、大宗收支、大宗电器的合并趋势</CardDescription>
                </CardHeader>
                <CardContent>
                  {/* 性能优化：使用 LazyChart 懒加载图表 */}
                  <LazyChart height={300} loadingText="支出趋势图加载中...">
                    <ChartContainer config={chartConfig} className="h-[300px]">
                      <LineChart data={overallExpenseData}>
                        <XAxis dataKey="period" />
                        <YAxis tickFormatter={yAxisFormatter} />

                        <Line
                          key="支出总体"
                          type="monotone"
                          dataKey="支出总体"
                          stroke="#ff0000"
                          strokeWidth={2}
                          dot={{ r: 4 }}
                        />
                        <Line
                          key="日常零碎支出"
                          type="monotone"
                          dataKey="日常零碎支出"
                          stroke="#ffc658"
                          strokeWidth={2}
                          dot={{ r: 4 }}
                        />
                        <Line
                          key="大宗收支"
                          type="monotone"
                          dataKey="大宗收支"
                          stroke={TAG_COLORS['大宗收支'] || '#8000ff'}
                          strokeWidth={2}
                          dot={{ r: 4 }}
                        />
                        <Line
                          key="大宗电器"
                          type="monotone"
                          dataKey="大宗电器"
                          stroke={TAG_COLORS['大宗电器'] || '#ff7300'}
                          strokeWidth={2}
                          dot={{ r: 4 }}
                        />

                        <ChartTooltip
                          content={
                            <ChartTooltipContent formatter={moneyTooltipFormatter} />
                          }
                        />
                        <ChartLegend content={ChartLegendContent} />
                      </LineChart>
                    </ChartContainer>
                  </LazyChart>
                </CardContent>
              </Card>
            )}

            {/* Regular Tags Chart */}
            {tagStats.length > 0 && (
              <Card className={isMobile ? 'w-full' : 'flex-1'}>
                <CardHeader>
                  <CardTitle>日常消费趋势线</CardTitle>
                  <CardDescription>主要日常消费标签的变化趋势（不含大宗收支）</CardDescription>
                </CardHeader>
                <CardContent>
                  {/* 性能优化：使用 LazyChart 懒加载图表 */}
                  <LazyChart height={300} loadingText="消费趋势图加载中...">
                    <ChartContainer config={chartConfig} className="h-[300px]">
                      <LineChart data={timeSeriesData}>
                        <XAxis dataKey="period" />
                        <YAxis tickFormatter={yAxisFormatter} />

                        {regularTagStats.slice(0, 5).map(({ tag }) => (
                          <Line key={tag} type="monotone" dataKey={tag} stroke={TAG_COLORS[tag]} strokeWidth={2} dot={{ r: 4 }} />
                        ))}

                        <ChartTooltip
                          content={
                            <ChartTooltipContent formatter={moneyTooltipFormatter} />
                          }
                        />
                        <ChartLegend content={ChartLegendContent} />
                      </LineChart>
                    </ChartContainer>
                  </LazyChart>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Major Items Details */}
          {majorTagStats.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>大宗项目详情</CardTitle>
                <CardDescription>大宗收支和大宗电器的详细统计</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {majorTagStats.map((stat) => (
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
          )}


          {/* Regular Tags Details */}
          {tagStats.length > 0 && (
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
          )}
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
