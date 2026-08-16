import React from 'react'
import { type WeightCreateProps, type ExerciseCreateProps, type WeightPlanCreateProps, type WeightPlanCurveType } from '@lib/data'
import { type HealthState, useHealthStore } from '@lib/store/health'

import PageLayout from '@components/page_layout'
import WeightChart from '@components/health/weight_chart'
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
import { Trash2, Target, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { Switch } from '@/components/ui/switch'

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
  const weightPlan = useHealthStore((state: HealthState) => state.weightPlan)
  const analysisResult = useHealthStore((state: HealthState) => state.analysisResult)
  const controlRate = useHealthStore((state: HealthState) => state.controlRate)
  const isOnTrack = useHealthStore((state: HealthState) => state.isOnTrack)
  const fetchWeightPlan = useHealthStore((state: HealthState) => state.fetchWeightPlan)
  const createWeightPlan = useHealthStore((state: HealthState) => state.createWeightPlan)
  const updateWeightPlan = useHealthStore((state: HealthState) => state.updateWeightPlan)
  const deleteWeightPlan = useHealthStore((state: HealthState) => state.deleteWeightPlan)
  const planCheckinStatus = useHealthStore((state: HealthState) => state.planCheckinStatus)
  const weightSaveMessage = useHealthStore((state: HealthState) => state.weightSaveMessage)
  const fetchPlanCheckinStatus = useHealthStore((state: HealthState) => state.fetchPlanCheckinStatus)
  const fetchWeightsWithStatus = useHealthStore((state: HealthState) => state.fetchWeightsWithStatus)
  const isMobile = useIsMobile()

  const selectItems = dateSpanSelectOptions.map((option) => (
    <SelectItem key={option.value} value={option.value}>
      {option.label}
    </SelectItem>
  ))
  const [dateSpan, setDateSpan] = React.useState<DateSpanChoice>('90d')

  const [endDate, setEndDate] = React.useState<Date>(new Date()) // Default to today
  const [startDate, setStartDate] = React.useState<Date>(new Date(new Date().setDate(new Date().getDate() - 90)))

  const [createDate, setCreateDate] = React.useState<Date>(new Date()) // Default to today
  const [createWeightValue, setCreateWeightValue] = React.useState<string>('')

  // Exercise form state
  const [exerciseDate, setExerciseDate] = React.useState<Date>(new Date())
  const [exerciseDescription, setExerciseDescription] = React.useState<string>('')
  const [isExerciseDialogOpen, setIsExerciseDialogOpen] = React.useState<boolean>(false)

  // Weight plan form state
  const [planTargetWeight, setPlanTargetWeight] = React.useState<string>('')
  const [planInitialWeight, setPlanInitialWeight] = React.useState<string>('')
  const [planInitialWeightAuto, setPlanInitialWeightAuto] = React.useState<boolean>(true)
  const [planStartDate, setPlanStartDate] = React.useState<Date>(new Date()) // Can be customized
  const [planTargetDate, setPlanTargetDate] = React.useState<Date>(new Date(new Date().setMonth(new Date().getMonth() + 3)))
  const [planCurveType, setPlanCurveType] = React.useState<WeightPlanCurveType>('linear')
  const [planNotifyEnabled, setPlanNotifyEnabled] = React.useState<boolean>(false)
  const [planNotifyTime, setPlanNotifyTime] = React.useState<string>('08:30')
  const [planFeedbackEnabled, setPlanFeedbackEnabled] = React.useState<boolean>(false)
  const [planDescription, setPlanDescription] = React.useState<string>('')
  const [isPlanDialogOpen, setIsPlanDialogOpen] = React.useState<boolean>(false)

  // Fetch plan on mount and when plan changes
  React.useEffect(() => {
    fetchWeightPlan().then(() => {
      fetchPlanCheckinStatus()
    })
  }, [fetchWeightPlan, fetchPlanCheckinStatus])

  React.useEffect(() => {
    const startDateUnix = Math.floor(startDate.getTime() / 1000)
    const endDateUnix = Math.floor(endDate.getTime() / 1000)
    fetchWeights(0, 4096, startDateUnix, endDateUnix)
    // Also fetch weights with status for the chart
    fetchWeightsWithStatus(startDateUnix, endDateUnix)
    // Fetch plan expected points aligned to current date range
    fetchPlanExpected(startDateUnix, endDateUnix)
  }, [fetchWeights, fetchWeightsWithStatus, fetchPlanExpected, startDate, endDate])

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

  // Fetch plan checkin status when plan changes
  React.useEffect(() => {
    if (weightPlan) {
      fetchPlanCheckinStatus()
    }
  }, [weightPlan, fetchPlanCheckinStatus])

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

  // Populate plan dialog when opening or when existing plan changes
  React.useEffect(() => {
    if (weightPlan) {
      setPlanTargetWeight(String(weightPlan.target_weight))
      setPlanInitialWeight(weightPlan.initial_weight ? String(weightPlan.initial_weight) : '')
      setPlanInitialWeightAuto(weightPlan.initial_weight === null || weightPlan.initial_weight === undefined)
      setPlanStartDate(new Date(weightPlan.start_time * 1000))
      setPlanTargetDate(new Date(weightPlan.target_time * 1000))
      setPlanCurveType(weightPlan.curve_type || 'linear')
      setPlanNotifyEnabled(weightPlan.notify_enabled || false)
      setPlanNotifyTime(weightPlan.notify_time || '08:30')
      setPlanFeedbackEnabled(weightPlan.feedback_enabled || false)
      setPlanDescription(weightPlan.description || '')
    } else {
      setPlanTargetWeight('')
      setPlanInitialWeight('')
      setPlanInitialWeightAuto(true)
      setPlanStartDate(new Date())
      setPlanTargetDate(new Date(new Date().setMonth(new Date().getMonth() + 3)))
      setPlanCurveType('linear')
      setPlanNotifyEnabled(false)
      setPlanNotifyTime('08:30')
      setPlanFeedbackEnabled(false)
      setPlanDescription('')
    }
  }, [weightPlan, isPlanDialogOpen])
  const handleCreatePlan = async () => {
    const props: WeightPlanCreateProps = {
      target_weight: parseFloat(planTargetWeight),
      initial_weight: planInitialWeightAuto ? null : parseFloat(planInitialWeight),
      start_time: Math.floor(planStartDate.getTime() / 1000),
      target_time: Math.floor(planTargetDate.getTime() / 1000),
      description: planDescription,
      curve_type: planCurveType,
      notify_enabled: planNotifyEnabled,
      notify_time: planNotifyTime,
      feedback_enabled: planFeedbackEnabled,
    }
    if (weightPlan && weightPlan.id > 0) {
      await updateWeightPlan(weightPlan.id, props)
    } else {
      await createWeightPlan(props)
    }
    setIsPlanDialogOpen(false)
  }

  const handleDeletePlan = async () => {
    if (weightPlan && weightPlan.id > 0) {
      await deleteWeightPlan(weightPlan.id)
    }
    setIsPlanDialogOpen(false)
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

  // Get trend icon
  const getTrendIcon = () => {
    if (!analysisResult) return <Minus className="h-5 w-5" />
    switch (analysisResult.current_trend) {
      case 'decreasing':
        return <TrendingDown className="h-5 w-5 text-green-500" />
      case 'increasing':
        return <TrendingUp className="h-5 w-5 text-red-500" />
      default:
        return <Minus className="h-5 w-5 text-gray-500" />
    }
  }

  return (
    <>
      <PageLayout>
        {/* 体重管理部分 */}
        <div className={isMobile ? 'text-lg px-2' : 'text-xl'}>体重管理</div>
        
        {/* 趋势和控制率概览 */}
        {analysisResult && (
          <div className={`grid gap-4 ${isMobile ? 'grid-cols-2 px-2' : 'grid-cols-4'} mb-4`}>
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
              <div className="text-xs text-gray-500">Current</div>
              <div className="text-lg font-bold">{analysisResult.current_weight.toFixed(1)} kg</div>
            </div>
            <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
              <div className="text-xs text-gray-500">Trend</div>
              <div className="flex items-center gap-1">
                {getTrendIcon()}
                <span className="text-sm font-medium capitalize">{analysisResult.current_trend}</span>
              </div>
            </div>
            <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-3">
              <div className="text-xs text-gray-500">Weekly Δ</div>
              <div className="text-lg font-bold">{(analysisResult.slope * 7).toFixed(2)} kg</div>
            </div>
            <div className={`${isOnTrack ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'} rounded-lg p-3`}>
              <div className="text-xs text-gray-500">Control</div>
              <div className="text-lg font-bold">{controlRate.toFixed(0)}%</div>
            </div>
          </div>
        )}

        {/* Rhythm 反馈 Toast */}
        {weightSaveMessage && (
          <div className={`mb-4 ${isMobile ? 'px-2' : ''}`}>
            <div className="bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 px-4 py-2 rounded-lg text-sm font-medium">
              {weightSaveMessage}
            </div>
          </div>
        )}

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
          {/* 设置体重计划按钮 */}
          <div className="flex flex-col gap-2">
            <Label htmlFor="weight-plan" className="px-1 text-sm">
              Weight Plan
            </Label>
            <Dialog open={isPlanDialogOpen} onOpenChange={setIsPlanDialogOpen}>
              <DialogTrigger className={isMobile ? 'w-full' : 'w-48'}>
                <div className="flex items-center gap-2 px-3 py-2 border rounded-md bg-white dark:bg-gray-800 cursor-pointer hover:bg-gray-50">
                  <Target className="h-4 w-4" />
                  <span className="text-sm">{weightPlan ? 'Update Plan' : 'Set Plan'}</span>
                </div>
              </DialogTrigger>
              <DialogContent className={isMobile ? 'w-[95vw] max-w-[95vw]' : ''}>
                <DialogHeader>
                  <DialogTitle>{weightPlan ? 'Update Weight Plan' : 'Set Weight Plan'}</DialogTitle>
                  <DialogDescription>Configure your target weight, timeline, curve and Rhythm integration.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {weightPlan && (
                    <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-md text-sm">
                      <div className="font-medium">Current Plan:</div>
                      <div>Target: {weightPlan.target_weight} kg</div>
                      <div>By: {new Date(weightPlan.target_time * 1000).toLocaleDateString()}</div>
                    </div>
                  )}
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="target-weight" className={isMobile ? '' : 'text-right'}>
                      Target Weight (kg)
                    </Label>
                    <Input
                      id="target-weight"
                      className={isMobile ? 'w-full' : 'col-span-3'}
                      placeholder="e.g., 70"
                      value={planTargetWeight}
                      onChange={(e) => setPlanTargetWeight(e.target.value)}
                    />
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="start-date" className={isMobile ? '' : 'text-right'}>
                      Start Date
                    </Label>
                    <DatePicker
                      label=""
                      placeholder="Select start date"
                      onChange={(date: Date) => {
                        setPlanStartDate(date)
                      }}
                    />
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="target-date" className={isMobile ? '' : 'text-right'}>
                      Target Date
                    </Label>
                    <DatePicker
                      label=""
                      placeholder="Select target date"
                      onChange={(date: Date) => {
                        setPlanTargetDate(date)
                      }}
                    />
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label className={isMobile ? '' : 'text-right'}>Initial Weight</Label>
                    <div className={isMobile ? 'w-full' : 'col-span-3 flex items-center gap-4'}>
                      <div className="flex items-center gap-2">
                        <Switch
                          id="initial-weight-auto"
                          checked={planInitialWeightAuto}
                          onCheckedChange={(checked: boolean) => setPlanInitialWeightAuto(checked)}
                        />
                        <Label htmlFor="initial-weight-auto" className="text-sm font-normal">
                          Auto
                        </Label>
                      </div>
                      {!planInitialWeightAuto && (
                        <Input
                          id="initial-weight"
                          className="w-32"
                          placeholder="kg"
                          value={planInitialWeight}
                          onChange={(e) => setPlanInitialWeight(e.target.value)}
                        />
                      )}
                    </div>
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="curve-type" className={isMobile ? '' : 'text-right'}>
                      Curve Type
                    </Label>
                    <Select
                      value={planCurveType}
                      onValueChange={(value) => setPlanCurveType(value as WeightPlanCurveType)}
                    >
                      <SelectTrigger id="curve-type" className={isMobile ? 'w-full' : 'col-span-3'}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectLabel>Curve</SelectLabel>
                          <SelectItem value="linear">Linear</SelectItem>
                          <SelectItem value="polynomial">Polynomial (ease-out)</SelectItem>
                          <SelectItem value="exponential">Exponential</SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label className={isMobile ? '' : 'text-right'}>Rhythm Notify</Label>
                    <div className={isMobile ? 'w-full' : 'col-span-3 flex items-center gap-4'}>
                      <Switch
                        id="plan-notify"
                        checked={planNotifyEnabled}
                        onCheckedChange={(checked: boolean) => setPlanNotifyEnabled(checked)}
                      />
                      {planNotifyEnabled && (
                        <Input
                          id="notify-time"
                          className="w-24"
                          placeholder="HH:MM"
                          value={planNotifyTime}
                          onChange={(e) => setPlanNotifyTime(e.target.value)}
                        />
                      )}
                    </div>
                  </div>
                  <div className={`grid items-center gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label className={isMobile ? '' : 'text-right'}>Rhythm Feedback</Label>
                    <div className={isMobile ? 'w-full' : 'col-span-3 flex items-center gap-2'}>
                      <Switch
                        id="plan-feedback"
                        checked={planFeedbackEnabled}
                        onCheckedChange={(checked: boolean) => setPlanFeedbackEnabled(checked)}
                      />
                      <Label htmlFor="plan-feedback" className="text-sm font-normal">
                        Sync weight records to Rhythm checkin
                      </Label>
                    </div>
                  </div>
                  <div className={`grid items-start gap-4 ${isMobile ? 'grid-cols-1' : 'grid-cols-4'}`}>
                    <Label htmlFor="plan-description" className={isMobile ? '' : 'text-right pt-2'}>
                      Description
                    </Label>
                    <Textarea
                      id="plan-description"
                      className={isMobile ? 'w-full' : 'col-span-3'}
                      placeholder="e.g., Lose 5kg in 3 months..."
                      value={planDescription}
                      onChange={(e) => setPlanDescription(e.target.value)}
                      rows={2}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <div className="flex gap-2 justify-end">
                    {weightPlan && (
                      <DialogClose
                        className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
                        onClick={handleDeletePlan}
                      >
                        Delete
                      </DialogClose>
                    )}
                    <DialogClose
                      className="bg-amber-500 text-white px-4 py-2 rounded hover:bg-amber-600 disabled:bg-gray-400"
                      onClick={handleCreatePlan}
                      disabled={!planTargetWeight.trim() || isNaN(parseFloat(planTargetWeight))}
                    >
                      {weightPlan ? 'Update Plan' : 'Save Plan'}
                    </DialogClose>
                  </div>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>
        <div className={isMobile ? 'px-2' : ''}>
          {/* Rhythm 状态徽章 */}
          {weightPlan && weightPlan.feedback_enabled && planCheckinStatus && (
            <div className="flex gap-2 mb-3">
              <div
                className={`px-3 py-1 rounded-full text-xs font-medium ${
                  planCheckinStatus.today_done
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200'
                }`}
              >
                {planCheckinStatus.today_done ? '今日已打卡' : '今日未打卡'}
              </div>
              <div className="px-3 py-1 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200 text-xs font-medium">
                连续 {planCheckinStatus.streak} 天
              </div>
            </div>
          )}
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
