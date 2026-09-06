import PageLayout from '@components/page_layout'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import DatePicker from '@components/date_picker'
import type { RhythmSection } from '@lib/store/rhythm'
import { useRhythmStore } from '@lib/store/rhythm'
import type { AffairDomainValue, AffairKindValue, AffairStateValue } from '@lib/data/affair'
import { AffairDomain, AffairKind } from '@lib/data/affair'
import { useEffect, useState } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  OverviewCard,
  DomainPieChart,
  WarningList,
} from '@components/rhythm/overview_card'
import { TimelineView } from '@components/rhythm/timeline_view'
import {
  AffairKanban,
  AffairList,
  AffairEditDialog,
  AffairCreateButton,
} from '@components/rhythm/affair_views'
import {
  VentureCard,
  VentureDetail,
} from '@components/rhythm/venture_views'
import {
  CheckinPanel,
  HabitHeatmap,
  PreceptComplianceChart,
} from '@components/rhythm/discipline_views'
import {
  EnergyProfileEditor,
  TemplateEditor,
  PolicyEditor,
} from '@components/rhythm/foundation_views'
import {
  ReviewCard,
  ReviewSummaryEditor,
  WeekReviewCard,
  EncroachmentList,
  DomainTrendChart,
  EnergyActualChart,
} from '@components/rhythm/review_views'
import { EnergyTab } from '@components/rhythm/energy_tab'
import type { AffairData } from '@lib/data/affair'
import {
  LayoutDashboard,
  Clock,
  Briefcase,
  Target,
  Settings,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Zap,
  Search,
} from 'lucide-react'

const tabDefs = [
  { value: 'overview', label: '概览', icon: LayoutDashboard },
  { value: 'timeline', label: '时间线', icon: Clock },
  { value: 'energy', label: '精力', icon: Zap },
  { value: 'affairs', label: '事务中心', icon: Briefcase },
  { value: 'ventures', label: '事业', icon: Target },
  { value: 'discipline', label: '戒律/习惯', icon: CheckCircle2 },
  { value: 'foundation', label: '基础配置', icon: Settings },
  { value: 'review', label: '复盘统计', icon: BarChart3 },
] as const

type TabValue = typeof tabDefs[number]['value']

const RhythmPage = () => {
  const [activeTab, setActiveTab] = useState<TabValue>('overview')
  const selectedDate = useRhythmStore((s) => s.selectedDate)
  const setSelectedDate = useRhythmStore((s) => s.setSelectedDate)
  const dashboard = useRhythmStore((s) => s.dashboard)
  const error = useRhythmStore((s) => s.error)
  const degraded = useRhythmStore((s) => s.degraded)
  const fetchDashboard = useRhythmStore((s) => s.fetchDashboard)
  const retrySection = useRhythmStore((s) => s.retrySection)
  const planDay = useRhythmStore((s) => s.planDay)
  const rebalanceDay = useRhythmStore((s) => s.rebalanceDay)

  useEffect(() => {
    fetchDashboard(selectedDate).catch(() => {})
  }, [selectedDate, fetchDashboard])

  const handlePrevDay = () => {
    const d = new Date(selectedDate)
    d.setDate(d.getDate() - 1)
    setSelectedDate(d)
  }

  const handleNextDay = () => {
    const d = new Date(selectedDate)
    d.setDate(d.getDate() + 1)
    setSelectedDate(d)
  }

  const handleToday = () => {
    setSelectedDate(new Date())
  }

  const handlePlanDay = async () => {
    await planDay()
  }

  const handleRebalance = async () => {
    await rebalanceDay(undefined, 'manual')
  }

  const profile = dashboard?.energy_profile
  const needsCalibration = profile?.is_default
  const conflictCount = dashboard?.conflicts.encroachments.length ?? 0
  const inboxCount = dashboard?.inbox_summary.length ?? 0
  const overdueCount = dashboard?.overdue_summary.length ?? 0
  const todayDueCount = dashboard?.today_due_summary.length ?? 0

  return (
    <PageLayout>
      <header className="flex flex-col gap-4 px-2 md:px-0 shrink-0">
        <div className="flex items-center justify-between">
          <h1 className="text-xl md:text-2xl font-bold">Rhythm 后台</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleToday}>
              今日
            </Button>
            <Button variant="ghost" size="icon" onClick={handlePrevDay}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <DatePicker
              label=""
              placeholder="选择日期"
              value={new Date(selectedDate)}
              onChange={(date) => setSelectedDate(date)}
            />
            <Button variant="ghost" size="icon" onClick={handleNextDay}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={handlePlanDay}>
            <Sparkles className="h-4 w-4 mr-1" />
            生成日计划
          </Button>
          <Button variant="outline" size="sm" onClick={handleRebalance}>
            <RotateCcw className="h-4 w-4 mr-1" />
            再平衡
          </Button>
          <Button variant="link" size="sm" onClick={() => setActiveTab('timeline')}>
            跳转时间线
          </Button>
          {needsCalibration && (
            <Button
              variant="outline"
              size="sm"
              className="border-destructive text-destructive hover:bg-destructive/10"
              onClick={() => setActiveTab('foundation')}
            >
              <AlertCircle className="h-3 w-3 mr-1" />
              精力画像为默认导入，建议校准
            </Button>
          )}
          {conflictCount > 0 && <Badge variant="destructive">冲突 {conflictCount}</Badge>}
          {inboxCount > 0 && <Badge variant="secondary">INBOX {inboxCount}</Badge>}
          {overdueCount > 0 && <Badge variant="destructive">逾期 {overdueCount}</Badge>}
          {todayDueCount > 0 && <Badge>今日截止 {todayDueCount}</Badge>}
        </div>

        {/* dashboard 子模块降级提示：部分数据为占位值，可整体重试 */}
        {degraded.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-yellow-300 bg-yellow-50 p-2 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">
              以下模块暂时降级：{degraded.join('、')}（显示为占位数据）
            </span>
            <Button variant="outline" size="sm" onClick={() => retrySection('dashboard').catch(() => {})}>
              <RotateCcw className="h-3 w-3 mr-1" />
              重试
            </Button>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)} className="w-full">
        <TabsList className="flex w-full flex-wrap h-auto gap-1 justify-start">
          {tabDefs.map((tab) => {
            const Icon = tab.icon
            return (
              <TabsTrigger key={tab.value} value={tab.value} className="gap-1">
                <Icon className="h-4 w-4" />
                {tab.label}
              </TabsTrigger>
            )
          })}
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <SectionGuard section="dashboard">
            <OverviewTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="timeline" className="mt-4">
          <SectionGuard section="timeline">
            <TimelineTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="energy" className="mt-4">
          <EnergyTab />
        </TabsContent>
        <TabsContent value="affairs" className="mt-4">
          <SectionGuard section="affairs">
            <AffairsTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="ventures" className="mt-4">
          <SectionGuard section="ventures">
            <VenturesTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="discipline" className="mt-4">
          <SectionGuard section="checkins">
            <DisciplineTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="foundation" className="mt-4">
          <SectionGuard section="config">
            <FoundationTab />
          </SectionGuard>
        </TabsContent>
        <TabsContent value="review" className="mt-4">
          <SectionGuard section="review">
            <ReviewTab />
          </SectionGuard>
        </TabsContent>
      </Tabs>
    </PageLayout>
  )
}

// ---------------------------------------------------------------------------
// Section guard：分片级 loading / error / retry
// ---------------------------------------------------------------------------

const SectionGuard = ({
  section,
  children,
}: {
  section: RhythmSection
  children: React.ReactNode
}) => {
  const status = useRhythmStore((s) => s.sections[section])
  const retrySection = useRhythmStore((s) => s.retrySection)

  if (status.loading && status.error === null) {
    return <div className="p-6 text-sm text-muted-foreground">加载中...</div>
  }

  if (status.error) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span className="flex-1">{status.error}</span>
        <Button variant="outline" size="sm" onClick={() => retrySection(section).catch(() => {})}>
          <RotateCcw className="h-3 w-3 mr-1" />
          重试
        </Button>
      </div>
    )
  }

  return <>{children}</>
}

// ---------------------------------------------------------------------------
// Tab implementations
// ---------------------------------------------------------------------------

const OverviewTab = () => {
  const dashboard = useRhythmStore((s) => s.dashboard)
  return (
    <div className="space-y-4">
      <OverviewCard dashboard={dashboard} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <DomainPieChart
          minutes={dashboard?.timeline.domain_minutes ?? { life: 0, work: 0, career: 0 }}
          profile={dashboard?.energy_profile ?? null}
        />
        <WarningList dashboard={dashboard} />
      </div>
    </div>
  )
}

const TimelineTab = () => <TimelineView />

const FILTER_STATE_OPTIONS: AffairStateValue[] = [
  'INBOX',
  'PLANNED',
  'SCHEDULED',
  'DOING',
  'DEFERRED',
  'ACTIVE',
  'PAUSED',
  'KICKOFF',
  'DELEGATED',
  'REVIEWING',
]

const AffairsFilterBar = () => {
  const filters = useRhythmStore((s) => s.affairFilters)
  const setAffairFilters = useRhythmStore((s) => s.setAffairFilters)
  const resetAffairFilters = useRhythmStore((s) => s.resetAffairFilters)

  const hasFilters =
    filters.search.trim() !== '' ||
    filters.states.length > 0 ||
    filters.domains.length > 0 ||
    filters.kinds.length > 0

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border p-2">
      <div className="relative">
        <Search className="h-3.5 w-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={filters.search}
          onChange={(e) => setAffairFilters({ search: e.target.value })}
          placeholder="搜索标题..."
          className="h-8 w-44 pl-7 text-sm"
        />
      </div>
      <Select
        value={filters.states[0] ?? 'all'}
        onValueChange={(v) => setAffairFilters({ states: v === 'all' ? [] : [v as AffairStateValue] })}
      >
        <SelectTrigger className="h-8 w-32 text-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部状态</SelectItem>
          {FILTER_STATE_OPTIONS.map((s) => (
            <SelectItem key={s} value={s}>
              {s}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={filters.domains[0] ?? 'all'}
        onValueChange={(v) => setAffairFilters({ domains: v === 'all' ? [] : [v as AffairDomainValue] })}
      >
        <SelectTrigger className="h-8 w-32 text-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部域</SelectItem>
          {Object.values(AffairDomain).map((d) => (
            <SelectItem key={d} value={d}>
              {d}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={filters.kinds[0] ?? 'all'}
        onValueChange={(v) => setAffairFilters({ kinds: v === 'all' ? [] : [v as AffairKindValue] })}
      >
        <SelectTrigger className="h-8 w-36 text-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部类型</SelectItem>
          {Object.values(AffairKind).map((k) => (
            <SelectItem key={k} value={k}>
              {k}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={resetAffairFilters}>
          重置
        </Button>
      )}
    </div>
  )
}

const AffairsTab = () => {
  const allAffairs = useRhythmStore((s) => s.allAffairs)
  const affairFilters = useRhythmStore((s) => s.affairFilters)
  const fetchAffairsByKind = useRhythmStore((s) => s.fetchAffairsByKind)
  const [view, setView] = useState<'kanban' | 'list'>('kanban')
  const [editing, setEditing] = useState<AffairData | null>(null)

  useEffect(() => {
    fetchAffairsByKind()
  }, [fetchAffairsByKind])

  const hasFilters =
    affairFilters.search.trim() !== '' ||
    affairFilters.states.length > 0 ||
    affairFilters.domains.length > 0 ||
    affairFilters.kinds.length > 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <AffairCreateButton />
        <Button variant={view === 'kanban' ? 'default' : 'outline'} size="sm" onClick={() => setView('kanban')}>
          看板
        </Button>
        <Button variant={view === 'list' ? 'default' : 'outline'} size="sm" onClick={() => setView('list')}>
          列表
        </Button>
      </div>
      <AffairsFilterBar />
      {view === 'kanban' ? (
        <AffairKanban affairs={allAffairs} onEdit={(a) => setEditing(a)} />
      ) : (
        <AffairList affairs={allAffairs} onEdit={(a) => setEditing(a)} />
      )}
      {hasFilters && allAffairs.length === 0 && (
        <div className="text-sm text-muted-foreground">当前筛选条件下暂无事务</div>
      )}
      <AffairEditDialog
        affair={editing}
        open={!!editing}
        onOpenChange={(open) => !open && setEditing(null)}
      />
    </div>
  )
}

const VenturesTab = () => {
  const ventures = useRhythmStore((s) => s.ventures)
  const fetchAffairsByKind = useRhythmStore((s) => s.fetchAffairsByKind)
  const [selected, setSelected] = useState<AffairData | null>(null)

  useEffect(() => {
    fetchAffairsByKind()
  }, [fetchAffairsByKind])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-1 space-y-4">
        <div className="font-semibold">事业列表</div>
        {ventures.map((v) => (
          <VentureCard
            key={v.id}
            venture={v}
            selected={selected?.id === v.id}
            onSelect={setSelected}
          />
        ))}
        {ventures.length === 0 && (
          <div className="text-sm text-muted-foreground border rounded-md p-4">暂无进行中的事业</div>
        )}
      </div>
      <div className="lg:col-span-2">
        {selected ? (
          <VentureDetail
            venture={selected}
            onRefresh={() => fetchAffairsByKind()}
          />
        ) : (
          <div className="text-muted-foreground p-4 border rounded-md">选择事业查看详情</div>
        )}
      </div>
    </div>
  )
}

const DisciplineTab = () => {
  const habits = useRhythmStore((s) => s.habits)
  const [selectedHabit, setSelectedHabit] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      <CheckinPanel />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PreceptComplianceChart />
        <div className="border rounded-md p-4">
          <h3 className="font-semibold mb-2">习惯热力图</h3>
          <div className="flex gap-2 mb-2 flex-wrap">
            {habits.slice(0, 5).map((h) => (
              <Button
                key={h.id}
                variant={selectedHabit === h.id ? 'default' : 'outline'}
                size="sm"
                onClick={() => setSelectedHabit(h.id)}
              >
                {h.title}
              </Button>
            ))}
          </div>
          {selectedHabit && <HabitHeatmap affairId={selectedHabit} />}
        </div>
      </div>
    </div>
  )
}

const FoundationTab = () => (
  <div className="space-y-4">
    <EnergyProfileEditor />
    <TemplateEditor />
    <PolicyEditor />
  </div>
)

const ReviewTab = () => {
  const dayReview = useRhythmStore((s) => s.dayReview)
  const weekReview = useRhythmStore((s) => s.weekReview)
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
        <div className="space-y-2">
          <ReviewCard review={dayReview} title="日评分" />
          <ReviewSummaryEditor scope="day" review={dayReview} />
        </div>
        {weekReview ? (
          <WeekReviewCard />
        ) : (
          <ReviewCard review={weekReview} title="周评分" />
        )}
      </div>
      <EncroachmentList />
      <DomainTrendChart />
      <EnergyActualChart />
    </div>
  )
}

export default RhythmPage
