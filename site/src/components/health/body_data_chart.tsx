/**
 * @file body_data_chart.tsx
 * @brief Generic single-metric body data chart (通用身体数据曲线)
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 数据源: body_data store 的 /series + /analysis（按选中指标）。
 * metric == 'weight' 时额外叠加体重计划信息（planExpected 线 + above/below 状态点），
 * 数据来自 health store（/weight-plan/expected 与 /weight/with-status），计划逻辑不动。
 */

import React, { useMemo, useEffect, useState } from 'react'
import { Line, CartesianGrid, XAxis, YAxis, ResponsiveContainer, ComposedChart } from 'recharts'
import { type ChartConfig, ChartContainer, ChartTooltip } from '@components/ui/chart'
import { type HealthState, useHealthStore } from '@lib/store/health'
import { type BodyDataState, useBodyDataStore } from '@lib/store/body_data'
import { formatMetricValue } from '@lib/data/body_data'
import BodyMetricPicker from '@components/health/body_metric_picker'
import { useIsMobile } from '@/hooks/use-mobile'

// Chart configuration
const chartConfig: ChartConfig = {
  actual: {
    label: 'Actual',
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

const startOfDayMs = (ts: number): number => {
  const d = new Date(ts)
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}
const dayMs = 24 * 60 * 60 * 1000

interface BodyDataChartProps {
  /** 时间范围（Unix 秒），与页面日期选择联动 */
  startTime: number
  endTime: number
}

const BodyDataChart: React.FC<BodyDataChartProps> = ({ startTime, endTime }) => {
  const [metric, setMetric] = useState<string>('weight')
  const isMobile = useIsMobile()

  // body_data store
  const seriesCache = useBodyDataStore((state: BodyDataState) => state.seriesCache)
  const analysisResult = useBodyDataStore((state: BodyDataState) => state.analysisResult)
  const analysisMetric = useBodyDataStore((state: BodyDataState) => state.analysisMetric)
  const fetchSeries = useBodyDataStore((state: BodyDataState) => state.fetchSeries)
  const fetchAnalysis = useBodyDataStore((state: BodyDataState) => state.fetchAnalysis)
  const getMetricDef = useBodyDataStore((state: BodyDataState) => state.getMetricDef)

  // health store: only used for the weight plan overlay (metric == 'weight')
  const isLoading = useHealthStore((state: HealthState) => state.isLoading)
  const weightPlan = useHealthStore((state: HealthState) => state.weightPlan)
  const weightsWithStatus = useHealthStore((state: HealthState) => state.weightsWithStatus)
  const planExpectedPoints = useHealthStore((state: HealthState) => state.planExpectedPoints)

  const metricDef = getMetricDef(metric)
  const unit = metricDef?.unit ?? ''

  // Fetch series + analysis when metric or range changes
  useEffect(() => {
    fetchSeries(metric, startTime, endTime)
    fetchAnalysis(metric, 'linear', startTime, endTime)
  }, [metric, startTime, endTime, fetchSeries, fetchAnalysis])

  const isWeight = metric === 'weight'

  // Build chart data. Weight keeps the daily skeleton with plan overlay;
  // other metrics plot measured days + future predictions only.
  const chartData = useMemo(() => {
    const data: ChartDataPoint[] = []
    const predictedByDay = new Map<number, number>()
    if (analysisMetric === metric && analysisResult?.predicted_points) {
      analysisResult.predicted_points.forEach((p) => {
        if (!p.is_actual) {
          predictedByDay.set(startOfDayMs(p.htime * 1000), p.value)
        }
      })
    }

    if (isWeight) {
      const rangeStart = startOfDayMs(startTime * 1000)
      const rangeEnd = startOfDayMs(endTime * 1000)
      if (rangeEnd >= rangeStart) {
        for (let t = rangeStart; t <= rangeEnd; t += dayMs) {
          data.push({ timestamp: t })
        }
      }

      const weightByDay = new Map<number, typeof weightsWithStatus[0]>()
      weightsWithStatus.forEach((w) => {
        weightByDay.set(startOfDayMs(w.htime * 1000), w)
      })
      data.forEach((p) => {
        const w = weightByDay.get(p.timestamp)
        if (w) {
          p.value = w.value
          p.status = w.status
          p.expectedValue = w.expected_value
          p.diff = w.diff
        }
      })

      const expectedByDay = new Map<number, number>()
      planExpectedPoints.forEach((ep) => {
        expectedByDay.set(startOfDayMs(ep.htime * 1000), ep.expected_weight)
      })
      data.forEach((p) => {
        const expected = expectedByDay.get(p.timestamp)
        if (expected !== undefined) {
          p.planExpected = expected
        }
      })

      data.forEach((p) => {
        const predicted = predictedByDay.get(p.timestamp)
        if (predicted !== undefined) {
          p.predicted = predicted
        }
      })
      return data
    }

    // Generic metric: measured days from the series endpoint
    const series = seriesCache[metric]
    const valueByDay = new Map<number, number>()
    series?.points.forEach((point) => {
      valueByDay.set(startOfDayMs(point.htime * 1000), point.value)
    })

    const timestamps = new Set<number>([...valueByDay.keys(), ...predictedByDay.keys()])
    ;[...timestamps].sort((a, b) => a - b).forEach((t) => {
      const point: ChartDataPoint = { timestamp: t }
      const value = valueByDay.get(t)
      if (value !== undefined) point.value = value
      const predicted = predictedByDay.get(t)
      if (predicted !== undefined) point.predicted = predicted
      data.push(point)
    })
    return data
  }, [metric, isWeight, seriesCache, analysisMetric, analysisResult, weightsWithStatus, planExpectedPoints, startTime, endTime])

  const hasActualValues = chartData.some((d) => d.value !== undefined)

  const formatValue = (value: number): string =>
    unit ? `${formatMetricValue(metric, value)} ${unit}` : formatMetricValue(metric, value)

  // Get color based on status (weight plan overlay only)
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'above':
        return '#ef4444'
      case 'below':
        return '#22c55e'
      case 'normal':
      default:
        return '#2563eb'
    }
  }

  // Custom tooltip content
  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: any[] }) => {
    if (!active || !payload || payload.length === 0) return null

    const data = payload.find((p) => p && p.payload)?.payload as ChartDataPoint | undefined
    if (!data) return null

    const actualEntry = payload.find((p) => p.dataKey === 'value' || p.name === 'Actual')
    const predictedEntry = payload.find((p) => p.dataKey === 'predicted' || p.name === 'Predicted')
    const planEntry = payload.find((p) => p.dataKey === 'planExpected' || p.name === 'Plan Target')

    const actualValue = (actualEntry?.value as number | undefined) ?? data.value
    const predictedValue = (predictedEntry?.value as number | undefined) ?? data.predicted
    const planValue = (planEntry?.value as number | undefined) ?? data.planExpected

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
    const metricName = metricDef?.labelEn ?? metric

    return (
      <div className="bg-white dark:bg-gray-800 border rounded-lg p-3 shadow-lg">
        <div className="text-muted-foreground text-xs mb-1">{date}</div>

        {actualValue !== undefined && (
          <div className="font-semibold">
            {metricName}: {formatValue(actualValue)}
            {isWeight && data.status && (
              <span className={`text-xs ml-1 ${data.status === 'above' ? 'text-red-500' : data.status === 'below' ? 'text-green-500' : 'text-blue-500'}`}>
                {statusText[data.status]}
              </span>
            )}
          </div>
        )}

        {isWeight && data.expectedValue !== undefined && data.expectedValue > 0 && (
          <div className="text-xs text-gray-500 mt-1">
            Expected: {formatValue(data.expectedValue)}
            {data.diff !== undefined && (
              <span className={data.diff > 0 ? 'text-red-500' : 'text-green-500'}>
                {' '}({data.diff > 0 ? '+' : ''}{data.diff.toFixed(1)})
              </span>
            )}
          </div>
        )}

        {predictedValue !== undefined && (
          <div className="text-xs text-green-600 mt-1">
            Predicted: {formatValue(predictedValue)}
          </div>
        )}

        {planValue !== undefined && (
          <div className="text-xs text-amber-600 mt-1">
            Plan Target: {formatValue(planValue)}
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
    const pad = Math.max((max - min) * 0.1, isWeight ? 5 : 1)
    return [min - pad, max + pad]
  }, [chartData, isWeight])

  const trendInfo = useMemo(() => {
    if (analysisMetric !== metric || !analysisResult) return null
    const { slope, current_trend, r_squared } = analysisResult
    const weeklyChange = Math.abs(slope) * 7

    return {
      direction: current_trend,
      weeklyChange,
      rSquared: r_squared,
    }
  }, [metric, analysisMetric, analysisResult])

  const xDomain: [number, number] = [
    startOfDayMs(startTime * 1000),
    startOfDayMs(endTime * 1000),
  ]

  return (
    <div className="flex flex-col items-center justify-center w-full">
      <div className="flex items-center justify-between w-full mb-4 gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <h2 className={`font-bold ${isMobile ? 'text-lg' : 'text-xl'}`}>Body Data Chart</h2>
          <BodyMetricPicker
            value={metric}
            onChange={setMetric}
            className={isMobile ? 'w-36' : 'w-44'}
          />
        </div>
      </div>

      {/* Analysis Summary */}
      {trendInfo && (
        <div className={`flex gap-4 mb-4 ${isMobile ? 'text-xs' : 'text-sm'} flex-wrap`}>
          <div className="px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900">
            <span className="text-blue-800 dark:text-blue-200">
              Trend: {trendInfo.direction}
            </span>
          </div>
          <div className="px-3 py-1 rounded-full bg-green-100 dark:bg-green-900">
            <span className="text-green-800 dark:text-green-200">
              Weekly Δ: {trendInfo.weeklyChange.toFixed(2)} {unit}
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
      ) : hasActualValues ? (
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
                  domain={xDomain}
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

                {/* Plan Target Line (weight only) */}
                {isWeight && planExpectedPoints.length > 0 && (
                  <Line
                    type="monotone"
                    dataKey="planExpected"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="Plan Target"
                    connectNulls
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

                {/* Actual Line with status-based dots (weight) or plain dots */}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#2563eb"
                  strokeWidth={isMobile ? 1.5 : 2}
                  dot={(dotProps: any) => {
                    const point = dotProps.payload as ChartDataPoint | undefined
                    if (!point || point.value === undefined) return null
                    const color = isWeight ? getStatusColor(point.status) : '#2563eb'
                    return (
                      <circle
                        cx={dotProps.cx}
                        cy={dotProps.cy}
                        r={isMobile ? 4 : 5}
                        fill={color}
                        stroke={color}
                        strokeWidth={2}
                      />
                    )
                  }}
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
              <span>Measured</span>
            </div>
            {isWeight && (
              <>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span>Above Expected</span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span>Below Expected</span>
                </div>
              </>
            )}
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-green-500 opacity-50" style={{ background: '#10b981' }} />
              <span>Predicted</span>
            </div>
            {isWeight && planExpectedPoints.length > 0 && (
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span>Plan Target</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div>No {metricDef?.labelEn ?? metric} data available for this date range.</div>
      )}
    </div>
  )
}

export default BodyDataChart
