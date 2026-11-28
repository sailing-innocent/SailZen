/**
 * @file rhythm.tsx
 * @brief Rhythm v2 页面 — SailTick 驱动的可视化日程画布 + 重要项目倒排 + 即时协商入口
 */

import { useEffect, useState } from 'react'
import PageLayout from '@components/page_layout'
import DatePicker from '@components/date_picker'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { useRhythmStore } from '@lib/store/rhythm'
import { TimelineView } from '@components/rhythm/timeline_view'
import { DomainAssistantBar } from '@components/tick/DomainAssistantBar'
import {
  ChevronLeft,
  ChevronRight,
  Target,
  Check,
  Plus,
  Trash2,
  MessageCircle,
  RefreshCw,
} from 'lucide-react'

const QUICK_PROMPTS = [
  '帮我看看今天怎么排最轻松高效',
  '下午 2:00-4:00 临时加会，帮我重排一下',
  '今天有点累，晚上只留轻任务和休息',
]

const RhythmPage = () => {
  const selectedDate = useRhythmStore((s) => s.selectedDate)
  const setSelectedDate = useRhythmStore((s) => s.setSelectedDate)
  const dashboard = useRhythmStore((s) => s.dashboard)
  const loading = useRhythmStore((s) => s.loading)
  const error = useRhythmStore((s) => s.error)
  const fetchDashboard = useRhythmStore((s) => s.fetchDashboard)
  const quickAddProject = useRhythmStore((s) => s.quickAddProject)
  const addMilestone = useRhythmStore((s) => s.addMilestone)
  const markMilestoneDone = useRhythmStore((s) => s.markMilestoneDone)
  const quickAddTask = useRhythmStore((s) => s.quickAddTask)
  const finishAffair = useRhythmStore((s) => s.finishAffair)
  const deleteAffair = useRhythmStore((s) => s.deleteAffair)
  const checkin = useRhythmStore((s) => s.checkin)

  // 极简新建项目
  const [projOpen, setProjOpen] = useState(false)
  const [projTitle, setProjTitle] = useState('')
  const [projTargetDate, setProjTargetDate] = useState('')
  const [projDesc, setProjDesc] = useState('')

  // 极简新建里程碑
  const [msDrafts, setMsDrafts] = useState<Record<number, string>>({})

  // 极简随手记待办
  const [taskTitle, setTaskTitle] = useState('')
  const [taskDdl, setTaskDdl] = useState('')

  useEffect(() => {
    fetchDashboard(selectedDate).catch(() => {})
  }, [selectedDate, fetchDashboard])

  const shiftDay = (delta: number) => {
    const d = new Date(`${selectedDate}T00:00:00`)
    d.setDate(d.getDate() + delta)
    setSelectedDate(d)
  }

  const handleCreateProject = async () => {
    if (!projTitle.trim()) return
    await quickAddProject(projTitle, projTargetDate || undefined, projDesc)
    setProjTitle('')
    setProjTargetDate('')
    setProjDesc('')
    setProjOpen(false)
  }

  const handleAddMilestone = async (ventureId: number) => {
    const t = (msDrafts[ventureId] ?? '').trim()
    if (!t) return
    await addMilestone(ventureId, t)
    setMsDrafts((prev) => ({ ...prev, [ventureId]: '' }))
  }

  const handleQuickAddTask = async () => {
    if (!taskTitle.trim()) return
    await quickAddTask(taskTitle, taskDdl || undefined)
    setTaskTitle('')
    setTaskDdl('')
  }

  const projects = dashboard?.projects ?? []
  const focusAffairs = dashboard?.focus_affairs ?? []
  const overdueAffairs = dashboard?.overdue_affairs ?? []
  const habits = dashboard?.today_checkins?.habits ?? []

  return (
    <PageLayout>
      <div className="p-4 mx-auto w-full max-w-6xl space-y-4">
        {/* 顶栏：日期导航 + SailTick 联动 */}
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl md:text-2xl font-bold flex items-center gap-2">
              Rhythm 日程画布
              <Badge variant="secondary" className="text-xs font-normal">
                SailTick 驱动
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              排布日程是与 AI 长期交流理解的过程，这里只保留清晰画布与随手微调
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setSelectedDate(new Date())}>
              今天
            </Button>
            <Button variant="ghost" size="icon" onClick={() => shiftDay(-1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <DatePicker
              label=""
              placeholder="选择日期"
              value={new Date(`${selectedDate}T00:00:00`)}
              onChange={(date) => setSelectedDate(date)}
            />
            <Button variant="ghost" size="icon" onClick={() => shiftDay(1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={() => fetchDashboard()} disabled={loading}>
              <RefreshCw className={`h-3.5 w-3.5 mr-1 ${loading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <a href="/tick">
                <MessageCircle className="h-3.5 w-3.5 mr-1" />
                SailTick 票据
              </a>
            </Button>
          </div>
        </header>

        {error && (
          <div className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-sm text-destructive">
            加载失败：{error}
          </div>
        )}

        {/* 节奏规划师分域待确认票据 + 日报日程摘录 + 多端共享 owner:rhythm 协商对话 */}
        <DomainAssistantBar
          domain="rhythm"
          surface="web_rhythm"
          title="与节奏规划师即时协商（日程重排 · 项目倒排）"
          placeholder="例如：下午 2-4 点临时加会帮我重排 / 新建项目：下月底上线 v2 / 今天好累减负"
          quickPrompts={QUICK_PROMPTS}
          contextHints={{ selected_date: selectedDate }}
          onDataChanged={() => {
            void fetchDashboard()
          }}
        />

        {/* 主画布：左可视化时间线 + 右项目倒排与焦点待办 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          <div className="lg:col-span-7 space-y-4">
            <TimelineView timeline={dashboard?.timeline ?? null} />
          </div>

          <div className="lg:col-span-5 space-y-4">
            {/* 重要项目倒排 */}
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-1.5">
                      <Target className="h-4 w-4 text-primary" />
                      重要项目倒排
                    </CardTitle>
                    <CardDescription>只需定好目标日，SailTick 负责日常拆解与跟进</CardDescription>
                  </div>
                  <Dialog open={projOpen} onOpenChange={setProjOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" size="sm">
                        <Plus className="h-3.5 w-3.5 mr-1" />
                        新项目
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>新建重要项目</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-3 py-2">
                        <div className="space-y-1.5">
                          <Label>项目名称</Label>
                          <Input
                            placeholder="例如：SailZen 3.0 正式上线"
                            value={projTitle}
                            onChange={(e) => setProjTitle(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label>目标完成日期（倒排依据）</Label>
                          <Input
                            type="date"
                            value={projTargetDate}
                            onChange={(e) => setProjTargetDate(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label>一句话背景（可选）</Label>
                          <Input
                            placeholder="核心目标或交付标准"
                            value={projDesc}
                            onChange={(e) => setProjDesc(e.target.value)}
                          />
                        </div>
                        <Button onClick={handleCreateProject} disabled={!projTitle.trim()} className="w-full">
                          创建项目
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {projects.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-3 text-center">
                    暂无登记中的重要项目，点右上角新建或直接跟 SailTick 说一句即可。
                  </p>
                ) : (
                  projects.map((p) => {
                    const pct = Math.round((p.completion_ratio ?? 0) * 100)
                    return (
                      <div key={p.affair_id} className="rounded-lg border p-3 space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div className="font-medium text-sm">{p.title}</div>
                          {p.target_date ? (
                            <Badge
                              variant={
                                p.days_left !== null && p.days_left !== undefined && p.days_left <= 7
                                  ? 'destructive'
                                  : 'secondary'
                              }
                            >
                              {p.days_left !== null && p.days_left !== undefined
                                ? p.days_left < 0
                                  ? `超期 ${Math.abs(p.days_left)} 天`
                                  : `剩 ${p.days_left} 天`
                                : p.target_date}
                            </Badge>
                          ) : (
                            <Badge variant="outline">未定目标日</Badge>
                          )}
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>
                            目标 {p.target_date || '待定'} · 近14天投入 {p.recent_14d_hours}h
                          </span>
                          <span>里程碑 {pct}%</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-primary transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        {p.milestones.length > 0 && (
                          <div className="space-y-1 pt-1">
                            {p.milestones.map((m) => {
                              const done = m.state === 'DONE'
                              return (
                                <div
                                  key={m.id}
                                  className="flex items-center justify-between gap-2 text-xs"
                                >
                                  <span
                                    className={
                                      done ? 'line-through text-muted-foreground' : 'text-foreground'
                                    }
                                  >
                                    • {m.title}
                                  </span>
                                  {!done && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-6 px-2 text-xs"
                                      onClick={() => markMilestoneDone(m.id)}
                                    >
                                      <Check className="h-3 w-3 mr-0.5" />
                                      完成
                                    </Button>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                        <div className="flex gap-1.5 pt-1">
                          <Input
                            className="h-7 text-xs"
                            placeholder="随手加一个里程碑…"
                            value={msDrafts[p.affair_id] ?? ''}
                            onChange={(e) =>
                              setMsDrafts((prev) => ({ ...prev, [p.affair_id]: e.target.value }))
                            }
                            onKeyDown={(e) => e.key === 'Enter' && handleAddMilestone(p.affair_id)}
                          />
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs"
                            onClick={() => handleAddMilestone(p.affair_id)}
                          >
                            加
                          </Button>
                        </div>
                      </div>
                    )
                  })
                )}
              </CardContent>
            </Card>

            {/* 焦点待办 + 随手捕获 */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  待办焦点
                  {overdueAffairs.length > 0 && (
                    <Badge variant="destructive" className="ml-2 text-xs">
                      逾期 {overdueAffairs.length}
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>随手记下就行，不需要填权重和精力点数</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex gap-1.5">
                  <Input
                    className="h-8 text-sm"
                    placeholder="随手记一件要做的事…"
                    value={taskTitle}
                    onChange={(e) => setTaskTitle(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleQuickAddTask()}
                  />
                  <Input
                    type="date"
                    className="h-8 w-36 text-xs"
                    value={taskDdl}
                    onChange={(e) => setTaskDdl(e.target.value)}
                  />
                  <Button
                    size="sm"
                    className="h-8 shrink-0"
                    onClick={handleQuickAddTask}
                    disabled={!taskTitle.trim()}
                  >
                    添加
                  </Button>
                </div>

                {focusAffairs.length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-3">
                    当前没有积压待办，保持轻松。
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {focusAffairs.slice(0, 12).map((a) => (
                      <div
                        key={a.id}
                        className="flex items-center justify-between gap-2 rounded-md border px-2.5 py-2 text-sm"
                      >
                        <div className="min-w-0">
                          <div className="truncate font-medium">{a.title}</div>
                          {a.urgency_ddl && (
                            <div className="text-xs text-muted-foreground">
                              截止 {a.urgency_ddl.slice(0, 10)}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="标记完成"
                            onClick={() => finishAffair(a.id)}
                          >
                            <Check className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-destructive"
                            title="删除"
                            onClick={() => deleteAffair(a.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 轻量习惯打卡（仅在有活跃习惯时展示） */}
            {habits.length > 0 && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">今日习惯</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {habits.map((h) => (
                    <div
                      key={h.affair.id}
                      className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                    >
                      <div>
                        <div className="font-medium">{h.affair.title}</div>
                        <div className="text-xs text-muted-foreground">
                          本周 {h.week_done_count}/{h.week_target ?? 3} 次
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant={h.done_today ? 'secondary' : 'outline'}
                        disabled={h.done_today}
                        onClick={() => checkin(h.affair.id, 'done')}
                      >
                        {h.done_today ? '已打卡 ✓' : '打卡'}
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </PageLayout>
  )
}

export default RhythmPage
