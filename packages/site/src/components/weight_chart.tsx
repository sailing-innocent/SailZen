import React from 'react'
import { type HealthState, useHealthStore } from '@lib/store/health'

// import { CartesianGrid, Line, LineChart, XAxis } from 'recharts'
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
// import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Line, LineChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { type ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@components/ui/chart'

const WeightChart: React.FC = () => {
  const weights = useHealthStore((state: HealthState) => state.weights)
  const isLoading = useHealthStore((state: HealthState) => state.isLoading)

  const data = weights.map((weight) => ({
    value: parseFloat(weight.value),
    timestamp: weight.htime * 1000, // Keep the numeric timestamp for scaling
  }))
  const chartConfig = {
    desktop: {
      label: 'Desktop',
      color: '#2563eb',
    },
    mobile: {
      label: 'Mobile',
      color: '#60a5fa',
    },
  } satisfies ChartConfig

  return (
    <div className="flex flex-col items-center justify-center">
      <h2 className="text-xl font-bold mb-4">Weight Chart</h2>
      {isLoading ? (
        <div className="w-full space-y-3">Loading...</div>
      ) : weights.length > 0 ? (
        <div className="w-full">
          {/* Here you would render your chart component with the weights data */}
          <p>Chart data would be rendered here. {weights.length}</p>

          <ChartContainer config={chartConfig} className="min-h-[200px] w-full">
            <LineChart data={data} margin={{ right: 30, left: 30 }}>
              <CartesianGrid vertical={false} />
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={['dataMin - 100000000', 'dataMax + 100000000']}
                tickLine={false}
                axisLine={false}
                minTickGap={32}
                tickMargin={8}
                tickFormatter={(value) => new Date(value).toLocaleDateString()}
                scale="time"
              />
              <YAxis domain={['dataMin - 5', 'dataMax + 5']} tickLine={false} axisLine={false} tickMargin={8} />

              <Line dataKey="value" />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    formatter={(value, _name, item) => {
                      const date = item.payload?.timestamp
                        ? new Date(item.payload.timestamp).toLocaleDateString('zh-CN', {
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                          })
                        : ''
                      return (
                        <div className="flex flex-col gap-1">
                          <div className="text-muted-foreground text-xs">{date}</div>
                          <div className="font-semibold">{value} kg</div>
                        </div>
                      )
                    }}
                  />
                }
              />
            </LineChart>
          </ChartContainer>
        </div>
      ) : (
        <div>No weight data available.</div>
      )}
    </div>
  )
}

export default WeightChart
