import React, { useState } from 'react'
import { ChallengeType, ChallengeTypeLabels, ChallengeTypeIcons, type ChallengeCreateProps } from '@lib/data/challenge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { CalendarIcon, Plus, Target } from 'lucide-react'
import { format } from 'date-fns'
import { cn } from '@/lib/utils'
import { useIsMobile } from '@/hooks/use-mobile'

interface CreateChallengeDialogProps {
  onCreate: (props: ChallengeCreateProps) => Promise<void>
  isCreating?: boolean
}

const PRESET_DAYS = [7, 14, 21, 30, 100]

const CreateChallengeDialog: React.FC<CreateChallengeDialogProps> = ({
  onCreate,
  isCreating = false,
}) => {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [type, setType] = useState<string>(ChallengeType.NO_SNACK)
  const [days, setDays] = useState<number>(14)
  const [customDays, setCustomDays] = useState<string>('')
  const [startDate, setStartDate] = useState<Date>(new Date())
  const [description, setDescription] = useState('')
  const isMobile = useIsMobile()

  const handleSubmit = async () => {
    const finalDays = customDays ? parseInt(customDays, 10) : days
    
    if (!title || !type || !finalDays || !startDate) {
      return
    }

    await onCreate({
      title,
      type: type as typeof ChallengeType[keyof typeof ChallengeType],
      days: finalDays,
      startDate,
      description,
    })

    // 重置表单并关闭
    setTitle('')
    setType(ChallengeType.NO_SNACK)
    setDays(14)
    setCustomDays('')
    setStartDate(new Date())
    setDescription('')
    setOpen(false)
  }

  const isValid = title && type && (customDays ? parseInt(customDays) > 0 : days > 0) && startDate

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Target className="h-4 w-4" />
          新挑战
        </Button>
      </DialogTrigger>
      
      <DialogContent className={cn('max-w-md', isMobile && 'w-[95vw] max-w-[95vw]')}>
        <DialogHeader>
          <DialogTitle>创建新挑战</DialogTitle>
          <DialogDescription>
            设置你的打卡挑战目标，坚持就是胜利！
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* 挑战标题 */}
          <div className="grid gap-2">
            <Label htmlFor="title">挑战标题</Label>
            <Input
              id="title"
              placeholder="例如：禁止吃零食打卡"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          {/* 挑战类型 */}
          <div className="grid gap-2">
            <Label htmlFor="type">挑战类型</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger>
                <SelectValue placeholder="选择类型" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(ChallengeType).map(([key, value]) => (
                  <SelectItem key={value} value={value}>
                    <div className="flex items-center gap-2">
                      <span>{ChallengeTypeIcons[value as keyof typeof ChallengeTypeIcons]}</span>
                      <span>{ChallengeTypeLabels[value as keyof typeof ChallengeTypeLabels]}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 挑战天数 */}
          <div className="grid gap-2">
            <Label>挑战天数</Label>
            <div className="flex flex-wrap gap-2">
              {PRESET_DAYS.map((d) => (
                <Button
                  key={d}
                  type="button"
                  variant={days === d && !customDays ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setDays(d)
                    setCustomDays('')
                  }}
                >
                  {d}天
                </Button>
              ))}
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  placeholder="自定义"
                  className="w-24"
                  value={customDays}
                  onChange={(e) => setCustomDays(e.target.value)}
                  min={1}
                  max={365}
                />
                <span className="text-sm text-muted-foreground">天</span>
              </div>
            </div>
          </div>

          {/* 开始日期 */}
          <div className="grid gap-2">
            <Label>开始日期</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className={cn(
                    'w-full justify-start text-left font-normal',
                    !startDate && 'text-muted-foreground'
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {startDate ? (
                    format(startDate, 'yyyy年MM月dd日')
                  ) : (
                    <span>选择日期</span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={startDate}
                  onSelect={(date) => date && setStartDate(date)}
                  disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                  
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* 描述（可选） */}
          <div className="grid gap-2">
            <Label htmlFor="description">
              描述 <span className="text-muted-foreground">(可选)</span>
            </Label>
            <Input
              id="description"
              placeholder="添加一些激励自己的话..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* 预览 */}
          {isValid && (
            <div className="rounded-lg bg-muted p-3 text-sm">
              <p className="font-medium text-muted-foreground">挑战预览</p>
              <p className="mt-1">
                {ChallengeTypeIcons[type as keyof typeof ChallengeTypeIcons]} {title}
              </p>
              <p className="text-muted-foreground">
                {customDays || days}天打卡 · 从 {format(startDate, 'MM月dd日')} 开始
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid || isCreating}>
            {isCreating ? '创建中...' : '创建挑战'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default CreateChallengeDialog
