/**
 * @file index.ts
 * @brief The Store Interface
 * @author sailing-innocent
 * @date 2024-12-26
 */

export * from './money'
export * from './affair'
export * from './pems'
export * from './rhythm'

export { useBudgetsStore, useFinanceTagsStore } from './money'
export { useRhythmStore } from './rhythm'

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import { api_get_health } from '@lib/api'

export interface ServerState {
  serverHealth: boolean
  fetchServerHealth: () => void
}

export const useServerStore: UseBoundStore<StoreApi<ServerState>> = create<ServerState>((set) => ({
  serverHealth: false,
  fetchServerHealth: async () => {
    set({ serverHealth: await api_get_health() })
  },
}))
