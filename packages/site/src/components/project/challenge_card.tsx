import React from 'react'
import { type ChallengeData, type ChallengeStats, ChallengeStatus, ChallengeTypeIcons, ChallengeTypeLabels } from '@lib/data/challenge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { CheckCircle2, XCircle, AlertCircle, Trophy, Calendar } from 'lucide-react'

interface ChallengeCardProps {
  challenge: ChallengeData
  stats: ChallengeStats | null
  onCheckIn: () => void
  onViewDetail: () => void
  isLoading?: boolean
}

const ChallengeCard: React.FC<ChallengeCardProps> = ({
  challenge,
  stats,
  onCheckIn,
  onViewDetail,
  isLoading = false,
}) => {
  const progress = stats ? Math.round((stats.successDays / challenge.days) * 100) : 0
  const isCompleted = challenge.status === ChallengeStatus.COMPLETED
  const isAborted = challenge.status === ChallengeStatus.ABORTED

  // 计算剩余天数
  const remainingDays = challenge.days - (stats?.currentDay || 0)
  
  // 获取状态显示
  const getStatusDisplay = () => {
    if (isCompleted) {
      return {
        icon: <Trophy className="h-4 w-4 text-yellow-500" />,
        text: '已完成',
        color: 'text-yellow-600',
      }
    }
    if (isAborted) {
      return {
        icon: <AlertCircle className="h-4 w-4 text-gray-500" />,
        text: '已中止',
        color: 'text-gray-600',
      }
    }
    if (stats?.isTodayChecked) {
      return {
        icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
        text: '今日已打卡',
        color: 'text-green-600',
      }
    }
    return {
      icon: <Calendar className="h-4 w-4 text-blue-500" />,
      text: `剩余 ${Math.max(0, remainingDays)} 天`,
      color: 'text-blue-600',
    }
  }

  const statusDisplay = getStatusDisplay()

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{ChallengeTypeIcons[challenge.type]}</span>
            <div>
              <CardTitle className="text-lg font-semibold">{challenge.title}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {ChallengeTypeLabels[challenge.type]} · {challenge.days}天挑战
              </p>
            </div>
          </div>
          <div className={`flex items-center gap-1 text-sm ${statusDisplay.color}`}>
            {statusDisplay.icon}
            <span>{statusDisplay.text}</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 进度条 */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">总进度</span>
            <span className="font-medium">{progress}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* 统计信息 */}
        {stats && (
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="rounded-lg bg-green-50 p-2">
              <div className="flex items-center justify-center gap-1 text-green-600">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-lg font-semibold">{stats.successDays}</span>
              </div>
              <p className="text-xs text-muted-foreground">成功</p>
            </div>
            <div className="rounded-lg bg-red-50 p-2">
              <div className="flex items-center justify-center gap-1 text-red-600">
                <XCircle className="h-4 w-4" />
                <span className="text-lg font-semibold">{stats.failedDays}</span>
              </div>
              <p className="text-xs text-muted-foreground">失败</p>
            </div>
            <div className="rounded-lg bg-blue-50 p-2">
              <div className="flex items-center justify-center gap-1 text-blue-600">
                <Trophy className="h-4 w-4" />
                <span className="text-lg font-semibold">{stats.successRate}%</span>
              </div>
              <p className="text-xs text-muted-foreground">成功率</p>
            </div>
          </div>
        )}

        {/* 当前进度文字 */}
        {!isCompleted && !isAborted && stats && (
          <div className="text-center text-sm text-muted-foreground">
            第 <span className="font-medium text-foreground">{stats.currentDay}</span> / {challenge.days} 天
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-2">
          {challenge.status === ChallengeStatus.ACTIVE && !stats?.isTodayChecked && (
            <Button 
              onClick={onCheckIn} 
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? '处理中...' : '今日打卡'}
            </Button>
          )}
          {challenge.status === ChallengeStatus.ACTIVE && stats?.isTodayChecked && (
            <Button 
              variant="outline" 
              onClick={onViewDetail} 
              disabled={isLoading}
              className="flex-1"
            >
              查看详情
            </Button>
          )}
          {(isCompleted || isAborted) && (
            <Button 
              variant="outline" 
              onClick={onViewDetail} 
              disabled={isLoading}
              className="flex-1"
            >
              查看回顾
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default ChallengeCard
