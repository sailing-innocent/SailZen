import { create, type StoreApi, type UseBoundStore } from 'zustand'
import { type WeightCreateProps, type WeightData, type ExerciseCreateProps, type ExerciseData } from '@lib/data/health'

import { api_get_weights, api_create_weight, api_get_exercises, api_create_exercise, api_delete_exercise } from '@lib/api/health'

export interface HealthState {
  weights: WeightData[]
  exercises: ExerciseData[]
  isLoading: boolean
  fetchWeights: (skip: number, limit: number, start: number, end: number) => Promise<void>
  createWeight: (weight: WeightCreateProps) => void
  fetchExercises: (skip: number, limit: number, start: number, end: number) => Promise<void>
  createExercise: (exercise: ExerciseCreateProps) => Promise<void>
  deleteExercise: (id: number) => Promise<void>
}

export const useHealthStore: UseBoundStore<StoreApi<HealthState>> = create<HealthState>((set) => ({
  weights: [],
  exercises: [],
  isLoading: false,
  fetchWeights: async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1) => {
    set({ isLoading: true })
    try {
      const weights = await api_get_weights(skip, limit, start, end)
      set({ weights: weights, isLoading: false })
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
  },
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
