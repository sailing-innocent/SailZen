import React, { useState } from 'react'
import { CheckInStatus, formatChallengeDate, type CheckInData, type CheckInStatusValue } from '@lib/data/challenge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { CheckCircle2, XCircle, RotateCcw, Trophy } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CheckInDialogProps {
  isOpen: boolean
  onClose: () => void
  day: number
  date: Date
  currentStatus: CheckInStatusValue
  challengeTitle: string
  onSuccess: () => void
  onFail: () => void
  onReset: () => void
  isLoading?: boolean
}

const CheckInDialog: React.FC<CheckInDialogProps> = ({
  isOpen,
  onClose,
  day,
  date,
  currentStatus,
  challengeTitle,
  onSuccess,
  onFail,
  onReset,
  isLoading = false,
}) => {
  const [note, setNote] = useState('')
  const isPending = currentStatus === CheckInStatus.PENDING
  const isSuccess = currentStatus === CheckInStatus.SUCCESS
  const isFailed = currentStatus === CheckInStatus.FAILED

  const handleSuccess = () => {
    onSuccess()
    setNote('')
  }

  const handleFail = () => {
    onFail()
    setNote('')
  }

  const handleReset = () => {
    onReset()
    setNote('')
  }

  // 获取状态对应的UI
  const getStatusUI = () => {
    if (isSuccess) {
      return {
        icon: <CheckCircle2 className="h-12 w-12 text-green-500" />,
        title: '今日已打卡成功',
        description: '继续保持，你正在变得更好！',
        color: 'text-green-600',
      }
    }
    if (isFailed) {
      return {
        icon: <XCircle className="h-12 w-12 text-red-500" />,
        title: '今日打卡失败',
        description: '没关系，明天继续加油！',
        color: 'text-red-600',
      }
    }
    return {
      icon: <Trophy className="h-12 w-12 text-blue-500" />,
      title: '今日打卡',
      description: '记录今天的挑战结果',
      color: 'text-blue-600',
    }
  }

  const statusUI = getStatusUI()

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-sm">
        <DialogHeader className="text-center">
          <div className="mx-auto mb-4">{statusUI.icon}</div>
          <DialogTitle className={cn('text-xl', statusUI.color)}>
            {statusUI.title}
          </DialogTitle>
          <DialogDescription>
            {challengeTitle}
            <br />
            第 {day} 天 · {formatChallengeDate(date)}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {/* 备注输入 */}
          {(isPending || isSuccess || isFailed) && (
            <div className="space-y-2">
              <label className="text-sm font-medium">
                备注 <span className="text-muted-foreground">(可选)</span>
              </label>
              <Textarea
                placeholder="记录一下今天的感受..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={isLoading}
                className="resize-none"
                rows={3}
              />
            </div>
          )}

          {/* 状态显示 */}
          {!isPending && (
            <div className={cn(
              'mt-4 rounded-lg p-3 text-center text-sm',
              isSuccess && 'bg-green-50 text-green-700',
              isFailed && 'bg-red-50 text-red-700'
            )}>
              {isSuccess ? '✨ 恭喜你完成了今天的挑战！' : '💪 明天继续加油，不要轻易放弃！'}
            </div>
          )}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          {isPending ? (
            <>
              {/* 待打卡状态：显示成功/失败按钮 */}
              <Button
                onClick={handleSuccess}
                disabled={isLoading}
                className="w-full gap-2 bg-green-600 hover:bg-green-700"
              >
                <CheckCircle2 className="h-4 w-4" />
                {isLoading ? '处理中...' : '打卡成功'}
              </Button>
              <Button
                onClick={handleFail}
                disabled={isLoading}
                variant="outline"
                className="w-full gap-2 border-red-300 text-red-600 hover:bg-red-50"
              >
                <XCircle className="h-4 w-4" />
                打卡失败
              </Button>
            </>
          ) : (
            <>
              {/* 已打卡状态：显示重置按钮 */}
              <Button
                onClick={handleReset}
                disabled={isLoading}
                variant="outline"
                className="w-full gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                {isLoading ? '处理中...' : '重置为未打卡'}
              </Button>
              <Button onClick={onClose} variant="ghost" className="w-full">
                关闭
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default CheckInDialog
