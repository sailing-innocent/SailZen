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
  // 计算开始日期是星期几 (0=周日, 1=周一, ..., 6=周六)
  // 我们使用周一作为一周的第一天，所以周一=0, 周日=6
  const getDayOfWeek = (date: Date): number => {
    const day = date.getDay() // 0=周日, 1=周一, ..., 6=周六
    return day === 0 ? 6 : day - 1 // 转换为: 周一=0, ..., 周日=6
  }

  const startDayOfWeek = getDayOfWeek(startDate)
  const totalDays = checkIns.length

  // 计算需要多少行来显示所有日期
  // 前面补白的格子数 + 总天数，除以7向上取整
  const totalCells = startDayOfWeek + totalDays
  const totalWeeks = Math.ceil(totalCells / 7)
  const totalGridCells = totalWeeks * 7

  // 构建日历网格数据
  const calendarGrid: (CheckInData | null)[] = []

  // 1. 添加前面的空白格子
  for (let i = 0; i < startDayOfWeek; i++) {
    calendarGrid.push(null)
  }

  // 2. 添加打卡数据
  calendarGrid.push(...checkIns)

  // 3. 添加后面的空白格子（补齐最后一行）
  const remainingCells = totalGridCells - calendarGrid.length
  for (let i = 0; i < remainingCells; i++) {
    calendarGrid.push(null)
  }

  // 将一维数组转换为二维数组（每周一行）
  const weeks: (CheckInData | null)[][] = []
  for (let i = 0; i < calendarGrid.length; i += 7) {
    weeks.push(calendarGrid.slice(i, i + 7))
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
            {week.map((checkIn, dayIndex) => {
              // 空白格子
              if (!checkIn) {
                return <div key={`empty-${weekIndex}-${dayIndex}`} className="p-2" />
              }

              const isToday = isTodayDay(startDate, checkIn.day)
              const style = getStatusStyle(checkIn.status, isToday)

              const dateStr = `${checkIn.date.getMonth() + 1}/${checkIn.date.getDate()}`

              return (
                <div
                  key={checkIn.day}
                  className={style.className}
                  onClick={() => handleDayClick(checkIn)}
                  title={`第${checkIn.day}天 - ${formatChallengeDate(checkIn.date)} - ${style.label}`}
                >
                  <span className="text-[10px] text-muted-foreground">{dateStr}</span>
                  <span className="text-sm font-semibold">{checkIn.day}</span>
                  {style.icon}
                </div>
              )
            })}
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
