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
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { AffairData, AffairCreateProps, AffairUpdateProps } from '@lib/data/affair'
import { AffairKind, AffairDomain, AffairState, AffairStateLabels, getAffairPriority, getAffairDeadline, formatDeadline, getDefaultKindMeta } from '@lib/data/affair'
import type { AffairAction } from '@lib/api/affair'
import { useRhythmStore } from '@lib/store/rhythm'
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

interface AffairCardProps {
  affair: AffairData
  onEdit: (affair: AffairData) => void
}

const AffairCard = ({ affair, onEdit }: AffairCardProps) => {
  const deleteAffair = useRhythmStore((s) => s.deleteAffair)
  const transit = useRhythmStore((s) => s.transitAffair)
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
      const deferTo = new Date(Date.now() + 24 * 60 * 60 * 1000)
      await transit(affair.id, action, { defer_to: deferTo.toISOString() })
    } else {
      await transit(affair.id, action)
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
    </div>
  )
}

interface AffairKanbanProps {
  affairs: AffairData[]
  onEdit: (affair: AffairData) => void
}

export const AffairKanban = ({ affairs, onEdit }: AffairKanbanProps) => {
  const groups: Record<string, AffairData[]> = {}
  Object.values(AffairKind).forEach((k) => (groups[k] = []))
  affairs.forEach((a) => {
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

  const handleSubmit = async () => {
    if (!data.title.trim()) return
    await createAffair(data)
    setData({ ...emptyCreate })
    onOpenChange(false)
  }

  const update = (patch: Partial<AffairCreateProps>) => {
    const next = { ...data, ...patch }
    if (patch.kind && patch.kind !== data.kind) {
      next.kind_meta = getDefaultKindMeta(patch.kind as typeof AffairKind[keyof typeof AffairKind])
    }
    setData(next)
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
  const [data, setData] = useState<Partial<AffairCreateProps>>({})

  const update = (patch: Partial<AffairCreateProps>) => setData((d) => ({ ...d, ...patch }))

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

const AffairForm = ({
  data,
  onChange,
}: {
  data: Partial<AffairCreateProps>
  onChange: (patch: Partial<AffairCreateProps>) => void
}) => {
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
          <Select value={data.domain ?? 'work'} onValueChange={(v) => onChange({ domain: v })}>
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
          <Select value={data.kind ?? 'task_oneoff'} onValueChange={(v) => onChange({ kind: v })}>
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
        <div className="space-y-2">
          <Label>截止时间</Label>
          <Input
            type="datetime-local"
            value={
              data.urgency_ddl
                ? new Date(data.urgency_ddl).toISOString().slice(0, 16)
                : ''
            }
            onChange={(e) => onChange({ urgency_ddl: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>kind_meta (JSON)</Label>
        <Textarea
          value={JSON.stringify(data.kind_meta ?? {}, null, 2)}
          onChange={(e) => {
            try {
              onChange({ kind_meta: JSON.parse(e.target.value) })
            } catch {
              // ignore invalid JSON while typing
            }
          }}
          className="font-mono text-xs"
        />
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
