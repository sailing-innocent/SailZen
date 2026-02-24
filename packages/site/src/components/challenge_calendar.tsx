import React from 'react'
import { type CheckInData, CheckInStatus, formatChallengeDate, isTodayDay } from '@lib/data/challenge'
import { CheckCircle2, XCircle, Circle, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChallengeCalendarProps {
  checkIns: CheckInData[]
  startDate: Date
  onCheckInClick?: (day: number) => void
  onDayClick?: (checkIn: CheckInData) => void
}

const ChallengeCalendar: React.FC<ChallengeCalendarProps> = ({
  checkIns,
  startDate,
  onCheckInClick,
  onDayClick,
}) => {
  // 将打卡记录按周分组（每行7天）
  const weeks: CheckInData[][] = []
  for (let i = 0; i < checkIns.length; i += 7) {
    weeks.push(checkIns.slice(i, i + 7))
  }

  // 获取状态对应的样式和图标
  const getStatusStyle = (status: CheckInStatusValue, isToday: boolean) => {
    const baseClasses = 'flex flex-col items-center justify-center p-2 rounded-lg cursor-pointer transition-all hover:scale-105'
    
    switch (status) {
      case CheckInStatus.SUCCESS:
        return {
          className: cn(baseClasses, 'bg-green-100 text-green-700 border-2 border-green-300'),
          icon: <CheckCircle2 className="h-5 w-5" />,
          label: '成功',
        }
      case CheckInStatus.FAILED:
        return {
          className: cn(baseClasses, 'bg-red-100 text-red-700 border-2 border-red-300'),
          icon: <XCircle className="h-5 w-5" />,
          label: '失败',
        }
      case CheckInStatus.FUTURE:
        return {
          className: cn(baseClasses, 'bg-gray-50 text-gray-400 border-2 border-gray-200 cursor-not-allowed'),
          icon: <Clock className="h-5 w-5" />,
          label: '未来',
        }
      case CheckInStatus.PENDING:
      default:
        if (isToday) {
          return {
            className: cn(baseClasses, 'bg-blue-100 text-blue-700 border-2 border-blue-400 ring-2 ring-blue-200 animate-pulse'),
            icon: <Circle className="h-5 w-5" />,
            label: '今天',
          }
        }
        return {
          className: cn(baseClasses, 'bg-yellow-50 text-yellow-600 border-2 border-yellow-300 border-dashed'),
          icon: <Circle className="h-5 w-5" />,
          label: '待打卡',
        }
    }
  }

  const handleDayClick = (checkIn: CheckInData) => {
    if (checkIn.status === CheckInStatus.FUTURE) {
      return // 未来日期不可点击
    }
    
    const isToday = isTodayDay(startDate, checkIn.day)
    
    if (isToday && onCheckInClick) {
      onCheckInClick(checkIn.day)
    } else if (onDayClick) {
      onDayClick(checkIn)
    }
  }

  return (
    <div className="space-y-4">
      {/* 星期标题 */}
      <div className="grid grid-cols-7 gap-2 text-center">
        {['一', '二', '三', '四', '五', '六', '日'].map((day, index) => (
          <div key={index} className="text-sm font-medium text-muted-foreground py-1">
            {day}
          </div>
        ))}
      </div>

      {/* 日历网格 */}
      <div className="space-y-2">
        {weeks.map((week, weekIndex) => (
          <div key={weekIndex} className="grid grid-cols-7 gap-2">
            {week.map((checkIn) => {
              const isToday = isTodayDay(startDate, checkIn.day)
              const style = getStatusStyle(checkIn.status, isToday)
              
              return (
                <div
                  key={checkIn.day}
                  className={style.className}
                  onClick={() => handleDayClick(checkIn)}
                  title={`第${checkIn.day}天 - ${formatChallengeDate(checkIn.date)} - ${style.label}`}
                >
                  <span className="text-xs font-medium">{checkIn.day}</span>
                  {style.icon}
                </div>
              )
            })}
            {/* 补全最后一周的空白 */}
            {week.length < 7 && 
              Array.from({ length: 7 - week.length }).map((_, idx) => (
                <div key={`empty-${idx}`} className="p-2" />
              ))
            }
          </div>
        ))}
      </div>

      {/* 图例 */}
      <div className="flex flex-wrap justify-center gap-4 pt-2 text-xs text-muted-foreground">
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-green-100 border border-green-300 flex items-center justify-center">
            <CheckCircle2 className="h-3 w-3 text-green-700" />
          </div>
          <span>成功</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-red-100 border border-red-300 flex items-center justify-center">
            <XCircle className="h-3 w-3 text-red-700" />
          </div>
          <span>失败</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-yellow-50 border border-yellow-300 border-dashed" />
          <span>待打卡</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-blue-100 border border-blue-400 ring-1 ring-blue-200" />
          <span>今天</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded bg-gray-50 border border-gray-200" />
          <span>未来</span>
        </div>
      </div>
    </div>
  )
}

export default ChallengeCalendar
