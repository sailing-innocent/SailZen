import React, { useState } from 'react'
import { ChevronDownIcon } from 'lucide-react'
import { Button } from '@components/ui/button'
import { Calendar } from '@components/ui/calendar'
import { Label } from '@components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'

export interface DatePickerProps {
  label: string
  placeholder?: string
  value?: Date
  onChange: (date: Date) => void
}

const DatePicker: React.FC<DatePickerProps> = (props: DatePickerProps) => {
  const { label, placeholder, value, onChange } = props

  const [open, setOpen] = useState(false)
  const [date, setDate] = useState<Date | undefined>(value)
  const displayDate = date ? date.toLocaleDateString() : placeholder || 'Select date'

  // Update local state when value prop changes
  React.useEffect(() => {
    setDate(value)
  }, [value])
  return (
    <div className="flex flex-col gap-3">
      <Label htmlFor="date" className="px-1">
        {label}
      </Label>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" id="date" className="w-48 justify-between font-normal">
            {displayDate}
            <ChevronDownIcon />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto overflow-hidden p-0" align="start">
          <Calendar
            mode="single"
            selected={date}
            captionLayout="dropdown"
            onSelect={(date) => {
              setDate(date)
              setOpen(false)
              onChange(date as Date)
            }}
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

export default DatePicker
