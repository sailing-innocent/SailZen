import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  type WeightCreateProps,
  type WeightData,
  type ExerciseCreateProps,
  type ExerciseData,
  type WeightAnalysisResult,
  type WeightPlanCreateProps,
  type WeightPlanData,
  type WeightPlanProgress,
  type DailyPrediction,
  type WeightRecordWithStatus,
} from '@lib/data/health'

import {
  api_get_weights,
  api_create_weight,
  api_get_exercises,
  api_create_exercise,
  api_delete_exercise,
  api_analyze_weight_trend,
  api_create_weight_plan,
  api_get_weight_plan,
  api_get_weight_plan_progress,
  api_get_weights_with_status,
} from '@lib/api/health'

export interface HealthState {
  // Weight data
  weights: WeightData[]
  isLoading: boolean
  // Current date range for refreshes
  currentStartTime: number | null
  currentEndTime: number | null
  setCurrentDateRange: (start: number | null, end: number | null) => void
  fetchWeights: (skip: number, limit: number, start: number, end: number) => Promise<void>
  createWeight: (weight: WeightCreateProps) => Promise<void>

  // Weight analysis
  analysisResult: WeightAnalysisResult | null
  fetchWeightAnalysis: (start?: number, end?: number, modelType?: string) => Promise<void>

  // Weight plan
  weightPlan: WeightPlanData | null
  planProgress: WeightPlanProgress | null
  dailyPredictions: DailyPrediction[]
  controlRate: number
  isOnTrack: boolean
  fetchWeightPlan: () => Promise<void>
  createWeightPlan: (plan: WeightPlanCreateProps) => Promise<void>
  fetchPlanProgress: () => Promise<void>

  // Weight records with status (compared to plan)
  weightsWithStatus: WeightRecordWithStatus[]
  fetchWeightsWithStatus: (start?: number, end?: number) => Promise<void>

  // Exercise data
  exercises: ExerciseData[]
  fetchExercises: (skip: number, limit: number, start: number, end: number) => Promise<void>
  createExercise: (exercise: ExerciseCreateProps) => void
  deleteExercise: (id: number) => Promise<void>

  // Helper: Check if a weight is over the expected value
  isWeightOverExpected: (weightValue: number, timestamp: number) => boolean
}

export const useHealthStore: UseBoundStore<StoreApi<HealthState>> = create<HealthState>((set, get) => ({
  // Weight state
  weights: [],
  isLoading: false,
  currentStartTime: null,
  currentEndTime: null,
  setCurrentDateRange: (start: number | null, end: number | null) => {
    set({ currentStartTime: start, currentEndTime: end })
  },
  fetchWeights: async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1) => {
    set({ isLoading: true })
    try {
      const weights = await api_get_weights(skip, limit, start, end)
      // Store the date range for later refreshes
      set({ 
        weights: weights, 
        isLoading: false,
        currentStartTime: start > 0 ? start : null,
        currentEndTime: end > 0 ? end : null,
      })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  createWeight: async (weight: WeightCreateProps) => {
    const new_weight = await api_create_weight(weight)
    set(
      (state: HealthState): HealthState => ({
        ...state,
        weights: [...state.weights, new_weight],
      })
    )
    // Refresh plan progress and weights with status using current date range
    await get().fetchPlanProgress()
    const { currentStartTime, currentEndTime } = get()
    await get().fetchWeightsWithStatus(
      currentStartTime || undefined,
      currentEndTime || undefined
    )
  },

  // Weight analysis state
  analysisResult: null,
  fetchWeightAnalysis: async (start?: number, end?: number, modelType: string = 'linear') => {
    set({ isLoading: true })
    try {
      const result = await api_analyze_weight_trend(start, end, modelType)
      set({ analysisResult: result, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  // Weight plan state
  weightPlan: null,
  planProgress: null,
  dailyPredictions: [],
  controlRate: 0,
  isOnTrack: true,
  fetchWeightPlan: async () => {
    try {
      const plan = await api_get_weight_plan()
      set({ weightPlan: plan || null })
    } catch (error) {
      console.error('Failed to fetch weight plan:', error)
      set({ weightPlan: null })
    }
  },
  createWeightPlan: async (plan: WeightPlanCreateProps) => {
    const new_plan = await api_create_weight_plan(plan)
    set({ weightPlan: new_plan })
    // Fetch progress after creating plan
    await get().fetchPlanProgress()
  },
  fetchPlanProgress: async () => {
    try {
      const progress = await api_get_weight_plan_progress()
      if (progress && progress.plan && progress.plan.id !== -1) {
        set({
          planProgress: progress,
          dailyPredictions: progress.daily_predictions || [],
          controlRate: progress.control_rate || 0,
          isOnTrack: progress.is_on_track ?? true,
        })
      } else {
        // Reset plan-related state when no valid plan
        set({
          planProgress: null,
          dailyPredictions: [],
          controlRate: 0,
          isOnTrack: true,
        })
      }
    } catch (error) {
      console.error('Failed to fetch plan progress:', error)
      set({
        planProgress: null,
        dailyPredictions: [],
        controlRate: 0,
        isOnTrack: true,
      })
    }
  },

  // Weight records with status
  weightsWithStatus: [],
  fetchWeightsWithStatus: async (start?: number, end?: number) => {
    set({ isLoading: true })
    try {
      // Don't pass undefined values, let the API use defaults
      const result = await api_get_weights_with_status(
        start && start > 0 ? start : undefined,
        end && end > 0 ? end : undefined
      )
      set({ weightsWithStatus: result, isLoading: false })
    } catch (error) {
      console.error('Failed to fetch weights with status:', error)
      set({ weightsWithStatus: [], isLoading: false })
    }
  },

  isWeightOverExpected: (weightValue: number, timestamp: number): boolean => {
    const { dailyPredictions } = get()
    if (!dailyPredictions || dailyPredictions.length === 0) return false

    // Find the expected weight for this timestamp
    const day = dailyPredictions.find((d) => Math.abs(d.htime - timestamp) < 43200) // within 12 hours
    if (!day) return false

    // If actual weight is higher than expected, it's over (for weight loss scenario)
    // This assumes the goal is to lose weight
    return weightValue > day.expected_weight + 0.5 // 0.5kg tolerance
  },

  // Exercise state
  exercises: [],
  fetchExercises: async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1) => {
    set({ isLoading: true })
    try {
      const exercises = await api_get_exercises(skip, limit, start, end)
      set({ exercises: exercises, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },
  createExercise: async (exercise: ExerciseCreateProps) => {
    const new_exercise = await api_create_exercise(exercise)
    set(
      (state: HealthState): HealthState => ({
        ...state,
        exercises: [new_exercise, ...state.exercises],
      })
    )
  },
  deleteExercise: async (id: number) => {
    await api_delete_exercise(id)
    set(
      (state: HealthState): HealthState => ({
        ...state,
        exercises: state.exercises.filter((e) => e.id !== id),
      })
    )
  },
}))

export default useHealthStore
