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
import type { TimeBlockData, BlockStatusValue } from '@lib/data/rhythm'
import { useRhythmStore } from '@lib/store/rhythm'
import { formatTime, blockTypeColor, blockTypeLabel, sortBlocks } from './utils'
import { Check, SkipForward, Play, Move } from 'lucide-react'

interface TimeBlockItemProps {
  block: TimeBlockData
}

export const TimeBlockItem = ({ block }: TimeBlockItemProps) => {
  const setBlockStatus = useRhythmStore((s) => s.setBlockStatus)
  const moveBlock = useRhythmStore((s) => s.moveBlock)
  const [isEditing, setIsEditing] = useState(false)
  const [start, setStart] = useState(block.start_time.slice(0, 16))
  const [end, setEnd] = useState(block.end_time.slice(0, 16))

  const handleStatus = (status: BlockStatusValue) => {
    setBlockStatus(block.id, status)
  }

  const handleMove = () => {
    moveBlock(block.id, new Date(start), new Date(end))
    setIsEditing(false)
  }

  const statusActions: { status: BlockStatusValue; icon: React.ReactNode; label: string }[] = [
    { status: 'DONE', icon: <Check className="h-4 w-4" />, label: '完成' },
    { status: 'DOING', icon: <Play className="h-4 w-4" />, label: '进行中' },
    { status: 'SKIPPED', icon: <SkipForward className="h-4 w-4" />, label: '跳过' },
  ]

  return (
    <div className="flex items-center justify-between rounded-md border p-3 gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-2 h-10 rounded ${blockTypeColor(block.block_type)}`} />
        <div className="min-w-0">
          <div className="font-medium truncate">{block.affair_title || blockTypeLabel(block.block_type)}</div>
          <div className="text-sm text-muted-foreground">
            {formatTime(block.start_time)} - {formatTime(block.end_time)}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant="outline">{block.block_type}</Badge>
        <Badge>{block.status}</Badge>
        {!block.pinned && (
          <>
            {statusActions.map((a) => (
              <Button
                key={a.status}
                variant="ghost"
                size="icon"
                onClick={() => handleStatus(a.status)}
                title={a.label}
              >
                {a.icon}
              </Button>
            ))}
            <Dialog open={isEditing} onOpenChange={setIsEditing}>
              <DialogTrigger asChild>
                <Button variant="ghost" size="icon" title="移动">
                  <Move className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>调整时间块</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>开始</Label>
                      <Input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>结束</Label>
                      <Input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} />
                    </div>
                  </div>
                  <Button onClick={handleMove}>保存</Button>
                </div>
              </DialogContent>
            </Dialog>
          </>
        )}
      </div>
    </div>
  )
}

export const TimelineView = () => {
  const timeline = useRhythmStore((s) => s.dayTimeline)
  if (!timeline) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">加载中...</CardContent>
      </Card>
    )
  }

  const sorted = sortBlocks(timeline.blocks)

  return (
    <Card>
      <CardHeader>
        <CardTitle>时间线</CardTitle>
        <CardDescription>
          plan_version {timeline.plan_version} · 缓冲 {timeline.buffer_free_minutes}/{timeline.buffer_total_minutes} 分钟
        </CardDescription>
      </CardHeader>
      <CardContent>
        {sorted.length === 0 && <div className="text-muted-foreground">暂无时间块，点击生成日计划。</div>}
        <div className="space-y-2">
          {sorted.map((block) => (
            <TimeBlockItem key={block.id} block={block} />
          ))}
        </div>
        {timeline.unplaced.length > 0 && (
          <div className="mt-4 p-3 border rounded-md bg-muted">
            <div className="font-medium mb-2">未放置事务</div>
            <div className="space-y-1">
              {timeline.unplaced.map((item) => (
                <div key={item.affair_id} className="text-sm text-muted-foreground">
                  {item.title} — {item.reason}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
