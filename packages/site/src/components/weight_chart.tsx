import React, { useMemo, useCallback, useEffect } from 'react'
import { type HealthState, useHealthStore } from '@lib/store/health'
import { Line, LineChart, CartesianGrid, XAxis, YAxis, ResponsiveContainer, ComposedChart } from 'recharts'
import { type ChartConfig, ChartContainer, ChartTooltip } from '@components/ui/chart'
import { useIsMobile } from '@/hooks/use-mobile'

// Chart configuration
const chartConfig: ChartConfig = {
  actual: {
    label: 'Actual Weight',
    color: '#2563eb',
  },
  predicted: {
    label: 'Predicted Trend',
    color: '#10b981',
  },
  plan: {
    label: 'Plan Target',
    color: '#f59e0b',
  },
  above: {
    label: 'Above Target',
    color: '#ef4444',
  },
  below: {
    label: 'Below Target',
    color: '#22c55e',
  },
}

interface ChartDataPoint {
  timestamp: number
  value?: number
  status?: 'above' | 'below' | 'normal'
  expectedValue?: number
  diff?: number
  predicted?: number
  planExpected?: number
}

const WeightChart: React.FC = () => {
  const isLoading = useHealthStore((state: HealthState) => state.isLoading)
  const analysisResult = useHealthStore((state: HealthState) => state.analysisResult)
  const dailyPredictions = useHealthStore((state: HealthState) => state.dailyPredictions)
  const weightPlan = useHealthStore((state: HealthState) => state.weightPlan)
  const isOnTrack = useHealthStore((state: HealthState) => state.isOnTrack)
  const controlRate = useHealthStore((state: HealthState) => state.controlRate)
  const weightsWithStatus = useHealthStore((state: HealthState) => state.weightsWithStatus)
  const fetchWeightAnalysis = useHealthStore((state: HealthState) => state.fetchWeightAnalysis)
  const fetchPlanProgress = useHealthStore((state: HealthState) => state.fetchPlanProgress)
  const isMobile = useIsMobile()

  // Fetch plan progress on mount
  useEffect(() => {
    fetchPlanProgress()
  }, [])

  // Fetch analysis when weights change
  useEffect(() => {
    if (weightsWithStatus.length > 0) {
      const startTime = weightsWithStatus[0]?.htime
      const endTime = weightsWithStatus[weightsWithStatus.length - 1]?.htime
      fetchWeightAnalysis(startTime, endTime, 'linear')
    }
  }, [weightsWithStatus.length])

  // Build chart data combining actual weights with status, predictions, and plan
  const chartData = useMemo(() => {
    const data: ChartDataPoint[] = []
    
    // Add actual weight points with status
    weightsWithStatus.forEach((w) => {
      const timestamp = w.htime * 1000
      data.push({
        timestamp,
        value: w.value,
        status: w.status,
        expectedValue: w.expected_value,
        diff: w.diff,
      })
    })

    // Add predicted points from analysis (future predictions)
    if (analysisResult?.predicted_weights) {
      analysisResult.predicted_weights.forEach((p) => {
        if (!p.is_actual) {
          const timestamp = p.htime * 1000
          // Check if this point already exists
          const existing = data.find((d) => Math.abs(d.timestamp - timestamp) < 86400000)
          if (existing) {
            existing.predicted = p.value
          } else {
            data.push({
              timestamp,
              predicted: p.value,
            })
          }
        }
      })
    }

    // Add plan expected weights
    if (dailyPredictions?.length > 0) {
      dailyPredictions.forEach((d) => {
        const timestamp = d.htime * 1000
        const existing = data.find((item) => Math.abs(item.timestamp - timestamp) < 86400000)
        if (existing) {
          existing.planExpected = d.expected_weight
        } else {
          data.push({
            timestamp,
            planExpected: d.expected_weight,
          })
        }
      })
    }

    // Sort by timestamp
    return data.sort((a, b) => a.timestamp - b.timestamp)
  }, [weightsWithStatus, analysisResult, dailyPredictions])

  // Get color based on status
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'above':
        return '#ef4444' // Red - above expected
      case 'below':
        return '#22c55e' // Green - below expected
      case 'normal':
      default:
        return '#2563eb' // Blue - within tolerance
    }
  }

  // Custom tooltip content
  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload || payload.length === 0) return null
    
    const data = payload[0]?.payload as ChartDataPoint
    if (!data) return null
    
    const date = new Date(data.timestamp).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
    
    const statusText: Record<string, string> = {
      above: ' (Above expected)',
      below: ' (Below expected)',
      normal: '',
    }
    
    return (
      <div className="bg-white dark:bg-gray-800 border rounded-lg p-3 shadow-lg">
        <div className="text-muted-foreground text-xs mb-1">{date}</div>
        
        {/* Actual Weight */}
        {data.value !== undefined && (
          <div className="font-semibold">
            Actual: {data.value.toFixed(1)} kg
            {data.status && (
              <span className={`text-xs ml-1 ${data.status === 'above' ? 'text-red-500' : data.status === 'below' ? 'text-green-500' : 'text-blue-500'}`}>
                {statusText[data.status]}
              </span>
            )}
          </div>
        )}
        
        {/* Expected Value */}
        {data.expectedValue !== undefined && data.expectedValue > 0 && (
          <div className="text-xs text-gray-500 mt-1">
            Expected: {data.expectedValue.toFixed(1)} kg
            {data.diff !== undefined && (
              <span className={data.diff > 0 ? 'text-red-500' : 'text-green-500'}>
                {' '}({data.diff > 0 ? '+' : ''}{data.diff.toFixed(1)})
              </span>
            )}
          </div>
        )}
        
        {/* Predicted */}
        {data.predicted !== undefined && (
          <div className="text-xs text-green-600 mt-1">
            Predicted: {data.predicted.toFixed(1)} kg
          </div>
        )}
        
        {/* Plan Target */}
        {data.planExpected !== undefined && (
          <div className="text-xs text-amber-600 mt-1">
            Plan Target: {data.planExpected.toFixed(1)} kg
          </div>
        )}
      </div>
    )
  }

  // Calculate Y domain
  const yDomain = useMemo(() => {
    if (chartData.length === 0) return ['auto', 'auto']
    
    const allValues = chartData.flatMap((d) => [
      d.value,
      d.predicted,
      d.planExpected,
    ]).filter((v): v is number => v !== undefined)
    
    if (allValues.length === 0) return ['auto', 'auto']
    
    const min = Math.min(...allValues)
    const max = Math.max(...allValues)
    return [min - 5, max + 5]
  }, [chartData])

  // Trend info
  const trendInfo = useMemo(() => {
    if (!analysisResult) return null
    const { slope, current_trend, r_squared } = analysisResult
    const dailyChange = Math.abs(slope)
    const weeklyChange = dailyChange * 7
    
    return {
      direction: current_trend,
      weeklyChange,
      rSquared: r_squared,
    }
  }, [analysisResult])

  return (
    <div className="flex flex-col items-center justify-center w-full">
      <div className="flex items-center justify-between w-full mb-4">
        <h2 className={`font-bold ${isMobile ? 'text-lg' : 'text-xl'}`}>Weight Chart</h2>
        
        {/* Analysis Summary */}
        {weightPlan && (
          <div className={`text-right ${isMobile ? 'text-xs' : 'text-sm'}`}>
            <div className="flex items-center gap-2">
              <span>Plan Control:</span>
              <span className={`font-semibold ${isOnTrack ? 'text-green-500' : 'text-red-500'}`}>
                {controlRate.toFixed(0)}%
              </span>
            </div>
            <div className="text-gray-500">
              Target: {weightPlan.target_weight}kg by {new Date(weightPlan.target_time * 1000).toLocaleDateString()}
            </div>
          </div>
        )}
      </div>

      {/* Trend Badge */}
      {trendInfo && (
        <div className={`flex gap-4 mb-4 ${isMobile ? 'text-xs' : 'text-sm'}`}>
          <div className="px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900">
            <span className="text-blue-800 dark:text-blue-200">
              Trend: {trendInfo.direction}
            </span>
          </div>
          <div className="px-3 py-1 rounded-full bg-green-100 dark:bg-green-900">
            <span className="text-green-800 dark:text-green-200">
              Weekly Δ: {trendInfo.weeklyChange.toFixed(2)} kg
            </span>
          </div>
          <div className="px-3 py-1 rounded-full bg-gray-100 dark:bg-gray-800">
            <span className="text-gray-800 dark:text-gray-200">
              R²: {trendInfo.rSquared.toFixed(3)}
            </span>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="w-full space-y-3">Loading...</div>
      ) : weightsWithStatus.length > 0 ? (
        <div className="w-full">
          <ChartContainer
            config={chartConfig}
            className={`${isMobile ? 'h-[250px]' : 'h-[350px]'} w-full max-w-full !aspect-auto overflow-hidden [&_.recharts-responsive-container]:!w-full`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                margin={
                  isMobile
                    ? { right: 10, left: 10, top: 10, bottom: 10 }
                    : { right: 30, left: 30, top: 20, bottom: 20 }
                }
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  domain={['dataMin - 86400000', 'dataMax + 86400000']}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={isMobile ? 50 : 32}
                  tickMargin={8}
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return isMobile
                      ? `${date.getMonth() + 1}/${date.getDate()}`
                      : date.toLocaleDateString()
                  }}
                  scale="time"
                  tick={{ fontSize: isMobile ? 10 : 12 }}
                />
                <YAxis
                  domain={yDomain}
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  tick={{ fontSize: isMobile ? 10 : 12 }}
                  width={isMobile ? 35 : 45}
                />

                {/* Plan Target Line */}
                {dailyPredictions.length > 0 && (
                  <Line
                    type="monotone"
                    dataKey="planExpected"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="Plan Target"
                  />
                )}

                {/* Predicted Trend Line */}
                <Line
                  type="monotone"
                  dataKey="predicted"
                  stroke="#10b981"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Predicted"
                />

                {/* Actual Weight Points with status-based colors */}
                {chartData.map((point, index) => {
                  if (point.value === undefined) return null
                  const color = getStatusColor(point.status)
                  return (
                    <Line
                      key={`point-${index}`}
                      data={[point]}
                      type="monotone"
                      dataKey="value"
                      stroke="transparent"
                      dot={{
                        r: isMobile ? 4 : 5,
                        fill: color,
                        stroke: color,
                        strokeWidth: 2,
                      }}
                      isAnimationActive={false}
                    />
                  )
                })}

                {/* Connect points with a line (use blue as default line color) */}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#2563eb"
                  strokeWidth={isMobile ? 1.5 : 2}
                  dot={false}
                  name="Actual"
                />

                <ChartTooltip content={<CustomTooltip />} />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartContainer>

          {/* Legend */}
          <div className={`flex flex-wrap justify-center gap-3 mt-4 ${isMobile ? 'text-xs' : 'text-sm'}`}>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span>On Target</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span>Above Expected</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span>Below Expected</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-green-500 opacity-50" style={{ background: '#10b981' }} />
              <span>Predicted</span>
            </div>
            {dailyPredictions.length > 0 && (
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span>Plan Target</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div>No weight data available.</div>
      )}
    </div>
  )
}

export default WeightChart
