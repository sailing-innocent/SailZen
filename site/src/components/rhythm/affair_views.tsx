import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { AffairData, AffairCreateProps, AffairUpdateProps, AffairDomainValue, AffairKindValue, VentureMeta } from '@lib/data/affair'
import {
  AffairKind,
  AffairDomain,
  AffairStateLabels,
  getAffairPriority,
  getAffairDeadline,
  formatDeadline,
  getDefaultKindMeta,
  syncVentureTargetDate,
} from '@lib/data/affair'
import type { AffairFilterState } from '@lib/store/rhythm'
import { useRhythmStore } from '@lib/store/rhythm'
import { AffairPostponeDialog } from '@components/affair'
import type { AffairAction } from '@lib/api/affair'
import { DateTimePicker } from '@/components/ui/datetime-picker'
import { Plus, Edit2, Trash2, Play, Check, X, Archive, Pause, RotateCcw, Calendar, Clock } from 'lucide-react'

const kindLabel: Record<string, string> = {
  base_rhythm: '基础节奏',
  precept: '戒律',
  habit: '习惯',
  fixed_plan: '刚性规划',
  task_oneoff: '一次性任务',
  task_maintenance: '维护任务',
  venture: '事业',
  async_callback: '异步回调',
  buffer: '缓冲',
  generic: '未分类',
}

const domainColor: Record<string, string> = {
  life: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  work: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  career: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
}

const stateColor: Record<string, string> = {
  INBOX: 'bg-gray-100 text-gray-800',
  PLANNED: 'bg-blue-100 text-blue-800',
  SCHEDULED: 'bg-indigo-100 text-indigo-800',
  DOING: 'bg-yellow-100 text-yellow-800',
  DONE: 'bg-green-100 text-green-800',
  DEFERRED: 'bg-purple-100 text-purple-800',
  CANCELED: 'bg-red-100 text-red-800',
  ACTIVE: 'bg-blue-100 text-blue-800',
  PAUSED: 'bg-orange-100 text-orange-800',
  ARCHIVED: 'bg-gray-100 text-gray-800',
  KICKOFF: 'bg-blue-100 text-blue-800',
  DELEGATED: 'bg-purple-100 text-purple-800',
  REVIEWING: 'bg-yellow-100 text-yellow-800',
  COMPLETED: 'bg-green-100 text-green-800',
}

/** 表单补丁：创建字段 + 更新专用字段（clear_* 仅在编辑语义下生效，创建提交时会剥离） */
type FormPatch = Partial<AffairCreateProps> & Partial<AffairUpdateProps>

interface AffairCardProps {
  affair: AffairData
  onEdit: (affair: AffairData) => void
}

const AffairCard = ({ affair, onEdit }: AffairCardProps) => {
  const deleteAffair = useRhythmStore((s) => s.deleteAffair)
  const transit = useRhythmStore((s) => s.transitAffair)
  const fetchAffairsByKind = useRhythmStore((s) => s.fetchAffairsByKind)
  const fetchDashboard = useRhythmStore((s) => s.fetchDashboard)
  const [postponeOpen, setPostponeOpen] = useState(false)
  const priority = getAffairPriority(getAffairDeadline(affair), affair.state)
  const priorityClass = {
    urgent: 'border-l-4 border-red-500',
    high: 'border-l-4 border-orange-400',
    normal: 'border-l-4 border-blue-300',
    low: 'border-l-4 border-gray-200',
  }[priority]

  const availableActions = (): AffairAction[] => {
    const s = affair.state
    if (s === 'DONE' || s === 'CANCELED' || s === 'ARCHIVED' || s === 'COMPLETED') return []
    if (affair.kind === 'async_callback') {
      if (s === 'INBOX') return ['confirm']
      if (s === 'ACTIVE' || s === 'KICKOFF') return ['handoff', 'pause']
      if (s === 'DELEGATED') return ['return_review']
      if (s === 'REVIEWING') return ['approve', 'request_revision']
      if (s === 'PAUSED') return ['resume']
      return []
    }
    if (['base_rhythm', 'precept', 'habit', 'task_maintenance', 'venture'].includes(affair.kind)) {
      if (s === 'INBOX') return ['confirm']
      if (s === 'ACTIVE') return ['pause', 'archive']
      if (s === 'PAUSED') return ['resume', 'archive']
      return []
    }
    if (s === 'INBOX') return ['confirm', 'dismiss']
    if (s === 'PLANNED' || s === 'SCHEDULED') return ['start', 'defer', 'cancel']
    if (s === 'DOING') return ['finish', 'cancel']
    if (s === 'DEFERRED') return ['replan', 'cancel']
    return []
  }

  const actionIcons: Record<string, React.ReactNode> = {
    confirm: <Check className="h-3 w-3" />,
    start: <Play className="h-3 w-3" />,
    finish: <Check className="h-3 w-3" />,
    cancel: <X className="h-3 w-3" />,
    dismiss: <X className="h-3 w-3" />,
    defer: <Calendar className="h-3 w-3" />,
    replan: <RotateCcw className="h-3 w-3" />,
    pause: <Pause className="h-3 w-3" />,
    resume: <Play className="h-3 w-3" />,
    archive: <Archive className="h-3 w-3" />,
    handoff: <Clock className="h-3 w-3" />,
    return_review: <RotateCcw className="h-3 w-3" />,
    approve: <Check className="h-3 w-3" />,
    request_revision: <RotateCcw className="h-3 w-3" />,
  }

  const handleAction = async (action: AffairAction) => {
    if (action === 'defer') {
      // 延期走 AffairPostponeDialog（内部复用 affairs store 的 confirm/defer），
      // 关闭后刷新 rhythm 分片保持看板/概览一致。
      setPostponeOpen(true)
      return
    }
    await transit(affair.id, action)
  }

  const handlePostponeClose = (open: boolean) => {
    setPostponeOpen(open)
    if (!open) {
      fetchAffairsByKind().catch(() => {})
      fetchDashboard().catch(() => {})
    }
  }

  return (
    <div className={`rounded-md border p-3 bg-card ${priorityClass}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-medium truncate">{affair.title}</div>
          <div className="text-xs text-muted-foreground truncate">
            {kindLabel[affair.kind] || affair.kind} · {formatDeadline(getAffairDeadline(affair))}
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(affair)}>
            <Edit2 className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => deleteAffair(affair.id)}>
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1 mt-2">
        <Badge variant="outline" className={domainColor[affair.domain] ?? ''}>
          {affair.domain}
        </Badge>
        <Badge variant="outline" className={stateColor[affair.state] ?? ''}>
          {AffairStateLabels[affair.state]}
        </Badge>
        <Badge variant="outline">重要 {affair.importance}</Badge>
        <Badge variant="outline">⚡ {affair.energy_cost}</Badge>
        {availableActions().map((action) => (
          <Button
            key={action}
            variant="outline"
            size="sm"
            className="h-6 px-1.5 text-xs"
            onClick={() => handleAction(action)}
          >
            {actionIcons[action]}
            <span className="ml-1">{action}</span>
          </Button>
        ))}
      </div>
      <AffairPostponeDialog affair={affair} open={postponeOpen} onOpenChange={handlePostponeClose} />
    </div>
  )
}

const applyFilters = (affairs: AffairData[], filters: AffairFilterState): AffairData[] => {
  const search = filters.search.trim().toLowerCase()
  return affairs.filter((a) => {
    if (search && !a.title.toLowerCase().includes(search)) return false
    if (filters.states.length > 0 && !filters.states.includes(a.state)) return false
    if (filters.domains.length > 0 && !filters.domains.includes(a.domain)) return false
    if (filters.kinds.length > 0 && !filters.kinds.includes(a.kind)) return false
    return true
  })
}

interface AffairKanbanProps {
  affairs: AffairData[]
  onEdit: (affair: AffairData) => void
}

export const AffairKanban = ({ affairs, onEdit }: AffairKanbanProps) => {
  const filters = useRhythmStore((s) => s.affairFilters)
  const groups: Record<string, AffairData[]> = {}
  Object.values(AffairKind).forEach((k) => (groups[k] = []))
  applyFilters(affairs, filters).forEach((a) => {
    if (!groups[a.kind]) groups[a.kind] = []
    groups[a.kind].push(a)
  })

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Object.entries(groups)
        .filter(([, items]) => items.length > 0)
        .map(([kind, items]) => (
          <Card key={kind} className="min-w-[240px]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold">
                {kindLabel[kind] || kind} ({items.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {items.map((affair) => (
                <AffairCard key={affair.id} affair={affair} onEdit={onEdit} />
              ))}
            </CardContent>
          </Card>
        ))}
    </div>
  )
}

interface AffairListProps {
  affairs: AffairData[]
  onEdit: (affair: AffairData) => void
}

export const AffairList = ({ affairs, onEdit }: AffairListProps) => {
  return (
    <div className="space-y-2">
      {affairs.map((affair) => (
        <AffairCard key={affair.id} affair={affair} onEdit={onEdit} />
      ))}
    </div>
  )
}

const emptyCreate: AffairCreateProps = {
  title: '',
  description: '',
  domain: 'work',
  kind: 'task_oneoff',
  kind_meta: {},
  state: 'INBOX',
  importance: 3,
  energy_cost: 10,
  est_minutes: 30,
  fallback_plan: '',
}

interface AffairCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const AffairCreateDialog = ({ open, onOpenChange }: AffairCreateDialogProps) => {
  const createAffair = useRhythmStore((s) => s.createAffair)
  const [data, setData] = useState<AffairCreateProps>({ ...emptyCreate })

  const update = (patch: FormPatch) => {
    const { clear_urgency_ddl: _c1, clear_window: _c2, ...rest } = patch
    const next: AffairCreateProps = { ...data, ...rest }
    if (patch.kind && patch.kind !== data.kind) {
      next.kind_meta = getDefaultKindMeta(patch.kind as typeof AffairKind[keyof typeof AffairKind])
    }
    setData(next)
  }

  const handleSubmit = async () => {
    if (!data.title.trim()) return
    // 创建语义不接受 clear_* 标志（目标日为空时直接不传 DDL 即可），这里统一剥离
    const { clear_urgency_ddl: _c1, clear_window: _c2, ...createProps } = data as AffairCreateProps & Partial<AffairUpdateProps>
    await createAffair(createProps)
    setData({ ...emptyCreate })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>新建事务</DialogTitle>
        </DialogHeader>
        <AffairForm data={data} onChange={update} />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit}>创建</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface AffairEditDialogProps {
  affair: AffairData | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const AffairEditDialog = ({ affair, open, onOpenChange }: AffairEditDialogProps) => {
  const updateAffair = useRhythmStore((s) => s.updateAffair)
  const [data, setData] = useState<FormPatch>({})

  const update = (patch: FormPatch) => setData((d) => ({ ...d, ...patch }))

  const handleSubmit = async () => {
    if (!affair) return
    await updateAffair(affair.id, data as AffairUpdateProps)
    setData({})
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑事务 #{affair?.id}</DialogTitle>
        </DialogHeader>
        {affair && <AffairForm data={{ ...affair, ...data }} onChange={update} />}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Kind-specific meta subforms
// ---------------------------------------------------------------------------

const num = (v: string, fallback = 0): number => {
  const n = parseFloat(v)
  return Number.isNaN(n) ? fallback : n
}

const parseNumList = (v: string): number[] =>
  v
    .split(/[,，\s]+/)
    .map((s) => parseInt(s, 10))
    .filter((n) => !Number.isNaN(n))

/** 通用 bool 选择（Switch 需要受控 label，Select 更紧凑） */
const BoolSelect = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
  <Select value={String(value)} onValueChange={(v) => onChange(v === 'true')}>
    <SelectTrigger>
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="true">是</SelectItem>
      <SelectItem value="false">否</SelectItem>
    </SelectContent>
  </Select>
)

interface MetaSubformProps {
  meta: Record<string, unknown>
  onField: (patch: Record<string, unknown>) => void
}

const PreceptMetaForm = ({ meta, onField }: MetaSubformProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">戒律参数</div>
    <div className="space-y-2">
      <Label>规则文本</Label>
      <Input value={String(meta.rule_text ?? '')} onChange={(e) => onField({ rule_text: e.target.value })} />
    </div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>周期</Label>
        <Select value={String(meta.cycle ?? 'daily')} onValueChange={(v) => onField({ cycle: v })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">每日</SelectItem>
            <SelectItem value="weekly">每周</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>核销时间 (HH:MM)</Label>
        <Input value={String(meta.check_time ?? '')} onChange={(e) => onField({ check_time: e.target.value })} />
      </div>
      <div className="space-y-2">
        <Label>严重级别</Label>
        <Select value={String(meta.severity ?? 'soft')} onValueChange={(v) => onField({ severity: v })}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="hard">hard</SelectItem>
            <SelectItem value="soft">soft</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-2">
        <Label>占用分钟</Label>
        <Input type="number" value={Number(meta.block_minutes ?? 0)} onChange={(e) => onField({ block_minutes: num(e.target.value) })} />
      </div>
    </div>
    <div className="space-y-2">
      <Label>周掩码 (逗号分隔，0=周日)</Label>
      <Input
        value={Array.isArray(meta.weekday_mask) ? (meta.weekday_mask as number[]).join(',') : ''}
        onChange={(e) => onField({ weekday_mask: parseNumList(e.target.value) })}
      />
    </div>
  </div>
)

const HabitMetaForm = ({ meta, onField }: MetaSubformProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">习惯参数</div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>每周频次</Label>
        <Input type="number" min={0} max={7} value={Number(meta.freq_per_week ?? 0)} onChange={(e) => onField({ freq_per_week: num(e.target.value) })} />
      </div>
      <div className="space-y-2">
        <Label>单次最少分钟</Label>
        <Input type="number" value={Number(meta.min_session_minutes ?? 0)} onChange={(e) => onField({ min_session_minutes: num(e.target.value) })} />
      </div>
      <div className="space-y-2">
        <Label>当前连击</Label>
        <Input type="number" value={Number(meta.streak ?? 0)} onChange={(e) => onField({ streak: num(e.target.value) })} />
      </div>
      <div className="space-y-2">
        <Label>最佳连击</Label>
        <Input type="number" value={Number(meta.best_streak ?? 0)} onChange={(e) => onField({ best_streak: num(e.target.value) })} />
      </div>
    </div>
    <div className="space-y-2">
      <Label>偏好时段 (逗号分隔)</Label>
      <Input
        value={Array.isArray(meta.preferred_slots) ? (meta.preferred_slots as string[]).join(',') : ''}
        onChange={(e) => onField({ preferred_slots: e.target.value.split(/[,，\s]+/).filter(Boolean) })}
      />
    </div>
  </div>
)

const MaintenanceMetaForm = ({ meta, onField }: MetaSubformProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">维护任务参数</div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>间隔天数</Label>
        <Input type="number" min={1} value={Number(meta.interval_days ?? 7)} onChange={(e) => onField({ interval_days: num(e.target.value, 7) })} />
      </div>
      <div className="space-y-2">
        <Label>单次分钟</Label>
        <Input type="number" value={Number(meta.session_minutes ?? 60)} onChange={(e) => onField({ session_minutes: num(e.target.value, 60) })} />
      </div>
    </div>
  </div>
)

const FixedPlanMetaForm = ({ meta, onField }: MetaSubformProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">刚性规划参数</div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>不可移动</Label>
        <BoolSelect value={Boolean(meta.immovable ?? true)} onChange={(v) => onField({ immovable: v })} />
      </div>
      <div className="space-y-2">
        <Label>legs (逗号分隔分钟)</Label>
        <Input
          value={Array.isArray(meta.legs) ? (meta.legs as number[]).join(',') : ''}
          onChange={(e) => onField({ legs: parseNumList(e.target.value) })}
        />
      </div>
      <div className="space-y-2">
        <Label>固定开始</Label>
        <Input value={String(meta.fixed_start ?? '')} placeholder="HH:MM 或 ISO 时间" onChange={(e) => onField({ fixed_start: e.target.value || null })} />
      </div>
      <div className="space-y-2">
        <Label>固定结束</Label>
        <Input value={String(meta.fixed_end ?? '')} placeholder="HH:MM 或 ISO 时间" onChange={(e) => onField({ fixed_end: e.target.value || null })} />
      </div>
    </div>
  </div>
)

const AsyncCallbackMetaForm = ({ meta, onField }: MetaSubformProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">异步回调参数</div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>当前阶段</Label>
        <Input value={String(meta.current_phase ?? '')} onChange={(e) => onField({ current_phase: e.target.value })} />
      </div>
      <div className="space-y-2">
        <Label>委托对象</Label>
        <Input value={String(meta.delegate_to ?? '')} onChange={(e) => onField({ delegate_to: e.target.value })} />
      </div>
      <div className="space-y-2">
        <Label>当前轮次</Label>
        <Input type="number" min={1} value={Number(meta.round ?? 1)} onChange={(e) => onField({ round: num(e.target.value, 1) })} />
      </div>
      <div className="space-y-2">
        <Label>最大轮次</Label>
        <Input type="number" min={1} value={Number(meta.max_rounds ?? 3)} onChange={(e) => onField({ max_rounds: num(e.target.value, 3) })} />
      </div>
      <div className="space-y-2">
        <Label>预计等待小时</Label>
        <Input type="number" value={Number(meta.est_wait_hours ?? 24)} onChange={(e) => onField({ est_wait_hours: num(e.target.value, 24) })} />
      </div>
      <div className="space-y-2">
        <Label>仅工作时段</Label>
        <BoolSelect value={Boolean(meta.work_hours_only ?? false)} onChange={(v) => onField({ work_hours_only: v })} />
      </div>
    </div>
  </div>
)

interface VentureMetaFormProps extends MetaSubformProps {
  /** venture 专属：目标日变化时联动 urgency_ddl / clear_urgency_ddl（单一来源） */
  onVentureField: (patch: Partial<VentureMeta>) => void
}

const VentureMetaForm = ({ meta, onVentureField }: VentureMetaFormProps) => (
  <div className="space-y-3 rounded-md border p-3 bg-muted/20">
    <div className="text-sm font-medium">事业参数</div>
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <Label>目标日</Label>
        <Input
          type="date"
          value={String(meta.target_date ?? '')}
          onChange={(e) => onVentureField({ target_date: e.target.value || null })}
        />
      </div>
      <div className="space-y-2">
        <Label>每周预算小时</Label>
        <Input
          type="number"
          step="0.5"
          value={Number(meta.weekly_budget_hours ?? 0)}
          onChange={(e) => onVentureField({ weekly_budget_hours: num(e.target.value) })}
        />
      </div>
      <div className="space-y-2">
        <Label>总预估小时</Label>
        <Input
          type="number"
          step="0.5"
          value={Number(meta.total_est_hours ?? 0)}
          onChange={(e) => onVentureField({ total_est_hours: num(e.target.value) })}
        />
      </div>
      <div className="space-y-2">
        <Label>仅业余时间</Label>
        <BoolSelect value={Boolean(meta.spare_time_only ?? true)} onChange={(v) => onVentureField({ spare_time_only: v })} />
      </div>
    </div>
    <p className="text-xs text-muted-foreground">
      目标日与截止时间（urgency_ddl）自动联动：设置目标日会同步截止时间，清空目标日会同时清除两者。
    </p>
  </div>
)

const AffairForm = ({
  data,
  onChange,
}: {
  data: Partial<AffairCreateProps>
  onChange: (patch: FormPatch) => void
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const kind = data.kind ?? 'task_oneoff'
  const meta = (data.kind_meta ?? {}) as Record<string, unknown>

  const onMetaField = (patch: Record<string, unknown>) => {
    onChange({ kind_meta: { ...meta, ...patch } })
  }

  const onVentureField = (patch: Partial<VentureMeta>) => {
    const merged = { ...meta, ...patch } as VentureMeta
    const synced = syncVentureTargetDate(merged)
    onChange({
      kind_meta: synced.kind_meta,
      urgency_ddl: synced.urgency_ddl,
      clear_urgency_ddl: synced.clear_urgency_ddl,
    })
  }

  return (
    <div className="space-y-4 py-4">
      <div className="space-y-2">
        <Label>标题</Label>
        <Input value={data.title ?? ''} onChange={(e) => onChange({ title: e.target.value })} />
      </div>
      <div className="space-y-2">
        <Label>描述</Label>
        <Textarea value={data.description ?? ''} onChange={(e) => onChange({ description: e.target.value })} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Domain</Label>
          <Select value={data.domain ?? 'work'} onValueChange={(v) => onChange({ domain: v as AffairDomainValue })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(AffairDomain).map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Kind</Label>
          <Select value={kind} onValueChange={(v) => onChange({ kind: v as AffairKindValue })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.values(AffairKind).map((k) => (
                <SelectItem key={k} value={k}>
                  {kindLabel[k] || k}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>重要性</Label>
          <Input
            type="number"
            min={1}
            max={5}
            value={data.importance ?? 3}
            onChange={(e) => onChange({ importance: parseInt(e.target.value, 10) })}
          />
        </div>
        <div className="space-y-2">
          <Label>精力成本</Label>
          <Input
            type="number"
            min={0}
            value={data.energy_cost ?? 10}
            onChange={(e) => onChange({ energy_cost: parseInt(e.target.value, 10) })}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>预计分钟</Label>
          <Input
            type="number"
            min={0}
            value={data.est_minutes ?? 30}
            onChange={(e) => onChange({ est_minutes: parseInt(e.target.value, 10) })}
          />
        </div>
        {kind !== 'venture' && (
          <div className="space-y-2">
            <DateTimePicker
              label="截止时间"
              value={data.urgency_ddl}
              onChange={(v) => onChange({ urgency_ddl: v })}
            />
          </div>
        )}
      </div>

      {kind === 'precept' && <PreceptMetaForm meta={meta} onField={onMetaField} />}
      {kind === 'habit' && <HabitMetaForm meta={meta} onField={onMetaField} />}
      {kind === 'task_maintenance' && <MaintenanceMetaForm meta={meta} onField={onMetaField} />}
      {kind === 'fixed_plan' && <FixedPlanMetaForm meta={meta} onField={onMetaField} />}
      {kind === 'async_callback' && <AsyncCallbackMetaForm meta={meta} onField={onMetaField} />}
      {kind === 'venture' && <VentureMetaForm meta={meta} onField={onMetaField} onVentureField={onVentureField} />}

      <div className="space-y-2">
        <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdvanced((v) => !v)}>
          {showAdvanced ? '收起高级模式' : '高级模式 (kind_meta JSON)'}
        </Button>
        {showAdvanced && (
          <Textarea
            value={JSON.stringify(meta, null, 2)}
            onChange={(e) => {
              try {
                onChange({ kind_meta: JSON.parse(e.target.value) })
              } catch {
                // ignore invalid JSON while typing
              }
            }}
            className="font-mono text-xs"
          />
        )}
      </div>
    </div>
  )
}

export const AffairCreateButton = () => {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4 mr-1" />
        新建事务
      </Button>
      <AffairCreateDialog open={open} onOpenChange={setOpen} />
    </>
  )
}
