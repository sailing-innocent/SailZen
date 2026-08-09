import React, { useEffect, useMemo, useState } from 'react'
import PageLayout from '@components/page_layout'
import { usePemsStore } from '@lib/store/'
import { useIsMobile } from '@/hooks/use-mobile'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ChevronLeft,
  ChevronRight,
  Zap,
  Heart,
  Moon,
  Smile,
  Activity,
} from 'lucide-react'
import { format, addDays, startOfWeek, isSameDay, parseISO } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { RhythmLabels, RhythmColors } from '@lib/data/pems'

const EnergyPage = () => {
  const isMobile = useIsMobile()
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date(), { weekStartsOn: 1 }))
  const {
    dayView,
    selectedDate,
    isLoading,
    fetchDayView,
    logHealthOnDay,
  } = usePemsStore()

  useEffect(() => {
    fetchDayView(selectedDate)
  }, [selectedDate, fetchDayView])

  const weekDays = useMemo(() => {
    return Array.from({ length: 7 }).map((_, i) => addDays(weekStart, i))
  }, [weekStart])

  const selected = useMemo(() => {
    return selectedDate ? parseISO(selectedDate) : new Date()
  }, [selectedDate])

  const handlePrevWeek = () => setWeekStart((d) => addDays(d, -7))
  const handleNextWeek = () => setWeekStart((d) => addDays(d, 7))
  const handleSelectDay = (d: Date) => fetchDayView(d.toISOString())

  return (
    <PageLayout>
      <div className={`space-y-6 ${isMobile ? 'p-4' : 'p-6'}`}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className={`font-bold ${isMobile ? 'text-xl' : 'text-2xl'}`}>
              精力 / 日程
            </h1>
            <p className="text-muted-foreground text-sm">
              以日为单位、以周为视图的精力管理
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={handlePrevWeek}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium min-w-[120px] text-center">
              {format(weekStart, 'yyyy年MM月dd日', { locale: zhCN })} 起
            </span>
            <Button variant="outline" size="icon" onClick={handleNextWeek}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-7 gap-2">
          {weekDays.map((d) => {
            const isSelected = isSameDay(d, selected)
            return (
              <button
                key={d.toISOString()}
                onClick={() => handleSelectDay(d)}
                className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-colors ${
                  isSelected ? 'border-primary bg-primary/5' : 'hover:bg-accent'
                }`}
              >
                <span className="text-xs text-muted-foreground">
                  {format(d, 'EEE', { locale: zhCN })}
                </span>
                <span className={`text-lg font-semibold ${isSelected ? 'text-primary' : ''}`}>
                  {format(d, 'd')}
                </span>
              </button>
            )
          })}
        </div>

        {isLoading && <p className="text-sm text-muted-foreground">加载中...</p>}

        {dayView && (
          <div className={`grid gap-6 ${isMobile ? 'grid-cols-1' : 'md:grid-cols-3'}`}>
            <div className={isMobile ? '' : 'md:col-span-2 space-y-6'}>
              <DaySummaryCard dayView={dayView} />
              <MissionListCard
                title="今日安排"
                missions={dayView.planned_missions}
                emptyText="今日暂无安排任务"
              />
              <MissionListCard
                title="已完成"
                missions={dayView.completed_missions}
                emptyText="今日暂无完成任务"
              />
              <InsightList insights={dayView.insights} />
            </div>

            <div className="space-y-6">
              <HealthQuickLogCard
                date={selected}
                health={dayView.health_signals}
                onSubmit={(log) => logHealthOnDay(log, selected.toISOString())}
              />
            </div>
          </div>
        )}
      </div>
    </PageLayout>
  )
}

const DaySummaryCard: React.FC<{ dayView: import('@lib/data/pems').DayViewData }> = ({
  dayView,
}) => {
  const budget = dayView.energy_budget
  const usedPercent = Math.min(
    100,
    budget.energy_budget > 0 ? (budget.energy_planned / budget.energy_budget) * 100 : 0
  )

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Zap className="h-4 w-4" />
          今日精力
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-3xl font-bold">{budget.energy_budget}</p>
            <p className="text-xs text-muted-foreground">精力预算</p>
          </div>
          <Badge className={RhythmColors[dayView.rhythm] || ''}>
            {RhythmLabels[dayView.rhythm] || dayView.rhythm}
          </Badge>
        </div>

        <div className="space-y-1">
          <div className="flex justify-between text-sm">
            <span>已安排 {budget.energy_planned}</span>
            <span>{usedPercent.toFixed(0)}%</span>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className={`h-full rounded-full ${
                usedPercent > 100 ? 'bg-red-500' : 'bg-primary'
              }`}
              style={{ width: `${usedPercent}%` }}
            />
          </div>
        </div>

        {budget.warning_messages.length > 0 && (
          <ul className="text-sm space-y-1">
            {budget.warning_messages.map((msg, idx) => (
              <li key={idx} className="text-destructive flex items-start gap-2">
                <span>•</span>
                <span>{msg}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

const MissionListCard: React.FC<{
  title: string
  missions: import('@lib/data/pems').PemsMissionBriefData[]
  emptyText: string
}> = ({ title, missions, emptyText }) => {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {missions.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          <ul className="space-y-2">
            {missions.map((m) => (
              <li
                key={m.id}
                className="flex items-center justify-between p-2 rounded-lg border"
              >
                <div>
                  <p className="text-sm font-medium">{m.name}</p>
                  {m.project_name && (
                    <p className="text-xs text-muted-foreground">{m.project_name}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Zap className="h-3 w-3" />
                    {m.energy_cost}
                  </span>
                  <span>{m.planned_minutes}min</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

const InsightList: React.FC<{ insights: import('@lib/data/pems').InsightData[] }> = ({
  insights,
}) => {
  if (insights.length === 0) return null
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Activity className="h-4 w-4" />
          洞察
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {insights.map((insight, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border ${
              insight.severity === 'danger'
                ? 'border-red-200 bg-red-50'
                : insight.severity === 'warning'
                ? 'border-yellow-200 bg-yellow-50'
                : 'border-blue-200 bg-blue-50'
            }`}
          >
            <p className="text-sm font-medium">{insight.title}</p>
            <p className="text-xs text-muted-foreground">{insight.message}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

const HealthQuickLogCard: React.FC<{
  date: Date
  health: import('@lib/data/pems').HealthSignalSummaryData
  onSubmit: (log: import('@lib/data/pems').HealthQuickLogProps) => void
}> = ({ date, health, onSubmit }) => {
  const [sleepHours, setSleepHours] = useState(health.sleep_hours ?? 7)
  const [sleepQuality, setSleepQuality] = useState(health.sleep_quality ?? 3)
  const [energyLevel, setEnergyLevel] = useState(health.energy_level ?? 3)
  const [mood, setMood] = useState(health.mood ?? 3)
  const [note, setNote] = useState('')

  useEffect(() => {
    setSleepHours(health.sleep_hours ?? 7)
    setSleepQuality(health.sleep_quality ?? 3)
    setEnergyLevel(health.energy_level ?? 3)
    setMood(health.mood ?? 3)
  }, [health])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      sleep_hours: sleepHours,
      sleep_quality: sleepQuality,
      energy_level: energyLevel,
      mood,
      note: note || undefined,
    })
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Heart className="h-4 w-4" />
          健康快拍
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <Label className="text-xs flex items-center gap-1">
              <Moon className="h-3 w-3" />
              睡眠时长 (小时)
            </Label>
            <Input
              type="number"
              step={0.5}
              min={0}
              max={24}
              value={sleepHours}
              onChange={(e) => setSleepHours(parseFloat(e.target.value))}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">睡眠质量 (1-5)</Label>
            <Select value={String(sleepQuality)} onValueChange={(v) => setSleepQuality(parseInt(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {v}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs flex items-center gap-1">
              <Zap className="h-3 w-3" />
              精力评分 (1-5)
            </Label>
            <Select value={String(energyLevel)} onValueChange={(v) => setEnergyLevel(parseInt(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {v}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs flex items-center gap-1">
              <Smile className="h-3 w-3" />
              情绪评分 (1-5)
            </Label>
            <Select value={String(mood)} onValueChange={(v) => setMood(parseInt(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((v) => (
                  <SelectItem key={v} value={String(v)}>
                    {v}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">备注</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="今天状态如何..." />
          </div>

          <Button type="submit" className="w-full">
            记录
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export default EnergyPage
