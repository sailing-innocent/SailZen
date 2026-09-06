import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

import type { CheckinTodayItemData, CheckinResultValue, HabitHeatmapData } from '@lib/data/rhythm'
import { useRhythmStore } from '@lib/store/rhythm'
import { api_get_today_checkins, api_checkin, api_get_habit_heatmap } from '@lib/api/rhythm'
import { Check, X, Minus, Calendar } from 'lucide-react'
import { formatDate } from './utils'

const resultOptions: { value: CheckinResultValue; icon: React.ReactNode; label: string }[] = [
  { value: 'kept', icon: <Check className="h-4 w-4" />, label: '遵守' },
  { value: 'violated', icon: <X className="h-4 w-4" />, label: '破戒' },
  { value: 'done', icon: <Check className="h-4 w-4" />, label: '完成' },
  { value: 'missed', icon: <Minus className="h-4 w-4" />, label: ' missed' },
  { value: 'exempt', icon: <Calendar className="h-4 w-4" />, label: '豁免' },
]

const CheckinItem = ({ item }: { item: CheckinTodayItemData }) => {
  const { checkin, fetchTodayCheckins } = useRhythmStore((s) => s)
  const [selected, setSelected] = useState<CheckinResultValue | ''>(item.last_result ?? '')
  const isHabit = item.affair.kind === 'habit'
  const isPrecept = item.affair.kind === 'precept'

  const handleCheckin = async (result: CheckinResultValue) => {
    setSelected(result)
    await checkin(item.affair.id, result)
    await fetchTodayCheckins()
  }

  const options = isHabit
    ? resultOptions.filter((o) => ['done', 'missed', 'exempt'].includes(o.value))
    : isPrecept
    ? resultOptions.filter((o) => ['kept', 'violated', 'exempt'].includes(o.value))
    : resultOptions

  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between rounded-md border p-3 gap-3">
      <div>
        <div className="font-medium">{item.affair.title}</div>
        <div className="text-sm text-muted-foreground">
          {isHabit
            ? `本周 ${item.week_done_count ?? 0}/${item.week_target ?? 0}`
            : item.affair.kind_meta?.check_time
            ? `核销时间 ${item.affair.kind_meta.check_time}`
            : ''}
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        {options.map((o) => (
          <Button
            key={o.value}
            variant={selected === o.value ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleCheckin(o.value)}
          >
            {o.icon}
            <span className="ml-1 hidden sm:inline">{o.label}</span>
          </Button>
        ))}
      </div>
      {item.done_today && <Badge>已打卡</Badge>}
    </div>
  )
}

export const CheckinPanel = () => {
  const todayCheckins = useRhythmStore((s) => s.todayCheckins)
  const fetchTodayCheckins = useRhythmStore((s) => s.fetchTodayCheckins)

  useEffect(() => {
    fetchTodayCheckins()
  }, [fetchTodayCheckins])

  if (!todayCheckins) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">加载中...</CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>今日待打卡</CardTitle>
          <CardDescription>precepts & habits</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {todayCheckins.precepts.length === 0 && todayCheckins.habits.length === 0 && (
            <div className="text-muted-foreground">今日无需打卡</div>
          )}
          {[...todayCheckins.precepts, ...todayCheckins.habits].map((item) => (
            <CheckinItem key={item.affair.id} item={item} />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export const HabitHeatmap = ({ affairId }: { affairId: number }) => {
  const [heatmap, setHeatmap] = useState<HabitHeatmapData | null>(null)

  useEffect(() => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - 84)
    api_get_habit_heatmap(affairId, start, end).then(setHeatmap)
  }, [affairId])

  if (!heatmap) return <div>加载中...</div>

  const weeks: string[] = []
  const data: boolean[][] = []
  let currentWeek: boolean[] = []
  heatmap.days.forEach((day) => {
    const d = new Date(day.date)
    if (d.getDay() === 1 && currentWeek.length > 0) {
      weeks.push(`W${weeks.length + 1}`)
      data.push(currentWeek)
      currentWeek = []
    }
    currentWeek.push(day.done)
  })
  if (currentWeek.length > 0) {
    data.push(currentWeek)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>习惯热力图</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex gap-1 overflow-x-auto">
          {data.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-1">
              {week.map((done, di) => (
                <div
                  key={di}
                  className={`w-4 h-4 rounded ${done ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-700'}`}
                  title={heatmap.days[wi * 7 + di]?.date}
                />
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export const PreceptComplianceChart = ({ logs }: { logs: { result: string; count: number }[] }) => {
  const kept = logs.find((l) => l.result === 'kept')?.count ?? 0
  const violated = logs.find((l) => l.result === 'violated')?.count ?? 0
  const exempt = logs.find((l) => l.result === 'exempt')?.count ?? 0
  const total = kept + violated + exempt
  const rate = total > 0 ? kept / (kept + violated) : 1

  return (
    <Card>
      <CardHeader>
        <CardTitle>Precept 合规率</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{total > 0 ? (rate * 100).toFixed(1) : 100}%</div>
        <div className="text-sm text-muted-foreground mt-1">
          遵守 {kept} · 破戒 {violated} · 豁免 {exempt}
        </div>
      </CardContent>
    </Card>
  )
}
