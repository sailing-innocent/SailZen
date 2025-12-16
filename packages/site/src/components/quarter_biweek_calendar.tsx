import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Calendar } from '@components/ui/calendar'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@components/ui/select'
import { Button } from '@components/ui/button'
import { listFullBiweeksInQuarter, type DateRange, getQuarterStartEnd, isWithin, formatYMD } from '@lib/utils/qbw_date'

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 21 }).map((_, idx) => currentYear - 10 + idx)

const monthOptions = [
  { value: 1, label: '一月' },
  { value: 2, label: '二月' },
  { value: 3, label: '三月' },
  { value: 4, label: '四月' },
  { value: 5, label: '五月' },
  { value: 6, label: '六月' },
  { value: 7, label: '七月' },
  { value: 8, label: '八月' },
  { value: 9, label: '九月' },
  { value: 10, label: '十月' },
  { value: 11, label: '十一月' },
  { value: 12, label: '十二月' },
]

export default function QuarterBiweekCalendar() {
  const today = new Date()
  const [year, setYear] = React.useState<number>(today.getFullYear())
  const [month, setMonth] = React.useState<number>(today.getMonth() + 1)
  const [selectedDate, setSelectedDate] = React.useState<Date | undefined>(today)
  const [quarter, setQuarter] = React.useState<number>(Math.floor(today.getMonth() / 3) + 1)
  const biweeks = React.useMemo(() => listFullBiweeksInQuarter(year, quarter), [year, quarter])
  const [biweekIndex, setBiweekIndex] = React.useState<number | undefined>(biweeks.length ? 1 : undefined)

  React.useEffect(() => {
    // Reset biweek selection when year/quarter changes
    if (biweeks.length === 0) {
      setBiweekIndex(undefined)
    } else if (!biweekIndex || biweekIndex > biweeks.length) {
      setBiweekIndex(1)
    }
  }, [year, quarter, biweeks.length])

  const biweekRange: DateRange | undefined = React.useMemo(() => {
    if (!biweekIndex) return undefined
    const bw = biweeks[biweekIndex - 1]
    if (!bw) return undefined
    return { from: bw.start, to: bw.end }
  }, [biweekIndex, biweeks])

  const calendarMonthAnchor = React.useMemo(() => {
    const { start } = getQuarterStartEnd(year, quarter)
    return new Date(start.getFullYear(), start.getMonth(), 1)
  }, [year, quarter])

  const modifiers = React.useMemo(() => {
    const rec: Record<string, (date: Date) => boolean> = {}
    biweeks.forEach((bw, idx) => {
      const key = `bw${idx + 1}`
      rec[key] = (date: Date) => isWithin(date, bw.start, bw.end)
    })
    if (biweekIndex) {
      const bw = biweeks[biweekIndex - 1]
      if (bw) {
        rec['bwFocus'] = (date: Date) => isWithin(date, bw.start, bw.end)
      }
    }
    return rec
  }, [biweeks, biweekIndex])

  const colorClasses = React.useMemo(
    () => [
      'bg-red-200/30',
      'bg-orange-200/30',
      'bg-amber-200/30',
      'bg-lime-200/30',
      'bg-emerald-200/30',
      'bg-teal-200/30',
      'bg-cyan-200/30',
      'bg-sky-200/30',
      'bg-blue-200/30',
      'bg-indigo-200/30',
      'bg-violet-200/30',
      'bg-fuchsia-200/30',
      'bg-pink-200/30',
      'bg-rose-200/30',
    ],
    []
  )

  const modifiersClassNames = React.useMemo(() => {
    const rec: Record<string, string> = {}
    biweeks.forEach((_, idx) => {
      const key = `bw${idx + 1}`
      const color = colorClasses[idx % colorClasses.length]
      rec[key] = `${color}`
    })
    rec['bwFocus'] = 'ring-2 ring-primary ring-offset-2 ring-offset-background'
    return rec
  }, [biweeks, colorClasses])

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>季度与双周日历</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <Select value={String(year)} onValueChange={(v) => setYear(parseInt(v))}>
            <SelectTrigger>
              <SelectValue placeholder="选择年份" />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((y) => (
                <SelectItem key={y} value={String(y)}>{y} 年</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={String(month)}
            onValueChange={(v) => {
              const m = parseInt(v)
              setMonth(m)
              const q = Math.floor((m - 1) / 3) + 1
              setQuarter(q)
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择月份" />
            </SelectTrigger>
            <SelectContent>
              {monthOptions.map((m) => (
                <SelectItem key={m.value} value={String(m.value)}>{m.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={String(quarter)} onValueChange={(v) => setQuarter(parseInt(v))}>
            <SelectTrigger>
              <SelectValue placeholder="选择季度" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">第 1 季度</SelectItem>
              <SelectItem value="2">第 2 季度</SelectItem>
              <SelectItem value="3">第 3 季度</SelectItem>
              <SelectItem value="4">第 4 季度</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={biweekIndex ? String(biweekIndex) : undefined}
            onValueChange={(v) => setBiweekIndex(parseInt(v))}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择季度内完整双周" />
            </SelectTrigger>
            <SelectContent>
              {biweeks.map((bw, idx) => (
                <SelectItem key={`${year}-${quarter}-${idx}`} value={String(idx + 1)}>
                  双周 {idx + 1}（{formatYMD(bw.start)} ~ {formatYMD(bw.end)}）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" onClick={() => {
            const now = new Date()
            setYear(now.getFullYear())
            setMonth(now.getMonth() + 1)
            setSelectedDate(now)
            setQuarter(Math.floor(now.getMonth() / 3) + 1)
          }}>今天</Button>
        </div>

        <div className="overflow-x-auto">
          <Calendar
            key={`${year}-${quarter}-single`}
            month={calendarMonthAnchor}
            numberOfMonths={3}
            mode="single"
            selected={selectedDate}
            onSelect={(d: Date | undefined) => {
              setSelectedDate(d)
              if (d) {
                setYear(d.getFullYear())
                setMonth(d.getMonth() + 1)
                setQuarter(Math.floor(d.getMonth() / 3) + 1)
              }
            }}
            showOutsideDays
            captionLayout="label"
            modifiers={modifiers}
            modifiersClassNames={modifiersClassNames}
          />
        </div>

        <div className="text-sm text-muted-foreground mt-3">
          {!biweekRange && selectedDate && (
            <span>已选择日期：{formatYMD(selectedDate)}</span>
          )}
          {biweekRange && (
            <span>
              已选择双周：{formatYMD(biweekRange.from as Date)} ~ {formatYMD(biweekRange.to as Date)}（季度内完整双周）
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}


