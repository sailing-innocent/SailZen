import React, { useEffect, useMemo, useState } from 'react'
import DatePicker from '@components/date_picker'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { parseDdl } from '@lib/data/affair'

const pad2 = (n: number): string => String(n).padStart(2, '0')

const toLocalDateTimeParts = (value?: string | number | Date | null) => {
  const date = parseDdl(value)
  if (!date) return { date: undefined as Date | undefined, time: '' }
  return {
    date,
    time: `${pad2(date.getHours())}:${pad2(date.getMinutes())}`,
  }
}

export interface DateTimePickerProps {
  label?: string
  value?: string | number | Date | null
  onChange: (value: string | undefined) => void
}

export const DateTimePicker: React.FC<DateTimePickerProps> = ({ label, value, onChange }) => {
  const { date, time } = useMemo(() => toLocalDateTimeParts(value), [value])
  const [timeValue, setTimeValue] = useState(time)

  useEffect(() => {
    setTimeValue(time)
  }, [time])

  const handleDateChange = (d?: Date) => {
    if (!d) {
      onChange(undefined)
      return
    }
    const [hours = 0, minutes = 0] = (timeValue || '00:00').split(':').map(Number)
    const next = new Date(d.getFullYear(), d.getMonth(), d.getDate(), hours, minutes)
    onChange(next.toISOString())
  }

  const handleTimeChange = (t: string) => {
    setTimeValue(t)
    if (!date) return
    const [hours = 0, minutes = 0] = t.split(':').map(Number)
    const next = new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes)
    onChange(next.toISOString())
  }

  return (
    <div className="space-y-2">
      {label && <Label>{label}</Label>}
      <div className="flex items-center gap-2">
        <DatePicker label="" placeholder="选择日期" value={date} onChange={handleDateChange} />
      </div>
    </div>
  )
}
