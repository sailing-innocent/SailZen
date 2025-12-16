/**
 * @file health.ts
 * @brief My Health Data API
 * @author sailing-innocent
 * @date 2024-12-29
 */

import { SERVER_URL, API_BASE } from './config'
import { type WeightCreateProps, type WeightData, type WeightStatsResponse } from '@lib/data/health'

const HEALTH_API_BASE = API_BASE + '/health'

const api_get_weight = async (index: number): Promise<WeightData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/${index}`)
    if (!response.ok) {
      throw new Error(`Error fetching weight data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weight data:', error)
    throw error
  }
}

const api_get_weights = async (skip: number = 0, limit: number = -1, start: number = -1, end: number = -1): Promise<WeightData[]> => {
  try {
    const api_with_param =
      `${SERVER_URL}/${HEALTH_API_BASE}/weight?skip=` +
      skip.toString() +
      `&limit=` +
      limit.toString() +
      `&start=` +
      start.toString() +
      `&end=` +
      end.toString()
    const response = await fetch(api_with_param)
    if (!response.ok) {
      throw new Error(`Error fetching weights data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weights data:', error)
    throw error
  }
}

const api_get_weights_avg = async (start: number = -1, end: number = -1): Promise<WeightStatsResponse> => {
  try {
    const api_with_param = `${SERVER_URL}/${HEALTH_API_BASE}/weight/avg?start=` + start.toString() + `&end=` + end.toString()
    const response = await fetch(api_with_param)
    if (!response.ok) {
      throw new Error(`Error fetching weights data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to fetch weights data:', error)
    throw error
  }
}

const api_create_weight = async (newWeight: WeightCreateProps): Promise<WeightData> => {
  try {
    const response = await fetch(`${SERVER_URL}/${HEALTH_API_BASE}/weight/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(newWeight),
    })
    if (!response.ok) {
      throw new Error(`Error creating weight data: ${response.statusText}`)
    }
    return response.json()
  } catch (error) {
    console.error('Failed to create weight data:', error)
    throw error
  }
}

// prettier-ignore
export {
  api_get_weight,
  api_get_weights,
  api_create_weight
}
