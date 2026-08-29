/**
 * @file pems.ts
 * @brief Personal Energy Management System Store
 * @author sailing-innocent
 * @date 2026-03-01
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type {
  DayViewData,
  TimeSpanViewData,
  EnergyBudgetData,
  InsightData,
  HealthQuickLogProps,
  TimeSpanReviewProps,
} from '@lib/data/pems'
import {
  api_get_day_view,
  api_plan_day,
  api_log_health_on_day,
  api_get_timespan_view,
  api_review_timespan,
  api_get_energy_budget,
  api_get_daily_insights,
  api_get_weekly_insights,
} from '@lib/api/pems'

export interface PemsState {
  // Day view
  dayView: DayViewData | null
  selectedDate: string
  isLoading: boolean
  fetchDayView: (date?: Date | string) => Promise<void>
  planDay: (date?: Date | string) => Promise<void>
  logHealthOnDay: (log: HealthQuickLogProps, date?: Date | string) => Promise<void>

  // Timespan view
  timespanView: TimeSpanViewData | null
  fetchTimespanView: (spanId: number) => Promise<void>
  reviewTimespan: (spanId: number, review: TimeSpanReviewProps) => Promise<void>

  // Energy & insights
  energyBudget: EnergyBudgetData | null
  dailyInsights: InsightData[]
  weeklyInsights: InsightData[]
  fetchEnergyBudget: (date?: Date | string) => Promise<void>
  fetchDailyInsights: (date?: Date | string) => Promise<void>
  fetchWeeklyInsights: (date?: Date | string) => Promise<void>
}

const getTodayString = (): string => new Date().toISOString().split('T')[0]

export const usePemsStore: UseBoundStore<StoreApi<PemsState>> = create<PemsState>((set, get) => ({
  dayView: null,
  selectedDate: getTodayString(),
  isLoading: false,

  fetchDayView: async (date?: Date | string) => {
    const targetDate = date || get().selectedDate
    set({ isLoading: true, selectedDate: typeof targetDate === 'string' ? targetDate : targetDate.toISOString().split('T')[0] })
    try {
      const dayView = await api_get_day_view(targetDate)
      set({ dayView, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      console.error('Failed to fetch day view:', error)
      throw error
    }
  },

  planDay: async (date?: Date | string) => {
    const targetDate = date || get().selectedDate
    try {
      const dayView = await api_plan_day(targetDate)
      set({ dayView })
    } catch (error) {
      console.error('Failed to plan day:', error)
      throw error
    }
  },

  logHealthOnDay: async (log: HealthQuickLogProps, date?: Date | string) => {
    const targetDate = date || get().selectedDate
    try {
      const dayView = await api_log_health_on_day(targetDate, log)
      set({ dayView })
    } catch (error) {
      console.error('Failed to log health:', error)
      throw error
    }
  },

  timespanView: null,
  fetchTimespanView: async (spanId: number) => {
    try {
      const timespanView = await api_get_timespan_view(spanId)
      set({ timespanView })
    } catch (error) {
      console.error('Failed to fetch timespan view:', error)
      throw error
    }
  },
  reviewTimespan: async (spanId: number, review: TimeSpanReviewProps) => {
    try {
      const timespanView = await api_review_timespan(spanId, review)
      set({ timespanView })
    } catch (error) {
      console.error('Failed to review timespan:', error)
      throw error
    }
  },

  energyBudget: null,
  dailyInsights: [],
  weeklyInsights: [],
  fetchEnergyBudget: async (date?: Date | string) => {
    const targetDate = date || get().selectedDate
    try {
      const energyBudget = await api_get_energy_budget(targetDate)
      set({ energyBudget })
    } catch (error) {
      console.error('Failed to fetch energy budget:', error)
      throw error
    }
  },
  fetchDailyInsights: async (date?: Date | string) => {
    const targetDate = date || get().selectedDate
    try {
      const dailyInsights = await api_get_daily_insights(targetDate)
      set({ dailyInsights })
    } catch (error) {
      console.error('Failed to fetch daily insights:', error)
      throw error
    }
  },
  fetchWeeklyInsights: async (date?: Date | string) => {
    const targetDate = date || get().selectedDate
    try {
      const weeklyInsights = await api_get_weekly_insights(targetDate)
      set({ weeklyInsights })
    } catch (error) {
      console.error('Failed to fetch weekly insights:', error)
      throw error
    }
  },
}))

export default usePemsStore
