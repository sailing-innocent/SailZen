/**
 * @file timeline_view.tsx
 * @brief Rhythm v2 可视化日程画布（SailTick 自主编排 + 一键微调）
 */

import { useState } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type {
  BlockStatusValue,
  DayTimelineData,
  OccupancyTypeValue,
  TimeBlockData,
} from '@lib/data/rhythm'
import { useRhythmStore } from '@lib/store/rhythm'
import { formatTime, blockTypeColor, blockTypeLabel, sortBlocks } from './utils'
import {
  Check,
  SkipForward,
  Play,
  Clock,
  Trash2,
  Pin,
  Sparkles,
  Plus,
  CalendarOff,
} from 'lucide-react'

const STATUS_BADGE: Record<BlockStatusValue, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
  PLANNED: { label: '计划', variant: 'outline' },
  DOING: { label: '进行中', variant: 'default' },
  DONE: { label: '已完成', variant: 'secondary' },
  SKIPPED: { label: '已跳过', variant: 'outline' },
  MOVED: { label: '已移走', variant: 'outline' },
}

const TimeBlockItem = ({ block }: { block: TimeBlockData }) => {
  const setBlockStatus = useRhythmStore((s) => s.setBlockStatus)
  const moveBlock = useRhythmStore((s) => s.moveBlock)
  const deleteBlock = useRhythmStore((s) => s.deleteBlock)
  const deleteOccupancy = useRhythmStore((s) => s.deleteOccupancy)

  const [isEditing, setIsEditing] = useState(false)
  const [start, setStart] = useState(block.start_time.slice(0, 16))
  const [end, setEnd] = useState(block.end_time.slice(0, 16))

  const note = typeof block.ref?.note === 'string' ? block.ref.note : ''
  const isOccupancy = block.block_type === 'occupied' && block.ref?.source === 'occupancy_api'
  const isDone = block.status === 'DONE'
  const isSkipped = block.status === 'SKIPPED'

  const handleMove = async () => {
    await moveBlock(block.id, new Date(start), new Date(end))
    setIsEditing(false)
  }

  const handleDelete = async () => {
    if (isOccupancy) {
      await deleteOccupancy(block.id)
    } else {
      await deleteBlock(block.id)
    }
  }

  const badgeInfo = STATUS_BADGE[block.status] ?? { label: block.status, variant: 'outline' as const }

  return (
    <div
      className={`flex items-center justify-between rounded-lg border p-3 gap-3 transition-opacity ${
        isDone ? 'bg-muted/40 opacity-80' : isSkipped ? 'opacity-55' : 'bg-card'
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-1.5 self-stretch rounded-full shrink-0 ${blockTypeColor(block.block_type)}`} />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {block.pinned && <Pin className="h-3.5 w-3.5 text-rose-500 shrink-0" />}
            <span className={`font-medium truncate ${isDone ? 'line-through text-muted-foreground' : ''}`}>
              {block.affair_title || blockTypeLabel(block.block_type)}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground mt-0.5">
            <span>
              {formatTime(block.start_time)} - {formatTime(block.end_time)}
            </span>
            <Badge variant="outline" className="text-[10px] py-0 px-1.5">
              {blockTypeLabel(block.block_type)}
            </Badge>
            <Badge variant={badgeInfo.variant} className="text-[10px] py-0 px-1.5">
              {badgeInfo.label}
            </Badge>
          </div>
          {note && <p className="text-xs text-muted-foreground mt-1 truncate">{note}</p>}
        </div>
      </div>

      <div className="flex items-center gap-1 shrink-0">
        {!isOccupancy && (
          <>
            <Button
              variant={isDone ? 'secondary' : 'ghost'}
              size="icon"
              className="h-8 w-8"
              onClick={() => setBlockStatus(block.id, isDone ? 'PLANNED' : 'DONE')}
              title={isDone ? '撤回完成' : '标记完成'}
            >
              <Check className="h-4 w-4" />
            </Button>
            {!isDone && (
              <Button
                variant={block.status === 'DOING' ? 'secondary' : 'ghost'}
                size="icon"
                className="h-8 w-8"
                onClick={() => setBlockStatus(block.id, 'DOING')}
                title="开始进行"
              >
                <Play className="h-4 w-4" />
              </Button>
            )}
            {!isDone && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setBlockStatus(block.id, isSkipped ? 'PLANNED' : 'SKIPPED')}
                title="跳过"
              >
                <SkipForward className="h-4 w-4" />
              </Button>
            )}
          </>
        )}

        {!block.pinned && (
          <Dialog open={isEditing} onOpenChange={setIsEditing}>
            <DialogTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8" title="调整时间">
                <Clock className="h-4 w-4" />
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>调整时间块</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-2">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>开始</Label>
                    <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>结束</Label>
                    <Input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
                  </div>
                </div>
                <Button onClick={handleMove} className="w-full">
                  保存
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        )}

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive"
          onClick={handleDelete}
          title="移除"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export const TimelineView = ({ timeline }: { timeline: DayTimelineData | null }) => {
  const createBlock = useRhythmStore((s) => s.createBlock)
  const createOccupancy = useRhythmStore((s) => s.createOccupancy)

  const [addBlockOpen, setAddBlockOpen] = useState(false)
  const [blkTitle, setBlkTitle] = useState('')
  const [blkStart, setBlkStart] = useState('10:00')
  const [blkEnd, setBlkEnd] = useState('11:00')
  const [blkType, setBlkType] = useState('focus')

  const [addOccOpen, setAddOccOpen] = useState(false)
  const [occLabel, setOccLabel] = useState('')
  const [occType, setOccType] = useState<OccupancyTypeValue>('meeting')
  const [occStart, setOccStart] = useState('14:00')
  const [occEnd, setOccEnd] = useState('15:00')

  const handleCreateBlock = async () => {
    if (!blkTitle.trim()) return
    await createBlock({
      title: blkTitle.trim(),
      start: blkStart,
      end: blkEnd,
      block_type: blkType,
    })
    setBlkTitle('')
    setAddBlockOpen(false)
  }

  const handleCreateOcc = async () => {
    await createOccupancy({
      occupancy_type: occType,
      start: occStart,
      end: occEnd,
      label: occLabel.trim() || occType,
    })
    setOccLabel('')
    setAddOccOpen(false)
  }

  const sorted = sortBlocks(timeline?.blocks ?? [])
  const completedMin = timeline?.completed_minutes ?? 0
  const plannedMin = timeline?.planned_minutes ?? 0

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">当日日程画布</CardTitle>
            <CardDescription>
              {plannedMin > 0
                ? `已完成 ${completedMin} / ${plannedMin} 分钟 · v${timeline?.plan_version ?? 0}`
                : '由 SailTick 按你的节奏自主排布，随时可微调'}
            </CardDescription>
          </div>
          <div className="flex items-center gap-1.5">
            <Dialog open={addOccOpen} onOpenChange={setAddOccOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <CalendarOff className="h-3.5 w-3.5 mr-1" />
                  钉占用
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>添加刚性占用（会议/请假/外出）</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div className="space-y-1.5">
                    <Label>事项名称</Label>
                    <Input
                      placeholder="例如：项目评审会"
                      value={occLabel}
                      onChange={(e) => setOccLabel(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>类型</Label>
                    <Select value={occType} onValueChange={(v) => setOccType(v as OccupancyTypeValue)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="meeting">会议</SelectItem>
                        <SelectItem value="leave">请假</SelectItem>
                        <SelectItem value="appointment">预约</SelectItem>
                        <SelectItem value="travel">出行</SelectItem>
                        <SelectItem value="other">其他</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>开始</Label>
                      <Input type="time" value={occStart} onChange={(e) => setOccStart(e.target.value)} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>结束</Label>
                      <Input type="time" value={occEnd} onChange={(e) => setOccEnd(e.target.value)} />
                    </div>
                  </div>
                  <Button onClick={handleCreateOcc} className="w-full">
                    钉入时间线
                  </Button>
                </div>
              </DialogContent>
            </Dialog>

            <Dialog open={addBlockOpen} onOpenChange={setAddBlockOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Plus className="h-3.5 w-3.5 mr-1" />
                  补一块
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>手动补一个时间块</DialogTitle>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div className="space-y-1.5">
                    <Label>标题</Label>
                    <Input
                      placeholder="例如：推进核心原型"
                      value={blkTitle}
                      onChange={(e) => setBlkTitle(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>类型</Label>
                    <Select value={blkType} onValueChange={setBlkType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="focus">专注推进</SelectItem>
                        <SelectItem value="career">个人项目</SelectItem>
                        <SelectItem value="habit">运动/习惯</SelectItem>
                        <SelectItem value="light">轻松事项</SelectItem>
                        <SelectItem value="rest">休息缓冲</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label>开始</Label>
                      <Input type="time" value={blkStart} onChange={(e) => setBlkStart(e.target.value)} />
                    </div>
                    <div className="space-y-1.5">
                      <Label>结束</Label>
                      <Input type="time" value={blkEnd} onChange={(e) => setBlkEnd(e.target.value)} />
                    </div>
                  </div>
                  <Button onClick={handleCreateBlock} disabled={!blkTitle.trim()} className="w-full">
                    添加
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {timeline?.ai_rationale && (
          <div className="mt-2 flex items-start gap-2 rounded-md bg-primary/5 border border-primary/15 px-3 py-2 text-xs text-foreground/90">
            <Sparkles className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
            <span>{timeline.ai_rationale}</span>
          </div>
        )}
      </CardHeader>

      <CardContent>
        {sorted.length === 0 ? (
          <div className="text-sm text-muted-foreground py-8 text-center">
            今天还没有排布好的时间块。可以直接在上方告诉 SailTick 你今天的状态或想推进的事，让它马上帮你排妥。
          </div>
        ) : (
          <div className="space-y-2">
            {sorted.map((block) => (
              <TimeBlockItem key={block.id} block={block} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
