/**
 * @file challenge.ts
 * @brief Challenge Store - Zustand 状态管理
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  type ChallengeCreateProps,
  type ChallengeData,
  type CheckInData,
  type ChallengeStats,
  ChallengeStatus,
  CheckInStatus,
  calculateChallengeStats,
  getTodayMissionId,
  isTodayDay,
} from '@lib/data/challenge'

import {
  api_get_challenges,
  api_get_challenge_detail,
  api_get_active_challenges,
  api_create_challenge,
  api_delete_challenge,
  api_abort_challenge,
  api_check_in_success,
  api_check_in_failed,
  api_reset_check_in,
  api_get_challenge_stats,
} from '@lib/api/challenge'

// ============================================
// State 类型定义
// ============================================

export interface ChallengeState {
  // 数据
  challenges: ChallengeData[]
  activeChallenges: ChallengeData[]
  currentChallenge: ChallengeData | null
  currentCheckIns: CheckInData[]
  currentStats: ChallengeStats | null
  
  // 加载状态
  isLoading: boolean
  isCreating: boolean
  isCheckingIn: boolean
  
  // 错误信息
  error: string | null
}

export interface ChallengeActions {
  // 查询操作
  fetchChallenges: () => Promise<void>
  fetchActiveChallenges: () => Promise<void>
  fetchChallengeDetail: (challengeId: number) => Promise<void>
  fetchChallengeStats: (challengeId: number) => Promise<void>
  
  // 修改操作
  createChallenge: (props: ChallengeCreateProps) => Promise<ChallengeData | null>
  deleteChallenge: (challengeId: number) => Promise<boolean>
  abortChallenge: (challengeId: number) => Promise<boolean>
  
  // 打卡操作
  checkInSuccess: (missionId: number, challengeId: number) => Promise<void>
  checkInFailed: (missionId: number, challengeId: number) => Promise<void>
  resetCheckIn: (missionId: number, challengeId: number) => Promise<void>
  
  // 快捷操作
  getTodayMissionId: () => number | null
  isTodayChecked: () => boolean
  canCheckInToday: () => boolean
  
  // 状态清理
  clearError: () => void
  clearCurrentChallenge: () => void
}

export type ChallengeStore = ChallengeState & ChallengeActions

// ============================================
// Store 创建
// ============================================

export const useChallengeStore: UseBoundStore<StoreApi<ChallengeStore>> = create<ChallengeStore>((set, get) => ({
  // 初始状态
  challenges: [],
  activeChallenges: [],
  currentChallenge: null,
  currentCheckIns: [],
  currentStats: null,
  isLoading: false,
  isCreating: false,
  isCheckingIn: false,
  error: null,

  // ==========================================
  // 查询操作
  // ==========================================

  fetchChallenges: async (): Promise<void> => {
    set({ isLoading: true, error: null })
    try {
      const challenges = await api_get_challenges()
      set({ challenges, isLoading: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch challenges'
      set({ error: errorMsg, isLoading: false })
    }
  },

  fetchActiveChallenges: async (): Promise<void> => {
    set({ isLoading: true, error: null })
    try {
      const activeChallenges = await api_get_active_challenges()
      set({ activeChallenges, isLoading: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch active challenges'
      set({ error: errorMsg, isLoading: false })
    }
  },

  fetchChallengeDetail: async (challengeId: number): Promise<void> => {
    set({ isLoading: true, error: null })
    try {
      const detail = await api_get_challenge_detail(challengeId)
      if (detail) {
        const stats = calculateChallengeStats(
          detail.checkIns,
          detail.challenge.startDate,
          detail.challenge.days
        )
        set({
          currentChallenge: detail.challenge,
          currentCheckIns: detail.checkIns,
          currentStats: stats,
          isLoading: false,
        })
      } else {
        set({ error: 'Challenge not found', isLoading: false })
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to fetch challenge detail'
      set({ error: errorMsg, isLoading: false })
    }
  },

  fetchChallengeStats: async (challengeId: number): Promise<void> => {
    try {
      const stats = await api_get_challenge_stats(challengeId)
      if (stats) {
        set({ currentStats: stats })
      }
    } catch (err) {
      console.error('Failed to fetch challenge stats:', err)
    }
  },

  // ==========================================
  // 修改操作
  // ==========================================

  createChallenge: async (props: ChallengeCreateProps): Promise<ChallengeData | null> => {
    set({ isCreating: true, error: null })
    try {
      const challenge = await api_create_challenge(props)
      set((state) => ({
        challenges: [challenge, ...state.challenges],
        activeChallenges: [challenge, ...state.activeChallenges],
        isCreating: false,
      }))
      return challenge
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to create challenge'
      set({ error: errorMsg, isCreating: false })
      return null
    }
  },

  deleteChallenge: async (challengeId: number): Promise<boolean> => {
    set({ isLoading: true, error: null })
    try {
      const success = await api_delete_challenge(challengeId)
      if (success) {
        set((state) => ({
          challenges: state.challenges.filter((c) => c.id !== challengeId),
          activeChallenges: state.activeChallenges.filter((c) => c.id !== challengeId),
          currentChallenge: state.currentChallenge?.id === challengeId ? null : state.currentChallenge,
          currentCheckIns: state.currentChallenge?.id === challengeId ? [] : state.currentCheckIns,
          currentStats: state.currentChallenge?.id === challengeId ? null : state.currentStats,
          isLoading: false,
        }))
      }
      return success
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to delete challenge'
      set({ error: errorMsg, isLoading: false })
      return false
    }
  },

  abortChallenge: async (challengeId: number): Promise<boolean> => {
    set({ isLoading: true, error: null })
    try {
      const success = await api_abort_challenge(challengeId)
      if (success) {
        // 刷新当前挑战详情
        await get().fetchChallengeDetail(challengeId)
        // 更新挑战列表中的状态
        set((state) => ({
          challenges: state.challenges.map((c) =>
            c.id === challengeId ? { ...c, status: ChallengeStatus.ABORTED } : c
          ),
          activeChallenges: state.activeChallenges.filter((c) => c.id !== challengeId),
          isLoading: false,
        }))
      }
      return success
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to abort challenge'
      set({ error: errorMsg, isLoading: false })
      return false
    }
  },

  // ==========================================
  // 打卡操作
  // ==========================================

  checkInSuccess: async (missionId: number, challengeId: number): Promise<void> => {
    set({ isCheckingIn: true, error: null })
    try {
      await api_check_in_success(missionId)
      // 刷新详情
      await get().fetchChallengeDetail(challengeId)
      set({ isCheckingIn: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to check in'
      set({ error: errorMsg, isCheckingIn: false })
    }
  },

  checkInFailed: async (missionId: number, challengeId: number): Promise<void> => {
    set({ isCheckingIn: true, error: null })
    try {
      await api_check_in_failed(missionId)
      // 刷新详情
      await get().fetchChallengeDetail(challengeId)
      set({ isCheckingIn: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to check in'
      set({ error: errorMsg, isCheckingIn: false })
    }
  },

  resetCheckIn: async (missionId: number, challengeId: number): Promise<void> => {
    set({ isCheckingIn: true, error: null })
    try {
      await api_reset_check_in(missionId)
      // 刷新详情
      await get().fetchChallengeDetail(challengeId)
      set({ isCheckingIn: false })
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to reset check-in'
      set({ error: errorMsg, isCheckingIn: false })
    }
  },

  // ==========================================
  // 快捷查询
  // ==========================================

  getTodayMissionId: (): number | null => {
    const { currentChallenge, currentCheckIns } = get()
    if (!currentChallenge) {
      return null
    }
    return getTodayMissionId(currentCheckIns, currentChallenge.startDate)
  },

  isTodayChecked: (): boolean => {
    const { currentStats } = get()
    return currentStats?.isTodayChecked ?? false
  },

  canCheckInToday: (): boolean => {
    const { currentChallenge, currentStats } = get()
    if (!currentChallenge || !currentStats) {
      return false
    }
    
    // 必须是活跃状态
    if (currentChallenge.status !== ChallengeStatus.ACTIVE) {
      return false
    }
    
    // 必须在挑战天数范围内
    if (currentStats.currentDay < 1 || currentStats.currentDay > currentChallenge.days) {
      return false
    }
    
    return true
  },

  // ==========================================
  // 状态清理
  // ==========================================

  clearError: (): void => {
    set({ error: null })
  },

  clearCurrentChallenge: (): void => {
    set({
      currentChallenge: null,
      currentCheckIns: [],
      currentStats: null,
    })
  },
}))

export default useChallengeStore
