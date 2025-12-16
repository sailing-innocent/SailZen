import { create, type StoreApi, type UseBoundStore } from 'zustand'
import { type WeightCreateProps, type WeightData } from '@lib/data/health'

import { api_get_weights, api_create_weight } from '@lib/api/health'

export interface HealthState {
  weights: WeightData[]
  isLoading: boolean
  fetchWeights: (skip: number, limit: number, start: number, end: number) => Promise<void>
  createWeight: (weight: WeightCreateProps) => void
}

export const useHealthStore: UseBoundStore<StoreApi<HealthState>> = create<HealthState>((set) => ({
  weights: [],
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
}))

export default useHealthStore
