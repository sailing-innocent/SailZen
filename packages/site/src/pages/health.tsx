import React from 'react'
import { type WeightCreateProps } from '@lib/data'
import { type HealthState, useHealthStore } from '@lib/store/health'

import PageLayout from '@components/page_layout'
import WeightChart from '@components/weight_chart'
import DatePicker from '@components/date_picker'

import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'

type DateSpanChoice = '7d' | '30d' | '90d' | '1y' | 'all'

interface DateSpanOption {
  value: DateSpanChoice
  label: string
  getDate: () => Date
}
const now = new Date()
const dateSpanSelectOptions: DateSpanOption[] = [
  { value: '7d', label: 'Last 7 Days', getDate: () => new Date(new Date().setDate(now.getDate() - 7)) },
  { value: '30d', label: 'Last 30 Days', getDate: () => new Date(new Date().setDate(now.getDate() - 30)) },
  { value: '90d', label: 'Last 90 Days', getDate: () => new Date(new Date().setDate(now.getDate() - 90)) },
  { value: '1y', label: 'Last 1 Year', getDate: () => new Date(new Date().setFullYear(now.getFullYear() - 1)) },
  { value: 'all', label: 'All Time', getDate: () => new Date(0) },
]

const HealthPage = () => {
  const fetchWeights = useHealthStore((state: HealthState) => state.fetchWeights)
  const createWeight = useHealthStore((state: HealthState) => state.createWeight)

  const selectItems = dateSpanSelectOptions.map((option) => (
    <SelectItem key={option.value} value={option.value}>
      {option.label}
    </SelectItem>
  ))
  const [dateSpan, setDateSpan] = React.useState<DateSpanChoice>('1y')

  const [endDate, setEndDate] = React.useState<Date>(new Date()) // Default to today
  const [startDate, setStartDate] = React.useState<Date>(new Date(new Date().setFullYear(new Date().getFullYear() - 1)))

  const [createDate, setCreateDate] = React.useState<Date>(new Date()) // Default to today
  const [createWeightValue, setCreateWeightValue] = React.useState<string>('')

  React.useEffect(() => {
    const startDateUnix = Math.floor(startDate.getTime() / 1000)
    const endDateUnix = Math.floor(endDate.getTime() / 1000)
    // console.log(`Fetching weights from ${startDateUnix} to ${endDateUnix}`)
    fetchWeights(0, 4096, startDateUnix, endDateUnix)
  }, [fetchWeights, startDate, endDate])

  // change startDate and endDate when dateSpan changes
  React.useEffect(() => {
    const now = new Date()
    let newStartDate: Date
    const option = dateSpanSelectOptions.find((option) => option.value === dateSpan)
    if (option) {
      newStartDate = option.getDate()
    } else {
      newStartDate = new Date(new Date().setFullYear(now.getFullYear() - 1))
    }
    setStartDate(newStartDate)
    setEndDate(now)
  }, [dateSpan])

  return (
    <>
      <PageLayout>
        <div>Health Page</div>
        <div className="flex gap-4">
          <DatePicker
            label="Start Date"
            placeholder={startDate.toLocaleDateString()}
            onChange={(date: Date) => {
              setStartDate(date)
            }}
          />
          <DatePicker
            label="End Date"
            placeholder={endDate.toLocaleDateString()}
            onChange={(date: Date) => {
              setEndDate(date)
            }}
          />
          <div className="flex flex-col gap-3">
            <Label htmlFor="date-span" className="px-1">
              Date Span
            </Label>
            <Select onValueChange={(value) => setDateSpan(value as '7d' | '30d' | '90d' | '1y' | 'all')}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select DateSpan" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Date Span</SelectLabel>
                  {selectItems}
                </SelectGroup>
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-3">
            <Label htmlFor="add-weight" className="px-1">
              Add Weight
            </Label>
            <Dialog>
              <DialogTrigger className="w-48">
                <Input id="add-weight" placeholder="Add Weight" />
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Weight</DialogTitle>
                  <DialogDescription>Enter your weight data below.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="weight" className="text-right">
                      Weight
                    </Label>
                    <Input
                      id="weight"
                      className="col-span-3"
                      placeholder="e.g., 70.5"
                      onChange={(e) => setCreateWeightValue(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="weight-date" className="text-right">
                      Date
                    </Label>
                    <DatePicker
                      label=""
                      placeholder="Select date"
                      onChange={(date: Date) => {
                        setCreateDate(date)
                      }}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose
                    className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                    onClick={async () => {
                      const props: WeightCreateProps = {
                        value: createWeightValue,
                        htime: Math.floor(createDate.getTime() / 1000),
                      }
                      await createWeight(props)
                      setCreateWeightValue('')
                      setCreateDate(new Date())
                    }}
                  >
                    Save
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
        <div>
          <WeightChart />
        </div>
      </PageLayout>
    </>
  )
}

export default HealthPage
