import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { useRhythmStore } from '@lib/store/rhythm'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer } from 'recharts'
import { formatDate } from './utils'
import { AlertTriangle, Calendar, TrendingUp } from 'lucide-react'

export const ReviewCard = ({ review, title }: { review: ReturnType<typeof useRhythmStore.getState>['dayReview']; title: string }) => {
  if (!review) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">加载中...</CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{review.period_key}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="text-4xl font-bold mb-4">{review.rhythm_score}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground">戒律合规率</div>
            <div className="font-medium">{(review.precept_compliance_rate * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">习惯一致性</div>
            <div className="font-medium">{(review.habit_consistency * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">睡眠窗守约</div>
            <div className="font-medium">{(review.sleep_window_keeping * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">事业预算达成</div>
            <div className="font-medium">{(review.venture_budget_fulfillment * 100).toFixed(1)}%</div>
          </div>
          <div>
            <div className="text-muted-foreground">缓冲消耗</div>
            <div className="font-medium">{(review.buffer_consumed * 100).toFixed(1)}%</div>
          </div>
        </div>
        {review.ai_summary && (
          <div className="mt-4 p-3 bg-muted rounded-md text-sm">
            <div className="font-medium mb-1">AI 评语</div>
            {review.ai_summary}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export const EncroachmentList = () => {
  const dashboard = useRhythmStore((s) => s.dashboard)
  const encroachments = dashboard?.conflicts.encroachments ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5" />
          冲突/侵占
        </CardTitle>
      </CardHeader>
      <CardContent>
        {encroachments.length === 0 ? (
          <div className="text-muted-foreground">暂无侵占事件</div>
        ) : (
          <div className="space-y-2">
            {encroachments.map((e, idx) => (
              <div key={idx} className="flex items-start gap-2 rounded-md border p-3">
                <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5" />
                <div>
                  <Badge variant="outline">{e.type}</Badge>
                  <div className="text-sm mt-1">{e.message}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export const DomainTrendChart = () => {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<{ date: string; life: number; work: number; career: number }[]>([])
  const getDomainTrend = useRhythmStore((s) => s.fetchDomainTrend)

  useEffect(() => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    getDomainTrend(start, end).then((res) => setData(res.days))
  }, [days, getDomainTrend])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          三域时长趋势
        </CardTitle>
        <div className="flex gap-2">
          {[7, 30, 90].map((d) => (
            <Button key={d} variant={days === d ? 'default' : 'outline'} size="sm" onClick={() => setDays(d)}>
              {d} 天
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tickFormatter={(v) => formatDate(v)} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="life" stroke="#22c55e" />
              <Line type="monotone" dataKey="work" stroke="#3b82f6" />
              <Line type="monotone" dataKey="career" stroke="#a855f7" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

export const EnergyActualChart = () => {
  const dashboard = useRhythmStore((s) => s.dashboard)
  const profile = dashboard?.energy_profile

  const data = [
    { name: '预算', value: profile?.daily_energy_budget ?? 100 },
    { name: '已用', value: dashboard?.timeline.energy_consumed ?? 0 },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          精力预算 vs 实际
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
