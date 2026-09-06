import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import type { RhythmDashboardData, EnergyProfileData, DomainMinutesData } from '@lib/data/rhythm'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { minutesToHours } from './utils'

interface OverviewCardProps {
  dashboard: RhythmDashboardData | null
}

const domainColors: Record<string, string> = {
  life: '#22c55e',
  work: '#3b82f6',
  career: '#a855f7',
}

export const OverviewCard = ({ dashboard }: OverviewCardProps) => {
  if (!dashboard) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">加载中...</CardContent>
      </Card>
    )
  }

  const { timeline, day_review, energy_profile, conflicts, inbox_summary, overdue_summary, today_due_summary } = dashboard
  const budget = energy_profile.daily_energy_budget
  const consumed = timeline.energy_consumed
  const budgetPercent = budget > 0 ? Math.min((consumed / budget) * 100, 100) : 0
  const overload = consumed > budget * 1.1

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>今日节奏分</CardDescription>
          <CardTitle className="text-3xl">{day_review.rhythm_score}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>精力预算</CardDescription>
          <CardTitle className="text-3xl">
            {consumed}/{budget}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Progress value={budgetPercent} className={overload ? 'text-red-500' : ''} />
          {overload && <p className="text-xs text-red-500 mt-1">超过 110%</p>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>冲突/侵占</CardDescription>
          <CardTitle className="text-3xl">{conflicts.encroachments.length}</CardTitle>
        </CardHeader>
      </Card>
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>待处理</CardDescription>
          <CardTitle className="text-3xl">
            {inbox_summary.length + overdue_summary.length + today_due_summary.length}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2 flex-wrap">
          <Badge variant="secondary">INBOX {inbox_summary.length}</Badge>
          <Badge variant="destructive">逾期 {overdue_summary.length}</Badge>
          <Badge>今日截止 {today_due_summary.length}</Badge>
        </CardContent>
      </Card>
    </div>
  )
}

export const DomainPieChart = ({ minutes, profile }: { minutes: DomainMinutesData; profile: EnergyProfileData | null }) => {
  const data = [
    { name: 'life', value: minutes.life },
    { name: 'work', value: minutes.work },
    { name: 'career', value: minutes.career },
  ].filter((d) => d.value > 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>三域时间</CardTitle>
        <CardDescription>实际投入 vs 目标权重</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {data.map((entry) => (
                  <Cell key={entry.name} fill={domainColors[entry.name] ?? '#8884d8'} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => [`${value} 分钟`, '']} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-sm mt-2">
          <div>
            <div className="font-bold">{minutes.life}</div>
            <div className="text-muted-foreground">life</div>
          </div>
          <div>
            <div className="font-bold">{minutes.work}</div>
            <div className="text-muted-foreground">work</div>
          </div>
          <div>
            <div className="font-bold">{minutes.career}</div>
            <div className="text-muted-foreground">career</div>
          </div>
        </div>
        {profile && (
          <div className="grid grid-cols-3 gap-2 text-center text-xs text-muted-foreground mt-2">
            <div>目标 {(profile.life_weight / (profile.life_weight + profile.work_weight + profile.career_weight) * 100).toFixed(0)}%</div>
            <div>目标 {(profile.work_weight / (profile.life_weight + profile.work_weight + profile.career_weight) * 100).toFixed(0)}%</div>
            <div>目标 {(profile.career_weight / (profile.life_weight + profile.work_weight + profile.career_weight) * 100).toFixed(0)}%</div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export const WarningList = ({ dashboard }: OverviewCardProps) => {
  if (!dashboard) return null
  const warnings = dashboard.timeline.warnings ?? []
  const encroachments = dashboard.conflicts.encroachments ?? []
  return (
    <Card>
      <CardHeader>
        <CardTitle>告警</CardTitle>
      </CardHeader>
      <CardContent>
        {warnings.length === 0 && encroachments.length === 0 && (
          <div className="text-muted-foreground">暂无告警</div>
        )}
        <div className="space-y-2">
          {warnings.map((w, idx) => (
            <div key={idx} className="text-sm p-2 bg-yellow-50 dark:bg-yellow-950 rounded">
              {typeof w === 'string' ? w : (w as { message?: string }).message ?? JSON.stringify(w)}
            </div>
          ))}
          {encroachments.map((e, idx) => (
            <div key={`e-${idx}`} className="text-sm p-2 bg-red-50 dark:bg-red-950 rounded text-red-700 dark:text-red-300">
              {e.message}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
