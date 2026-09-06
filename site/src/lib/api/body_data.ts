/**
 * @file body_data.ts
 * @brief Body Data (身体数据) API
 * @author sailing-innocent
 * @date 2026-09-06
 *
 * 对应后端 BodyDataController（/api/v1/health/body-data）。
 * 核心语义：data JSON 中不存在某 key = 本次未测量。
 */

import { SERVER_URL, API_BASE } from './config'
import {
  type BodyDataRecord,
  type BodyDataCreateProps,
  type BodyDataUpdateProps,
  type BodyDataSeriesResponse,
  type BodyMetricSchemaResponse,
  type BodyMetricAnalysisResult,
} from '@lib/data/body_data'

const BODY_DATA_API_BASE = API_BASE + '/health/body-data'

// ==================== Body Data CRUD APIs ====================

const api_create_body_data = async (props: BodyDataCreateProps): Promise<BodyDataRecord> => {
  try {
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(props),
    })
    if (!response.ok) {
      throw new Error(`Error creating body data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to create body data:', error)
    throw error
  }
}

const api_get_body_data_list = async (
  skip: number = 0,
  limit: number = -1,
  start: number = -1,
  end: number = -1,
  metric: string = ''
): Promise<BodyDataRecord[]> => {
  try {
    const params = new URLSearchParams()
    params.append('skip', skip.toString())
    params.append('limit', limit.toString())
    params.append('start', start.toString())
    params.append('end', end.toString())
    if (metric) {
      params.append('metric', metric)
    }
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/?${params}`)
    if (!response.ok) {
      throw new Error(`Error fetching body data list: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch body data list:', error)
    throw error
  }
}

const api_get_body_data = async (id: number): Promise<BodyDataRecord> => {
  try {
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/${id}`)
    if (!response.ok) {
      throw new Error(`Error fetching body data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch body data:', error)
    throw error
  }
}

const api_update_body_data = async (
  id: number,
  props: BodyDataUpdateProps
): Promise<BodyDataRecord> => {
  try {
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(props),
    })
    if (!response.ok) {
      throw new Error(`Error updating body data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to update body data:', error)
    throw error
  }
}

const api_delete_body_data = async (id: number): Promise<void> => {
  try {
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/${id}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new Error(`Error deleting body data: ${response.statusText}`)
    }
  } catch (error) {
    console.error('Failed to delete body data:', error)
    throw error
  }
}

// ==================== Body Metric Schema / Series / Analysis APIs ====================

const api_get_body_metrics = async (): Promise<BodyMetricSchemaResponse> => {
  try {
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/metrics`)
    if (!response.ok) {
      throw new Error(`Error fetching body metrics: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch body metrics:', error)
    throw error
  }
}

const api_get_body_series = async (
  metric: string,
  start: number = -1,
  end: number = -1
): Promise<BodyDataSeriesResponse> => {
  try {
    const params = new URLSearchParams()
    params.append('metric', metric)
    if (start > 0) params.append('start', start.toString())
    if (end > 0) params.append('end', end.toString())
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/series?${params}`)
    if (!response.ok) {
      throw new Error(`Error fetching body series: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch body series:', error)
    throw error
  }
}

const api_analyze_body_metric = async (
  metric: string,
  modelType: string = 'linear',
  start: number = -1,
  end: number = -1
): Promise<BodyMetricAnalysisResult> => {
  try {
    const params = new URLSearchParams()
    params.append('metric', metric)
    params.append('model_type', modelType)
    if (start > 0) params.append('start', start.toString())
    if (end > 0) params.append('end', end.toString())
    const response = await fetch(`${SERVER_URL}/${BODY_DATA_API_BASE}/analysis?${params}`)
    if (!response.ok) {
      throw new Error(`Error analyzing body metric: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to analyze body metric:', error)
    throw error
  }
}

// prettier-ignore
export {
  api_create_body_data,
  api_get_body_data_list,
  api_get_body_data,
  api_update_body_data,
  api_delete_body_data,
  api_get_body_metrics,
  api_get_body_series,
  api_analyze_body_metric,
}
