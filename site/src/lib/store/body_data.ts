/**
 * @file body_data.ts
 * @brief Body Data (身体数据) zustand store
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 指标注册表优先使用后端 /metrics 动态下发结果（含 x_ 自定义指标），
 * 未加载完成前回退到 BUILTIN_METRICS 镜像（首屏 fallback）。
 * 核心语义：record.data 中不存在某 key = 本次未测量。
 */

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import {
  BUILTIN_METRICS,
  type BodyMetricDef,
  type BodyDataRecord,
  type BodyDataCreateProps,
  type BodyDataUpdateProps,
  type BodyDataSeriesResponse,
  type BodyMetricAnalysisResult,
} from '@lib/data/body_data'
import {
  api_get_body_metrics,
  api_get_body_data_list,
  api_create_body_data,
  api_update_body_data,
  api_delete_body_data,
  api_get_body_series,
  api_analyze_body_metric,
} from '@lib/api/body_data'

export interface BodyDataState {
  // Metric registry (builtin + custom, dynamically discovered by backend)
  metrics: BodyMetricDef[]
  metricsLoaded: boolean
  fetchMetrics: () => Promise<void>

  // Body data records
  records: BodyDataRecord[]
  isLoading: boolean
  currentStartTime: number | null
  currentEndTime: number | null
  setCurrentDateRange: (start: number | null, end: number | null) => void
  fetchRecords: (
    skip?: number,
    limit?: number,
    start?: number,
    end?: number,
    metric?: string
  ) => Promise<void>
  createRecord: (props: BodyDataCreateProps) => Promise<BodyDataRecord>
  updateRecord: (id: number, props: BodyDataUpdateProps) => Promise<BodyDataRecord>
  deleteRecord: (id: number) => Promise<void>

  // Single-metric series cache (key = metric, invalidated on record changes)
  seriesCache: Record<string, BodyDataSeriesResponse>
  fetchSeries: (metric: string, start?: number, end?: number) => Promise<void>

  // Trend analysis for a single metric
  analysisResult: BodyMetricAnalysisResult | null
  analysisMetric: string | null
  fetchAnalysis: (
    metric: string,
    modelType?: string,
    start?: number,
    end?: number
  ) => Promise<void>

  // Helper: look up metric definition (dynamic registry first, then builtin mirror)
  getMetricDef: (key: string) => BodyMetricDef | undefined
}

export const useBodyDataStore: UseBoundStore<StoreApi<BodyDataState>> = create<BodyDataState>(
  (set, get) => ({
    // Metric registry
    metrics: BUILTIN_METRICS,
    metricsLoaded: false,
    fetchMetrics: async () => {
      try {
        const metrics = await api_get_body_metrics()
        set({ metrics: metrics || BUILTIN_METRICS, metricsLoaded: true })
      } catch (error) {
        console.error('Failed to fetch body metrics:', error)
        set({ metrics: BUILTIN_METRICS, metricsLoaded: false })
      }
    },

    // Records
    records: [],
    isLoading: false,
    currentStartTime: null,
    currentEndTime: null,
    setCurrentDateRange: (start: number | null, end: number | null) => {
      set({ currentStartTime: start, currentEndTime: end })
    },
    fetchRecords: async (
      skip: number = 0,
      limit: number = -1,
      start: number = -1,
      end: number = -1,
      metric: string = ''
    ) => {
      set({ isLoading: true })
      try {
        const records = await api_get_body_data_list(skip, limit, start, end, metric)
        set({
          records: records,
          isLoading: false,
          currentStartTime: start > 0 ? start : null,
          currentEndTime: end > 0 ? end : null,
        })
      } catch (error) {
        set({ isLoading: false })
        throw error
      }
    },
    createRecord: async (props: BodyDataCreateProps) => {
      const new_record = await api_create_body_data(props)
      set(
        (state: BodyDataState): BodyDataState => ({
          ...state,
          records: [new_record, ...state.records],
          // Invalidate derived series/analysis caches
          seriesCache: {},
          analysisResult: null,
          analysisMetric: null,
        })
      )
      return new_record
    },
    updateRecord: async (id: number, props: BodyDataUpdateProps) => {
      const updated = await api_update_body_data(id, props)
      set(
        (state: BodyDataState): BodyDataState => ({
          ...state,
          records: state.records.map((r) => (r.id === id ? updated : r)),
          seriesCache: {},
          analysisResult: null,
          analysisMetric: null,
        })
      )
      return updated
    },
    deleteRecord: async (id: number) => {
      await api_delete_body_data(id)
      set(
        (state: BodyDataState): BodyDataState => ({
          ...state,
          records: state.records.filter((r) => r.id !== id),
          seriesCache: {},
          analysisResult: null,
          analysisMetric: null,
        })
      )
    },

    // Series cache
    seriesCache: {},
    fetchSeries: async (metric: string, start?: number, end?: number) => {
      const series = await api_get_body_series(
        metric,
        start ?? -1,
        end ?? -1
      )
      set(
        (state: BodyDataState): BodyDataState => ({
          ...state,
          seriesCache: { ...state.seriesCache, [metric]: series },
        })
      )
    },

    // Analysis
    analysisResult: null,
    analysisMetric: null,
    fetchAnalysis: async (
      metric: string,
      modelType: string = 'linear',
      start?: number,
      end?: number
    ) => {
      const result = await api_analyze_body_metric(metric, modelType, start ?? -1, end ?? -1)
      set({ analysisResult: result, analysisMetric: metric })
    },

    // Helper
    getMetricDef: (key: string): BodyMetricDef | undefined =>
      get().metrics.find((m) => m.key === key),
  })
)

export default useBodyDataStore
