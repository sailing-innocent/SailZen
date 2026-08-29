import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import type { AffairData } from '@lib/data/affair'
import { getKindMeta } from '@lib/data/affair'
import { useRhythmStore } from '@lib/store/rhythm'
import { api_add_milestone, api_get_venture_progress } from '@lib/api/affair'
import { api_get_venture_burndown } from '@lib/api/rhythm'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { formatDate } from './utils'
import { Check, Plus, Target } from 'lucide-react'

interface VentureCardProps {
  venture: AffairData
  onSelect: (v: AffairData) => void
  selected: boolean
}

export const VentureCard = ({ venture, onSelect, selected }: VentureCardProps) => {
  const meta = getKindMeta(venture, 'venture')
  const targetDate = meta?.target_date ? formatDate(meta.target_date) : '无目标日'
  return (
    <Card
      className={`cursor-pointer hover:shadow-md transition-shadow ${selected ? 'ring-2 ring-primary' : ''}`}
      onClick={() => onSelect(venture)}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{venture.title}</CardTitle>
        <CardDescription>目标日: {targetDate}</CardDescription>
      </CardHeader>
      <CardContent>
        <Badge variant="outline">{venture.state}</Badge>
        <div className="mt-2 text-sm text-muted-foreground">
          周预算: {meta?.weekly_budget_hours ?? 0} h · 总预估: {meta?.total_est_hours ?? 0} h
        </div>
      </CardContent>
    </Card>
  )
}

export const MilestoneTree = ({
  venture,
  onRefresh,
}: {
  venture: AffairData
  onRefresh: () => void
}) => {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [estMinutes, setEstMinutes] = useState(60)

  const handleAdd = async () => {
    await api_add_milestone(venture.id, { title, est_minutes: estMinutes })
    setTitle('')
    setEstMinutes(60)
    setOpen(false)
    onRefresh()
  }

  const milestones = venture.kind_meta?.milestones as AffairData[] | undefined

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle>里程碑</CardTitle>
        <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          添加
        </Button>
      </CardHeader>
      <CardContent>
        {!milestones || milestones.length === 0 ? (
          <div className="text-muted-foreground">暂无里程碑</div>
        ) : (
          <div className="space-y-2">
            {milestones.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-md border p-2">
                <div>
                  <div className="font-medium">{m.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {m.est_minutes} 分钟 · {m.state}
                  </div>
                </div>
                {m.state === 'DONE' && <Check className="h-4 w-4 text-green-500" />}
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加里程碑</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>标题</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>预计分钟</Label>
              <Input
                type="number"
                value={estMinutes}
                onChange={(e) => setEstMinutes(parseInt(e.target.value, 10))}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={handleAdd}>添加</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export const VentureProgressChart = ({ ventureId }: { ventureId: number }) => {
  const [burndown, setBurndown] = useState<Awaited<ReturnType<typeof api_get_venture_burndown>> | null>(null)

  useEffect(() => {
    api_get_venture_burndown(ventureId).then(setBurndown)
  }, [ventureId])

  if (!burndown) return <div>加载中...</div>

  const chartData = burndown.weeks.map((week, idx) => ({
    week,
    planned: burndown.planned[idx],
    actual: burndown.actual[idx],
    milestones: burndown.milestones_done[idx],
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>燃尽图</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="week" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="planned" stroke="#8884d8" name="计划小时" />
              <Line type="monotone" dataKey="actual" stroke="#82ca9d" name="实际完成小时" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

export const VentureDetail = ({
  venture,
  onRefresh,
}: {
  venture: AffairData
  onRefresh: () => void
}) => {
  const meta = getKindMeta(venture, 'venture')
  const [progress, setProgress] = useState<Awaited<ReturnType<typeof api_get_venture_progress>> | null>(null)

  useEffect(() => {
    api_get_venture_progress(venture.id).then(setProgress)
  }, [venture.id])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            {venture.title}
          </CardTitle>
          <CardDescription>
            目标日: {meta?.target_date ? formatDate(meta.target_date) : '未设置'} · 周预算: {meta?.weekly_budget_hours ?? 0} h
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {progress && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-muted-foreground text-sm">剩余周数</div>
                  <div className="text-xl font-bold">{progress.weeks_left ?? '-'}</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-sm">本周消耗</div>
                  <div className="text-xl font-bold">{progress.week_consumed_hours} h</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-sm">累计完成</div>
                  <div className="text-xl font-bold">{progress.total_done_hours} h</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-sm">压力指数</div>
                  <div className="text-xl font-bold">{progress.countdown_pressure ?? '-'}</div>
                </div>
              </div>
              <div>
                <div className="text-sm text-muted-foreground mb-1">里程碑完成度</div>
                <Progress value={progress.completion_ratio * 100} />
              </div>
            </>
          )}
        </CardContent>
      </Card>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MilestoneTree venture={venture} onRefresh={onRefresh} />
        <VentureProgressChart ventureId={venture.id} />
      </div>
    </div>
  )
}
