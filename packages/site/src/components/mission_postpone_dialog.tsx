import React, { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { useMissionsStore, type MissionsState } from '@lib/store/project'
import type { MissionData } from '@lib/data/project'
import { parseDdl } from '@lib/data/project'

export interface MissionPostponeDialogProps {
  mission: MissionData
  open: boolean
  onOpenChange: (open: boolean) => void
}

const MissionPostponeDialog: React.FC<MissionPostponeDialogProps> = ({
  mission,
  open,
  onOpenChange,
}) => {
  const [days, setDays] = useState<number>(7)
  const [isLoading, setIsLoading] = useState(false)

  const postponeMission = useMissionsStore((state: MissionsState) => state.postponeMission)

  // Calculate new deadline preview
  const getNewDeadlinePreview = (): string => {
    const currentDdl = parseDdl(mission.ddl)
    if (!currentDdl) return '未设置'
    const newDdl = new Date(currentDdl.getTime() + days * 24 * 60 * 60 * 1000)
    return newDdl.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      weekday: 'long',
    })
  }

  const getCurrentDeadline = (): string => {
    const currentDdl = parseDdl(mission.ddl)
    if (!currentDdl) return '未设置'
    return currentDdl.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      weekday: 'long',
    })
  }

  const handlePostpone = async () => {
    if (days <= 0) return
    setIsLoading(true)
    try {
      await postponeMission(mission.id, days)
      onOpenChange(false)
    } finally {
      setIsLoading(false)
    }
  }

  const quickOptions = [
    { label: '1 天', value: 1 },
    { label: '3 天', value: 3 },
    { label: '1 周', value: 7 },
    { label: '2 周', value: 14 },
    { label: '1 月', value: 30 },
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>延期任务</DialogTitle>
          <DialogDescription>
            将任务「{mission.name}」的截止日期延后
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Current deadline */}
          <div className="space-y-1">
            <Label className="text-muted-foreground">当前截止日期</Label>
            <p className="text-sm font-medium">{getCurrentDeadline()}</p>
          </div>

          {/* Quick options */}
          <div className="space-y-2">
            <Label>快速选择</Label>
            <div className="flex flex-wrap gap-2">
              {quickOptions.map((option) => (
                <Button
                  key={option.value}
                  variant={days === option.value ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setDays(option.value)}
                >
                  {option.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Custom days input */}
          <div className="space-y-2">
            <Label htmlFor="days">自定义天数</Label>
            <div className="flex items-center gap-2">
              <Input
                id="days"
                type="number"
                min={1}
                max={365}
                value={days}
                onChange={(e) => setDays(parseInt(e.target.value) || 1)}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">天</span>
            </div>
          </div>

          {/* New deadline preview */}
          <div className="space-y-1 p-3 bg-muted rounded-md">
            <Label className="text-muted-foreground">新截止日期</Label>
            <p className="text-sm font-medium text-primary">{getNewDeadlinePreview()}</p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handlePostpone} disabled={isLoading || days <= 0}>
            {isLoading ? '延期中...' : '确认延期'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default MissionPostponeDialog
