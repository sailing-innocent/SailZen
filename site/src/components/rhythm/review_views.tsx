import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { useRhythmStore } from '@lib/store/rhythm'
import { api_update_review_summary } from '@lib/api/rhythm'
import type { ReviewData } from '@lib/data/rhythm'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer } from 'recharts'
import { formatDate } from './utils'
import { getISOWeek, getISOWeekYear, setISOWeek, setISOWeekYear } from 'date-fns'
import { AlertTriangle, Calendar, ChevronLeft, ChevronRight, Save, TrendingUp } from 'lucide-react'

// ---------------------------------------------------------------------------
// Week period_key helpers（后端格式 W{iso_year}-{week:02d}）
// ---------------------------------------------------------------------------

export const parseWeekKey = (key: string): { year: number; week: number } | null => {
  const m = /^W(\d{4})-(\d{2})$/.exec(key)
  if (!m) return null
  return { year: parseInt(m[1], 10), week: parseInt(m[2], 10) }
}

export const shiftWeekKey = (key: string, delta: number): string | null => {
  const parsed = parseWeekKey(key)
  if (!parsed) return null
  const monday = setISOWeek(setISOWeekYear(new Date(), parsed.year), parsed.week + delta)
  return `W${getISOWeekYear(monday)}-${String(getISOWeek(monday)).padStart(2, '0')}`
}

// ---------------------------------------------------------------------------
// Review cards
// ---------------------------------------------------------------------------

export const ReviewCard = ({ review, title }: { review: ReviewData | null; title: string }) => {
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

/** AI 评语编辑：调用 PUT /review/{scope}/{period_key}/summary 后刷新对应复盘 */
export const ReviewSummaryEditor = ({
  scope,
  review,
}: {
  scope: 'day' | 'week'
  review: ReviewData | null
}) => {
  const fetchReview = useRhythmStore((s) => s.fetchReview)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setText(review?.ai_summary ?? '')
    setError(null)
  }, [review?.period_key, review?.ai_summary])

  const handleSave = async () => {
    if (!review) return
    setSaving(true)
    setError(null)
    try {
      await api_update_review_summary(scope, review.period_key, text)
      await fetchReview(scope, scope === 'week' ? review.period_key : undefined)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  if (!review) return null

  return (
    <div className="space-y-2">
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="填写本期复盘评语..."
        className="text-sm"
      />
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={handleSave} disabled={saving}>
          <Save className="h-3 w-3 mr-1" />
          {saving ? '保存中...' : '保存评语'}
        </Button>
        {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
      </div>
    </div>
  )
}

/** 周复盘卡片：带相邻周导航（period_key 之间直接跳转） */
export const WeekReviewCard = () => {
  const weekReview = useRhythmStore((s) => s.weekReview)
  const fetchReview = useRhythmStore((s) => s.fetchReview)
  const [navError, setNavError] = useState<string | null>(null)

  const handleShift = async (delta: number) => {
    if (!weekReview) return
    const next = shiftWeekKey(weekReview.period_key, delta)
    if (!next) {
      setNavError(`无法解析周键: ${weekReview.period_key}`)
      return
    }
    setNavError(null)
    await fetchReview('week', next).catch((e) => setNavError(e instanceof Error ? e.message : String(e)))
  }

  const canNav = weekReview ? parseWeekKey(weekReview.period_key) !== null : false

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[auto_1fr_auto] items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          disabled={!canNav}
          onClick={() => handleShift(-1)}
          aria-label="上一周"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <ReviewCard review={weekReview} title="周评分" />
        <Button
          variant="outline"
          size="icon"
          disabled={!canNav}
          onClick={() => handleShift(1)}
          aria-label="下一周"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
      {navError && <div className="text-xs text-red-600 dark:text-red-400">{navError}</div>}
      <ReviewSummaryEditor scope="week" review={weekReview} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Other review widgets
// ---------------------------------------------------------------------------

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
  const domainTrend = useRhythmStore((s) => s.domainTrend)
  const getDomainTrend = useRhythmStore((s) => s.fetchDomainTrend)

  useEffect(() => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    // fetchDomainTrend 将结果写入 store.domainTrend（Promise<void>），这里订阅 store 而非返回值
    getDomainTrend(start, end).catch(() => {})
  }, [days, getDomainTrend])

  const data = domainTrend?.days ?? []

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
