import React, { useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import ReminderTodoList from '@components/project/reminder_todo_list'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useServerStore, usePemsStore } from '@lib/store/'
import { useIsMobile } from '@/hooks/use-mobile'
import {
  Wallet,
  Heart,
  FolderKanban,
  Activity,
  Package,
  Zap,
  Moon,
  Smile,
  ChevronRight,
} from 'lucide-react'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { RhythmLabels, RhythmColors } from '@lib/data/pems'

const MainPage = () => {
  const serverHealth = useServerStore((state) => state.serverHealth)
  const isMobile = useIsMobile()
  const {
    dayView,
    isLoading,
    fetchDayView,
    logHealthOnDay,
  } = usePemsStore()

  useEffect(() => {
    fetchDayView()
  }, [fetchDayView])

  const today = new Date()

  return (
    <PageLayout>
      <div className={`space-y-6 ${isMobile ? 'p-4' : 'p-6'}`}>
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className={`font-bold ${isMobile ? 'text-xl' : 'text-2xl'}`}>
              欢迎回来
            </h1>
            <p className="text-muted-foreground text-sm">
              {format(today, 'yyyy年MM月dd日 EEEE', { locale: zhCN })}
            </p>
          </div>
          <Badge variant={serverHealth ? 'default' : 'destructive'}>
            <Activity className="h-3 w-3 mr-1" />
            {serverHealth ? '服务正常' : '服务异常'}
          </Badge>
        </div>

        {/* Main Content Grid */}
        <div className={`grid gap-6 ${isMobile ? 'grid-cols-1' : 'md:grid-cols-3'}`}>
          {/* Left column */}
          <div className={isMobile ? 'space-y-6' : 'md:col-span-2 space-y-6'}>
            {dayView && <EnergyTodayCard dayView={dayView} />}
            <ReminderTodoList title="待办任务" showFilters={true} />
            {dayView && <InsightList insights={dayView.insights} />}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Quick Access */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">快捷入口</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-4 gap-2">
                <QuickAccessCard
                  icon={<Zap className="h-5 w-5" />}
                  label="精力"
                  href="/energy"
                  color="text-yellow-500"
                />
                <QuickAccessCard
                  icon={<Wallet className="h-5 w-5" />}
                  label="财务"
                  href="/money"
                  color="text-green-600"
                />
                <QuickAccessCard
                  icon={<Heart className="h-5 w-5" />}
                  label="健康"
                  href="/health"
                  color="text-red-500"
                />
                <QuickAccessCard
                  icon={<FolderKanban className="h-5 w-5" />}
                  label="项目"
                  href="/project"
                  color="text-blue-600"
                />
                <QuickAccessCard
                  icon={<Package className="h-5 w-5" />}
                  label="物资"
                  href="/necessity"
                  color="text-orange-500"
                />
              </CardContent>
            </Card>

            {dayView && (
              <HealthQuickLogCard
                date={today}
                health={dayView.health_signals}
                onSubmit={(log) => logHealthOnDay(log)}
              />
            )}

            {/* Tips Card */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">使用提示</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="text-sm text-muted-foreground space-y-2">
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>精力页面可查看整周精力分布与健康快拍</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>点击任务左侧复选框可快速完成任务</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>红色边框表示任务紧急或已逾期</span>
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

const EnergyTodayCard: React.FC<{ dayView: import('@lib/data/pems').DayViewData }> = ({
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
          今日精力概览
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div>
              <p className="text-3xl font-bold">{budget.energy_budget}</p>
              <p className="text-xs text-muted-foreground">精力预算</p>
            </div>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>已安排 {budget.energy_planned}</p>
              <p>实际消耗 {budget.energy_actual}</p>
            </div>
          </div>
          <Badge className={RhythmColors[dayView.rhythm] || ''}>
            {RhythmLabels[dayView.rhythm] || dayView.rhythm}
          </Badge>
        </div>

        <div className="space-y-1">
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className={`h-full rounded-full ${
                usedPercent > 100 ? 'bg-red-500' : 'bg-primary'
              }`}
              style={{ width: `${usedPercent}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            健康修正系数 {budget.health_multiplier}%
          </p>
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

        {dayView.planned_missions.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">今日重点任务</p>
            <div className="space-y-1">
              {dayView.planned_missions.slice(0, 3).map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between text-sm p-2 rounded-lg border"
                >
                  <span>{m.name}</span>
                  <span className="text-xs text-muted-foreground">{m.energy_cost} 精力</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <a
          href="/energy"
          className="inline-flex items-center text-sm text-primary hover:underline"
        >
          查看精力详情
          <ChevronRight className="h-4 w-4" />
        </a>
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
          今日洞察
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
}> = ({ health, onSubmit }) => {
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
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label className="text-xs flex items-center gap-1">
              <Moon className="h-3 w-3" />
              睡眠时长
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

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">睡眠质量</Label>
              <Select value={String(sleepQuality)} onValueChange={(v) => setSleepQuality(parseInt(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5].map((v) => (
                    <SelectItem key={v} value={String(v)}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs flex items-center gap-1">
                <Zap className="h-3 w-3" />
                精力
              </Label>
              <Select value={String(energyLevel)} onValueChange={(v) => setEnergyLevel(parseInt(v))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 4, 5].map((v) => (
                    <SelectItem key={v} value={String(v)}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs flex items-center gap-1">
              <Smile className="h-3 w-3" />
              情绪
            </Label>
            <Select value={String(mood)} onValueChange={(v) => setMood(parseInt(v))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((v) => (
                  <SelectItem key={v} value={String(v)}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">备注</Label>
            <Input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="今天状态如何..."
            />
          </div>

          <Button type="submit" className="w-full" size="sm">
            记录
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

interface QuickAccessCardProps {
  icon: React.ReactNode
  label: string
  href: string
  color?: string
}

const QuickAccessCard: React.FC<QuickAccessCardProps> = ({
  icon,
  label,
  href,
  color = 'text-primary',
}) => {
  return (
    <a
      href={href}
      className="flex flex-col items-center justify-center p-3 rounded-lg border hover:bg-accent transition-colors"
    >
      <span className={color}>{icon}</span>
      <span className="mt-1 text-xs">{label}</span>
    </a>
  )
}

export default MainPage
