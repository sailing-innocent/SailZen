import React from 'react'
import { type WeightCreateProps, type ExerciseCreateProps } from '@lib/data'
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
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useIsMobile } from '@/hooks/use-mobile'
import { Trash2 } from 'lucide-react'

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
  const exercises = useHealthStore((state: HealthState) => state.exercises)
  const fetchExercises = useHealthStore((state: HealthState) => state.fetchExercises)
  const createExercise = useHealthStore((state: HealthState) => state.createExercise)
  const deleteExercise = useHealthStore((state: HealthState) => state.deleteExercise)
  const isMobile = useIsMobile()

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

  // Exercise form state
  const [exerciseDate, setExerciseDate] = React.useState<Date>(new Date())
  const [exerciseDescription, setExerciseDescription] = React.useState<string>('')
  const [isExerciseDialogOpen, setIsExerciseDialogOpen] = React.useState<boolean>(false)

  React.useEffect(() => {
    const startDateUnix = Math.floor(startDate.getTime() / 1000)
    const endDateUnix = Math.floor(endDate.getTime() / 1000)
    // console.log(`Fetching weights from ${startDateUnix} to ${endDateUnix}`)
    fetchWeights(0, 4096, startDateUnix, endDateUnix)
  }, [fetchWeights, startDate, endDate])

  // Fetch exercises on mount and when date range changes
  React.useEffect(() => {
    const startDateUnix = Math.floor(startDate.getTime() / 1000)
    const endDateUnix = Math.floor(endDate.getTime() / 1000)
    fetchExercises(0, 100, startDateUnix, endDateUnix)
  }, [fetchExercises, startDate, endDate])

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

  const handleCreateExercise = async () => {
    const props: ExerciseCreateProps = {
      htime: Math.floor(exerciseDate.getTime() / 1000),
      description: exerciseDescription,
    }
    await createExercise(props)
    setExerciseDescription('')
    setExerciseDate(new Date())
    setIsExerciseDialogOpen(false)
  }

  const handleDeleteExercise = async (id: number) => {
    await deleteExercise(id)
  }

  // Format timestamp to date string
  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <>
      <PageLayout>
        <div className={isMobile ? 'text-lg px-2' : 'text-xl'}>体重管理</div>
        {/* 响应式控件布局：移动端垂直堆叠，桌面端横向排列 */}
        <div className={`flex gap-3 ${isMobile ? 'flex-col px-2' : 'flex-row flex-wrap'}`}>
          {/* 日期选择器组 */}
          <div className={`flex gap-3 ${isMobile ? 'flex-col' : 'flex-row'}`}>
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
          </div>
          {/* 时间范围选择 */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="date-span" className="px-1 text-sm">
              Date Span
            </Label>
            <Select onValueChange={(value) => setDateSpan(value as '7d' | '30d' | '90d' | '1y' | 'all')}>
              <SelectTrigger className={isMobile ? 'w-full' : 'w-[180px]'}>
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
          {/* 添加体重按钮 */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="add-weight" className="px-1 text-sm">
              Add Weight
            </Label>
            <Dialog>
              <DialogTrigger className={isMobile ? 'w-full' : 'w-48'}>
                <Input id="add-weight" placeholder="Add Weight" />
              </DialogTrigger>
              <DialogContent className={isMobile ? 'w-[95vw] max-w-[95vw]' : ''}>
                <DialogHeader>
                  <DialogTitle>Add Weight</DialogTitle>
                  <DialogDescription>Enter your weight data below.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="weight" className={isMobile ? '' : 'text-right'}>
                      Weight
                    </Label>
                    <Input
                      id="weight"
                      className={isMobile ? 'w-full' : 'col-span-3'}
                      placeholder="e.g., 70.5"
                      onChange={(e) => setCreateWeightValue(e.target.value)}
                    />
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="weight-date" className={isMobile ? '' : 'text-right'}>
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
        <div className={isMobile ? 'px-2' : ''}>
          <WeightChart />
        </div>

        {/* 运动记录部分 */}
        <div className={`${isMobile ? 'text-lg px-2 mt-8' : 'text-xl mt-10'} border-t pt-6`}>运动记录</div>
        <div className={`flex gap-3 ${isMobile ? 'flex-col px-2' : 'flex-row flex-wrap'}`}>
          {/* 添加运动记录按钮 */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="add-exercise" className="px-1 text-sm">
              Add Exercise
            </Label>
            <Dialog open={isExerciseDialogOpen} onOpenChange={setIsExerciseDialogOpen}>
              <DialogTrigger className={isMobile ? 'w-full' : 'w-48'}>
                <Input id="add-exercise" placeholder="Add Exercise Record" readOnly />
              </DialogTrigger>
              <DialogContent className={isMobile ? 'w-[95vw] max-w-[95vw]' : ''}>
                <DialogHeader>
                  <DialogTitle>Add Exercise Record</DialogTitle>
                  <DialogDescription>Record your exercise activity below.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="exercise-date" className={isMobile ? '' : 'text-right'}>
                      Date & Time
                    </Label>
                    <DatePicker
                      label=""
                      placeholder="Select date"
                      onChange={(date: Date) => {
                        setExerciseDate(date)
                      }}
                    />
                  </div>
                  <div className={`grid items-start gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="exercise-description" className={isMobile ? '' : 'text-right pt-2'}>
                      Description
                    </Label>
                    <Textarea
                      id="exercise-description"
                      className={isMobile ? 'w-full' : 'col-span-3'}
                      placeholder="e.g., Ran 5km in the park, felt good..."
                      value={exerciseDescription}
                      onChange={(e) => setExerciseDescription(e.target.value)}
                      rows={4}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <DialogClose
                    className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-gray-400"
                    onClick={handleCreateExercise}
                    disabled={!exerciseDescription.trim()}
                  >
                    Save
                  </DialogClose>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* 运动记录列表 */}
        <div className={`${isMobile ? 'px-2' : ''} mt-4`}>
          <h3 className={`font-semibold mb-3 ${isMobile ? 'text-base' : 'text-lg'}`}>Recent Exercises</h3>
          {exercises.length === 0 ? (
            <div className="text-gray-500 text-sm">No exercise records yet.</div>
          ) : (
            <div className="space-y-2">
              {exercises.map((exercise) => (
                <div
                  key={exercise.id}
                  className="border rounded-lg p-3 bg-white dark:bg-gray-800 flex justify-between items-start gap-2"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-500 mb-1">{formatDate(exercise.htime)}</div>
                    <div className="text-sm break-words">{exercise.description}</div>
                  </div>
                  <button
                    onClick={() => handleDeleteExercise(exercise.id)}
                    className="text-red-500 hover:text-red-700 p-1 flex-shrink-0"
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </PageLayout>
    </>
  )
}

export default HealthPage
